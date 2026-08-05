"""The NCAA bracket page: a locked draw, and a real elimination tree.

Two failures lived here and both were invisible from the outside — the numbers all
looked plausible:

  1. The seeded field was RE-DERIVED every time anything asked for it, and one of
     the committee-score inputs (recent form) counted the bracket being seeded. So
     the seeds and the S-curve region split drifted as the tournament played: teams
     were labelled with regions they were never drawn into, a first-round game
     showed a 5-seed, and a team that had dropped out of the recomputed field
     rendered with no seed at all.
  2. The page was a set of round columns, so nothing said which two matchups fed
     the next one.
"""
import json

import pytest

import app.seasonmode as sm
from app import regions as R
from app.web import state as wstate


@pytest.fixture
def db(tmp_path):
    sm.DB_PATH = str(tmp_path / "season.db")
    sm.init_schema()
    yield


def _dual(conn, sid, rno, bpos, home, away, name, winner=0):
    conn.execute("INSERT INTO duals (season_id, week, round, conf, is_conf, round_no, bpos,"
                 " home, away, status, home_points, away_points, winner)"
                 " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (sid, 20, "NCAA", name, 0, rno, bpos, home, away, "final", 6, 1, winner))


def _draw_96(conn, sid, field):
    """Write the opening round + Round of 64 of a 96-team regional draw, exactly as
    `_region_play_in` / `_region_main_draw` lay them out (home always wins)."""
    regs = R.scurve_regions(field)
    for r in range(4):
        for g in range(8):
            _dual(conn, sid, 1, r * 8 + g, regs[r][8 + g], regs[r][23 - g], "First Round")
    for slot, r in enumerate(R.MAIN_DRAW_ORDER):
        for k in range(8):
            bye = regs[r][R.BYE_SEQ[k] - 1]
            feeder = regs[r][8 + (8 - R.BYE_SEQ[k])]        # that line's play-in winner
            _dual(conn, sid, 2, slot * 8 + k, bye, feeder, "Round of 64")


def test_drawn_positions_reads_region_and_seed_off_the_bracket(db):
    """A bracket records where it was drawn: region from `bpos`, seed line from the
    slot. That is what lets a season drawn before the field was locked still label
    itself correctly."""
    field = [f"S{i:02d}" for i in range(96)]
    conn = sm._db()
    _draw_96(conn, 1, field)
    conn.commit()
    exact, loose = sm._drawn_positions(conn, 1, 96)
    conn.close()
    regs = R.scurve_regions(field)
    for r in range(4):
        for line in range(1, 17):                    # byes (1-8) and play-in homes (9-16)
            assert exact[regs[r][line - 1]] == (r, line)
        for line in range(17, 25):                   # the opening round's away side:
            assert loose[regs[r][line - 1]] == r     # region only — its line isn't recorded
            assert regs[r][line - 1] not in exact


def test_honour_drawn_field_pins_a_shuffled_field_back_onto_its_bracket(db):
    """The repair path: hand it a field in the wrong order (what a re-derivation
    produces mid-tournament) and it comes back matching the bracket on the board."""
    field = [f"S{i:02d}" for i in range(96)]
    conn = sm._db()
    _draw_96(conn, 1, field)
    conn.commit()
    shuffled = field[48:] + field[:48]                # a badly drifted re-derivation
    fixed = sm._honour_drawn_field(conn, 1, shuffled)
    conn.close()
    assert sorted(fixed) == sorted(field) and len(fixed) == 96
    # Region membership is recovered for every team, seed lines 1-16 exactly.
    assert R.region_index_of(fixed) == R.region_index_of(field)
    for r, members in enumerate(R.scurve_regions(fixed)):
        assert members[:16] == R.scurve_regions(field)[r][:16]


def test_honour_drawn_field_leaves_a_field_that_already_matches_alone(db):
    """The validation path, and why it matters: a correct field carries the eight
    lines per region the bracket can't name, so rebuilding it would LOSE precision.
    Agreement means hands off."""
    field = [f"S{i:02d}" for i in range(96)]
    conn = sm._db()
    _draw_96(conn, 1, field)
    conn.commit()
    assert sm._honour_drawn_field(conn, 1, list(field)) == field
    conn.close()


def test_uncurve_inverts_the_scurve(db):
    field = list(range(96))
    assert sm._uncurve(R.scurve_regions(field)) == field


def test_committee_score_ignores_the_bracket_it_is_seeding(db):
    """The drift bug: the seed score must not move when postseason duals land, or
    the field is a different field every time the page is opened."""
    sid = sm.create_season("D2", "women", seed=5)
    for _ in range(6):
        sm.advance(sid)
    before = sm.committee_seed_score(sid, set())
    assert before                                     # the season has enough results to rank
    conn = sm._db()
    schools = list(before)[:8]
    for i in range(0, 8, 2):                          # postseason results arrive
        _dual(conn, sid, 1, i, schools[i], schools[i + 1], "Round of 64")
    conn.commit()
    conn.close()
    sm._pi_cache.clear()
    assert sm.committee_seed_score(sid, set()) == before


def test_team_form_still_defaults_to_every_round(db):
    """Narrowing the corpus is for the seeding path only — the season page's form
    column still counts the conference tournament and the NCAAs."""
    sid = sm.create_season("D2", "women", seed=5)
    for _ in range(6):
        sm.advance(sid)
    full = sm.team_form(sid)
    conn = sm._db()
    school = list(full)[0]
    _dual(conn, sid, 1, 0, school, list(full)[1], "Round of 64")
    conn.commit()
    conn.close()
    assert sm.team_form(sid)[school]["w"] == full[school]["w"] + 1
    assert sm.team_form(sid, sm.SEED_ROUNDS)[school]["w"] == full[school]["w"]


# --------------------------------------------------------------------------
# The bracket canvas — geometry the page renders straight into HTML/SVG
# --------------------------------------------------------------------------

def _m(home, away, winner=None):
    return {"home": {"school": home, "region": "X"}, "away": {"school": away, "region": "X"},
            "winner": winner, "played": winner is not None, "bpos": 0, "region": "X"}


def _round(name, pairs):
    return {"name": name, "matchups": [_m(*p) for p in pairs]}


def test_canvas_centres_every_matchup_between_its_two_feeders():
    cols = [_round("Round of 64", [(f"A{i}", f"B{i}", f"A{i}") for i in range(8)]),
            _round("Round of 32", [(f"A{2*i}", f"A{2*i+1}", f"A{2*i}") for i in range(4)]),
            _round("Round of 16", [(f"A{4*i}", f"A{4*i+2}", f"A{4*i}") for i in range(2)]),
            _round("Regional Final", [("A0", "A4", "A0")])]
    cv = wstate._bracket_canvas(cols)
    by_col: dict = {}
    for c in cv["cards"]:
        by_col.setdefault(c["col"], []).append(c)
    for i in (1, 2, 3):
        for k, card in enumerate(by_col[i]):
            feeders = by_col[i - 1][2 * k:2 * k + 2]
            assert card["y"] == pytest.approx(sum(f["y"] for f in feeders) / 2)
    # One link per feeder, and every one is live (each winner is standing in the
    # card the link points at) — that is what makes a path traceable.
    assert len(cv["links"]) == 8 + 4 + 2
    assert all(l["won"] for l in cv["links"])
    assert cv["height"] > cv["card_h"] * 8                 # a real canvas, not stacked cards


def test_canvas_lays_a_play_in_level_with_the_slot_it_feeds():
    """The opening round is the same width as the round it feeds — one source per
    destination — so it sits level with its slot instead of halving into it."""
    cols = [_round("First Round", [(f"P{i}", f"Q{i}", f"P{i}") for i in range(8)]),
            _round("Round of 64", [(f"BYE{i}", f"P{i}", f"BYE{i}") for i in range(8)]),
            _round("Round of 32", [(f"BYE{2*i}", f"BYE{2*i+1}", f"BYE{2*i}") for i in range(4)])]
    cv = wstate._bracket_canvas(cols)
    playin = [c for c in cv["cards"] if c["col"] == 0]
    r64 = [c for c in cv["cards"] if c["col"] == 1]
    assert [c["y"] for c in playin] == [c["y"] for c in r64]
    assert all(c["playin"] for c in playin) and not any(c["playin"] for c in r64)
    assert cv["columns"][0]["playin"] and not cv["columns"][1]["playin"]


def test_ladders_order_the_opening_round_by_the_slot_it_feeds():
    """The one hop that isn't positional: the bracketer swaps which play-in winner
    faces which bye, so the column has to be reordered by who fed whom or the lines
    cross."""
    rounds = [
        {"name": "First Round", "national": False,
         "matchups": [_m("P0", "Q0", "P0"), _m("P1", "Q1", "P1"), _m("P2", "Q2", "P2")]},
        {"name": "Round of 64", "national": False,
         "matchups": [_m("B0", "P2", "B0"), _m("B1", "P0", "B1"), _m("B2", "P1", "B2")]},
    ]
    for i, m in enumerate(rounds[0]["matchups"]):
        m["bpos"] = i
    ladders = wstate._region_ladders(rounds, ["X"])
    assert [m["winner"] for m in ladders[0]["rounds"][0]["matchups"]] == ["P2", "P0", "P1"]
    cv = ladders[0]["canvas"]
    assert all(l["won"] for l in cv["links"])          # every play-in feeds a real slot
