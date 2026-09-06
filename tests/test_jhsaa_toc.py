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
from app import jhsaa_awards as jaw
from app import world as wd
from app.web import state as st
from app.web.server import create_app


@pytest.fixture(scope="module")
def archived(tmp_path_factory):
    """A world with one JHSAA season archived, on a database of its own."""
    db = str(tmp_path_factory.mktemp("jhsaa") / "toc.db")
    real_load, real_db, real_ready = jh.load_schools, wd.WORLD_DB, wd._schema_ready_for

    def small(gender):
        """A scaled association — a real one, roughly a tenth the size.

        ‼️ SIZED AGAINST `PROTECTED`, NOT AT A FIXED DISTRICT COUNT. This took the
        first TWO districts per classification, which silently assumed every pair of
        leagues comes to more than the 16 protected seats. Leagues run 7-12, so a
        reclassification that puts two small ones at the head of a class's alphabet
        leaves Sectionals ZERO entrants and the ladder is handed an empty field."""
        out = []
        for grp in jh.GROUPS:
            names = sorted({s.district for s in real_load(gender) if s.group == grp})
            pool, keep = [], set()
            for name in names:
                keep.add(name)
                pool = [s for s in real_load(gender)
                        if s.group == grp and s.district in keep]
                if len(pool) > jh.PROTECTED + 8:
                    break
            out += pool
        return out

    real_primed, real_prime = wd.is_primed, wd.prime
    real_fields = dict(jh.STATE_FIELD)
    # ‼️ SCALE THE FIELD TABLE WITH THE POOLS (2026-08). Field size is PER-CLASS
    # CONFIGURATION, not a function of sponsor count — so a tenth-size class
    # under the real 32/40 tables is SMALLER than its own State field, the
    # Specials fill State with literally every program, and every premise of the
    # form "a program that missed State" or "a program with nothing to show"
    # stops existing (these tests passed pre-Specials only because the road ran
    # short and left teams out). 32→16 and 40→20 keep the three shapes distinct
    # and both draw branches live (20 expands through the Qualifiers Round,
    # 16 is the power-of-two, 24 keeps its byes and the fixed-24 ladder).
    for grp, real in real_fields.items():
        jh.STATE_FIELD[grp] = {24: 24, 32: 16, 40: 20}[real]
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
        jh.STATE_FIELD.clear()
        jh.STATE_FIELD.update(real_fields)
        jh._season_cache.clear()
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready
        wd.is_primed, wd.prime = real_primed, real_prime


# --- the event itself ----------------------------------------------------------

def test_the_field_is_one_champion_per_classification(archived):
    toc = archived["arc"]["toc"]
    champs = {nm for nm in archived["arc"]["champions"].values() if nm}
    assert set(toc["field"]) == champs
    assert len(toc["field"]) == len(jh.GROUPS)


def test_the_toc_is_a_standard_seeded_bracket(archived):
    """‼️ COMMON BRACKET LOGIC, nothing else (owner rule 2026-08): the field sits
    on the standard seed lines of the next power of two, byes fall to the top
    seeds, and the bracket is FIXED — a winner takes the beaten seed's line, no
    re-pairing between rounds. At twelve that is 5v12 · 6v11 · 7v10 · 8v9 with
    seeds 1-4 sitting; a 9 is the lone 8v9 game into the 1 line; a 14 would add
    4v13 — the same rule at every count, so this asserts the RULE (round-one
    pairs sum to m+1, byes are exactly the top seeds, every later round halves),
    never a hand-typed shape."""
    toc = archived["arc"]["toc"]
    seeds, n = toc["seeds"], len(toc["field"])
    m = 1
    while m < n:
        m *= 2
    r1 = toc["rounds"][0]
    assert all(seeds[g["home"]] + seeds[g["away"]] == m + 1 for g in r1)
    played = {seeds[g[k]] for g in r1 for k in ("home", "away")}
    assert played == set(range(m - n + 1, n + 1)), \
        "byes go to the top seeds and nobody else"
    alive = n
    for games in toc["rounds"]:
        alive -= len(games)
    assert alive == 1
    for prev, nxt in zip(toc["rounds"][1:], toc["rounds"][2:]):
        assert len(prev) == 2 * len(nxt), "every column halves into the next"
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
    # ‼️ ON THE PHASE, NOT ON THE COURT COUNT. This asserted that no five-court dual
    # between two TOC-field teams was rated, which reads as a proxy for "no TOC dual"
    # and is not one: the mid-season SHOWCASES are 1S/4D too, are deliberately rated,
    # and can pair two programs that both go on to win their classification. It
    # passed only until a rename shuffled which programs met in a showcase.
    assert not [d for d in rated if d.get("phase") in jh.POSTSEASON]
    champs = set(season["toc"]["field"])
    assert champs, "the TOC field is empty — the fixture did not play one"


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
            # level='v': the JV season shares this table and is not on this record.
            n = conn.execute("SELECT COUNT(*) c FROM world_jhsaa_dual WHERE world_id=?"
                             " AND year=? AND gender='girls' AND school=? AND level='v'",
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
        # Varsity rows only: the JV season shares this table.
        played = {r["school"]: r["n"] for r in conn.execute(
            "SELECT school, COUNT(*) n FROM world_jhsaa_dual WHERE world_id=? AND"
            " year=? AND gender='girls' AND level='v' GROUP BY school",
            (w["id"], w["year"]))}
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
    # ⚠️ All-Region is CLASS-BLIND and lives on the SEASON, so emptying a
    # classification's slate no longer removes it — it has to go separately.
    arc["all_region"] = {}
    try:
        conn.execute("UPDATE world_jhsaa SET data=? WHERE world_id=? AND year=? AND"
                     " gender='girls'", (json.dumps(arc), w["id"], w["year"]))
        conn.commit()
        season = wd.jhsaa_school_history(w["id"], "girls", champ)["seasons"][0]
        assert season["honors"] == [] and season["champion"] and season["toc_champion"]
        assert season["honoured"], "a title IS an honour, however bare the season"
        html = archived["client"].get(
            f"/jhsaa/school/{champ}?g=girls&view=honors").get_data(as_text=True)
        # Both banners are gold LINES on the season's trophy card now, in sentence
        # case (owner 2026-09 — see `test_a_toc_program_page_shows_the_run`). The
        # subject of this test is that an awardless season still DRAWS its titles,
        # which is a question about the pane's filter, not about the casing.
        assert "Tournament of Champions" in html
        assert "State champion" in html          # one row, whatever the class
    finally:
        conn.execute("UPDATE world_jhsaa SET data=? WHERE world_id=? AND year=? AND"
                     " gender='girls'", (original, w["id"], w["year"]))
        conn.commit()
        conn.close()


def test_a_season_with_nothing_to_show_is_not_listed_as_an_honour(archived):
    """The other half: `honoured` must be COMPUTED, never simply true for everyone,
    or the panel becomes the ledger a second time. TEAM honours widened it (owner
    rule 2027-08 — a tournament-unit win or a State appearance counts, not just
    titles and TOC berths), so the floor is "won nothing, reached nothing".

    ⚠️ It is no longer safe to look for a bare season in the LIVE archive. Doubles
    honours are PAIRINGS (owner correction 2027-08), so an All-District team is 10
    singles + 8 pairs = **26 athletes** spread over a district of about a dozen
    schools, and All-Region sits on top of that — in practice every program places
    somebody. That is the honours being wide, not `honoured` being hardcoded, and
    the two are only distinguishable by taking the awards away. So this strips a
    classification's slate and checks a program in it goes dark."""
    w = archived["world"]
    rows = [wd.jhsaa_school_history(w["id"], "girls", s.name)["seasons"]
            for s in jh.load_schools("girls")]
    seasons = [r[0] for r in rows if r]
    for row in seasons:
        assert row["honoured"] == bool(
            row["honors"] or row["champion"] or row["toc_champion"]
            or row["unit_wins"] or row["made_state"])

    # Now take the awards away from one classification and find a program in it
    # that won nothing and reached nothing — it must go unhonoured.
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row
    original = conn.execute(
        "SELECT data FROM world_jhsaa WHERE world_id=? AND year=? AND gender='girls'",
        (w["id"], w["year"])).fetchone()["data"]
    arc = json.loads(original)
    grp = jh.GROUPS[0]
    arc["awards"][grp] = {"poy": None, "all_state": []}
    arc["all_district"][grp] = {}
    arc["all_region"] = {}       # class-blind, and on the SEASON — see above
    try:
        conn.execute("UPDATE world_jhsaa SET data=? WHERE world_id=? AND year=? AND"
                     " gender='girls'", (json.dumps(arc), w["id"], w["year"]))
        conn.commit()
        bare = [wd.jhsaa_school_history(w["id"], "girls", s.name)["seasons"][0]
                for s in jh.load_schools("girls") if s.group == grp]
        assert any(not r["honoured"] for r in bare), \
            "no program in a classification with NO awards went unhonoured"
        for r in bare:
            assert r["honoured"] == bool(
                r["champion"] or r["toc_champion"] or r["unit_wins"] or r["made_state"])
    finally:
        conn.execute("UPDATE world_jhsaa SET data=? WHERE world_id=? AND year=? AND"
                     " gender='girls'", (original, w["id"], w["year"]))
        conn.commit()
        conn.close()


def test_a_toc_title_is_listed_in_the_honours_exactly_once(archived):
    """It appeared twice, one row apart: a gold banner from the template and a text
    line from the season row. The champion gets the banner — the same treatment the
    state title gets — and the text line is for programs that made the field."""
    w = archived["world"]
    champ = archived["arc"]["toc"]["champion"]
    row = wd.jhsaa_school_history(w["id"], "girls", champ)["seasons"][0]
    assert not [h for h in row["honors"] if "Tournament of Champions" in h]
    html = archived["client"].get(
        f"/jhsaa/school/{champ}?g=girls&view=honors").get_data(as_text=True)
    # ‼️ COUNT INSIDE THE PANE, NOT THE DOCUMENT. The banner is sentence case since
    # the trophy case (owner 2026-09), and the scope rail every JHSAA page carries
    # already prints "Tournament of Champions" twice — once as a nav link, once in a
    # `title=` — so a document-wide count of the phrase measures the chrome and can
    # never reach 1. It was only ever 1 because the old banner SHOUTED and nothing
    # else on the page did. The invariant is unchanged: the champion's season is
    # drawn once in the trophy case, with the gold line and no duplicate text row.
    # Anchored on the PANE, not on `data-pane` alone — the tab bar's buttons carry
    # that attribute too, and splitting on it slices the tab bar instead.
    team = html.split('class="jh-pane" data-pane="team"', 1)[1]
    team = team.split('class="jh-pane" data-pane="players"', 1)[0]
    assert team.count("Tournament of Champions") == 1
    # A beaten entrant has no banner, so it keeps the text line — in
    # `team_honors`, because a TOC finish is a TEAM honour (`_season_row`'s own
    # rule: `honors` is individual awards, full stop; the school page files the
    # two lists on separate tabs, and this line belongs with the trophies).
    other = next(n for n in archived["arc"]["toc"]["field"] if n != champ)
    beaten = wd.jhsaa_school_history(w["id"], "girls", other)["seasons"][0]
    assert [h for h in beaten["team_honors"]
            if h.startswith("Tournament of Champions")]
    assert not [h for h in beaten["honors"] if "Tournament of Champions" in h]


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
    # The program HQ (owner rule 2026-09) files the run where each piece lives:
    # the chip stays on the identity block, the duals on the Season view's card,
    # the banner in the Honors view's trophy case.
    html = archived["client"].get(
        f"/jhsaa/school/{champ}?g=girls&view=season").get_data(as_text=True)
    assert "Tournament of Champions" in html
    assert 'class="jh-tag toc">TOC' in html          # gold, and its own label
    honors = archived["client"].get(
        f"/jhsaa/school/{champ}?g=girls&view=honors").get_data(as_text=True)
    # The trophy case draws the title as a gold LINE on that season's card, in
    # sentence case — the uppercase pill went with the card grid (owner 2026-09:
    # "drop the uppercase micro-labels"). What this test is about is that the run
    # reaches the Honors view at all, so it asserts the title, not its casing.
    assert "Tournament of Champions" in honors


def test_every_jhsaa_page_renders_against_a_real_season(archived):
    c = archived["client"]
    champ = archived["arc"]["toc"]["champion"]
    sc = next(s for s in jh.load_schools("girls") if s.name == champ)
    for path in ("/jhsaa?g=girls", "/jhsaa/class?g=girls", "/jhsaa/toc?g=girls", "/jhsaa/bracket?g=girls",
                 "/jhsaa/rankings?g=girls", f"/jhsaa/rankings?g=girls&group={sc.group}",
                 "/jhsaa/districts?g=girls", "/jhsaa/champions?g=girls",
                 f"/jhsaa/district/{sc.group}/{sc.district}?g=girls",
                 f"/jhsaa/school/{champ}?g=girls",
                 f"/jhsaa/school/{champ}?g=girls&view=team",
                 f"/jhsaa/school/{champ}?g=girls&view=season",
                 f"/jhsaa/school/{champ}?g=girls&view=history",
                 f"/jhsaa/school/{champ}?g=girls&view=honors",
                 f"/jhsaa/school/{champ}?g=girls&view=records"):
        assert c.get(path).status_code == 200, path


# --- the rankings page ------------------------------------------------------------

def test_the_rankings_page_shows_the_whole_classification(archived):
    """The hub's rail panel cuts the list at twelve; the page must not.
    ‼️ Compare ESCAPED names: Jinja autoescape writes Sandra Day O'Connor as
    O&#39;Connor, so a raw substring check fails on exactly the apostrophe
    schools while every plain name passes — which is how this hid until the
    fixture's district cut picked one up."""
    from markupsafe import escape
    grp = jh.GROUPS[0]
    rows = wd.jhsaa_group_ranking(archived["arc"], grp)
    assert len(rows) > 12
    html = archived["client"].get(
        f"/jhsaa/rankings?g=girls&group={grp}").get_data(as_text=True)
    for r in rows:
        assert str(escape(r["school"])) in html, r["school"]


# --- the honors page, over the SAME archived season --------------------------
# An empty-state route test cannot see any of this: every fault below only exists
# once a season has actually been selected and written down.

def test_the_honors_page_renders_every_classification(archived):
    c = archived["client"]
    for grp in jh.GROUPS:
        r = c.get(f"/jhsaa/honors?g=girls&group={grp}")
        assert r.status_code == 200, grp
        html = r.get_data(as_text=True)
        assert "All-State" in html and "All-Region" in html and "All-District" in html
        assert "Flight check" in html


def test_the_honors_page_names_every_selection(archived):
    """The rows must carry PEOPLE. A doubles selection is a PAIRING, so both of
    its players' names have to be on the page and both have to link to their own
    player page — a pairing rendered as one linked name and one bare one is the
    'half a pairing' fault, and it looks completely fine."""
    import html as _html
    arc = wd.get_jhsaa(archived["world"]["id"], archived["world"]["year"], "girls")
    for grp in jh.GROUPS:
        aw = arc["awards"][grp]
        # Unescape: Jinja escapes an apostrophe to &#39;, and plenty of these
        # players are named Ta'amu or O'Rourke.
        html = _html.unescape(archived["client"].get(
            f"/jhsaa/honors?g=girls&group={grp}").get_data(as_text=True))
        rows = [r for t in aw["teams"] for r in t["players"]]
        assert rows, grp
        for r in rows:
            for nm in r["names"]:
                assert nm in html, (grp, nm)
            for pid in jaw.row_pids(r):
                assert pid in html, (grp, r["name"], pid)


def test_the_honors_page_separates_singles_from_doubles_teams(archived):
    """‼️ "8 doubles" means eight PAIRS — sixteen athletes. The page has to say so;
    a flat list of eighteen rows reads as eighteen individuals."""
    html = archived["client"].get(
        f"/jhsaa/honors?g=girls&group={jh.GROUPS[0]}").get_data(as_text=True)
    assert "Doubles teams" in html and "pairs ·" in html and "athletes" in html


def test_every_region_and_district_team_is_on_the_honors_page(archived):
    """The region and district views are SWITCHERS over the whole set, not the
    first one with a link to the rest — every team is in the page, one shown."""
    arc = wd.get_jhsaa(archived["world"]["id"], archived["world"]["year"], "girls")
    assert arc["all_region"], "All-Region is archived at the SEASON level"
    for grp in jh.GROUPS:
        html = archived["client"].get(
            f"/jhsaa/honors?g=girls&group={grp}").get_data(as_text=True)
        # All-Region is class-blind, so EVERY classification page carries the
        # association's whole set of region teams — the same ten, unchanged.
        for rn in arc["all_region"]:
            assert rn in html, (grp, rn)
        for dn in (arc["all_district"].get(grp) or {}):
            assert dn in html, (grp, dn)


def test_an_archived_season_keeps_its_honors_pinned_to_that_year(archived):
    """The archive is the point: a season has to still be readable years later,
    and a link taken inside an archived season must stay inside it."""
    yr = archived["world"]["year"]
    grp = jh.GROUPS[0]
    r = archived["client"].get(f"/jhsaa/honors?g=girls&group={grp}&year={yr}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert f"year={yr}" in html          # cross-links carry the pin


def test_the_flight_check_is_archived_and_shown(archived):
    """Flight weighting is structural, so what it produced is part of the record —
    archived with the season, not recomputed on read by whatever the selector has
    become by then."""
    arc = wd.get_jhsaa(archived["world"]["id"], archived["world"]["year"], "girls")
    assert arc["all_region_flight_check"]["floor"] == jaw.FLIGHT_FLOOR["region"]
    for grp in jh.GROUPS:
        fc = arc["awards"][grp]["flight_check"]
        assert fc.get("state"), grp
        assert fc["state"]["floor"] == jaw.FLIGHT_FLOOR["state"]
        html = archived["client"].get(
            f"/jhsaa/honors?g=girls&group={grp}").get_data(as_text=True)
        for flight, n in fc["state"]["flights"].items():
            assert f"{flight} × {n}" in html, (grp, flight)


def test_the_honors_view_never_overwrites_a_player_with_their_school(archived):
    """‼️ THE REGRESSION THAT ACTUALLY SHIPPED, tested where it happened.

    The selector's rows always named people. `jhsaa_honors_view.deco()` splatted
    `_jh_deco(...)` — which describes a SCHOOL and whose dict is keyed `name` —
    over each award row, so every selection rendered as its own school: All-State
    read "Beacon Hill", "Belmonte West", "Serrano". Every other caller splats a
    deco over a row that IS a school, where `name` colliding is correct; this is
    the one place the row is a PERSON.

    A test on `season["awards"]` cannot see this and stays green with the fix
    reverted, because the data underneath was never wrong. So this goes through
    the VIEW, on every surface it builds, and compares each decorated row against
    the ARCHIVED row it was built from: the crest must arrive and nothing else
    may."""
    w = archived["world"]
    arc = wd.get_jhsaa(w["id"], w["year"], "girls")
    schools = {s.name for s in jh.load_schools("girls")}

    def surfaces(aw, ad, view=False):
        """The same rows in the same order, off the archive and off the view."""
        out = []
        poy = view["poy"] if view else aw.get("poy")
        if poy:
            out.append(("poy", poy))
        tiers = view["teams"] if view else aw.get("teams", [])
        for t in tiers:
            out += [(f"all-state {t['name']}", r) for r in t["players"]]
        out += [("hm", r) for r in (view["honorable_mention"] if view
                                    else aw.get("honorable_mention", []))]
        if view:
            for rg in view["regions"]:
                # A region carries TIERS (+ an HM in the one big enough), never
                # a flat `players` list — see `jhsaa_awards.region_rows`.
                for t in rg["tiers"]:
                    out += [(f"all-region {rg['region']} {t['name']}".strip(), r)
                            for r in t["players"]]
                out += [(f"all-region {rg['region']} Honorable Mention", r)
                        for r in rg["honorable_mention"]]
            for d in view["districts"]:
                out += [(f"all-district {d['district']}", r) for r in d["players"]]
                if d["poy"]:
                    out.append((f"district poy {d['district']}", d["poy"]))
        else:
            # All-Region hangs off the SEASON, not the class's slate. Walk it in
            # the same order the VIEW does (it sorts by region name), or the two
            # lists are compared row-against-unrelated-row.
            reg_all = arc.get("all_region") or {}
            for rn in sorted(reg_all):
                for _rn, tier, r in jaw.region_rows({rn: reg_all[rn]}):
                    out.append((f"all-region {rn} {tier}".strip(), r))
            for dn in sorted(ad):
                out += [(f"all-district {dn}", r) for r in ad[dn]]
                r = (aw.get("district_poy") or {}).get(dn)
                if r:
                    out.append((f"district poy {dn}", r))
        return out

    pairs_seen = 0
    for grp in jh.GROUPS:
        v = st.jhsaa_honors_view(w["seed"], "girls", group=grp)
        assert v["ready"] and v["teams"] and v["districts"], grp
        shown = surfaces(None, None, view=v)
        stored = surfaces(arc["awards"][grp], arc["all_district"].get(grp) or {})
        assert len(shown) == len(stored) and shown, (grp, len(shown), len(stored))
        for (w1, seen), (w2, kept) in zip(shown, stored):
            assert w1 == w2, (grp, w1, w2)
            # The crest is what `deco` is FOR — it must still arrive…
            assert "mark" in seen, (grp, w1)
            # …and it must have brought nothing else with it. Every field that
            # describes the PERSON has to survive the merge untouched.
            for k in ("name", "names", "pid", "pids", "school", "kind",
                      "flight", "wins", "losses"):
                assert seen[k] == kept[k], (grp, w1, k, seen[k], kept[k])
            assert seen["name"] not in schools, (grp, w1, seen["name"])
            assert seen["name"] != seen["school"], (grp, w1)
            for nm in seen["names"]:
                assert nm not in schools, (grp, w1, nm)
            assert len(jaw.row_pids(seen)) == len(seen["names"])
            pairs_seen += seen["kind"] == "doubles"
    assert pairs_seen, "no pairing reached the view"


def test_all_region_is_one_team_per_region_for_the_whole_gender(archived):
    """‼️ ALL-REGION IS CLASS-BLIND (owner rule 2027-08). There is no 7A
    All-Region team — there is a Gold Valley All-Region team, drawn from every
    program in Gold Valley whatever its enrollment.

    Selected per classification it was a district by another name: a class-region
    holds four or five schools, and ten regions × six classes × 18 selections
    honoured roughly a thousand players out of an association of ~300 programs.
    So it is archived at the SEASON level, once, and every classification page
    shows the same set."""
    w = archived["world"]
    arc = wd.get_jhsaa(w["id"], w["year"], "girls")
    assert arc["all_region"]
    for grp in jh.GROUPS:
        assert "all_region" not in arc["awards"][grp], grp

    home = {s.name: (s.area, s.group) for s in jh.load_schools("girls")}
    for rn, reg in arc["all_region"].items():
        rows = [r for _a, _b, r in jaw.region_rows({rn: reg})]
        assert all(home[r["school"]][0] == rn for r in rows), rn
        assert len({r["school"] for r in rows}) > 2, rn
    assert any(len({home[r["school"]][1] for _a, _b, r in jaw.region_rows({rn: reg})}) > 1
               for rn, reg in arc["all_region"].items()), \
        "no region team mixed classifications"

    # A big region crowns two teams; the biggest also crowns an Honorable
    # Mention. Both thresholds are on the PROGRAM COUNT, never a name list.
    for rn, reg in arc["all_region"].items():
        n = reg["programs"]
        assert len(reg["tiers"]) == (2 if n >= jaw.AR_TIER2_MIN_PROGRAMS else 1), (rn, n)
        if n < jaw.AR_HM_MIN_PROGRAMS:
            assert not reg["honorable_mention"], rn
        # HM in the one region that gets it is capped at ONE ENTRY per school.
        from collections import Counter
        c = Counter(r["school"] for r in reg["honorable_mention"])
        assert not c or max(c.values()) <= jaw.AR_HM_PER_SCHOOL, (rn, c.most_common(3))

    # The view serves the same slate from every classification.
    slates = [tuple(sorted(rg["region"] for rg in
                           st.jhsaa_honors_view(w["seed"], "girls", group=g)["regions"]))
              for g in jh.GROUPS]
    assert len(set(slates)) == 1 and slates[0], slates

    # And it reaches a player's honours from whichever class they play in.
    honoured = {p for _rn, _t, r in jaw.region_rows(arc["all_region"])
                for p in jaw.row_pids(r)}
    assert honoured
    for grp in jh.GROUPS:
        merged = {**arc["awards"][grp], "all_region": arc["all_region"]}
        hits = [pid for pid in honoured
                if any("All-Region" in h for h in jaw.honors_for(pid, merged, grp))]
        assert len(hits) == len(honoured), grp


def test_an_expanded_bracket_page_renders_two_draws(archived):
    """‼️ An expanded field renders as TWO trees — the main draw and the Qualifying
    that fed it — because a FRESH draw sits between the First Round and the
    Octofinals, so there is no bracket path across the boundary and one positional
    tree would draw links that do not exist (`_bracket_canvas` halves 2k/2k+1).
    Rendered, not just viewed: a template resolves a wrong shape to an empty box
    with no error anywhere, which is how the TOC page shipped as a toolbar over
    nothing. The fixture's smaller classes scale the 40-field down
    so any group whose archived bracket carries `round_names`
    exercises the split; a 24-shape group keeps the single tree and no tab."""
    arc = archived["arc"]
    expanded = [g for g in jh.GROUPS
                if (arc["brackets"][g] or {}).get("round_names")]
    plain = [g for g in jh.GROUPS
             if not (arc["brackets"][g] or {}).get("round_names")]
    assert expanded, "no expanded bracket in the fixture — the split is untested"
    assert plain, "no 24-shape bracket in the fixture — the old shape is untested"
    html = archived["client"].get(
        f"/jhsaa/bracket?g=girls&group={expanded[0]}").get_data(as_text=True)
    assert 'data-view="qual"' in html and ">Qualifying<" in html
    # both sections carry real cards: the champion is in the main tree, and the
    # Qualifiers Round chip names the qualifying one
    assert arc["brackets"][expanded[0]]["champion"] in html
    html24 = archived["client"].get(
        f"/jhsaa/bracket?g=girls&group={plain[0]}").get_data(as_text=True)
    assert 'data-view="qual"' not in html24


# --- the title board -----------------------------------------------------------

def test_the_title_board_agrees_with_the_program_pages(archived):
    """‼️ THE BOARD IS A FOLD, AND A FOLD THAT DISAGREES WITH WHAT IT FOLDS IS THE
    WHOLE RISK. `jhsaa_title_board` walks each season's archive ONCE and credits
    whoever it names, because asking `_season_row` per program would re-read the year
    ~860 times; that speed is bought by re-deriving numbers the program page derives
    its own way, so the two must land on the same answer. Checked against the ledger
    rows themselves — district titles, unit wins, State finishes, the TOC — not
    against a second copy of this function's arithmetic."""
    w = archived["world"]
    board = {r["school"]: r for r in wd.jhsaa_title_board(w["id"], "girls")["rows"]}
    assert board, "a played season archived no programs at all"
    seen_state = seen_units = 0
    for school in list(board)[:40]:
        seasons = wd.jhsaa_school_seasons(w["id"], "girls", school)
        r = board[school]
        assert r["seasons"] == len(seasons), school
        assert r["dist"] == sum(1 for s in seasons if s["district_title"]), school
        assert r["state_apps"] == sum(1 for s in seasons if s["made_state"]), school
        assert r["CHAMP"] == sum(1 for s in seasons if s["champion"]), school
        assert r["toc"] == sum(1 for s in seasons if s["toc_champion"]), school
        assert r["toc_apps"] == sum(1 for s in seasons if s["made_toc"]), school
        # The road: the board buckets a unit win by the stage that named it, the
        # program page renders the same wins as honour chips. The COUNTS must match
        # even though neither knows how the other groups them.
        units = sum(len(s["unit_wins"]) for s in seasons)
        # `unit_wins` leads with the district title, which is its own column here.
        stage_total = sum(r[s] for _n, s, _l in wd.jhsaa_title_stages())
        assert stage_total + r["dist"] == units, (school, stage_total, units)
        seen_state += r["state_apps"]
        seen_units += stage_total
    assert seen_state and seen_units, "no State runs or unit wins in the sample"


def test_a_state_finish_lands_in_exactly_one_column(archived):
    """A finish is counted DOWN from teams still alive, so the columns are BANDS, not
    round indices — a field that is not a power of two does not halve out of the gate.
    Every entrant must fall in exactly one band: a program that appeared and was
    counted nowhere is a silently short row, which reads as a program that never
    played rather than as a bug."""
    w = archived["world"]
    from app.world import JH_STATE_COLUMNS
    for r in wd.jhsaa_title_board(w["id"], "girls")["rows"]:
        assert sum(r[k] for k, _l in JH_STATE_COLUMNS) == r["state_apps"], r["school"]


def test_the_title_board_page_renders_its_champions(archived):
    """The page, not the function: a table this wide is exactly where a template
    dereferences a key that isn't there and Jinja prints nothing at all."""
    html = archived["client"].get("/jhsaa/titles?g=girls").get_data(as_text=True)
    champs = [nm for nm in (archived["arc"].get("champions") or {}).values() if nm]
    assert champs, "the season crowned nobody"
    for nm in champs:
        assert nm in html, nm
    # every column the view promises is really in the header
    for _n, short, _l in wd.jhsaa_title_stages():
        assert f'data-k="{short}"' in html, short
    # and a champion's row carries a real count, not an empty cell
    assert 'data-k="CHAMP" data-v="1"' in html


# --- the JV participation record -----------------------------------------------

def test_played_survives_the_archive_and_reaches_the_player_page(archived):
    """The JV column on a career, end to end: simulated -> `world_jhsaa_dual.played`
    -> the ledger. A unit test cannot see this — the column has to round-trip SQLite
    and the row has to come back through `_schedule_rows`."""
    w, g = archived["world"], "girls"
    school = next(iter(archived["arc"]["standings"]["9A"].values()))[0]["school"]
    sched = wd.jhsaa_schedule(w["id"], w["year"], g, school)
    jv = [d for d in sched if (d.get("level") or "v") == "jv"]
    assert jv, "no JV duals archived for this program"
    assert all(d["played"] for d in jv), "played did not survive the archive"
    assert all(d["lines"] for d in jv), "the JV box score did not survive the archive"

    # somebody who dressed AND took a court, and their record off the archive
    jv_recs = st._jh_line_records(sched, "jv")
    name = next(n for d in jv for n in d["played"]
                if any(jv_recs.get(n, {"s": [0, 0], "d": [0, 0]})["s"]
                       + jv_recs.get(n, {"s": [0, 0], "d": [0, 0]})["d"]))
    jw, jl, jt = wd.jhsaa_jv_player_record(sched, name)
    assert jw + jl + jt > 0, "played did not round-trip for a courted player"

    # ‼️ THE SALT, NOT "". The name draw is salted, so `build_roster` on a bare salt
    # returns the right pids attached to DIFFERENT PEOPLE and the lookup by name finds
    # nobody — the `_resolve_member` trap, one layer up.
    salt = wd.active_salt(wd.DEFAULT_SEED)
    sc = next(s for s in jh.load_schools(g) if s.name == school)
    roster = jh.build_roster(sc, archived["arc"]["season_year"], salt)
    hit = next((p for p in roster if p.name == name), None)
    assert hit is not None, "a JV participant is not on the program's roster"

    html = archived["client"].get(
        f"/jhsaa/player/{school}/{hit.pid}?g={g}").get_data(as_text=True)
    assert "<th style=\"width:58px\">JV</th>" in html
    # ‼️ THE LEDGER CELL IS THE PLAYER'S OWN PER-COURT JV RECORD (owner
    # correction — "a record next to a person's name has to be that person's"),
    # NEVER `jhsaa_jv_player_record`: that is the TEAM's result in the duals
    # they dressed for, asserted above only as the archive round-trip. This
    # test asserted the team string for a while and passed by coincidence.
    rec = jv_recs[name]
    own = f"{rec['s'][0] + rec['d'][0]}-{rec['s'][1] + rec['d'][1]}"
    assert own in html


def test_a_jv_dual_never_lands_on_the_varsity_record(archived):
    """The whole reason `played` is its own field. `state`'s player view hands the
    WHOLE schedule — both levels — to `_jh_line_records`; only empty `lines` keeps JV
    out of the singles/doubles record and the flight box."""
    w, g = archived["world"], "girls"
    school = next(iter(archived["arc"]["standings"]["9A"].values()))[0]["school"]
    sched = wd.jhsaa_schedule(w["id"], w["year"], g, school)
    varsity = [d for d in sched if (d.get("level") or "v") != "jv"]
    from app.web.state import _jh_line_records
    both, only_v = _jh_line_records(sched), _jh_line_records(varsity)
    assert both == only_v, "filtering by level changed the varsity records — JV leaked"


# --- the toggles actually being wired ----------------------------------------

def test_the_jv_schedule_rows_are_expandable_like_the_varsity_ones(archived):
    """‼️ MARKUP IS NOT WIRING. The JV rows rendered the caret and the hidden line row
    from day one; the click handler bound to `document.currentScript.previousElement-
    Sibling`, i.e. the VARSITY table alone, so nothing listened on the JV one. It looked
    correct and did nothing, which is why it read as "JV toggling is broken"."""
    w, g = archived["world"], "girls"
    school = next(iter(archived["arc"]["standings"]["9A"].values()))[0]["school"]
    html = archived["client"].get(
        f"/jhsaa/school/{school}?g={g}&view=season").get_data(as_text=True)
    assert 'data-pane="jv"' in html
    assert 'data-lines="jv' in html, "no expandable JV row rendered"
    assert 'data-for="jv' in html, "no JV line-score row rendered"
    # the handler must be delegated from the panel, not bound to one table
    assert "previousElementSibling" not in html
    assert "tr[data-lines]" in html and "row.closest('table')" in html
    assert html.count("jh_tabs_script") == 0        # macro, not a literal


def test_the_player_flight_box_toggles_varsity_and_jv(archived):
    """Both halves: the JV pane exists, and `jh_tabs_script` was actually called for
    each bar — `jh_tabs` alone renders a bar that does nothing."""
    w, g = archived["world"], "girls"
    school = next(iter(archived["arc"]["standings"]["9A"].values()))[0]["school"]
    sched = wd.jhsaa_schedule(w["id"], w["year"], g, school)
    jv = [d for d in sched if (d.get("level") or "v") == "jv"]
    name = next(nm for d in jv for ln in d["lines"]
                for nm in (ln["home"] if d["home"] else ln["away"]))
    salt = wd.active_salt(wd.DEFAULT_SEED)
    sc = next(s for s in jh.load_schools(g) if s.name == school)
    hit = next(p for p in jh.build_roster(sc, archived["arc"]["season_year"], salt)
               if p.name == name)
    html = archived["client"].get(
        f"/jhsaa/player/{school}/{hit.pid}?g={g}").get_data(as_text=True)
    assert 'data-tabs="jhflsingles"' in html and 'data-tabs="jhfldoubles"' in html
    assert '[data-tabs="jhflsingles"]' in html, "the singles tab bar has no script"
    assert '[data-tabs="jhfldoubles"]' in html, "the doubles tab bar has no script"
    assert html.count('data-pane="jv"') >= 2      # one pane per flight box


def test_a_players_jv_record_is_their_own_not_the_teams(archived):
    """The JV column showed the TEAM's result in the duals a player dressed for, so a
    kid who dressed for every JV dual carried the program's 15-3-1 beside his own 2-1
    in singles. A record next to a person's name has to be that person's."""
    from app.web.state import _jh_line_records
    w, g = archived["world"], "girls"
    school = next(iter(archived["arc"]["standings"]["9A"].values()))[0]["school"]
    sched = wd.jhsaa_schedule(w["id"], w["year"], g, school)
    jv = [d for d in sched if (d.get("level") or "v") == "jv"]
    assert jv
    mine = _jh_line_records(sched, "jv")
    assert mine, "no JV line records resolved"
    # nobody's own JV record can exceed the courts they were actually named on
    for nm, r in mine.items():
        played = sum(1 for d in jv for ln in d["lines"]
                     if nm in (ln["home"] if d["home"] else ln["away"]))
        assert sum(r["s"]) + sum(r["d"]) == played, nm
    # and the varsity read is untouched by any of it
    assert _jh_line_records(sched) == _jh_line_records(
        [d for d in sched if (d.get("level") or "v") == "v"])


# --- individual state titles on the player header ------------------------------

def test_an_individual_state_champion_gets_a_gold_chip_and_a_gold_name(archived):
    """The header chips, end to end: an archived individual draw's champion ->
    `title_chips` on the player view -> a gold chip in the identity block, and the
    name itself carries the `champ` class. Read off the REAL archive, because the
    chip's champion predicate (`tag == "CHAMP"`) only exists once a draw is stored."""
    from app import jhsaa_individuals as ji
    w, g = archived["world"], "girls"
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT grp, flight, data FROM world_jhsaa_individual"
            " WHERE world_id=? AND year=? AND gender=? ORDER BY grp, flight",
            (w["id"], w["year"], g)).fetchone()
    finally:
        conn.close()
    assert row is not None, "no individual draw archived"
    d = json.loads(row["data"])
    champ_ix = d.get("champion")
    assert champ_ix is not None, "the draw crowned nobody"
    entry = d["entries"][champ_ix]
    school, pid = entry["school"], entry["players"][0]["pid"]

    view = st.jhsaa_player_view(wd.DEFAULT_SEED, g, school, pid)
    assert view["found"]
    assert view["individual_titles"] >= 1
    chip = (f"{archived['arc']['season_year']} {row['grp']} "
            f"{ji.FLIGHT_NAMES[row['flight']]} State Champion")
    assert chip in view["title_chips"]

    # honour chips are structured, MERGED by honour, and never repeat a text —
    # the "duplicate" chips were per-season honours rendered without their year
    texts = [h["text"] for h in view["honors"]]
    assert len(texts) == len(set(texts))
    for h in view["honors"]:
        assert h["years"].startswith("'") if h["years"] else True
    assert view["honors_total"] == sum(len(s["honors"]) for s in view["seasons"])

    html = archived["client"].get(
        f"/jhsaa/player/{school}/{pid}?g={g}").get_data(as_text=True)
    assert f'<span class="jh-chip gold">{chip}</span>' in html
    assert 'class="champ"' in html, "the champion's name is not gold"


def test_a_player_without_a_title_keeps_a_plain_name(archived):
    """The gold name is a champion's alone — a champion's own team-mate who never
    won a draw renders without the class."""
    w, g = archived["world"], "girls"
    school = next(iter(archived["arc"]["standings"]["9A"].values()))[0]["school"]
    salt = wd.active_salt(wd.DEFAULT_SEED)
    sc = next(s for s in jh.load_schools(g) if s.name == school)
    roster = jh.build_roster(sc, archived["arc"]["season_year"], salt)
    hit = next(p for p in roster
               if not st.jhsaa_player_view(
                   wd.DEFAULT_SEED, g, school, p.pid)["individual_titles"])
    view = st.jhsaa_player_view(wd.DEFAULT_SEED, g, school, hit.pid)
    assert view["title_chips"] == []
    html = archived["client"].get(
        f"/jhsaa/player/{school}/{hit.pid}?g={g}").get_data(as_text=True)
    assert 'class="champ"' not in html


def test_a_rivalry_dual_is_played_and_the_card_marks_it(archived):
    """Crosstown rivalries (owner rule 2026-09), through the whole stack: the fixture
    is on the schedule and the card says which invitational it was.

    ‼️ RENDERED, not just computed. `d.rival` is a new attribute the template
    dereferences, and Jinja resolves a missing one to Undefined and prints nothing — a
    template is the one place here where a wrong type ships a page instead of raising
    (`brk_canvas`, `AAR-jhsaa-individual-state-tournaments.md`). The only way to know
    the chip is there is to look at the HTML."""
    import app.world as wd
    w = archived["world"]
    schools = jh.load_schools("girls")
    rivals = jh.rival_map(schools)
    by = {s.name: s for s in schools}
    marked = 0
    for name, mates in sorted(rivals.items()):
        cross = [b for b in mates if b in by and
                 (by[b].group, by[b].district) != (by[name].group, by[name].district)]
        if not cross:
            continue
        sched = wd.jhsaa_school_history(w["id"], "girls", name)["seasons"]
        if not sched:
            continue
        html = archived["client"].get(
            f"/jhsaa/school/{name}?g=girls&view=season").get_data(as_text=True)
        if "RIVALRY" not in html:
            continue
        for opp in cross:                       # the chip sits on the rival's row
            assert opp in html, (name, opp)
        marked += 1
        if marked >= 3:
            break
    assert marked >= 3, "no rendered card carried a rivalry chip"


# --- the Epiregional on the page --------------------------------------------------

def test_the_epiregional_panel_and_match_center_label(archived):
    """The Zonal champions' play-in (owner rule 2026-09) on every surface that
    shows it: its OWN panel on the bracket page (never a tree column), the bye
    list worded for the draw's real shape — a 32 has no byes and must not list
    its top eight under "Byes" — and the Match Center naming the phase rather than
    falling through to "Invitational" (the non-district fallback)."""
    arc, w, g = archived["arc"], archived["world"], "girls"
    for grp in jh.GROUPS:
        epi = (arc.get("epiregional") or {}).get(grp) or {}
        assert epi.get("rounds") and epi["rounds"][0], grp
        html = archived["client"].get(
            f"/jhsaa/bracket?g={g}&group={grp}").get_data(as_text=True)
        assert f"{grp} Epiregionals" in html
        assert epi["rounds"][0][0]["unit"] in html
        n = len(arc["brackets"][grp]["field"])
        if n & (n - 1) == 0:
            assert "Seed lines 1–8" in html and ">Byes:" not in html, grp
        elif arc["brackets"][grp].get("round_names"):
            assert "Double byes" in html, grp
        else:
            assert "Byes:" in html, grp
    # the Match Center page for one Epiregional dual
    grp = jh.GROUPS[0]
    gm = (arc["epiregional"][grp]["rounds"][0])[0]
    sched = wd.jhsaa_schedule(w["id"], w["year"], g, gm["home"])
    row = next(d for d in sched if d.get("phase") == "epiregional")
    html = archived["client"].get(f"/jhsaa/dual/{row['id']}?g={g}").get_data(as_text=True)
    assert "Epiregional" in html and "Invitational" not in html


def test_the_research_export_carries_the_jv_events(archived):
    """‼️ THE JV EVENTS ARE IN THE EXPORT (owner rule 2070, reversing the 2026-08
    varsity-only decision): the JV season's duals ride in duals.csv labelled
    level='jv' with their elastic shape stated, the JV Team State Tournament ships
    as jhsaa_jv_state.json plus its phase='jv_state' duals, and the JV
    Singles/Doubles draws sit in jhsaa_individuals.json under the classless "ALL"
    key — which a classification-scoped export must KEEP (the group-scoped-reader
    trap). Through the ARCHIVE path, which is the only path a real export uses."""
    import csv as _csv
    import io as _io
    import json as _json
    from app.research_export import build_jhsaa
    from app import world as wd2
    y = archived["arc"]["season_year"]
    files = build_jhsaa(y, "girls")
    rows = list(_csv.DictReader(_io.TextIOWrapper(_io.BytesIO(files["duals.csv"]))))
    jv = [r for r in rows if r["level"] == "jv"]
    assert jv, "no JV duals reached the export"
    assert all(r["level"] in ("v", "jv") for r in rows)
    # a JV row states its elastic shape; varsity rows leave the column empty
    assert all(r["shape"] for r in jv)
    assert all(not r["shape"] for r in rows if r["level"] == "v")
    # a tied JV dual names no winner; an untied one always does
    for r in jv:
        assert (r["tied"] == "1") == (not r["winner_program_id"]), r
    # the JV Team State Tournament: its own JSON, and its duals in the table
    jvs = _json.loads(files["jhsaa_jv_state.json"])
    if wd2.jhsaa_jv_state(archived["world"]["id"], archived["world"]["year"],
                          "girls"):
        assert jvs.get("champion") and jvs.get("regions")
        assert any(r["phase"] == "jv_state" for r in jv)
    # the classless JV individual draws survive a class-scoped export
    for scope in ("all", "7A"):
        indiv = _json.loads(build_jhsaa(y, "girls", scope)["jhsaa_individuals.json"])
        assert "ALL" in indiv.get("girls", {}), scope
        assert {"JVS", "JVD"} <= set(indiv["girls"]["ALL"]), scope


def test_the_jv_regional_bracket_renders_and_switches(archived):
    """‼️ The regional draws were ALWAYS archived (`ev["regions"]`, every season) and
    never rendered — which from the site reads as the brackets not being preserved
    year over year (owner report 2070). One region at a time through a <select>;
    checked by RENDERING, because a template dereferencing the wrong type paints an
    empty box instead of raising."""
    from app import world as wd2
    ev = wd2.jhsaa_jv_state(archived["world"]["id"], archived["world"]["year"],
                            "girls")
    if not ev or not ev.get("regions"):
        import pytest as _pytest
        _pytest.skip("no JV state event archived in this fixture")
    regions = sorted(ev["regions"])
    html = archived["client"].get("/jhsaa/jv-state?g=girls").get_data(as_text=True)
    assert "Regional Championships" in html
    for rn in regions:                      # every region is offered in the switcher
        assert rn in html
    # switching regions shows THAT region's champion on its bracket
    rn = regions[-1]
    html2 = archived["client"].get(
        f"/jhsaa/jv-state?g=girls&region={rn}").get_data(as_text=True)
    champ = ev["regions"][rn].get("champion")
    assert champ and champ in html2
    assert f"{rn} Regional" in html2
