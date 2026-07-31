import random

from engine import random_player
from engine.gtt import GTTTeam, simulate_gtt_dual, LINES_TO_CLINCH

SLOTS = ["MS1", "MS2", "MS3", "WS1", "WS2", "WS3", "XD1", "XD2", "XD3"]


def _gtt_team(name, base, seed):
    rng = random.Random(seed)
    men = [random_player(rng, f"{name}M{i}", base=base) for i in range(3)]
    women = [random_player(rng, f"{name}W{i}", base=base) for i in range(3)]
    return GTTTeam(name=name, men=men, women=women)


def test_gtt_clinch_at_5():
    home = _gtt_team("H", 0.60, 1)
    away = _gtt_team("A", 0.55, 2)
    res = simulate_gtt_dual(home, away, seed=10)
    assert res.home_points + res.away_points <= 9
    assert max(res.home_points, res.away_points) == LINES_TO_CLINCH   # clinch at 5
    assert res.winner in (0, 1)
    # winner is the side that reached the clinch
    assert (res.winner == 0) == (res.home_points > res.away_points)


def test_gtt_nine_lines_three_disciplines():
    res = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=4)
    assert [l.slot for l in res.lines] == SLOTS


def test_gtt_completed_lines_equal_points():
    # Lopsided -> likely early clinch; completed lines == points actually played.
    res = simulate_gtt_dual(_gtt_team("H", 0.80, 1), _gtt_team("A", 0.40, 2), seed=3)
    completed = sum(1 for l in res.lines if l.completed)
    assert completed == res.home_points + res.away_points
    # every unfinished line carries no result
    assert all(l.result is None for l in res.lines if not l.completed)
    assert all(l.result is not None for l in res.lines if l.completed)


def test_gtt_deterministic():
    r1 = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    r2 = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    assert (r1.home_points, r1.away_points) == (r2.home_points, r2.away_points)
    assert [l.slot for l in r1.lines] == [l.slot for l in r2.lines]
    assert [l.home_won for l in r1.lines] == [l.home_won for l in r2.lines]


def test_gtt_fast_fidelity_runs_and_clinches():
    res = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2),
                            seed=7, fidelity="fast")
    assert max(res.home_points, res.away_points) == LINES_TO_CLINCH
    assert res.winner in (0, 1)


def test_lines_are_fast4_sets():
    """Every GTT line is a single Fast4 set: first to 4 games, tiebreak at 3-3,
    so no completed line exceeds 4 games and the only one-game margin is 4-3."""
    res = simulate_gtt_dual(_gtt_team("H", 0.62, 1), _gtt_team("A", 0.55, 2), seed=4)
    for ln in res.lines:
        if not ln.completed:
            continue
        sets = ln.result.set_scores
        assert len(sets) == 1, "a GTT line is a single set"
        hi, lo = max(sets[0]), min(sets[0])
        assert hi == 4, f"Fast4 set won at 4 games, got {sets[0]}"
        assert lo <= 3 and (hi - lo >= 2 or (hi, lo) == (4, 3))


def test_form_keeps_determinism():
    a = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    b = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    assert [l.home_won for l in a.lines] == [l.home_won for l in b.lines]


def test_pros_develop_toward_their_peak():
    """A pro used to be FROZEN at their college exit level from 22 until 29, then
    only decline — no prime years at all. They now develop toward the ceiling they
    graduated with, tapering to zero at PEAK_AGE, mirroring decline past it."""
    import copy
    import random
    from app.development import generate_prospect, RICH_ATTRS
    import app.gtt_seasonmode as gs

    def raw(x):
        return sum(x.current[a] for a in RICH_ATTRS)

    grad = generate_prospect(random.Random(9), "Riser", "US", gender="male", talent=62)
    for _ in range(4):                       # four college years -> a real graduate
        grad.develop_year()
    assert grad.ceiling_overall() > grad.current_overall(), "fixture needs headroom"

    def prime(p):
        c = copy.deepcopy(p)
        for age in range(gs.ENTRY_AGE + 1, gs.PEAK_AGE + 1):
            taper = max(0.0, min(1.0, (gs.PEAK_AGE - age) / (gs.PEAK_AGE - gs.ENTRY_AGE)))
            c.develop(scale=gs.PRO_GROWTH * taper)
        return c

    peaked = prime(grad)
    assert raw(peaked) > raw(grad), "a pro must improve across their twenties"
    assert peaked.current_overall() > grad.current_overall(), "growth must be visible in OVR"
    assert peaked.current_overall() <= grad.ceiling_overall(), "never past the ceiling"

    # growth is spent by the peak: the last step before PEAK_AGE adds nothing
    at_peak = copy.deepcopy(peaked)
    at_peak.develop(scale=gs.PRO_GROWTH * 0.0)
    assert raw(at_peak) == raw(peaked)


def _graduate(seed=9, talent=62):
    import random
    from app.development import generate_prospect
    g = generate_prospect(random.Random(seed), "P", "US", gender="male", talent=talent)
    for _ in range(4):
        g.develop_year()
    return g


def _club_with_style(gs, lid, archetype, strength=0.8):
    """Pin a club's staff to a known archetype — club style now comes from a real
    coach row, so a test says which coach rather than scanning for a lucky id."""
    conn = gs._db()
    fid = conn.execute("SELECT id FROM gtt_franchises WHERE league_id=? ORDER BY id",
                       (lid,)).fetchall()[0]["id"]
    conn.execute("DELETE FROM gtt_coaches WHERE league_id=? AND fid=?", (lid, fid))
    conn.execute("INSERT INTO gtt_coaches (league_id, pid, name, archetype, strength,"
                 " fid, origin, joined_year) VALUES (?,?,?,?,?,?,?,0)",
                 (lid, "test-pid", "Test Coach", archetype, strength, fid, "retired-pro"))
    conn.commit(); conn.close()
    return fid


def test_club_coaching_shapes_players_by_archetype(tmp_path):
    """Clubs build the attributes their ARCHETYPE teaches, weighted — so two clubs
    turn the same free agent into genuinely different players."""
    import copy
    gs, lid = _coach_league(tmp_path, name="Shape", teams=4)
    grad = _graduate()

    def career(archetype, years=6):
        fid = _club_with_style(gs, lid, archetype)
        p = copy.deepcopy(grad)
        for _ in range(years):
            assert gs.apply_club_coaching(p, lid, fid, 0)
        return p

    net = career("net-poacher")
    base = career("topspin-grinder")
    assert net.current["poaching"] > grad.current["poaching"]
    assert net.current["net_play"] > grad.current["net_play"]
    assert base.current["net_play"] == grad.current["net_play"]      # grinders don't volley
    assert base.current["shot_tolerance"] > grad.current["shot_tolerance"]
    assert net.current["shot_tolerance"] == grad.current["shot_tolerance"]
    # weighted, not flat: the archetype's 1.0 attrs move more than its 0.6 ones
    assert (net.current["poaching"] - grad.current["poaching"]) > \
           (net.current["overhead"] - grad.current["overhead"])
    # and it reaches the ENGINE, not just the sheet
    assert net.engine_player().rich["poaching"] > grad.engine_player().rich["poaching"]


def test_club_coaching_scales_with_staff_quality_and_coachability(tmp_path):
    import copy
    gs, lid = _coach_league(tmp_path, name="Quality", teams=4)
    grad = _graduate()

    def gain(strength, p):
        fid = _club_with_style(gs, lid, "net-poacher", strength=strength)
        q = copy.deepcopy(p)
        gs.apply_club_coaching(q, lid, fid, 0)
        return q.current["poaching"] - p.current["poaching"]

    assert gain(0.9, grad) > gain(0.3, grad), "a better staff must teach more"

    dull, keen = copy.deepcopy(grad), copy.deepcopy(grad)
    dull.current["coachability"] = 20.0
    keen.current["coachability"] = 80.0
    assert gain(0.9, keen) > gain(0.9, dull)


def test_club_coaching_is_additive_not_capped_by_potential(tmp_path):
    """Additive to CURRENT ability, not gated on remaining potential — a finished
    veteran can still be reshaped by the right club."""
    import copy
    gs, lid = _coach_league(tmp_path, name="Additive", teams=4)
    p = _graduate()
    for _ in range(12):                       # run growth right out
        p.develop_year()
    fid = _club_with_style(gs, lid, "net-poacher")
    before = p.current["poaching"]
    q = copy.deepcopy(p)
    gs.apply_club_coaching(q, lid, fid, 0)
    assert q.current["poaching"] > before


def _coach_league(tmp_path, name="Staff", teams=6, years=0):
    import app.gtt_seasonmode as gs
    import app.injuries as inj
    gs.DB_PATH = str(tmp_path / "c.db")
    gs._schema_ready_for = None
    inj.set_enabled(False)
    lid = gs.create_league(name, seed=3, n_teams=teams)
    for _ in range(years):
        gs.advance_seasons(lid, 1, fidelity="fast")
    return gs, lid


def test_coach_pool_carries_a_surplus(tmp_path):
    """More coaches than jobs, so a club has a real choice of styles — the same
    reason the player free-agent pool needs a surplus."""
    gs, lid = _coach_league(tmp_path, teams=6)
    conn = gs._db()
    total = conn.execute("SELECT COUNT(*) c FROM gtt_coaches WHERE league_id=?",
                         (lid,)).fetchone()["c"]
    hired = conn.execute("SELECT COUNT(*) c FROM gtt_coaches WHERE league_id=? AND fid IS NOT NULL",
                         (lid,)).fetchone()["c"]
    conn.close()
    assert hired == 6, "every club must have a staff"
    assert total > hired, "no surplus — the pool is exactly one staff per job"


def test_retired_players_take_over_the_coaching_jobs(tmp_path):
    """The point of the pro league: you keep seeing people after they stop playing.
    The year-zero synthetic staffs must give way to real finished careers."""
    gs, lid = _coach_league(tmp_path, teams=6, years=12)
    conn = gs._db()
    rows = conn.execute("SELECT pid, origin FROM gtt_coaches WHERE league_id=?"
                        " AND fid IS NOT NULL", (lid,)).fetchall()
    ex_players = [r for r in rows if r["pid"]]
    conn.close()
    assert len(ex_players) >= 4, f"only {len(ex_players)}/6 jobs went to ex-players"
    assert all(r["origin"] != "synthetic" for r in ex_players)


def test_coach_pool_does_not_grow_without_bound(tmp_path):
    """Unemployed staffs leave the game, so the pool stays a shortlist."""
    gs, lid = _coach_league(tmp_path, teams=6, years=10)
    conn = gs._db()
    total = conn.execute("SELECT COUNT(*) c FROM gtt_coaches WHERE league_id=?",
                         (lid,)).fetchone()["c"]
    conn.close()
    assert total < 6 + gs.COACH_SURPLUS + 6 * gs.COACH_POOL_YEARS, f"pool ballooned to {total}"


def test_a_coach_teaches_what_they_themselves_were(tmp_path):
    """A club's identity traces to a person: their coaching archetype is inferred
    from how they played, so the eras become causal rather than a fixed cycle."""
    import random
    from app.development import generate_prospect
    from app import playstyles
    gs, lid = _coach_league(tmp_path, teams=4)

    volleyer = generate_prospect(random.Random(5), "V", "US", gender="male", talent=60)
    for a in ("poaching", "net_play", "volley_touch", "doubles_chemistry"):
        volleyer.current[a] = 78.0
    grinder = generate_prospect(random.Random(6), "G", "US", gender="male", talent=60)
    for a in ("shot_tolerance", "groundstroke_consistency", "rally_patience", "stamina"):
        grinder.current[a] = 78.0

    assert playstyles.best_fit(volleyer.current) == "net-poacher"
    assert playstyles.best_fit(grinder.current) == "topspin-grinder"


def test_coach_rows_are_cleared_with_their_league(tmp_path):
    gs, lid = _coach_league(tmp_path, teams=4)

    def rows():
        conn = gs._db()
        n = conn.execute("SELECT COUNT(*) c FROM gtt_coaches").fetchone()["c"]
        conn.close()
        return n

    assert rows() > 0
    gs.delete_league(lid)
    assert rows() == 0, "deleting a league left its coaches behind"
    gs.create_league("Again", seed=4, n_teams=4)
    gs.reset()
    assert rows() == 0, "the whole-tour reset left coaches behind"


def test_unsigned_free_agents_retire(tmp_path):
    """A free agent nobody signs is finished — the drain that stops free agency
    being a limbo nobody ever leaves. Tested on the rule directly: going through a
    whole season would let the waiver wire re-sign them, which is correct behaviour
    and not what this asserts."""
    gs, lid = _coach_league(tmp_path, name="Drain", teams=4)
    conn = gs._db()
    pid = conn.execute("SELECT pid FROM gtt_players WHERE league_id=? LIMIT 1",
                       (lid,)).fetchone()["pid"]
    conn.execute("UPDATE gtt_players SET fid=NULL, status='active', fa_years=0"
                 " WHERE league_id=? AND pid=?", (lid, pid))
    conn.commit()

    def status_and_clock():
        r = conn.execute("SELECT status, fa_years FROM gtt_players"
                         " WHERE league_id=? AND pid=?", (lid, pid)).fetchone()
        return r["status"], r["fa_years"]

    for season in range(1, gs.FA_SEASONS_BEFORE_RETIRE + 1):
        retirees = gs.retire_unsigned(conn, lid)
        st, clock = status_and_clock()
        assert clock == season
        if season < gs.FA_SEASONS_BEFORE_RETIRE:
            assert st == "active", "retired too early"
    st, _ = status_and_clock()
    assert st == "retired", "an unsigned free agent never left the pool"
    assert any(r[0] == pid for r in retirees), "should surface as a coaching candidate"
    conn.close()


def test_signing_resets_the_unsigned_clock(tmp_path):
    gs, lid = _coach_league(tmp_path, name="Reset", teams=4)
    conn = gs._db()
    pid = conn.execute("SELECT pid FROM gtt_players WHERE league_id=? LIMIT 1",
                       (lid,)).fetchone()["pid"]
    fid = conn.execute("SELECT id FROM gtt_franchises WHERE league_id=? LIMIT 1",
                       (lid,)).fetchone()["id"]
    conn.execute("UPDATE gtt_players SET fid=NULL, fa_years=0 WHERE league_id=? AND pid=?",
                 (lid, pid))
    conn.commit()
    gs.retire_unsigned(conn, lid)                       # one season out
    conn.execute("UPDATE gtt_players SET fid=? WHERE league_id=? AND pid=?", (fid, lid, pid))
    conn.commit()
    gs.retire_unsigned(conn, lid)                       # signed -> clock resets
    r = conn.execute("SELECT status, fa_years FROM gtt_players WHERE league_id=? AND pid=?",
                     (lid, pid)).fetchone()
    conn.close()
    assert r["fa_years"] == 0 and r["status"] == "active"


def test_synthetic_staffs_are_gone_after_the_first_season(tmp_path):
    """The year-zero staffs are scaffolding. From year one every job belongs to a
    real finished career."""
    gs, lid = _coach_league(tmp_path, name="Scaffold", teams=4, years=3)
    conn = gs._db()
    synth = conn.execute("SELECT COUNT(*) c FROM gtt_coaches WHERE league_id=?"
                         " AND origin='synthetic'", (lid,)).fetchone()["c"]
    real = conn.execute("SELECT COUNT(*) c FROM gtt_coaches WHERE league_id=?"
                        " AND fid IS NOT NULL AND pid IS NOT NULL", (lid,)).fetchone()["c"]
    conn.close()
    assert synth == 0, "synthetic seed staffs survived their first season"
    assert real > 0, "no real ex-player took a job"


def test_draft_leaves_a_standing_free_agent_pool(tmp_path):
    """The wire used to drain to zero by year 8 because the intake filled roster
    HOLES and nothing more. The draft now leaves a surplus every year, sized per
    club, so add/drop still exists in a mature league."""
    gs, lid = _coach_league(tmp_path, name="Wire", teams=8, years=6)
    conn = gs._db()
    free = conn.execute("SELECT COUNT(*) c FROM gtt_players WHERE league_id=?"
                        " AND status='active' AND fid IS NULL", (lid,)).fetchone()["c"]
    conn.close()
    assert free >= 8, f"only {free} free agents left — the wire drained again"


def test_rosters_lock_except_for_season_ending_injuries(tmp_path):
    """No week-to-week churn: a club may only sign mid-season to cover someone out
    for the year."""
    import app.gtt_seasonmode as gs2
    gs, lid = _coach_league(tmp_path, name="Lock", teams=6)
    conn = gs._db()
    fid = conn.execute("SELECT id FROM gtt_franchises WHERE league_id=? LIMIT 1",
                       (lid,)).fetchone()["id"]
    roster = gs._active(conn, lid, fid)
    assert roster
    assert not gs._season_ending_out(conn, lid, 0, fid, roster), "no injury, no opening"
    conn.execute("INSERT INTO gtt_injuries (scope, pid, team, name, week, tag, total,"
                 " duals_remaining, season_ending) VALUES (?,?,?,?,?,?,?,?,1)",
                 (gs._inj_scope(lid, 0), roster[0]["pid"], str(fid), "x", 1, "t", 0, 0))
    conn.commit()
    assert gs._season_ending_out(conn, lid, 0, fid, roster), "a year-ending injury must open a slot"
    conn.close()


def test_lower_divisions_feed_the_surplus_not_the_starting_lineups(tmp_path):
    """D1 fills rosters; D2-D4 stock the wire. The two draws use different shares."""
    import app.gtt_seasonmode as gs2
    assert gs2.GRAD_D1_SHARE > gs2.GRAD_D1_SHARE_SURPLUS, \
        "the surplus must lean on the lower divisions more than the roster draw does"
    assert gs2.GRAD_D1_SHARE_SURPLUS < 0.5


def test_retired_players_are_pruned_but_never_the_notable_ones(tmp_path):
    """The archive keeps careers worth following — Hall of Famers and coaches are
    permanent — and drops only the anonymous long-gone tail."""
    gs, lid = _coach_league(tmp_path, name="Prune", teams=4)
    conn = gs._db()
    rows = conn.execute("SELECT pid FROM gtt_players WHERE league_id=? LIMIT 3",
                        (lid,)).fetchall()
    nobody, famous, coach_pid = [r["pid"] for r in rows]
    for pid in (nobody, famous, coach_pid):
        conn.execute("UPDATE gtt_players SET status='retired', fid=NULL, joined_year=0,"
                     " seasons=1 WHERE league_id=? AND pid=?", (lid, pid))
    conn.execute("INSERT INTO gtt_hof (league_id, pid, name, gender, year_enshrined)"
                 " VALUES (?,?,?,?,?)", (lid, famous, "Famous", "m", 2))
    conn.execute("INSERT INTO gtt_coaches (league_id, pid, name, archetype, strength,"
                 " fid, origin, joined_year) VALUES (?,?,?,?,?,?,?,?)",
                 (lid, coach_pid, "Coach", "all-court", 0.6, None, "retired-pro", 2))
    conn.commit()

    gs.prune_retired(conn, lid, gs.RETIRED_KEEP_YEARS + 5)
    left = {r["pid"] for r in conn.execute(
        "SELECT pid FROM gtt_players WHERE league_id=?", (lid,)).fetchall()}
    conn.close()
    assert nobody not in left, "the anonymous tail was never pruned"
    assert famous in left, "a Hall of Famer was pruned"
    assert coach_pid in left, "a coach was pruned"


def test_alumni_lists_everyone_past_college_by_state(tmp_path):
    gs, lid = _coach_league(tmp_path, name="Alumni", teams=4, years=3)
    everyone = gs.alumni(lid, "all", limit=100000)
    assert everyone
    states = {p["state"] for p in everyone}
    assert {"playing", "retired"} <= states
    for s in ("playing", "free-agent", "coaching", "retired", "hall-of-fame"):
        assert all(p["state"] == s for p in gs.alumni(lid, s, limit=100000))
    assert sum(len(gs.alumni(lid, s, limit=100000)) for s in
               ("playing", "free-agent", "coaching", "retired", "hall-of-fame")) == len(everyone)


def test_gtt_short_club_plays_instead_of_crashing():
    """Same class of crash as the college dual (engine.dual._court): the nine-line
    card reads fixed lineup indices, and `gtt_seasonmode._lineup` returns fewer than
    three when a club is genuinely that thin. A short club plays its last body in the
    slot it can't fill rather than IndexError-ing the page."""
    full = _gtt_team("H", 0.60, 1)
    for n in (2, 1):
        thin = GTTTeam(name="Thin", men=list(full.men[:n]), women=list(full.women[:n]))
        res = simulate_gtt_dual(thin, _gtt_team("A", 0.55, 2), seed=10)   # must not raise
        assert [l.slot for l in res.lines] == SLOTS
        assert res.winner in (0, 1)
        assert simulate_gtt_dual(_gtt_team("A", 0.55, 2), thin, seed=10).winner in (0, 1)
