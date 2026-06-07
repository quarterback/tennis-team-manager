import random

from app.juniors import (generate_class, national_rankings, state_rankings,
                         international_rankings, top_by_nation)


def _klass(n=300, seed=1):
    return generate_class(random.Random(seed), n=n, grad_year=2026, gender="male", intl_share=0.35)


def test_class_size_and_origins():
    k = _klass()
    assert len(k.recruits) == 300
    for p in k.recruits:
        assert p.grad_year == 2026
        assert "," in p.hometown                       # "City, Region"
        if p.domestic:
            assert p.region in {s for s, _ in __import__("app.juniors", fromlist=["US_STATES"]).US_STATES}
        else:
            assert not p.domestic


def test_intl_share_roughly_holds():
    k = _klass()
    intl = sum(1 for p in k.recruits if not p.domestic)
    assert 0.25 <= intl / len(k.recruits) <= 0.45     # ~35%


def test_national_ranking_sorted_and_deterministic():
    a = national_rankings(_klass(seed=7))
    b = national_rankings(_klass(seed=7))
    assert [p.name for p in a] == [p.name for p in b]   # deterministic
    scores = [0.6 * p.current_overall() + 0.4 * p.scouting_report("service") for p in a]
    assert scores == sorted(scores, reverse=True)        # descending recruiting score


def test_state_and_international_boards():
    k = _klass()
    ca = state_rankings(k, "California")
    assert all(p.domestic and p.region == "California" for p in ca)
    intl = international_rankings(k)
    assert all(not p.domestic for p in intl)
    nations = top_by_nation(k, per=10)
    assert all(len(v) <= 10 for v in nations.values())
    assert all(all(p.region == nation for p in v) for nation, v in nations.items())
