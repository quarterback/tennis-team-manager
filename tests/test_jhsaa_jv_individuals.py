"""The JV individual state tournaments.

Two families of failure, and they hide in different places. The QUALIFYING path
is silent when it breaks — a district that quietly emits no champion, a school
entering an ineligible player, a doubles pair that is one person twice — because
every one of those still produces a draw that renders. The PIGTAIL arithmetic is
silent in the other direction: a field of 97 that loses an entrant, or one of 200
that assigns two play-ins to a seed before every seed has one, still crowns a
champion and still archives.
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

@pytest.mark.parametrize("n", [2, 17, 64, 95, 96])
def test_a_field_at_or_under_the_cap_has_no_pigtails(n):
    main, groups = jvi._pigtails(_field(n))
    assert groups == []
    assert _seeds(main) == list(range(1, n + 1))


def test_ninety_seven_is_one_pigtail_on_the_one_seed():
    """The spec's own worked example: the 1 seed plays the winner of the 97 vs
    the lowest main-field seat."""
    main, groups = jvi._pigtails(_field(97))
    assert _seeds(main) == list(range(1, 96))
    assert len(groups) == 1
    line, group = groups[0]
    assert line == 1
    assert sorted(_seeds(group)) == [96, 97]


def test_one_hundred_is_four_pigtails_on_seeds_one_to_four():
    """Four surplus entrants, four play-ins, on seeds 1-4 in order — and the
    surplus paired against the bottom of the field from the bottom up, so every
    line carries the same combined seed and no top seed draws a softer one."""
    main, groups = jvi._pigtails(_field(100))
    assert _seeds(main) == list(range(1, 93))
    assert [line for line, _ in groups] == [1, 2, 3, 4]
    assert [sorted(_seeds(g)) for _, g in groups] == \
        [[93, 100], [94, 99], [95, 98], [96, 97]]


def test_one_hundred_and_five_is_nine_pigtails_on_seeds_one_to_nine():
    _, groups = jvi._pigtails(_field(105))
    assert [line for line, _ in groups] == list(range(1, 10))
    assert all(len(g) == 2 for _, g in groups)


def test_the_assignment_wraps_only_once_every_seed_has_one():
    """A field of 200: all 96 seeds carry a play-in and then it starts again at
    seed 1, so seeds 1-8 carry a second and NOBODY carries a second before seed
    96 has a first."""
    main, groups = jvi._pigtails(_field(200))
    assert main == []
    assert [line for line, _ in groups] == list(range(1, 97))
    doubled = [line for line, g in groups if len(g) - 1 > 1]
    assert doubled == list(range(1, 9))
    # every line that is not doubled carries exactly one match
    assert {len(g) - 1 for line, g in groups if line not in doubled} == {1}


@pytest.mark.parametrize("n", [96, 97, 100, 105, 128, 191, 192, 200, 400])
def test_every_pigtail_removes_exactly_one_entrant(n):
    """The arithmetic that makes the cap hold at any size: a play-in match takes
    two in and sends one on, so the main draw is the cap whatever the field."""
    main, groups = jvi._pigtails(_field(n))
    matches = sum(len(g) - 1 for _, g in groups)
    assert len(main) + len(groups) == min(n, jvi.MAIN_DRAW)
    assert len(main) + sum(len(g) for _, g in groups) == n
    assert n - matches == min(n, jvi.MAIN_DRAW)
    # nobody is dealt twice and nobody is dropped
    seen = _seeds(main) + [s for _, g in groups for s in _seeds(g)]
    assert sorted(seen) == list(range(1, n + 1))


def test_the_lowest_seeds_are_the_pigtail_entrants():
    """The surplus plays in; the strength of the field does not."""
    n = 120
    main, groups = jvi._pigtails(_field(n))
    playing_in = {s for _, g in groups for s in _seeds(g)}
    assert min(playing_in) > max(_seeds(main))


# --- the state draw ----------------------------------------------------------

@pytest.fixture(scope="module")
def state(by_group):
    return jvi.run_jv_state(by_group, "girls", 0, seed=0)


def test_the_state_field_is_exactly_the_district_champions(by_group, state):
    """Classless: one draw per bracket over every district's champion, whatever
    class they came out of. No at-large, no wild card, nobody else."""
    for bracket in jvi.BRACKETS:
        champs = jvi.district_champions(by_group, bracket, gender="girls",
                                        year=0, seed=0)
        assert champs, bracket
        d = state[bracket]
        assert len(d["entries"]) == len(champs)
        assert {e["school"] for e in d["entries"]} == {c.school for c in champs}
        # every entrant carries a district title, and no two came from one district
        districts = [e["district"] for e in d["entries"]]
        assert all(districts) and len(set(districts)) == len(districts)


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

def test_the_play_in_archives_as_its_own_pre_round(by_group, monkeypatch):
    """Forced by shrinking the cap rather than by inventing a 97-school
    association: the pre-round has to be a DISTINCT first round in the archive,
    each match naming the seed line it feeds, or the bracket cannot render it and
    a result is untraceable."""
    champs = jvi.district_champions(by_group, jvi.SINGLES, gender="girls",
                                    year=0, seed=0)
    cap = max(2, len(champs) - 2)
    monkeypatch.setattr(jvi, "MAIN_DRAW", cap)
    d = jvi.run_state(champs, jvi.SINGLES, gender="girls", seed=5)
    arc = ji.draw_to_dict(d)
    pre = arc["rounds"][0]
    assert all(m["rnd"] == jvi.PIGTAIL_ROUND for m in pre)
    assert [m["seed_line"] for m in pre] == list(range(1, len(pre) + 1))
    # the main draw never claims one
    assert all("seed_line" not in m
               for rnd in arc["rounds"][1:] for m in rnd)
    # the field is intact: everyone who qualified is in `entries`, play-in
    # losers included, so a finish can be read for every one of them
    assert len(arc["entries"]) == len(champs)
    assert len(arc["finishes"]) == len(champs)
    assert arc["champion"] is not None


def test_a_played_pigtail_survivor_reaches_the_main_draw(by_group, monkeypatch):
    champs = jvi.district_champions(by_group, jvi.DOUBLES, gender="girls",
                                    year=0, seed=0)
    monkeypatch.setattr(jvi, "MAIN_DRAW", max(2, len(champs) - 1))
    d = jvi.run_state(champs, jvi.DOUBLES, gender="girls", seed=5)
    pre = d.rounds[0]
    assert len(pre) == 1
    survivor = pre[0].winner
    later = {e.key for rnd in d.rounds[1:] for m in rnd for e in (m.hi, m.lo)}
    assert survivor.key in later
    loser = pre[0].lo if pre[0].winner_is_hi else pre[0].hi
    assert loser.key not in later


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
        conn.execute(
            "INSERT INTO world_jhsaa (world_id, year, gender, data)"
            " VALUES (?,?,?,?)",
            (w["id"], 0, "girls", json.dumps(
                {"season_year": 2040, "champions": {}, "awards": {},
                 "standings": {"5A": {"Basalt League": [
                     {"school": "Sixes", "record": "9-3", "place": 1}]}}})))
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


def test_it_stays_off_the_varsity_career_title_roll(archived):
    """The other half of the rule, and it is not a contradiction: a JV title is a
    result on a player's page, and it is not a varsity counter. The repeat roll
    ranks by dual FLIGHT WEIGHT, which prices courts the association plays — JV
    brackets have no such weight and must not be given an invented one."""
    from app import world as wd
    assert wd.jhsaa_individual_title_repeats(archived["id"], "girls",
                                             minimum=1) == []


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
    assert "JV Singles" in html and "Bo Reyes" in html
    # classless: the event heading carries no class, and the hero says State
    assert "JV Singles State Champion" in html
    r2 = client.get("/jhsaa/individuals?flight=JVD&g=girls&year=0")
    assert r2.status_code == 200 and "Cy Odom" in r2.data.decode()
    # the class rail does not scope the draw — any class shows the same champion
    r3 = client.get("/jhsaa/individuals?flight=JVS&g=girls&year=0&group=1A")
    assert "Bo Reyes" in r3.data.decode()


def test_the_view_splits_a_play_in_off_the_bracket_tree(by_group, monkeypatch):
    """`_bracket_canvas` links columns positionally on the main draw's halving, so
    a pigtail pre-round must reach the page as its own panel, never as a column —
    checked on the assembled archive dict the view consumes."""
    import json
    from app import world as wd
    from app.web import state as st
    champs = jvi.district_champions(by_group, jvi.SINGLES, gender="girls",
                                    year=0, seed=0)
    monkeypatch.setattr(jvi, "MAIN_DRAW", max(2, len(champs) - 2))
    d = ji.draw_to_dict(jvi.run_state(champs, jvi.SINGLES, gender="girls",
                                      seed=5))
    w = wd.get_or_create(wd.DEFAULT_SEED)
    conn = wd._db()
    try:
        conn.execute("DELETE FROM world_jhsaa_individual WHERE world_id=?"
                     " AND flight=?", (w["id"], jvi.SINGLES))
        conn.execute(
            "INSERT INTO world_jhsaa_individual (world_id, year, gender, grp,"
            " flight, data) VALUES (?,?,?,?,?,?)",
            (w["id"], 0, "girls", jvi.GROUP_KEY, jvi.SINGLES, json.dumps(d)))
        conn.commit()
    finally:
        conn.close()
    view = st.jhsaa_individual_view(wd.DEFAULT_SEED, "girls", "9A",
                                    jvi.SINGLES, 0)
    assert view["ready"] and view["jv"] and view["group_label"] == ""
    assert len(view["playins"]) == 2
    assert [p["seed_line"] for p in view["playins"]] == [1, 2]
    # the canvas columns are the MAIN rounds only, halving as the tree needs
    assert len(view["rounds"]) == len(d["rounds"]) - 1
    assert all(m["rnd"] != jvi.PIGTAIL_ROUND
               for c in view["rounds"] for m in c["games"] if "rnd" in m)


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
