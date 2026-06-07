import pytest

from app.web.server import create_app
from app.web.state import get_recruits, national_rankings, team_roster


@pytest.fixture
def client():
    return create_app().test_client()


def test_nav_has_recruiting(client):
    assert b"Recruiting" in client.get("/").data


def test_recruiting_board(client):
    r = client.get("/recruiting?u=D1-men&grad_year=2026")
    assert r.status_code == 200
    assert b"Blue Chip" in r.data and b"class of 2026" in r.data


def test_recruiting_scopes(client):
    assert client.get("/recruiting?u=D1-men&scope=state&state=California").status_code == 200
    assert client.get("/recruiting?u=D1-women&scope=intl").status_code == 200


def test_recruit_profile_and_404(client):
    pid = national_rankings(get_recruits("male", 2026))[0].pid
    r = client.get(f"/recruit/{pid}?u=D1-men&grad_year=2026")
    assert r.status_code == 200
    assert b"Scouting" in r.data and b"projection" in r.data
    assert client.get("/recruit/NOPE?u=D1-men").status_code == 404


def test_recruits_deterministic(client):
    a = [p.pid for p in get_recruits("male", 2026).recruits]
    b = [p.pid for p in get_recruits("male", 2026).recruits]
    assert a == b and len(set(a)) == len(a)        # cached + stable, unique pids


def test_team_and_player_pages(client, tmp_path):
    import app.seasonmode as sm
    sm.DB_PATH = str(tmp_path / "season.db")          # player card reads season-mode data
    assert client.get("/teams?u=D1-men&school=Oregon").status_code == 200
    pid = team_roster("D1", "men", "Oregon")[0]["p"].pid
    r = client.get(f"/player/{pid}?u=D1-men&school=Oregon")
    assert r.status_code == 200
    assert b"match by match" in r.data and b"Bio" in r.data
