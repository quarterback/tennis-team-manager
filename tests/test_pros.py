"""Pro tier — the portal-only elite cohort a cut above blue-chips."""
import random

from app import pros
from app.development import overall_to_str


def _cohort(salt="s1", gender="men", cycle="2026-fall", n=18):
    return pros.generate_pros(salt, gender, cycle, n=n)


def test_cohort_in_pro_band_with_badge():
    c = _cohort()
    assert len(c) == 18
    for p in c:
        assert 81 <= p.current_overall() <= 90            # above the 80 college ceiling
        assert pros.is_pro(p)
        assert p.recruit_stars == 6                       # above the 5-star ladder


def test_pro_beats_a_blue_chip_on_court():
    """A pro should win a clear majority of duels vs a top blue-chip recruit — the whole
    point of the tier is that they're demonstrably better, not just higher on paper."""
    from engine import simulate_match
    from app.development import generate_prospect
    pro = _cohort(n=1)[0]
    bc = generate_prospect(random.Random(7), "Chip Elite", "US", "male",
                           talent=74.0, maturity_range=(1.0, 1.0))   # blue-chip grade
    wins = sum(simulate_match(pro.engine_player(), bc.engine_player(), seed=s).winner == 0
               for s in range(200))
    assert wins >= 130            # pro clearly favoured (not a coin flip, not a lock)


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
