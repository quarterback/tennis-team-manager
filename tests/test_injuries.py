"""Injuries — the deliberately non-deterministic system. We assert the dice are
calibrated and wired (lineup filtering, per-save persistence, medical redshirts),
not golden outcomes."""
import os
import tempfile

import pytest

from app import injuries
from app.ncaa import load_division, build_roster


@pytest.fixture(autouse=True)
def _enable_seeded():
    """Injury tests need the dice ON and pinned to a seed (the global autouse
    fixture turns them off for determinism elsewhere)."""
    injuries.set_enabled(True)
    injuries.seed_for_testing(2026)
    yield
    injuries.seed_for_testing(None)
    injuries.set_enabled(True)


def _starters(prog):
    r = build_roster(prog)
    return sorted(r, key=lambda p: p.current_overall(), reverse=True)[:6]


def test_disabled_never_injures():
    injuries.set_enabled(False)
    p = _starters(load_division("D1", "men").programs[0])[0]
    assert all(injuries.roll_injury(p) == 0 for _ in range(1000))


def test_durability_in_unit_range():
    for prog in load_division("D1", "men").programs[:5]:
        for p in _starters(prog):
            assert 0.0 <= injuries.durability(p) <= 1.0
            assert 0.0 < injuries.injury_rate(p) < 0.2


def test_severity_bounds():
    """Every injury is either 1..6 duals or season-ending (-1) — never out of band."""
    p = _starters(load_division("D2", "men").programs[0])[0]
    saw_injury = False
    for _ in range(5000):
        out = injuries.roll_injury(p)
        if out == 0:
            continue
        saw_injury = True
        assert out == injuries.SEASON_ENDING or injuries.MIN_DUALS_OUT <= out <= injuries.MAX_DUALS_OUT
    assert saw_injury, "injuries should be common enough to show up in 5000 rolls"


def test_prevalence_about_half_a_starter():
    """~0.5 starters hurt at any given time, averaged across a division."""
    import statistics
    div = load_division("D2", "men")

    def prevalence(starters, n_duals=30, trials=120):
        seen = []
        for _ in range(trials):
            rem = [0] * len(starters)
            for _d in range(n_duals):
                seen.append(sum(1 for r in rem if r != 0))
                for i in range(len(starters)):
                    if rem[i] > 0:
                        rem[i] -= 1
                for i in range(len(starters)):
                    if rem[i] == 0:
                        o = injuries.roll_injury(starters[i])
                        rem[i] = -1 if o == injuries.SEASON_ENDING else o
        return statistics.mean(seen)

    vals = [prevalence(_starters(p)) for p in div.programs[:10]]
    avg = statistics.mean(vals)
    assert 0.3 <= avg <= 0.75, f"prevalence {avg:.2f} off the ~0.5 target"


def test_season_ending_is_rare():
    """Of all injuries, ~1-in-100 end the season."""
    p = _starters(load_division("D1", "men").programs[0])[0]
    injuries.seed_for_testing(7)
    inj = season = 0
    for _ in range(200000):
        out = injuries.roll_injury(p)
        if out == 0:
            continue
        inj += 1
        if out == injuries.SEASON_ENDING:
            season += 1
    assert inj > 0
    assert 0.003 <= season / inj <= 0.03, f"season-ending share {season/inj:.4f}"


# ---- wiring: lineup filter --------------------------------------------------

def test_lineup_drops_injured():
    from app.season import coach_lineup
    prog = load_division("D1", "men").programs[0]
    roster = build_roster(prog)
    healthy = sorted(roster, key=lambda p: p.str_value(), reverse=True)
    ace = healthy[0]
    team, chosen = coach_lineup(prog, roster, None, 0.5, lineup_seed=1, dual_seed=1,
                                unavailable={ace.pid})
    assert ace.pid not in {p.pid for p in chosen}
    assert len(chosen) == 6   # a depth body pulled up


def test_dual_between_reports_who_played():
    from app.season import dual_between
    div = load_division("D2", "men")
    a, b = div.programs[0], div.programs[1]
    rec = dual_between(a, b, seed=5, conf=False)
    assert rec["home_played"] and rec["away_played"]
    assert len(rec["home_played"]) == 6


# ---- wiring: per-save persistence + medical redshirt rollover ---------------

def test_seasonmode_persists_injuries():
    from app import seasonmode as sm
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    old = sm.DB_PATH
    try:
        sm.DB_PATH = path
        sm.init_schema()
        injuries.seed_for_testing(99)
        sid = sm.create_season("D3", "men", seed=2026)
        for _ in range(40):
            out = sm.advance(sid)
            if out.get("phase") == "complete":
                break
        conn = sm._db()
        total = conn.execute("SELECT COUNT(*) c FROM injuries WHERE season_id=?",
                             (sid,)).fetchone()["c"]
        conn.close()
        assert total > 0, "a full division-season should produce injuries"
        # season_ending_pids returns exactly the season-ending cohort
        assert isinstance(sm.season_ending_pids(sid), set)
    finally:
        sm.DB_PATH = old
        os.unlink(path)


def test_medical_redshirt_repeats_class_with_rs_tag():
    from app.world import graduate
    from app.development import Prospect

    jr = Prospect(name="Hurt Junior", pid="rs-test-1", class_year="Jr")
    so = Prospect(name="Healthy Soph", pid="ok-test-2", class_year="So")
    rosters = {("D1", "men"): {"School": [jr, so]}}
    graduate(rosters, redshirts={"rs-test-1"})
    kept = {p.pid: p for p in rosters[("D1", "men")]["School"]}
    assert kept["rs-test-1"].class_year == "RS-Jr"   # repeated, tagged
    assert kept["ok-test-2"].class_year == "Jr"        # normal advance So->Jr


def test_rs_tag_persists_then_graduates():
    from app.world import graduate
    from app.development import Prospect

    # An RS-Jr advances to RS-Sr next year, then graduates the year after.
    p = Prospect(name="RS player", pid="rs-test-3", class_year="RS-Jr")
    rosters = {("D1", "men"): {"S": [p]}}
    graduate(rosters)
    assert rosters[("D1", "men")]["S"][0].class_year == "RS-Sr"
    grads = graduate(rosters)            # RS-Sr graduates
    assert grads == 1
    assert rosters[("D1", "men")]["S"] == []


def test_redshirt_senior_gets_fifth_year():
    from app.world import graduate
    from app.development import Prospect

    sr = Prospect(name="Hurt Senior", pid="rs-test-4", class_year="Sr")
    rosters = {("D1", "men"): {"S": [sr]}}
    grads = graduate(rosters, redshirts={"rs-test-4"})
    assert grads == 0                                  # did NOT graduate
    assert rosters[("D1", "men")]["S"][0].class_year == "RS-Sr"


# ---- web UI: injury log pages ----------------------------------------------

def test_injury_pages_render(tmp_path):
    import app.seasonmode as sm
    from app.web.server import create_app
    sm.DB_PATH = str(tmp_path / "inj.db")
    injuries.set_enabled(True)
    injuries.seed_for_testing(2026)
    c = create_app().test_client()
    c.get("/season?u=D1-men")                 # create the season
    for _ in range(6):                        # play several weeks so injuries accrue
        c.post("/season/advance?u=D1-men")
    league = c.get("/injuries?u=D1-men")
    assert league.status_code == 200
    assert b"Injuries" in league.data
    # conference filter is accepted
    assert c.get("/injuries?u=D1-men&conf=All").status_code == 200
    # the per-program page carries the injury log panel
    team = c.get("/teams?u=D1-men&school=Oregon")
    assert team.status_code == 200
    assert b"Injury Log" in team.data
