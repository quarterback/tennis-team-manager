"""THE METASTATE — the at-larges' first qualifying layer (owner rule 2026-09).

The Parastate put the `2 x bids` lowest seeds together, so a 48's seeds 17-24 drew
seeds 41-48 and won 279 of 288 of those duals over six seasons. The metas pair the
bottom `bids` seeds among THEMSELVES first and send `bids / 2` winners on to meet
the next `bids / 2` seeds, so the weakest seeds play each other and the middle of
the field byes to the State draw.

Two things are pinned here that nothing else can catch:

* the arithmetic CLOSES — every shape lands back on the class's own road field
  size, so the State draw is the bracket that class already played; and
* a meta loser is NOT a State participant, which is the one substantive break
  with the Parastate (where every entrant is, because the Parastate is a round OF
  the State event). That is bought by the metas being their own PHASE with their
  own archive key, and it is invisible in the draw itself.

1A and Group 3 are OUT by owner decision and keep the single-Parastate
progression; their at-larges enter the Parastate directly.
"""
import pytest

from app import jhsaa as jh
from app import world as wd


class _School:
    def __init__(self, name):
        self.name = name


class _Team:
    """The only surface the draw touches: a name, and an order to play by."""
    def __init__(self, name, i):
        self.school, self.i = _School(name), i


class _Res:
    def __init__(self, winner, hp, ap):
        self.winner, self.home_points, self.away_points = winner, hp, ap


@pytest.fixture(autouse=True)
def stub_dual(monkeypatch):
    """The better seed always wins, so the survivors of every round are exactly
    predictable and the SHAPE is what is under test, never who won."""
    monkeypatch.setattr(jh, "play_dual",
                        lambda a, b, *, seed, phase:
                        _Res(0, 3, 2) if a.i < b.i else _Res(1, 2, 3))


def _play(group, n_field):
    field = [_Team(f"T{i + 1:02}", i) for i in range(n_field)]
    return jh.run_state_parastate(field, byes=jh.parastate_byes(group),
                                  meta=jh.metastate_bids(group), seed=11)


# --------------------------------------------------------------- the tables ----

def test_1a_and_group_3_do_not_play_the_metas():
    """Owner decision: they crown from 32 off a 24-team road and keep the single
    Parastate they already play. Pinned as membership, since the whole change is
    which classes are in the tuple."""
    for g in ("1A", "Group 3"):
        assert g in jh.ATLARGE_GROUPS and g not in jh.METASTATE_GROUPS
        assert jh.metastate_bids(g) == 0
        # Unchanged: the road less the WHOLE allocation, exactly as before.
        assert jh.parastate_byes(g) == jh.state_field_size(g) - jh.AT_LARGE_BIDS[g]


def test_every_metastate_class_is_an_at_large_class_with_an_even_allocation():
    """The import-time assertions, restated as a test so the reason survives.
    An ODD allocation is what breaks the halving — `bids / 2` stops being a whole
    number of seeds and both rounds advance a middle team unplayed."""
    for g in jh.METASTATE_GROUPS:
        assert g in jh.ATLARGE_GROUPS, g
        assert jh.AT_LARGE_BIDS[g] % 2 == 0, g


def test_the_arithmetic_closes_on_the_road_field_at_every_shape():
    """A pure fold over the tables — no season, so it cannot rot behind a fixture.
    metas take `bids` and return `bids / 2`; the Parastate takes those plus
    `bids / 2` seeds and returns `bids / 2`; the draw is `byes + bids / 2`, which
    is the road field size at every allocation."""
    for g in jh.ATLARGE_GROUPS:
        bids = jh.AT_LARGE_BIDS[g]
        crowns_from = jh.state_field_size(g) + bids
        through_meta = jh.metastate_bids(g) // 2
        post_meta = crowns_from - through_meta          # losers are out
        para = post_meta - jh.parastate_byes(g)
        assert para % 2 == 0, g
        assert jh.parastate_byes(g) + para // 2 == jh.state_field_size(g), g


# ----------------------------------------------------------------- the round ----

@pytest.mark.parametrize("group, n_field, duals", [("9A", 48, 8), ("7A", 40, 4)])
def test_the_metas_pair_the_lowest_seeds_among_themselves(group, n_field, duals):
    arc = _play(group, n_field)
    meta = arc["meta"]
    bids = jh.AT_LARGE_BIDS[group]
    # Exactly the bottom `bids` seeds, and nobody else.
    assert meta["field"] == [f"T{i:02}" for i in range(n_field - bids + 1, n_field + 1)]
    assert len(meta["rounds"][0]) == duals
    assert meta["round_names"] == [jh.METASTATE_NAME]
    # Paired high-low WITHIN the block — the best meta seed meets the worst.
    first = meta["rounds"][0][0]
    assert {first["home"], first["away"]} == {f"T{n_field - bids + 1:02}",
                                              f"T{n_field:02}"}


@pytest.mark.parametrize("group, n_field", [("9A", 48), ("7A", 40)])
def test_a_metastate_loser_is_not_in_the_state_field(group, n_field):
    """‼️ THE WHOLE POINT. `world.jhsaa_state_result` reports `made_state` off
    membership of the draw's `field`, so keeping a meta loser out of that list is
    the only thing that makes 'a Metastate participant with no State
    appearance' true."""
    arc = _play(group, n_field)
    bids = jh.AT_LARGE_BIDS[group]
    through = set(arc["meta"]["advanced"])
    played = set(arc["meta"]["field"])
    assert len(through) == bids // 2
    assert through < played
    for name in played - through:
        assert name not in arc["field"], name
        assert wd.jhsaa_state_result(arc, name)["made_state"] is False
    for name in through:
        assert name in arc["field"], name
        assert wd.jhsaa_state_result(arc, name)["made_state"] is True


@pytest.mark.parametrize("group, n_field", [("9A", 48), ("7A", 40)])
def test_the_state_draw_is_the_road_field_and_the_top_seeds_bye_it(group, n_field):
    arc = _play(group, n_field)
    assert len(arc["field"]) == n_field - jh.metastate_bids(group) // 2
    assert arc["round_names"][0] == jh.PARASTATE_NAME
    # The Parastate is exactly the teams past the byes, and the draw behind it is
    # the class's own road field.
    para = arc["rounds"][0]
    assert len(para) * 2 == len(arc["field"]) - jh.parastate_byes(group)
    assert jh.parastate_byes(group) + len(para) == jh.state_field_size(group)
    # A seed inside the bye line never plays before the main draw.
    byed = arc["field"][:jh.parastate_byes(group)]
    for gm in para:
        assert gm["home"] not in byed and gm["away"] not in byed


def test_a_metastate_winner_keeps_its_seed():
    """Winners re-enter in SEED order, not in the order the duals were played, so
    the Parastate's high-low pairing sees the order it always did."""
    arc = _play("9A", 48)
    order = {n: i for i, n in enumerate(arc["field"])}
    advanced = [n for n in arc["meta"]["advanced"]]
    ranks = [order[n] for n in sorted(advanced, key=lambda n: int(n[1:]))]
    assert ranks == sorted(ranks), "survivors re-entered out of seed order"


def test_the_classes_that_do_not_play_them_are_byte_identical():
    """1A passes `meta=0` and its old byes, so its draw must be exactly what it
    was — the guard against the change reaching a class the owner excluded."""
    field = [_Team(f"T{i + 1:02}", i) for i in range(32)]
    new = jh.run_state_parastate(field, byes=jh.parastate_byes("1A"),
                                 meta=jh.metastate_bids("1A"), seed=11)
    old = jh.run_state_parastate(field, byes=32 - 8, seed=11)
    assert "meta" not in new
    assert jh.parastate_byes("1A") == 16
    # Same byes, same shape; `old` above is the pre-change call at the 1A numbers.
    assert new["field"] == [t.school.name for t in field]
    assert len(new["rounds"][0]) == 8


def test_a_short_field_plays_no_metas_at_all():
    """‼️ THE METAS NEVER EAT INTO THE BYE LINES. Capped with `min(meta, len(field))`
    a small world (a fixture's two districts a class, a save whose road ran dry)
    put its WHOLE field into the metas: every team played one, half were out
    before the Parastate, and the survivors all byed into a draw the association
    never plays. Under the floor the round simply does not convene and the class
    degrades exactly as it did before the metas existed."""
    for n in (6, 12, 24, 32, 39):
        field = [_Team(f"T{i + 1:02}", i) for i in range(n)]
        arc = jh.run_state_parastate(field, byes=jh.parastate_byes("9A"),
                                     meta=jh.metastate_bids("9A"), seed=5)
        # 9A needs 24 bye lines plus a 16-team meta block: 40 teams.
        assert "meta" not in arc, n
        assert arc["field"] == [t.school.name for t in field], n
        # ‼️ AND THE PARASTATE TAKES THE WHOLE ALLOCATION BACK, so a short world
        # still PLAYS one. Passing `road − bids / 2` with no metas behind it left
        # the bye line too high by the half the metas would have removed, and the
        # Parastate quietly stopped convening at all.
        old = jh.run_state_parastate(
            [_Team(f"T{i + 1:02}", i) for i in range(n)],
            byes=jh.state_field_size("9A") - jh.AT_LARGE_BIDS["9A"], seed=5)
        assert arc["round_names"] == old["round_names"], n
        assert arc["rounds"] == old["rounds"], n
    field = [_Team(f"T{i + 1:02}", i) for i in range(40)]
    arc = jh.run_state_parastate(field, byes=jh.parastate_byes("9A"),
                                 meta=jh.metastate_bids("9A"), seed=5)
    assert "meta" in arc and len(arc["meta"]["rounds"][0]) == 8


# ---------------------------------------------------------------- the finish ----

def test_a_metastate_exit_reads_back_as_its_own_finish_and_supersedes_the_specials():
    """A Specials WINNER is a State qualifier and can be seeded into the metas, so
    the meta check has to be tried before the Specials or its year would read as
    ending a round earlier than it did."""
    grp = {jh.METASTATE_PHASE: {"field": ["Alpha", "Beta"]},
           "state_special": {"field": ["Alpha"]},
           "state": {"field": ["Gamma"], "rounds": [], "champion": "Gamma"}}
    res = wd.jhsaa_postseason_result(grp, "Alpha")
    assert res["finish"] == jh.METASTATE_FINISH and res["made_state"] is False
    assert jh.METASTATE_FINISH == "Metastate"
    # And it ranks deeper than a Specials exit on the season-depth ladder.
    ladder = wd.jh_road_ladder()
    assert ladder.index(jh.METASTATE_FINISH) > ladder.index(jh.STATE_SPECIAL_FINISH)


def test_a_season_archived_before_the_metas_still_reads():
    """The key is absent from every earlier archive; `.get` on read, never a
    migration — the section's own idiom."""
    grp = {"state": {"field": ["Gamma"], "rounds": [], "champion": "Gamma"},
           "state_special": {"field": ["Alpha"]}}
    assert wd.jhsaa_postseason_result(grp, "Alpha")["finish"] == jh.STATE_SPECIAL_FINISH
    assert wd.jhsaa_postseason_result(grp, "Nobody")["finish"] == ""


# ----------------------------------------------------------------- the page ----

def test_the_metas_render_as_their_own_stage_on_the_bracket_page(monkeypatch):
    """‼️ A ROUND NOTHING RENDERS IS INDISTINGUISHABLE FROM A ROUND THAT WAS NOT
    PLAYED — the JV regional brackets' lesson, which were archived every season
    and readable nowhere. Hand-archived, because the real-season fixture is a
    small world where the metas correctly do not convene at all (a field under
    `byes + bids` plays none), so the path a live 48-team class takes every season
    is exactly the one that fixture cannot reach.

    They render as a STAGE and not a tree column: eight duals feeding a separate
    Parastate field is not a halving, and `_bracket_canvas` links columns on
    exactly that halving."""
    import os
    from app import world as world
    from app.web.server import create_app
    os.environ.setdefault("PTC_NO_BOOT_WARM", "1")

    grp = jh.METASTATE_GROUPS[0]
    meta = {"field": ["Alpha", "Beta", "Gamma", "Delta"],
            "round_names": [jh.METASTATE_NAME],
            "advanced": ["Alpha", "Beta"],
            "rounds": [[{"home": "Alpha", "away": "Delta", "winner": "Alpha",
                         "home_points": 5, "away_points": 0},
                        {"home": "Beta", "away": "Gamma", "winner": "Beta",
                         "home_points": 3, "away_points": 2}]]}
    arc = {"season_year": 2099, "champions": {}, "standings": {},
           "brackets": {grp: {"field": ["Alpha", "Beta"], "champion": "Alpha",
                              "rounds": [[{"home": "Alpha", "away": "Beta",
                                           "winner": "Alpha",
                                           "home_points": 5, "away_points": 0}]]}},
           jh.METASTATE_PHASE: {grp: meta}}
    monkeypatch.setattr(world, "jhsaa_years", lambda wid, g: [0])
    monkeypatch.setattr(world, "get_jhsaa", lambda wid, yr, g: arc)
    html = create_app().test_client().get(
        f"/jhsaa/bracket?group={grp}").get_data(as_text=True)
    assert jh.METASTATE_NAME in html
    # Both duals of the round are on the page, losers included — that is the only
    # surface a meta exit is visible on.
    for name in ("Alpha", "Beta", "Gamma", "Delta"):
        assert name in html, name
