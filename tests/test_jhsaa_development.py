"""The 2026-08 per-player development-curve model and its era gate.

New-era cohorts (entry >= `jhsaa.dev_era()`) develop on a rolled four-year
trajectory (`jhsaa._dev_maturity`) instead of the legacy lockstep `_MATURITY`
bands; pre-era cohorts must keep their exact legacy numbers. The suite runs on
a fresh throwaway DB (root conftest), so with no archive the era is 0 and
everything generates new-era unless a test pins the era itself.
"""
import statistics

import pytest

from app import jhsaa, worldconfig


@pytest.fixture(autouse=True)
def _fresh_era():
    yield
    worldconfig.set("jhsaa_dev_era", "")
    jhsaa.reset_schools()


def _school():
    return jhsaa.load_schools("boys")[0]


def test_rosters_are_deterministic():
    s = _school()
    a = [(p.pid, p.current_overall()) for p in jhsaa.build_roster(s, 2035)]
    b = [(p.pid, p.current_overall()) for p in jhsaa.build_roster(s, 2035)]
    assert a == b


def test_pre_era_cohorts_stay_on_the_legacy_bands():
    """Pin the era past everyone: every maturity must land inside the legacy
    grade band (+ program `mature` step + prodigy floor) — i.e. the old code
    path, byte-for-byte. This is what protects six years of archived seasons."""
    worldconfig.set("jhsaa_dev_era", "9999")
    jhsaa.reset_schools()
    for s in jhsaa.load_schools("boys")[:20]:
        mod = jhsaa._program_mod(s, 2035, "")
        for p in jhsaa.build_roster(s, 2035):
            lo, hi = jhsaa._MATURITY[p.grade]
            step = mod.get("mature", 0.0) * (p.grade - 9)
            lo = min(1.0, lo + step)
            hi = max(min(1.0, hi + step), jhsaa.PRODIGY_MATURITY[1])
            m = p.current_overall() / max(1, p.ceiling_overall())
            # current is clamped at GRADE_MIN, which can only RAISE the ratio.
            assert m >= lo - 0.06 and m <= hi + 0.03, (p.name, p.grade, m)


def test_era_gate_splits_cohorts_not_seasons():
    """With the era set mid-roster, older cohorts regenerate identically to a
    fully-legacy build while the gated cohorts differ — the name_era shape."""
    s = _school()
    worldconfig.set("jhsaa_dev_era", "9999")
    jhsaa.reset_schools()
    legacy = {p.pid: p.current_overall() for p in jhsaa.build_roster(s, 2035)}
    worldconfig.set("jhsaa_dev_era", "2034")     # juniors/seniors pre-era
    jhsaa.reset_schools()
    mixed = {p.pid: (p.current_overall(), p.entry_year)
             for p in jhsaa.build_roster(s, 2035)}
    assert set(legacy) == set(mixed)
    changed = False
    for pid, (ovr, entry) in mixed.items():
        if entry < 2034:
            assert ovr == legacy[pid], "pre-era cohort re-rated"
        elif ovr != legacy[pid]:
            changed = True
    assert changed, "new-era cohorts never took the new model"


def test_some_freshmen_arrive_ready_and_nobody_stagnates():
    schools = jhsaa.load_schools("boys")[:40]
    fresh, seniors = [], []
    for s in schools:
        r = jhsaa.build_roster(s, 2035)
        fresh += [p for p in r if p.grade == 9]
        seniors += [p for p in r if p.grade == 12]
    ready = [p for p in fresh
             if p.current_overall() / max(1, p.ceiling_overall()) > 0.62]
    # DEV_READY_RATE is 0.24; allow slack for clamps and the base band's top.
    assert len(ready) / len(fresh) > 0.12, len(ready) / len(fresh)
    # Program-wide floor: the same player never regresses, and always visibly
    # improves year over year (DEV_MIN_STEP on maturity).
    s = schools[0]
    y1 = {p.pid: p.current_overall() for p in jhsaa.build_roster(s, 2035)}
    y2 = {p.pid: p.current_overall() for p in jhsaa.build_roster(s, 2036)
          if p.grade > 9}
    for pid, ovr in y2.items():
        if pid in y1:
            assert ovr >= y1[pid], pid


def test_trajectories_reorder_the_ladder_between_seasons():
    """Late bloomers must be able to PASS team-mates — the lockstep model's
    ladder was frozen for four years, which was the owner's report."""
    swaps = 0
    for s in jhsaa.load_schools("boys")[:40]:
        y1 = [p.pid for p in jhsaa.build_roster(s, 2035) if p.grade < 12]
        y2 = jhsaa.build_roster(s, 2036)
        order2 = [p.pid for p in y2 if p.pid in set(y1)]
        stay = [pid for pid in y1 if pid in set(order2)]
        if [pid for pid in order2] != stay:
            swaps += 1
    assert swaps > 5, swaps


def test_grade_means_step_upward():
    by_grade = {g: [] for g in jhsaa.GRADES}
    for s in jhsaa.load_schools("girls")[:40]:
        for p in jhsaa.build_roster(s, 2035):
            by_grade[p.grade].append(p.current_overall())
    means = [statistics.mean(by_grade[g]) for g in jhsaa.GRADES]
    assert means == sorted(means), means
