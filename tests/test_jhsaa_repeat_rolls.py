"""The two CAREER honour rolls on the History sub-rail (owner request, 2026-08).

Every other JHSAA surface is scoped to one season, so a multi-year run is invisible:
a name in 2028 and the same name in 2030 with nothing joining them. These folds are
the only thing that can see a career, which is why they need coverage a single played
season cannot give — the fixture archives SEVERAL small seasons by hand, because a
repeat by definition needs more than one.
"""
import json

import pytest

from app import world as wd
from app.web import state as st


def poy_row(pid, name, school, kind="singles", pids=None, names=None):
    """An awards `poy` row as `jhsaa_awards._row` writes it — `pids`/`names` carry
    the pairing, and a DOUBLES POY honours two athletes."""
    return {"pid": pid, "pids": list(pids or [pid]), "name": name,
            "names": list(names or [name]), "school": school, "kind": kind,
            "grade": 12, "grades": [12], "district": "Basalt League", "region": "Kangas"}


def draw(champ_players, school, champion=0):
    """A `draw_to_dict` blob, cut down to what the fold reads: entries plus the
    champion INDEX into them (never a copy of the entrant — the archive's own rule)."""
    return json.dumps({
        "entries": [{"school": "Somebody Else", "players": [{"pid": "z" * 16,
                                                             "name": "Nobody",
                                                             "grade": 10}]},
                    {"school": school, "players": champ_players}],
        "champion": champion, "runner_up": 0, "rounds": [], "finishes": {}})


@pytest.fixture(scope="module")
def archive():
    """Four archived girls' seasons, written straight into the world tables.

    Deliberately hand-built rather than simulated: the folds read only `awards.poy`
    and the individual draws, a real season takes minutes a gender, and one season
    cannot contain a repeat at all."""
    w = wd.get_or_create(wd.DEFAULT_SEED)
    conn = wd._db()
    try:
        conn.execute("DELETE FROM world_jhsaa WHERE world_id=?", (w["id"],))
        conn.execute("DELETE FROM world_jhsaa_individual WHERE world_id=?", (w["id"],))
        seasons = {
            0: {"9A": poy_row("aaaa", "Ada Kane", "Coles Creek"),
                "2A": poy_row("ffff", "Fay Ng", "Harrow")},
            1: {"9A": poy_row("aaaa", "Ada Kane", "Coles Creek"),
                # a DOUBLES POY — one selection, TWO athletes
                "2A": poy_row("cccc", "Cy Odom", "Sixes", kind="doubles",
                              pids=["cccc", "bbbb"], names=["Cy Odom", "Bo Reyes"])},
            2: {"6A": poy_row("aaaa", "Ada Kane", "Mater Dei"),
                "2A": poy_row("dddd", "Dee Fox", "Sixes")},
            3: {"1A": poy_row("bbbb", "Bo Reyes", "Sixes")},
        }
        for year, awards in seasons.items():
            conn.execute(
                "INSERT INTO world_jhsaa (world_id, year, gender, data) VALUES (?,?,?,?)",
                (w["id"], year, "girls",
                 json.dumps({"season_year": 2030 + year, "standings": {}, "champions": {},
                             "awards": {g: {"poy": p} for g, p in awards.items()}})))
        # Individual titles: Ada wins No. 1 singles twice, Bo wins No. 2 doubles twice
        # with DIFFERENT partners, and Cy wins one. Mixed is archived under 'mixed'.
        ada = [{"pid": "aaaa", "name": "Ada Kane", "grade": 11}]
        titles = [
            (0, "9A", "S1", draw(ada, "Coles Creek", 1)),
            (2, "6A", "S1", draw(ada, "Mater Dei", 1)),
            (0, "2A", "D2", draw([{"pid": "bbbb", "name": "Bo Reyes", "grade": 10},
                                  {"pid": "cccc", "name": "Cy Odom", "grade": 12}],
                                 "Sixes", 1)),
            (1, "2A", "D2", draw([{"pid": "bbbb", "name": "Bo Reyes", "grade": 11},
                                  {"pid": "dddd", "name": "Dee Fox", "grade": 9}],
                                 "Sixes", 1)),
        ]
        conn.executemany(
            "INSERT INTO world_jhsaa_individual (world_id, year, gender, grp, flight,"
            " data) VALUES (?,?,?,?,?,?)",
            [(w["id"], y, "girls", g, f, d) for y, g, f, d in titles])
        # MIXED DOUBLES — archived under gender 'mixed', and its entry is always
        # [boy, girl] (`jhsaa_individuals.mixed_entry` is the only builder). Ada is
        # the GIRL, so she is the second player; the boy must never reach this page.
        conn.execute(
            "INSERT INTO world_jhsaa_individual (world_id, year, gender, grp, flight,"
            " data) VALUES (?,?,?,?,?,?)",
            (w["id"], 2, "mixed", "9A", "XD",
             draw([{"pid": "eeee", "name": "Eli Ward", "grade": 12}] + ada,
                  "Coles Creek", 1)))
        conn.commit()
    finally:
        conn.close()
    return w


# --- Repeat Players of the Year ---------------------------------------------------

def test_only_repeats_are_listed_and_the_deepest_run_leads(archive):
    rows = wd.jhsaa_poy_repeats(archive["id"], "girls")
    assert [(r["name"], r["count"]) for r in rows] == [("Ada Kane", 3), ("Bo Reyes", 2)]
    # Dee Fox and Cy Odom won once each and are not a repeat.
    assert all(r["name"] not in ("Dee Fox",) for r in rows)


def test_a_doubles_poy_credits_both_athletes(archive):
    """‼️ Through `row_pids`. A doubles POY is ONE selection describing TWO people;
    matching on `row["pid"]` credits half of them and looks perfectly fine on the
    page it is on."""
    rows = {r["pid"]: r for r in wd.jhsaa_poy_repeats(archive["id"], "girls")}
    assert rows["bbbb"]["count"] == 2, "the doubles POY did not reach the partner"
    years = [a["year"] for a in rows["bbbb"]["awards"]]
    assert years == [1, 3]


def test_the_class_rides_on_each_award_not_on_the_player(archive):
    """A 2A run and a 9A run are different achievements, so the page shows the class
    per award and does not decide between them."""
    row = next(r for r in wd.jhsaa_poy_repeats(archive["id"], "girls")
               if r["pid"] == "aaaa")
    assert [a["group"] for a in row["awards"]] == ["9A", "9A", "6A"]
    assert row["groups"] == ["9A", "6A"]


def test_a_career_that_moved_school_reads_as_two_stints(archive):
    """The owner's own row shape: one clause per school, in career order."""
    view = st.jhsaa_repeat_poy(wd.DEFAULT_SEED, "girls")
    row = next(r for r in view["rows"] if r["pid"] == "aaaa")
    assert [(st_["school"], [a["season_year"] for a in st_["won"]])
            for st_ in row["stints"]] == [("Coles Creek", [2030, 2031]),
                                          ("Mater Dei", [2032])]


def test_the_rolls_are_banded_by_count(archive):
    """"3-time Players of the Year", then 2-time — a heading, not a column of
    numbers to compare down (owner layout, 2026-08)."""
    view = st.jhsaa_repeat_poy(wd.DEFAULT_SEED, "girls")
    # ‼️ THE BANDS ARE FIXED DOWN TO 4 AND EMPTY ONES ARE KEPT (owner): nobody here
    # has four, and the section is still on the page saying so.
    assert [b["heading"] for b in view["bands"]] == [
        "4-time Players of the Year", "3-time Players of the Year",
        "2-time Players of the Year"]
    assert view["bands"][0]["rows"] == []
    ch = st.jhsaa_repeat_individual_champions(wd.DEFAULT_SEED, "girls")
    assert [b["count"] for b in ch["bands"]] == [4, 3, 2]
    assert [b["heading"] for b in ch["bands"]][-1] == "2-time Individual State Champions"
    # and never a 1-time band: a single title is not a repeat, which is the page.
    assert all(b["count"] >= 2 for b in ch["bands"])
    assert sum(len(b["rows"]) for b in ch["bands"]) == len(ch["rows"])


def test_league_and_district_poy_are_never_counted(archive):
    """Explicitly out of scope: the association crowns one per league per class per
    year, so aggregating it is a longer list of more people, not a harder thing."""
    conn = wd._db()
    try:
        r = conn.execute("SELECT data FROM world_jhsaa WHERE world_id=? AND year=0"
                         " AND gender='girls'", (archive["id"],)).fetchone()
        arc = json.loads(r["data"])
        arc["awards"]["9A"]["district_poy"] = {
            "Basalt League": poy_row("dddd", "Dee Fox", "Sixes")}
        conn.execute("UPDATE world_jhsaa SET data=? WHERE world_id=? AND year=0"
                     " AND gender='girls'", (json.dumps(arc), archive["id"]))
        conn.commit()
    finally:
        conn.close()
    assert all(r["pid"] != "dddd"
               for r in wd.jhsaa_poy_repeats(archive["id"], "girls"))


# --- Repeat individual state champions --------------------------------------------

def test_a_doubles_title_belongs_to_the_person_not_the_pairing(archive):
    """Bo won No. 2 doubles twice with DIFFERENT partners. Keyed on the pair that is
    two one-title pairings and Bo appears nowhere; keyed on the person it is a repeat,
    which is what a career is."""
    rows = {r["pid"]: r for r in
            wd.jhsaa_individual_title_repeats(archive["id"], "girls")}
    assert rows["bbbb"]["count"] == 2
    assert [t["partner"] for t in rows["bbbb"]["titles"]] == ["Cy Odom", "Dee Fox"]
    assert "cccc" not in rows, "one title with each of two partners is not a repeat"


def test_a_mixed_doubles_title_counts(archive):
    """‼️ IT COUNTS (owner correction, 2026-08: "if a kid wins a mixed doubles title
    it counts"). A first pass read across from the rule that mixed credits no AWARD
    and excluded it — but that rule is about résumés, TOSS and the recruit hand-off.
    This roll is a record of state titles a person has won, and this is one."""
    row = next(r for r in wd.jhsaa_individual_title_repeats(archive["id"], "girls")
               if r["pid"] == "aaaa")
    assert row["count"] == 3
    # Ordered by year, then by how hard the flight is to win (`JH_FLIGHT_RANK`).
    assert [(t["year"], t["flight"]) for t in row["titles"]] == [
        (0, "S1"), (2, "S1"), (2, "XD")]


def test_only_this_gender_half_of_a_mixed_pair_is_credited(archive):
    """A mixed pair is one player from each field, so the boy in it must never
    appear on the girls' roll — the entry is [boy, girl] by construction, so the
    side is an index rather than a guess."""
    girls = {r["pid"] for r in wd.jhsaa_individual_title_repeats(archive["id"], "girls")}
    assert "eeee" not in girls
    # and the boy's own page sees his half (one title — not a repeat, so not listed,
    # but the fold must have credited him rather than her).
    boys = wd.jhsaa_individual_title_repeats(archive["id"], "boys", minimum=1)
    assert [(r["pid"], r["count"]) for r in boys] == [("eeee", 1)]


def test_each_title_carries_its_flight_class_and_school(archive):
    row = next(r for r in wd.jhsaa_individual_title_repeats(archive["id"], "girls")
               if r["pid"] == "aaaa")
    assert [(t["year"], t["flight"], t["group"], t["school"]) for t in row["titles"]] \
        == [(0, "S1", "9A", "Coles Creek"), (2, "S1", "6A", "Mater Dei"),
            (2, "XD", "9A", "Coles Creek")]


def test_the_flight_rank_comes_from_the_associations_own_weights():
    """‼️ S1, D1, S2, D2, S3, D3, XD (owner, 2026-08) — DERIVED from
    `jhsaa.FLIGHT_WEIGHTS`, which already prices every flight for TOSS and for the
    award résumés, never typed. A first pass built it off
    `jhsaa_individuals.FLIGHTS` (S1-S3 then D1-D3 — how a DRAW SHEET reads) and got
    a ranking the association does not use, with No. 1 doubles below No. 3 singles.

    D1 sits level with S1 because a state dual is 1S/4D and the anti-stacking rule
    makes S1+D1 consume ranks #1-#3: measured over 40 5A girls programs, S1 is
    staffed at mean ability rank 1.2 and D1 at 2.4, and most classes have no No. 2
    singles seat at all."""
    from app import jhsaa as jh, jhsaa_individuals as ji
    assert wd._jh_flight_rank() == ("S1", "D1", "S2", "D2", "S3", "D3", "XD")
    # A flight nobody ranked would drop out of every row silently — the roll would
    # look complete and be missing titles.
    assert set(wd._jh_flight_rank()) == set(ji.FLIGHTS) | {"XD"}
    # and the order IS the weights, so the two cannot drift apart
    ranked = [f for f in wd._jh_flight_rank() if f != "XD"]
    assert [jh.FLIGHT_WEIGHTS[f] for f in ranked] == sorted(
        (jh.FLIGHT_WEIGHTS[f] for f in ranked), reverse=True)


def test_ties_break_on_flight_quality(archive):
    """Two No. 1 singles titles outrank two No. 2 doubles titles at the same count —
    the ordering is the only judgement the page makes."""
    rows = wd.jhsaa_individual_title_repeats(archive["id"], "girls")
    assert [r["pid"] for r in rows] == ["aaaa", "bbbb"]
    assert all("_quality" not in r for r in rows), "the sort key leaked into the view"


def test_the_pages_render_the_rolls(archive):
    """‼️ Through the ROUTES, and with `prime` stubbed. A cold request to a world that
    exists answers with the WARMING SHELL, which carries no rows at all — the stub
    `test_jhsaa_routes.warm_client` uses, for the same reason: no JHSAA surface reads
    a college program, so reporting warm here is honest."""
    import os
    os.environ.setdefault("PTC_NO_BOOT_WARM", "1")
    from app.web.server import create_app
    real_primed, real_prime = wd.is_primed, wd.prime
    wd.is_primed = lambda *a, **k: True
    wd.prime = lambda *a, **k: None
    try:
        c = create_app().test_client()
        _render_rolls(c)
    finally:
        wd.is_primed, wd.prime = real_primed, real_prime


def _render_rolls(c):
    poy = c.get("/jhsaa/repeat-poy?g=girls").get_data(as_text=True)
    assert "3-time Players of the Year" in poy
    assert "Ada Kane" in poy and "Coles Creek" in poy and "Mater Dei" in poy
    champs = c.get("/jhsaa/repeat-champions?g=girls").get_data(as_text=True)
    assert "Bo Reyes" in champs and "Cy Odom" in champs      # partner shown as context
    assert "Dee Fox" in champs                               # the other partner
    # ‼️ ONE DENSE TABLE, not a roll of cards (owner, 2026-09: the card layout "is
    # too bloated now that we've run a lot of these and it covers the whole
    # state"). The bands survive as separator rows inside that one table.
    for html in (poy, champs):
        assert html.count('<table class="bl-table jh-repeat">') == 1
        assert 'class="jh-roll"' not in html
        assert '<tr class="band">' in html


def test_a_player_who_left_and_came_back_is_two_stints():
    """Consecutive awards at one school are ONE clause; a return after a spell
    elsewhere starts a new one, because it was not one long stay."""
    stints = st._jh_career_stints([
        {"year": 0, "season_year": 2030, "school": "Sixes"},
        {"year": 1, "season_year": 2031, "school": "Harrow"},
        {"year": 2, "season_year": 2032, "school": "Sixes"},
    ], {})
    assert [s_["school"] for s_ in stints] == ["Sixes", "Harrow", "Sixes"]


# --- the PROGRAM's individual state champions -------------------------------------

def test_a_mixed_title_credits_both_programs(archive):
    """‼️ A MIXED TITLE IS THE SCHOOL'S (owner correction, 2026-08): "it should be
    crediting both the boys and girls program with the honor when it's won, just like
    the other doubles and singles brackets." It was excluded on the grounds that a
    mixed pair is one player from each of the school's two SEPARATE teams and a page
    scoped to one gender had no flight box to hang it on — which answered a layout
    question by dropping a title the school won.

    The program-level counterpart of the CAREER rule, and deliberately the opposite
    of it: a career belongs to a person and a person has one gender, so the rolls
    credit only the winner's own; a PROGRAM has both teams."""
    seasons = [{"year": 2, "season_year": 2032, "group": "9A"}]
    for gender in ("girls", "boys"):
        rows = wd.jhsaa_school_individual_champions(
            archive["id"], gender, "Coles Creek", seasons)
        mixed = [r for r in rows if r["flight"] == "XD"]
        assert len(mixed) == 1, f"{gender} program lost its mixed title"
        assert mixed[0]["mixed"] is True
        # the ROW names both players — the pair is what won it
        assert [p["name"] for p in mixed[0]["players"]] == ["Eli Ward", "Ada Kane"]


def test_a_program_still_gets_its_own_flighted_titles(archive):
    """The mixed lookup is an addition, not a replacement — the girls' own No. 1
    singles title that season must still be there, and the boys (who won nothing
    flighted here) must not inherit it."""
    seasons = [{"year": 2, "season_year": 2032, "group": "6A"}]
    girls = wd.jhsaa_school_individual_champions(
        archive["id"], "girls", "Mater Dei", seasons)
    assert [r["flight"] for r in girls] == ["S1"]
    boys = wd.jhsaa_school_individual_champions(
        archive["id"], "boys", "Mater Dei", seasons)
    assert boys == []
