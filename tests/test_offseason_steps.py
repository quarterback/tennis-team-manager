"""The offseason runs as separate, visible steps — nothing important happens
inside another step's click.

    awards → WORLD CUPS → rollover → PRO OFFSEASON → (preseason portal, week 0)

The Davis / BJK cups used to run inside `_finalize_year`, and the pro league's
off-season was a silent tail of that same call, so you couldn't see either happen
or tell whether the pro roll had touched the college world.
"""
import app.world as wd
import app.worldconfig as wc


def _world(year=1, week=0, wid=1):
    return {"id": wid, "year": year, "week": week, "seed": 2026}


def test_cups_run_before_the_rollover(monkeypatch):
    """The cups step comes first while the season is complete, so the seniors the
    rollover is about to graduate play their last cup."""
    order = []
    monkeypatch.setattr(wd, "get_or_create", lambda *a, **k: _world())
    monkeypatch.setattr(wd, "_all_complete", lambda *a, **k: True)
    monkeypatch.setattr(wd, "cups_done", lambda w: "cups" in order)
    monkeypatch.setattr(wd, "run_world_cups",
                        lambda seed=2026, world=None: order.append("cups") or {"event": "world_cups"})
    monkeypatch.setattr(wd, "_finalize_year",
                        lambda seed, w: order.append("rollover") or {"event": "year"})

    assert wd.advance_week()["event"] == "world_cups"
    assert wd.advance_week()["event"] == "year"
    assert order == ["cups", "rollover"]          # cups strictly before graduation


def test_pro_offseason_is_its_own_step_at_week_zero(monkeypatch):
    """After the rollover the pro league drafts the class that just graduated —
    as a step of its own, before the new college season plays a dual."""
    monkeypatch.setattr(wd, "get_or_create", lambda *a, **k: _world(year=1, week=0))
    monkeypatch.setattr(wd, "_all_complete", lambda *a, **k: False)
    monkeypatch.setattr(wd, "pros_rolled", lambda w: False)
    called = []
    monkeypatch.setattr(wd, "run_pro_offseason",
                        lambda seed=2026, world=None: called.append(1) or {"event": "pro_offseason"})
    assert wd.advance_week()["event"] == "pro_offseason"
    assert called == [1]


def test_pro_offseason_does_not_repeat_or_fire_in_year_zero(monkeypatch):
    """Year 0 has no graduating class, and the step never runs twice for a year."""
    monkeypatch.setattr(wd, "_all_complete", lambda *a, **k: False)
    monkeypatch.setattr(wd, "run_pro_offseason",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    monkeypatch.setattr(wd, "prime", lambda *a, **k: None)
    monkeypatch.setattr(wd, "_active_unis", lambda: [])
    monkeypatch.setattr(wd, "simulate_cross", lambda *a, **k: 0)

    monkeypatch.setattr(wd, "get_or_create", lambda *a, **k: _world(year=0, week=0))
    monkeypatch.setattr(wd, "pros_rolled", lambda w: False)
    wd.advance_week()                               # year 0: no class to draft, must not fire

    monkeypatch.setattr(wd, "get_or_create", lambda *a, **k: _world(year=2, week=0))
    monkeypatch.setattr(wd, "pros_rolled", lambda w: True)
    wd.advance_week()                               # already rolled: must not fire again


def test_pros_rolled_marker_is_per_year(tmp_path, monkeypatch):
    monkeypatch.setattr(wc, "get", lambda k: {"pros_rolled_year": "3"}.get(k, ""))
    assert wd.pros_rolled(_world(year=3))
    assert not wd.pros_rolled(_world(year=4))


def test_cup_rosters_are_real_persisted_players(monkeypatch):
    """The cup pool comes from the world's own rosters — the ACTIVE universes
    developed to now plus the DORMANT ones as persisted. Never scan_rosters, which
    re-derives dormant divisions from the generator instead of reading the save."""
    monkeypatch.setattr(wd, "developed_rosters", lambda w: {("D1", "men"): {"A": ["dev"]}})
    monkeypatch.setattr(wd, "_load_rosters",
                        lambda conn, wid, yr, unis=None: {("D1", "men"): {"A": ["stored"]},
                                                          ("D3", "men"): {"B": ["dormant"]}})
    monkeypatch.setattr(wd, "scan_rosters",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("regenerated")))
    out = wd.cup_rosters(_world())
    assert out[("D1", "men")] == {"A": ["dev"]}        # active: the developed copy wins
    assert out[("D3", "men")] == {"B": ["dormant"]}    # dormant: the persisted rows


def test_new_league_clears_the_pro_roll_marker(tmp_path, monkeypatch):
    """`reset()` drops the GTT tables but not world_setting, so a stale marker read
    as done for the SAME year number in the next save — the new league's first
    rollover also lands on year 1 — and its first class was never drafted."""
    import app.seasonmode as sm
    sm.DB_PATH = str(tmp_path / "s.db")
    wc.set("pros_rolled_year", "1")
    assert wd.pros_rolled(_world(year=1))
    wd.reset()
    assert wc.get("pros_rolled_year") == ""        # value AND the in-memory memo
    assert not wd.pros_rolled(_world(year=1))      # the new save still owes the step


def test_unarchived_year_returns_no_cup(monkeypatch):
    """An explicit year answers for THAT year or not at all. It used to fall through
    to 'most recent archived', so the interval after the seasons complete but before
    the cup step runs rendered LAST year's champion under this year's pill."""
    from app.web import state
    monkeypatch.setattr(wd, "exists", lambda *a, **k: True)
    asked = {}

    def _latest(seed, gender, year=None):
        asked["year"] = year
        return None if year == 1 else {"event": "Davis Cup", "year": 0}
    monkeypatch.setattr(wd, "latest_world_cup", _latest)

    assert state.get_world_cup("men", year=wd.BASE_YEAR + 1) is None   # current, unarchived
    assert asked["year"] == 1                                          # asked for THAT year
    assert state.get_world_cup("men", year=wd.BASE_YEAR) is not None   # archived year still works


def test_header_offers_awards_before_the_cup(tmp_path, monkeypatch):
    """/world/advance refuses to move while honors are unstamped, so the header must
    not advertise the cup step yet — the button would redirect and do nothing."""
    import app.seasonmode as sm
    import app.honors as honors
    from app.web import server
    sm.DB_PATH = str(tmp_path / "s.db")
    monkeypatch.setattr(wd, "exists", lambda *a, **k: True)
    monkeypatch.setattr(wd, "load_world", lambda *a, **k: {"id": 1, "year": 0, "week": 20})
    monkeypatch.setattr(wd, "_active_unis", lambda: [("D1", "men")])
    monkeypatch.setattr(wd, "signed_counts", lambda *a, **k: {})
    monkeypatch.setattr(wd, "current_year_seed", lambda *a, **k: 2026)
    monkeypatch.setattr(wd, "cups_done", lambda w: False)
    monkeypatch.setattr(sm, "get_or_create", lambda *a, **k: 1)
    monkeypatch.setattr(sm, "load_season", lambda sid: {"phase": "complete"})
    monkeypatch.setattr(server, "UNIVERSES", [("D1-men", "D1", "men", "D1 Men")])

    monkeypatch.setattr(honors, "has_season", lambda *a, **k: False)
    g = server._game_context()
    assert g["awards_pending"] and g["action"] == "Run awards"

    monkeypatch.setattr(honors, "has_season", lambda *a, **k: True)
    g = server._game_context()
    assert not g["awards_pending"] and g["action"] == "Run Davis / BJK Cup"


def test_cup_failure_is_loud_not_swallowed(monkeypatch):
    """A cup that throws must NOT leave the year silently with no cup and no honors."""
    import app.national_teams as nt
    monkeypatch.setattr(wc, "active_genders", lambda: ["men"])
    monkeypatch.setattr(nt, "run_world_cup",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    class _Conn:
        def execute(self, *a, **k): return None
    try:
        wd._store_world_cups(_Conn(), _world(), {})
    except RuntimeError as e:
        assert "boom" in str(e)
    else:
        raise AssertionError("cup failure was swallowed")
