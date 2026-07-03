"""Pro tier — the portal-only elite cohort a cut above blue-chips."""
import random

from app import pros
from app.development import overall_to_str


def _cohort(salt="s1", gender="men", cycle="2026-fall", n=18):
    return pros.generate_pros(salt, gender, cycle, n=n)


def test_cohort_above_blue_chip_with_badge():
    from app import recruit_economy as re
    c = _cohort()
    assert len(c) == 18
    # a blue-chip RECRUIT's expected grade — pros must clear it (they're a cut above)
    bc = next(g for (name, _s, _c, g) in re.TIERS if name == "Blue Chip")   # 74
    for p in c:
        assert p.current_overall() >= 75 > bc - 1        # above the blue-chip gate
        assert pros.is_pro(p)
        assert p.recruit_stars == 6                       # above the 5-star ladder


def test_default_size_in_range():
    c = pros.generate_pros("s", "women", "2026-preseason")
    assert pros.PRO_PER_CYCLE[0] <= len(c) <= pros.PRO_PER_CYCLE[1]


def test_deterministic_per_cycle():
    a = _cohort(cycle="2026-fall")
    b = _cohort(cycle="2026-fall")
    assert [p.pid for p in a] == [p.pid for p in b]
    # a different cycle -> a different cohort
    c = _cohort(cycle="2027-fall")
    assert [p.pid for p in a] != [p.pid for p in c]


def test_cost_indexed_to_str_and_always_affordable():
    c = _cohort()
    costs = {p.pid: pros.pro_cost(p, c) for p in c}
    # every cost sits inside the band, so the raised elite cap (33.5) always covers it
    assert all(pros.PRO_COST_LO <= v <= pros.PRO_COST_HI for v in costs.values())
    # the strongest pro is the most expensive, the weakest the cheapest
    by_str = sorted(c, key=lambda p: overall_to_str(p.current_overall()))
    assert pros.pro_cost(by_str[0], c) <= pros.pro_cost(by_str[-1], c)
    assert pros.pro_cost(by_str[-1], c) == pros.PRO_COST_HI
