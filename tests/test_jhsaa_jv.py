"""The JV season. Everything here is silent when it breaks — a JV result reaching a
varsity counter, a drawn dual recorded as a loss, a JV dual sharing a calendar key
with its varsity namesake."""
import random

import pytest

import app.jhsaa as jh
import app.world as world


def _slice(gender="girls", groups=("9A", "5A"), per=2, salt="jvtest"):
    return {g: {n: jh.district_teams(ss, 0, salt)
                for n, ss in sorted(jh.districts(gender, g).items())[:per]}
            for g in groups}


def _teams(by_group):
    return [t for st in by_group.values() for ts in st.values() for t in ts]


# --- floor and format --------------------------------------------------------

def test_the_floor_is_what_lets_every_program_field_a_jv():
    assert jh.ROSTER_FLOOR == jh.lineup_need("regular") + jh.JV_MIN_SPARE
    for t in _teams(_slice()):
        assert jh.jv_spare(t) >= jh.JV_MIN_SPARE, t.school.name


def test_the_format_takes_the_thinner_side():
    assert jh.jv_format(jh.JV_MIN_SPARE - 1) is None
    assert jh.jv_dual_format(4, 30) is None
    assert jh.jv_dual_format(12, 6) is jh.JV_FORMATS[6]


def test_the_table_has_no_ceiling_and_every_size_dresses_exactly():
    """The authored 5-12 continue as one rule, so a deep pair plays a bigger card
    rather than being clamped back to 4S/4D."""
    for spare in range(jh.JV_MIN_SPARE, 41):
        fmt = jh.jv_format(spare)
        assert jh.jv_lineup_need(fmt) == spare, spare
        assert not fmt.doubles_team_point
        # doubles-forward at every size: singles never runs more than one past doubles
        assert fmt.n_singles <= fmt.n_doubles + 1, spare
    assert (jh.jv_format(14).n_singles, jh.jv_format(14).n_doubles) == (4, 5)
    assert (jh.jv_format(15).n_singles, jh.jv_format(15).n_doubles) == (5, 5)
    assert (jh.jv_format(17).n_singles, jh.jv_format(17).n_doubles) == (5, 6)


# --- the tie ladder ----------------------------------------------------------

class _Line:
    def __init__(self, sets):
        self.result = type("R", (), {"set_scores": sets})()


class _Res:
    def __init__(self, hp, ap, lines):
        self.home_points, self.away_points, self.lines = hp, ap, lines
        self.winner = 0 if hp > ap else 1        # what the engine says on a level dual


def test_jv_outcome_ignores_the_engine_winner_on_a_level_dual():
    level = _Res(2, 2, [_Line([(6, 4), (6, 4)]), _Line([(4, 6), (4, 6)])])
    assert level.winner == 1
    assert jh.jv_outcome(level) == 0


def test_the_tie_ladder_is_points_then_sets_then_games():
    assert jh.jv_outcome(_Res(3, 1, [_Line([(0, 6), (0, 6)])])) == 1
    assert jh.jv_outcome(_Res(1, 1, [_Line([(6, 0), (6, 0)]),
                                     _Line([(0, 6), (6, 4), (4, 6)])])) == 1
    assert jh.jv_outcome(_Res(1, 1, [_Line([(7, 6), (7, 6)]),
                                     _Line([(0, 6), (0, 6)])])) == -1
    assert jh.jv_outcome(_Res(1, 1, [_Line([(6, 3), (3, 6), (6, 3)]),
                                     _Line([(3, 6), (6, 3), (3, 6)])])) == 0


def test_a_record_carries_ties():
    t = jh.JVTeam(team=None, wins=2, losses=1, ties=1)
    assert t.record == "2-1-1"
    assert t.win_pct == pytest.approx(2.5 / 4)
    assert jh.JVTeam(team=None, wins=3, losses=2).record == "3-2"


# --- separation from varsity -------------------------------------------------

def test_a_jv_season_writes_nothing_to_the_varsity_season():
    by_group = _slice()
    teams = _teams(by_group)
    jv = jh.play_jv_season(by_group, 0, "girls", "jvtest")
    assert sum(len(t.schedule) for t in jv.values()) > 0
    for t in teams:
        assert (t.wins, t.losses, t.dwins, t.dlosses) == (0, 0, 0, 0), t.school.name
        assert (t.points_for, t.points_against) == (0.0, 0.0)
        assert not t.schedule and not t.records and not t.matches
    for t in jv.values():
        assert t.wins + t.losses + t.ties == len(t.schedule), t.school.name


def test_jv_rows_carry_a_box_score_of_the_right_shape():
    jv = jh.play_jv_season(_slice(groups=("9A",), per=1), 0, "girls", "jvtest")
    rows = [d for t in jv.values() for d in t.schedule]
    assert rows
    for d in rows:
        assert d["level"] == jh.LEVEL_JV
        s, _, dd = d["shape"].partition("S/")
        n_s, n_d = int(s), int(dd.rstrip("D"))
        # doubles are played first, so compare the SET — the order is the engine's
        slots = sorted(ln["slot"] for ln in d["lines"])
        assert slots == sorted([f"S{i}" for i in range(1, n_s + 1)] +
                               [f"D{i}" for i in range(1, n_d + 1)]), d["shape"]
        for ln in d["lines"]:
            assert len(ln["home"]) == len(ln["away"]) == (
                1 if ln["slot"].startswith("S") else 2)
            assert ln["score"]


def test_varsity_rows_are_stamped_too():
    teams = _teams(_slice(groups=("9A",), per=1))
    jh.play_dual(teams[0], teams[1], seed=7)
    assert all(d["level"] == jh.LEVEL_VARSITY for d in teams[0].schedule)


def test_the_match_key_separates_a_jv_dual_from_its_varsity_namesake():
    base = {"school": "A", "opp": "B", "home": 1, "phase": "regular", "district": 1}
    v = world.jh_match_key({**base, "level": "v"})
    j = world.jh_match_key({**base, "level": "jv"})
    assert v != j
    assert world.jh_match_key(base) == v         # a pre-migration row reads as varsity
    assert world.jh_match_key({"school": "B", "opp": "A", "home": 0, "phase": "regular",
                               "district": 1, "level": "jv"}) == j


# --- scheduling --------------------------------------------------------------

def test_invitationals_never_pair_a_league_mate():
    by_group = _slice(groups=("9A", "8A", "5A"), per=2)
    jv = {t.school.name: jh.JVTeam(team=t) for t in _teams(by_group)}
    pairs = jh.jv_invitational_pairs(jv, {n: set() for n in jv}, random.Random(1))
    assert pairs
    assert all(jh._dkey(a) != jh._dkey(b) for a, b in pairs)


def test_the_cap_is_a_limit_and_the_showcase_sits_outside_it():
    jv = jh.play_jv_season(_slice(groups=("9A", "8A"), per=2), 0, "girls", "jvtest")
    league = [sum(1 for d in t.schedule if d["phase"] not in jh.SHOWCASE)
              for t in jv.values()]
    assert max(league) <= jh.JV_DUAL_CAP
    assert max(len(t.schedule) for t in jv.values()) <= jh.JV_DUAL_CAP + 3


def test_the_jv_pool_is_the_ladder_below_varsity():
    t = _teams(_slice(groups=("9A",), per=1))[0]
    order = jh._order(t)
    assert jh.jv_pool(t) == order[jh.lineup_need("regular"):]
    top = order[0]
    t.records[top.pid] = [0, 40]
    assert jh._order(t)[0] is not top


# --- participation -----------------------------------------------------------

def test_the_box_score_names_exactly_the_players_who_dressed():
    """`played` and `lines` must agree — `_slot_players` resolves doubles off
    `f.n_singles`, so the elastic `fmt` has to reach it or D-slots name the wrong
    people off the varsity singles count, silently."""
    jv = jh.play_jv_season(_slice(groups=("9A",), per=1), 0, "girls", "jvtest")
    rows = [d for t in jv.values() for d in t.schedule]
    assert rows
    for d in rows:
        assert d["played"], d
        on_court = {nm for ln in d["lines"]
                    for nm in (ln["home"] if d["home"] else ln["away"])}
        assert on_court == set(d["played"]), d["shape"]
        assert len(d["played"]) == len(on_court), "a player was dressed twice"


def test_a_player_takes_the_teams_result_in_the_duals_they_dressed_for():
    jv = jh.play_jv_season(_slice(groups=("9A",), per=1), 0, "girls", "jvtest")
    t = next(t for t in jv.values() if t.schedule)
    name = t.schedule[0]["played"][0]
    w, l, ti = world.jhsaa_jv_player_record(t.schedule, name)
    mine = [d for d in t.schedule if name in d["played"]]
    assert w + l + ti == len(mine) > 0
    assert w == sum(1 for d in mine if d["won"] and not d["tied"])
    assert ti == sum(1 for d in mine if d["tied"])
    # never credited a dual they did not dress for
    assert w + l + ti <= len(t.schedule)
    assert world.jhsaa_jv_player_record(t.schedule, "Nobody At All") == (0, 0, 0)


def test_a_varsity_row_carries_no_played_so_the_fold_cannot_reach_it():
    teams = _teams(_slice(groups=("9A",), per=1))
    jh.play_dual(teams[0], teams[1], seed=7)
    d = teams[0].schedule[0]
    assert not d.get("played")
    nm = d["lines"][0]["home"][0]
    assert world.jhsaa_jv_player_record(teams[0].schedule, nm) == (0, 0, 0)


def test_a_season_archived_before_played_folds_to_nothing_not_to_the_teams_record():
    old = [{"level": "jv", "won": True, "tied": False},          # no `played` key
           {"level": "jv", "won": False, "tied": False}]
    assert world.jhsaa_jv_record(old) == (1, 1, 0)               # team record still reads
    assert world.jhsaa_jv_player_record(old, "Anyone") == (0, 0, 0)
