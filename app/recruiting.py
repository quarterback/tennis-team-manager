"""
Recruiting interest model — the College List / Dreamsheet / Timeline surfaces.

Mirrors the viperball recruit-profile layout on top of tennis's existing
consensus-ranking board (app.juniors). For a given prospect it deterministically
synthesises:

  • College List — schools that have shown interest / offered, each with an
    interest temperature (Hot / Warm / Cold), a StrikePrediction commit-% for
    the contenders, and a status badge (Finalist / Top School).
  • Dreamsheet — the aspirational schools the recruit themselves favours
    (high-prestige programs), tagged when they've actually offered.
  • Timeline — a believable chronology of the cycle (early interest → offers
    → official visits → narrowing the list).
  • A headline StrikePrediction: the current commit favourite + percentage.

Everything is seeded off the prospect's stable `pid`, so a recruit's board is
reproducible across requests without persisting anything. Stronger recruits
(more stars) draw deeper, higher-prestige boards; fringe recruits draw thin
ones — the realistic shape where blue-chips hold 14 offers and a 3-star holds 3.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

# Interest temperature buckets (label, ordering weight for display).
_HOT, _WARM, _COLD = "Hot", "Warm", "Cold"


GEO_WEIGHT = 0.55           # max home-proximity pull, at homecooking=1, same region
FAC_WEIGHT = 0.25           # how much a program's facilities grade lifts appeal
# Coach-side localism: a program whose coach recruits the backyard pulls in-region
# recruits harder, on top of the recruit's own homecooking. Max lift (a full homer,
# same region) = this weight; it fades with region proximity and the coach's lean.
COACH_LOCAL_WEIGHT = 0.50

# Island-territory / remote-state home pull. Coarse STATE_REGION proximity is 0 for
# PR/USVI/Guam (they aren't in the region map), so nothing binds a Puerto Rican kid
# to a Puerto Rico school. This is a DIRECT same-territory tug that only fires for a
# recruit whose home state/territory is one an ncaa.SCHOOL_LOCAL_TERRITORY program
# recruits — scaled by that program's local share — so general recruiting is
# untouched. Strong enough that in-range locals sign home; elite locals still escape
# to the mainland (a low-prestige D2's score can't out-pull a power even ×this), and
# the thin island pools self-limit, so those rosters end up local-heavy but not
# hermetic. Mirrors the year-0 base-roster tilt into the ongoing sim.
LOCAL_TERRITORY_PULL = 6.0

# Academics only pull a recruit BELOW their athletic station, and only for
# sub-elite talent. A blue-chip's ceiling commands a marquee program, so for
# them prestige trumps academics outright (gate → 0 at/above the elite line);
# the further a recruit sits below it, the more a strong GPA can tug them toward
# an academic program a level beneath their athletic station.
ELITE_CALIBER = 0.70        # ~5★/blue-chip line (overall ~62): academics never move them
FOUR_STAR = 0.55            # ~4★ line (overall ~53)
ACA_PULL = 2.5              # academic weight once gated (a strong-GPA 3★ still leans academic)


def academic_gate(caliber: float) -> float:
    """How much academics may pull a recruit. Academic programs (Ivy/NESCAC/UAA)
    land 3-stars and only the RARE 4-star — never a 5-star/blue-chip. The gate is
    full for 3★ and below, a thin sliver across the 4★ band, and exactly 0 at or
    above the elite line."""
    if caliber >= ELITE_CALIBER:                 # 5★/blue-chip: prestige rules, period
        return 0.0
    if caliber >= FOUR_STAR:                      # 4★: thin pull, fading to 0 at the elite line
        return 0.15 * (ELITE_CALIBER - caliber) / (ELITE_CALIBER - FOUR_STAR)
    return 1.0                                    # 3★ and below: full academic consideration


# --- International share of a base roster, by level, academics and gender ---------
# Calibrated to real NCAA tennis roster patterns (see recruiting guides): the
# international share is driven by ATHLETIC level (top D1 men 70-90%, mid-major
# 40-70%, strong D2 30-60%, lower tiers US-heavy), pulled DOWN hard by academics (a
# high-academic program — Ivy/NESCAC/UAA — recruits US merit and runs 10-25%
# regardless of athletic brand), and lower for women (≈30% less international than
# men at the same level).
# division -> (share at the prestige ref for a non-academic program, prestige slope,
#              prestige ref). Athletic prestige swings it within a division.
_INTL_BASE = {
    "D1": (0.51, 0.57, 0.60),   # power ~0.65, mid-major ~0.45 — Americans stay viable up top
    "D2": (0.46, 0.55, 0.25),
    "D3": (0.17, 0.30, 0.14),
    "D4": (0.17, 0.30, 0.14),
}
_WOMEN_INTL_FACTOR = 0.72       # women's rosters run ~30% less international than men's
_ACADEMIC_INTL_KNEE = 0.60      # academics at/below this don't damp the share
_ACADEMIC_INTL_DAMP = 1.9       # how hard academics above the knee pull toward US merit
_ACADEMIC_INTL_FLOOR = 0.20     # the strongest academic damp still leaves this multiple
# The onboarding "international share" dial now also tilts the BASE roster (it used to move
# only the recruit class, which is why a global world felt impossible to get). Additive from
# the 0.30 baseline so the DEFAULT is a NO-OP (no calibration change); raising it pushes the
# whole world global — at 0.80 a top program lands ~US 20% (tour-like), lower keeps US-heavy.
_INTL_BASELINE = 0.30
_INTL_GLOBAL_TILT = 0.70


def intl_share_for(division: str, gender: str = "men", prestige: float = 0.5,
                   academics: float = 0.5) -> float:
    """Target international fraction of a program's base roster (0..1). Athletic level
    (division + prestige) sets it; academics damps it toward US merit; women lower; then the
    world's international-share dial tilts the whole thing global (default 0.30 = unchanged)."""
    base, slope, ref = _INTL_BASE.get(division, (0.30, 0.40, 0.30))
    intl = base + slope * (float(prestige) - ref)
    damp = 1.0 - _ACADEMIC_INTL_DAMP * max(0.0, float(academics) - _ACADEMIC_INTL_KNEE)
    intl *= max(_ACADEMIC_INTL_FLOOR, damp)
    if gender == "women":
        intl *= _WOMEN_INTL_FACTOR
    from app import worldconfig
    intl += (worldconfig.intl_share() - _INTL_BASELINE) * _INTL_GLOBAL_TILT
    return max(0.03, min(0.92, intl))


# How strongly base rosters lean on home turf: the share of a program's DOMESTIC
# recruits drawn from its own region. Applies to EVERY program — prestige drives
# player quality and the international share, not how regional the domestic pool is.
LOCAL_REGION_TARGET = 0.70


@dataclass
class School:
    """A program the recruiting model can reason about."""
    name: str
    strength: float          # 0..1 athletic level (normalised Power Index / latent)
    tier: str                # 'P5' | 'MID' | 'IVY' | 'D2' | 'D3'
    abbr: str = ""
    color: str = ""
    prestige: float = 0.50   # athletic brand pull
    academics: float = 0.50  # academic profile
    facilities: float = 0.50 # facilities grade
    division: str = "D1"
    region: str = ""         # coarse geographic region code (for proximity)


def program_appeal(caliber: float, academic01: float, s: School,
                   home_region: str = "", homecooking: float = 0.0) -> float:
    """How appealing program `s` is to a recruit of athletic `caliber` (0..1),
    academic standing `academic01` (0..1), home region `home_region`, and
    `homecooking` (0..1 desire to stay near home).

    Three pulls combine:
      • athletic — programs near the recruit's level fit, and prestige programs
        actively court higher-caliber talent (brand pull).
      • academic — gated by talent (see `academic_gate`): top-tier recruits are
        ruled by prestige and ignore it, so a strong-GPA but SUB-elite kid is the
        one genuinely drawn to an Ivy / NESCAC / academy a level beneath their
        athletic station.
      • geography — ONE-WAY: a recruit who values home (high homecooking) leans
        toward nearby programs that fit; programs don't seek locals. Internationals
        have homecooking 0, so geography never moves them.
    """
    from app.ncaa import region_proximity
    prox = 1.0 - abs(s.prestige - caliber)
    athletic = 0.6 * prox + 0.4 * (s.prestige * caliber)
    academic = s.academics * academic01 * academic_gate(caliber)
    geo = homecooking * region_proximity(home_region, s.region)
    return (max(0.0, athletic) * (1.0 + ACA_PULL * academic)
            * (1.0 + GEO_WEIGHT * geo) * (1.0 + FAC_WEIGHT * s.facilities))


# Full US state name → coarse region code (recruits store the full state name).
def home_region(p) -> str:
    if not getattr(p, "domestic", False):
        return ""
    from app.ncaa import STATE_REGION
    from app.juniors import US_STATES
    code = dict(US_STATES).get(getattr(p, "region", ""), "")
    return STATE_REGION.get(code, "")


def schools_from_programs(programs, *, pi: dict | None = None) -> list["School"]:
    """Build recruiting Schools from ncaa.Program objects, carrying prestige,
    academics and region. `pi` optionally maps school→Power Index for the
    athletic level; otherwise the program's latent strength is used."""
    from app.ncaa import crest
    out: list[School] = []
    for p in programs:
        abbr, color = crest(p.school)
        level = pi.get(p.school) if pi else None
        out.append(School(
            name=p.school, strength=float(level if level is not None else p.strength),
            tier=p.division, abbr=abbr, color=color,
            prestige=getattr(p, "prestige", 0.5), academics=getattr(p, "academics", 0.5),
            facilities=getattr(p, "facilities", 0.5),
            division=p.division, region=getattr(p, "region", ""),
        ))
    return out


@dataclass
class Offer:
    school: str
    abbr: str
    color: str
    offered: bool
    interest: str            # Hot / Warm / Cold
    strikeprediction: int    # commit-% (0 when not a contender)
    status: str              # 'Finalist' | 'Top School' | ''
    scholarship: float = 0.0    # equivalency fraction the program put on the table
    scholarship_label: str = "—"


@dataclass
class TimelineEvent:
    label: str
    kind: str                # early_contact | offers | visits | narrowing
    week: int


@dataclass
class RecruitingProfile:
    offers: list[Offer] = field(default_factory=list)
    dreamsheet: list[Offer] = field(default_factory=list)
    timeline: list[TimelineEvent] = field(default_factory=list)
    predicted_school: str = ""
    predicted_pct: int = 0
    n_offers: int = 0


# Target offer count by star rating — blue-chips get courted by everyone, a
# 3-star by a handful. (stars -> (min, max)).
_OFFER_BAND = {5: (11, 16), 4: (7, 11), 3: (4, 8), 2: (2, 5), 1: (1, 3), 0: (0, 2)}


def _offer_count(stars: int, rng: random.Random) -> int:
    lo, hi = _OFFER_BAND.get(int(stars), (1, 3))
    return rng.randint(lo, hi)


def _interest(fit: float, rng: random.Random) -> str:
    """Temperature from mutual fit + jitter."""
    roll = fit + rng.uniform(-0.18, 0.18)
    return _HOT if roll >= 0.62 else _WARM if roll >= 0.38 else _COLD


def recruit_caliber(p) -> float:
    """TRUE athletic caliber on a 0..1 scale (visible current ability). This is the
    hidden truth — only the owner sees it (editor / scout_intel). The AI's
    recruiting must NOT key on this; use `perceived_caliber` instead. See
    docs/AAR-fog-of-war-recruiting.md."""
    return max(0.0, min(1.0, (p.current_overall() - 20) / 60.0))


# ---------------------------------------------------------------------------
# Fog-of-war recruiting — what a PROGRAM perceives, never the hidden truth.
# Two public signals every team sees, plus a per-coach blend. The whole AI
# recruiting matrix runs on these so computer programs get fooled exactly like
# real ones; the owner alone sees the truth (recruit_caliber / scout_intel).
# ---------------------------------------------------------------------------
def talent_caliber(p) -> float:
    """The recruiting service's STAR read: a NOISY projection of the recruit's
    ceiling (scouting_report's jittered 'feel'), on the 0..1 caliber scale.
    Sometimes dead-on, sometimes badly off — that's the point. Stars are built on
    this; performance (below) is a separate axis."""
    return max(0.0, min(1.0, (p.scouting_report("service") - 20) / 60.0))


def perf_caliber(p) -> float:
    """The recruit's PERFORMANCE read: their results-based junior STR (band
    31..57) mapped to the 0..1 caliber scale. 0 for anyone with no junior-circuit
    record. Pure performance — what they actually DID, not what they might become."""
    js = float(getattr(p, "junior_str", 0.0) or 0.0)
    return max(0.0, min(1.0, (js - 31.0) / 26.0))


def perceived_caliber(p, results_bias: float = 0.5) -> float:
    """How a program weighing `results_bias` sees this recruit: 0 = trust the
    service's stars (talent projection), 1 = trust the junior results
    (performance). The AI recruiting matrix runs on this — so the same kid is a
    steal to a tape-trusting program and a reach to a stars-trusting one, and each
    gets fooled in its own way.

    A program can only trust results that EXIST: the performance weight is scaled
    by `junior_str_reliability` (0 with no record → 1 with a thick one), so a kid
    with a thin/absent junior résumé is judged on the star projection even by a
    tape-trusting staff. Without this, an unproven recruit reads as half-caliber and
    genuinely good kids go unsigned."""
    b = max(0.0, min(1.0, results_bias))
    rel = max(0.0, min(1.0, float(getattr(p, "junior_str_reliability", 0.0) or 0.0)))
    w = b * rel                                  # how much THIS read leans on results
    return (1.0 - w) * talent_caliber(p) + w * perf_caliber(p)


def consensus_caliber(p) -> float:
    """The market's balanced read (stars-vs-results even) — used for a recruit's
    own sense of their level (who they aspire to) where no single program's
    philosophy applies."""
    return perceived_caliber(p, 0.5)


def recruit_academic01(p) -> float:
    """Academic standing on 0..1 from the 59-99 admissions index."""
    return max(0.0, min(1.0, (getattr(p, "academic_rating", 79) - 59) / 40.0))


def recruit_geo_prefs(p) -> tuple[bool, bool]:
    """(prefers_warm, prefers_big_city) for a recruit — deterministic from their pid,
    so no schema/persistence change. ~half prefer warmth, ~40% prefer a big city. These
    are marginal tiebreakers in the signing model (see world._pick_school)."""
    rng = random.Random(f"{getattr(p, 'pid', '')}|geopref")
    return rng.random() < 0.5, rng.random() < 0.4


def academic_sat(rating) -> int | None:
    """The 59-99 admissions index shown on the real SAT 800-1600 scale (59→800,
    99→1600), rounded to the nearest 10 like a real score. `None` for missing."""
    if rating is None:
        return None
    r = max(59, min(99, int(rating)))
    return int(round((800.0 + (r - 59) / 40.0 * 800.0) / 10.0) * 10)


def build_recruiting(p, schools: list[School], *, seed_salt: str = "") -> RecruitingProfile:
    """Deterministic recruiting board for prospect `p` over `schools` (which may
    span every division — one national pool). Offers + commit favourite are
    ranked by prestige+academics appeal, so high-academic talent surfaces Ivy /
    NESCAC / academy offers alongside (or above) low-major athletic options."""
    if not schools:
        return RecruitingProfile()
    rng = random.Random(f"{getattr(p, 'pid', '')}|recruiting|{seed_salt}")
    stars = int(getattr(p, "recruit_stars", 0) or 0)
    caliber = recruit_caliber(p)
    academic01 = recruit_academic01(p)
    hr = home_region(p)
    hc = float(getattr(p, "homecooking", 0.0))

    def fit(s: School) -> float:
        return program_appeal(caliber, academic01, s, hr, hc)

    fmax = max((fit(s) for s in schools), default=1.0) or 1.0
    ranked = sorted(schools, key=lambda s: fit(s) + rng.uniform(-0.05, 0.05) * fmax, reverse=True)
    n = min(_offer_count(stars, rng), len(ranked))
    chosen = ranked[:n]

    # StrikePrediction: softmax-ish share over the top contenders only.
    contenders = chosen[: min(5, len(chosen))]
    raw = [max(0.01, fit(s) / fmax) ** 3 for s in contenders]
    tot = sum(raw) or 1.0
    shares = [int(round(100 * r / tot)) for r in raw]

    from app import economy
    gender = getattr(p, "gender", "male")

    def _aid(s: School) -> tuple[float, str]:
        """Scholarship a program of this tier would offer the recruit. The
        ranking board is the D1 universe; a non-aid program (modelled via its
        prestige tier) instead leans on brand, surfaced as a label."""
        frac = economy.offered_fraction("D1", gender, caliber)
        if frac <= 0:
            return 0.0, "Prestige"
        return frac, economy.fraction_label(frac)

    offers: list[Offer] = []
    for i, s in enumerate(chosen):
        is_contender = i < len(contenders)
        pct = shares[i] if is_contender else 0
        if i == 0:
            status = "Finalist"
        elif i < 3 and is_contender:
            status = "Finalist"
        elif i < 5 and is_contender:
            status = "Top School"
        else:
            status = ""
        frac, frac_label = _aid(s)
        offers.append(Offer(
            school=s.name, abbr=s.abbr, color=s.color, offered=True,
            interest=_interest(fit(s) / fmax, rng), strikeprediction=pct, status=status,
            scholarship=frac, scholarship_label=frac_label,
        ))

    # Dreamsheet: the recruit's aspirational picks. Aspirations chase BRAND —
    # weighted by prestige, with academics gated by talent (an elite recruit
    # dreams of powerhouses, not academies) and a per-recruit jitter so two
    # blue-chips don't surface the identical four schools.
    offered_names = {o.school for o in offers}
    gate = academic_gate(caliber)
    dream_src = sorted(
        schools,
        key=lambda s: s.prestige + 0.6 * s.academics * gate + rng.uniform(-0.09, 0.09),
        reverse=True,
    )[: max(3, 2 + stars // 2)]
    dreamsheet = [
        Offer(school=s.name, abbr=s.abbr, color=s.color,
              offered=s.name in offered_names, interest="", strikeprediction=0, status="")
        for s in dream_src
    ]

    timeline = _build_timeline(offers, rng)
    predicted = offers[0] if offers else None
    return RecruitingProfile(
        offers=offers, dreamsheet=dreamsheet, timeline=timeline,
        predicted_school=predicted.school if predicted else "",
        predicted_pct=predicted.strikeprediction if predicted else 0,
        n_offers=len(offers),
    )


def _build_timeline(offers: list[Offer], rng: random.Random) -> list[TimelineEvent]:
    """Synthesise a believable recruiting chronology from the offer board."""
    if not offers:
        return []
    ev: list[TimelineEvent] = []
    early = offers[: min(3, len(offers))]
    for o in early:
        ev.append(TimelineEvent(f"Received interest from {o.school}",
                                "early_contact", rng.randint(1, 5)))
    for o in offers[: min(4, len(offers))]:
        ev.append(TimelineEvent(f"Offered by {o.school}", "offers", rng.randint(8, 15)))
    finalists = [o for o in offers if o.status == "Finalist"]
    for o in finalists[:2]:
        ev.append(TimelineEvent(f"Official visit to {o.school}", "visits", rng.randint(16, 19)))
    if len(offers) >= 5:
        ev.append(TimelineEvent(f"Narrowed list to {min(5, len(finalists) or 5)} schools",
                                "narrowing", rng.randint(19, 21)))
    ev.sort(key=lambda e: e.week)
    return ev


def schools_from_rank_rows(rows) -> list[School]:
    """Adapt app.web.rankings_data.RankRow rows into recruiting Schools.
    PI is already ~0..1; tier/crest carry straight over."""
    from app.web.rankings_data import crest
    out: list[School] = []
    for r in rows:
        abbr, color = crest(r.school)
        out.append(School(name=r.school, strength=float(r.pi), tier=r.tier,
                          abbr=abbr, color=color))
    return out
