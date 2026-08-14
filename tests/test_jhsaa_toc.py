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
            f"/jhsaa/school/{champ}?g=girls").get_data(as_text=True)
        assert "TOURNAMENT OF CHAMPIONS" in html
        assert f"{grp} STATE CHAMPION" in html
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
