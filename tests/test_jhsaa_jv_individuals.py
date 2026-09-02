"""The JV individual state tournaments.

Two families of failure, and they hide in different places. The QUALIFYING path
is silent when it breaks — a district that quietly emits no champion, a school
entering an ineligible player, a doubles pair that is one person twice — because
every one of those still produces a draw that renders. The QUALIFYING arithmetic
is silent in the other direction: a draw that lands one short of the open seats
still crowns a champion and still archives.
"""
import pytest

import app.jhsaa as jh
import app.jhsaa_individuals as ji
import app.jhsaa_jv_individuals as jvi


# --- fixtures ----------------------------------------------------------------

def _slice(gender="girls", groups=("9A", "5A", "1A"), per=3, salt="jvind"):
    """Real districts across three classifications — the state draw is CLASSLESS,
    so a fixture drawn from one class could not show that.

    ‼️ IT HAS TO BE THIS WIDE FOR THE DOUBLES BRACKET TO EXIST AT ALL. A pair is
    three eligible seniors deep (No. 1 plays singles, the next two pair) and the
    JV pool is the roster below the varsity eleven — measured on this fixture,
    ~72% of programs have a JV senior but only ~14% have three, so a two-district
    slice crowns one doubles champion and no draw. That thinness is the event
    working as specified (a school short of eligible seniors enters nobody), not
    a fixture accident, which is why the slice grows rather than the rule."""
    return {g: {n: jh.district_teams(ss, 0, salt)
                for n, ss in sorted(jh.districts(gender, g).items())[:per]}
            for g in groups}


@pytest.fixture(scope="module")
def by_group():
    return _slice()


def _one_district(by_group):
    group, dists = sorted(by_group.items())[0]
    district, teams = sorted(dists.items())[0]
    return group, district, teams


class _Squad:
    """A stand-in program, for the eligibility cases a real roster cannot pose.

    ‼️ IT EXISTS BECAUSE THE OBVIOUS TEST IS VACUOUS. "A district with no
    eligible seniors" written as `t.roster = [p for p in t.roster if p.grade !=
    12]` leaves a real roster of ~19 with ~14, and dropping it below
    `lineup_need("regular")` empties `jv_pool` outright — so the assertion passes
    for the wrong reason and would keep passing if the grade rule were deleted.
    A squad is assembled with a full varsity eleven UNDER the players being
    tested, so what is left over is a real JV pool that is genuinely ineligible.

    ‼️ AND IT NEVER MUTATES A PLAYER. `build_roster`'s Prospects are globally
    cached and shared across saves (CLAUDE.md), so grades are SELECTED, never
    rewritten. Only the roster list is ours."""

    def __init__(self, school, roster):
        self.school, self.roster, self.records = school, list(roster), {}


def _by_grade(by_group) -> dict:
    """Every fixture player, bucketed by grade and sorted STRONGEST FIRST. Pids
    stay distinct across programs, so a squad can be assembled from more than one.

    ‼️ THE SORT IS WHAT MAKES A SQUAD CONSTRUCTIBLE. `jv_pool` cuts the ladder by
    ABILITY, not by grade, so "eleven seniors on varsity and ninth-graders on JV"
    is only true if those seniors are actually the better players — a strong
    freshman would otherwise displace a weak senior into the JV pool and quietly
    invert the case under test. Squads are therefore built from the strongest
    upperclassmen down and the intended JV pool is asserted, not assumed."""
    out: dict = {}
    for d in by_group.values():
        for ts in d.values():
            for t in ts:
                for p in t.roster:
                    out.setdefault(p.grade, []).append(p)
    return {k: sorted(v, key=lambda p: -p.current_overall())
            for k, v in out.items()}


def _stub(seed_no: int) -> ji.Entry:
    """A field member that only has to be ORDERED. The pigtail split is pure
    arithmetic over a seed-ordered list, so nothing here needs a roster, an
    engine player or a rating that means anything — only that entry `i` is the
    `i`-th seed, which is what lets the sizes the spec names be tested exactly
    rather than approximately."""
    return ji.Entry(school=f"S{seed_no:04d}", players=[], engine=None,
                    rating=10_000.0 - seed_no, flight=jvi.SINGLES)


def _field(n: int) -> list:
    return [_stub(i) for i in range(1, n + 1)]


def _seeds(entries) -> list:
    """The seed numbers of a stub group, in the order they were dealt."""
    return [int(e.school[1:]) for e in entries]


# --- eligibility -------------------------------------------------------------

def test_every_entrant_is_a_jv_player_of_an_eligible_grade(by_group):
    """Both halves of the rule, checked against the roster rather than against a
    second copy of the rule: outside the varsity eleven, and of a grade the
    bracket admits — seniors in singles, juniors and seniors in doubles."""
    teams = [t for d in by_group.values() for ts in d.values() for t in ts]
    seen = {b: 0 for b in jvi.BRACKETS}
    for t in teams:
        varsity = {p.pid for p in jh._order(t)[:jh.lineup_need("regular")]}
        for bracket in jvi.BRACKETS:
            e = jvi.school_entry(t, bracket)
            if e is None:
                continue
            seen[bracket] += 1
            for p in e.players:
                assert p.grade in jvi.ELIGIBLE_GRADES[bracket], \
                    (bracket, t.school.name, p.name, p.grade)
                assert p.pid not in varsity, (t.school.name, p.name)
    assert all(seen.values()), seen


def test_the_singles_bracket_is_seniors_only(by_group):
    teams = [t for d in by_group.values() for ts in d.values() for t in ts]
    assert jvi.ELIGIBLE_GRADES[jvi.SINGLES] == (12,)
    for t in teams:
        e = jvi.school_entry(t, jvi.SINGLES)
        if e is not None:
            assert e.players[0].grade == 12


def test_the_doubles_bracket_reaches_down_to_juniors(by_group):
    """It has to, and the reason is arithmetic: a pair is three eligible players
    deep once the singles entrant is held out, and most programs have nowhere
    near three JV seniors. A juniors-and-seniors pool is what makes the bracket
    fieldable — so this asserts that juniors are actually being USED, not merely
    that the constant says they may be."""
    teams = [t for d in by_group.values() for ts in d.values() for t in ts]
    juniors = sum(1 for t in teams
                  for p in (jvi.school_entry(t, jvi.DOUBLES) or
                            type("E", (), {"players": ()})).players
                  if p.grade == 11)
    assert juniors, "no junior entered the doubles bracket"
    seniors_only = sum(1 for t in teams if len(jvi.jv_seniors(t)) >= 3)
    assert sum(1 for t in teams
               if jvi.school_entry(t, jvi.DOUBLES) is not None) > seniors_only


def test_the_singles_entrant_is_held_out_of_the_pair(by_group):
    """A school fields three different people. Now that the pools differ — a
    senior JV No. 1 tops BOTH — that has to be enforced rather than fall out of
    disjoint rank tuples."""
    teams = [t for d in by_group.values() for ts in d.values() for t in ts]
    checked = 0
    for t in teams:
        s = jvi.school_entry(t, jvi.SINGLES)
        d = jvi.school_entry(t, jvi.DOUBLES)
        if s is None or d is None:
            continue
        checked += 1
        pids = [p.pid for p in s.players + d.players]
        assert len(set(pids)) == 3, t.school.name
        # and they are the top of each pool, in ladder order
        pool = jvi.jv_ladder(t)
        assert s.players[0].pid == jvi.jv_eligible(t, jvi.SINGLES, pool)[0].pid
        rest = [p for p in jvi.jv_eligible(t, jvi.DOUBLES, pool)
                if p.pid != s.players[0].pid]
        assert [p.pid for p in d.players] == [p.pid for p in rest[:2]]
    assert checked


def test_a_school_short_of_eligible_players_enters_nobody(by_group):
    """Not a degraded entry and not a crash — a pair is two DIFFERENT people and
    there is nothing to fall back to, so the school simply sits the year out."""
    _, _, teams = _one_district(by_group)
    g = _by_grade(by_group)
    need = jh.lineup_need("regular")
    school = teams[0].school
    # the strongest upperclassmen make a full varsity eleven; the weakest
    # ninth-graders are the JV, so nobody eligible is below the line
    base = sorted(g[12] + g[11], key=lambda p: -p.current_overall())[:need]
    bench = g[9][-6:]
    none_eligible = _Squad(school, base + bench)
    assert {p.pid for p in jvi.jv_ladder(none_eligible)} == {p.pid for p in bench}
    assert jvi.school_entry(none_eligible, jvi.SINGLES) is None
    assert jvi.school_entry(none_eligible, jvi.DOUBLES) is None
    # ONE eligible JV player — the association's weakest senior, so he lands
    # below the eleven: a singles entry, and still not a pair.
    weak_sr, weak_jr = g[12][-1], g[11][-1]
    one = _Squad(school, base + bench[:5] + [weak_sr])
    assert weak_sr.pid in {p.pid for p in jvi.jv_ladder(one)}
    assert jvi.school_entry(one, jvi.SINGLES) is not None
    assert jvi.school_entry(one, jvi.DOUBLES) is None
    # TWO: a senior and a junior. The senior takes singles, so the pair is one
    # short — which is exactly the rule that holds the singles entrant out.
    two = _Squad(school, base + bench[:4] + [weak_sr, weak_jr])
    assert jvi.school_entry(two, jvi.SINGLES) is not None
    assert jvi.school_entry(two, jvi.DOUBLES) is None
    # THREE eligible: now it can field both.
    three = _Squad(school, base + bench[:3] + [weak_sr, weak_jr, g[11][-2]])
    assert jvi.school_entry(three, jvi.SINGLES) is not None
    assert jvi.school_entry(three, jvi.DOUBLES) is not None


# --- the district qualifier --------------------------------------------------

def test_a_district_of_several_eligible_schools_crowns_exactly_one(by_group):
    group, district, teams = _one_district(by_group)
    field = jvi.district_field(teams, jvi.SINGLES, group=group, district=district)
    assert len(field) > 1, "fixture district has nothing to qualify"
    d = jvi.run_district(teams, jvi.SINGLES, gender="girls", group=group,
                         district=district, seed=11)
    assert d.champion is not None
    assert d.rounds, "several entries and nobody played"
    # Exactly one survivor: every match eliminates one, so the field minus the
    # matches played is the champion alone.
    played = sum(len(r) for r in d.rounds)
    assert len(d.entries) - played == 1


def test_a_district_of_one_eligible_school_qualifies_unopposed(by_group):
    """One entry is a champion, not an empty draw — the district seat is filled
    by the only school that could fill it, having played nobody."""
    group, district, teams = _one_district(by_group)
    solo = [t for t in teams if jvi.school_entry(t, jvi.SINGLES) is not None][:1]
    d = jvi.run_district(solo, jvi.SINGLES, gender="girls", group=group,
                         district=district, seed=11)
    assert d is not None and d.champion is not None
    assert d.rounds == []
    assert d.champion.school == solo[0].school.name


def test_a_district_with_no_eligible_players_emits_no_champion(by_group):
    """A whole league of programs whose upperclassmen are all on varsity produces
    nothing, and the state field is one shorter that year. That is by design, so
    it must be a None rather than an empty draw somebody later reads a champion
    off."""
    group, district, teams = _one_district(by_group)
    g = _by_grade(by_group)
    need = jh.lineup_need("regular")
    base = sorted(g[12] + g[11], key=lambda p: -p.current_overall())[:need]
    league = [_Squad(t.school, base + g[9][-5:]) for t in teams]
    assert all(jvi.jv_ladder(s) for s in league), "vacuous: no JV pool at all"
    for bracket in jvi.BRACKETS:
        assert jvi.district_field(league, bracket, group=group,
                                  district=district) == []
        assert jvi.run_district(league, bracket, gender="girls", group=group,
                                district=district, seed=11) is None


def test_the_district_title_is_carried_on_the_entry(by_group):
    """It is an INDIVIDUAL honour for the player and the school, not a road unit —
    so it rides on the entry into the state draw, with the full
    (classification, name) identity, since the JHSAA reuses district names at
    every level."""
    group, district, teams = _one_district(by_group)
    d = jvi.run_district(teams, jvi.SINGLES, gender="girls", group=group,
                         district=district, seed=11)
    assert d.champion.district == f"{group} {district}"
    assert group in d.champion.district and district in d.champion.district


# --- the 96 cap and the pigtails ---------------------------------------------

# --- the qualifying arithmetic (owner spec 2026-09) --------------------------

@pytest.mark.parametrize("q,s,want", [
    # The owner's three worked examples, verbatim.
    (95, 32, [31, 32]),
    (94, 33, [28, 33]),
    (96, 31, [34, 31]),
])
def test_qualifying_reproduces_the_worked_examples(q, s, want):
    assert jvi.qualifying_rounds(q, s) == want


@pytest.mark.parametrize("q,s", [(95, 32), (94, 33), (96, 31), (90, 30),
                                 (128, 20), (40, 32), (200, 32), (60, 34)])
def test_qualifying_lands_on_exactly_the_open_spots(q, s):
    """A qualifying draw exists to produce a fixed number of qualifiers, so the
    one thing it must never do is produce a different number."""
    rounds = jvi.qualifying_rounds(q, s)
    cur = q
    for m in rounds:
        assert 0 < m <= cur // 2, (q, s, m)   # a round cannot pair more than half
        cur -= m
    assert cur == s, (q, s, rounds)


def test_the_final_qualifying_round_is_complete():
    """The shape's whole point: the LAST round is 2S entries playing S matches,
    so every match in it produces one qualifier. Byes live in the opening round."""
    for q, s in ((95, 32), (94, 33), (96, 31), (120, 30)):
        rounds = jvi.qualifying_rounds(q, s)
        before_final = q - sum(rounds[:-1])
        assert before_final == 2 * s, (q, s)
        assert rounds[-1] == s, (q, s)


def test_the_opening_round_byes_the_top_of_the_field():
    """Q=95, S=32: 31 matches, 62 play, 33 bye — and the 62 are the LOWEST seeds,
    which is what seeding the draw and assigning byes on the ranking means."""
    field = _field(95)
    direct, pairs = jvi._round_pairs(field, 95 - 31)
    assert len(pairs) == 31 and len(direct) == 33
    playing = {s for _, a, b in pairs for s in _seeds([a, b])}
    assert min(playing) > max(_seeds(direct))


def test_spots_close_the_field_at_128():
    assert jvi.STATE_FIELD == 128
    assert jvi.qualifying_spots(95, 1) == 32          # 95 champs + autobid
    assert jvi.qualifying_spots(95) == 33
    assert jvi.qualifying_spots(200) == 0             # never negative


# --- the state draw ----------------------------------------------------------

@pytest.fixture(scope="module")
def state(by_group):
    return jvi.run_jv_state(by_group, "girls", 0, seed=0)["state"]


def test_it_crowns_one_champion_per_bracket_per_gender(state):
    assert set(state) == set(jvi.BRACKETS)
    for bracket, d in state.items():
        assert d["group"] == jvi.GROUP_KEY, "a classless event stored under a class"
        assert d["flight"] == bracket
        assert d["champion"] is not None and d["runner_up"] is not None
        assert d["champion"] != d["runner_up"]


def test_the_doubles_draw_is_played_by_pairs(state):
    d = state[jvi.DOUBLES]
    for e in d["entries"]:
        assert len(e["players"]) == 2
        assert e["players"][0]["pid"] != e["players"][1]["pid"]
        assert " / " in e["full_label"]
    assert all(len(e["players"]) == 1 for e in state[jvi.SINGLES]["entries"])


def test_matches_run_the_full_best_of_three(state):
    """`INDIV_FORMAT` — the college championships' own, imported — so a decider is
    a real third set and never a match tiebreak, at either level. Nothing here
    reads a set or tiebreak rule of its own."""
    assert jvi.INDIV_FORMAT.best_of == 3
    assert not jvi.INDIV_FORMAT.final_set_tiebreak
    for d in state.values():
        for rnd in d["rounds"]:
            for m in rnd:
                sets = m["scoreline"].split()
                assert 2 <= len(sets) <= 3, m["scoreline"]
                for s in sets:
                    a, b = (int(x.split("(")[0]) for x in s.split("-"))
                    assert max(a, b) >= 6, m["scoreline"]


def test_a_rerun_reproduces_the_whole_thing(by_group):
    """Seeded determinism, end to end: the qualifiers, the field, the draw and
    every scoreline."""
    a = jvi.run_jv_state(by_group, "girls", 0, seed=0)
    b = jvi.run_jv_state(by_group, "girls", 0, seed=0)
    assert a == b
    assert a != jvi.run_jv_state(by_group, "girls", 0, seed=7)


def test_the_event_credits_nothing_to_the_varsity_season(by_group):
    """JV counts for nothing anywhere — no records, no résumé rows, no ladder
    movement. `JVTeam` guarantees that for the JV season by having no counters to
    reach; this event has to guarantee it by not writing."""
    teams = [t for d in by_group.values() for ts in d.values() for t in ts]
    before = [({k: list(v) for k, v in t.records.items()},
               {k: list(v) for k, v in t.matches.items()},
               [p.pid for p in jh._order(t)]) for t in teams]
    jvi.run_jv_state(by_group, "girls", 0, seed=3)
    after = [({k: list(v) for k, v in t.records.items()},
              {k: list(v) for k, v in t.matches.items()},
              [p.pid for p in jh._order(t)]) for t in teams]
    assert before == after


# --- the archived play-in round ----------------------------------------------

# --- it reads back as a state honour -----------------------------------------
#
# ‼️ HAND-ARCHIVED, NOT SIMULATED. The read path is what is under test — a
# CLASSLESS draw has to reach surfaces whose queries are all scoped to a
# classification — and a real season costs minutes a gender to reach two rows.
# The rows written here are exactly the shape `run_jhsaa` writes.

@pytest.fixture(scope="module")
def archived():
    import json
    from app import world as wd

    w = wd.get_or_create(wd.DEFAULT_SEED)
    conn = wd._db()
    try:
        conn.execute("DELETE FROM world_jhsaa WHERE world_id=?", (w["id"],))
        conn.execute("DELETE FROM world_jhsaa_individual WHERE world_id=?",
                     (w["id"],))
        # ‼️ A SEASON SUMMARY ROW PER GENDER. The champions roll walks
        # `world.jhsaa_years`, which reads THIS table — so a gender with draws
        # but no season row has an empty roll, and the JV rows below would look
        # like a boys/girls bug that is really a missing fixture.
        conn.executemany(
            "INSERT INTO world_jhsaa (world_id, year, gender, data)"
            " VALUES (?,?,?,?)",
            [(w["id"], 0, g, json.dumps(
                {"season_year": 2040, "champions": {}, "awards": {},
                 "standings": {"5A": {"Basalt League": [
                     {"school": "Sixes", "record": "9-3", "place": 1}]}}}))
             for g in ("girls", "boys")])
        def draw(flight, players):
            full = " / ".join(p["name"] for p in players)
            return json.dumps({
                "gender": "girls", "group": jvi.GROUP_KEY, "flight": flight,
                "n_seeds": 2,
                "entries": [{"school": "Harrow", "label": "Nobody",
                             "full_label": "Nobody", "seed": 1,
                             "district": "9A Quarry League",
                             "players": [{"pid": "z" * 16, "name": "Nobody",
                                          "grade": 12}]},
                            {"school": "Sixes", "label": full,
                             "full_label": full, "seed": 2,
                             "district": "5A Basalt League",
                             "players": players}],
                "champion": 1, "runner_up": 0,
                "finishes": {"Sixes": {"label": "Champion", "tag": "CHAMP"},
                             "Harrow": {"label": "Runner-up", "tag": "F"}},
                "rounds": [[{"rnd": "Final", "hi": 0, "lo": 1,
                             "winner_is_hi": False, "scoreline": "6-4 6-4",
                             "upset": True}]]})
        conn.executemany(
            "INSERT INTO world_jhsaa_individual (world_id, year, gender, grp,"
            " flight, data) VALUES (?,?,?,?,?,?)",
            [(w["id"], 0, "girls", jvi.GROUP_KEY, jvi.SINGLES,
              draw(jvi.SINGLES, [{"pid": "b" * 16, "name": "Bo Reyes",
                                  "grade": 12}])),
             (w["id"], 0, "girls", jvi.GROUP_KEY, jvi.DOUBLES,
              draw(jvi.DOUBLES, [{"pid": "c" * 16, "name": "Cy Odom",
                                  "grade": 11},
                                 {"pid": "d" * 16, "name": "Dee Fox",
                                  "grade": 12}])),
             # The BOYS draws of the same season. Four rows, because the event
             # crowns four champions a year: two brackets × two genders, each
             # its own draw under the one classless key.
             (w["id"], 0, "boys", jvi.GROUP_KEY, jvi.SINGLES,
              draw(jvi.SINGLES, [{"pid": "m" * 16, "name": "Milo Vance",
                                  "grade": 12}])),
             (w["id"], 0, "boys", jvi.GROUP_KEY, jvi.DOUBLES,
              draw(jvi.DOUBLES, [{"pid": "n" * 16, "name": "Nate Ferro",
                                  "grade": 11},
                                 {"pid": "o" * 16, "name": "Otto Lind",
                                  "grade": 12}]))])
        conn.commit()
    finally:
        conn.close()
    return w


def test_a_jv_title_shows_on_the_player_page_like_any_other_flight(archived):
    """Owner rule: "it's still a state honour, so this tournament shows up on a
    player page no different than the other individual flights." The player's own
    class is 5A and the draw is classless, so a group-scoped query would drop it."""
    from app import world as wd
    rows = wd.jhsaa_individual_results(archived["id"], 0, "girls", "5A",
                                       "b" * 16)
    assert [r["flight"] for r in rows] == [jvi.SINGLES]
    r = rows[0]
    assert r["champion"] and r["tag"] == "CHAMP"
    assert r["flight_name"] == jvi.BRACKET_NAMES[jvi.SINGLES]
    # the DRAW's group, not the page's: it was won statewide
    assert r["group"] == jvi.GROUP_KEY


def test_the_doubles_partner_reads_through_like_a_varsity_pair(archived):
    from app import world as wd
    rows = wd.jhsaa_individual_results(archived["id"], 0, "girls", "5A",
                                       "c" * 16)
    assert rows[0]["partner"] == "Dee Fox"
    assert rows[0]["flight_name"] == jvi.BRACKET_NAMES[jvi.DOUBLES]


def test_a_class_scoped_query_still_finds_it_from_any_class(archived):
    """It is CLASSLESS, so the champion's page finds it whatever class that
    program played in — the one property a per-class archive key would break."""
    from app import world as wd
    for grp in ("9A", "5A", "1A"):
        rows = wd.jhsaa_individual_results(archived["id"], 0, "girls", grp,
                                           "b" * 16)
        assert len(rows) == 1, grp


def test_the_program_page_counts_it_as_an_individual_state_title(archived):
    from app import world as wd
    seasons = [{"year": 0, "season_year": 2040, "group": "5A"}]
    got = wd.jhsaa_school_individual_champions(archived["id"], "girls",
                                               "Sixes", seasons)
    assert {r["flight"] for r in got} == set(jvi.BRACKETS)
    assert all(r["jv"] and r["group"] == jvi.GROUP_KEY for r in got)
    assert all(r["flight_name"] == jvi.BRACKET_NAMES[r["flight"]] for r in got)


def test_a_jv_title_counts_on_the_career_title_roll(archived):
    """The mixed correction's own logic, applied consistently: the repeat roll is
    a record of state titles a PERSON has won, and a JV state title is one of
    them. It ranks LAST in the flight tie-break — a JV bracket has no
    `FLIGHT_WEIGHTS` entry and is never given an invented one — and its rows
    carry an EMPTY group, because the title was won statewide and the flight
    name already says JV."""
    from app import world as wd
    rows = wd.jhsaa_individual_title_repeats(archived["id"], "girls", minimum=1)
    by_pid = {r["pid"]: r for r in rows}
    bo = by_pid["b" * 16]
    assert [t["flight"] for t in bo["titles"]] == [jvi.SINGLES]
    assert bo["titles"][0]["flight_name"] == jvi.BRACKET_NAMES[jvi.SINGLES]
    assert bo["titles"][0]["group"] == ""
    # both members of the pair are credited, partner carried as context
    assert by_pid["c" * 16]["titles"][0]["partner"] == "Dee Fox"
    assert by_pid["d" * 16]["titles"][0]["partner"] == "Cy Odom"


def test_the_championship_page_renders_the_jv_draw(archived, monkeypatch):
    """Through the ROUTE, not the view function — the route-wiring lesson this
    section keeps written at the top of `test_jhsaa_routes.py` — and against the
    archived draw, because an empty-state render cannot see a bracket at all.

    `is_primed`/`prime` are stubbed the way `test_jhsaa_toc.py` does it: once a
    world row exists, `_prime_world` answers every cold request with the loading
    page while it warms the college roster cache — minutes of work nothing on a
    JHSAA page reads."""
    import os
    from app import world as wd
    os.environ.setdefault("PTC_NO_BOOT_WARM", "1")
    monkeypatch.setattr(wd, "is_primed", lambda *a, **k: True)
    monkeypatch.setattr(wd, "prime", lambda *a, **k: None)
    from app.web.server import create_app
    client = create_app().test_client()
    r = client.get("/jhsaa/individuals?flight=JVS&g=girls&year=0")
    assert r.status_code == 200
    html = r.data.decode()
    assert "Bo Reyes" in html
    # ‼️ THE HEADING IS JUST THE EVENT (owner, 2026-08): "JV Singles". No class
    # — it is classless — no gender, since the scope bar's switch is what picks
    # one, and no "State", which is implied here as it is for every flight.
    assert "JV Singles Champion" in html
    assert "Statewide" not in html and "JV Singles State" not in html
    r2 = client.get("/jhsaa/individuals?flight=JVD&g=girls&year=0")
    assert r2.status_code == 200 and "Cy Odom" in r2.data.decode()
    # the class rail does not scope the draw — any class shows the same champion
    r3 = client.get("/jhsaa/individuals?flight=JVS&g=girls&year=0&group=1A")
    assert "Bo Reyes" in r3.data.decode()
    # ... and the History → Individual Champions roll tracks the JV titles the
    # same way, one flight from the dropdown, whatever class the rail shows
    for grp in ("9A", "1A"):
        h = client.get(f"/jhsaa/individual-champions?flight=JVS&group={grp}"
                       "&g=girls").data.decode()
        assert "Bo Reyes" in h and "def." in h, grp
    h = client.get("/jhsaa/individual-champions?flight=JVD&g=girls").data.decode()
    assert "Cy Odom" in h and "Dee Fox" in h
    # the varsity roll did not pick the JV titles up
    h = client.get("/jhsaa/individual-champions?flight=S1&group=5A&g=girls"
                   ).data.decode()
    assert "Bo Reyes" not in h


def test_each_gender_renders_its_own_jv_draw(archived, monkeypatch):
    """Four champions a season — two brackets × two genders — and the boys/girls
    switch on the scope bar is what picks one. A gender must never see the
    other's champion: the brackets share ONE classless archive key, so the
    gender column is the only thing separating them."""
    import os
    from app import world as wd
    os.environ.setdefault("PTC_NO_BOOT_WARM", "1")
    monkeypatch.setattr(wd, "is_primed", lambda *a, **k: True)
    monkeypatch.setattr(wd, "prime", lambda *a, **k: None)
    from app.web.server import create_app
    client = create_app().test_client()
    want = {("girls", jvi.SINGLES): ("Bo Reyes", "Milo Vance"),
            ("boys", jvi.SINGLES): ("Milo Vance", "Bo Reyes"),
            ("girls", jvi.DOUBLES): ("Cy Odom", "Nate Ferro"),
            ("boys", jvi.DOUBLES): ("Nate Ferro", "Cy Odom")}
    for (g, fl), (mine, theirs) in want.items():
        for path in ("/jhsaa/individuals?year=0&", "/jhsaa/individual-champions?"):
            h = client.get(f"{path}flight={fl}&g={g}").data.decode()
            assert mine in h, (g, fl, path)
            assert theirs not in h, (g, fl, path)


# --- the varsity event is untouched ------------------------------------------

def test_the_varsity_archive_shape_did_not_move():
    """`district` and `seed_line` are emitted only when set, so every varsity
    draw archives exactly the bytes it did before this event existed."""
    e = ji.Entry(school="X", players=[], engine=None, rating=1.0, flight="S1")
    assert e.district == ""
    d = ji.FlightDraw(gender="girls", group="1A", flight="S1", entries=[e])
    arc = ji.draw_to_dict(d)
    assert set(arc["entries"][0]) == {"school", "label", "full_label", "seed",
                                      "players"}
