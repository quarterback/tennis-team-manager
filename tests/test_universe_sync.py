"""One world, one clock — every active universe advances together.

Regression: the Season Hub's "Advance week →" stepped only the universe the page
was showing. The world week and the other universes stayed put, so the rankings
compared a men's field 25 duals into its year (full conference slate) against a
women's field 12 duals in whose conference play had barely started. Both boards
were internally correct — they were just from different weeks.
"""
import app.seasonmode as sm
import app.world as wd
from app.web.server import create_app


def _season_row(division, gender, seed, phase, week):
    conn = sm._db()
    cur = conn.execute(
        "INSERT INTO seasons (division, gender, seed, current_week, total_weeks, phase, champion)"
        " VALUES (?,?,?,?,?,?,?)", (division, gender, seed, week, 17, phase, None))
    conn.commit(); conn.close()
    return cur.lastrowid


def test_season_progress_orders_the_year(tmp_path):
    sm.DB_PATH = str(tmp_path / "s.db")
    kickoff = _season_row("D1", "men", 1, "ita_kickoff", 7)
    early = _season_row("D1", "women", 2, "regular", 8)
    late = _season_row("D2", "men", 3, "regular", 14)
    post = _season_row("D2", "women", 4, "conf_tournaments", 18)
    keys = [sm.season_progress(s) for s in (kickoff, early, late, post)]
    assert keys == sorted(keys)                 # strictly increasing through the year
    assert len(set(keys)) == 4


def test_season_progress_matches_for_seasons_at_the_same_point(tmp_path):
    sm.DB_PATH = str(tmp_path / "s.db")
    a = _season_row("D1", "men", 1, "regular", 11)
    b = _season_row("D1", "women", 2, "regular", 11)
    assert sm.season_progress(a) == sm.season_progress(b)


def test_resync_advances_only_the_laggards(tmp_path, monkeypatch):
    """resync_universes steps the behind universes until they stand level — and
    never advances the leader past where it already is."""
    sm.DB_PATH = str(tmp_path / "s.db")
    men = _season_row("D1", "men", 9, "regular", 14)          # 6 weeks ahead
    women = _season_row("D1", "women", 9, "regular", 8)

    monkeypatch.setattr(wd, "_active_unis", lambda: [("D1", "men"), ("D1", "women")])
    monkeypatch.setattr(wd, "get_or_create", lambda *a, **k: {"id": 1, "year": 0, "week": 8})
    monkeypatch.setattr(wd, "universe_sid",
                        lambda seed, w, d, g: men if g == "men" else women)
    monkeypatch.setattr(wd, "prime", lambda *a, **k: None)

    def _fake_advance(sid):                                    # one week per call
        conn = sm._db()
        conn.execute("UPDATE seasons SET current_week=current_week+1 WHERE id=?", (sid,))
        conn.commit(); conn.close()
    monkeypatch.setattr(wd.sm, "advance", _fake_advance)

    assert not wd.universes_in_sync()
    res = wd.resync_universes()
    assert res["in_sync"] and res["stepped"] == {"D1 women": 6}
    assert sm.load_season(men)["current_week"] == 14           # leader untouched
    assert sm.load_season(women)["current_week"] == 14


def test_resync_leaves_a_fall_portal_hold_alone(tmp_path, monkeypatch):
    """Only the world driver may release the fall-portal hold — sm.advance would
    pass it straight through and skip the portal entirely."""
    sm.DB_PATH = str(tmp_path / "s.db")
    men = _season_row("D1", "men", 9, "regular", 12)
    women = _season_row("D1", "women", 9, "fall_portal", 7)

    monkeypatch.setattr(wd, "_active_unis", lambda: [("D1", "men"), ("D1", "women")])
    monkeypatch.setattr(wd, "get_or_create", lambda *a, **k: {"id": 1, "year": 0, "week": 8})
    monkeypatch.setattr(wd, "universe_sid",
                        lambda seed, w, d, g: men if g == "men" else women)
    monkeypatch.setattr(wd, "prime", lambda *a, **k: None)
    monkeypatch.setattr(wd.sm, "advance",
                        lambda sid: (_ for _ in ()).throw(AssertionError("advanced a hold")))

    res = wd.resync_universes()
    assert res["steps"] == 0 and res["blocked"] == ["D1 women"] and not res["in_sync"]


def test_advance_route_drives_the_whole_world(tmp_path, monkeypatch):
    """With a world present, advancing moves the world clock (every universe), not
    whichever universe the page happens to be showing."""
    sm.DB_PATH = str(tmp_path / "s.db")
    app = create_app()
    calls = {"world": 0, "solo": 0}
    monkeypatch.setattr(wd, "exists", lambda *a, **k: True)
    monkeypatch.setattr(wd, "is_primed", lambda *a, **k: True)   # skip the warm-up hook
    monkeypatch.setattr(wd, "prime", lambda *a, **k: None)
    monkeypatch.setattr(wd, "load_world", lambda *a, **k: {"id": 1, "year": 0, "week": 3})
    monkeypatch.setattr(wd, "season_complete", lambda *a, **k: False)
    monkeypatch.setattr(wd, "advance_week", lambda *a, **k: calls.__setitem__("world", calls["world"] + 1))
    monkeypatch.setattr(sm, "advance", lambda sid: calls.__setitem__("solo", calls["solo"] + 1))

    assert app.test_client().post("/world/advance?u=D1-women").status_code in (302, 303)
    assert calls == {"world": 1, "solo": 0}


def test_there_is_exactly_one_advance_route(tmp_path):
    """Two advance endpoints is the bug. `world_advance` is the only route allowed
    to move a season forward — a per-universe sibling (the old /season/advance)
    silently forks the save into universes sitting at different weeks."""
    sm.DB_PATH = str(tmp_path / "s.db")
    app = create_app()
    # /gtt/advance is the pro tour, a separate league on its own clock — not a
    # college universe, so it isn't in scope here.
    advancing = {r.rule for r in app.url_map.iter_rules()
                 if "POST" in (r.methods or set()) and "advance" in r.rule
                 and not r.rule.startswith("/gtt/")}
    assert advancing == {"/world/advance"}


def test_web_layer_never_steps_a_season_directly():
    """No web route may call sm.advance — it bypasses the world driver (and with it
    the fall portal, the recruiting drip, the cross-division slate and prime()).
    The single exception is world_advance's no-world standalone branch."""
    import pathlib
    src = pathlib.Path(__file__).resolve().parent.parent / "app" / "web"
    hits = [f"{p.name}:{i}" for p in src.rglob("*.py")
            for i, line in enumerate(p.read_text().splitlines(), 1)
            if "sm.advance(" in line or "seasonmode.advance(" in line]
    assert len(hits) == 1 and hits[0].startswith("server.py:"), hits
