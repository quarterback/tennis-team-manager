"""Portal page-size + slate filtering: the ?per= parser, the shared q filter, and
the batch-apply endpoints' form conventions."""
import os
import tempfile

os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-portalpaging.db"))

from app.web.pagination import per_page_arg, paginate, DEFAULT_PER_PAGE
from app.web.state import _portal_q_filter


def test_per_page_arg_parses_sizes():
    assert per_page_arg(None) == DEFAULT_PER_PAGE
    assert per_page_arg("") == DEFAULT_PER_PAGE
    assert per_page_arg("junk") == DEFAULT_PER_PAGE
    assert per_page_arg("100") == 100
    assert per_page_arg(25, default=40) == 25
    # 0 / 'all' mean "show everything" (capped far above any real slate)
    assert per_page_arg("0") == 100_000
    assert per_page_arg("all") == 100_000
    assert per_page_arg("-5") == 100_000
    # absurd sizes are capped
    assert per_page_arg("999999999") == 100_000


def test_per_page_flows_through_paginate():
    rows = list(range(120))
    pg = paginate(rows, 1, per_page_arg("all"))
    assert pg.items == rows and pg.pages == 1
    pg = paginate(rows, 2, per_page_arg("100"))
    assert pg.items == rows[100:] and pg.pages == 2


def test_portal_q_filter_matches_name_and_schools():
    rows = [
        {"name": "Ana Server", "src_school": "Bay State", "dest_school": "Hill College"},
        {"name": "Bo Netman", "src_school": "River Tech", "dest_school": "Bay State"},
        {"name": "Cy Volley", "src_school": "Plains U", "dest_school": "Coast A&M"},
    ]
    assert _portal_q_filter(rows, "") == rows
    assert _portal_q_filter(rows, "  ") == rows
    # name match, case-insensitive
    assert [r["name"] for r in _portal_q_filter(rows, "ana")] == ["Ana Server"]
    # school match hits BOTH src and dest
    assert [r["name"] for r in _portal_q_filter(rows, "bay state")] == ["Ana Server", "Bo Netman"]
    assert _portal_q_filter(rows, "nowhere") == []


def test_portal_apply_routes_safe_without_world(tmp_path):
    """The batch-apply endpoints no-op (redirect back) when no world exists, and
    accept the dest_<pid>/cur_<pid>/drop_<pid> convention without erroring."""
    import app.seasonmode as sm
    import app.world as world
    prev_sm, prev_w, prev_ready = sm.DB_PATH, world.WORLD_DB, world._schema_ready_for
    sm.DB_PATH = world.WORLD_DB = str(tmp_path / "p.db")
    world._schema_ready_for = None
    try:
        from app.web.server import create_app
        c = create_app().test_client()
        for path in ("/fall-portal/apply", "/preseason-portal/apply"):
            r = c.post(path, data={"page": "2", "per": "100", "q": "bay",
                                   "dest_px1": "Hill College", "cur_px1": "Bay State",
                                   "drop_px2": "men"})
            assert r.status_code == 302
            # the redirect keeps the view (page / page size / search) intact
            assert "page=2" in r.headers["Location"]
            assert "per=100" in r.headers["Location"]
            assert "q=bay" in r.headers["Location"]
    finally:
        sm.DB_PATH, world.WORLD_DB, world._schema_ready_for = prev_sm, prev_w, prev_ready
