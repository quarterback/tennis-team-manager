"""The best season is the FURTHEST RUN, not the best record (owner rule 2026-08).

The report that produced the rule: a program whose ledger held a 28-4 that lost in
the State Octofinals and a 22-7 that reached the State semifinal was shown the 28-4.
"This program's best season was a semi-finals run, not the year they won 28 and lost
in Octas." Record only breaks a tie between two runs that got equally far.

These are pure folds over ledger rows, so they need no archived season — which is
also why they can pin the ORDER exhaustively rather than spot-checking one page.
"""
from app import world


def row(year, wins, losses, **kw):
    r = {"year": year, "season_year": year, "wins": wins, "losses": losses,
         "record": f"{wins}-{losses}", "group": "7A", "district": "Three Rivers League",
         "district_title": False, "unit_wins": [], "made_state": False, "state_place": 0,
         "state_finish": "", "champion": False, "made_toc": False, "toc_place": 0,
         "toc_finish": "", "courts_won": 0, "courts_lost": 0, "poy": [], "all_state": [],
         "all_district": [], "toc_champion": False}
    r.update(kw)
    return r


def test_a_semifinal_run_beats_a_better_record_that_went_out_earlier():
    octas = row(2031, 28, 4, made_state=True, state_place=16, state_finish="Octofinalist")
    semis = row(2032, 22, 7, made_state=True, state_place=4, state_finish="Semifinalist")
    t = world.jhsaa_program_totals([semis, octas])
    assert t["best"]["season_year"] == 2032


def test_the_record_breaks_a_tie_between_equally_deep_runs():
    a = row(2031, 28, 4, made_state=True, state_place=16, state_finish="Octofinalist")
    b = row(2032, 19, 12, made_state=True, state_place=16, state_finish="Octofinalist")
    assert world.jhsaa_program_totals([a, b])["best"]["season_year"] == 2031


def test_the_tiers_run_toc_over_state_over_the_road_over_nothing():
    """One season of each kind, deliberately given a WORSE record the further it went —
    so anything that reads the record instead of the finish inverts the whole list."""
    seasons = [
        row(2040, 30, 1),                                     # no postseason at all
        row(2041, 25, 5, state_finish="Wards"),               # road, shallow
        row(2042, 20, 9, state_finish="Divisionals"),         # road, deep
        row(2043, 15, 14, made_state=True, state_place=24, state_finish="Round of 40"),
        row(2044, 12, 17, made_state=True, state_place=1, state_finish="Champion",
            champion=True),
        row(2045, 10, 20, made_state=True, state_place=1, state_finish="Champion",
            champion=True, made_toc=True, toc_place=2, toc_finish="TOC Finalist"),
    ]
    order = sorted(seasons, key=world.jhsaa_season_depth)
    assert [s["season_year"] for s in order] == [2040, 2041, 2042, 2043, 2044, 2045]
    assert world.jhsaa_program_totals(seasons)["best"]["season_year"] == 2045


def test_every_road_rung_is_ranked_and_the_names_come_from_jhsaa():
    """‼️ A rung this ladder cannot name ranks at the BOTTOM of its tier — below a
    program that lost its first Area match — so a typed copy of a renamed round would
    read as an association that stopped playing it."""
    from app import jhsaa
    ladder = world.jh_road_ladder()
    assert jhsaa.DIVISIONAL_NAME in ladder
    assert jhsaa.SEMI_CONFERENCE_NAME in ladder
    assert jhsaa.CONFERENCE_NAME in ladder
    depths = [world.jhsaa_season_depth(row(2040, 10, 10, state_finish=name))
              for name in ladder]
    assert depths == sorted(depths), "the ladder must rank shallowest to deepest"
    unknown = world.jhsaa_season_depth(row(2040, 10, 10, state_finish="Moon Round"))
    assert unknown < depths[0]


def test_road_titles_do_not_double_count_the_district_title():
    """`unit_wins` LEADS with the district name when the program won its district
    (owner rule 2027-08), and that is already its own tile."""
    seasons = [
        row(2040, 20, 5, district_title=True,
            unit_wins=["Three Rivers League", "Area VII", "Ward III"]),
        row(2041, 18, 7, unit_wins=["Area IX"]),
    ]
    t = world.jhsaa_program_totals(seasons)
    assert t["road_titles"] == 3
    assert t["district_titles"] == 1


def test_a_program_with_no_played_season_has_no_best():
    assert world.jhsaa_program_totals([row(2040, 0, 0)])["best"] is None
