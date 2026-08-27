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
    # The two CAREER rolls on the History sub-rail. Both fold over every archived
    # season, so with nothing archived they must render an empty state rather than
    # raise on the first fold.
    "/jhsaa/repeat-poy",
    "/jhsaa/repeat-poy?g=boys",
    "/jhsaa/repeat-champions",
    "/jhsaa/repeat-champions?g=boys",
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


# --- the program directory ---------------------------------------------------------

DIRECTORY_MODES = ["county", "class", "az"]


@pytest.mark.parametrize("mode", DIRECTORY_MODES)
def test_the_directory_lists_every_program(warm_client, mode):
    """‼️ A DIRECTORY THAT DROPS PROGRAMS IS WORSE THAN NO DIRECTORY — you would go on
    believing the association has no school in that county. Every grouping is the SAME
    list regrouped, so all three must show all of it, and this is the only page in the
    section where that is checkable without playing a season (it reads the school list,
    never an archive)."""
    import re
    from app import jhsaa as jh
    html = warm_client.get(f"/jhsaa/schools?g=boys&mode={mode}").get_data(as_text=True)
    assert html.count('class="jh-dirrow"') == len(jh.load_schools("boys"))
    # and the rows are LINKS to program pages, not inert text
    assert re.search(r'class="jh-dirrow"[^>]*href="/jhsaa/school/', html, re.S) or \
        'href="/jhsaa/school/' in html


def test_a_directory_row_is_findable_by_more_than_its_name(warm_client):
    """The filter box is what replaces ctrl-F, and ctrl-F could only match the NAME.
    Each row carries a lower-cased haystack of everything you might search a school by;
    if that ever narrows back to the name, the page stops answering the question it
    exists for and still looks completely correct."""
    from app import jhsaa as jh
    html = warm_client.get("/jhsaa/schools?g=boys").get_data(as_text=True)
    s = jh.load_schools("boys")[0]
    hay = next(h for h in html.split('data-q="')[1:] if h.startswith(s.name.lower()))
    hay = hay.split('"')[0]
    for part in (s.city, s.county, s.area, s.district, s.group):
        if part:
            assert part.lower() in hay, (s.name, part)


# --- the scope bar is sticky -------------------------------------------------------

STICKY = ["/jhsaa/rankings", "/jhsaa/honors", "/jhsaa/districts", "/jhsaa/bracket",
          "/jhsaa/schools", "/jhsaa/toc", "/jhsaa/champions"]


@pytest.mark.parametrize("path", STICKY)
def test_a_scope_switch_keeps_you_on_the_page(warm_client, path):
    """‼️ THE SCOPE BAR SWITCHES SCOPE, NOT PAGE (owner rule 2026-08). Every control in
    it used to be hardcoded to `jhsaa_page`, so comparing the boys' and girls' rankings
    meant going back to the hub and walking in again — on every page, for every axis.
    A page keyed to one program (a school, a player) legitimately falls back; these are
    the ones that have somewhere to stay."""
    import re
    html = warm_client.get(path + "?g=boys").get_data(as_text=True)
    hrefs = re.findall(r'(?:href|value)="([^"]*)"', html.replace("&amp;", "&"))
    assert any(h.startswith(path) and "g=girls" in h for h in hrefs), path


def test_a_scope_switch_keeps_the_pages_own_query_state(warm_client):
    """A sort is part of where you are. Switching gender to compare two tables must not
    also re-sort the one you were reading."""
    import re
    html = warm_client.get("/jhsaa/rankings?g=boys&group=5A&sort=rec&dir=asc") \
        .get_data(as_text=True).replace("&amp;", "&")
    girls = [h for h in re.findall(r'value="(/jhsaa/rankings[^"]*)"', html)
             if "g=girls" in h]
    assert girls and all("sort=rec" in h and "dir=asc" in h for h in girls), girls


def test_a_gender_switch_keeps_an_All_class_filter(warm_client):
    """‼️ THE PAGE'S OWN ARGS OUTRANK THE SCOPE'S NORMALISATION. Players and Mismatches
    run on `group=All`, which `jhsaa_scope_view` normalises to the first classification
    for the RAIL — there is no "All" tab to light up. Seeding the switcher's args from
    the scope and filling the request in afterwards rewrote All → 9A, so switching
    gender silently narrowed the directory to one class while appearing to change only
    gender: every row on screen was correct, and most of them were missing."""
    import re
    for path in ("/jhsaa/players", "/jhsaa/misapplied"):
        html = warm_client.get(path + "?g=boys&group=All").get_data(as_text=True) \
            .replace("&amp;", "&")
        girls = [h for h in re.findall(r'value="(%s[^"]*)"' % re.escape(path), html)
                 if "g=girls" in h]
        assert girls, path
        assert all("group=All" in h for h in girls), (path, girls)


def test_the_toc_link_carries_the_class_it_was_taken_from(warm_client):
    """The TOC is class-BLIND — it fields every classification's champion — but the
    class is the scope bar's memory, and a link that drops it resets the rail on the
    way in, so leaving the TOC lands you on the first class instead of the one you
    were browsing."""
    html = warm_client.get("/jhsaa?g=boys&group=5A").get_data(as_text=True) \
        .replace("&amp;", "&")
    assert "/jhsaa/toc?u=" in html or "/jhsaa/toc?" in html
    toc = [h for h in html.split('href="') if h.startswith("/jhsaa/toc")]
    assert toc and all("group=5A" in h.split('"')[0] for h in toc), toc


def test_the_season_switch_is_not_thrown_away(warm_client):
    """‼️ A ROUTE THAT PARSES `year` AND DOESN'T PASS IT resets the control that sent
    it. The scope bar's season now keeps you on the page, so these two rebuilt their
    scope on the LATEST season and the dropdown snapped back the moment it was used —
    the page looked right, and the one thing the reader had just asked for was gone."""
    import inspect
    from app.web import server
    src = inspect.getsource(server.create_app)
    for name in ("jhsaa_players.html", "jhsaa_misapplied.html"):
        block = src.split(name)[0]
        call = block.rsplit("jhsaa_scope_view(", 1)[1].split(")")[0]
        assert call.rstrip().endswith("year"), (name, call)
