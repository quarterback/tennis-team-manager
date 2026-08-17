"""Rivalries — pairs of schools that must never be separated.

Owner rule 2027-08. A rivalry is a fact about two programs, not about their
enrollments, so it outranks every mechanism that would move one of them:
reclassification, league assignment and playing up all have to keep the pair
together or leave it alone.

‼️ WHY IT NEEDS A RULE AT ALL. A district is `(classification, name)`, so once two
rivals sit in different classifications there is no league either could join to be
with the other — the split is unrepairable short of another reclassification. The
2027-08 enrollment cascade did exactly this: Condotti Vanguard Academy (1,666)
cleared a 1,638 cut line, Romero-Finniski (1,526) did not, and two Ashbury schools
that had shared Metro League for as long as the association existed ended up a class
apart. Every individual number was correct.

This covers rivalries and nothing else — no season is simulated.
"""
import importlib.util
import os

from app import jhsaa as jh

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _importer():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_REPO, "scripts", "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_rivals_share_a_classification_and_a_league():
    """The invariant, asserted against the shipped data in BOTH genders — a rivalry
    that only holds for the girls' field is not a rivalry."""
    m = _importer()
    for gender in ("girls", "boys"):
        by_name = {s.name: s for s in jh.load_schools(gender)}
        for pair in m.RIVALRIES:
            live = [by_name[n] for n in pair if n in by_name]
            if len(live) < 2:
                continue
            assert len({s.group for s in live}) == 1, (gender, pair)
            assert len({s.district for s in live}) == 1, (gender, pair)


def _reclassify():
    spec = importlib.util.spec_from_file_location(
        "jhsaa_reclassify", os.path.join(_REPO, "scripts", "jhsaa_reclassify.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_rivalry_is_not_promoted_unless_every_member_clears_the_cut():
    """A pair moves as a block or not at all.

    ‼️ Asserted on the MECHANISM, not on the shipped data. The obvious data check —
    "nobody sits above a cut line the pair did not all clear" — asserts the opposite
    of the rule: a school held back BECAUSE its rival fell short is by definition
    above the line, so the correct outcome fails the check. Being over the line and
    staying put is the whole behaviour."""
    m, rc = _importer(), _reclassify()
    line = m.PROMOTE_ABOVE["7A"]
    m.RIVALRIES = [("Rival One", "Rival Two")]

    def rows(second):
        return [{"name": "Rival One", "classification": "7A", "group": "7A",
                 "enrollment": line + 20},
                {"name": "Rival Two", "classification": "7A", "group": "7A",
                 "enrollment": second},
                {"name": "Loner", "classification": "7A", "group": "7A",
                 "enrollment": line + 20}]

    held = rows(line - 100)                       # one clears, one does not
    rc.promote(held, m)
    assert [r["classification"] for r in held] == ["7A", "7A", "8A"], held

    both = rows(line + 5)                         # both clear
    rc.promote(both, m)
    assert [r["classification"] for r in both] == ["8A", "8A", "8A"], both


def test_a_league_cut_never_falls_between_rivals():
    """`draw_districts` sorts a pair adjacently AND walks the block boundary past it.
    Adjacency alone is not enough — the boundary landing exactly between them is
    what split Condotti and Romero-Finniski on a 7A redraw, with nothing having
    moved either school."""
    m = _importer()
    rows = [dict(name=f"s{i:03d}", area="A", county="C", city="T",
                 girls=True, boys=True) for i in range(97)]
    # Make two of them rivals, placed so a naive cut would separate them.
    rows[11]["name"], rows[12]["name"] = "Rival One", "Rival Two"
    m.RIVALRIES = [("Rival One", "Rival Two")]
    m._CANONICAL = {}
    cities = {"T": {"county": "C"}}
    out = m.draw_districts(rows, cities, "7A")
    assert out["Rival One"] == out["Rival Two"], out


def test_every_named_rivalry_is_live_in_the_data():
    """A rivalry naming a school that no longer exists is silently no rule at all —
    the same trap `OWNER_EDICTS` is verified against."""
    m = _importer()
    names = {s.name for s in jh.load_schools("girls")} | {
        s.name for s in jh.load_schools("boys")}
    for pair in m.RIVALRIES:
        missing = [n for n in pair if n not in names]
        assert not missing, (pair, "names nobody in the association", missing)
