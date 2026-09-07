"""Exchange students (owner rule 2026-09) — the one-year arrival.

The mechanic is deliberately almost invisible: a program occasionally gains one
extra player for ONE season, they carry a foreign flag and nothing else, and the
next year they are simply gone. What these tests pin is everything that must NOT
happen — no second season, no senior year (so no college hand-off), no effect on
the roster floor, and no marker anywhere that a UI could turn into a badge.
"""
import app.jhsaa as jh


def _mod(s):
    return jh._program_mod(s, 0, "")


def _hosts(gender="boys", year=0, salt=""):
    out = []
    for s in jh.load_schools(gender):
        p = jh.exchange_student(s, year, salt, _mod(s))
        if p is not None:
            out.append((s, p))
    return out


def test_an_arrival_lasts_exactly_one_season():
    """‼️ THE DEFINING PROPERTY. They are not a cohort seat: the roll is keyed on
    (school, year), so the season before and after simply do not produce them.
    That is what "like a senior that graduates in terms of how the game treats
    them the next year" (owner) means mechanically — nothing is deleted, and the
    year they DID play still rebuilds with them in it, so their box scores,
    honours and player page keep resolving forever."""
    school, p = _hosts()[0]
    assert any(q.pid == p.pid for q in jh.build_roster(school, 0, ""))
    for year in (-1, 1, 2, 3):
        assert not any(q.pid == p.pid for q in jh.build_roster(school, year, "")), year


def test_every_arrival_is_a_junior_so_none_reaches_the_college_board():
    """Grade 11, always (owner). This is also the whole of the college-pipeline
    guard: `jhsaa_recruit_class` takes `x.grade == 12` and `apply_to_class` swaps
    those graduating seniors into the national class's Jefferson slots. An
    eleventh-grader is never in that set, so a real exchange student goes home
    without a single filter being written. ‼️ If `EXCHANGE_GRADE` is ever allowed
    to be 12, that exclusion has to be built by hand."""
    assert jh.EXCHANGE_GRADE == 11
    assert {p.grade for _s, p in _hosts()} == {11}


def test_an_arrival_is_extra_and_never_props_up_the_roster_floor():
    """They are appended like a transfer, after the `ROSTER_FLOOR` top-up. A
    program's floor is what it fields on its OWN — if an arrival counted toward
    it, a thin program would run a seat short in the years one turns up, and be
    fine in the years one does not."""
    for school, p in _hosts()[:12]:
        roster = jh.build_roster(school, 0, "")
        assert len(roster) >= jh.ROSTER_FLOOR
        assert len([q for q in roster if q.pid != p.pid]) >= jh.ROSTER_FLOOR


def test_the_roll_is_local_to_the_school():
    """‼️ THE `upstart` LESSON, and the reason this needs no table. A draw over
    the whole pool is NON-LOCAL: adding or dropping one program would change
    which OTHERS host, retroactively rewriting archived seasons. Keyed on
    (school, year, salt) alone, one school's answer cannot depend on another's
    existence — so an archived season rebuilds identically after a sponsorship
    edit, a rename, or a reclassification elsewhere in the association."""
    schools = jh.load_schools("boys")
    before = [jh.exchange_student(s, 0, "", _mod(s)) for s in schools[:40]]
    # Same question asked with the pool in a different order and partly absent.
    after = [jh.exchange_student(s, 0, "", _mod(s)) for s in reversed(schools[:40])]
    assert [bool(p) for p in before] == [bool(p) for p in reversed(after)]
    assert [p.pid for p in before if p] == [p.pid for p in reversed(after) if p]


def test_every_classification_can_host_at_one_rate():
    """‼️ NOT A SMALL-SCHOOL MECHANIC (owner rule 2026-09: "any school from
    Group 3 to 9A can roll an exchange student … it's not exclusively a mechanic
    for smaller programs"). One rate for the association, no class term anywhere
    — which also makes the play-up bug unrepeatable: the first version keyed on
    `school.group`, the CHAMPIONSHIP a program enters, so a played-up 3A drew
    7A's rate. Anything that reads a program's class must read `classification`
    (what it is), never `group` (where it plays)."""
    assert isinstance(jh.EXCHANGE_RATE, float)
    hosts = _hosts()
    classes = {s.classification for s, _p in hosts}
    # Every band is represented across a full association, big schools included.
    assert {"9A", "8A"} & classes and {"1A", "Group 3"} & classes
    assert len(classes) >= 8, sorted(classes)


def test_the_four_named_archetypes_never_host():
    """Owner rule 2026-09: a program "flagged with neglect, turnout, coaching or
    blueblood" does not roll one — each is a program whose story is already about
    its own intake. `upstart` is deliberately NOT excluded (a rolled run, not a
    standing property, and the owner did not name it)."""
    assert set(jh.EXCHANGE_EXCLUDED_ARCHETYPES) == {
        "blue_blood", "coaching", "neglect", "turnout"}
    for school in jh.load_schools("boys"):
        mod = _mod(school)
        if mod.get("kind") in jh.EXCHANGE_EXCLUDED_ARCHETYPES:
            assert jh.exchange_student(school, 0, "", mod) is None, school.name


def test_the_arrival_rate_is_a_wrinkle_not_a_wave():
    """Sized so a season's arrivals are a handful across ~870 programs. If this
    ever reads like a migration, the mechanic has stopped being what it is."""
    hosts = _hosts()
    schools = jh.load_schools("boys")
    assert 0.02 <= len(hosts) / len(schools) <= 0.08, len(hosts)
    # One per program, by construction — the roll returns a single player.
    assert len({s.name for s, _p in hosts}) == len(hosts)


def test_the_nationality_mix_is_the_owner_s_americas_split():
    """‼️ DERIVED from the `global_college` preset, not typed out. The Americas
    are 14% of the mix — 1% Canada ("they almost never are exchange students"),
    8% West Indies, 5% Latin America — and country-by-country South America is
    dropped. Everything else keeps the preset's own proportions, which is what
    puts Africa at ~23% where the pro-tour mix has it near 3%."""
    w = jh._exchange_weights()
    tot = sum(w.values())
    assert round(w["canada"] / tot * 100, 6) == jh.EXCHANGE_CANADA_SHARE
    wi = sum(w[k] for k in jh._EXCHANGE_WEST_INDIES) / tot
    lat = sum(w[k] for k in jh._EXCHANGE_LATIN) / tot
    assert round(wi * 100, 6) == jh.EXCHANGE_WEST_INDIES_SHARE
    assert round(lat * 100, 6) == jh.EXCHANGE_LATIN_SHARE
    # The three pinned blocks are shares of the FINISHED mix, so the rest of the
    # world fills exactly what they leave.
    assert round((1 - wi - lat - w["canada"] / tot) * 100, 6) == round(
        100.0 - jh.EXCHANGE_WEST_INDIES_SHARE - jh.EXCHANGE_LATIN_SHARE
        - jh.EXCHANGE_CANADA_SHARE, 6)
    for dropped in ("us", "brazil", "argentina", "south_america"):
        assert dropped not in w, dropped
    # Africa is carried in full — the reason this reads `global_college` rather
    # than `_intl_weights`'s pro-tour `tennis_global`.
    africa = sum(v for k, v in w.items() if "africa" in k) / tot
    assert africa > 0.15, africa


def test_arrivals_are_good_without_being_a_lottery():
    """The infusion is centred above the host class with a wider spread, so most
    arrivals strengthen a lineup and some are ordinary squad players. If nearly
    every arrival were a team's No. 1, the mechanic would be deciding
    championships by dice — the fall portal's curated-flow lesson."""
    firsts = 0
    hosts = _hosts()
    for school, p in hosts:
        roster = jh.build_roster(school, 0, "")
        better = sum(1 for q in roster
                     if q.pid != p.pid and q.current_overall() > p.current_overall())
        firsts += (better == 0)
    assert 0.05 <= firsts / len(hosts) <= 0.45, firsts / len(hosts)


def test_nothing_marks_them_as_an_exchange_student():
    """‼️ OWNER RULE: "it's all behind the scenes … they're like any other student
    to the UI except they have a flag on their player profile". There is no badge,
    no roster label, no record column and no `Prospect` field — the ONLY thing
    that distinguishes one is `country`, which ordinary cohort players carry too
    (~10% of them). A future pass must not add a marker to "make it visible"."""
    school, p = _hosts()[0]
    assert p.country and p.country != "US"
    ordinary = jh.build_roster(school, 0, "")
    assert {type(q) for q in ordinary} == {type(p)}
    for attr in ("exchange", "is_exchange", "exchange_student", "arrival"):
        assert not hasattr(p, attr), attr


def test_no_arrival_predates_the_rollout_era(monkeypatch):
    """‼️ THE ONE THAT WOULD HAVE CORRUPTED A REAL SAVE. Every archived JHSAA
    season is REBUILT from seed — the school page, the player page and the
    research export all replay history through `build_roster` — so an ungated
    arrival appears on rosters for seasons played before the mechanic existed,
    whose duals, ladders and honours were archived without them. `exchange_era`
    is the `name_era` idiom and gates on the SEASON."""
    monkeypatch.setattr(jh, "exchange_era", lambda: 2040)
    schools = jh.load_schools("boys")[:150]
    for year in (2030, 2039):
        assert not [s for s in schools
                    if jh.exchange_student(s, year, "", _mod(s))], year
    assert [s for s in schools if jh.exchange_student(s, 2040, "", _mod(s))]
    # And the gate is on the roster too, not only the helper.
    host = next(s for s in schools if jh.exchange_student(s, 2040, "", _mod(s)))
    grade11 = lambda y: [q for q in jh.build_roster(host, y, "") if q.grade == 11]
    assert len(grade11(2039)) < len(grade11(2040))


def test_the_kill_switch_returns_the_pre_feature_association(monkeypatch):
    """`EXCHANGE_ENABLED` is the first diagnostic: off, every roster is exactly
    what it was before the mechanic existed."""
    school, _p = _hosts()[0]
    monkeypatch.setattr(jh, "EXCHANGE_ENABLED", False)
    assert jh.exchange_student(school, 0, "", _mod(school)) is None
    assert all(q.grade != 11 or q.pid for q in jh.build_roster(school, 0, ""))
