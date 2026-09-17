"""Generated siblings (owner rule 2026-09) — the roll that makes two players related.

The retired rule was "no generator, no suggestion pass, no same-surname scan";
what survives of it is the reason: a surname is not evidence. These tests pin the
shape the owner asked for — geography-gated, randomised so a shared surname never
implies a tie, era-gated so no archived roster is renamed — and the two things a
derived tie must reach: the doubles pairing and the page.
"""
import random

import pytest

import app.jhsaa as jh


SALT = "sib-test"


@pytest.fixture
def era0(monkeypatch):
    monkeypatch.setattr(jh, "sibling_era", lambda: -10_000)


def _schools():
    return {g: jh.load_schools(g) for g in ("girls", "boys")}


def _freshmen(schools, year=0, n=120):
    for s in schools[:n]:
        for p in jh.build_roster(s, year, SALT):
            if p.grade == 9:
                yield s, p


def test_the_roll_is_deterministic_and_the_kill_switch_restores_the_raw_draw(era0, monkeypatch):
    s = jh.load_schools("boys")[0]
    a = [(p.pid, p.name) for p in jh.build_roster(s, 0, SALT)]
    b = [(p.pid, p.name) for p in jh.build_roster(s, 0, SALT)]
    assert a == b
    monkeypatch.setattr(jh, "SIBLING_ENABLED", False)
    raw = [(p.pid, p.name) for p in jh.build_roster(s, 0, SALT)]
    # Same people, same pids, same order — only the surnames of rolled seats move.
    assert [x[0] for x in raw] == [x[0] for x in a]
    changed = [(x, y) for x, y in zip(raw, a) if x[1] != y[1]]
    for (_, old), (_, new) in changed:
        assert old.split(" ", 1)[0] == new.split(" ", 1)[0]


def test_the_name_swap_moves_no_attribute_roll(era0, monkeypatch):
    """The surname is applied after `_draw_name`, on its own rng streams — the
    same guarantee the name era gives: a linked seat's abilities are byte-identical
    to the same seat with the mechanic off."""
    s = jh.load_schools("girls")[3]
    on = {p.pid: (p.current_overall(), p.ceiling_overall(), p.grade)
          for p in jh.build_roster(s, 0, SALT)}
    monkeypatch.setattr(jh, "SIBLING_ENABLED", False)
    off = {p.pid: (p.current_overall(), p.ceiling_overall(), p.grade)
           for p in jh.build_roster(s, 0, SALT)}
    assert on == off


def test_the_rate_lands_near_the_constant_and_hits_stay_in_town(era0):
    sch = _schools()
    fresh = list(_freshmen(sch["boys"] + sch["girls"], n=200))
    hits = [(s, p) for s, p in fresh if p.jhsaa.get("sibling")]
    rate = len(hits) / len(fresh)
    assert 0.6 * jh.SIBLING_RATE < rate < 1.5 * jh.SIBLING_RATE, rate
    by_city = {}
    for g in ("girls", "boys"):
        for s in sch[g]:
            by_city.setdefault(s.name, s.city)
    for s, p in hits:
        # Same school (either gender) or the same TOWN — never further.
        assert by_city[p.jhsaa["sibling_school"]] == s.city
        gap = p.entry_year - p.jhsaa["sibling_entry"]
        assert 1 <= gap <= jh.SIBLING_MAX_GAP
    # Both halves of the gate are exercised on a real association.
    assert any(p.jhsaa["sibling_school"] != s.name for s, p in hits)
    assert any(p.jhsaa["sibling_gender"] != s.gender for s, p in hits)


def test_the_younger_takes_the_olders_surname_and_the_tie_reads_from_both_ends(era0):
    sch = _schools()
    for s, p in _freshmen(sch["boys"], n=80):
        link = p.jhsaa.get("sibling")
        if not link:
            continue
        older_name = p.jhsaa["sibling_name"]
        assert p.name.split(" ", 1)[1] == older_name.split(" ", 1)[1]
        # The older sibling's own page finds the younger one.
        osc = next(x for x in sch[p.jhsaa["sibling_gender"]]
                   if x.name == p.jhsaa["sibling_school"])
        younger = jh.generated_siblings(osc, 0, link, SALT)
        assert any(y["pid"] == p.pid and y["name"] == p.name for y in younger)
        # And the younger one's page names the older.
        mine = jh.generated_siblings(s, 0, p.pid, SALT)
        assert any(o["pid"] == link for o in mine)
        return
    pytest.fail("no generated sibling in the first 80 boys' programs")


def test_a_shared_surname_alone_is_never_a_tie(era0):
    """The whole point of the randomised roll: two Johnsons at one school are
    strangers unless the roll said otherwise."""
    sch = _schools()
    untied_pairs = 0
    for s in sch["boys"][:120]:
        roster = jh.build_roster(s, 0, SALT)
        tied = {(p.pid, p.jhsaa.get("sibling")) for p in roster if p.jhsaa.get("sibling")}
        tied_pids = {a for a, _ in tied} | {b for _, b in tied}
        by_sur = {}
        for p in roster:
            by_sur.setdefault(p.name.split(" ", 1)[-1], []).append(p)
        for group in by_sur.values():
            if len(group) >= 2 and not any(p.pid in tied_pids for p in group):
                untied_pairs += 1
    assert untied_pairs > 0


def test_nothing_before_the_era_is_renamed(monkeypatch):
    s = jh.load_schools("boys")[5]
    monkeypatch.setattr(jh, "sibling_era", lambda: 10_000)
    before = [(p.pid, p.name) for p in jh.build_roster(s, 0, SALT)]
    assert not any(p.jhsaa.get("sibling") for p in jh.build_roster(s, 0, SALT))
    monkeypatch.setattr(jh, "SIBLING_ENABLED", False)
    assert before == [(p.pid, p.name) for p in jh.build_roster(s, 0, SALT)]


def test_the_era_is_registered_so_a_new_save_clears_it():
    assert "jhsaa_sibling_era" in jh.ERA_SETTINGS


def test_an_exchange_seat_never_rolls(era0):
    s = jh.load_schools("boys")[0]
    for seat in range(jh.EXCHANGE_SEAT_BASE, jh.EXCHANGE_SEAT_BASE + 5):
        assert jh.sibling_link(s, 0, seat, SALT) is None


def test_the_roll_is_local_to_the_seat(era0):
    """Adding or removing a program never changes whether ANOTHER program's seat
    rolled — the decision reads no school list, only the pick on a hit does."""
    s = jh.load_schools("girls")[7]
    hits = {seat: jh.sibling_link(s, 0, seat, SALT) is not None for seat in range(40)}
    rng_hits = {seat: random.Random(f"{SALT}|jhsaa-sibling|{s.key}|0|{seat}").random()
                < jh.SIBLING_RATE for seat in range(40)}
    assert hits == rng_hits


def test_siblings_on_one_roster_reach_the_pairing(era0):
    """`TeamSeason.sibling_ids` carries the generated tie from both ends when both
    players are on the roster — that is what puts them on one doubles court."""
    found = False
    for s in jh.load_schools("boys")[:150]:
        ts = jh.district_teams([s], 0, SALT)[0]
        here = {p.pid for p in ts.roster}
        for p in ts.roster:
            o = p.jhsaa.get("sibling")
            if o and o in here:
                assert o in ts.sibling_ids[p.pid]
                assert p.pid in ts.sibling_ids[o]
                found = True
    assert found
