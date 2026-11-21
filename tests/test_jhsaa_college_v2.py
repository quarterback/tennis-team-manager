"""The alumni tracker's career model 2 (owner spec 2026-11, `app/jhsaa_college_v2.py`).

Model 1 produced one kind of career: every tracked senior played four seasons at
one college and climbed the lineup. Model 2 keeps the architecture — deterministic,
generated once, persisted whole, no college season simulated — and produces a
career as a sequence of states. What has to hold:

  - the same inputs give the same careers, and stored careers are never rewritten;
  - how many seniors play in college, and where, follows the class;
  - every college is a real program a player could actually attend;
  - a career's totals are its seasons, a transfer history is its seasons, and a
    player who stopped has no seasons after stopping;
  - two alumni at one college in one season never hold the same singles position;
  - a class with nothing but an exit rating on record still gets careers.

The measured DISTRIBUTION is `scripts/jhsaa_college_validate.py`'s job, not this
file's: these pin behaviour, not rates.
"""
import json
import random
from types import SimpleNamespace

import pytest

from app import jhsaa as jh
from app import jhsaa_college as jcol
from app import jhsaa_college_v2 as v2
from app import ncaa
from app import recruit_economy
from app import world as wd


def _class(seed, n=1500, shift=0.0, foreign_every=7):
    r = random.Random(seed)
    out = []
    for i in range(n):
        ovr = r.gauss(55 + shift, 10)
        out.append({"pid": f"k{seed}-{i}", "name": f"Player {seed}-{i}",
                    "hs": "Some High", "hs_ident": "some-high", "ovr": ovr,
                    "ceiling": ovr + abs(r.gauss(7, 4)), "pot": ovr + abs(r.gauss(6, 4)),
                    "academic": max(59, min(99, round(r.gauss(79, 8)))),
                    "domestic": i % foreign_every != 0,
                    "style": r.choice(["balanced", "serve_and_volley", "counterpuncher"])})
    return out


def _ref(seeds=(91, 92, 93)):
    return sorted(x for s in seeds for x in
                  sorted((k["ovr"] for k in _class(s)), reverse=True)[:v2.TARGET_BOUND])


@pytest.fixture(scope="module")
def built():
    """Three consecutive classes, each walking into teams the earlier ones are on."""
    ref, stored, classes = _ref(), {}, []
    for i, (seed, shift) in enumerate(((11, 0.0), (12, 0.0), (13, 0.0))):
        rows = v2.build_class(_class(seed, shift=shift), "girls", 2100 + i,
                              "v2-test", ref=ref, stored=stored)
        for r in rows:
            for s in r["seasons"]:
                stored.setdefault((s["college"], s["year"]), []).append(
                    {"pid": r["pid"], "slv": s["slv"], "dlv": s["dlv"],
                     "s_pos": s["s_pos"], "d_pair": s["d_pair"]})
        classes.append(rows)
    return {"classes": classes, "rows": [r for c in classes for r in c],
            "ctx": v2.Context("girls", "v2-test"), "ref": ref}


def test_it_is_the_same_every_time_and_varies_by_save():
    ref = _ref()
    a = v2.build_class(_class(21), "boys", 2100, "salt-a", ref=ref)
    assert a == v2.build_class(_class(21), "boys", 2100, "salt-a", ref=ref)
    b = v2.build_class(_class(21), "boys", 2100, "salt-b", ref=ref)
    assert [r["college"] for r in a] != [r["college"] for r in b]


def test_how_many_play_and_where_follows_the_class():
    """No quota: a deeper class sends more seniors on and more of them to D1; a
    thinner one fewer. (Model 1 sent exactly 200, in the same division shares,
    whatever the class.)"""
    ref = _ref()
    weak = v2.build_class(_class(31, shift=-2.0), "girls", 2100, "s", ref=ref)
    strong = v2.build_class(_class(31, shift=+2.0), "girls", 2100, "s", ref=ref)
    assert len(strong) > len(weak) + 20
    d1 = lambda rows: sum(r["division"] == "D1" for r in rows)      # noqa: E731
    assert d1(strong) > d1(weak)
    assert {r["division"] for r in strong} == set(v2.DIVISIONS)


def test_careers_are_not_all_one_career(built):
    """The point of the model. Each of these was 0% or 100% under model 1."""
    rows = built["rows"]
    n = len(rows)
    assert 0.05 < sum(r["peak"] is None for r in rows) / n < 0.45        # never started
    assert 0.03 < sum(bool(r["transfers"]) for r in rows) / n < 0.35     # moved
    assert 0.55 < sum(r["years"] == 4 for r in rows) / n < 0.95          # played it out
    assert sum(r["status"] == "left_team" for r in rows) > 0
    freshmen = [r["seasons"][0] for r in rows]
    assert 0.15 < sum(bool(s["s_pos"]) for s in freshmen) / n < 0.85
    # Lineups move both ways.
    moves = [[s["s_pos"] for s in r["seasons"] if s["s_pos"]] for r in rows]
    assert any(len(m) >= 2 and m[-1] > m[0] for m in moves)              # slid down
    assert any(len(m) >= 2 and m[-1] < m[0] for m in moves)              # climbed
    # Several kinds of career turn up, and no single kind is most of them.
    arcs = {r["arc"] for r in rows}
    assert len(arcs) >= 6
    assert max(sum(r["arc"] == a for r in rows) for a in arcs) / n < 0.6
    # Singles and doubles are separate careers.
    assert any(r["d_peak"] and (r["peak"] is None or r["d_peak"] < r["peak"])
               for r in rows)


def test_every_college_is_real_and_one_they_could_attend(built):
    ctx = built["ctx"]
    snaps = {s["pid"]: s for seed in (11, 12, 13) for s in _class(seed)}
    for r in built["rows"]:
        snap = snaps[r["pid"]]
        for c in r["colleges"]:
            prog = ctx.programs[c["college"]]                   # a real program
            assert prog.division == c["division"]
            # The one authority on the service academies.
            assert not (ncaa.us_only_program(prog.school) and not snap["domestic"])
            # D4 admits on academics — the division's design.
            if prog.division == "D4":
                assert snap["academic"] >= recruit_economy.d4_academic_min(
                    prog, 0, "v2-test")


def test_a_career_is_exactly_its_seasons(built):
    for r in built["rows"]:
        ss = r["seasons"]
        assert 1 <= len(ss) <= 4 and r["years"] == len(ss)
        assert [s["class"] for s in ss] == ["Fr", "So", "Jr", "Sr"][:len(ss)]
        assert [s["year"] for s in ss] == [r["grad_year"] + 1 + i for i in range(len(ss))]
        for k in ("s_w", "s_l", "d_w", "d_l"):
            assert r[k] == sum(s[k] for s in ss)
        played = [s["s_pos"] for s in ss if s["s_pos"]]
        assert r["s_peak"] == (min(played) if played else None)
        # Whoever stopped has nothing after stopping; whoever finished, finished.
        assert (r["status"] == "graduated") == (len(ss) == 4)
        for s in ss:
            n_s = ncaa.lineup_size(s["division"])
            assert s["s_pos"] is None or 1 <= s["s_pos"] <= n_s
            assert s["d_pair"] is None or 1 <= s["d_pair"] <= \
                ncaa.dual_format(s["division"]).n_doubles
            if s["injury"] == "out":
                assert s["s_w"] + s["s_l"] + s["d_w"] + s["d_l"] == 0
            # All-Conference comes first, at every level (owner rule 2026-11): an
            # All-American season is always an All-Conference season in the same
            # discipline.
            assert "All-American" not in s["honors"] or "All-Conference" in s["honors"]
            assert "All-American (doubles)" not in s["honors"] \
                or "All-Conference (doubles)" in s["honors"]
        # A career that ended early says how, and a transfer is never one of them.
        assert (r["departure"] is None) == (r["status"] == "graduated")
        if r["departure"]:
            assert r["departure"]["kind"] == r["status"] == r["arc"]
            assert r["departure"]["kind"] in ("left_team", "left_college",
                                              "injury_ended", "turned_pro")
            assert r["departure"]["year"] == ss[-1]["year"]
        # Model 1's keys still read, so a page built for it shows a model-2 career.
        assert (r["peak"], r["w"], r["l"]) == (r["s_peak"], r["s_w"], r["s_l"])
        assert all((s["pos"], s["w"], s["l"]) == (s["s_pos"], s["s_w"], s["s_l"])
                   for s in ss)


def test_a_transfer_history_is_the_seasons_it_describes(built):
    moved = [r for r in built["rows"] if r["transfers"]]
    assert moved
    for r in moved:
        ss = r["seasons"]
        assert [c["college"] for c in r["colleges"]] == \
            [ss[0]["college"]] + [t["to"] for t in r["transfers"]]
        for t in r["transfers"]:
            before = next(s for s in ss if s["year"] == t["year"])
            after = next(s for s in ss if s["year"] == t["year"] + 1)
            assert (before["college"], after["college"]) == (t["from"], t["to"])
            assert (before["role"], after["role"]) == (t["role_before"], t["role_after"])
            assert t["from"] != t["to"]
        # Each stint covers its seasons and nothing else.
        for c in r["colleges"]:
            years = [s["year"] for s in ss if s["college"] == c["college"]]
            assert years and (c["from"], c["to"]) == (min(years), max(years))
    # A bench player who moves, moves to somewhere they play.
    opp = [t for r in moved for t in r["transfers"] if t["reason"] == "opportunity"]
    assert opp and sum(t["role_after"] in ("starter", "doubles") for t in opp) \
        > 0.6 * len(opp)


def test_no_singles_position_is_held_twice(built):
    """Alumni at one college in one season share a team — classmates, and classes
    apart. The record of a career already written is never contradicted."""
    seen = set()
    for r in built["rows"]:
        for s in r["seasons"]:
            if s["s_pos"]:
                key = (s["college"], s["year"], s["s_pos"])
                assert key not in seen, key
                seen.add(key)
    shared = {}
    for r in built["rows"]:
        for s in r["seasons"]:
            shared.setdefault((s["college"], s["year"]), set()).add(r["pid"])
    assert any(len(v) > 1 for v in shared.values()), "no shared team to test"


def test_a_depth_chart_is_the_same_team_whoever_asks(built):
    """A program-season's roster does not depend on which alumnus is on it, and a
    teammate is the same player a year later — one class older."""
    ctx = built["ctx"]
    prog = ctx.by_div["D2"][40]
    a = v2.Context("girls", "v2-test").seats(prog, 2103)
    assert a == ctx.seats(prog, 2103)
    assert len(a) == ncaa.roster_cap("D2")
    nxt = {(x["cohort"], x["j"]) for x in ctx.seats(prog, 2104)}
    stay = [x for x in a if x["cohort"] > 2103 - 3]              # not this year's seniors
    assert stay and all((x["cohort"], x["j"]) in nxt for x in stay)


def test_a_class_with_only_an_exit_rating_still_gets_careers():
    """The reduced path — an older class, known only through the alumni index."""
    thin = [{"pid": s["pid"], "name": s["name"], "hs": s["hs"], "ovr": s["ovr"]}
            for s in _class(41)]
    rows = v2.build_class(thin, "boys", 2090, "s", ref=_ref())
    assert len(rows) > 100 and all(r["reduced"] for r in rows)
    assert rows == v2.build_class([dict(s) for s in thin], "boys", 2090, "s", ref=_ref())
    # Nationality is unknown, so the service academies are simply out of view.
    assert not any(ncaa.us_only_program(c["college"])
                   for r in rows for c in r["colleges"])


def test_a_strong_player_can_lead_a_smaller_program(built):
    """Not everybody takes the best offer: some choose a level where they lead,
    and it shows in what they do there."""
    ctx = built["ctx"]
    stars = [r for r in built["rows"]
             if r["level"]["talent"] - ctx.level[r["college"]] >= 2.0
             and r["division"] != "D1" and r["years"] == 4]
    assert stars
    assert sum(r["s_peak"] is not None and r["s_peak"] <= 3 for r in stars) \
        > 0.6 * len(stars)
    # …and a player over their head mostly waits.
    buried = [r for r in built["rows"]
              if ctx.level[r["college"]] - r["level"]["talent"] >= 2.0]
    assert buried
    first = [r["seasons"][0] for r in buried]
    assert sum(not s["s_pos"] for s in first) > 0.5 * len(first)


# --- the store ------------------------------------------------------------------

@pytest.fixture
def lab_world():
    wd.reset(wd.DEFAULT_SEED)
    w = wd.get_or_create_jhsaa_only(wd.DEFAULT_SEED, salt="v2-store")
    yield w
    wd.reset(wd.DEFAULT_SEED)


def test_the_snapshot_reads_the_season_off_the_match_log():
    """Singles and doubles are split, the flight is the one played most, and the
    postseason is counted — all from the log the rung already holds."""
    school = jh.load_schools("girls")[0]
    p = next(x for x in jh.build_roster(school, 2100, "snap") if x.grade == 12)
    log = ([("S2", True, "regular", [], None, "A")] * 9
           + [("S2", False, "regular", [], None, "B")] * 3
           + [("S1", True, "regular", [], None, "C")] * 2
           + [("D1", True, "regular", [], "q", "C")] * 6
           + [("D1", False, "state", [], "q", "D")] * 4)
    team = SimpleNamespace(school=school, roster=[p], matches={p.pid: log})
    s = jcol.snapshot_of(p, team)
    assert (s["s_w"], s["s_l"], s["d_w"], s["d_l"]) == (11, 3, 6, 4)
    assert (s["s_flight"], s["d_flight"]) == ("S2", "D1")
    assert (s["matches"], s["post_matches"]) == (24, 4)
    assert s["hs_ident"] == school.ident and s["pid"] == p.pid
    assert s["ceiling"] >= s["ovr"] and s["academic"] and s["net_edge"] is not None
    json.dumps(s)                                                # it has to store
    # No season played → no record, and the model is told so (None, never 0-0).
    bare = jcol.snapshot_of(p, SimpleNamespace(school=school, roster=[p]))
    assert bare["s_w"] is None and bare["matches"] == 0


def test_careers_already_written_are_never_touched(lab_world, monkeypatch):
    """Switching the active model changes classes that have NO rows — nothing
    else. A model-1 class stays model 1, byte for byte, and the snapshot of a
    class is captured whichever model wrote it."""
    w = lab_world
    schools = jh.load_schools("girls")
    league = [s for s in schools if (s.group, s.district) ==
              (schools[0].group, schools[0].district)]
    teams = jh.district_teams(league, 2100, "v2-store")
    conn = wd._db()
    try:
        assert jcol.ACTIVE_MODEL == 1                           # the shipped default
        n = jcol.record_class(conn, w["id"], "girls", 2100, "v2-store", teams)
        conn.commit()
        seniors = sum(p.grade == 12 for t in teams for p in t.roster)
        assert n == min(jcol.CLASS_SIZE, seniors) > 0
        before = conn.execute("SELECT pid, ver, data FROM world_jhsaa_college"
                              " ORDER BY pid").fetchall()
        assert {r[1] for r in before} == {1}
        snaps = conn.execute("SELECT COUNT(*) FROM world_jhsaa_grad_snapshot"
                             " WHERE grad_year=2100").fetchone()[0]
        assert snaps == min(v2.CANDIDATES, seniors)

        monkeypatch.setattr(jcol, "ACTIVE_MODEL", 2)
        # The same class again, and a read of it: nothing moves.
        jcol.record_class(conn, w["id"], "girls", 2100, "v2-store", teams)
        jcol.class_rows(conn, w["id"], "girls", 2100, "v2-store")
        conn.commit()
        after = conn.execute("SELECT pid, ver, data FROM world_jhsaa_college"
                             " WHERE grad_year=2100 ORDER BY pid").fetchall()
        assert [tuple(r) for r in after] == [tuple(r) for r in before]

        # The NEXT class is written with model 2, from its snapshot.
        teams2 = jh.district_teams(league, 2101, "v2-store")
        m = jcol.record_class(conn, w["id"], "girls", 2101, "v2-store", teams2)
        conn.commit()
        rows = jcol.class_rows(conn, w["id"], "girls", 2101, "v2-store")
        assert m == len(rows) > 0 and {r["model"] for r in rows} == {2}
        assert not any(r["reduced"] for r in rows)
        by_pid = {p.pid: (p, t) for t in teams2 for p in t.roster}
        for r in rows:
            p, t = by_pid[r["pid"]]
            assert (r["name"], r["hs"], r["hs_ident"]) == \
                (p.name, t.school.name, t.school.ident)
        vers = dict(conn.execute("SELECT grad_year, MAX(ver) FROM world_jhsaa_college"
                                 " GROUP BY grad_year").fetchall())
        assert vers == {2100: 1, 2101: 2}
    finally:
        conn.close()


def test_the_page_built_for_model_1_reads_a_model_2_class(lab_world, monkeypatch):
    """The interface has not been changed yet, so a model-2 career has to render
    through the page as it stands."""
    from flask import render_template
    from app.web import state as st
    from app.web.server import create_app
    w = lab_world
    monkeypatch.setattr(jcol, "ACTIVE_MODEL", 2)
    app = create_app()
    grad_year = wd.BASE_YEAR + w["year"] + 1
    schools = jh.load_schools("girls")
    league = [s for s in schools if (s.group, s.district) ==
              (schools[0].group, schools[0].district)]
    conn = wd._db()
    try:
        jcol.record_class(conn, w["id"], "girls", grad_year, "v2-store",
                          jh.district_teams(league, grad_year, "v2-store"))
        conn.commit()
    finally:
        conn.close()
    view = st.jhsaa_alumni_view(wd.DEFAULT_SEED, "girls")
    assert view["rows"] and {r["model"] for r in view["rows"]} == {2}
    with app.test_request_context("/jhsaa/alumni?g=girls"):
        html = render_template("jhsaa_alumni.html", active="High School", view=view,
                               gender="women", u="D1-women", uni_label="")
    for r in view["rows"]:
        assert r["name"] in html and r["college"] in html
        assert f'{r["w"]}-{r["l"]}' in html
