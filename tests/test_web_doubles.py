import app.seasonmode as sm
from app.web.server import create_app


def test_doubles_locked_before_team_tournament(tmp_path):
    """Until the team bracket is complete, the doubles championship is locked."""
    prev = sm.DB_PATH
    sm.DB_PATH = str(tmp_path / "s.db")
    try:
        c = create_app().test_client()
        r = c.get("/doubles-championship?u=D1-men")
        assert r.status_code == 200
        assert b"No doubles championship yet" in r.data
    finally:
        sm.DB_PATH = prev


def test_doubles_championship_after_team_tournament(played_season):
    """Once the season is complete the 64-pair draw renders with a champion."""
    c = create_app().test_client()
    r = c.get("/doubles-championship?u=D1-men")
    assert r.status_code == 200
    assert b"Doubles National Champions" in r.data
    # the draw controls and a smaller field both render
    assert c.get("/doubles-championship?u=D1-men&size=16").status_code == 200
