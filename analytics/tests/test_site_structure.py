"""Data-bearing coverage for the sidecar's structure: a synthetic multi-class
season goes through the GAME's own export builder, gets ingested and rendered,
and the assertions read the HTML — the same lesson as the game's own JHSAA
suite (an empty-state route test cannot see a page)."""
from __future__ import annotations

import json
import zipfile

import pytest

from fixture_season import build_season


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    from app.research_export import build_jhsaa

    from ptc_analytics import ingest, render

    tmp = tmp_path_factory.mktemp("sidecar")
    files = build_jhsaa(2028, "girls", season=build_season())
    zpath = tmp / "export.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        for name, blob in files.items():
            zf.writestr(name, blob)

    ingest.DATA_DIR = tmp / "data"
    render.DATA = tmp / "data"
    render.SITE = tmp / "site"
    ingest.ingest_zip(zpath)
    render.build_site(ingest.all_bundles())
    return tmp / "site"


def read(site, rel):
    p = site / rel
    assert p.exists(), f"missing page: {rel}"
    return p.read_text()


SCOPE = "jhsaa-2028-girls-all"


def test_exported_duals_carry_dates_and_both_venues(site):
    # the synthetic season stamps a date per dual; the sidecar renders it on
    # the schedule ("Mar 2"-style labels), and a double round robin must show
    # BOTH venues on one card — the old page listed every dual as "Home"
    # because export-file order clustered a team's home copies first.
    html = read(site, f"teams/{SCOPE}__halbrook-9a-team2-girls.html")
    assert ">vs<" in html and ">at<" in html
    assert "Mar " in html or "Apr " in html


def test_team_schedule_is_sectioned_like_the_game(site):
    html = read(site, f"teams/{SCOPE}__halbrook-9a-team1-girls.html")
    assert "League play" in html
    assert "Invitationals" in html
    assert "State championship" in html
    assert "DIST" in html and "INVITE" in html and "STATE" in html
    # no raw phase strings on the card
    assert ">regular<" not in html


def test_team_page_carries_rank_and_standing_context(site):
    html = read(site, f"teams/{SCOPE}__halbrook-9a-team1-girls.html")
    assert "No. 1" in html                      # class rank
    assert "of 8 in 9A" in html                 # class size
    assert "Halbrook Basin District" in html
    assert "Season analytics" in html           # the FM-style stats panel
    # roster shows singles/doubles season records, not just names
    assert "Singles" in html and "Doubles" in html


def test_scores_render_winner_first(site):
    # Team2 lost the invitational 0-7: its card must show "7–0" with an L
    # marker, never "0–7" (a scoreline is written from the winner's side).
    html = read(site, f"teams/{SCOPE}__halbrook-9a-team4-girls.html")
    assert "0–7" not in html
    assert "7–0" in html


def test_season_dashboard_is_class_first_and_ranked_on_power(site):
    html = read(site, f"seasons/{SCOPE}.html")
    # class + district structure on every row
    assert 'data-class="9A"' in html and 'data-class="5A"' in html
    assert 'data-district="Halbrook Basin District"' in html
    # the fixture makes Halbrook Team3 better by TOSS than Team2 despite a
    # worse record: class rank must follow the archived power (the game's own
    # ranking basis), so Team3 outranks Team2.
    t3 = html.index("Halbrook 9A Team3")
    t2 = html.index("Halbrook 9A Team2")
    assert t3 < t2, "rankings must order on archived power, not win pct"
    # district standings panels exist per (class, district)
    assert html.count('class="pt-panel pt-district"') == 4
    # tabs, not a stack
    assert 'data-tab="standings"' in html and 'data-tab="leaders"' in html


def test_district_standings_order_on_archived_place(site):
    html = read(site, f"seasons/{SCOPE}.html")
    start = html.index('data-district="Gold Valley League"')
    panel = html[start:start + 4000]
    first_team = panel.index("Gold 5A Team1")
    last_team = panel.index("Gold 5A Team4")
    assert first_team < last_team


def test_storylines_are_archived_not_rendered(site):
    assert not (site / "metrics" / "storylines.html").exists()
    archived = json.loads((site.parent / "data" / "storylines.json").read_text())
    assert isinstance(archived, list)
    idx = read(site, "metrics/index.html")
    assert "storylines.html" not in idx


def test_stat_center_is_one_scoped_grid(site):
    html = read(site, "metrics/teams.html")
    for old in ("shape.html", "format-lift.html", "resume.html", "depth.html", "predictive.html"):
        assert not (site / "metrics" / old).exists()
    # identity + scoping attributes on every row
    assert 'data-scope="jhsaa-2028-girls-all"' in html
    assert 'data-class="9A"' in html and 'data-league="Ashbury Metro League"' in html
    # switchable views over one table
    for view in ("shape", "format", "resume", "depth", "pred"):
        assert f'data-view="{view}"' in html
    # nothing renders until a season is picked
    assert "Pick a season" in html


def test_nav_has_no_flat_leaderboards(site):
    html = read(site, "index.html")
    assert "seasons/" in html
    assert "leaderboards/" not in html
    assert not (site / "leaderboards").exists()


def test_leaders_are_capped_per_class_and_carry_their_district(site):
    html = read(site, f"seasons/{SCOPE}.html")
    pane = html[html.index('data-tabpane="leaders"'):html.index('data-tabpane="awards"')]
    # per-classification cap, never a statewide slice: a smaller class's
    # qualifiers must survive even when the top of the statewide list is all
    # one class — both classes appear among leader rows.
    assert 'data-class="9A"' in pane and 'data-class="5A"' in pane
    # every leader row carries its team's district so the district picker
    # filters this tab too (an empty data-district opts a row out).
    assert 'data-district="Gold Valley League"' in pane
    assert 'data-district=""' not in pane


def test_every_archived_program_row_carries_class_and_district(site):
    html = read(site, f"seasons/{SCOPE}.html")
    # 16 programs, one rankings row each, every one classed and districted
    assert html.count("data-class=") >= 16


def test_a_season_with_a_jv_slate_exports_and_ingests_unchanged(tmp_path):
    """‼️ THE SIDECAR IS VARSITY-ONLY AND MUST STAY THAT WAY (owner rule 2026-08).

    JV duals live in `season["jv"]`, a collection the exporter never iterates, so a
    JV slate must change nothing in the zip. This pins that: the same season exported
    with and without a JV block produces byte-identical tables, and ingest still
    works. If JV is ever wanted here, `duals.csv` needs a `level` column FIRST —
    `aggregate` DERIVES each phase's dual shape by counting lines, and JV's elastic
    shapes at phase="regular" would corrupt the varsity shape rather than add a
    section."""
    import zipfile
    from app.research_export import build_jhsaa
    from ptc_analytics import ingest
    from fixture_season import build_season

    plain = build_jhsaa(2028, "girls", season=build_season())

    # A JV slate hung off the same season, shaped like jhsaa.play_jv_dual writes it.
    season = build_season()
    a, b = list(season["teams"].values())[:2]

    class _JV:
        def __init__(self, team):
            self.school, self.schedule = team.school, []
    ja, jb = _JV(a), _JV(b)
    for side, other, home in ((ja, jb, True), (jb, ja, False)):
        side.schedule.append({
            "opp": other.school.name, "home": home, "phase": "regular",
            "pf": 4.0, "pa": 3.0, "won": home, "tied": False, "district": True,
            "level": "jv", "shape": "3S/2D", "played": ["JV Kid"],
            "lines": [{"slot": "S1", "home": ["JV Kid"], "away": ["Other Kid"],
                       "score": "6-1, 6-2", "home_won": True}]})
    season["jv"] = {ja.school.name: ja, jb.school.name: jb}

    withjv = build_jhsaa(2028, "girls", season=season)

    assert set(withjv) == set(plain)
    for name in plain:
        if name == "manifest.json":
            continue                     # carries a `generated_at` wall clock
        assert withjv[name] == plain[name], f"{name} changed when a JV slate existed"
    a_m, b_m = (json.loads(x["manifest.json"]) for x in (plain, withjv))
    a_m.pop("generated_at", None); b_m.pop("generated_at", None)
    assert a_m == b_m
    assert b"JV Kid" not in b"".join(withjv[n] for n in withjv if n.endswith(".csv"))

    zpath = tmp_path / "jv.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        for name, blob in withjv.items():
            zf.writestr(name, blob)
    assert ingest.ingest_zip(zpath)
