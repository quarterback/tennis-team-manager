import app.seasonmode as sm
from app.web.server import create_app


def test_singles_locked_before_team_tournament(tmp_path):
    prev = sm.DB_PATH
    sm.DB_PATH = str(tmp_path / "s.db")
    try:
        c = create_app().test_client()
        r = c.get("/singles-championship?u=D1-men")
        assert r.status_code == 200
        assert b"No singles championship yet" in r.data
    finally:
        sm.DB_PATH = prev


def test_singles_championship_after_team_tournament(played_season):
    c = create_app().test_client()
    r = c.get("/singles-championship?u=D1-men")
    assert r.status_code == 200
    assert b"Singles National Champion" in r.data
    assert c.get("/singles-championship?u=D1-men&size=64").status_code == 200
