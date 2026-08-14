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
from app.web import state as st
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


def test_a_toc_run_lands_on_the_season_record(archived):
    """‼️ There is no separate postseason record. The NCAA and the NFHS both carry the
    postseason inside the season total, so `record` has to cover EVERY dual a program
    played — and the TOC is the last thing played, by the six programs whose record
    matters most. It used to be snapshotted inside the loop that ran each state draw,
    which cannot have seen a TOC that needs every group's champion, so those six
    archived their final duals on the schedule and left them off the record."""
    w = archived["world"]
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row
    try:
        for school in archived["arc"]["toc"]["field"]:
            row = wd.jhsaa_school_history(w["id"], "girls", school)["seasons"][0]
            n = conn.execute("SELECT COUNT(*) c FROM world_jhsaa_dual WHERE world_id=?"
                             " AND year=? AND gender='girls' AND school=?",
                             (w["id"], w["year"], school)).fetchone()["c"]
            assert row["wins"] + row["losses"] == n, (school, row["record"], n)
            assert row["made_toc"]
    finally:
        conn.close()


def test_every_archived_record_covers_every_dual_played(archived):
    """The same rule over the whole association, not just the six: a record is the
    record. Before the fix 131 of 137 programs balanced and the six that did not were
    exactly the TOC field, which is the shape a sampled check would have missed."""
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row
    w, off = archived["world"], []
    try:
        played = {r["school"]: r["n"] for r in conn.execute(
            "SELECT school, COUNT(*) n FROM world_jhsaa_dual WHERE world_id=? AND"
            " year=? AND gender='girls' GROUP BY school", (w["id"], w["year"]))}
    finally:
        conn.close()
    for grp, dists in (archived["arc"]["standings"] or {}).items():
        for rows in dists.values():
            for r in rows:
                got = sum(int(x) for x in r["record"].split("-"))
                if got != played.get(r["school"], 0):
                    off.append((r["school"], r["record"], played.get(r["school"])))
    assert not off, off[:5]


def test_no_program_publishes_a_postseason_record(archived):
    """The tile the owner read 27-4 and 6-1 off and added together. A postseason leaves
    a FINISH behind, not a second record — the record already contains it."""
    w, champ = archived["world"], archived["arc"]["toc"]["champion"]
    hist = wd.jhsaa_school_history(w["id"], "girls", champ)
    for key in ("post_record", "pwins", "plosses", "toc_wins", "toc_losses"):
        assert key not in hist["seasons"][0], key
        assert key not in hist["totals"], key
    assert hist["seasons"][0]["toc_finish"] == "TOC Champion"
    html = archived["client"].get(
        f"/jhsaa/school/{champ}?g=girls").get_data(as_text=True)
    assert ">Post<" not in html


def test_a_title_survives_a_season_with_no_individual_awards(archived):
    """‼️ The Honours panel selects the seasons it will draw, and the TEAM titles are
    banners rendered from `champion` / `toc_champion` rather than entries in `honors`.
    So a program that won its classification and the TOC without a single All-District
    player has an empty `honors` list, and a panel filtering on that list drops the
    season BEFORE either banner can render — the titles vanish from the one panel that
    exists to show them. (True of the state title before the TOC existed, too.)"""
    w, champ = archived["world"], archived["arc"]["toc"]["champion"]
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT data FROM world_jhsaa WHERE world_id=? AND year=? AND"
                       " gender='girls'", (w["id"], w["year"])).fetchone()
    original = row["data"]
    arc = json.loads(original)
    grp = next(g for g, nm in arc["champions"].items() if nm == champ)
    arc["awards"][grp] = {"poy": None, "all_state": []}      # strip every award...
    arc["all_district"][grp] = {}                            # ...this program could win
    try:
        conn.execute("UPDATE world_jhsaa SET data=? WHERE world_id=? AND year=? AND"
                     " gender='girls'", (json.dumps(arc), w["id"], w["year"]))
        conn.commit()
        season = wd.jhsaa_school_history(w["id"], "girls", champ)["seasons"][0]
        assert season["honors"] == [] and season["champion"] and season["toc_champion"]
        assert season["honoured"], "a title IS an honour, however bare the season"
        html = archived["client"].get(
            f"/jhsaa/school/{champ}?g=girls").get_data(as_text=True)
        assert "TOURNAMENT OF CHAMPIONS" in html
        assert f"{grp} STATE CHAMPION" in html
    finally:
        conn.execute("UPDATE world_jhsaa SET data=? WHERE world_id=? AND year=? AND"
                     " gender='girls'", (original, w["id"], w["year"]))
        conn.commit()
        conn.close()


def test_a_season_with_nothing_to_show_is_not_listed_as_an_honour(archived):
    """The other half: `honoured` must not simply be true for everyone, or the panel
    becomes the ledger a second time. TEAM honours widened it (owner rule 2027-08 —
    a tournament-unit win or a State appearance counts, not just titles and TOC
    berths), so the floor is now "won nothing, reached nothing": such a season is
    still unhonoured, and at least one program in the association has one."""
    w = archived["world"]
    rows = [wd.jhsaa_school_history(w["id"], "girls", s.name)["seasons"]
            for s in jh.load_schools("girls")]
    seasons = [r[0] for r in rows if r]
    for row in seasons:
        assert row["honoured"] == bool(
            row["honors"] or row["champion"] or row["toc_champion"]
            or row["unit_wins"] or row["made_state"])
    assert any(not s["honoured"] for s in seasons)


def test_a_toc_title_is_listed_in_the_honours_exactly_once(archived):
    """It appeared twice, one row apart: a gold banner from the template and a text
    line from the season row. The champion gets the banner — the same treatment the
    state title gets — and the text line is for programs that made the field."""
    w = archived["world"]
    champ = archived["arc"]["toc"]["champion"]
    row = wd.jhsaa_school_history(w["id"], "girls", champ)["seasons"][0]
    assert not [h for h in row["honors"] if "Tournament of Champions" in h]
    html = archived["client"].get(
        f"/jhsaa/school/{champ}?g=girls").get_data(as_text=True)
    assert html.count("TOURNAMENT OF CHAMPIONS") == 1
    # A beaten entrant has no banner, so it keeps the text line.
    other = next(n for n in archived["arc"]["toc"]["field"] if n != champ)
    beaten = wd.jhsaa_school_history(w["id"], "girls", other)["seasons"][0]
    assert [h for h in beaten["honors"] if h.startswith("Tournament of Champions")]


def test_a_program_that_missed_the_toc_carries_nothing(archived):
    w = archived["world"]
    outside = next(s.name for s in jh.load_schools("girls")
                   if s.name not in archived["arc"]["toc"]["field"])
    row = wd.jhsaa_school_history(w["id"], "girls", outside)["seasons"][0]
    assert not row["made_toc"] and row["toc_finish"] == ""


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


def test_the_schedule_labels_the_toc_duals_as_toc(archived):
    """A TOC dual is not a state dual and must not read as one — the champion's card
    showed three green STATE rows where the last two were the Tournament of Champions.
    The label comes off the PHASE, which is why the phase exists."""
    champ = archived["arc"]["toc"]["champion"]
    view = st.jhsaa_school_view(wd.DEFAULT_SEED, "girls", champ)
    kinds = [d["kind"] for d in view["schedule"]]
    assert kinds.count("TOC") == sum(
        1 for games in archived["arc"]["toc"]["rounds"]
        for gm in games if champ in (gm["home"], gm["away"]))
    assert kinds[-1] == "TOC"                     # the last thing played all year
    for d in view["schedule"]:
        assert (d["kind"] == "TOC") == (d["phase"] == "toc"), d


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
