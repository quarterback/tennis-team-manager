"""JHSAA program archetypes — a school-level modifier ON TOP of the classification bands.

Durable program conditions (facilities, feeder networks, community participation,
coaching tradition, reputation), not current team strength — and deliberately not derived
from classification or public/private. Stored in an editable override table so the owner
can promote and demote programs as Jefferson's history develops; generation NEVER branches
on a school name.

  blue_blood   generates better, and clusters
  development  ordinary freshmen, best-in-association seniors — arrive good vs leave great
  doubles      generates normally; the edge is in doubles only, per match
  upstart      a temporary multi-year run, rolled per world and expiring by itself
"""
import statistics as stat

import pytest

from app import jhsaa
from app import overrides as ov


@pytest.fixture(autouse=True)
def _clean():
    """Clears the OVERRIDE layer only. The seed list in `data/jhsaa/archetypes.json` is
    real data and stays — which is why `_peers` skips schools that are on it, rather than
    these tests pretending the association is untagged."""
    ov.init_schema()
    for s in jhsaa.load_schools("boys"):
        ov.clear_jhsaa_archetype(s.name)
    jhsaa._arch_cache.clear()
    yield
    for s in jhsaa.load_schools("boys"):
        ov.clear_jhsaa_archetype(s.name)
    jhsaa._arch_cache.clear()


def _peers(group="5A", n=10):
    """Peers that are NOT on an upstart run, so a tag is the only thing that varies.

    Tagging a school removes its own upstart lift (a blue blood is not also an upstart),
    which is correct behaviour and would otherwise make "tagging changes nothing" false
    for a school that happened to be having a moment."""
    live = set(jhsaa.upstarts(2029, "")) | set(jhsaa._arch_seed())
    return [s for s in jhsaa.load_schools("boys")
            if s.group == group and s.name not in live][:n]


def _profile(schools, tag=""):
    for sc in schools:
        ov.clear_jhsaa_archetype(sc.name)
        if tag:
            ov.set_jhsaa_archetype(sc.name, tag)
    jhsaa._arch_cache.clear()
    top9, by = [], {g: [] for g in (9, 12)}
    for sc in schools:
        r = jhsaa.build_roster(sc, 2029)
        top9.append(sum(sorted((p.current_overall() for p in r), reverse=True)[:9]) / 9)
        for g in (9, 12):
            by[g].append(stat.mean([p.current_overall() for p in r if p.grade == g]))
    return {"top9": stat.mean(top9), 9: stat.mean(by[9]), 12: stat.mean(by[12])}


def test_a_tag_is_read_from_the_table_not_from_the_school_name():
    """The whole storage rule: generation must change when the TABLE changes, and a
    school is nothing but an ordinary program until it is tagged."""
    sc = _peers()[0]
    before = _profile([sc])
    ov.set_jhsaa_archetype(sc.name, "blue_blood")
    jhsaa._arch_cache.clear()
    after = _profile([sc], "blue_blood")
    assert after["top9"] > before["top9"]
    ov.clear_jhsaa_archetype(sc.name)
    jhsaa._arch_cache.clear()
    assert _profile([sc])["top9"] == pytest.approx(before["top9"])


def test_the_modifier_does_not_flatten_the_classification_model():
    """Additive, not a replacement — so the classification ladder must survive INSIDE
    each tag: a blue-blood small school is a strong SMALL-school program and still sits
    under a blue-blood big one.

    What it must NOT assert is that a blue-blood 3A-1A stays under an ORDINARY 7A. A
    powerhouse small school beating an average big one is the whole thesis of the talent
    model (Oregon 2026: Oregon Episcopal, smallest classification, No. 9 statewide), and
    an earlier version of this test had it backwards."""
    for tag in ("", "blue_blood", "development"):
        rung = [_profile(_peers(g, 10), tag)["top9"] for g in ("7A", "5A", "3A-1A")]
        assert rung == sorted(rung, reverse=True), (tag, rung)


def test_a_blue_blood_clusters_rather_than_carrying_one_star():
    """"Several strong players in the same roster" — so the lift has to reach the middle
    of the lineup, not just the number one."""
    peers = _peers()
    base, blue = _profile(peers), _profile(peers, "blue_blood")
    assert blue["top9"] - base["top9"] >= 2.0, (base, blue)


def test_a_blue_blood_arrives_already_strong():
    """It shows on DAY ONE — that is what the tradition and the feeder network buy. Its
    ninth-graders sit well clear of an ordinary program's and clear of a development
    program's, which is the whole distinction between the two."""
    peers = _peers()
    base, blue, dev = _profile(peers), _profile(peers, "blue_blood"), _profile(peers, "development")
    assert blue[9] - base[9] >= 3.0, (base, blue)
    assert blue[9] > dev[9], (blue, dev)


def test_a_development_program_arrives_ordinary_and_climbs_hardest():
    """Arrive good vs leave great. A development program can beat a blue blood outright
    in a given season — that is the point of it — but it has to do it over four years,
    so what is pinned here is the SHAPE, not which one wins."""
    peers = _peers()
    base = _profile(peers)
    blue = _profile(peers, "blue_blood")
    dev = _profile(peers, "development")
    assert dev[9] < blue[9], (dev, blue)                 # ordinary on arrival
    assert (dev[12] - dev[9]) > (blue[12] - blue[9]) > (base[12] - base[9])


def test_a_doubles_school_generates_completely_normally():
    """The roster is not better; the doubles is."""
    peers = _peers()
    assert _profile(peers, "doubles")["top9"] == pytest.approx(_profile(peers)["top9"])
    mod = jhsaa.ARCHETYPES["doubles"]
    assert (mod["mean"], mod["spread"], mod["pot"], mod["mature"]) == (0.0, 1.0, 0.0, 0.0)


def test_a_tag_only_ever_affects_the_school_it_is_on():
    """Upstarts are drawn over the WHOLE pool and tagged schools skipped at application.
    Filtering the pool instead made the table non-local: tagging one school changed which
    OTHER schools drew an upstart, because it changed what `rng.sample` sampled from."""
    peers = _peers(n=6)
    others = [s for s in _peers(n=12)[6:]]
    before = _profile(others)
    for sc in peers:
        ov.set_jhsaa_archetype(sc.name, "blue_blood")
    jhsaa._arch_cache.clear()
    after = {}
    top9 = []
    for sc in others:
        r = jhsaa.build_roster(sc, 2029)
        top9.append(sum(sorted((p.current_overall() for p in r), reverse=True)[:9]) / 9)
    assert stat.mean(top9) == pytest.approx(before["top9"])


def test_a_doubles_school_plays_better_doubles_and_identical_singles():
    peers = _peers(n=16)
    subject, field = peers[0], peers[1:]

    def record(tag):
        ov.clear_jhsaa_archetype(subject.name)
        if tag:
            ov.set_jhsaa_archetype(subject.name, tag)
        jhsaa._arch_cache.clear()
        s = d = [0, 0]
        s, d = [0, 0], [0, 0]
        for i, opp in enumerate(field):
            a = jhsaa.TeamSeason(school=subject, roster=jhsaa.build_roster(subject, 2029))
            b = jhsaa.TeamSeason(school=opp, roster=jhsaa.build_roster(opp, 2029))
            jhsaa.play_dual(a, b, seed=500 + i, phase="regular")
            for ln in a.schedule[-1]["lines"]:
                box = d if ln["slot"].startswith("D") else s
                box[0 if ln["home_won"] else 1] += 1
        return s, d

    s0, d0 = record("")
    s1, d1 = record("doubles")
    assert s0 == s1, ("singles must be untouched", s0, s1)
    assert d1[0] > d0[0], ("doubles must improve", d0, d1)


def test_the_doubles_lift_never_mutates_the_cached_prospect():
    """`build_roster` caches Prospects globally and shares them across saves, so an
    ephemeral per-match boost that edited one would become permanent everywhere."""
    sc = _peers()[0]
    p = jhsaa.build_roster(sc, 2029)[5]
    before = dict(p.current)
    jhsaa._doubles_lift(p, sc.name, 0)
    assert p.current == before


def test_upstarts_are_about_ten_at_a_time_and_expire():
    live = {y: jhsaa.upstarts(y, "") for y in range(2027, 2035)}
    for y, u in live.items():
        assert 5 <= len(u) <= 16, (y, len(u))
        assert all(0.15 <= v <= 0.30 for v in u.values()), u
    # a run ends: nobody is on one for the whole window
    forever = set.intersection(*(set(u) for u in live.values()))
    assert not forever, forever


def test_upstarts_are_deterministic_and_skip_tagged_programs():
    assert jhsaa.upstarts(2029, "s") == jhsaa.upstarts(2029, "s")
    assert jhsaa.upstarts(2029, "s") != jhsaa.upstarts(2029, "other")
    named = next(iter(jhsaa.upstarts(2029, "s")))
    ov.set_jhsaa_archetype(named, "blue_blood")
    jhsaa._arch_cache.clear()
    assert named not in jhsaa.upstarts(2029, "s")


def test_upstart_is_not_a_storable_tag():
    """It is a RUN. A stored tag would make it permanent, which is the one thing it must
    not be — so the editor never offers it."""
    assert "upstart" in jhsaa.ARCHETYPES              # it is a real archetype...
    from app.web import server                        # ...but not an editable one
    import inspect
    src = inspect.getsource(server)
    import re
    body = src.split("def editor_jhsaa_archetype")[1][:1500]
    accepted = re.search(r"if kind in \(([^)]*)\)", body).group(1)
    assert "upstart" not in accepted, accepted
    assert "blue_blood" in accepted and "development" in accepted and "doubles" in accepted


# --- the two layers -----------------------------------------------------------

def test_the_seed_list_reaches_generation():
    """`data/jhsaa/archetypes.json` is real data, not documentation: a seeded program
    must generate as its archetype with no override row present at all."""
    seed = jhsaa._arch_seed()
    assert seed, "no seeded programs"
    assert set(seed.values()) <= {"blue_blood", "development", "doubles"}
    school = next(iter(seed))
    assert jhsaa.archetype(school) == seed[school]


def test_an_override_promotes_demotes_and_reverts():
    """Three distinct intentions, and a single clear could only express two: set a tag,
    DEMOTE a seeded program ("none"), or drop the override and revert to the file."""
    seeded = next(iter(jhsaa._arch_seed()))
    base = jhsaa._arch_seed()[seeded]

    ov.set_jhsaa_archetype(seeded, "doubles")
    jhsaa._arch_cache.clear()
    assert jhsaa.archetype(seeded) == "doubles"

    ov.set_jhsaa_archetype(seeded, "none")
    jhsaa._arch_cache.clear()
    assert jhsaa.archetype(seeded) == ""          # demoted despite the seed

    ov.clear_jhsaa_archetype(seeded)
    jhsaa._arch_cache.clear()
    assert jhsaa.archetype(seeded) == base        # reverted to the file
