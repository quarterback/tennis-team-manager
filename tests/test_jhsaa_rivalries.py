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


# --- CROSS-TOWN RIVALRIES: the annual fixture (owner rule 2026-09) ------------
#
# The rules above keep a named pair TOGETHER; these put the town on the schedule.
# `import_jhsaa.RIVALRIES` is a classification-integrity constraint applied once at
# import; `jhsaa.RIVAL_OVERRIDES` + `jhsaa.rival_map` decide who plays whom every
# season. Both tables are needed and the app cannot read `scripts/`, so the agreement
# between them is asserted here rather than shared.


def test_the_two_rivalry_tables_agree():
    """‼️ Every `import_jhsaa.RIVALRIES` pair must also be a `RIVAL_OVERRIDES` pair.
    Without the entry the season-time derivation quietly breaks the named rivalry the
    moment a third program in town has a better claim on the seat — Alameda and
    Condotti Vanguard Academy are both Ashbury 7A, so on class alone Alameda takes it
    and the association's oldest rivalry stops being played. Nothing errors; the card
    just stops carrying the one dual the table exists to protect."""
    named = {frozenset(p) for p in _importer().RIVALRIES}
    coded = {frozenset(p) for p in jh.RIVAL_OVERRIDES}
    assert named <= coded, sorted(map(sorted, named - coded))


def test_a_named_pair_survives_a_better_claim_in_town():
    """The override in action, against the shipped data: Condotti keeps Romero-Finniski
    even though Alameda is the same class, the same town and alphabetically first."""
    for gender in ("girls", "boys"):
        rm = jh.rival_map(jh.load_schools(gender))
        for a, b in jh.RIVAL_OVERRIDES:
            if a in rm and b in rm:
                assert b in rm[a] and a in rm[b], (gender, a, b)


def test_rivals_are_symmetric_capped_and_in_town():
    """The three structural properties of the derivation, over the whole association.
    The cap binds the DERIVED pairs only — an override is a decision and takes its
    seat ahead of them, and a program carrying MORE overrides than the cap (a
    returned North holds its town triangle plus its cross-town twin) simply plays
    them all; derived pairs never push anyone past the cap. Overrides are likewise
    exempt from the same-town and class-gap gates — an owner-declared rivalry
    answers to no gate."""
    overrides = {frozenset(p) for p in jh.RIVAL_OVERRIDES}
    ov_of: dict[str, set[str]] = {}
    for x, y in jh.RIVAL_OVERRIDES:
        ov_of.setdefault(x, set()).add(y)
        ov_of.setdefault(y, set()).add(x)
    for gender in ("girls", "boys"):
        schools = jh.load_schools(gender)
        by = {s.name: s for s in schools}
        rm = jh.rival_map(schools)
        assert set(rm) == set(by)
        for a, mates in rm.items():
            held = ov_of.get(a, set()) & mates
            assert len(mates) <= max(jh.RIVALS_PER_PROGRAM, len(held)), (a, sorted(mates))
            assert len(mates - held) <= jh.RIVALS_PER_PROGRAM, (a, sorted(mates))
            for b in mates:
                assert a in rm[b], (a, b)                     # symmetric
                assert a != b
                if frozenset((a, b)) in overrides:
                    continue
                assert by[a].city == by[b].city, (a, b)       # same town, always
                gap = abs(jh._GROUP_IX[by[a].group] - jh._GROUP_IX[by[b].group])
                assert gap <= jh.RIVAL_MAX_GAP, (a, by[a].group, b, by[b].group)


def test_the_owners_two_towns_actually_play_each_other():
    """The report, as data. Cherry Hill's campuses and Port Meridian's nine programs
    are spread across leagues and classifications, so the ordinary non-district draw
    met them in some seasons and not others — owner: "none of the cherry hill schools
    or port meridian schools play each other much/enough and that's not realistic."

    Cherry Hill is the stem case (three campuses of one name, so they take each other
    before anything else in town); Port Meridian is the metro case (nine programs, six
    leagues, 9A down to 3A). Every program in both must end up with a rival."""
    for gender in ("girls", "boys"):
        schools = jh.load_schools(gender)
        rm = jh.rival_map(schools)
        stem = [s for s in schools if s.name.startswith("Cherry Hill")]
        meridian = [s for s in schools if s.city == "Port Meridian"]
        assert len(stem) >= 2 and len(meridian) >= 5, gender
        for s in stem + meridian:
            assert rm[s.name], (gender, s.name, "no cross-town rival")
        # Cherry Hill's campuses take EACH OTHER, never a stranger across town.
        names = {s.name for s in stem}
        for s in stem:
            assert rm[s.name] & names, (gender, s.name, sorted(rm[s.name]))


def test_a_rivalry_is_played_every_season_and_the_venue_alternates():
    """The fixture itself, through the shipped scheduler. Two seasons, because the
    property under test is annual — and the venue must swap between them: `play_dual`
    makes its first argument the host and `home_court` gives the host a real lift, so a
    fixed order would hand one school the advantage for the life of the save."""
    where = {}
    for year in (2030, 2031):
        by_group = {}
        for group in ("8A", "7A"):
            d = jh.districts("girls", group)
            by_group[group] = {n: jh.district_teams(d[n], year)
                               for n in sorted(d)[:4]}
        teams, _p = jh.play_regular_season(by_group, year, "girls")
        by = {t.school.name: t for t in teams}
        rm = jh.rival_map([t.school for t in teams])
        checked = 0
        for a, mates in rm.items():
            for b in mates:
                if a > b or b not in by:
                    continue
                A, B = by[a].school, by[b].school
                if (A.group, A.district) == (B.group, B.district):
                    continue                      # league-mates: home and away already
                row = [x for x in by[a].schedule if x["opp"] == b]
                assert row, (year, a, b, "codified rivals never met")
                where.setdefault((a, b), []).append(row[0]["home"])
                checked += 1
        assert checked, "the fixture held no cross-league rivalry"
    both = [v for v in where.values() if len(v) == 2]
    assert both and all(v[0] != v[1] for v in both), where


def test_the_kill_switch_removes_every_fixture():
    """`RIVALRIES_ENABLED` off must be the pre-feature season, not a smaller one —
    the first diagnostic when a rung is slow (`SHOWCASE_ENABLED`'s idiom)."""
    schools = jh.load_schools("girls")[:40]
    teams = jh.district_teams(schools, 2030)
    played = {id(t): set() for t in teams}
    assert jh._rivalry_pairs(teams, 2030, played)
    jh.RIVALRIES_ENABLED = False
    try:
        played = {id(t): set() for t in teams}
        assert jh._rivalry_pairs(teams, 2030, played) == []
        assert not any(played.values())
    finally:
        jh.RIVALRIES_ENABLED = True


def test_the_fixture_is_reserved_before_the_early_draw():
    """‼️ The early matcher is ALLOWED to pair two town rivals — a rival inside its ±1
    class gate is an ordinary candidate to it — and when it did, that random draw
    became the annual fixture. The dual was then played at the early window's 5S/2D
    shape rather than the league's, and its host was whichever side the matcher put
    first, so the venue could stay with one school two seasons running. Reserving the
    pairs before the first draw is what makes the fixture a fixture.

    So: no rivalry dual may be played in the early window, and every one must carry the
    league shape."""
    by_group = {}
    for group in ("8A", "7A"):
        d = jh.districts("girls", group)
        by_group[group] = {n: jh.district_teams(d[n], 2030) for n in sorted(d)[:4]}
    teams, _p = jh.play_regular_season(by_group, 2030, "girls")
    by = {t.school.name: t for t in teams}
    rm = jh.rival_map([t.school for t in teams])
    checked = 0
    for a, mates in rm.items():
        for b in mates:
            if a > b or b not in by:
                continue
            A, B = by[a].school, by[b].school
            if (A.group, A.district) == (B.group, B.district):
                continue
            rows = [x for x in by[a].schedule if x["opp"] == b]
            assert len(rows) == 1, (a, b, "played more than once")
            assert rows[0]["phase"] != jh.EARLY_FORMAT_PHASE, (a, b, rows[0]["phase"])
            assert rows[0]["phase"] == "regular", (a, b, rows[0]["phase"])
            checked += 1
    assert checked, "the fixture held no cross-league rivalry"
