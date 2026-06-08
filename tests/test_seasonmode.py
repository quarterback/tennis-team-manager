import importlib

import pytest

import app.seasonmode as sm


@pytest.fixture
def db(tmp_path):
    sm.DB_PATH = str(tmp_path / "season.db")
    yield


def test_schedule_structure(db):
    sid = sm.create_season("D1", "men", seed=2026)
    s = sm.load_season(sid)
    assert s["total_weeks"] > 8 and s["phase"] == "regular"
    sched = sm.team_schedule(sid, "Oregon")
    assert 18 <= len(sched) <= 30                       # ~ a real-season slate
    # non-conference is front-loaded, then conference
    flags = [d["is_conf"] for d in sched]
    first_conf = flags.index(1)
    assert set(flags[:first_conf]) == {0}              # all early duals non-conf
    assert flags[-1] == 1                              # season ends in conference play


def test_advance_populates_results_and_standings(db):
    sid = sm.create_season("D1", "women", seed=7)
    r = sm.advance(sid)
    assert r["phase"] == "regular" and r["played"] > 0
    # week 1 duals are now final with scores
    finals = [d for d in sm.week_duals(sid, 1) if d["status"] == "final"]
    assert finals and all(d["home_points"] + d["away_points"] >= 4 for d in finals)
    st = sm.standings(sid)
    assert any(row["ow"] + row["ol"] > 0 for table in st.values() for row in table)


def test_get_or_create_is_idempotent(db):
    a = sm.get_or_create("D1", "men", seed=3)
    b = sm.get_or_create("D1", "men", seed=3)
    assert a == b


def test_full_season_reaches_a_champion(db):
    sid = sm.create_season("D1", "women", seed=11)
    guard = 0
    while sm.load_season(sid)["phase"] != "complete" and guard < 80:
        sm.advance(sid); guard += 1
    s = sm.load_season(sid)
    assert s["phase"] == "complete" and s["champion"]    # ran regular → conf → NCAA


def test_every_roster_player_gets_a_match(db):
    """The playing-time guarantee: by the end of the regular season every player
    on every roster — including walk-ons — has a completed singles match."""
    import json
    from app.ncaa import build_roster, load_division
    sid = sm.create_season("D2", "women", seed=5)
    guard = 0
    while sm.load_season(sid)["phase"] == "regular" and guard < 40:
        sm.advance(sid); guard += 1
    conn = sm._db()
    rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'"
                        " AND round='REG'", (sid,)).fetchall()
    conn.close()
    played = set()
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            if ln.get("completed"):
                played.add(ln.get("home_pid"))
                played.add(ln.get("away_pid"))
    never = [pr.pid for p in load_division("D2", "women").programs
             for pr in build_roster(p) if pr.pid not in played]
    assert not never, f"{len(never)} roster players never played a match"


def test_lineups_are_deterministic(db, tmp_path):
    """Re-running the same season (fresh DB, same seed) yields identical duals —
    the playing-time guarantee is a pure function of seed/division/roster."""
    import hashlib

    def run(path):
        sm.DB_PATH = path
        sm._forced_cache.clear()
        sid = sm.create_season("D1", "men", seed=2026)
        for _ in range(4):
            sm.advance(sid)
        conn = sm._db()
        rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'"
                            " ORDER BY id", (sid,)).fetchall()
        conn.close()
        return hashlib.md5("".join(r["lines_json"] or "" for r in rows).encode()).hexdigest()

    assert run(str(tmp_path / "a.db")) == run(str(tmp_path / "b.db"))
