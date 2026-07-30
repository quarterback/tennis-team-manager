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
    from app import world as wd
    from app.web.server import create_app
    sm.DB_PATH = str(tmp_path / "inj.db")
    injuries.set_enabled(True)
    injuries.seed_for_testing(2026)
    c = create_app().test_client()
    c.get("/season?u=D1-men")                 # create the season
    sid = sm.get_or_create("D1", "men", seed=wd.current_year_seed())
    for _ in range(6):                        # play several weeks so injuries accrue
        sm.advance(sid)                       # standalone: no world driver
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
    # Resolve the season the SAME way team_roster does. Hardcoding 2026 here made
    # the test order-dependent: if an earlier test left a world behind, its year
    # seed is not 2026, so team_roster read a different season and saw no injuries.
    sid = sm.get_or_create("D1", "men", seed=wd.current_year_seed())
    for _ in range(6):
        sm.advance(sid)               # standalone: no world driver
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


# ---- pro league: the SAME durability system ---------------------------------

def test_pros_get_injured_like_college(tmp_path):
    """The pro game had no injuries at all — gtt_seasonmode never referenced this
    module, so durability meant nothing once a player graduated. Pros now roll on
    the same shared store: same dice, same durability scaling, same grace rules."""
    import app.gtt_seasonmode as gs
    p = str(tmp_path / "gtt.db")
    gs.DB_PATH = p
    gs._schema_ready_for = None
    injuries.set_enabled(True)
    injuries.seed_for_testing(2026)
    lid = gs.create_league("Durability", seed=3, n_teams=4)
    gs.advance_all(lid, fidelity="fast")          # a whole pro season

    conn = gs._db()
    rows = conn.execute("SELECT pid, team, total, season_ending FROM gtt_injuries"
                        " WHERE scope=?", (gs._inj_scope(lid, 0),)).fetchall()
    conn.close()
    assert rows, "a full pro season produced no injuries at all"
    # same shape as college: out 1-6 duals, or season-ending
    for r in rows:
        assert r["season_ending"] == 1 or 1 <= r["total"] <= injuries.MAX_DUALS_OUT


def test_injured_pro_is_dropped_from_the_lineup(tmp_path):
    """An injured pro is filtered out and a reserve is pulled up — the college
    depth behaviour, not a parallel implementation."""
    import app.gtt_seasonmode as gs
    p = str(tmp_path / "gtt2.db")
    gs.DB_PATH = p
    gs._schema_ready_for = None
    injuries.set_enabled(False)                   # control the injury by hand
    lid = gs.create_league("Depth", seed=4, n_teams=4)
    conn = gs._db()
    fid = conn.execute("SELECT id FROM gtt_franchises WHERE league_id=? LIMIT 1",
                       (lid,)).fetchone()["id"]
    scope = gs._inj_scope(lid, 0)
    _team, men, _women = gs._lineup(conn, lid, fid, "T", scope)
    starter = men[0]
    conn.execute("INSERT INTO gtt_injuries (scope, pid, team, name, week, tag, total,"
                 " duals_remaining, season_ending) VALUES (?,?,?,?,?,?,?,?,0)",
                 (scope, starter, str(fid), "x", 1, "t", 3, 3))
    conn.commit()
    _team2, men2, _w2 = gs._lineup(conn, lid, fid, "T", scope)
    conn.close()
    assert starter not in men2, "injured pro still in the lineup"
    assert len(men2) == len(men), "a reserve should have been pulled up"


def test_gtt_injuries_are_cleared_with_their_league(tmp_path):
    """gtt_injuries is keyed by an opaque scope int, so it has to be cleared
    explicitly. SQLite reuses league/franchise rowids and a new save reuses the
    default seed, so pids and scopes repeat EXACTLY — stale rows would bench
    players in a league that never injured them."""
    import app.gtt_seasonmode as gs
    gs.DB_PATH = str(tmp_path / "gtt.db")
    gs._schema_ready_for = None
    injuries.set_enabled(False)
    lid = gs.create_league("Wipe", seed=6, n_teams=4)

    def _seed_row(league_id):
        conn = gs._db()
        conn.execute("INSERT INTO gtt_injuries (scope, pid, team, name, week, tag,"
                     " total, duals_remaining, season_ending) VALUES (?,?,?,?,?,?,?,?,1)",
                     (gs._inj_scope(league_id, 0), "ghost", "1", "Ghost", 1, "t", 0, 0))
        conn.commit(); conn.close()

    def _rows():
        conn = gs._db()
        n = conn.execute("SELECT COUNT(*) c FROM gtt_injuries").fetchone()["c"]
        conn.close()
        return n

    _seed_row(lid)
    assert _rows() == 1
    gs.delete_league(lid)
    assert _rows() == 0, "deleting a league left its injury rows behind"

    lid2 = gs.create_league("Wipe2", seed=6, n_teams=4)
    _seed_row(lid2)
    gs.reset()
    assert _rows() == 0, "the whole-tour reset left injury rows behind"


# ---- retirements -------------------------------------------------------------

def test_retirement_rate_is_rare_and_scales_with_matches():
    """0.2% per completed singles match (owner rule): a handful per conference per
    season, not a weekly occurrence."""
    injuries.set_enabled(True)
    injuries.seed_for_testing(11)
    n = 200_000
    hits = sum(1 for _ in range(n) if injuries.roll_retirement())
    rate = hits / n
    assert 0.0015 < rate < 0.0025, f"retirement rate drifted to {rate:.4%}"


def test_retirement_never_fires_with_injuries_off():
    injuries.set_enabled(False)
    assert not any(injuries.roll_retirement() for _ in range(5000))


def test_retirement_ignores_the_score_and_costs_the_line(tmp_path):
    """A retirement does NOT care what the score is: whoever pulls out hurt loses the
    line even if they were ahead. That is the whole difference between a retirement
    and a normal loss."""
    import app.seasonmode as sm
    from app.ncaa import load_division, build_roster
    sm.DB_PATH = str(tmp_path / "ret.db")
    injuries.set_enabled(True)
    injuries.seed_for_testing(5)

    div = load_division("D1", "men")
    home, away = div.programs[0], div.programs[1]
    progs = {home.school: home, away.school: away}
    hp, ap = build_roster(home)[0].pid, build_roster(away)[0].pid

    conn = sm._db()
    conn.execute("INSERT INTO seasons (division, gender, seed, current_week,"
                 " total_weeks, phase) VALUES ('D1','men',1,1,10,'regular')")
    sid = conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]

    # HOME won the line on court, but HOME is the one who retires -> home loses it.
    rec = {"lines": [{"slot": "S1", "completed": True, "home_won": True,
                      "home_pid": hp, "away_pid": ap}],
           "home_points": 1, "away_points": 0}
    orig_r, orig_s = injuries.roll_retirement, injuries.retiring_side
    injuries.roll_retirement, injuries.retiring_side = (lambda: True), (lambda: True)
    try:
        n = sm._mark_retirements(conn, sid, rec, home.school, away.school, progs, 1, "t")
    finally:
        injuries.roll_retirement, injuries.retiring_side = orig_r, orig_s
    conn.commit()

    ln = rec["lines"][0]
    assert n == 1 and ln["retired"] is True
    assert ln["retired_pid"] == hp, "the retiring player must be the one drawn"
    assert ln["home_won"] is False, "retiring loses the line regardless of the score"
    assert (rec["home_points"], rec["away_points"]) == (0, 1), "dual points not corrected"

    hurt = conn.execute("SELECT pid, school FROM injuries WHERE season_id=?",
                        (sid,)).fetchall()
    conn.close()
    assert [r["pid"] for r in hurt] == [hp]
    assert hurt[0]["school"] == home.school


def test_retiring_side_is_a_coin_flip_not_the_loser():
    injuries.set_enabled(True)
    injuries.seed_for_testing(21)
    n = 20_000
    home = sum(1 for _ in range(n) if injuries.retiring_side())
    assert 0.45 < home / n < 0.55, "the retiring side is biased"
