import app.seasonmode as sm
from app.web.server import create_app


def test_season_web_flow(tmp_path):
    sm.DB_PATH = str(tmp_path / "season.db")
    c = create_app().test_client()
    assert b"Season" in c.get("/", follow_redirects=True).data   # nav (dashboard, or onboarding if no world yet)
    assert c.get("/season?u=D1-men").status_code == 200       # creates the season
    assert c.post("/season/advance?u=D1-men").status_code in (302, 303)
    hub = c.get("/season?u=D1-men")
    assert hub.status_code == 200 and b"Power Index" in hub.data
    assert c.get("/season/standings?u=D1-men").status_code == 200
    assert c.get("/season/schedule?u=D1-men&school=Oregon").status_code == 200
