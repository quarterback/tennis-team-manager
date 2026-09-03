"""Every State field size draws a bracket that can actually be rendered.

The report: a 9A bracket where four teams advanced WITHOUT PLAYING, round after
round, cards overlapping — and it was every classification on the 32-team table.
`run_state` was sending a 32-team field down the qualifying expansion built for the
40, which then padded the leftovers with byes; a 32 needs none of it (owner, 2026-08:
"32 can happen with no byes… 32-16-8-4-2 works fine, with 8 zonal champions as the
top 8 seeds").

These play the draw with a stubbed dual and then RENDER it, because the fault was
only visible on the page: the archive was internally consistent either way.
"""
import pytest

from app import jhsaa as jh
from app.web import state as st


class _School:
    def __init__(self, name):
        self.name = name


class _Team:
    """The only surface `run_state` touches: a name, and an order to play by."""
    def __init__(self, name, i):
        self.school, self.i = _School(name), i


class _Res:
    def __init__(self, winner, hp, ap):
        self.winner, self.home_points, self.away_points = winner, hp, ap


@pytest.fixture(autouse=True)
def stub_dual(monkeypatch):
    """The better seed wins, so the champion is always T01 and every shape is
    comparable. The draw's SHAPE is what is under test, never who won."""
    monkeypatch.setattr(jh, "play_dual",
                        lambda a, b, *, seed, phase:
                        _Res(0, 3, 2) if a.i < b.i else _Res(1, 2, 3))


def draw(n, champions=8):
    field = [_Team(f"T{i + 1:02}", i) for i in range(n)]
    br = jh.run_state(field, seed=7, champions=champions)
    return {**br, "field": [t.school.name for t in field]}


def columns(br):
    main, qual = st._jh_split_state(br)
    return (st._jh_bracket_cols(main, {}),
            st._jh_bracket_cols(qual, {}) if qual else [], main, qual)


def byes_per_column(cols):
    return [{m["home"]["school"] for m in c["matchups"] if m.get("bye")} for c in cols]


@pytest.mark.parametrize("n", list(range(17, 41)))
def test_no_team_ever_byes_in_two_rounds_running(n):
    """‼️ THE REPORTED FAULT, at every size. A team that byes twice in a row has not
    been given a bye — it has been left out of a bracket that no longer halves, which
    is what put four teams on screen advancing unplayed to the final."""
    main_cols, qual_cols, _, _ = columns(draw(n))
    for cols, which in ((main_cols, "main"), (qual_cols, "qualifying")):
        seq = byes_per_column(cols)
        for i in range(len(seq) - 1):
            assert not (seq[i] & seq[i + 1]), (n, which, sorted(seq[i] & seq[i + 1]))


@pytest.mark.parametrize("n", list(range(17, 41)))
def test_every_column_halves_into_the_next(n):
    """What the shared canvas assumes: cards `2k` and `2k+1` feed card `k`. A column
    that is not twice the next one draws links to nothing."""
    for cols in columns(draw(n))[:2]:
        widths = [len(c["matchups"]) for c in cols]
        for a, b in zip(widths, widths[1:]):
            assert a == 2 * b, (n, widths)


def test_a_power_of_two_field_plays_straight_through_with_no_byes():
    """‼️ 32 → 16 → 8 → 4 → 2, nobody sitting out (owner, 2026-08). The champions'
    privilege is a SEEDING guarantee; a 24-field's eight byes are a consequence of
    that field's shape, not the rule — see
    `test_the_epiregional_plays_all_eight_champions_for_four_bye_lines`, which pins
    both shapes (the bye lines are the Epiregional winners plus the ATR four now,
    owner rule 2026-09)."""
    br = draw(32)
    assert not br.get("round_names"), "a 32 needs no qualifying round"
    assert [len(r) for r in br["rounds"]] == [16, 8, 4, 2, 1]
    cols, _, _, qual = columns(br)
    assert qual is None
    assert all(not b for b in byes_per_column(cols)), "a full bracket has no byes"
    # ...and the rounds are named for what they are, once each.
    assert [c["name"] for c in cols] == ["Round of 32", "Octofinals", "Quarterfinals",
                                         "Semifinals", "Championship"]


def test_the_twenty_four_field_still_byes_its_eight_champions():
    """The shape the association actually crowns most classes on: eight byes, and
    they are the eight Zonal champions' — unchanged by the 32 fix."""
    br = draw(24)
    cols = columns(br)[0]
    assert [len(c["matchups"]) for c in cols] == [16, 8, 4, 2, 1]
    assert len(byes_per_column(cols)[0]) == 8
    assert byes_per_column(cols)[0] <= {f"T{i + 1:02}" for i in range(8)}


def test_the_forty_field_keeps_its_qualifying_round():
    """The expansion is not deleted — it is confined to the field that needs it. A 40
    will not fit a bracket whose byes are the champions' own, so it plays the Qualies
    and the First Round in front of a fresh draw."""
    br = draw(40)
    assert br.get("round_names"), "a 40 still qualifies into its main draw"
    main, qual = st._jh_split_state(br)
    assert len(main["field"]) == 16, "both shapes converge at the Octofinals"
    assert qual is not None


@pytest.mark.parametrize("n", [33, 36, 39])
def test_a_short_forty_field_names_its_rounds_off_the_teams_that_played(n):
    """‼️ A team that byed the opening Qualies round appears only in the SECOND one,
    so reading the first round alone filed it with the double-bye champions: the main
    draw's field over-counted and the rounds were named off a team count that never
    existed ("Round of 20", then Octofinals twice)."""
    main, _ = st._jh_split_state(draw(n))
    assert len(main["field"]) == 16
    names = [c["name"] for c in st._jh_bracket_cols(main, {})]
    assert names == ["Octofinals", "Quarterfinals", "Semifinals", "Championship"], n
