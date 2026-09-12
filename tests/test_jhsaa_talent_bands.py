"""JHSAA program TALENT TIERS (owner rule 2026-09) — see
docs/AAR-jhsaa-program-talent-tiers.md.

Three layers: the CLASSIFICATION is the structural environment (roster size,
nothing about ability), the PROGRAM TIER is where this school sits on one
association-wide scale, and the COHORT ROLL is year-to-year variation around
that identity. Tier ranges are in TEAM terms (mean current OVR of the top
eleven). The tier table and the per-program assignment are data
(`data/jhsaa/talent_bands.json`), edited from `/jhsaa/programs`, with a
per-save override table on top exactly like archetypes.
"""
import json
import statistics as stat

import pytest

from app import jhsaa
from app import overrides as ov
from app import worldconfig as wc


@pytest.fixture(autouse=True)
def _clean():
    """Clear the OVERRIDE layer only — the seed file is real data and stays.
    Force the tier era to 0 so every cohort in this test's save draws from its
    tier, whatever the module-level DB happens to have archived."""
    ov.init_schema()
    prev = wc.get("jhsaa_band_era")
    wc.set("jhsaa_band_era", "0")
    for n in list(ov.get_jhsaa_bands()):
        ov.clear_jhsaa_band(n)
    jhsaa.reset_schools()
    yield
    for n in list(ov.get_jhsaa_bands()):
        ov.clear_jhsaa_band(n)
    wc.set("jhsaa_band_era", prev if prev is not None else "")
    jhsaa.reset_schools()


def _team(school, year=2030):
    r = jhsaa.build_roster(school, year)
    top = sorted((p.current_overall() for p in r), reverse=True)[:11]
    return sum(top) / len(top)


def _sample(n=6, gender="boys"):
    """Schools NOT on an upstart run and untagged, so the tier is the only lever."""
    live = set(jhsaa.upstarts(2030, "")) | set(jhsaa._arch_seed())
    return [s for s in jhsaa.load_schools(gender) if s.name not in live][:n]


def _set(schools, tier):
    for s in schools:
        ov.set_jhsaa_band(s.name, tier)
    jhsaa.reset_schools()


# --- the tier table -------------------------------------------------------------

def test_the_tier_table_is_data_and_bottom_to_top():
    tiers = jhsaa.band_tiers()
    assert len(tiers) >= 10, "the owner's ladder has many rungs, not five"
    narrow = [t for t in tiers if not t["wide"]]
    assert all(t["lo"] < t["hi"] for t in tiers)
    assert [t["lo"] for t in narrow] == sorted(t["lo"] for t in narrow)
    assert narrow[0]["lo"] <= 20 and narrow[-1]["hi"] >= 75, "a real bottom and a real top"
    assert any(t["wide"] for t in tiers), "volatile tiers exist"
    with open(jhsaa._BAND_SEED_PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    assert [t["key"] for t in doc["tiers"]] == [t["key"] for t in tiers]


def test_every_program_has_a_seeded_tier_and_the_roll_agrees_with_it():
    """The seed file is the RECORD (`scripts/roll_talent_bands.py`), and the roll it
    was written from is deterministic on the name — so a school missing from the
    file would generate exactly what the file says."""
    seed = jhsaa._band_seed()
    names = {r["name"] for r in jhsaa.playup_rows()}
    assert names <= set(seed), sorted(names - set(seed))[:5]
    amap = jhsaa._arch_map(ov.jhsaa_archetype_version())
    for n in sorted(names)[:200]:
        assert seed[n] == jhsaa.rolled_band(n, amap.get(n, ""))


def test_the_initial_roll_is_thick_in_the_middle_and_thin_at_the_ends():
    seed = jhsaa._band_seed()
    tiers = jhsaa.band_tiers()
    counts = {t["key"]: sum(1 for v in seed.values() if v == t["key"]) for t in tiers}
    assert counts["average"] > counts["abysmal"] and counts["average"] > counts["dynasty"]
    assert counts["abysmal"] >= 10, "there is a genuine bottom"
    assert counts["dynasty"] >= 5, "and a genuine top"


# --- assignment: override over seed over roll --------------------------------------

def test_an_override_wins_a_none_reverts_to_the_roll_and_a_clear_reverts_to_the_seed():
    s = _sample(1)[0]
    seeded = jhsaa._band_seed()[s.name]
    assert jhsaa.program_band(s.name) == seeded
    other = next(t["key"] for t in jhsaa.band_tiers() if t["key"] != seeded)
    ov.set_jhsaa_band(s.name, other); jhsaa.reset_schools()
    assert jhsaa.program_band(s.name) == other
    ov.set_jhsaa_band(s.name, "none"); jhsaa.reset_schools()
    assert jhsaa.program_band(s.name) == jhsaa.rolled_band(s.name)
    ov.clear_jhsaa_band(s.name); jhsaa.reset_schools()
    assert jhsaa.program_band(s.name) == seeded


def test_an_assignment_to_a_retired_tier_reads_as_the_roll():
    s = _sample(1)[0]
    ov.set_jhsaa_band(s.name, "no_such_tier"); jhsaa.reset_schools()
    assert jhsaa.program_band(s.name) == jhsaa.rolled_band(s.name)
    assert not jhsaa.band_is_assigned(s.name)


def test_the_fingerprint_moves_when_the_table_does():
    s = _sample(1)[0]
    before = ov.jhsaa_band_version()
    ov.set_jhsaa_band(s.name, "abysmal")
    assert ov.jhsaa_band_version() != before


def test_editing_the_tier_table_is_a_file_write_and_survives_a_reload(tmp_path, monkeypatch):
    """The whole point: retuning the ladder is data, never code."""
    import shutil
    scratch = tmp_path / "talent_bands.json"
    shutil.copy(jhsaa._BAND_SEED_PATH, scratch)
    monkeypatch.setattr(jhsaa, "_BAND_SEED_PATH", str(scratch))
    jhsaa.reset_schools()
    tiers = [dict(t) for t in jhsaa.band_tiers()]
    tiers[0]["lo"], tiers[0]["hi"] = 15, 26
    tiers.append({"key": "test_tier", "label": "Test", "lo": 40, "hi": 45, "wide": True,
                  "weight": 0})
    jhsaa.set_band_tiers(tiers)
    jhsaa.reset_schools()
    got = jhsaa.band_tiers()
    assert got[0]["lo"] == 15 and got[0]["hi"] == 26
    assert jhsaa.band_tier("test_tier")["wide"] is True
    s = _sample(1)[0]
    res = jhsaa.bulk_edit_band_seed("test_tier", [s.name, "No Such School"])
    assert res == {"applied": [s.name], "unknown": ["No Such School"]}
    assert jhsaa.program_band(s.name) == "test_tier"


# --- the cohort centre ----------------------------------------------------------------

def test_a_narrow_tier_is_a_stable_centre_with_a_small_jitter():
    s = _sample(1)[0]
    _set([s], "average")
    t = jhsaa.band_tier("average")
    centres = [jhsaa.band_centre(s, y) for y in range(2027, 2047)]
    assert all(t["lo"] <= c <= t["hi"] for c in centres)
    assert max(centres) - min(centres) <= 2 * jhsaa.BAND_COHORT_JITTER + 1e-9
    assert len(set(centres)) > 1, "no two years are copies"
    assert jhsaa.band_centre(s, 2030) == jhsaa.band_centre(s, 2030), "deterministic"


def test_a_wide_tier_rerolls_its_centre_across_the_whole_range_per_cohort():
    s = _sample(1)[0]
    _set([s], "volatile_wide")
    t = jhsaa.band_tier("volatile_wide")
    centres = [jhsaa.band_centre(s, y) for y in range(2027, 2067)]
    assert all(t["lo"] <= c <= t["hi"] for c in centres)
    assert max(centres) - min(centres) > 0.6 * (t["hi"] - t["lo"]), centres


def test_the_centre_is_seeded_on_identity_not_display_name():
    s = _sample(1)[0]
    _set([s], "average")
    import dataclasses
    renamed = dataclasses.replace(s, name="Renamed Academy", source=s.ident)
    ov.set_jhsaa_band("Renamed Academy", "average"); jhsaa.reset_schools()
    assert jhsaa.band_centre(renamed, 2030) == jhsaa.band_centre(s, 2030)


# --- generation --------------------------------------------------------------------------

def test_the_tier_sets_the_team_on_one_scale_regardless_of_classification():
    """A 9A can be abysmal and a 1A can be a dynasty: the class sets roster size
    and nothing about ability."""
    schools = jhsaa.load_schools("boys")
    live = set(jhsaa.upstarts(2030, "")) | set(jhsaa._arch_seed())
    big = [s for s in schools if s.classification == "9A" and s.name not in live][:4]
    small = [s for s in schools if s.classification == "1A" and s.name not in live][:4]
    assert big and small
    _set(big, "abysmal"); _set(small, "dynasty")
    assert max(_team(s) for s in big) < min(_team(s) for s in small)
    assert all(_team(s) < 36 for s in big), [_team(s) for s in big]
    # A 1A carries 14-16 players to a 9A's 20-24, so fewer draws lift its top
    # eleven less — the depth the classification still buys. Loose on purpose.
    assert all(_team(s) > 54 for s in small), [_team(s) for s in small]


def test_each_tier_lands_inside_its_own_range_in_team_terms():
    """The ranges are what the owner reads off a program page, so the calibration
    from ceiling centre to top-eleven mean has to hold — loosely (a sample of a
    dozen programs, one season), and with the attribute floor of 20 binding at
    the very bottom."""
    schools = _sample(12)
    for key in ("poor", "average", "good", "elite"):
        t = jhsaa.band_tier(key)
        _set(schools, key)
        got = stat.mean(_team(s) for s in schools)
        assert t["lo"] - 3 <= got <= t["hi"] + 3, (key, got, t)


def test_an_abysmal_roster_is_mostly_bad_players_not_a_shifted_ladder():
    """The old model handed a bad school one 60 and a 25 — the same 35-point ladder
    shifted down. A bottom-tier program's BEST player is now ordinary."""
    schools = _sample(6)
    _set(schools, "abysmal")
    for s in schools:
        r = jhsaa.build_roster(s, 2030)
        top = sorted((p.current_overall() for p in r), reverse=True)
        # ONE stray star is allowed: `generate_prospect` rolls a nation elite spike
        # per player regardless of the ceiling passed in (the kid who is just good
        # and happens to go to a bad school), and that is a feature. Two is not
        # an abysmal program.
        assert top[1] < 52, (s.name, top[:3])


def test_the_era_gate_keeps_earlier_cohorts_byte_identical():
    """Players are rebuilt from seed, so a tier must not rewrite a roster that is
    already in the archive: cohorts entering before `band_era()` draw exactly as
    they did on the classification model."""
    s = _sample(1)[0]
    wc.set("jhsaa_band_era", "9999"); jhsaa.reset_schools()
    legacy = [(p.pid, p.name, p.current_overall(), p.ceiling_overall())
              for p in jhsaa.build_roster(s, 2030)]
    wc.set("jhsaa_band_era", "2029"); jhsaa.reset_schools()
    mixed = {p.pid: (p.name, p.current_overall(), p.ceiling_overall(), p.entry_year)
             for p in jhsaa.build_roster(s, 2030)}
    for pid, name, cur, ceil in legacy:
        got = mixed[pid]
        assert got[0] == name, "names never move"
        if got[3] < 2029:
            assert (got[1], got[2]) == (cur, ceil), (pid, got, cur, ceil)
    assert any(e < 2029 for _, _, _, e in mixed.values())
    assert any(e >= 2029 for _, _, _, e in mixed.values())


def test_archetypes_still_stack_on_the_tier():
    schools = _sample(6)
    _set(schools, "average")
    base = stat.mean(_team(s) for s in schools)
    for s in schools:
        ov.set_jhsaa_archetype(s.name, "blue_blood")
    jhsaa._arch_cache.clear(); jhsaa.reset_schools()
    try:
        blue = stat.mean(_team(s) for s in schools)
    finally:
        for s in schools:
            ov.clear_jhsaa_archetype(s.name)
        jhsaa._arch_cache.clear(); jhsaa.reset_schools()
    assert blue - base >= 4.0, (base, blue)


def test_the_association_is_genuinely_unequal_now():
    """The reason for all of it (the 2080 export): team-strength sd 8.3, weakest
    boys program 33, 71% of programs between 40 and 60. Loose bounds, not goldens."""
    vals = [_team(s) for s in jhsaa.load_schools("boys")[::3]]
    assert stat.pstdev(vals) >= 10.5, stat.pstdev(vals)
    assert min(vals) < 28, min(vals)
    assert sum(40 <= v < 60 for v in vals) / len(vals) < 0.65


# --- the editor -------------------------------------------------------------------------

def test_the_program_editor_carries_the_tier_and_a_tier_board():
    s = _sample(1)[0]
    ed = jhsaa.program_editor(s.name, board="band")
    assert ed["selected"]["band"] == jhsaa.program_band(s.name)
    assert ed["selected"]["band_assigned"] is True
    assert [k for k, _ in ed["boards"]].count("band") == 1
    assert {c[0] for c in ed["cats"]} == {t["key"] for t in jhsaa.band_tiers()}
    assert sum(c[2] for c in ed["cats"]) == len(jhsaa.playup_rows())
    ov.set_jhsaa_band(s.name, "abysmal"); jhsaa.reset_schools()
    ed = jhsaa.program_editor(s.name)
    assert ed["selected"]["band"] == "abysmal" and ed["selected"]["band_edited"]
    assert any(c["name"] == s.name for c in ed["edited"])
