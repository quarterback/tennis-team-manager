"""The Tournament of Champions, end to end — over a REAL archived season.

`test_jhsaa_routes` renders every JHSAA page with nothing archived, which proves the
route is wired and the empty state works. It cannot see anything that only goes wrong
once there is data, and the TOC shipped with three such faults at once:

  * the page handed `brk_canvas` the raw bracket COLUMNS instead of a `_bracket_canvas`
    result, so Jinja resolved `cv.width` / `cv.cards` / `cv.links` to Undefined and drew
    a zero-size box — a toolbar and a champion above nothing, with no error anywhere;
  * `jh_round_tabs(rounds, u, gender, pin)` put the year in the macro's `id` slot, so
    the round-by-round list was never keyed to its own script; and
  * the duals were played under `phase="state"`, which made them indistinguishable in
    `world_jhsaa_dual` from the state tournament that fed the event — a program that
    reached the TOC had no way to say so, and its state record counted the TOC duals.

So this runs a season, archives it the way the world rung does, and asserts on the
rendered HTML. The association is cut to two districts per classification to keep it
to a few seconds; every code path is the real one.
"""
import json
import sqlite3

import pytest

from app import jhsaa as jh
from app import world as wd
from app.web.server import create_app


@pytest.fixture(scope="module")
def archived(tmp_path_factory):
    """A world with one JHSAA season archived, on a database of its own."""
    db = str(tmp_path_factory.mktemp("jhsaa") / "toc.db")
    real_load, real_db, real_ready = jh.load_schools, wd.WORLD_DB, wd._schema_ready_for

    def small(gender):
        """Two districts per classification — a real association, a tenth the size."""
        out = []
        for grp in jh.GROUPS:
            keep = sorted({s.district for s in real_load(gender) if s.group == grp})[:2]
            out += [s for s in real_load(gender)
                    if s.group == grp and s.district in keep]
        return out

    real_primed, real_prime = wd.is_primed, wd.prime
    jh.load_schools = small
    jh._season_cache.clear()
    wd.WORLD_DB = db
    wd._schema_ready_for = None
    try:
        w = wd.get_or_create(wd.DEFAULT_SEED)
        wd.run_jhsaa(wd.DEFAULT_SEED, w)
        # Once a world row EXISTS, `_prime_world` answers every cold request with the
        # warming loader instead of the page. Priming for real would build all ~4k
        # college programs, and no JHSAA surface reads one — the association is its
        # own world. So report warm and let the pages render.
        wd.is_primed = lambda *a, **k: True
        wd.prime = lambda *a, **k: None
        yield {"db": db, "world": w,
               "client": create_app().test_client(),
               "arc": wd.get_jhsaa(w["id"], w["year"], "girls")}
    finally:
        jh.load_schools = real_load
        jh._season_cache.clear()
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready
        wd.is_primed, wd.prime = real_primed, real_prime


# --- the event itself ----------------------------------------------------------

def test_the_field_is_one_champion_per_classification(archived):
    toc = archived["arc"]["toc"]
    champs = {nm for nm in archived["arc"]["champions"].values() if nm}
    assert set(toc["field"]) == champs
    assert len(toc["field"]) == len(jh.GROUPS)


def test_the_draw_halves_cleanly_to_one(archived):
    """Six into four into two into one. A single play-in regardless of field size left
    five standing and produced a three-team "semifinal" with a bye nobody earned."""
    toc = archived["arc"]["toc"]
    alive, shape = len(toc["field"]), []
    for games in toc["rounds"]:
        shape.append(alive)
        alive -= len(games)
    assert shape == [6, 4, 2] and alive == 1
    assert toc["champion"] in toc["field"]


def test_the_field_is_seeded_on_toss_not_on_classification(archived):
    """The whole point of the event: a 4A champion that rated above the 6A one is the
    higher seed, so the field order must not be the classification order."""
    toc = archived["arc"]["toc"]
    seeds = toc["seeds"]
    assert sorted(seeds.values()) == list(range(1, len(toc["field"]) + 1))
    assert [seeds[n] for n in toc["field"]] == list(range(1, len(toc["field"]) + 1))


# --- the duals are TELLABLE APART in the archive --------------------------------

def test_toc_duals_are_archived_under_their_own_phase(archived):
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT school, opp, won FROM world_jhsaa_dual"
                        " WHERE phase='toc' AND gender='girls'").fetchall()
    conn.close()
    toc = archived["arc"]["toc"]
    played = sum(len(r) for r in toc["rounds"])
    assert len(rows) == 2 * played           # a dual sits on both sides' cards
    assert {r["school"] for r in rows} <= set(toc["field"])


def test_the_toc_stays_out_of_the_toss_rating(archived):
    """TOSS is the SEEDING input and the TOC is played after the seeds are drawn from
    it; its 1S/4D lines would also reach flights the weight table stops short of."""
    season = jh.run_season("girls", archived["arc"]["season_year"], seed=0,
                           salt=wd.active_salt(wd.DEFAULT_SEED))
    rated = jh.rating_duals(list(season["teams"].values()))
    champs = set(season["toc"]["field"])
    for d in rated:
        assert not (d["home"] in champs and d["away"] in champs
                    and d["home_points"] + d["away_points"] == 5)


def test_a_toc_run_does_not_inflate_the_state_record(archived):
    """"Post" is the state tournament the program was seeded into. Folding the TOC in
    made a champion's state run read one or two duals longer than it was."""
    w, champ = archived["world"], archived["arc"]["toc"]["champion"]
    row = wd.jhsaa_school_history(w["id"], "girls", champ)["seasons"][0]
    assert row["made_toc"] and row["toc_champion"]
    assert row["toc_wins"] >= 1 and row["toc_record"] != "0-0"
    assert row["pwins"] + row["plosses"] < row["toc_wins"] + row["toc_losses"] + 12
    # The state finish is the CLASSIFICATION title, unchanged by what came after it.
    assert row["champion"] and row["state_finish"] == "Champion"


def test_a_program_that_missed_the_toc_carries_nothing(archived):
    w = archived["world"]
    outside = next(s.name for s in jh.load_schools("girls")
                   if s.name not in archived["arc"]["toc"]["field"])
    row = wd.jhsaa_school_history(w["id"], "girls", outside)["seasons"][0]
    assert not row["made_toc"] and row["toc_finish"] == ""
    assert row["toc_wins"] == row["toc_losses"] == 0


# --- the pages -------------------------------------------------------------------

def test_the_toc_page_draws_a_real_bracket(archived):
    """The bug the owner reported: a toolbar and a champion above an empty box. A
    canvas the template can draw has a width, a card per game and elbows between."""
    html = archived["client"].get("/jhsaa/toc?g=girls").get_data(as_text=True)
    toc = archived["arc"]["toc"]
    games = sum(len(r) for r in toc["rounds"])
    byes = len(toc["field"]) - 2 * len(toc["rounds"][0])
    assert html.count("brk-card") >= games + byes
    assert "brk-link" in html and 'class="brk-canvas"' in html
    assert "width:0px" not in html


def test_the_toc_page_lists_every_round(archived):
    """"Why can't I see round by round results like everything else?" — the same
    Results-by-round panel the state bracket carries."""
    html = archived["client"].get("/jhsaa/toc?g=girls").get_data(as_text=True)
    assert "Results by round" in html
    for name in ("Quarterfinals", "Semifinals", "Championship"):
        assert name in html, name
    for nm in archived["arc"]["toc"]["field"]:
        assert nm in html, nm


def test_a_toc_program_page_shows_the_run(archived):
    """Making the field is the honour, so it has to be ON the program page — the chip
    beside the state finish, the duals on the card, and a line in the honours."""
    champ = archived["arc"]["toc"]["champion"]
    html = archived["client"].get(
        f"/jhsaa/school/{champ}?g=girls").get_data(as_text=True)
    assert "Tournament of Champions" in html
    assert 'class="jh-tag toc">TOC' in html          # gold, and its own label
    assert "TOURNAMENT OF CHAMPIONS" in html         # the honours row


def test_every_jhsaa_page_renders_against_a_real_season(archived):
    c = archived["client"]
    champ = archived["arc"]["toc"]["champion"]
    sc = next(s for s in jh.load_schools("girls") if s.name == champ)
    for path in ("/jhsaa?g=girls", "/jhsaa/toc?g=girls", "/jhsaa/bracket?g=girls",
                 "/jhsaa/rankings?g=girls", f"/jhsaa/rankings?g=girls&group={sc.group}",
                 "/jhsaa/districts?g=girls", "/jhsaa/champions?g=girls",
                 f"/jhsaa/district/{sc.group}/{sc.district}?g=girls",
                 f"/jhsaa/school/{champ}?g=girls"):
        assert c.get(path).status_code == 200, path


# --- the rankings page ------------------------------------------------------------

def test_the_rankings_page_shows_the_whole_classification(archived):
    """The hub's rail panel cuts the list at twelve; the page must not."""
    grp = jh.GROUPS[0]
    rows = wd.jhsaa_group_ranking(archived["arc"], grp)
    assert len(rows) > 12
    html = archived["client"].get(
        f"/jhsaa/rankings?g=girls&group={grp}").get_data(as_text=True)
    for r in rows:
        assert r["school"] in html, r["school"]
