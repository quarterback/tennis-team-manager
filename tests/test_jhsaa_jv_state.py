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
    """‼️ A SEASON BIG ENOUGH TO PLAY AN OPENING ROUND.

    A field that fills its bracket exactly plays no opening round at all, so a small
    fixture never reaches that code — and the real association crowns twenty regions
    into a 32-slot draw and reaches it every single year. Owner: "my save has a lot
    more teams and full rosters on them so I'm far more likely to fill out all 20
    regions than you are in your smaller tests."
    """
    gender, salt = "boys", ""
    by_group = {g: {n: jh.district_teams(ss, 0, salt)
                    for n, ss in sorted(jh.districts(gender, g).items())[:8]}
                for g in ("9A", "7A", "5A", "3A", "2A", "Group 2")}
    jv = jh.play_jv_season(by_group, 2068, gender, salt)
    return jvs.run_jv_state(jv, gender=gender, year=2068, seed=11)


def test_every_region_champion_is_in_the_state_draw(big):
    """‼️ WINNING YOUR REGION IS QUALIFYING — nothing sits in front of State to be
    survived. All twenty champions ARE the field (owner, 2026-09: "the qualifiers who
    get in, all 20, are already at State; there is no qualifying once into the field
    of 20"): twelve are seeded through and eight open in the Round of 20, which is
    the TOC's own shape — twelve champions in a 16 draw open in a Round of 12 and
    nobody calls that qualifying either. The event used to cut the field by hand and
    play a play-in in a bracket of its own; owner: "you didn't have to invent a
    bespoke JV format when we already have lots of bracket formats that work beyond
    16."

    ‼️ ON `big`, NOT `arc`. A fixture crowning few enough regions to fill no opening
    round never runs this at all, and the association crowns twenty every year.
    """
    import app.world as world
    assert "play_in" not in big, "the separate play-in bracket is gone"
    rounds = world.jhsaa_state_rounds(big["state"])
    # ‼️ NAMED BY ITS FIELD, like varsity's R32/R24/R40 and the TOC's Round of 12 —
    # never "qualifying", which would describe a gate this event does not have.
    assert rounds[0]["name"] == f"Round of {len(big['ranked'])}"
    assert set(big["state"]["field"]) == set(big["ranked"])
    # Everyone in the opening round is a region champion, and it is a real round of
    # the same draw rather than a feeder into a fresh one.
    playing = {t for gm in rounds[0]["games"] for t in (gm["home"], gm["away"])}
    assert playing <= set(big["ranked"]) and playing
    # And nothing anywhere in the event is called qualifying.
    assert not any("Qualif" in (r["name"] or "")
                   for r in rounds), [r["name"] for r in rounds]


def test_the_state_draw_never_skips_a_round(big):
    """‼️ 20 -> 16 -> 8 -> 4 -> 2 (owner, 2026-09: "don't skip the R16"). The opening
    round takes the field to sixteen and the draw plays every column after it in
    full — never a jump from qualifying straight to the quarterfinals."""
    import app.world as world
    rounds = world.jhsaa_state_rounds(big["state"])
    alive = [r["alive"] for r in rounds]
    assert alive[0] == len(big["state"]["field"])
    for i, r in enumerate(rounds[1:], 1):
        assert r["alive"] == alive[i - 1] - len(rounds[i - 1]["games"])
    assert rounds[-1]["alive"] == 2 and len(rounds[-1]["games"]) == 1
    # After the opening round the draw is a clean power of two — 16, then 8, 4, 2.
    after = [r["alive"] for r in rounds[1:]]
    assert after == [2 ** i for i in range(len(after), 0, -1)], after


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
    assert jvs.PHASE_LABELS[row["phase"]] == "JV STATE"
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
    assert len(field) == len(set(field))


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


def test_the_tree_labels_seeds_from_the_statewide_ranking(jv):
    """‼️ CONSTRUCTED, because the fixture need not contain the case.

    `_jh_bracket_cols` falls back to numbering a field 1..n by its ORDER, which is
    right for a draw whose field is its ranking and wrong the moment a lower-ranked
    champion wins the play-in: they take a slot above their rank, so the tree calls
    them #13 while the ranking, the qualifying panel and the round lists all call
    them #20 — the same team with two numbers on one page. The view passes the
    statewide map through the bracket's `seed_map`, and this pins that it is honoured.
    """
    from app.web.state import _jh_bracket_cols, _jh_schools
    schools = _jh_schools("boys")
    names = [e.name for e in jvs.entries(jv)][:4]
    assert len(names) == 4
    # A field whose order is NOT the ranking: the last-ranked team came through the
    # play-in and sits in the second slot.
    ranked = names[:1] + names[2:] + names[1:2]      # names[1] ranks last
    field = names
    seeds = {n: i + 1 for i, n in enumerate(ranked)}
    bracket = {"field": field, "seed_map": seeds, "champion": field[0],
               "rounds": [[{"home": field[0], "away": field[1], "home_points": 3.0,
                            "away_points": 2.0, "winner": field[0]},
                           {"home": field[2], "away": field[3], "home_points": 1.0,
                            "away_points": 3.0, "winner": field[3]}],
                          [{"home": field[0], "away": field[3], "home_points": 3.0,
                            "away_points": 0.0, "winner": field[0]}]]}
    seen = {}
    for col in _jh_bracket_cols(bracket, schools):
        for m in col["matchups"]:
            for side in ("home", "away"):
                t = m.get(side)
                if t and t.get("school"):
                    seen.setdefault(t["school"], t.get("seed"))
    assert seen[names[1]] == seeds[names[1]] == 4, "tree labelled a seed by slot"
    for n, sd in seeds.items():
        assert seen[n] == sd, n


def test_twenty_champions_pair_13v20_14v19_15v18_16v17():
    """‼️ STRICT SEED LINES, AND THE SPEC'S PAIRINGS ARE A RULE, NOT A SIDE EFFECT.

    The event first used `engine.tournament.seeded_draw`, which SHUFFLES within seed
    tiers — right for a classification's State draw (a TOSS seeding is an estimated
    ordering, so the tiers are the claim the evidence supports) and wrong for a
    championship of champions ranked on a season's record. Measured over four seeds it
    gave (12,20)(13,17)(15,18)(16,19), then (12,18)(13,20)(14,17)(15,19), then
    (9,17)(10,19)(11,20)(15,18) — a different opening round every year, with seed 9
    playing in while seed 15 was seeded through. The TOC's order fold is strict and is
    what makes the association's own pairings true.

    Pure arithmetic on the draw order — no season needed, so this cannot rot behind a
    fixture that crowns fewer than twenty regions.
    """
    order = [1]
    while len(order) < jvs.REGIONS:
        m = 2 * len(order)
        order = [s for a in order for s in (a, m + 1 - a)]
    pairs = [(order[i], order[i + 1]) for i in range(0, len(order), 2)]
    games = sorted(tuple(sorted(p)) for p in pairs
                   if p[0] <= jvs.REGIONS and p[1] <= jvs.REGIONS)
    assert games == [(13, 20), (14, 19), (15, 18), (16, 17)]
    through = sorted({s for p in pairs for s in p
                      if s <= jvs.REGIONS and not (p[0] <= jvs.REGIONS and p[1] <= jvs.REGIONS)})
    assert through == list(range(1, 13))


def test_an_archive_from_the_play_in_build_still_reads(jv, monkeypatch, tmp_path):
    """‼️ DERIVED ON READ, NEVER MIGRATED — the archive is the record of what was
    played, and the next shape change would need another migration nobody runs.

    The first build stored the qualifying duals in their own bracket under `play_in`
    and started `state` at the Round of 16. Read as if the current shape, that row's
    R16 becomes "the qualifying round": eight duals reported as four, their winners
    and losers labelled Qualified/Lost qualifier, and the play-in that was actually
    played vanishes off the page.
    """
    import json
    import app.world as world
    from app.web.state import DEFAULT_SEED, jhsaa_jv_state_view
    monkeypatch.setenv("TENNIS_DB_PATH", str(tmp_path / "legacy.db"))
    monkeypatch.setattr(world, "WORLD_DB", str(tmp_path / "legacy.db"), raising=False)
    names = [e.name for e in jvs.entries(jv)][:20]
    assert len(names) == 20
    direct, playin = names[:12], names[12:]
    quals = [{"home": playin[i], "away": playin[len(playin) - 1 - i],
              "home_points": 3.0, "away_points": 2.0, "winner": playin[i]}
             for i in range(len(playin) // 2)]
    winners = [g["winner"] for g in quals]
    draw = direct + winners
    r16 = [{"home": draw[i], "away": draw[i + 1], "home_points": 3.0,
            "away_points": 1.0, "winner": draw[i]} for i in range(0, 16, 2)]
    legacy = {
        "field": names, "qualifiers": names, "ranked": names,
        "regions": {f"Region {i}": {"champion": n, "field": [n], "rounds": [],
                                    "round_names": []}
                    for i, n in enumerate(names)},
        "region_champions": {f"Region {i}": n for i, n in enumerate(names)},
        "play_in": {"champion": None, "field": playin, "rounds": [quals],
                    "round_names": [jvs.LEGACY_QUALIFYING_NAME]},
        "state": {"champion": r16[0]["winner"], "field": draw, "rounds": [r16],
                  "round_names": []},
        "champion": r16[0]["winner"],
    }
    w = world.get_or_create(DEFAULT_SEED)
    conn = world._db()
    conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data)"
                 " VALUES (?,?,?,?)",
                 (w["id"], w["year"], "boys", json.dumps({"season_year": 2068})))
    conn.execute("INSERT INTO world_jhsaa_jv_state (world_id, year, gender, data)"
                 " VALUES (?,?,?,?)", (w["id"], w["year"], "boys", json.dumps(legacy)))
    conn.commit(); conn.close()

    v = jhsaa_jv_state_view(DEFAULT_SEED, "boys", None, w["year"])
    assert v["ready"]
    # The archived opening round is on the page, ahead of the draw's own rounds —
    # four duals, not the eight of the Round of 16.
    # ‼️ RELABELLED ON READ. The stored name describes a gate this event does not
    # have, so it is rendered as the round it was: twenty alive, Round of 20.
    assert v["rounds"][0]["name"] == f"Round of {len(names)}" == "Round of 20"
    assert len(v["rounds"][0]["games"]) == 4
    # Desktop renders the canvas rather than the round tabs. Its first column must
    # therefore contain the four played games plus all twelve opening-round byes,
    # and feed the archived Round of 16 as one complete tree.
    assert [c["name"] for c in v["canvas"]["columns"]] == ["Round of 20", "Octofinals"]
    assert [c["n"] for c in v["canvas"]["columns"]] == [16, 8]
    first_col = [c for c in v["canvas"]["cards"] if c["col"] == 0]
    assert sum(c["played"] for c in first_col) == 4
    # The regional table shows how far each champion went, not how they entered.
    finish = {r["champion"]: r["finish"] for r in v["regions"]}
    assert finish[r16[0]["winner"]] == "Champion"
    assert all(f for n, f in finish.items() if n in set(draw))
    losers = {g["away"] for g in quals}
    assert {finish[n] for n in losers} == {"Round of 20"}


def test_a_regional_dual_is_archived_under_its_own_phase(jv):
    """‼️ TWO PHASES, because a phase is the archive's identity for an event and a
    regional championship is a different round from the State draw — which is the only
    thing that lets a program's card say JV REGIONALS where varsity says Regionals.
    The rounds and the words for them are the association's existing ones (owner,
    2026-09: "since the labels already exist it's not different but labeling can be");
    only the wording says JV."""
    field = jvs.entries(jv)
    a, b = field[4], field[5]
    jvs.play_dual(a, b, seed=7, phase=jvs.PHASE_REGION)
    row = a.jv.schedule[-1]
    assert row["phase"] == jvs.PHASE_REGION and row["level"] == jh.LEVEL_JV
    assert jvs.PHASE_LABELS[row["phase"]] == "JV REGIONALS"
    assert jvs.PHASE_REGION != jvs.PHASE


def test_the_region_draws_are_played_under_the_regional_phase(arc, jv):
    """The event's own regional duals, not just a hand-called one."""
    phases = {d["phase"] for t in jv.values() for d in t.schedule}
    assert jvs.PHASE_REGION in phases and jvs.PHASE in phases


def test_the_regional_bracket_is_on_the_page_one_region_at_a_time(arc, monkeypatch,
                                                                  tmp_path):
    """‼️ THE REGIONAL BRACKETS RENDER (owner rule 2070). Every region's full draw
    has been archived since the event began (`run_regionals` → `ev["regions"]`), but
    no surface ever rendered one — which from the site is indistinguishable from the
    brackets not being preserved year over year. One region at a time through the
    section's sibling <select>; the champions table and the State tree are untouched.
    Asserted on the view INCLUDING the canvas result's own attributes, because
    `brk_canvas` dereferences a `_bracket_canvas` RESULT and Jinja renders a wrong
    type as an empty box rather than raising."""
    import json
    import app.world as world
    from app.web.state import DEFAULT_SEED, jhsaa_jv_state_view
    monkeypatch.setenv("TENNIS_DB_PATH", str(tmp_path / "regional.db"))
    monkeypatch.setattr(world, "WORLD_DB", str(tmp_path / "regional.db"),
                        raising=False)
    w = world.get_or_create(DEFAULT_SEED)
    conn = world._db()
    conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data)"
                 " VALUES (?,?,?,?)",
                 (w["id"], w["year"], "boys", json.dumps({"season_year": 2068})))
    conn.execute("INSERT INTO world_jhsaa_jv_state (world_id, year, gender, data)"
                 " VALUES (?,?,?,?)", (w["id"], w["year"], "boys",
                                       json.dumps(arc, default=str)))
    conn.commit(); conn.close()

    # ‼️ COMPARE AGAINST THE RELABELLED READ, NOT THE RAW DICT. The view reads the
    # archive through `world.jhsaa_jv_state` -> `_relabel` (the GLOBAL former-names
    # data, not per-save), so a school or place name in the raw `arc` need not be
    # the name the page shows — the first draft of this test compared raw against
    # relabelled and failed on exactly that.
    ev = world.jhsaa_jv_state(w["id"], w["year"], "boys")

    # default: the state champion's own region is on screen
    v = jhsaa_jv_state_view(DEFAULT_SEED, "boys", None, w["year"])
    assert v["ready"] and v["region_brk"]
    assert v["region_brk"]["name"] == v["champion_region"]
    assert v["region_brk"]["options"] == sorted(ev["regions"])
    assert v["region_brk"]["champion"] == ev["regions"][v["champion_region"]]["champion"]

    # switching shows THAT region's draw, at its own size, with its own champion
    other = next(r for r in sorted(ev["regions"]) if r != v["champion_region"])
    v2 = jhsaa_jv_state_view(DEFAULT_SEED, "boys", None, w["year"], other)
    br = ev["regions"][other]
    rb = v2["region_brk"]
    assert rb["name"] == other and rb["champion"] == br["champion"]
    assert rb["field_n"] == len(br["field"])
    # the canvas is a real `_bracket_canvas` result: columns/cards are what
    # `brk_canvas` dereferences (a card's home/away are DECO objects, so the
    # name check reads the round tabs, whose games carry plain name strings)
    assert rb["canvas"]["columns"] and rb["canvas"]["cards"]
    assert any(br["champion"] in (gm.get("home"), gm.get("away"))
               for rd in rb["rounds"] for gm in rd["games"])
    assert rb["rounds"][-1]["games"], "the regional final is on the tabs"
    # a nonsense region falls back rather than 500ing
    v3 = jhsaa_jv_state_view(DEFAULT_SEED, "boys", None, w["year"], "Nowhere")
    assert v3["region_brk"]["name"] == v["champion_region"]
