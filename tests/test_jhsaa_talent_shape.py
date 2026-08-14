"""Classification talent is a DEPTH gradient, not a level ladder (owner rule 2027-08).

Tennis is not a sport where the big school simply has better players. Good players turn
up everywhere; what enrollment buys is depth. `_TALENT` therefore varies the mean while
WIDENING the spread as the mean falls, so the top of each classification overlaps and the
bottom does not.

The old bands were an even -5/-4 step with the spread NARROWING, which gets the sport
backwards in a way that is invisible in aggregate and obvious position by position: the
number ones were 12.4 apart while the number nines were only 8.3, so the TOP fell faster
than the DEPTH, and the smallest classification could not produce an elite player at all.

These pin the shape, not the numbers — every assertion is a relation between
classifications, so the bands can be retuned without rewriting the file.
"""
import statistics as stat

import pytest

from app import jhsaa


@pytest.fixture(scope="module")
def ladder():
    """{gender: {group: {position: mean current OVR}}} over a sample of each class."""
    out = {}
    for gender in ("boys", "girls"):
        out[gender] = {}
        for group in jhsaa.GROUPS:
            # ⚠️ MEASURE THE WHOLE CLASSIFICATION, not its first N. This took
            # `[:SAMPLE]` off an ALPHABETICAL list, so it measured whichever
            # programs happened to sort early — and a batch of school RENAMES
            # (owner cleanup 2027-08) moved enough of them to swing the 7A/6A
            # top-end gap past tolerance while `_TALENT` was untouched, i.e. the
            # test reported a talent-model regression that did not exist. Rosters
            # are cached, so the full population costs ~5s against the sample's
            # ~3s and carries no sampling error at all: a calibration check that
            # can be moved by renaming schools is not measuring what it claims.
            schools = [s for s in jhsaa.load_schools(gender) if s.group == group]
            cols = {i: [] for i in (1, 3, 5, 9)}
            best = 0.0
            for sc in schools:
                r = sorted((p.current_overall() for p in jhsaa.build_roster(sc, 2029)),
                           reverse=True)
                for i in cols:
                    cols[i].append(r[i - 1])
                best = max(best, r[0])
            out[gender][group] = {i: stat.mean(v) for i, v in cols.items()}
            out[gender][group]["best"] = best
    return out


@pytest.mark.parametrize("gender", ["boys", "girls"])
def test_depth_separates_the_classes_more_than_the_top_does(gender, ladder):
    """The whole rule in one assertion. If the number ones spread further than the number
    nines, the model is saying enrollment buys STARS, which is the thing it must not."""
    top = [ladder[gender][g][1] for g in jhsaa.GROUPS]
    deep = [ladder[gender][g][9] for g in jhsaa.GROUPS]
    assert max(top) - min(top) < max(deep) - min(deep), (top, deep)


@pytest.mark.parametrize("gender", ["boys", "girls"])
def test_the_two_biggest_classes_are_near_indistinguishable_at_the_top(gender, ladder):
    a, b = ladder[gender]["7A"][1], ladder[gender]["6A"][1]
    assert abs(a - b) <= 2.5, (a, b)


@pytest.mark.parametrize("gender", ["boys", "girls"])
def test_every_classification_can_produce_an_elite_number_one(gender, ladder):
    """The small school that goes top-ten in the state is an ordinary thing in real
    high-school tennis. Under the old bands 3A-1A topped out at 51 and could not."""
    for g in jhsaa.GROUPS:
        assert ladder[gender][g]["best"] >= 55.0, (g, ladder[gender][g]["best"])


@pytest.mark.parametrize("gender", ["boys", "girls"])
def test_the_lineup_falls_away_faster_at_a_smaller_school(gender, ladder):
    """#1 → #9 is the depth gradient, and it must widen as classifications shrink. The
    old bands had it NARROWING (23.2 at 7A, 19.2 at 3A-1A)."""
    drops = [ladder[gender][g][1] - ladder[gender][g][9] for g in jhsaa.GROUPS]
    assert drops[-1] > drops[0], drops
    assert drops[-1] - drops[0] >= 2.0, drops


@pytest.mark.parametrize("gender", ["boys", "girls"])
def test_the_bulk_still_indexes_downward(gender, ladder):
    """Thinner, not equal: the middle of the lineup still steps down the classes, which
    is what keeps a 7A dual different from a 1A one.

    Adjacent classes may TIE (`TOL`), because the bands deliberately overlap where the
    means are close and the spreads differ — 7A boys (58.0/15.0) against 6A (56.5/15.5)
    is the designed case, and measured over every program they sit 0.08 apart at #5.
    Demanding a strict step there asserts a ladder the model is documented not to have;
    what must hold is that the bulk never RISES as schools shrink, and that the two ends
    are a real distance apart."""
    TOL = 0.5
    mid = [ladder[gender][g][5] for g in jhsaa.GROUPS]
    assert all(b <= a + TOL for a, b in zip(mid, mid[1:])), mid
    assert mid[0] - mid[-1] >= 6.0, mid


def test_spread_widens_as_the_mean_falls():
    """The mechanism, asserted directly — 12 ceilings are drawn and the best 9 dress, so a
    wider draw lifts the number one and drags the number nine down. Narrowing the spread
    alongside the mean is the old shape."""
    for gender in ("boys", "girls"):
        bands = [jhsaa._TALENT[(g, gender)] for g in jhsaa.GROUPS]
        means = [m for m, _ in bands]
        spreads = [s for _, s in bands]
        assert means == sorted(means, reverse=True), means
        assert spreads == sorted(spreads), spreads
