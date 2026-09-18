"""The hosted Clinch Report (`app/clinch.py`): a static site rendered once, so
the manage page has to SAY when the rendered window trails the world, and the
build has to hand the sidecar a way back to the form (owner, 2026-09: after the
first build nothing linked to /clinch/manage and the report froze at that
season)."""
from app import clinch


def test_seasons_behind_counts_from_the_newest_rendered_year():
    assert clinch.seasons_behind(None, 2087) == 0
    assert clinch.seasons_behind({"years": []}, 2087) == 0
    assert clinch.seasons_behind({"years": [2084]}, 2084) == 0
    assert clinch.seasons_behind({"years": [2082, 2083, 2084]}, 2087) == 3
    assert clinch.seasons_behind({"years": [2088]}, 2087) == 0      # never negative
    # the lag reads the seasons actually RENDERED: a requested year not yet
    # played is skipped and the older cache still renders
    assert clinch.seasons_behind({"years": [2086, 2087], "rendered_years": [2086]}, 2087) == 1


def test_the_hosted_build_names_the_manage_page():
    assert clinch.MANAGE_URL == "/clinch/manage"
