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
