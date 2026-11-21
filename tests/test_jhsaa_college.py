"""The Jefferson alumni tracker (owner rule 2026-11, `app/jhsaa_college.py`).

The JHSAA sim is separate from the college game, so a lab save has no college world
to send its seniors into; simulating one was measured (10 minutes a year with only
D1 active) and rejected. The tracker instead gives each class's best seniors a real
program and a FINISHED four-year line, written once when the class graduates.

What has to hold:
  - it is written once and only read after — a retune never rewrites a career;
  - it is the same on every build (its own rng streams, keyed on the pid);
  - the service academies never take a non-American (the one placement authority);
  - a class from before the tracker is filled in from the alumni index, with no
    roster rebuilt;
  - the page and the player panel render a class that has DATA.
"""
import json
import random
from types import SimpleNamespace

import pytest

from app import jhsaa as jh
from app import jhsaa_college as jcol
from app import ncaa
from app import world as wd


@pytest.fixture(autouse=True)
def _model_one(monkeypatch):
    """This file covers the STORE and model 1, which classes already written
    under it still read. Model 2 is the shipped default and has its own file."""
    monkeypatch.setattr(jcol, "ACTIVE_MODEL", 1)


def _seniors(n=900, seed=7, foreign_every=6):
    r = random.Random(seed)
    out = []
    for i in range(n):
        ovr = r.gauss(55, 10)
        out.append({"pid": f"pid{seed}-{i}", "name": f"Player {i}", "hs": "Some High",
                    "ovr": ovr, "pot": ovr + abs(r.gauss(4, 5)),
                    "domestic": i % foreign_every != 0})
    return out


@pytest.fixture
def lab_world():
    """A JHSAA-only world on the suite's throwaway database."""
    wd.reset(wd.DEFAULT_SEED)
    w = wd.get_or_create_jhsaa_only(wd.DEFAULT_SEED, salt="alumni-test")
    yield w
    wd.reset(wd.DEFAULT_SEED)


@pytest.mark.parametrize("gender", ["girls", "boys"])
def test_a_class_is_the_best_seniors_dealt_across_real_programs(gender):
    seniors = _seniors()
    rows = jcol.build_class([dict(s) for s in seniors], gender, 2100, "s")
    assert len(rows) == jcol.CLASS_SIZE
    assert [r["rank"] for r in rows] == list(range(1, jcol.CLASS_SIZE + 1))
    # The best by the rating they LEFT on, and nobody else.
    best = {s["pid"] for s in sorted(seniors, key=lambda s: -s["ovr"])[:jcol.CLASS_SIZE]}
    assert {r["pid"] for r in rows} == best
    # Every destination is a real program of the division the row names.
    real = {d: {p.school for p in ps} for d, ps in jcol._programs(gender).items()}
    counts = {}
    for r in rows:
        assert r["college"] in real[r["division"]]
        counts[r["division"]] = counts.get(r["division"], 0) + 1
    assert counts == {d: n for d, n in
                      jcol.division_counts(jcol.CLASS_SIZE, gender).items() if n}
    # Spread: one class does not stack a program.
    per_college = {}
    for r in rows:
        per_college[r["college"]] = per_college.get(r["college"], 0) + 1
    assert max(per_college.values()) <= jcol.PER_PROGRAM
    # Division is earned on rank, with a blurred border — never inverted wholesale.
    mean_rank = {d: sum(r["rank"] for r in rows if r["division"] == d) / counts[d]
                 for d in counts}
    ordered = [mean_rank[d] for d in jcol.DIVISION_ORDER if d in mean_rank]
    assert ordered == sorted(ordered)


def test_the_line_is_a_finished_four_year_career():
    rows = jcol.build_class(_seniors(), "girls", 2100, "s")
    for r in rows:
        n = ncaa.lineup_size(r["division"])
        assert [s["class"] for s in r["seasons"]] == ["Fr", "So", "Jr", "Sr"]
        assert [s["year"] for s in r["seasons"]] == [2101, 2102, 2103, 2104]
        for s in r["seasons"]:
            assert s["pos"] is None or 1 <= s["pos"] <= n
            assert s["w"] >= 0 and s["l"] >= 0
        played = [s["pos"] for s in r["seasons"] if s["pos"]]
        assert r["peak"] == (min(played) if played else None)
        assert r["w"] == sum(s["w"] for s in r["seasons"])
        assert r["l"] == sum(s["l"] for s in r["seasons"])
    # A state this deep sends real No. 1s and some honours — and not only those.
    peaks = [r["peak"] for r in rows if r["peak"]]
    assert 10 <= sum(p == 1 for p in peaks) <= 120
    assert any(r["honors"] for r in rows) and not all(r["honors"] for r in rows)


def test_it_is_the_same_every_time_and_varies_by_save():
    a = jcol.build_class(_seniors(), "boys", 2100, "salt-a")
    assert a == jcol.build_class(_seniors(), "boys", 2100, "salt-a")
    b = jcol.build_class(_seniors(), "boys", 2100, "salt-b")
    assert [r["pid"] for r in a] == [r["pid"] for r in b]       # same class…
    assert [r["college"] for r in a] != [r["college"] for r in b]   # …other futures


def test_a_service_academy_never_takes_a_non_american(monkeypatch):
    """Every pipeline that places a player at a program asks the one authority.
    Forced: make the academies the most attractive programs in view."""
    academies = set(ncaa.SERVICE_ACADEMIES)
    assert any(p.school in academies for ps in jcol._programs("boys").values() for p in ps)
    real_gauss = random.Random.gauss
    for trial in range(6):
        rows = jcol.build_class(_seniors(seed=trial, foreign_every=2), "boys", 2100,
                                f"academy-{trial}")
        foreign = {s["pid"] for s in _seniors(seed=trial, foreign_every=2)
                   if not s["domestic"]}
        for r in rows:
            if r["college"] in academies:
                assert r["pid"] not in foreign
    assert real_gauss is random.Random.gauss


def test_written_once_and_never_rewritten(lab_world, monkeypatch):
    """The store is the record. A retune — or a second call — reaches classes that
    have not graduated yet and nobody else."""
    w = lab_world
    school = jh.load_schools("girls")[0]
    roster = jh.build_roster(school, 2100, "alumni-test")
    assert any(p.grade == 12 for p in roster)
    team = SimpleNamespace(school=school, roster=roster)
    conn = wd._db()
    try:
        n = jcol.record_class(conn, w["id"], "girls", 2100, "alumni-test", [team])
        conn.commit()
        assert n == sum(p.grade == 12 for p in roster)
        before = conn.execute("SELECT pid, data FROM world_jhsaa_college"
                              " ORDER BY pid").fetchall()
        monkeypatch.setattr(jcol, "HOME_STATE_PULL", 50.0)      # a "retune"
        monkeypatch.setattr(jcol, "RANK_BLUR", 0.4)
        jcol.record_class(conn, w["id"], "girls", 2100, "alumni-test", [team])
        conn.commit()
        after = conn.execute("SELECT pid, data FROM world_jhsaa_college"
                             " ORDER BY pid").fetchall()
        assert [tuple(r) for r in before] == [tuple(r) for r in after]
        # The stored line carries the real player and the real school.
        senior = next(p for p in roster if p.grade == 12)
        line = jcol.line_for(conn, w["id"], senior.pid, "alumni-test")
        assert line["name"] == senior.name and line["hs"] == school.name
        assert line["grad_year"] == 2100 and len(line["seasons"]) == 4
        # A player who has not graduated has no line — and asking writes nothing.
        junior = next(p for p in roster if p.grade != 12)
        assert jcol.line_for(conn, w["id"], junior.pid, "alumni-test") is None
        assert len(conn.execute("SELECT 1 FROM world_jhsaa_college").fetchall()) == n
    finally:
        conn.close()


def test_a_class_from_before_the_tracker_is_filled_in_from_the_alumni_index(lab_world):
    """No roster is rebuilt: the index already holds every senior and the rating
    they left on."""
    w = lab_world
    conn = wd._db()
    try:
        idx = _seniors(n=500, seed=3)
        conn.executemany(
            "INSERT INTO jhsaa_alumni (world_id, pid, gender, ident, school, grad_year,"
            " name, style, trait, ovr, rank, honored) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(w["id"], s["pid"], "boys", "id", s["hs"], 2090, s["name"], "", "",
              s["ovr"], 1 + i % 9, 0) for i, s in enumerate(idx)])
        conn.commit()
        assert 2090 in jcol.class_years(conn, w["id"], "boys")
        assert jcol.class_years(conn, w["id"], "girls") == []
        rows = jcol.class_rows(conn, w["id"], "boys", 2090, "alumni-test")
        assert len(rows) == jcol.CLASS_SIZE
        best = sorted(idx, key=lambda s: -s["ovr"])
        assert rows[0]["pid"] == best[0]["pid"]
        # Filled in ONCE: a second read is the stored class, row for row.
        assert jcol.class_rows(conn, w["id"], "boys", 2090, "alumni-test") == rows
        # …and a single player's line resolves the same way, off the pid alone.
        assert jcol.line_for(conn, w["id"], best[5]["pid"], "alumni-test")["rank"] == 6
        assert jcol.line_for(conn, w["id"], best[-1]["pid"], "alumni-test") is None
        assert len(jcol.all_rows(conn, w["id"], "alumni-test")) == jcol.CLASS_SIZE
    finally:
        conn.close()


def test_a_world_reset_clears_the_tracker(lab_world):
    w = lab_world
    conn = wd._db()
    try:
        jcol._insert(conn, w["id"], jcol.build_class(_seniors(), "girls", 2100, "s"))
        conn.commit()
    finally:
        conn.close()
    wd.reset(wd.DEFAULT_SEED)
    conn = wd._db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM world_jhsaa_college").fetchone()[0] == 0
    finally:
        conn.close()


def test_the_page_and_the_player_panel_render_a_class_with_data(lab_world):
    """An empty-state route test cannot see a page (CLAUDE.md). This renders the
    alumni table and the player page's College panel over a real roster."""
    from flask import render_template
    from app.web import state as st
    from app.web.server import create_app
    w = lab_world
    app = create_app()
    grad_year = wd.BASE_YEAR + w["year"] + 1                    # the season on screen
    school = jh.load_schools("girls")[0]
    roster = jh.build_roster(school, grad_year, "alumni-test")
    conn = wd._db()
    try:
        jcol.record_class(conn, w["id"], "girls", grad_year, "alumni-test",
                          [SimpleNamespace(school=school, roster=roster)])
        # The player page walks ARCHIVED seasons, so the season has to exist —
        # the summary row alone is enough for a roster and a career to resolve.
        conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data)"
                     " VALUES (?,?,?,?)",
                     (w["id"], w["year"], "girls",
                      json.dumps({"year": w["year"], "season_year": grad_year,
                                  "gender": "girls"})))
        conn.commit()
    finally:
        conn.close()
    wd._arc_forget(w["id"], w["year"], "girls")
    senior = next(p for p in roster if p.grade == 12)

    view = st.jhsaa_alumni_view(wd.DEFAULT_SEED, "girls")
    assert view["grad_year"] == grad_year and view["rows"]
    # ONE PAGE of the class, never the class (owner, 2026-11); the counts are
    # the whole class's.
    assert len(view["rows"]) <= st.ALUMNI_PER_PAGE
    assert sum(n for _d, n in view["division_counts"]) == view["total"]
    with app.test_request_context("/jhsaa/alumni?g=girls"):
        html = render_template("jhsaa_alumni.html", active="High School", view=view,
                               gender="women", u="D1-women", uni_label="")
    for r in view["rows"]:
        assert r["name"] in html and r["stints"][0]["college"] in html
        assert f'{r["s_w"]}-{r["s_l"]}' in html
    assert "College Alumni" in html
    # The other three views of the same careers render too.
    for mode in ("all", "colleges", "schools"):
        v = st.jhsaa_alumni_view(wd.DEFAULT_SEED, "girls", mode=mode)
        assert v["total"] > 0
        with app.test_request_context(f"/jhsaa/alumni?g=girls&mode={mode}"):
            assert "College Alumni" in render_template(
                "jhsaa_alumni.html", active="High School", view=v,
                gender="women", u="D1-women", uni_label="")

    pv = st.jhsaa_player_view(wd.DEFAULT_SEED, "girls", school.name, senior.pid)
    assert pv["found"] and pv["college"]["stints"][0]["college"]
    with app.test_request_context(f"/jhsaa/player/{school.name}/{senior.pid}?g=girls"):
        html = render_template("jhsaa_player.html", active="High School", view=pv,
                               gender="women", u="D1-women", uni_label="")
    line = pv["college"]
    assert line["stints"][0]["college"] in html
    assert f'Singles {line["s_w"]}-{line["s_l"]}' in html
    assert all(s["class"] in html for s in line["seasons"])



# --- the rung's wiring ---------------------------------------------------------

def test_the_rung_hands_it_real_teams_and_only_in_a_world_without_college(lab_world):
    """`run_jhsaa` passes `season["teams"].values()` — `TeamSeason`s. Built here the
    way the rung builds them (`district_teams`, real rosters, one league a class)
    without playing the season: the tracker reads a team's school and roster and
    nothing a dual produces.

    (The scaled played-season fixture in `tests/test_jhsaa_toc.py` cannot be used:
    it currently fails to field a Ward on untouched code.)"""
    w = lab_world
    schools = jh.load_schools("boys")
    league = {}
    for s in schools:
        league.setdefault((s.group, s.district), []).append(s)
    teams = []
    for members in list(league.values())[:6]:
        teams += jh.district_teams(members, 2100, "alumni-test")
    assert all(type(t).__name__ == "TeamSeason" for t in teams)
    seniors = [p for t in teams for p in t.roster if p.grade == 12]
    conn = wd._db()
    try:
        n = jcol.record_class(conn, w["id"], "boys", 2100, "alumni-test", teams)
        conn.commit()
        assert n == min(jcol.CLASS_SIZE, len(seniors)) > 0
        rows = jcol.class_rows(conn, w["id"], "boys", 2100, "alumni-test")
        best = sorted(seniors, key=lambda p: (-p.current_overall(), p.pid))[:n]
        assert [r["pid"] for r in rows] == [p.pid for p in best]
        by_pid = {p.pid: (p, t) for t in teams for p in t.roster}
        for r in rows:
            p, t = by_pid[r["pid"]]
            assert r["name"] == p.name and r["hs"] == t.school.name
    finally:
        conn.close()
    # The rung asks ONE question before it writes, through the probe that is
    # deliberately never memoised — so attaching college to a lab save stops the
    # tracker at once, and a college save never starts it.
    import inspect
    src = inspect.getsource(wd.run_jhsaa)
    assert "track_alumni = tracks_alumni(seed)" in src and "if track_alumni:" in src
    # …and that rule: a world with no college in it, or one that does not hand its
    # seniors to a real recruit board.
    assert wd.tracks_alumni(wd.DEFAULT_SEED)
