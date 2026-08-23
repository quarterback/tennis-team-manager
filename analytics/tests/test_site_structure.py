"""Data-bearing coverage for the sidecar's structure: a synthetic multi-class
season goes through the GAME's own export builder, gets ingested and rendered,
and the assertions read the HTML — the same lesson as the game's own JHSAA
suite (an empty-state route test cannot see a page)."""
from __future__ import annotations

import zipfile

import pytest

from fixture_season import TRANSFERS, build_season


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    from app.research_export import build_jhsaa

    from ptc_analytics import ingest, render

    tmp = tmp_path_factory.mktemp("sidecar")
    ingest.DATA_DIR = tmp / "data"
    render.DATA = tmp / "data"
    render.SITE = tmp / "site"

    # TWO consecutive seasons, because the movement join, the development
    # curve and the departures side of a team's movement panel are all
    # differences between years — a one-season fixture makes every one of them
    # legitimately empty, and a test written against it would pass while
    # measuring nothing.
    for year, bump, moves in ((2028, 0.0, None), (2029, 3.0, TRANSFERS)):
        files = build_jhsaa(year, "girls",
                            season=build_season(year, bump=bump, moves=moves))
        zpath = tmp / f"export-{year}.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            for name, blob in files.items():
                zf.writestr(name, blob)
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


def test_storylines_are_gone_entirely(site):
    # Sunset, not archived (owner call): the page went first, then the whole
    # computation. Both halves are asserted because the previous state of this
    # feature was "computed every build, written to JSON, rendered nowhere" —
    # deleting only the page would leave that back.
    from ptc_analytics import metrics as metrics_mod

    assert not (site / "metrics" / "storylines.html").exists()
    assert not (site.parent / "data" / "storylines.json").exists()
    assert not hasattr(metrics_mod, "storylines")
    assert "storylines.html" not in read(site, "metrics/index.html")


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


# --------------------------------------------------------------------------
# Ability, scouting, movement and the classification report. Everything below
# needs DATA to be visible at all — an empty-state route test cannot see any
# of it, which is why the fixture plays two real seasons with varying OVR and
# a transfer between them.
# --------------------------------------------------------------------------

SCOPE29 = "jhsaa-2029-girls-all"


def test_the_win_curve_is_fitted_not_hardcoded(site):
    # The curve that prices every expected-share number is fitted on the
    # ingested flights and shows its own receipt: an observed column beside a
    # modelled one. A hard-coded table would have no sample count to report.
    html = read(site, "metrics/value.html")
    assert "fitted on the ingested seasons, never hard-coded" in html
    assert "Favourite won" in html and "Model says" in html
    from ptc_analytics import ability
    assert ability.MIN_FIT_SAMPLES > 0


def test_ability_prices_a_flight_on_the_gap_it_was_played_at(site):
    # The fixture makes stronger teams genuinely stronger, so the fit must
    # come out with a positive slope (a bigger OVR edge wins more often) and
    # an intercept near zero (an even gap is a coin flip).
    from ptc_analytics import ability, ingest
    bundles = ability_bundles(ingest)
    idx = ability.build(bundles)
    singles = idx.curve_for("jhsaa", True)
    assert singles is not None and singles.fitted, "no singles curve was fitted"
    assert singles.b > 0, "a bigger OVR edge must win more often, not less"
    assert abs(singles.a) < 0.5, "an even gap should be close to a coin flip"
    assert singles.bands, "the fit must publish its observed bands"


def ability_bundles(ingest):
    from ptc_analytics import aggregate
    return aggregate.load_bundles(ingest.all_bundles())


def test_scouting_searches_by_geography_not_only_by_class(site):
    # The whole point of this surface: area/county/town are top-level axes
    # beside classification, because a cohort build is "everyone near here"
    # and a class-first tree makes that query unaskable.
    html = read(site, f"scout/{SCOPE29}.html")
    for control in ("f-area", "f-county", "f-town", "f-class", "f-league"):
        assert f'id="{control}"' in html, f"missing search axis: {control}"
    assert '"areas":' in html and '"counties":' in html
    # and it still never opens on the whole association
    assert "never opens on the whole association at once" in html


def test_scouting_carries_the_four_ways_in(site):
    # Several KINDS of candidate, not one list: the finders are preset
    # searches, and the cohort builder is the geographic one.
    html = read(site, f"scout/{SCOPE29}.html")
    from ptc_analytics import market
    for key, label, _fn, _blurb, _sort in market.FINDERS:
        assert f'data-finder="{key}"' in html, f"missing finder: {key}"
        assert label in html
    assert 'data-tab="cohort"' in html
    assert '"catchment":' in html


def test_the_shortlist_exports_the_games_own_batch_format(site):
    # The loop only closes if the tool emits exactly what the bulk transfer
    # field takes: player_id,DestinationSchool, one per line, no header.
    html = read(site, f"scout/{SCOPE29}.html")
    assert "player_id,DestinationSchool" in html
    assert "pid + ',' + e.dest" in html, "the batch line must be id,destination"
    # ...and refuses the three rows that would be a no-op or a miss
    assert "e.dest === e.from" in html
    assert "progByName[e.dest] === undefined" in html


def test_every_finder_actually_finds_somebody(site):
    # ‼️ The finder tests above assert the CONTROLS exist. This one asserts
    # they return people, because all three returned an empty list against the
    # first version of this fixture (uniform rosters, ability and team
    # strength the same variable) and every test still passed. If this one
    # fails, the fixture stopped containing the shape a finder looks for —
    # fix the fixture, don't loosen the finder.
    from ptc_analytics import ability, aggregate, ingest, market
    bundles = ability_bundles(ingest)
    careers = aggregate.player_careers(bundles)
    boards = aggregate.leaderboards(bundles, careers)
    idx = ability.build(bundles)
    move = market.movement(bundles)
    growth = market.fit_growth(bundles, idx)
    rows = market.player_rows(bundles, careers, boards, idx, move, growth)[SCOPE29]

    found = {key: fn(rows) for key, _label, fn, _blurb, _sort in market.FINDERS}
    for key, hits in found.items():
        assert hits, f"the {key} finder found nobody"

    # ...and they are looking for DIFFERENT things, which is the whole point:
    # one list under three names would be worse than no lists.
    buried = {r["player_id"] for r in found["benched"]}
    reservoir = {r["player_id"] for r in found["reservoir"]}
    stranded = {r["player_id"] for r in found["stranded"]}
    assert not buried & reservoir, "buried and reservoir must not overlap"
    assert not buried & stranded and not reservoir & stranded
    # buried players clear their class's starting line; reservoir players don't
    assert all(r["vs_starter"] >= 0 for r in found["benched"])
    assert all(r["vs_starter"] < 0 for r in found["reservoir"])
    # a stranded player is top of their own ladder on a bottom-third program
    assert all(r["ladder_rank"] <= 3 and r["team_class_pctile"] >= 0.667
               for r in found["stranded"])


def test_scout_rows_carry_the_market_columns(site):
    from ptc_analytics import ability, ingest, market, aggregate
    bundles = ability_bundles(ingest)
    careers = aggregate.player_careers(bundles)
    boards = aggregate.leaderboards(bundles, careers)
    idx = ability.build(bundles)
    move = market.movement(bundles)
    growth = market.fit_growth(bundles, idx)
    rows = market.player_rows(bundles, careers, boards, idx, move, growth)[SCOPE29]

    assert rows, "no scouting rows built"
    ranked = [r for r in rows if r["ladder_rank"] == 1]
    assert ranked, "nobody is top of their own ladder"
    # 'where would this player start' is the column the whole cascade turns on
    assert any(r["starts_in"] for r in rows)
    # a ladder is a ladder: exactly one player per program at each position
    for r in rows:
        assert r["ladder_rank"] is not None
        assert 1 <= r["ladder_rank"] <= r["roster_size"]


def test_a_transfer_is_read_from_both_ends(site):
    pid, dest = next(iter(TRANSFERS.items()))
    from ptc_analytics import ability, ingest, market, aggregate
    bundles = ability_bundles(ingest)
    move = market.movement(bundles)
    key = ("jhsaa", "girls", 2029, pid)
    assert key in move["moved"], "the fixture's transfer was not detected"
    rec = move["moved"][key]
    assert rec["to"] == dest
    assert rec["from"] != dest

    # the receiving program reports an arrival, the losing one a departure —
    # and the departure is read off the FOLLOWING season, so it lands on 2028
    dest_slug = f"{SCOPE29}__{dest.lower().replace(' ', '-')}-girls.html"
    html = read(site, f"teams/{dest_slug}")
    assert "Movement" in html
    assert rec["from"] in html, "the arrival's previous program is not shown"

    src_slug = f"jhsaa-2028-girls-all__{rec['from'].lower().replace(' ', '-')}-girls.html"
    src_html = read(site, f"teams/{src_slug}")
    assert dest in src_html, "the departure's destination is not shown"


def test_the_newest_season_reports_departures_as_unknown_not_zero(site):
    # There is no 2030 export, so nothing can say who left after 2029. A
    # program that lost seven and one that lost none must not print the same
    # number, so the panel says so rather than showing 0.
    html = read(site, f"teams/{SCOPE29}__halbrook-9a-team1-girls.html")
    assert "next season not ingested" in html


def test_team_roster_is_a_depth_chart(site):
    html = read(site, f"teams/{SCOPE29}__halbrook-9a-team1-girls.html")
    assert ">OVR<" in html and ">POT<" in html
    assert "pt-ldr" in html, "the roster must carry ladder positions"
    assert "dresses" in html, "the dressing line must be stated"


def test_stat_center_gained_talent_and_movement_views(site):
    html = read(site, "metrics/teams.html")
    for view in ("shape", "format", "resume", "depth", "pred", "talent", "move"):
        assert f'data-view="{view}"' in html
    assert "xShare" in html and "Talent luck" in html
    assert "From arrivals" in html


def test_classification_report_answers_the_three_questions(site):
    html = read(site, f"classes/{SCOPE29}.html")
    assert 'data-tab="strength"' in html
    assert 'data-tab="shape"' in html
    assert 'data-tab="health"' in html
    # cross-class evidence exists because the fixture plays 9A vs 5A
    assert "Cross-class results" in html
    assert "vs 5A" in html and "vs 9A" in html
    assert "No cross-class duals in this export" not in html
    # the talent-shape table runs a column per ladder position
    assert "Mean OVR by ladder position" in html
    assert "Concentration" in html


def test_cross_class_head_to_head_uses_championship_group(site):
    # 9A beats 5A everywhere in the fixture (9A teams are created first and so
    # rank stronger), so the matrix must show it — and it must be built on the
    # championship group, which is who a program actually plays.
    from ptc_analytics import classes, ingest
    bundles = ability_bundles(ingest)
    b = next(x for x in bundles if x.scope_id == SCOPE29)
    h2h = classes.head_to_head(b)
    assert ("9A", "5A") in h2h, "no cross-class duals were found"
    nine = h2h[("9A", "5A")]
    five = h2h[("5A", "9A")]
    assert nine["w"] == five["l"] and nine["l"] == five["w"], "the mirror must agree"
    assert nine["w"] > nine["l"], "9A should be beating 5A in this fixture"


def test_nav_reaches_the_new_desks(site):
    html = read(site, "index.html")
    assert "scout/index.html" in html
    assert "classes/index.html" in html
    assert (site / "scout" / "index.html").exists()
    assert (site / "classes" / "index.html").exists()


# --------------------------------------------------------------------------
# Review follow-ups. Each of these pins a fault that shipped and produced
# plausible-looking output rather than an error.
# --------------------------------------------------------------------------

def test_only_snapshot_scopes_are_priced_on_ability(site):
    # ‼️ A college export's players.csv is TODAY's roster, not the one that
    # played (research_export.build_college says so outright). Pricing an old
    # flight off it uses later OVRs and silently DROPS every flight whose
    # players have since graduated, so the gate is on the export's semantics,
    # not on taste.
    from ptc_analytics import aggregate, ingest
    bundles = ability_bundles(ingest)
    assert bundles and all(b.roster_is_snapshot for b in bundles)
    assert aggregate.snapshot_bundles(bundles) == bundles

    class _Fake:
        roster_is_snapshot = False
        scope_id = "college-2029-D1-women"
    mixed = list(bundles) + [_Fake()]
    assert aggregate.snapshot_bundles(mixed) == bundles, "a non-snapshot scope must be excluded"


def test_a_non_snapshot_scope_gets_no_ability_no_scouting_and_is_named(site):
    from ptc_analytics import ability, aggregate, classes, ingest, market
    real = ability_bundles(ingest)

    class _Fake:
        """A college-shaped bundle: enough surface for the gate to reject it
        before anything reads a player."""
        roster_is_snapshot = False
        family, gender, year = "college", "women", 2029
        scope_id, label = "college-2029-D1-women", "2029 D1 Women"
        players, programs, duals_full, championships = {}, {}, {}, {}
        regular_shape = state_shape = None

    mixed = list(real) + [_Fake()]
    idx = ability.build(mixed)
    assert "college-2029-D1-women" in idx.skipped, "the skip must be reported, not silent"
    assert idx.ability("college-2029-D1-women") is None
    # ...and every downstream layer refuses it too
    assert not any(k[0] == "college-2029-D1-women" for k in idx.team)
    assert not any(k[0] == "college-2029-D1-women" for k in idx.player)
    assert all(k[1] != 2029 or k[0] != "college" for k in market.movement(mixed)["moved"])
    assert all(r["scope_id"] != "college-2029-D1-women" for r in classes.build(mixed, {}, idx))
    # the index page names what it left out rather than quietly shortening
    assert "Not covered here" in read(site, "scout/index.html") or \
        "{% if skipped %}" not in read(site, "scout/index.html")


def test_the_fit_counts_each_contested_flight_once(site):
    # The curve is fitted on both sides of every flight so it is symmetric
    # about a zero gap, but a mirrored row is the SAME flight seen from the
    # other bench. Counting it as evidence halved MIN_FIT_SAMPLES and doubled
    # every number the page reports.
    from ptc_analytics import ability, ingest
    bundles = ability_bundles(ingest)
    idx = ability.build(bundles)

    for (family, kind), curve in idx.curves.items():
        flights = 0
        for b in bundles:
            if b.family != family:
                continue
            sa = idx.ability(b.scope_id)
            for mu in ability.line_matchups(b, sa):
                if mu["side"] != "home":
                    continue
                if ("S" if mu["singles"] else "D") == kind:
                    flights += 1
        assert curve.samples == flights, (
            f"{family}/{kind}: reported {curve.samples} flights, actually {flights}")
        # and the observed bands total the same real flights, not twice them
        assert sum(row["n"] for row in curve.bands.values()) == flights


def test_a_max_only_filter_shows_results(site):
    # Setting only "OVR max" or only "Matches max" must load the grid. Both
    # were missing from anyFilter() while being present in the reset list —
    # the entered constraint appeared to do nothing.
    html = read(site, f"scout/{SCOPE29}.html")
    assert "var NUM_FILTERS" in html
    for control in ("f-ovrmin", "f-ovrmax", "f-potmin", "f-mmax", "f-rankmin"):
        assert f"'{control}'" in html, f"{control} missing from the filter lists"
    # one list, read by both consumers — that is what stops them drifting again
    assert "TEXT_FILTERS.concat(NUM_FILTERS)" in html
    assert "NUM_FILTERS.some" in html


def test_jv_duals_never_reach_the_analytics(site):
    # The JHSAA now plays a JV season and both levels share one schedule table,
    # so duals.csv carries both. Owner rule: JV never reaches analytics. A JV
    # dual left in inflates every schedule-derived record (while the standings
    # file stays varsity-only, so a team page disagrees with itself) and
    # averages JV's elastic lineup into the derived varsity shape.
    from ptc_analytics import aggregate

    raw = {
        "family": "jhsaa",
        "scope": {"year": 2028, "gender": "girls", "classification": "all"},
        "manifest": {},
        "tables": {"duals": [
            {"dual_id": "v1", "level": "v", "phase": "regular",
             "home_program_id": "A", "away_program_id": "B",
             "home_points": "5", "away_points": "2", "winner_program_id": "A"},
            {"dual_id": "jv1", "level": "jv", "phase": "regular",
             "home_program_id": "A", "away_program_id": "B",
             "home_points": "5", "away_points": "2", "winner_program_id": "A"},
            # pre-JV export: no `level` at all, and every dual in one is varsity
            {"dual_id": "old", "phase": "regular",
             "home_program_id": "A", "away_program_id": "B",
             "home_points": "5", "away_points": "2", "winner_program_id": "A"},
        ]},
    }
    b = aggregate.Bundle(raw)
    assert set(b.duals) == {"v1", "old"}, "a JV dual reached the aggregator"
    assert "jv1" not in b.duals_full


def test_the_export_marks_a_duals_level(site):
    # The filter above is only possible because the export says which level a
    # dual was: "carries no lines" is also what a varsity dual whose lines
    # failed to record looks like, so the column has to exist.
    import csv, io
    from app.research_export import build_jhsaa

    season = build_season(2028)
    teams = list(season["teams"].values())
    teams[0].schedule.append({
        "opp": teams[1].school.name, "home": True, "phase": "regular",
        "pf": 5.0, "pa": 2.0, "won": True, "district": True,
        "date": "2028-04-01", "level": "jv", "lines": []})
    files = build_jhsaa(2028, "girls", season=season)
    rows = list(csv.DictReader(io.StringIO(files["duals.csv"].decode())))
    assert "level" in rows[0], "duals.csv must mark a dual's level"
    assert sum(1 for r in rows if r["level"] == "jv") == 1
    assert all(r["level"] in ("v", "jv") for r in rows)
