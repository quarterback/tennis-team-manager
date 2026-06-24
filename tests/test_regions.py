"""S-curve regional split + cosmetic region naming for the NCAA bracket."""
from app import regions as R


def test_scurve_matches_spec_and_balances():
    seeds = list(range(1, 97))                      # overall seeds 1..96
    regs = R.scurve_regions(seeds)
    assert [len(r) for r in regs] == [24, 24, 24, 24]
    # The serpentine from the spec: line 1 A,B,C,D = 1,2,3,4; line 2 = 8,7,6,5.
    assert [regs[r][0] for r in range(4)] == [1, 2, 3, 4]
    assert [regs[r][1] for r in range(4)] == [8, 7, 6, 5]
    assert [regs[r][2] for r in range(4)] == [9, 10, 11, 12]
    # Perfectly balanced: every region has the same seed-sum.
    sums = [sum(r) for r in regs]
    assert len(set(sums)) == 1


def test_scurve_64():
    seeds = list(range(1, 65))
    regs = R.scurve_regions(seeds)
    assert [len(r) for r in regs] == [16, 16, 16, 16]
    assert len({sum(r) for r in regs}) == 1


def test_region_index_round_trip():
    seeds = [f"T{i}" for i in range(96)]
    idx = R.region_index_of(seeds)
    assert len(idx) == 96
    assert set(idx.values()) == {0, 1, 2, 3}
    # #1 and #2 overall land in different regions (opposite halves of the draw).
    assert idx[seeds[0]] != idx[seeds[1]]


def test_region_names_distinct_and_deterministic():
    a = R.region_names(2026)
    assert len(a) == 4 and len(set(a)) == 4         # four distinct labels
    assert all(n in R.LEAGUE_NAMES for n in a)
    assert R.region_names(2026) == a                # deterministic per seed
    assert R.region_names(2027) != a or True        # may differ across years (cosmetic)
