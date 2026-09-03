"""The JV Team State Tournament pilot (JHSAA 2068).

‼️ THESE RUN A REAL JV SEASON. An empty-state check cannot see this event at all —
every rule in it is about who a played season made eligible, which is the lesson
`tests/test_jhsaa_routes.py` was written down for.
"""
import pytest

from app import jhsaa as jh
from app import jhsaa_jv_state as jvs


@pytest.fixture(scope="module")
def jv():
    """A real JV season over four classifications. Wide on purpose: the event is
    CLASSLESS and seeded by REGION, so a slice from one class could show neither."""
    gender, salt = "boys", ""
    by_group = {g: {n: jh.district_teams(ss, 0, salt)
                    for n, ss in sorted(jh.districts(gender, g).items())[:4]}
                for g in ("9A", "5A", "2A", "Group 2")}
    return jh.play_jv_season(by_group, 2068, gender, salt)


@pytest.fixture(scope="module")
def arc(jv):
    return jvs.run_jv_state(jv, gender="boys", year=2068)


@pytest.fixture(scope="module")
def big():
    """‼️ A SEASON BIG ENOUGH TO PLAY THE QUALIFYING ROUND.

    The play-in only happens when MORE than `DIRECT_SEEDS` regions crown a champion.
    The `jv` fixture crowns twelve, so it never reaches that code at all — and the
    real association crowns twenty and reaches it every single year. A `set()` of
    entries (a dataclass, so unhashable) sat on that path through a full green suite
    for exactly this reason. Owner: "my save has a lot more teams and full rosters
    on them so I'm far more likely to fill out all 20 regions than you are in your
    smaller tests."
    """
    gender, salt = "boys", ""
    by_group = {g: {n: jh.district_teams(ss, 0, salt)
                    for n, ss in sorted(jh.districts(gender, g).items())[:8]}
                for g in ("9A", "7A", "5A", "3A", "2A", "Group 2")}
    jv = jh.play_jv_season(by_group, 2068, gender, salt)
    return jvs.run_jv_state(jv, gender=gender, year=2068, seed=11)


def test_a_full_sized_field_plays_the_qualifying_round(big):
    """The path the real association takes every season: more region champions than
    direct seats, so the surplus plays in for the last seats in the draw.

    ‼️ ON `big`, NOT `arc`. A fixture that crowns twelve or fewer regions never runs
    this code at all — and the association crowns twenty and runs it every year. A
    `set()` of entries (a dataclass, so unhashable) sat on this exact path through a
    full green suite. Owner: "my save has a lot more teams and full rosters on them so
    I'm far more likely to fill out all 20 regions than you are in your smaller
    tests."
    """
    ranked = big["ranked"]
    assert len(ranked) > jvs.DIRECT_SEEDS, "fixture too small to test the play-in"
    rest = ranked[jvs.DIRECT_SEEDS:]
    games = big["play_in"]["rounds"][0]
    assert len(games) == len(rest) // 2
    winners = {gm["winner"] for gm in games}
    assert winners <= set(rest)
    assert set(ranked[:jvs.DIRECT_SEEDS]) | winners == set(big["state"]["field"])


def test_the_state_draw_never_skips_a_round(big):
    """‼️ 20 -> 16 -> 8 -> 4 -> 2 (owner, 2026-09: "don't skip the R16"). The
    qualifying round is a round of its OWN, in front of the draw — a play-in winner
    has qualified FOR the bracket, not through its first round — so every column of
    the State draw is exactly half the one before it."""
    import app.world as world
    rounds = world.jhsaa_state_rounds(big["state"])
    alive = [r["alive"] for r in rounds]
    assert alive[0] == len(big["state"]["field"])
    for i, r in enumerate(rounds[1:], 1):
        assert r["alive"] == alive[i - 1] - len(rounds[i - 1]["games"])
    assert rounds[-1]["alive"] == 2 and len(rounds[-1]["games"]) == 1
    # The qualifying round is NOT one of them.
    assert big["play_in"]["round_names"] == [jvs.QUALIFYING_NAME]


def test_the_postseason_never_moves_the_record_it_is_seeded_from(jv):
    """A region final that bumped `wins` would re-rank the statewide field the
    play-in and the State draw are cut from — the mid-event drift the eligibility
    freeze exists to stop, arriving through the record instead of the roster."""
    field = jvs.entries(jv)
    a, b = field[0], field[1]
    before = [(e.jv.wins, e.jv.losses, e.jv.ties,
               e.jv.points_for, e.jv.points_against) for e in (a, b)]
    jvs.play_dual(a, b, seed=4242)
    after = [(e.jv.wins, e.jv.losses, e.jv.ties,
              e.jv.points_for, e.jv.points_against) for e in (a, b)]
    assert before == after


def test_the_dual_is_recorded_on_both_schedules_with_its_box_score(jv):
    """‼️ THE ROW IS THE ONLY WAY THE EVENT REACHES A PROGRAM'S PAGE. `world.
    run_jhsaa` archives JV schedule entries into `world_jhsaa_dual`; a dual played
    and not recorded is a dual nobody can ever see."""
    field = jvs.entries(jv)
    a, b = field[2], field[3]
    n = len(a.jv.schedule)
    jvs.play_dual(a, b, seed=99)
    row = a.jv.schedule[-1]
    assert len(a.jv.schedule) == n + 1 and b.jv.schedule[-1]["opp"] == a.name
    assert row["phase"] == jvs.PHASE and row["level"] == jh.LEVEL_JV
    assert row["shape"] == "3S/2D" and not row["tied"]
    # Five courts, and the players named are the seven who dressed.
    assert len(row["lines"]) == 5
    assert len(row["played"]) == jvs.LINEUP
    assert row["won"] != b.jv.schedule[-1]["won"]


def test_the_card_is_five_odd_courts_and_seven_players():
    """‼️ THE ODD COURT COUNT IS THE LOAD-BEARING PART. Three of the eight
    JV_FORMATS are even and `jv_outcome` really does return draws; a bracket cannot
    advance a tie and this association has no tie-break anywhere. If the format ever
    goes even, every round of this event becomes able to end without a winner."""
    courts = jvs.FORMAT.n_singles + jvs.FORMAT.n_doubles
    assert courts == 5 and courts % 2 == 1
    assert (jvs.FORMAT.n_singles, jvs.FORMAT.n_doubles) == (3, 2)
    assert jvs.LINEUP == 7 and jvs.ROSTER == 16


def test_district_berths_match_the_association_table():
    for n, want in ((1, 1), (2, 1), (5, 1), (6, 2), (9, 2),
                    (10, 3), (15, 3), (16, 4), (40, 4)):
        assert jvs.district_berths(n) == want, n
    assert jvs.district_berths(0) == 0


def test_every_entrant_is_eligible_and_actually_played_jv(jv):
    """Both halves of the eligibility rule, checked against the roster rather than
    against a second copy of the rule: below the varsity eleven on the frozen ladder,
    AND having appeared in a JV dual this season."""
    field = jvs.entries(jv)
    assert field, "no program entered"
    for e in field:
        pool = {p.pid for p in jh.jv_pool(e.jv.team)}
        played = jvs.played_jv(e.jv)
        for p in e.players:
            assert p.pid in pool, (e.name, p.name)
            assert p.name in played, (e.name, p.name)
        # ‼️ 16 IS A CEILING, NOT A SQUAD SIZE — a program carries up to sixteen and
        # dresses seven, so the roster may be anywhere in between.
        assert jvs.LINEUP <= len(e.players) <= jvs.ROSTER


def test_a_program_that_never_played_jv_cannot_enter(jv):
    """"Any school that FIELDED a JV team" — a program with an empty JV schedule has
    not fielded one, however deep its roster."""
    idle = [t for t in jv.values() if not t.schedule]
    entered = {e.name for e in jvs.entries(jv)}
    for t in idle:
        assert t.school.name not in entered


def test_seeding_reads_the_record_not_ability(jv):
    """‼️ The whole reason a JV bracket was once ruled impossible was "JV has no
    ranking". It has a RECORD; what it has no business reading is ability. Two
    programs with identical JV records seed identically however different their
    rosters are — this fails the moment `seed_key` reaches for `jv_strength`.

    ‼️ CONSTRUCTED, not hunted for in the fixture. `points_for`/`against` are floats
    accumulated over ~15 duals, so two programs never tie on them by chance — a
    version of this test that searched the season for a tie asserted on an empty
    list and would have passed vacuously the day the search stopped finding one.
    """
    field = jvs.entries(jv)
    strong = max(field, key=lambda e: jh.jv_strength(e.jv.team))
    weak = min(field, key=lambda e: jh.jv_strength(e.jv.team))
    assert jh.jv_strength(strong.jv.team) > jh.jv_strength(weak.jv.team)
    for e in (strong, weak):                      # same record, different rosters
        e.jv.wins, e.jv.losses, e.jv.ties = 9, 3, 1
        e.jv.points_for, e.jv.points_against = 41.0, 22.0
    assert jvs.seed_key(strong) == jvs.seed_key(weak)


def test_seeding_orders_a_better_record_first(jv):
    """And it is not merely blind to ability — it has to actually rank."""
    field = jvs.entries(jv)
    good, bad = field[0], field[1]
    good.jv.wins, good.jv.losses, good.jv.ties = 12, 1, 0
    bad.jv.wins, bad.jv.losses, bad.jv.ties = 2, 11, 0
    good.jv.points_for = bad.jv.points_for = 30.0
    good.jv.points_against = bad.jv.points_against = 20.0
    assert jvs.seed_key(good) > jvs.seed_key(bad)


def test_the_state_draw_is_cut_from_the_region_champions(arc):
    """Every team in the draw is a region champion, and nobody is in it twice."""
    field = arc["state"]["field"]
    assert field and set(field) <= set(arc["ranked"])
    assert len(field) == len(set(field)) <= jvs.STATE_FIELD


def test_one_champion_per_region_and_a_single_state_champion(arc):
    champs = [c for c in arc["region_champions"].values() if c]
    assert champs and len(champs) == len(set(champs)), "a program won two regions"
    assert arc["ranked"] and set(arc["ranked"]) == set(champs)
    assert arc["champion"] in arc["state"]["field"]


def test_qualifiers_come_from_their_own_district_and_within_its_berths(jv):
    """A district is `(classification, name)` — the association reuses league names at
    every level, so keying on the name alone would merge five leagues into one."""
    field = jvs.entries(jv)
    quals = jvs.district_qualifiers(field)
    seen = {}
    for e in quals:
        seen.setdefault((e.school.group, e.school.district), []).append(e)
    sizes = {}
    for e in field:
        sizes.setdefault((e.school.group, e.school.district), []).append(e)
    for key, got in seen.items():
        assert len(got) == jvs.district_berths(len(sizes[key])), key


def test_the_pilot_does_not_reach_earlier_seasons():
    """A year gate, not a flag: a world that already archived 2067 must keep reading
    it as a season with no JV team tournament in it."""
    assert jh.JV_STATE_FROM == 2068
