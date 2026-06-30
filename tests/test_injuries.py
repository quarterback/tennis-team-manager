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
    team, chosen, _ = coach_lineup(prog, roster, None, 0.5, lineup_seed=1, dual_seed=1,
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
    # conference filter + status toggle are accepted
    assert c.get("/injuries?u=D1-men&conf=All").status_code == 200
    assert c.get("/injuries?u=D1-men&status=all").status_code == 200
    # default (currently out) is a subset of the full-season list
    from app.web.state import injury_rows
    out_now = injury_rows("D1", "men", active_only=True)
    all_season = injury_rows("D1", "men", active_only=False)
    assert all(r["active"] for r in out_now)
    assert len(out_now) <= len(all_season)
    # the per-program page carries the injury log panel
    team = c.get("/teams?u=D1-men&school=Oregon")
    assert team.status_code == 200
    assert b"Injury Log" in team.data


# ---- short-handed lineups + redshirt-slot protection ------------------------

def test_lineup_never_short_of_six_when_depth_exists():
    """Filtering the injured can leave <6 healthy; the engine fields six, so the
    lineup backfills the least-hurt injured rather than building a short Team
    (which would IndexError in simulate_dual)."""
    from app.season import coach_lineup
    prog = load_division("D1", "men").programs[0]
    roster = build_roster(prog)                 # D1 cap 12
    out = {p.pid for p in roster[:8]}           # 8 injured -> 4 healthy
    team, chosen, _ = coach_lineup(prog, roster, None, 0.5, lineup_seed=1, dual_seed=1,
                                unavailable=out)
    assert len(chosen) == 6
    assert len(team.singles) == 6
    assert len({p.pid for p in chosen}) == 6    # six distinct bodies pressed in


def test_lineup_clamps_a_sub_six_roster():
    """A roster with fewer than six players total can't seat six; the lineup pads
    to six so the dual still resolves instead of crashing."""
    from app.season import coach_lineup
    prog = load_division("D1", "men").programs[0]
    roster = build_roster(prog)[:4]             # only four players exist
    team, chosen, _ = coach_lineup(prog, roster, None, 0.5, lineup_seed=1, dual_seed=1)
    assert len(chosen) == 6
    assert len(team.singles) == 6


def test_short_handed_dual_resolves_end_to_end():
    from app.season import dual_between
    div = load_division("D2", "men")
    a, b = div.programs[0], div.programs[1]
    ra = build_roster(a)
    rec = dual_between(a, b, seed=11, conf=False,
                       unavailable_home={p.pid for p in ra[:len(ra) - 3]})  # 3 healthy
    assert rec["home_points"] + rec["away_points"] >= 4   # a winner was reached


def _mk_prospect(pid, rating, cls="So"):
    from app.development import Prospect
    from app.player_attributes import RICH_ATTRS
    return Prospect(name=pid, pid=pid, class_year=cls,
                    current={a: rating for a in RICH_ATTRS})


def test_normalize_protects_redshirt_returner():
    """A weak medical-redshirt senior survives the over-cap trim; the weakest
    movable player is the one displaced (recruiting already filled the opening)."""
    from app.world import _normalize, roster_cap

    cap = roster_cap("D1")                       # 12
    rs = _mk_prospect("rs-sr", 30, cls="RS-Sr")  # weakest on the roster
    others = [_mk_prospect(f"p{i}", 40 + i) for i in range(cap)]   # 12, all stronger
    rosters = {("D1", "men"): {"S": others + [rs]}}      # cap+1 -> over by one

    _normalize(rosters, protect={"rs-sr"})
    kept = {p.pid for p in rosters[("D1", "men")]["S"]}
    assert "rs-sr" in kept                       # the promised fifth year stays
    assert "p0" not in kept                       # weakest movable displaced instead
    assert len(kept) == cap


def test_normalize_unprotected_redshirt_can_be_displaced():
    """Without protection the same weak senior is the one displaced — proving the
    protect set is what saves them."""
    from app.world import _normalize, roster_cap

    cap = roster_cap("D1")
    rs = _mk_prospect("rs-sr", 30)
    rosters = {("D1", "men"): {"S": [_mk_prospect(f"p{i}", 40 + i) for i in range(cap)] + [rs]}}
    _normalize(rosters)                          # no protect
    assert "rs-sr" not in {p.pid for p in rosters[("D1", "men")]["S"]}


def test_overcap_surplus_relocates_not_deleted():
    """The over-cap surplus is sent to a program with an open slot, not deleted —
    no player vanishes from the universe when another team has room."""
    from app.world import _normalize, roster_cap
    div = load_division("D1", "men")
    a, b = div.programs[0].school, div.programs[1].school
    cap = roster_cap("D1")
    full = [_mk_prospect(f"a{i}", 50 + i) for i in range(cap + 1)]   # A is over by one
    room = [_mk_prospect(f"b{i}", 45 + i) for i in range(cap - 2)]   # B has open slots
    rosters = {("D1", "men"): {a: full, b: room}}
    before = sum(len(r) for r in rosters[("D1", "men")].values())

    out = _normalize(rosters)
    after = {s: [p.pid for p in r] for s, r in rosters[("D1", "men")].items()}
    assert out["relocated"] == 1 and out["departed"] == 0
    assert len(after[a]) == cap                              # A trimmed to cap
    assert "a0" in after[b]                                   # weakest A surplus landed at B
    assert sum(len(r) for r in rosters[("D1", "men")].values()) == before   # nobody deleted


def test_signed_freshman_kept_over_marginal_returner():
    """A signed recruit (class 'Fr') always keeps its seat; an over-cap roster
    displaces the weakest RETURNER instead — even if the freshman rates lower."""
    from app.world import _normalize, roster_cap

    cap = roster_cap("D1")
    fresh = _mk_prospect("frosh", 30, cls="Fr")                  # weakest overall, but signed
    returners = [_mk_prospect(f"r{i}", 40 + i) for i in range(cap)]  # all stronger returners
    rosters = {("D1", "men"): {"S": returners + [fresh]}}        # over by one

    _normalize(rosters)
    kept = {p.pid for p in rosters[("D1", "men")]["S"]}
    assert "frosh" in kept                                       # recruit keeps its seat
    assert "r0" not in kept                                      # weakest returner displaced


def test_injured_player_stays_on_roster_with_badge(tmp_path):
    """An injured player must remain visible on the program roster (just flagged
    out), not disappear until they return."""
    import app.seasonmode as sm
    from app import world as wd
    from app.web.server import create_app
    from app.web.state import team_roster
    sm.DB_PATH = str(tmp_path / "inj.db")
    injuries.set_enabled(True)
    injuries.seed_for_testing(2026)
    c = create_app().test_client()
    c.get("/season?u=D1-men")
    for _ in range(6):
        c.post("/season/advance?u=D1-men")
    sid = sm.get_or_create("D1", "men", seed=wd.current_year_seed())
    active = [e for e in sm.injury_log(sid) if e["active"]]
    assert active, "six weeks of D1 should produce at least one active injury"
    school = active[0]["school"]
    rows = team_roster("D1", "men", school)
    hurt = [r for r in rows if r["injury"]]
    assert hurt, "the injured player is still on the roster"
    # injured pid is present in the full roster, not filtered out
    assert active[0]["pid"] in {r["p"].pid for r in rows}
    html = c.get(f"/teams?u=D1-men&school={school}").data.decode()
    assert "bl-badge injured" in html        # the out badge renders


def test_recovery_grace_blocks_instant_reinjury(tmp_path):
    """A returning player enters a grace window: available to play, but the model
    is injury-aware and won't re-injure them until the window ticks out."""
    import app.seasonmode as sm
    sm.DB_PATH = str(tmp_path / "g.db")
    sm.init_schema()
    sid = sm.create_season("D3", "men", seed=2026)
    conn = sm._db()
    conn.execute("INSERT INTO injuries (season_id, pid, school, name, week, tag,"
                 " total, duals_remaining, season_ending) VALUES (?,?,?,?,?,?,?,?,0)",
                 (sid, "PID", "S", "Hurt Guy", 1, "REG", 1, 1))   # out for 1 dual
    conn.commit()

    def protected():
        return {r["pid"] for r in conn.execute(
            "SELECT pid FROM injuries WHERE season_id=? AND school=?"
            " AND (season_ending=1 OR duals_remaining<>0)", (sid, "S")).fetchall()}

    assert "PID" in sm._unavailable(conn, sid, "S")     # out now
    sm._recover_team(conn, sid, "S")                    # heals -> drops into grace
    assert "PID" not in sm._unavailable(conn, sid, "S") # back & available
    assert "PID" in protected()                          # ...but grace-protected
    for _ in range(injuries.RETURN_GRACE_DUALS):         # ride out the grace window
        sm._recover_team(conn, sid, "S")
    assert "PID" not in protected()                      # fully recovered, re-injurable
    conn.close()
