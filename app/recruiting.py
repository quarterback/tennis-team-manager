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


GEO_WEIGHT = 0.35           # how strongly home proximity pulls a recruit


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
    division: str = "D1"
    region: str = ""         # coarse geographic region code (for proximity)


def program_appeal(caliber: float, academic01: float, s: School,
                   home_region: str = "") -> float:
    """How appealing program `s` is to a recruit of athletic `caliber` (0..1),
    academic standing `academic01` (0..1), and home region `home_region`.

    Three pulls combine:
      • athletic — programs near the recruit's level fit, and prestige programs
        actively court higher-caliber talent (brand pull).
      • academic — meaningful only when BOTH recruit and school are strong
        academically, so a smart, strong kid is genuinely drawn to an Ivy /
        NESCAC / academy even though its athletic tier is lower.
      • geography — recruits lean toward programs near home (same state/region),
        a real factor especially below the blue-chip tier.
    """
    from app.ncaa import region_proximity
    prox = 1.0 - abs(s.prestige - caliber)
    athletic = 0.6 * prox + 0.4 * (s.prestige * caliber)
    academic = s.academics * academic01
    geo = region_proximity(home_region, s.region)
    return max(0.0, athletic) * (1.0 + 0.9 * academic) * (1.0 + GEO_WEIGHT * geo)


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
    """Visible athletic caliber on a 0..1 scale."""
    return max(0.0, min(1.0, (p.current_overall() - 20) / 60.0))


def recruit_academic01(p) -> float:
    """Academic standing on 0..1 from the 59-99 admissions index."""
    return max(0.0, min(1.0, (getattr(p, "academic_rating", 79) - 59) / 40.0))


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

    def fit(s: School) -> float:
        return program_appeal(caliber, academic01, s, hr)

    fmax = max((fit(s) for s in schools), default=1.0) or 1.0
    ranked = sorted(schools, key=lambda s: fit(s) + rng.uniform(-0.05, 0.05) * fmax, reverse=True)
    n = min(_offer_count(stars, rng), len(ranked))
    chosen = ranked[:n]

    # StrikePrediction: softmax-ish share over the top contenders only.
    contenders = chosen[: min(5, len(chosen))]
    raw = [max(0.01, fit(s) / fmax) ** 3 for s in contenders]
    tot = sum(raw) or 1.0
    shares = [int(round(100 * r / tot)) for r in raw]

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
        offers.append(Offer(
            school=s.name, abbr=s.abbr, color=s.color, offered=True,
            interest=_interest(fit(s) / fmax, rng), strikeprediction=pct, status=status,
        ))

    # Dreamsheet: the recruit's aspirational picks — top programs by combined
    # athletic prestige + academic draw, tagged when they've actually offered.
    offered_names = {o.school for o in offers}
    dream_src = sorted(schools, key=lambda s: s.prestige + 0.6 * s.academics,
                       reverse=True)[: max(3, 2 + stars // 2)]
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
