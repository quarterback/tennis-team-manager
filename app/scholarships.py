"""
Scholarships as a finite economic value — the recruiting currency.

A program's scholarship pool is a *budget*, not a headcount: a number of
scholarships whose backend worth is set by an exchange rate that diminishes by
classification. So a D3 scholarship is not worth a D2 one, which is not worth a
D1 one — even though D2 and D3 play at a similar level, the real separator is the
aid a program can put on the table.

Limits are keyed by **(classification, gender)** because the real sport is:
women's tennis is a headcount sport (D1 women carry 8 full rides) while men's is
an equivalency sport (D1 men split 4.5). Each cell carries:
  • count       — funded roster slots (the rest of the roster are walk-ons),
  • rate        — exchange rate: what one of its scholarships is worth (D1 = 1.0),
  • cap         — total scholarship *equivalency* (the gender-real number:
                  D1 men 4.5 / women 8.0). app.economy splits this into the
                  per-player fractional offers,
  • fractional  — D1/D2 are equivalency sports (offers split to quarters);
                  D3 awards are whole (and worth zero athletic aid).

Top-tier (academically elite) D3 programs are special: their scholarships carry
full D1 worth, but they have far fewer of them — so a Swarthmore can win a
recruit on value, it just can't stack a roster of them.

`effective_value = count * rate` is the program's total recruiting spend power,
the single number the recruiting layer can compare across classifications.

All limits are editable live from the editor — per classification AND per
gender — via `set_limit(division, gender=…, count=…, rate=…, cap=…)`.
"""
from __future__ import annotations

MIN_FRACTION = 0.25                     # smallest slice of a scholarship (D1/D2)
ELITE_D3_ACADEMICS = 0.85              # a D3 this academic awards D1-worth aid

GENDERS = ("men", "women")

# Default per-(classification, gender) limits — edit here, or override live via
# the editor. The `cap` column is the real NCAA equivalency total per gender.
DEFAULT_LIMITS = {
    ("D1", "men"):   {"count": 6, "rate": 1.00, "cap": 4.5, "fractional": True},
    ("D1", "women"): {"count": 8, "rate": 1.00, "cap": 8.0, "fractional": True},
    ("D2", "men"):   {"count": 5, "rate": 0.70, "cap": 4.5, "fractional": True},
    ("D2", "women"): {"count": 6, "rate": 0.70, "cap": 6.0, "fractional": True},
    ("D3", "men"):   {"count": 3, "rate": 0.30, "cap": 0.0, "fractional": False},
    ("D3", "women"): {"count": 3, "rate": 0.30, "cap": 0.0, "fractional": False},
}
# Academically elite D3: D1-worth scholarships, but fewer of them.
ELITE_D3_LIMITS = {"count": 4, "rate": 1.00, "cap": 0.0, "fractional": False}

# Live overrides set from the editor: (division, gender) -> {count?, rate?, cap?}.
_overrides: dict[tuple[str, str], dict] = {}
# The academically-elite D3 tier is its own editable cell (applies to both genders).
_elite_override: dict = {}


def _norm_division(division: str) -> str:
    d = (division or "").strip().lower()
    if d in ("d1", "i", "division i", "1"):
        return "D1"
    if d in ("d2", "ii", "division ii", "2"):
        return "D2"
    if d in ("d3", "iii", "division iii", "3"):
        return "D3"
    return (division or "D1").upper()


def _norm_gender(gender: str | None) -> str:
    g = (gender or "").strip().lower()
    if g in ("women", "female", "w", "f", "girls"):
        return "women"
    return "men"            # default/canonical gender when unspecified


def set_limit(division: str, gender: str | None = None, *,
              count=None, rate=None, cap=None) -> None:
    """Override a scholarship limit. `gender=None` applies the change to BOTH
    genders of the classification (so the old division-only call still works)."""
    div = _norm_division(division)
    targets = (_norm_gender(gender),) if gender else GENDERS
    for g in targets:
        o = _overrides.setdefault((div, g), {})
        if count is not None:
            o["count"] = max(0, int(count))
        if rate is not None:
            o["rate"] = max(0.0, min(1.0, float(rate)))
        if cap is not None:
            o["cap"] = max(0.0, float(cap))


def set_elite_limit(*, count=None, rate=None, cap=None) -> None:
    """Override the academically-elite D3 scholarship tier (applies to both genders).
    Editable from the editor like every other classification."""
    if count is not None:
        _elite_override["count"] = max(0, int(count))
    if rate is not None:
        _elite_override["rate"] = max(0.0, min(1.0, float(rate)))
    if cap is not None:
        _elite_override["cap"] = max(0.0, float(cap))


def clear_overrides() -> None:
    _overrides.clear()
    _elite_override.clear()


def any_overrides() -> bool:
    return bool(_overrides) or bool(_elite_override)


def get_overrides() -> dict:
    return {k: dict(v) for k, v in _overrides.items()}


def _is_elite_d3(division: str, academics: float) -> bool:
    return division == "D3" and academics >= ELITE_D3_ACADEMICS


def limits(division: str, gender: str | None = None, academics: float = 0.0) -> dict:
    """Resolved scholarship limits for a (division, gender): count / rate / cap /
    fractional / effective_value, after the elite-D3 rule and editor overrides."""
    div = _norm_division(division)
    g = _norm_gender(gender)
    if _is_elite_d3(div, academics):
        base = dict(ELITE_D3_LIMITS)
        base["elite_d3"] = True
        base.update(_elite_override)
    else:
        base = dict(DEFAULT_LIMITS.get((div, g), DEFAULT_LIMITS[("D3", "men")]))
        base["elite_d3"] = False
        base.update(_overrides.get((div, g), {}))
    base["effective_value"] = round(base["count"] * base["rate"], 2)
    return base


def program_limits(program) -> dict:
    return limits(program.division, getattr(program, "gender", "men"),
                  getattr(program, "academics", 0.0))


def slots(program) -> int:
    """How many roster players a program funds with athletic aid — its scholarship
    headcount (the rest of the roster are walk-ons)."""
    return int(round(program_limits(program)["count"]))


def value(program) -> float:
    """Total recruiting spend power (count × exchange rate)."""
    return program_limits(program)["effective_value"]


def cap(division: str, gender: str | None = None) -> float:
    """Total scholarship equivalency for a (division, gender) — the gender-real
    headline number that app.economy splits into fractional offers. Reflects any
    editor override."""
    return float(limits(division, gender)["cap"])
