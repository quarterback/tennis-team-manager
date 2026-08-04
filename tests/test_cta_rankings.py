"""CTA individual rankings — national / regional / newcomer scopes.

The CTA (College Tennis Association) is our in-game analogue of the real ITA.
Regions are the nine US census divisions plus an "Outlying" bucket for the
non-contiguous / non-state places (AK, HI, DC, PR, USVI, Guam — owner rule
2027-08; BC covers Simon Fraser). Newcomer is a D1 singles-only freshman board.
"""
import json
import os

from app.scout_intel import US_REGIONS, US_REGION_ORDER


# --- Region map integrity ---------------------------------------------------

def test_census_division_map_covers_every_school_state():
    """Every state a program actually sits in must map to a region — otherwise
    that program silently vanishes from the regional boards."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "data", "ncaa", "locations.json"), encoding="utf-8") as fh:
        schools = json.load(fh)["schools"]
    states = {v["state"] for v in schools.values()}
    unmapped = states - set(US_REGIONS)
    assert not unmapped, f"school states with no CTA region: {unmapped}"


def test_census_division_membership():
    # The 50 states + DC all mapped.
    assert len([st for st in US_REGIONS if len(st) == 2]) >= 51
    # Spot-check the census divisions (the owner's chosen cut — Texas has no
    # region of its own, California isn't lumped with the PNW-and-everything).
    assert US_REGIONS["TX"] == "West South Central"
    assert US_REGIONS["NC"] == "South Atlantic"
    assert US_REGIONS["CA"] == "Pacific"
    assert US_REGIONS["OR"] == "Pacific"
    assert US_REGIONS["IL"] == "East North Central"
    assert US_REGIONS["MN"] == "West North Central"
    assert US_REGIONS["TN"] == "East South Central"
    assert US_REGIONS["NY"] == "Mid-Atlantic"
    assert US_REGIONS["MA"] == "New England"
    assert US_REGIONS["CO"] == "Mountain"
    # The Outlying bucket: non-contiguous states, the capital, territories, BC.
    for code in ("AK", "HI", "DC", "PR", "VI", "GU", "BC"):
        assert US_REGIONS[code] == "Outlying", code
    # Order list and map values agree exactly.
    assert set(US_REGIONS.values()) == set(US_REGION_ORDER)
    assert US_REGION_ORDER[-1] == "Outlying"


# --- Ranking rows (played season) -------------------------------------------

def test_regional_player_rows_group_by_school_region(played_season):
    from app.web.state import regional_player_rows
    groups = regional_player_rows("D1", "men", "singles", min_matches=3)
    assert groups, "a fully-played D1 season must yield regional singles boards"
    order = [reg for reg, _ in groups]
    assert order == [r for r in US_REGION_ORDER if r in order]  # canonical order
    for reg, players in groups:
        assert 1 <= len(players) <= 10
        for r in players:
            assert r["region"] == reg
            assert r["rk"] >= 1                      # national rank carried over
        # within a region the national order is preserved
        rks = [r["rk"] for r in players]
        assert rks == sorted(rks)


def test_regional_doubles_rows(played_season):
    from app.web.state import regional_player_rows
    groups = regional_player_rows("D1", "men", "doubles", min_matches=3)
    assert groups
    for reg, pairs in groups:
        for r in pairs:
            assert r["region"] == reg
            assert r["p1"] and r["p2"]


def test_newcomer_rows_are_freshman_only(played_season):
    from app.web.state import newcomer_ranking_rows
    from app.world import _base_class
    rows = newcomer_ranking_rows("D1", "men", min_matches=3)
    assert rows, "a full D1 season should surface at least one ranked freshman"
    assert len(rows) <= 50
    for r in rows:
        assert _base_class(r["class"]) == "Fr"
    # re-ranked among themselves but national order preserved
    rks = [r["rk"] for r in rows]
    assert rks == sorted(rks)


# --- Web routes -------------------------------------------------------------

def test_rankings_scopes_render(played_season):
    from app.web.server import create_app
    c = create_app().test_client()
    r = c.get("/rankings?u=D1-men&view=singles&scope=regional")
    assert r.status_code == 200
    assert b"CTA Regional Rankings" in r.data
    r = c.get("/rankings?u=D1-men&view=doubles&scope=regional")
    assert r.status_code == 200
    assert b"CTA Regional Rankings" in r.data
    r = c.get("/rankings?u=D1-men&view=singles&scope=newcomer")
    assert r.status_code == 200
    assert b"CTA Newcomer Rankings" in r.data
    # legacy team-regional URL still serves the team region cards
    r = c.get("/rankings?u=D1-men&view=regional")
    assert r.status_code == 200
    assert b"CTA Regional Rankings" in r.data


def test_newcomer_scope_falls_back_outside_d1_singles(played_season):
    """Newcomer is D1 + singles only: a doubles request quietly serves national."""
    from app.web.server import create_app
    c = create_app().test_client()
    r = c.get("/rankings?u=D1-men&view=doubles&scope=newcomer")
    assert r.status_code == 200
    assert b"CTA Newcomer Rankings" not in r.data
    assert b"PAIR" in r.data


# --- Final rankings archive (persisted at CT finish) -------------------------

def test_final_rankings_stamped_when_conference_tournaments_end(played_season):
    """Advancing through the conference tournaments stamps the season's final
    boards into the year-over-year archive — teams, singles and doubles, capped
    at the page's field sizes, rows carrying region + class so the archived
    board replays every scope."""
    from app import rankings_archive as ra
    assert 2026 in ra.years("D1", "men")
    teams = ra.board(2026, "D1", "men", "teams")
    singles = ra.board(2026, "D1", "men", "singles")
    doubles = ra.board(2026, "D1", "men", "doubles")
    assert teams and singles and doubles
    assert len(teams) <= ra.TEAM_CAP[False]
    assert len(singles) <= ra.SINGLES_CAP[False]
    assert [r["rk"] for r in teams] == list(range(1, len(teams) + 1))
    pts = [r["points"] for r in singles]
    assert pts == sorted(pts, reverse=True)
    for r in singles[:10]:
        assert r["pid"] and r["name"] and r["region"] in US_REGION_ORDER
        assert r["cls"]
    for r in doubles[:5]:
        assert r["pid"] and r["pid2"] and r["name2"]


def test_stamp_is_once_and_final(played_season):
    """A later re-stamp is a NO-OP: the archived board is the one that stood
    when the conference tournaments ended — the points corpus keeps growing
    through the NCAAs, and the final board must not chase it."""
    from app import rankings_archive as ra
    import app.seasonmode as sm
    sid = sm.get_or_create("D1", "men", seed=2026)
    before = ra.board(2026, "D1", "men", "singles")
    assert before
    assert ra.stamp_final_rankings(sid) == 0          # already archived → no-op
    after = ra.board(2026, "D1", "men", "singles")
    assert [(r["pid"], r["points"]) for r in after] == [(r["pid"], r["points"]) for r in before]


def test_player_final_ranks(played_season):
    from app import rankings_archive as ra
    top = ra.board(2026, "D1", "men", "singles")[0]
    mine = ra.player_final_ranks(top["pid"])
    assert any(fr["board"] == "singles" and fr["rk"] == 1 and fr["year"] == 2026
               for fr in mine)


def test_archived_rankings_route(played_season):
    """A past season serves the frozen final board through the same page, with
    regional and newcomer scopes derived from the stored region/class."""
    from app import rankings_archive as ra
    from app.web.server import create_app
    conn = ra._conn()
    try:
        base = dict(year=2001, season_no=1, division="D1", gender="men",
                    conf_abbr="AC", region="Pacific", w=20, l=2)
        conn.execute("DELETE FROM cta_rankings WHERE year=2001")
        conn.executemany(
            "INSERT INTO cta_rankings (year, season_no, division, gender, board, rk,"
            " school, conf_abbr, region, pid, name, pid2, name2, cls, w, l, points)"
            " VALUES (:year, :season_no, :division, :gender, :board, :rk, :school,"
            " :conf_abbr, :region, :pid, :name, :pid2, :name2, :cls, :w, :l, :points)",
            [{**base, "board": "singles", "rk": 1, "school": "Stanford",
              "pid": "t-arch-1", "name": "Archie Vault", "pid2": None, "name2": None,
              "cls": "Fr", "points": 88.0},
             {**base, "board": "singles", "rk": 2, "school": "Stanford",
              "pid": "t-arch-2", "name": "Sen Ior", "pid2": None, "name2": None,
              "cls": "Sr", "points": 80.0},
             {**base, "board": "teams", "rk": 1, "school": "Stanford",
              "pid": None, "name": None, "pid2": None, "name2": None,
              "cls": None, "points": 70.0}])
        conn.commit()
    finally:
        conn.close()
    try:
        c = create_app().test_client()
        r = c.get("/rankings?u=D1-men&season=2001&view=singles")
        assert r.status_code == 200
        assert b"Final 2001 CTA Rankings" in r.data and b"Archie Vault" in r.data
        r = c.get("/rankings?u=D1-men&season=2001&view=singles&scope=newcomer")
        assert b"Archie Vault" in r.data and b"Sen Ior" not in r.data
        r = c.get("/rankings?u=D1-men&season=2001&view=singles&scope=regional")
        assert b"Pacific" in r.data and b"Archie Vault" in r.data
        r = c.get("/rankings?u=D1-men&season=2001&view=teams")
        assert b"Stanford" in r.data
    finally:
        conn = ra._conn()
        conn.execute("DELETE FROM cta_rankings WHERE year=2001")
        conn.commit()
        conn.close()


# --- Recruiting class archive ------------------------------------------------

def test_signing_class_archive(tmp_path):
    """world_signing keeps every year: a past year reads back as the archived
    class, and the tracker enriches it with how each signee turned out (Active /
    Grad / Left) from the persisted world store."""
    import json as _json
    import app.world as world
    from app.ncaa import load_division, build_roster
    from app.web.state import signing_tracker

    prev = world.WORLD_DB
    world.WORLD_DB = str(tmp_path / "w.db")
    try:
        world.init_schema()
        conn = world._db()
        conn.execute("INSERT INTO world (seed, year, week, salt) VALUES (4242, 2, 0, 's')")
        wid = conn.execute("SELECT id FROM world WHERE seed=4242").fetchone()["id"]
        roster = build_roster(load_division("D1", "men").programs[0])
        a, b, c = roster[0], roster[1], roster[2]
        for p, school in ((a, "Stanford"), (b, "Stanford"), (c, "Baylor")):
            conn.execute(
                "INSERT INTO world_signing (world_id, year, gender, school, pid, data)"
                " VALUES (?, 0, 'men', ?, ?, ?)",
                (wid, school, p.pid, _json.dumps(world.prospect_to_dict(p))))
        # a: still rostered THIS year (transferred to Duke); b: graduated; c: gone
        conn.execute("INSERT INTO world_roster (world_id, year, division, gender, school, pid, data)"
                     " VALUES (?, 2, 'D1', 'men', 'Duke', ?, ?)",
                     (wid, a.pid, _json.dumps(world.prospect_to_dict(a))))
        conn.execute("INSERT INTO world_graduates (world_id, year, division, gender, pid, str, ovr, data)"
                     " VALUES (?, 1, 'D1', 'men', ?, 44.0, 60.0, ?)",
                     (wid, b.pid, _json.dumps(world.prospect_to_dict(b))))
        conn.execute("INSERT INTO world_roster (world_id, year, division, gender, school, pid, data)"
                     " VALUES (?, 1, 'D1', 'men', 'Baylor', ?, ?)",
                     (wid, c.pid, _json.dumps(world.prospect_to_dict(c))))
        conn.commit()
        conn.close()

        assert world.signing_years(seed=4242) == [0]
        klass = world.signings(seed=4242, year=0).get("men", {})
        assert set(klass) == {"Stanford", "Baylor"}
        assert world.signings(seed=4242).get("men", {}) == {}     # current year: none

        trk = signing_tracker("men", None, seed=4242, year=0)
        assert trk["archive"] and trk["year"] == 0
        assert trk["total_signed"] == 3
        by_pid = {r["p"].pid: r for r in trk["commitments"]}
        assert by_pid[a.pid]["out"]["status"] == "Active"
        assert by_pid[a.pid]["out"]["school"] == "Duke"           # transfer visible
        assert by_pid[b.pid]["out"]["status"] == "Grad"
        assert by_pid[b.pid]["out"]["str_now"] == 44.0
        assert by_pid[c.pid]["out"]["status"] == "Left"
        assert by_pid[a.pid]["str_sign"] > 0

        live = signing_tracker("men", None, seed=4242)            # current cycle: empty
        assert not live["archive"] and live["total_signed"] == 0
        assert {y["val"] for y in live["years"]} == {0, 2}
    finally:
        world.WORLD_DB = prev
