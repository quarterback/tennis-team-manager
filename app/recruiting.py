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


@dataclass
class School:
    """A program the recruiting model can reason about."""
    name: str
    strength: float          # 0..1 prestige (normalised Power Index)
    tier: str                # 'P5' | 'MID' | 'IVY'
    abbr: str = ""
    color: str = ""


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


def build_recruiting(p, schools: list[School], *, seed_salt: str = "") -> RecruitingProfile:
    """Deterministic recruiting board for prospect `p` over `schools`."""
    if not schools:
        return RecruitingProfile()
    rng = random.Random(f"{getattr(p, 'pid', '')}|recruiting|{seed_salt}")
    stars = int(getattr(p, "recruit_stars", 0) or 0)
    # Recruit caliber on a 0..1 scale (visible current ability).
    caliber = max(0.0, min(1.0, (p.current_overall() - 20) / 60.0))

    # Mutual fit: a recruit and a program fit when their levels are close;
    # prestige programs also lean toward higher-caliber recruits.
    def fit(s: School) -> float:
        proximity = 1.0 - abs(s.strength - caliber)
        pull = 0.65 * proximity + 0.35 * (1.0 - abs(s.strength - caliber) ** 1.5)
        return max(0.0, min(1.0, pull))

    ranked = sorted(schools, key=lambda s: fit(s) + rng.uniform(-0.05, 0.05), reverse=True)
    n = min(_offer_count(stars, rng), len(ranked))
    chosen = ranked[:n]

    # StrikePrediction: softmax-ish share over the top contenders only.
    contenders = chosen[: min(5, len(chosen))]
    raw = [max(0.01, fit(s)) ** 3 for s in contenders]
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
            interest=_interest(fit(s), rng), strikeprediction=pct, status=status,
            scholarship=frac, scholarship_label=frac_label,
        ))

    # Dreamsheet: the recruit's aspirational picks — the most prestigious
    # programs overall, tagged when they've actually offered.
    offered_names = {o.school for o in offers}
    dream_src = sorted(schools, key=lambda s: s.strength, reverse=True)[: max(3, 2 + stars // 2)]
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
