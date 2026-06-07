"""
Scholarship economy — equivalency-sport budgets, fractional offers, per-division
caps.

Ported in spirit from o27v2's `economy.py` (per-team budgets + a demand curve),
but recast for the thing college tennis actually runs on: **scholarship
equivalencies**, not money. There is no currency here by design — a coach does
not spend dollars, they spend fractions of a fixed scholarship allotment, and
the allotment differs by division and gender (the real NCAA equivalency limits).

The model
---------
  * Every (division, gender) has a hard **cap** — the total scholarship
    equivalency a program may field at once. These are the real NCAA numbers:
        D1 men 4.5   D1 women 8.0
        D2 men 4.5   D2 women 6.0
        D3 men 0.0   D3 women 0.0   (no athletic aid — "commitment slots")
  * An offer is a **fraction** of a full ride: full / half / quarter / sixth.
    A program splits its cap across its recruited core, so a D1 men's roster
    is a handful of full rides plus a couple of partials — not eight full
    scholarships.
  * `allocate_scholarships()` distributes the cap down a sorted roster, best
    player first, taking the largest affordable fraction each time. It is the
    one place that decides both `scholarship` (the fraction) and `walk_on`
    (roster filler, unchanged from the prior binary model so league/portal
    logic and existing tests keep their meaning).
  * D3 carries no athletic money, but its recruited core are still *recruited*
    (not walk-ons). A `prestige_pull()` multiplier is the lever that lets a
    top-academic D3 / Ivy out-recruit a lesser scholarship program for the
    right player (see docs/DESIGN §5).

Everything is deterministic and stateless: the same roster + division + gender
always allocates the same way, so it composes with the seeded roster builder
without persisting anything of its own.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Fractional offers
# ---------------------------------------------------------------------------

FULL    = 1.0
HALF    = 0.5
QUARTER = 0.25
SIXTH   = round(1.0 / 6.0, 4)        # 0.1667 — the smallest equivalency offer

# Largest → smallest; the greedy allocator walks this list.
OFFER_FRACTIONS: tuple[float, ...] = (FULL, HALF, QUARTER, SIXTH)

# Human labels for display.
FRACTION_LABELS: dict[float, str] = {
    FULL: "Full", HALF: "½", QUARTER: "¼", SIXTH: "⅙", 0.0: "—",
}

# A tiny epsilon so floating-point dust never blocks an exactly-affordable offer.
_EPS = 1e-6


# ---------------------------------------------------------------------------
# Per-division × gender caps (real NCAA equivalency limits)
# ---------------------------------------------------------------------------

SCHOLARSHIP_CAPS: dict[tuple[str, str], float] = {
    ("D1", "men"):   4.5,
    ("D1", "women"): 8.0,
    ("D2", "men"):   4.5,
    ("D2", "women"): 6.0,
    ("D3", "men"):   0.0,
    ("D3", "women"): 0.0,
}

# Prestige pull for the no-money tier: a top D3 / Ivy program still wins the
# right recruit on academics + brand. Applied as a recruiting-fit multiplier,
# NOT a scholarship — D3 athletic aid stays zero.
PRESTIGE_PULL: dict[str, float] = {
    "IVY": 1.35,        # Ivy academics carry the offer
    "P5":  1.10,        # marquee brand
    "MID": 1.0,
}


def _norm_division(division: str) -> str:
    """Accept 'd1' / 'D1' / 'Division I' loosely; fall back to 'D1'."""
    d = (division or "").strip().lower()
    if d in ("d1", "i", "division i", "1"):
        return "D1"
    if d in ("d2", "ii", "division ii", "2"):
        return "D2"
    if d in ("d3", "iii", "division iii", "3"):
        return "D3"
    return (division or "D1").upper()


def _norm_gender(gender: str) -> str:
    g = (gender or "").strip().lower()
    if g in ("men", "male", "m", "boys"):
        return "men"
    if g in ("women", "female", "w", "f", "girls"):
        return "women"
    return g or "men"


def cap_for(division: str, gender: str) -> float:
    """Scholarship-equivalency cap for a (division, gender).

    Sourced from `app.scholarships`, which owns the editable per-(division,
    gender) limits — so a cap edited live in the editor flows straight through
    the fractional allocation here. The module-level `SCHOLARSHIP_CAPS` below is
    the documented baseline / fallback if scholarships can't be imported."""
    try:
        from app import scholarships
        return scholarships.cap(division, gender)
    except Exception:
        return SCHOLARSHIP_CAPS.get(
            (_norm_division(division), _norm_gender(gender)), 4.5
        )


def offers_aid(division: str, gender: str) -> bool:
    """True when the division funds athletic scholarships at all (D1/D2)."""
    return cap_for(division, gender) > 0.0


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------

def _largest_affordable(remaining: float) -> float:
    """The biggest offer fraction that still fits in `remaining`, or 0.0."""
    for f in OFFER_FRACTIONS:
        if f <= remaining + _EPS:
            return f
    return 0.0


def allocate_scholarships(roster: list, division: str, gender: str,
                          *, scholarship_slots: int) -> None:
    """Stamp `scholarship` (equivalency fraction) and `walk_on` on every player
    in `roster`, in place.

    `roster` must be pre-sorted best → worst. The top `scholarship_slots`
    players are the recruited core (`walk_on = False`); the rest are walk-ons
    (`walk_on = True`, `scholarship = 0.0`) — this preserves the binary model
    league/portal logic depends on. The division cap is then spread across the
    recruited core, best player first, largest affordable fraction each time.

    D3 (cap 0) leaves the recruited core at `scholarship = 0.0` but still
    non-walk-on: they are committed roster members on no athletic aid.
    """
    cap = cap_for(division, gender)
    remaining = cap
    for idx, pr in enumerate(roster):
        is_core = idx < scholarship_slots
        pr.walk_on = not is_core
        if not is_core or cap <= 0.0:
            pr.scholarship = 0.0
            continue
        frac = _largest_affordable(remaining)
        pr.scholarship = frac
        remaining = max(0.0, remaining - frac)


def budget_summary(roster: list, division: str, gender: str) -> dict:
    """Program scholarship ledger for the team page: cap, how much is committed,
    what's left, and the offer breakdown."""
    cap = cap_for(division, gender)
    allocated = round(sum(getattr(p, "scholarship", 0.0) or 0.0 for p in roster), 4)
    fulls = sum(1 for p in roster if abs(getattr(p, "scholarship", 0.0) - FULL) < _EPS)
    partials = sum(1 for p in roster
                   if 0.0 < getattr(p, "scholarship", 0.0) < FULL - _EPS)
    walk_ons = sum(1 for p in roster if getattr(p, "walk_on", False))
    return {
        "cap": cap,
        "allocated": allocated,
        "remaining": round(max(0.0, cap - allocated), 4),
        "offers_aid": cap > 0.0,
        "full_rides": fulls,
        "partials": partials,
        "walk_ons": walk_ons,
    }


def fraction_label(fraction: float) -> str:
    """'Full' / '½' / '¼' / '⅙' / '—' for a stored fraction (snaps to nearest
    canonical offer so float dust still labels cleanly)."""
    f = float(fraction or 0.0)
    if f <= _EPS:
        return FRACTION_LABELS[0.0]
    nearest = min(OFFER_FRACTIONS, key=lambda c: abs(c - f))
    return FRACTION_LABELS.get(nearest, f"{f:.2f}")


# ---------------------------------------------------------------------------
# Recruiting integration — what a program would offer a target
# ---------------------------------------------------------------------------

def prestige_pull(tier: str) -> float:
    """Recruiting-fit multiplier for a program tier — the lever that lets
    Ivy / top-D3 compete without scholarship money."""
    return PRESTIGE_PULL.get((tier or "MID").upper(), 1.0)


def offered_fraction(division: str, gender: str, caliber: float) -> float:
    """The scholarship fraction a program in this division would put in front of
    a recruit of `caliber` (0..1 visible ability). Blue-chips draw full rides at
    a funded program; mid-tier recruits draw partials; everyone draws 0 where
    the division offers no aid (D3). Deterministic — no RNG, it's a sticker
    price, not a roll."""
    if not offers_aid(division, gender):
        return 0.0
    c = max(0.0, min(1.0, caliber))
    if c >= 0.78:
        return FULL
    if c >= 0.55:
        return HALF
    if c >= 0.32:
        return QUARTER
    return SIXTH
