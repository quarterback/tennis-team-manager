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


def test_the_play_in_pairs_highest_against_lowest(arc):
    """13v20, 14v19, 15v18, 16v17 — folded from the ranking, so it stays right at any
    number of regions rather than pairing four typed seeds."""
    ranked = arc["ranked"]
    rest = ranked[jvs.DIRECT_SEEDS:]
    for i, p in enumerate(arc["play_in"]):
        assert p["hi"] == rest[i]
        assert p["lo"] == rest[len(rest) - 1 - i]
        assert p["winner"] in (p["hi"], p["lo"])


def test_the_state_field_is_the_direct_seeds_plus_the_play_in_winners(arc):
    direct = arc["ranked"][:jvs.DIRECT_SEEDS]
    winners = {p["winner"] for p in arc["play_in"]}
    assert set(arc["state_field"]) == set(direct) | winners
    assert len(arc["state_field"]) == len(set(arc["state_field"]))
    assert len(arc["state_field"]) <= jvs.STATE_FIELD


def test_one_champion_per_region_and_a_single_state_champion(arc):
    champs = [c for c in arc["region_champions"].values() if c]
    assert champs and len(champs) == len(set(champs)), "a program won two regions"
    assert arc["ranked"] and set(arc["ranked"]) == set(champs)
    assert arc["champion"] in arc["state_field"]


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
