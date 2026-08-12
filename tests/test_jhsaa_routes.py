"""Every JHSAA route actually responds.

The TOC page shipped with `g, group, year, u = _jh_scope_args()` against a helper that
returns SIX values, so clicking the tab raised ValueError on the first line of the view.
It was never caught because the page was validated by rendering its template directly —
which exercises the view function and the template and skips the route that wires them
together, the one line that was wrong.

These call the routes. No archive is required: a JHSAA page with nothing archived must
render its empty state, not raise.
"""
import pytest

from app.web.server import create_app


@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("PTC_NO_BOOT_WARM", "1")
    return create_app().test_client()


ROUTES = [
    "/jhsaa",
    "/jhsaa?g=boys",
    "/jhsaa/toc",
    "/jhsaa/toc?g=boys",
    "/jhsaa/bracket",
    "/jhsaa/districts",
    "/jhsaa/champions",
]


@pytest.mark.parametrize("path", ROUTES)
def test_the_page_responds(client, path):
    r = client.get(path)
    assert r.status_code in (200, 302), (path, r.status_code)
