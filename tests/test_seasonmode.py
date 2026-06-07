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
