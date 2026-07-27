"""Service academies roster US citizens ONLY (owner rule 2026-07).

Army / Navy / Air Force / Coast Guard / Merchant Marine can never have an
international player, through ANY pipeline: the year-0 base roster, the recruiting
drip, the portals (pre-season / fall / year-end), the coach carousel, pro free
agents, or walk-on fill. See docs/AAR-service-academy-us-only-rosters.md.

The state senior military colleges (The Citadel, VMI) are ordinary universities
that DO enroll internationals, and must stay ungated.
"""
import copy
import os
import random
import tempfile

os.environ.setdefault("TENNIS_DB_PATH", tempfile.mktemp(suffix="-academies.db"))

from app import world
from app.ncaa import (SERVICE_ACADEMIES, admits_nationality, blocked_schools_for,
                      build_roster, is_domestic_player, load_division, roster_cap,
                      us_only_program)

DIV_OF_ACADEMY = {"Army": "D1", "Navy": "D1", "Air Force": "D1",
                  "Coast Guard": "D4", "Merchant Marine": "D4"}


class _P:
    """Minimal stand-in for a Prospect where only nationality matters."""

    def __init__(self, pid, country="US", name="Test Player", **kw):
        self.pid = pid
        self.name = name
        self.country = country
        self.domestic = country in ("US", "USA", "United States")
        self.walk_on = False
        self.class_year = "Fr"
        self.academic_rating = 85
        for k, v in kw.items():
            setattr(self, k, v)


# --- the citizenship gate itself ------------------------------------------

def test_the_five_academies_are_us_only():
    assert SERVICE_ACADEMIES == frozenset(
        {"Army", "Navy", "Air Force", "Coast Guard", "Merchant Marine"})
    for s in SERVICE_ACADEMIES:
        assert us_only_program(s)
    # Senior military colleges are NOT federal academies — they admit internationals.
    for s in ("The Citadel", "VMI", "Texas", "Coast Guard Academy"):
        assert not us_only_program(s)


def test_admits_nationality():
    us, intl = _P("a"), _P("b", country="ESP")
    assert is_domestic_player(us) and not is_domestic_player(intl)
    assert admits_nationality("Navy", us)
    assert not admits_nationality("Navy", intl)
    assert admits_nationality("Texas", intl)          # everyone else takes anyone
    assert admits_nationality("VMI", intl)
    # A PR/Guam kid is a US citizen (dual territory flag, still domestic).
    assert admits_nationality("Army", _P("c", secondary_country="PR"))
    # blocked_schools_for is the exclude-set form of the same rule.
    assert blocked_schools_for(us) == frozenset()
    assert blocked_schools_for(intl) == SERVICE_ACADEMIES


def test_citizenship_error_message():
    assert world._citizenship_error(_P("a"), "Navy") == ""
    assert world._citizenship_error(_P("b", country="FRA"), "Texas") == ""
    msg = world._citizenship_error(_P("b", country="FRA", name="Luc Petit"), "Navy")
    assert "Navy" in msg and "Luc Petit" in msg


# --- year-0 base rosters ---------------------------------------------------

def test_academy_base_rosters_are_entirely_american():
    for school, div in DIV_OF_ACADEMY.items():
        for gender in ("men", "women"):
            prog = load_division(div, gender).by_school(school)
            assert prog is not None, f"{school} missing from {div}-{gender}"
            roster = build_roster(prog)
            assert roster, f"{school} {gender} roster is empty"
            foreign = [(p.name, p.country) for p in roster if not is_domestic_player(p)]
            assert not foreign, f"{school} {gender} has internationals: {foreign}"
            # ...and they're real American kids, not blank-country placeholders.
            assert all(p.country == "US" for p in roster)
            assert all(p.hometown for p in roster)


def test_non_academy_programs_still_recruit_the_world():
    """The gate is per-program: it must not leak into the rest of the world."""
    intl = 0
    for prog in load_division("D1", "men").programs[:60]:
        if prog.school in SERVICE_ACADEMIES:
            continue
        intl += sum(1 for p in build_roster(prog) if not is_domestic_player(p))
    assert intl > 0, "the level-based international share is gone from D1 men"


# --- the recruiting drip (signing) ----------------------------------------

def test_pick_school_never_sends_an_international_to_an_academy():
    """Every window of the cycle, including the signing-day relax pass."""
    from tests.test_recruit_signing import _market
    market = _market()
    klass = world.national_class(2026, 0, "men")
    intl = [p for p in klass if not is_domestic_player(p)]
    assert len(intl) > 50, "no internationals in the class — test is vacuous"
    # Wide-open seats everywhere, so nothing but the citizenship gate blocks a pick.
    avail = {s: 20 for s in market["progs"]}
    for progress in (0.0, 0.5, 1.0):
        picks = {p.pid: world._pick_school(p, market, avail, jitter_salt="acad",
                                           progress=progress) for p in intl[:400]}
        bad = {pid: s for pid, s in picks.items() if s in SERVICE_ACADEMIES}
        assert not bad, f"international signed at an academy (progress={progress}): {bad}"


def test_a_full_cycle_fills_the_academies_with_americans_only():
    """The gate must not STARVE them: over a real signing cycle (real seat caps) an
    academy still fills every opening it has — just domestically. If this ever
    regresses, Army/Navy/Air Force thin out season over season, because D1 has no
    auto-generated walk-on depth to paper over an unsigned class."""
    from tests.test_recruit_signing import _market, _run_cycle
    market = _market()
    klass = world.national_class(2026, 0, "men")
    signed = _run_cycle(market, klass)
    dom_of = {p.pid: is_domestic_player(p) for p in klass}
    bad = [(p.name, p.country, signed[p.pid]) for p in klass
           if signed.get(p.pid) in SERVICE_ACADEMIES and not dom_of[p.pid]]
    assert not bad, f"internationals signed at academies over a full cycle: {bad}"
    took = {s: sum(1 for d in signed.values() if d == s) for s in SERVICE_ACADEMIES
            if s in market["progs"]}
    openings = {s: market["cap"].get(s, 0) for s in took}
    assert any(openings.values()), "no academy had an opening — test is vacuous"
    for s, n in took.items():
        assert n == openings[s], f"{s} signed {n} of its {openings[s]} open seats"


def test_international_recruit_board_has_no_academy():
    from app.recruiting import build_recruiting, schools_from_programs
    progs = [p for p in load_division("D1", "men").programs]
    schools = schools_from_programs(progs)
    assert any(s.name in SERVICE_ACADEMIES for s in schools), "academies not in the pool"
    klass = world.national_class(2026, 0, "men")
    intl = [p for p in klass if not is_domestic_player(p)][:150]
    assert intl
    for p in intl:
        rec = build_recruiting(p, schools, seed_salt="2026")
        listed = {o.school for o in rec.offers} | {o.school for o in rec.dreamsheet}
        assert not (listed & SERVICE_ACADEMIES), f"{p.name} shows an academy: {listed}"


# --- the portals -----------------------------------------------------------

def _world4(gender="men", n=14):
    """A slice of every division, with the academies forced in, deep-copied."""
    rosters = {}
    for div in ("D1", "D2", "D3", "D4"):
        prog = {p.school: p for p in load_division(div, gender).programs}
        keep = [s for s in prog if s in SERVICE_ACADEMIES]
        keep += [s for s in prog if s not in SERVICE_ACADEMIES][:n]
        rosters[(div, gender)] = {s: [copy.deepcopy(q) for q in build_roster(prog[s])]
                                  for s in keep}
    return rosters


def _academies_in(rosters, gender):
    return {s for (_d, g), schools in rosters.items() if g == gender
            for s in schools if s in SERVICE_ACADEMIES}


def test_fall_portal_never_places_an_international_at_an_academy():
    r = _world4()
    present = _academies_in(r, "men")
    assert present, "no academies in the snapshot"
    # Empty every academy so they have the most open seats in the world — the only
    # thing that can keep an international out is the citizenship gate.
    for (div, _g), schools in r.items():
        for s in list(schools):
            if s in present:
                schools[s] = schools[s][:1]
    # Make every lower-division international a huge riser so the engine wants to move them.
    ps = {}
    for (div, _g), schools in r.items():
        if div == "D1":
            continue
        for s, roster in schools.items():
            for p in roster:
                if not is_domestic_player(p):
                    ps[p.pid] = (58.0, 0.95)
    moves = world.fall_portal_proposals(r, ps, random.Random(7), "men")
    assert moves, "portal proposed nothing — test is vacuous"
    by_pid = {p.pid: p for (_d, _g), sc in r.items() for roster in sc.values() for p in roster}
    bad = [(m["name"], m["dest_school"]) for m in moves
           if m["dest_school"] in SERVICE_ACADEMIES
           and not is_domestic_player(by_pid[m["pid"]])]
    assert not bad, f"fall portal moved internationals to academies: {bad}"


def test_fall_planner_refuses_a_hand_picked_academy_destination():
    r = _world4()
    plan = world._FPPlanner(r, {}, "men")
    academy = next(s for s in plan.schools if s in SERVICE_ACADEMIES)
    plan.pool[academy] = plan.pool[academy][:1]          # plenty of room
    plan.strs[academy] = sorted(plan._sv(p) for p in plan.pool[academy])
    intl = next((s, p) for s in plan.schools if plan.div_of[s] == "D2"
                for p in plan.pool[s] if not is_domestic_player(p))
    src, p = intl
    assert plan.place(p, src, dest=academy) is None     # refused outright
    assert p not in plan.pool[academy]
    # ...and the same seat is open to an American from the same school.
    us = next(q for q in plan.pool[src] if is_domestic_player(q))
    assert plan.place(us, src, dest=academy) == academy


def test_year_end_transfer_portal_keeps_academies_american():
    r = _world4()
    present = _academies_in(r, "men")
    for (div, _g), schools in r.items():
        for s in list(schools):
            if s in present:
                schools[s] = schools[s][:1]             # wide-open academy seats
    world.transfer_portal(r, {}, random.Random(3), "men")
    bad = [(p.name, p.country, s) for (_d, _g), schools in r.items()
           for s, roster in schools.items() if s in SERVICE_ACADEMIES
           for p in roster if not is_domestic_player(p)]
    assert not bad, f"transfer portal put internationals on academies: {bad}"


def test_normalize_never_relocates_an_international_to_an_academy():
    r = _world4()
    present = _academies_in(r, "men")
    for (div, _g), schools in r.items():
        for s in list(schools):
            if s in present:
                schools[s] = schools[s][:1]             # the only open seats in the world
    # Push one non-academy roster over cap with internationals, so the surplus must move.
    over = next(s for s in r[("D1", "men")] if s not in present)
    donor = next(s for s in r[("D2", "men")] if s not in present)
    seed_intl = [q for q in r[("D2", "men")][donor] if not is_domestic_player(q)]
    assert seed_intl, "no internationals available to overflow"
    for i in range(8):                            # distinct copies, distinct pids
        extra = copy.deepcopy(seed_intl[i % len(seed_intl)])
        extra.pid = f"{extra.pid}-of{i}"
        r[("D1", "men")][over].append(extra)
    assert len(r[("D1", "men")][over]) > roster_cap("D1")
    world._normalize(r)
    bad = [(p.name, p.country, s) for (_d, _g), schools in r.items()
           for s, roster in schools.items() if s in SERVICE_ACADEMIES
           for p in roster if not is_domestic_player(p)]
    assert not bad, f"_normalize put internationals on academies: {bad}"


def test_coach_carousel_followers_respect_the_academy():
    """A coach who lands an academy job brings only their American players."""
    from app import coachreg
    r = _world4()
    present = _academies_in(r, "men")
    for (_div, _g), schools in r.items():
        for s in list(schools):
            if s in present:
                schools[s] = schools[s][:1]             # wide-open academy seats
    # coach_carousel PERSISTS its swaps (coachreg.swap_head_coaches writes coach_seat),
    # so snapshot the seats and put them back — a test must not leave the shared
    # registry reshuffled for whatever runs after it.
    conn = coachreg._conn()
    seats = [tuple(s) for s in conn.execute(
        "SELECT division,gender,school,role,coach_id,tenure FROM coach_seat")]
    conn.close()
    try:
        out = world.coach_carousel(r, {}, random.Random(5), "men")
        assert out["moves"] > 0, "no coach moved — test is vacuous"
        bad = [(p.name, p.country, s) for (_d, _g), schools in r.items()
               for s, roster in schools.items() if s in SERVICE_ACADEMIES
               for p in roster if not is_domestic_player(p)]
        assert not bad, f"coach carousel dragged internationals to academies: {bad}"
    finally:
        conn = coachreg._conn()
        conn.execute("DELETE FROM coach_seat")
        conn.executemany("INSERT INTO coach_seat VALUES (?,?,?,?,?,?)", seats)
        conn.commit()
        conn.close()


# --- walk-on fill ---------------------------------------------------------

def test_pool_walkon_sweep_and_autogen_keep_academies_american():
    """D4 academies fill their walk-on tail from the leftover pool + auto-gen."""
    gender = "men"
    rosters = {}
    prog = {p.school: p for p in load_division("D4", gender).programs}
    keep = [s for s in prog if s in SERVICE_ACADEMIES]
    assert keep, "no D4 academies"
    rosters[("D4", gender)] = {s: [copy.deepcopy(q) for q in build_roster(prog[s])][:2]
                              for s in keep}
    placed = world.assign_pool_walkons(rosters, {gender: {}}, 2026, 0)
    assert placed > 0, "leftover sweep placed nobody — test is vacuous"
    intake = world.refill_walkons(rosters, 1, 2026)
    bad = [(p.name, p.country, s) for s, roster in rosters[("D4", gender)].items()
           for p in roster if not is_domestic_player(p)]
    assert not bad, f"walk-on fill put internationals on academies: {bad}"
    assert len(next(iter(rosters[("D4", gender)].values()))) == roster_cap("D4"), \
        "academy roster did not fill to cap"
    assert placed + intake > 0


# --- pro free agents ------------------------------------------------------

def test_assign_pros_skips_academies_for_international_pros():
    from app import pros
    cohort = [_P("pro-us", country="US", name="US Pro"),
              _P("pro-intl", country="SRB", name="Intl Pro")]
    for p in cohort:                              # assign_pros ranks on current_overall
        p.current_overall = lambda: 70.0
    programs = [{"school": "Navy", "budget": 999.0, "prestige": 0.99, "us_only": True},
                {"school": "Rice", "budget": 999.0, "prestige": 0.10}]
    got = {a["pid"]: a["school"] for a in pros.assign_pros(cohort, programs)}
    assert got["pro-us"] == "Navy"                # the top-prestige club takes the American
    assert got["pro-intl"] == "Rice"              # the international can't go there
