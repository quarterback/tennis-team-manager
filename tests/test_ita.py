"""ITA Kickoff Weekend + National Team Indoor Championship — the season opener."""
import hashlib
import json

import pytest

import app.ita as ita
import app.seasonmode as sm


@pytest.fixture
def db(tmp_path):
    sm.DB_PATH = str(tmp_path / "season.db")
    sm._forced_cache.clear()
    yield


# --- pure draw logic --------------------------------------------------------

def test_kickoff_sites_partition_the_top_field():
    ranked = [f"T{i:02d}" for i in range(80)]
    sites = ita.kickoff_sites(ranked)
    assert len(sites) == ita.KICKOFF_SITES
    assert all(len(s) == ita.TEAMS_PER_SITE for s in sites)
    flat = [t for s in sites for t in s]
    assert sorted(flat) == sorted(ranked[:ita.KICKOFF_FIELD])   # exactly the top 60, no dupes
    # each site is ordered best-first, so site[0] is the host (top seed)
    rank = {t: i for i, t in enumerate(ranked)}
    for s in sites:
        assert s == sorted(s, key=lambda t: rank[t])


def test_site_pairs_seed_one_v_four():
    site = ["A", "B", "C", "D"]                       # best→worst
    assert ita.site_pairs(site) == [("A", "D"), ("B", "C")]


def test_indoor_field_is_winners_plus_autobid_host():
    ranked = [f"T{i:02d}" for i in range(80)]
    winners = [f"T{i:02d}" for i in range(1, 30, 2)]  # 15 winners, none of them T00
    field = ita.indoor_field(winners, ranked)
    assert len(field) == ita.INDOOR_FIELD            # 16
    assert "T00" in field                            # top-ranked auto-bid host added
    assert field == sorted(field, key=lambda t: ranked.index(t))  # seeded by rank


# --- season-mode wiring -----------------------------------------------------

def test_d1_season_opens_with_the_ita_phase(db):
    sid = sm.create_season("D1", "men", seed=2026)
    s = sm.load_season(sid)
    assert s["phase"] == "ita_kickoff"               # D1 opens on the ITA, not regular
    # the regular slate is pushed back behind the ITA weeks
    reg_weeks = [d["week"] for d in sm.team_schedule(sid, sm.load_division("D1", "men").programs[0].school)
                 if d["round"] == "REG"]
    assert not reg_weeks or min(reg_weeks) > ita.lead_weeks("D1")


def test_d2_d3_open_on_a_top8_indoor_with_no_kickoff(db):
    for div in ("D2", "D3"):
        sid = sm.create_season(div, "women", seed=5)
        assert sm.load_season(sid)["phase"] == "ita_indoor"   # no Kickoff — straight to the Indoor
        while sm.load_season(sid)["phase"].startswith("ita"):
            sm.advance(sid)
        conn = sm._db()
        kick = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='ITAK'",
                            (sid,)).fetchone()["c"]
        indoor = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='ITAI'"
                             " AND status='final'", (sid,)).fetchone()["c"]
        conn.close()
        assert kick == 0                                      # no Kickoff sites for D2/D3
        assert indoor == ita.SMALL_INDOOR_FIELD - 1           # 8-team single-elim = 7 duals
        assert sm.indoor_champion(sid)


def test_ita_runs_then_hands_off_to_the_fall_portal(db):
    sid = sm.create_season("D1", "women", seed=11)
    guard = 0
    while sm.load_season(sid)["phase"].startswith("ita") and guard < 20:
        sm.advance(sid); guard += 1
    s = sm.load_season(sid)
    # The opener now hands off to the fall-portal boundary, with the regular-season
    # first week already pre-set. A standalone advance passes straight through it to
    # the regular season (the world driver instead holds there to run the portal).
    assert s["phase"] == "fall_portal"
    assert s["current_week"] == ita.lead_weeks("D1") + 1
    assert sm.advance(sid)["phase"] == "regular"
    # a single Indoor champion was crowned, and it's a real program
    champ = sm.indoor_champion(sid)
    assert champ in {p.school for p in sm.load_division("D1", "women").programs}
    # the Kickoff produced exactly one winner per site → the Indoor field
    conn = sm._db()
    finals = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='ITAK'"
                          " AND round_no=2 AND status='final'", (sid,)).fetchone()["c"]
    indoor = conn.execute("SELECT COUNT(*) c FROM duals WHERE season_id=? AND round='ITAI'"
                          " AND status='final'", (sid,)).fetchone()["c"]
    conn.close()
    assert finals == ita.KICKOFF_SITES               # 15 site champions
    assert indoor == ita.INDOOR_FIELD - 1            # 16-team single-elim = 15 duals


def test_ita_feeds_the_record_and_the_power_index(db):
    sid = sm.create_season("D1", "men", seed=3)
    while sm.load_season(sid)["phase"].startswith("ita"):
        sm.advance(sid)
    # overall standings reflect ITA results even before any regular dual is played
    played = sum(row["ow"] + row["ol"] for table in sm.standings(sid).values() for row in table)
    assert played > 0
    # the ITA opener also feeds the live Power Index — an early read on who's good —
    # so teams that played carry a rating before the regular season starts...
    pi = sm.power_index(sid)
    assert pi
    # ...but only the ITA participants, not the whole division, have results yet
    assert len(pi) < len(sm.load_division("D1", "men").programs)


def test_ita_web_pages_render(tmp_path):
    """The season hub and the /season/ita bracket page render through the ITA opener."""
    from app.web.server import create_app
    import app.seasonmode as smod
    smod.DB_PATH = str(tmp_path / "season.db")
    c = create_app().test_client()
    assert c.get("/season?u=D1-men").status_code == 200       # creates the D1 season
    assert c.get("/season/ita?u=D1-men").status_code == 200   # pre-draw note renders
    sid = smod.get_or_create("D1", "men", seed=2026)
    for _ in range(6):                                        # run the whole ITA opener
        smod.advance(sid)                                     # standalone: no world driver
    page = c.get("/season/ita?u=D1-men")
    assert page.status_code == 200 and b"National Team Indoor" in page.data
    assert c.get("/season?u=D1-men").status_code == 200       # hub renders post-ITA


def test_ita_is_deterministic(db, tmp_path):
    def run(path):
        sm.DB_PATH = path
        sm._forced_cache.clear()
        sid = sm.create_season("D1", "men", seed=2026)
        while sm.load_season(sid)["phase"].startswith("ita"):
            sm.advance(sid)
        conn = sm._db()
        rows = conn.execute("SELECT round, round_no, bpos, home, away, winner FROM duals"
                            " WHERE season_id=? AND round IN ('ITAK','ITAI') ORDER BY round, round_no, bpos",
                            (sid,)).fetchall()
        conn.close()
        return hashlib.md5(json.dumps([tuple(r) for r in rows]).encode()).hexdigest()

    assert run(str(tmp_path / "a.db")) == run(str(tmp_path / "b.db"))
