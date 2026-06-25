"""Dynamic prestige momentum: the signed YoY drift added on top of base prestige,
which moves a program's recruiting-budget tier both ways."""
import app.ncaa as ncaa
import app.overrides as ov
from app import recruit_economy as re
from app.web.server import create_app


def _budget_tier(school, division="D1", gender="men"):
    p = ncaa.load_division(division, gender).by_school(school)
    return p.prestige, re._prestige_tier(p.prestige)


def test_momentum_moves_prestige_and_budget_tier_both_ways():
    create_app()
    div = ncaa.load_division("D1", "men")
    # a clear low-major and a clear blue-blood
    low = min(div.programs, key=lambda p: p.prestige).school
    top = max(div.programs, key=lambda p: p.prestige).school
    base_low, tier_low = _budget_tier(low)
    base_top, tier_top = _budget_tier(top)

    ov.set_prestige_momentum_batch({(low, "men"): 0.18, (top, "men"): -0.18})
    ncaa.reset_caches()
    new_low, ntier_low = _budget_tier(low)
    new_top, ntier_top = _budget_tier(top)

    # the low-major's prestige (and tier) climbed; the blue-blood's fell.
    assert new_low > base_low + 0.1
    assert new_top < base_top - 0.1
    rank = re._TIER_RANK
    assert rank[ntier_low] > rank[tier_low]      # climbed at least a tier
    assert rank[ntier_top] < rank[tier_top]      # slid at least a tier

    # cleanup: momentum cleared → back to baseline
    ov.set_prestige_momentum_batch({(low, "men"): 0.0, (top, "men"): 0.0})
    _conn = ov._db()
    _conn.execute("DELETE FROM roster_overrides WHERE kind='prestige_dyn'")
    _conn.commit(); _conn.close()
    ncaa.reset_caches()
    assert abs(_budget_tier(low)[0] - base_low) < 1e-6
    assert abs(_budget_tier(top)[0] - base_top) < 1e-6


def test_momentum_clamps_to_division_band():
    create_app()
    div = ncaa.load_division("D1", "men")
    top = max(div.programs, key=lambda p: p.prestige).school
    hi = ncaa.DIVISION_PRESTIGE_RANGE["D1"][1]
    ov.set_prestige_momentum_batch({(top, "men"): 0.9})     # absurd → clamp to band top
    ncaa.reset_caches()
    assert ncaa.load_division("D1", "men").by_school(top).prestige <= hi + 1e-9
    _conn = ov._db()
    _conn.execute("DELETE FROM roster_overrides WHERE kind='prestige_dyn'")
    _conn.commit(); _conn.close()
    ncaa.reset_caches()
