"""
Scholarships as a finite economic value — the recruiting currency.

A program's scholarship pool is a *budget*, not a headcount: a number of
scholarships whose backend worth is set by an exchange rate that diminishes by
classification. So a D3 scholarship is not worth a D2 one, which is not worth a
D1 one — even though D2 and D3 play at a similar level, the real separator is the
aid a program can put on the table.

Per level (all tunable here, and overridable live from the editor):
  • count       — how many scholarships the program has to give,
  • rate        — exchange rate: what one of its scholarships is worth (D1 = 1.0),
  • fractional  — D1/D2 are equivalency sports: a scholarship splits down to
                  quarters (offer 0.25 / 0.5 / 0.75 / 1.0). D3 awards are whole.

Top-tier (academically elite) D3 programs are special: their scholarships carry
full D1 worth, but they have far fewer of them — so a Swarthmore can win a
recruit on value, it just can't stack a roster of them.

`effective_value = count * rate` is the program's total recruiting spend power,
the single number the recruiting layer can compare across classifications.
"""
from __future__ import annotations

MIN_FRACTION = 0.25                     # smallest slice of a scholarship (D1/D2)
ELITE_D3_ACADEMICS = 0.85              # a D3 this academic awards D1-worth aid

# Default per-classification limits — edit here, or override live via the editor.
DEFAULT_LIMITS = {
    "D1": {"count": 6, "rate": 1.00, "fractional": True},
    "D2": {"count": 5, "rate": 0.70, "fractional": True},
    "D3": {"count": 3, "rate": 0.30, "fractional": False},
}
# Academically elite D3: D1-worth scholarships, but fewer of them.
ELITE_D3_LIMITS = {"count": 4, "rate": 1.00, "fractional": False}

# Live overrides set from the editor: division -> {count?, rate?}.
_overrides: dict[str, dict] = {}


def set_limit(division: str, *, count=None, rate=None) -> None:
    o = _overrides.setdefault(division, {})
    if count is not None:
        o["count"] = max(0, int(count))
    if rate is not None:
        o["rate"] = max(0.0, min(1.0, float(rate)))


def clear_overrides() -> None:
    _overrides.clear()


def any_overrides() -> bool:
    return bool(_overrides)


def get_overrides() -> dict:
    return {d: dict(v) for d, v in _overrides.items()}


def _is_elite_d3(division: str, academics: float) -> bool:
    return division == "D3" and academics >= ELITE_D3_ACADEMICS


def limits(division: str, academics: float = 0.0) -> dict:
    """Resolved scholarship limits for a program: count / rate / fractional /
    effective_value, after the elite-D3 rule and any editor overrides."""
    if _is_elite_d3(division, academics):
        base = dict(ELITE_D3_LIMITS)
        base["elite_d3"] = True
    else:
        base = dict(DEFAULT_LIMITS.get(division, DEFAULT_LIMITS["D3"]))
        base["elite_d3"] = False
    base.update(_overrides.get(division, {}))
    base["effective_value"] = round(base["count"] * base["rate"], 2)
    return base


def program_limits(program) -> dict:
    return limits(program.division, getattr(program, "academics", 0.0))


def slots(program) -> int:
    """How many roster players a program funds with athletic aid — its scholarship
    headcount (the rest of the roster are walk-ons)."""
    return int(round(program_limits(program)["count"]))


def value(program) -> float:
    """Total recruiting spend power (count × exchange rate)."""
    return program_limits(program)["effective_value"]
