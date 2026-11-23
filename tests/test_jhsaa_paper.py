"""The paper (`app.jhsaa_paper`): the season replayed as dated editions.

Two halves. The export path runs on the 2042 boys research zip in
`analytics/archives` (a real, full-size season, no database). The in-app path
renders `/jhsaa/paper` against the real archived season `test_jhsaa_toc` plays.
"""
import datetime as dt
import json
import os

import pytest

from app import jhsaa_paper as paper

ZIP = os.path.join(os.path.dirname(__file__), "..", "analytics", "archives",
                   "play-to-clinch-jhsaa-2042-boys.zip")


@pytest.fixture(scope="module")
def season():
    return paper.load_export(ZIP)


def test_the_calendar_runs_preseason_to_closing_inside_the_window(season):
    eds = paper.editions(season, "Juniper Highlands")
    assert eds[0]["kind"] == "preseason" and eds[-1]["kind"] == "closing"
    dates = [e["date"] for e in eds]
    assert dates == sorted(dates) and len(set(dates)) == len(dates)
    first = min(d["date"] for d in season["duals"] if d["date"])
    assert eds[0]["date"] < first


def test_every_dual_lands_in_exactly_one_edition(season):
    """Each edition reports [since, date); together they cover the season once."""
    area = "Juniper Highlands"
    local = {p["name"] for p in season["programs"].values() if p["area"] == area}
    seen = []
    for e in paper.editions(season, area):
        v = paper.edition_view(season, area, e["n"])
        seen += [r["id"] for day in v["results"] for r in day["rows"]]
    played = [d["id"] for d in season["duals"] if d["date"] and {d["home"], d["away"]} & local]
    assert sorted(seen) == sorted(played)


def test_nothing_in_a_packet_is_dated_on_or_after_its_morning(season):
    area = "Juniper Highlands"
    for n in (1, 5, 20):
        pk = paper.packet(season, area, n)
        morning = pk["edition"]["date"]
        assert all(r["date"] < morning for r in pk["results_since_last_edition"])
        # the standings are the fold through that morning, not the final table
        recs = paper.records_through(season, dt.date.fromisoformat(morning))
        for t in pk["league_standings_this_morning"]:
            for row in t["rows"]:
                r = recs.get(row["school"])
                want = paper._rec(r["w"], r["l"], r["t"]) if r else "0-0"
                assert row["overall"] == want
        assert all(s["date"] >= morning for s in pk["before_the_next_edition"])


def test_the_preseason_packet_knows_last_season_not_this_one(season):
    pk = paper.packet(season, "Juniper Highlands", 0)
    assert pk["results_since_last_edition"] == []
    assert all(p["record_to_date"] == "0-0" for p in pk["programs"])
    assert any(p["last_season"] for p in pk["programs"])


def test_the_demo_editions_render(season):
    here = os.path.join(os.path.dirname(__file__), "..", "docs", "paper",
                        "2042-boys-juniper-highlands")
    stories = paper.load_stories_dir(here)
    assert stories
    html = paper.render_preview(season, "Juniper Highlands", stories)
    assert "The Juniper Highlands Courier" in html
    for pay in stories.values():
        assert pay["stories"][0]["headline"].replace("'", "&#39;") in html


def test_a_writer_reply_is_parsed_out_of_surrounding_text():
    text = 'Here it is:\n{"stories": [{"slot": "lead", "headline": "H", "body": ["x"]}], "ledger": []}'
    assert paper._parse_payload(text)["stories"][0]["headline"] == "H"


def test_the_paper_page_renders_in_the_app(season, monkeypatch):
    """The in-app route, the real template and base page, fed the real 2042
    season in place of the archive read (the shared real-season fixture in
    test_jhsaa_toc is broken on main for an unrelated reason)."""
    from app import world as wd
    from app.web.server import create_app
    monkeypatch.setattr(wd, "is_primed", lambda *a, **k: True)
    monkeypatch.setattr(wd, "prime", lambda *a, **k: None)
    monkeypatch.setattr(wd, "get_or_create", lambda *a, **k: {"id": 1, "year": 15, "seed": 0})
    monkeypatch.setattr(wd, "jhsaa_years", lambda *a, **k: [15])
    monkeypatch.setattr(paper, "load_archive", lambda *a, **k: season)
    c = create_app().test_client()
    html = c.get("/jhsaa/paper?g=boys&area=Juniper Highlands").get_data(as_text=True)
    assert "The Juniper Highlands Courier" in html and "Edition 1 of" in html
    assert "No stories have been written" in html
    html = c.get("/jhsaa/paper?g=boys&area=Juniper Highlands&ed=3").get_data(as_text=True)
    assert "Standings this morning" in html and "Big Basin League" in html
    assert "No. 1 singles:" in html
