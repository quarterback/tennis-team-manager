from app.web.server import create_app
from app.web.awards import season_awards


def test_awards_page_renders():
    c = create_app().test_client()
    r = c.get("/awards?u=D1-men")
    assert r.status_code == 200
    assert b"All-American" in r.data and b"All-Conference" in r.data


def test_season_awards_structure(played_season):
    aw = season_awards("D1", "men")
    # National All-American tiers exist and are PERFORMANCE-ordered (honors are
    # earned on court — wins x win% x position x a mild team factor — not by rating).
    assert aw["all_american"], "expected at least one All-American tier"
    first = aw["all_american"][0]["players"]
    assert first, "First Team should not be empty"
    perfs = [p["perf"] for p in first]
    assert perfs == sorted(perfs, reverse=True)
    # Every honored player is reverse-indexed for player cards.
    for p in first:
        assert any("All-American" in h for h in aw["by_pid"][p["pid"]])
    # All-Conference is grouped per conference with First/Second teams.
    assert aw["all_conference"]
    conf, teams = aw["all_conference"][0]
    assert teams and teams[0]["players"]
