"""Playing up — competing a classification above your enrollment class.

Owner rule 2027-08. Real associations let a strong program play up, and here it is a
durable property of programs that are good at TENNIS (the blue-blood seed list),
layered with an editable override exactly the way archetypes are.

‼️ THE INVARIANT THE WHOLE FEATURE RESTS ON: it moves `group` and NEVER
`classification`. `group` is the championship you enter — leagues, the ladder, State,
All-State — while `classification` is how many students you have, and `_TALENT` reads
that (`School.talent_group`). Playing up must COST you a harder field, not buy you
better players; keyed on `group`, a 5A blue-blood playing up to 6A would be GENERATED
with 6A talent, which inverts the choice entirely and would show up nowhere except a
position-by-position measurement.

No season is simulated here — this file covers play-up and nothing else.
"""
import pytest

from app import jhsaa as jh
from app import overrides as ov


@pytest.fixture
def clean():
    """A pristine override table, restored afterwards — the store is shared."""
    before = ov.get_jhsaa_playups()
    for school in before:
        ov.clear_jhsaa_playup(school)
    jh.reset_schools()
    yield
    for school in list(ov.get_jhsaa_playups()):
        ov.clear_jhsaa_playup(school)
    for school, v in before.items():
        ov.set_jhsaa_playup(school, v)
    jh.reset_schools()


#: Condotti Vanguard Academy and Romero-Finniski are a deliberate, owner-named
#: exception to the play-up mechanism (owner correction 2026-08: they are
#: enrollment-level 3A academies competing in 7A while GENERATING 9A-caliber
#: rosters — `School.talent` pins the generation class by decree, the one place
#: in the association talent is decoupled from enrollment). They trip
#: `School.plays_up` (a raw classification/group mismatch detector) but arrived
#: in 7A by owner edict, not through the play-up override system this file
#: tests — same pattern as `import_jhsaa.OWNER_EDICTS`/`RIVALRIES`, a named
#: exception rather than a rule.
_PLAY_DOWN_EXCEPTIONS = {"Condotti Vanguard Academy", "Romero-Finniski"}


def _ups(gender="girls"):
    return [s for s in jh.load_schools(gender)
            if s.plays_up and s.name not in _PLAY_DOWN_EXCEPTIONS]


# --- the ladder step ---------------------------------------------------------------

def test_playing_up_is_exactly_one_classification():
    # LADDER only (2046 expansion): the Great Basin Group 1/2 groups sit
    # after 1A in GROUPS but are NOT rungs on the size ladder.
    for i, g in enumerate(jh.LADDER_GROUPS):
        if i == 0:
            continue
        assert jh.play_up_group(g) == jh.LADDER_GROUPS[i - 1], g


def test_great_basin_groups_are_outside_the_play_up_ladder():
    """Group 1/2 (2046) are a geographic pair, not classes above or below 1A:
    they can never play up, never be a play-up target, and the ladder step is an
    identity for them — a naive GROUPS.index would have promoted Group 1
    'up' into 1A."""
    for g in jh.GB_GROUPS:
        assert not jh.can_play_up(g)
        assert jh.play_up_group(g) == g
        for other in jh.GROUPS:
            assert not jh.valid_playup_target(g, other)
            assert not jh.valid_playup_target(other, g)


def test_the_top_class_has_nothing_to_play_up_to():
    """9A is the ceiling, so the step is a no-op rather than an error or a wrap
    around to the bottom of the ladder."""
    top = jh.GROUPS[0]
    assert jh.play_up_group(top) == top


def test_a_raw_classification_is_its_own_group():
    """1A and 2A used to share one combined "2A-1A" championship; they now crown
    separately (the fixed 24-team shape), so a 1A school playing up steps to 2A —
    a real intermediate group, not straight to 3A."""
    assert jh.champ_group("1A") == "1A"
    assert jh.champ_group("2A") == "2A"
    assert jh.play_up_group("1A") == "2A"
    assert jh.play_up_group("2A") == "3A"


# --- what the seed list produces ---------------------------------------------------

def test_the_association_has_a_dozen_or_so_playing_up(clean):
    ups = _ups()
    assert 10 <= len(ups) <= 20, [s.name for s in ups]


def test_a_played_up_school_competes_above_its_own_class(clean):
    for s in _ups():
        assert s.group == jh.play_up_group(s.classification), s.name
        assert s.group != jh.champ_group(s.classification), s.name


def test_only_small_schools_play_up(clean):
    """‼️ PLAYING UP IS A SMALL-SCHOOL THING (owner correction 2027-08): "play up is
    for schools at the 4A or under level to play with teams at their competitive
    level, not already big schools". An 8A blue-blood moving to 9A is not playing up,
    it is a big school in a slightly bigger class — and the first pass shipped exactly
    that, which is why the floor is asserted rather than left to the seed script.
    9A's exclusion falls out of the same rule rather than needing its own."""
    floor = jh.GROUPS.index("4A")
    for s in _ups():
        assert jh.GROUPS.index(jh.champ_group(s.classification)) >= floor, s.name
    assert not [s for s in _ups() if s.classification == jh.GROUPS[0]]


def test_boys_and_girls_play_up_together(clean):
    """Playing up belongs to the SCHOOL, like its league and its archetype — a
    program cannot compete in 6A for girls and 5A for boys, and it cannot land in
    two DIFFERENT leagues of that 6A either. The split-league form of this bug was
    invisible unless you compared both team pages for the same school side by
    side — `_playup_league` is computed once, gender-agnostic, so both reads are
    guaranteed to see the identical assignment rather than two independent ones."""
    girls = {s.name: s for s in jh.load_schools("girls")}
    boys = {s.name: s for s in jh.load_schools("boys")}
    g_up = {s.name for s in _ups("girls")}
    b_up = {s.name for s in _ups("boys")}
    for name in g_up:
        if name in boys:
            assert name in b_up, name
    for name in (g_up & boys.keys() & girls.keys()):
        assert girls[name].group == boys[name].group, name
        assert girls[name].district == boys[name].district, name


# --- ‼️ the invariant ---------------------------------------------------------------

def test_playing_up_never_touches_the_talent_band(clean):
    """A played-up school generates at its OWN classification, not the one it plays
    in. This is the whole point: a harder field, not better players."""
    for s in _ups():
        assert s.talent_group == jh.champ_group(s.classification), s.name
        assert s.talent_group != s.group, s.name


def test_the_roster_is_identical_with_and_without_the_flag(clean):
    """The strongest form of the same statement, measured rather than asserted about
    the code: hold a played-up school in its own class through the override and its
    twelve players come out unchanged, player for player. If `_TALENT` were ever
    keyed on `group` again this is what would catch it — nothing else would, because
    the rosters stay perfectly plausible either way."""
    up = _ups()[0]
    was = [(p.name, round(p.current_overall(), 6))
           for p in jh.build_roster(up, 2029)]

    ov.set_jhsaa_playup(up.name, "no")            # hold it in its own class
    jh.reset_schools()
    down = next(s for s in jh.load_schools("girls") if s.name == up.name)
    assert not down.plays_up and down.group == jh.champ_group(down.classification)
    now = [(p.name, round(p.current_overall(), 6))
           for p in jh.build_roster(down, 2029)]

    assert was == now, up.name


# --- the league moves with the program ---------------------------------------------

def test_a_played_up_school_joins_a_real_league_of_its_new_class(clean):
    """A district is (classification, name), so a school competing in 6A while
    carrying its 5A league name lands in a 6A district holding nobody else — a
    one-team league, which in a double round robin is no league season at all."""
    for gender in ("girls", "boys"):
        by_group = {}
        for s in jh.load_schools(gender):
            by_group.setdefault((s.group, s.district), []).append(s)
        for s in _ups(gender):
            mates = by_group[(s.group, s.district)]
            assert len(mates) >= 4, (s.name, s.group, s.district, len(mates))


def test_playing_up_ignores_league_size_and_prefers_geography(clean):
    """Geography is a preference, never a gate (owner rule): a played-up program
    joins the CLOSEST existing league in its new class — county match first, then
    area — with no capacity cap and no maximum distance, the same way real
    high-school sport already crosses state lines (WIAA fields Oregon border
    schools; Nevada, California and Arizona programs cross both ways). If there is
    a same-COUNTY league in the target class, the program must land in one of
    them, however full it already is — `jh.MAX_DISTRICT` no longer gates this
    path at all."""
    assert not hasattr(jh, "MAX_DISTRICT"), \
        "a capacity constant reappeared on the play-up path — size must stay a non-factor"
    # The candidate pool is SCHOOL-level, not per gender (a girls-only sponsor is
    # still a real member of its league and county) — so build it by UNIONING both
    # genders' settled schools, the same pool `_compute_playup_league` itself sees,
    # rather than either gender's `load_schools` alone (which would silently drop
    # every school that doesn't field THAT gender's team).
    settled_by_group, seen = {}, set()
    for gender in ("girls", "boys"):
        for x in jh.load_schools(gender):
            if x.plays_up or x.name in seen:
                continue
            seen.add(x.name)
            settled_by_group.setdefault(x.group, []).append(x)
    for gender in ("girls", "boys"):
        for s in _ups(gender):
            mates = settled_by_group.get(s.group, [])
            same_county_districts = {m.district for m in mates if m.county == s.county}
            if same_county_districts:
                assert s.district in same_county_districts, \
                    (s.name, s.district, same_county_districts)


# --- the override layers over the seed ---------------------------------------------

def test_the_override_can_promote_a_school_the_file_did_not_pick(clean):
    # Eligibility is the 4A-and-below rule, not merely "not already the top class"
    # — `can_play_up` is enforced on the READ, so a 5A pick would be refused.
    plain = next(s for s in jh.load_schools("girls")
                 if not s.plays_up and jh.can_play_up(s.classification))
    ov.set_jhsaa_playup(plain.name, jh.play_up_group(plain.classification))
    jh.reset_schools()
    now = next(s for s in jh.load_schools("girls") if s.name == plain.name)
    assert now.plays_up
    assert now.group == jh.play_up_group(now.classification)


def test_the_override_can_hold_a_seeded_school_in_its_own_class(clean):
    seeded = _ups()[0]
    ov.set_jhsaa_playup(seeded.name, "no")
    jh.reset_schools()
    now = next(s for s in jh.load_schools("girls") if s.name == seeded.name)
    assert not now.plays_up
    assert now.group == jh.champ_group(now.classification)


def test_clearing_reverts_to_the_seed_list_rather_than_to_off(clean):
    """"Not playing up" and "no opinion" are different states — a single clear could
    only express one of them, which is why the store keeps "no" rather than deleting
    the row (the archetype table's rule)."""
    seeded = _ups()[0]
    ov.set_jhsaa_playup(seeded.name, "no")
    jh.reset_schools()
    assert not next(s for s in jh.load_schools("girls")
                    if s.name == seeded.name).plays_up

    ov.clear_jhsaa_playup(seeded.name)
    jh.reset_schools()
    assert next(s for s in jh.load_schools("girls")
                if s.name == seeded.name).plays_up


def test_the_season_cache_falls_when_a_play_up_changes(clean):
    """A play-up moves which championship a program enters, so a cached season built
    from the old classification map must not be served. The archetype fingerprint
    alone would not have noticed."""
    before = ov.jhsaa_playup_version()
    plain = next(s for s in jh.load_schools("girls") if not s.plays_up)
    ov.set_jhsaa_playup(plain.name, jh.play_up_group(plain.classification))
    assert ov.jhsaa_playup_version() != before


# --- a league is only a league if somebody plays in it ------------------------

def _dead_leagues(rows):
    """(group, league) pairs whose every member has stopped sponsoring tennis."""
    lg = {}
    for r in rows:
        d = jh._row_league(r)
        if d:
            lg.setdefault((r["group"], d), []).append(r)
    return {k for k, v in lg.items() if not any(jh._sponsors_any(x) for x in v)}


def test_the_association_really_does_hold_empty_leagues():
    """The premise of the two tests below, asserted against the shipped data rather
    than assumed. Since `former_school` (2026-08) a program that stops sponsoring keeps
    its data row while dropping out of `load_schools`, so a league can be fully
    populated in `_rows()` and completely empty on the field. If this ever stops being
    true the tests below stop testing anything, and that should be visible."""
    dead = _dead_leagues(jh._rows())
    assert dead, "no empty leagues left — the guard below is no longer exercised"


def test_no_eligible_school_can_be_played_up_into_an_empty_league(clean):
    """‼️ The 3A bug, swept over every school that COULD be played up.

    `_compute_playup_league` reads raw rows, so it counted programs that no longer
    sponsor tennis as settled members of their league. Copperview (3A, sponsors
    neither gender) is the lone member of Coastal Range League and sits in Puerto
    Alma's own county, so it beat every real 3A league on the county term: played up,
    Puerto Alma joined a league with nobody in it, played no league duals at all
    (0-0 in district, 2-12 overall) and was crowned champion of a league of one.

    The existing coverage checked only the ~13 SEEDED play-ups, none of which happens
    to sit near a dead league — which is exactly why this shipped. The property belongs
    to the PLACEMENT, so it is swept over every eligible school."""
    rows = jh._rows()
    dead = _dead_leagues(rows)
    live_in = {}
    for r in rows:
        d = jh._row_league(r)
        if d and jh._sponsors_any(r):
            live_in[(r["group"], d)] = live_in.get((r["group"], d), 0) + 1
    checked = 0
    for r in rows:
        target = jh.play_up_group(r["classification"]) if \
            jh.can_play_up(r["classification"]) else None
        if not target:
            continue
        placed = jh._compute_playup_league(rows, {r["name"]: target}).get(r["name"])
        assert placed, (r["name"], target, "no league at all")
        assert (target, placed) not in dead, (r["name"], target, placed)
        # ‼️ The FLOOR, not merely "not empty" (owner rule 2026-09): a play-up joins
        # a league, it never brings one into existence, so a league too small to be
        # one is not a candidate and the program travels instead.
        assert live_in.get((target, placed), 0) >= jh.PLAY_UP_LEAGUE_MIN, \
            (r["name"], target, placed, live_in.get((target, placed), 0))
        checked += 1
    assert checked > 100, checked


def test_a_ghost_league_never_beats_a_real_one_on_geography(clean):
    """The mechanism in isolation: a same-county league is the strongest signal the
    placement has, so a league of ghosts in the mover's own county outranked a real
    league everywhere else. Sponsorship is checked FIRST — geography only orders the
    leagues that are actually being played."""
    rows = [
        {"name": "Mover", "classification": "3A", "group": "3A",
         "county": "Home", "area": "West", "girls": True, "boys": True,
         "girls_district": "Old League", "boys_district": "Old League"},
        # Same county as the mover, and nobody left in it.
        {"name": "Ghost", "classification": "4A", "group": "4A",
         "county": "Home", "area": "West", "girls": False, "boys": False,
         "girls_district": "Ghost League", "boys_district": "Ghost League"},
    ] + [
        # A real 4A league, one area away and four programs strong.
        {"name": f"Real {i}", "classification": "4A", "group": "4A",
         "county": "Away", "area": "West", "girls": True, "boys": True,
         "girls_district": "Real League", "boys_district": "Real League"}
        for i in range(4)
    ]
    placed = jh._compute_playup_league(rows, {"Mover": "4A"})
    assert placed["Mover"] == "Real League", placed


def test_a_play_up_travels_rather_than_join_a_league_too_small_to_be_one():
    """Owner rule 2026-09: "it should never invent a one-team or two-team or 4-team or
    whatever conference … none of this is real so they can be wherever." Geography is
    cosmetic, so it orders the leagues that are real and is never the reason a program
    lands in one that is not. Here the mover's OWN county holds a five-team league —
    under the floor — and a full league sits an area away; it must travel."""
    rows = [{"name": "Mover", "classification": "3A", "group": "3A",
             "county": "Home", "area": "West", "girls": True, "boys": True,
             "girls_district": "Old", "boys_district": "Old"}]
    rows += [{"name": f"Small {i}", "classification": "4A", "group": "4A",
              "county": "Home", "area": "West", "girls": True, "boys": True,
              "girls_district": "Small League", "boys_district": "Small League"}
             for i in range(jh.PLAY_UP_LEAGUE_MIN - 1)]
    rows += [{"name": f"Big {i}", "classification": "4A", "group": "4A",
              "county": "Away", "area": "East", "girls": True, "boys": True,
              "girls_district": "Big League", "boys_district": "Big League"}
             for i in range(jh.PLAY_UP_LEAGUE_MIN)]
    assert jh._compute_playup_league(rows, {"Mover": "4A"})["Mover"] == "Big League"


def test_one_more_member_is_always_allowed_there_is_no_ceiling():
    """The floor is not a capacity rule and must not grow a mirror. 10 is a drawing
    guide for a fresh map, never a limit (owner, 2026-09: "the 10 is not a hard cap …
    if it needs to go bigger it always can"), so a same-county league already well over
    it still wins against a smaller one further away."""
    rows = [{"name": "Mover", "classification": "3A", "group": "3A",
             "county": "Home", "area": "West", "girls": True, "boys": True,
             "girls_district": "Old", "boys_district": "Old"}]
    rows += [{"name": f"Full {i}", "classification": "4A", "group": "4A",
              "county": "Home", "area": "West", "girls": True, "boys": True,
              "girls_district": "Full League", "boys_district": "Full League"}
             for i in range(14)]
    rows += [{"name": f"Room {i}", "classification": "4A", "group": "4A",
              "county": "Away", "area": "East", "girls": True, "boys": True,
              "girls_district": "Roomy League", "boys_district": "Roomy League"}
             for i in range(jh.PLAY_UP_LEAGUE_MIN)]
    assert jh._compute_playup_league(rows, {"Mover": "4A"})["Mover"] == "Full League"


def test_when_no_league_clears_the_floor_it_takes_the_biggest_not_the_nearest():
    """A class the owner has moved most of the way out of still has to place a mover,
    and "a bigger league if needed" is the rule — never the nearest small one, and never
    a new one. This cannot happen on the shipped data (every live league is 8+); it
    exists so the placement degrades in the owner's stated direction if it ever does."""
    rows = [{"name": "Mover", "classification": "3A", "group": "3A",
             "county": "Home", "area": "West", "girls": True, "boys": True,
             "girls_district": "Old", "boys_district": "Old"}]
    rows += [{"name": f"Near {i}", "classification": "4A", "group": "4A",
              "county": "Home", "area": "West", "girls": True, "boys": True,
              "girls_district": "Near League", "boys_district": "Near League"}
             for i in range(2)]
    rows += [{"name": f"Far {i}", "classification": "4A", "group": "4A",
              "county": "Away", "area": "East", "girls": True, "boys": True,
              "girls_district": "Far League", "boys_district": "Far League"}
             for i in range(4)]
    assert jh._compute_playup_league(rows, {"Mover": "4A"})["Mover"] == "Far League"


def test_two_play_ups_cannot_both_fill_the_same_last_seat():
    """The one-pass rule, now that size decides something: a mover already placed counts
    toward the league it joined, so a run of play-ups cannot each read a league as
    though the others had not gone there."""
    rows = [{"name": n, "classification": "3A", "group": "3A",
             "county": "Home", "area": "West", "girls": True, "boys": True,
             "girls_district": "Old", "boys_district": "Old"}
            for n in ("Mover A", "Mover B")]
    rows += [{"name": f"Big {i}", "classification": "4A", "group": "4A",
              "county": "Home", "area": "West", "girls": True, "boys": True,
              "girls_district": "Big League", "boys_district": "Big League"}
             for i in range(jh.PLAY_UP_LEAGUE_MIN)]
    out = jh._compute_playup_league(rows, {"Mover A": "4A", "Mover B": "4A"})
    assert out == {"Mover A": "Big League", "Mover B": "Big League"}, out
