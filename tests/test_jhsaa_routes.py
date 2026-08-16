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


# --- every classification is reachable from every surface --------------------------

CLASS_SURFACES = ["/jhsaa", "/jhsaa/rankings", "/jhsaa/honors", "/jhsaa/bracket",
                  "/jhsaa/districts", "/jhsaa/toc", "/jhsaa/champions"]


@pytest.fixture(scope="module")
def warm_client():
    """A client that always gets the PAGE, never the warming loader.

    Once a world row exists, `_prime_world` answers a cold request with the
    warming shell — which carries no scope rail, so a class-coverage assertion
    against it fails for a reason that has nothing to do with the ladder (and
    only once another test in the module has warmed the world, which is what
    made it order-dependent). No JHSAA surface reads a college program, so
    reporting warm is honest here — the same stub `test_jhsaa_toc` uses."""
    import os
    from app import world as wd
    os.environ.setdefault("PTC_NO_BOOT_WARM", "1")
    real_primed, real_prime = wd.is_primed, wd.prime
    wd.is_primed = lambda *a, **k: True
    wd.prime = lambda *a, **k: None
    try:
        yield create_app().test_client()
    finally:
        wd.is_primed, wd.prime = real_primed, real_prime


@pytest.mark.parametrize("path", CLASS_SURFACES)
def test_every_surface_lists_every_classification(warm_client, path):
    """‼️ THE CLASS SWITCHER IS THE ONLY WAY INTO A CLASSIFICATION, so a surface that
    lists fewer than `GROUPS` makes part of the association unreachable — you can
    see 7A's season and simply cannot get to 9A's. Every one of these pages carries
    the same scope rail (`_jhsaa.html`), so they must all agree with the ladder;
    the rankings and honors pages ALSO carry a `<select>` switcher, and it is the
    same list. This is a data-driven check on purpose: the nine-class ladder
    (owner 2027-08) added 9A and 8A on top of a six-class association, and a
    hardcoded list anywhere would keep rendering a complete-looking page."""
    import re
    from app import jhsaa as jh
    html = warm_client.get(path + "?g=boys").get_data(as_text=True)
    missing = [g for g in jh.GROUPS
               if not re.search(r">\s*%s\s*<" % re.escape(g), html)]
    assert not missing, (path, missing)


def test_every_classification_has_its_own_class_colour():
    """A class tab and a class chip are keyed on the classification NAME
    (`.jh-class a.on.c-9A`), and `.jh-class a.on` sets `color:#fff` with no
    background of its own — so a classification with no rule renders WHITE ON
    THE CARD, an invisible selected tab, while everything else works. Same trap
    as a theme swatch keyed on a scheme name: adding a classification means
    adding a colour, and nothing errors when you don't."""
    import os
    css = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "app", "web", "static", "css", "jhsaa.css"),
               encoding="utf-8").read()
    from app import jhsaa as jh
    for g in jh.GROUPS:
        assert f".jh-class a.on.c-{g} " in css, g
        assert f".jh-chip.c-{g} " in css, g
