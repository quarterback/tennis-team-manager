"""Nationality flags on the JHSAA surfaces — a SMOKE test, no season played.

`p.country` has been stamped on ~10% of JHSAA players since the 2026-08 name era
and no JHSAA template ever passed it, so the flags were invisible for a year.
Fixing that missed the school page's HQ roster PREVIEW — the same template
renders the roster twice and only the Team tab got the flag, which is not the
loop a default page load shows.

‼️ THE EXPENSIVE TEST IS THE WRONG TOOL HERE. Rendering the real page needs an
archived season (minutes); an empty-state route test renders the roster table
with NO ROWS, so the flag code is never reached and a broken version passes.
What actually broke was cheap and structural — a field missing from a view dict,
and one of two loops in a template — so this asserts exactly those two things.
"""
import re

import app.jhsaa as jh

SCHOOL_TPL = "app/web/templates/jhsaa_school.html"
PLAYER_TPL = "app/web/templates/jhsaa_player.html"


def test_the_roster_view_carries_country():
    """The view-model half: `country` reaches the template at all."""
    import inspect
    from app.web import state
    src = inspect.getsource(state.jhsaa_school_view)
    assert '"country": p.country' in src
    src = inspect.getsource(state.jhsaa_player_view)
    assert '"country": player.country' in src


def test_every_roster_loop_on_the_school_page_renders_the_flag():
    """‼️ THE REGRESSION THIS FILE EXISTS FOR. `jhsaa_school.html` lists the
    roster TWICE — the HQ preview (top six, what a default load shows) and the
    Team tab — and the first fix reached only the second. Count the player links
    and require a flag beside each: a third roster loop added later fails here
    rather than shipping half-flagged."""
    html = open(SCHOOL_TPL).read()
    # Each roster row that links a player. The flag may sit on the line above the
    # anchor or inline with it, so the window is the CELL — from the <td> that
    # opens the row to the anchor itself.
    hits = [m.start() for m in re.finditer(r"url_for\('jhsaa_player'", html)
            if "p.pid" in html[m.start():m.start() + 120]]
    assert len(hits) >= 2, "expected the HQ preview and the Team tab"
    for at in hits:
        # The cell the anchor sits in, back to whichever <td class="pl"> opens it
        # (the flag may be inline with the anchor or on a line above it, and the
        # Team tab carries an explanatory comment in between).
        before = html[max(0, at - 900):at]
        cut = before.rfind('<td class="pl"')
        cell = before[cut:] if cut >= 0 else before
        assert "player-flag" in cell, html[at - 120:at + 60].strip()[:120]


def test_the_player_profile_renders_the_flag():
    """The one surface the owner named: "they have a flag on their player
    profile"."""
    html = open(PLAYER_TPL).read()
    assert "player-flag" in html
    assert "view.country" in html


def test_us_players_are_never_flagged():
    """A flag on ~90% of rows carries no information, so US is unmarked — the
    guard is in the template, on every flag site."""
    for path in (SCHOOL_TPL, PLAYER_TPL):
        html = open(path).read()
        for chunk in html.split("player-flag")[:-1]:
            tail = chunk[-160:]
            assert "!= 'US'" in tail, f"{path}: an unguarded flag"


def test_a_foreign_player_actually_exists_to_flag():
    """The data half, and the reason any of this matters: the association really
    does generate non-US players, so an unflagged UI was losing real
    information."""
    school = jh.load_schools("boys")[0]
    roster = jh.build_roster(school, 0, "")
    assert roster and all(p.country for p in roster)
    pool = [p for s in jh.load_schools("boys")[:25]
            for p in jh.build_roster(s, 0, "")]
    foreign = [p for p in pool if p.country != "US"]
    assert foreign, "no foreign-flagged player generated at all"
    # ~10% by design (the 2026-08 name era's 5% Canada + 5% international).
    assert 0.02 <= len(foreign) / len(pool) <= 0.25, len(foreign) / len(pool)
