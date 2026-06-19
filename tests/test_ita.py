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
    assert not reg_weeks or min(reg_weeks) > ita.ITA_LEAD_WEEKS


def test_non_d1_skips_the_ita(db):
    sid = sm.create_season("D2", "women", seed=5)
    assert sm.load_season(sid)["phase"] == "regular"


def test_ita_runs_then_hands_off_to_the_regular_season(db):
    sid = sm.create_season("D1", "women", seed=11)
    guard = 0
    while sm.load_season(sid)["phase"].startswith("ita") and guard < 20:
        sm.advance(sid); guard += 1
    s = sm.load_season(sid)
    assert s["phase"] == "regular"
    assert s["current_week"] == ita.ITA_LEAD_WEEKS + 1
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


def test_ita_counts_toward_the_record_but_not_the_power_index(db):
    sid = sm.create_season("D1", "men", seed=3)
    while sm.load_season(sid)["phase"].startswith("ita"):
        sm.advance(sid)
    # overall standings reflect ITA results even before any regular dual is played
    played = sum(row["ow"] + row["ol"] for table in sm.standings(sid).values() for row in table)
    assert played > 0
    # ...but the regular-season Power Index is still empty (ITA excluded, like CT/NCAA)
    assert sm.power_index(sid) == {}


def test_ita_web_pages_render(tmp_path):
    """The season hub and the /season/ita bracket page render through the ITA opener."""
    from app.web.server import create_app
    import app.seasonmode as smod
    smod.DB_PATH = str(tmp_path / "season.db")
    c = create_app().test_client()
    assert c.get("/season?u=D1-men").status_code == 200       # creates the D1 season
    assert c.get("/season/ita?u=D1-men").status_code == 200   # pre-draw note renders
    for _ in range(6):                                        # run the whole ITA opener
        c.post("/season/advance?u=D1-men")
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
