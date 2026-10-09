"""The school page's individual-champion index (`world._school_champion_index`):
one fold per (world, gender, newest year) under a burst of threads, older
generations evicted when a new season publishes, and a build that straddles
`reset()` never publishes into the new world's cache (review 2026-10, P1/P2)."""
import threading

import app.world as wd


def _patch(monkeypatch, years, counter, barrier=None):
    monkeypatch.setattr(wd, "jhsaa_years", lambda wid, g: years)

    def fold(wid, g):
        counter.append((wid, g))
        if barrier is not None:
            barrier.wait(timeout=5)
        return {"School": [{"year": years[0]}]}
    monkeypatch.setattr(wd, "_fold_school_champion_index", fold)


def test_a_burst_of_misses_folds_once(monkeypatch):
    wd._reset_school_champion_index()
    calls = []
    start = threading.Barrier(16)
    _patch(monkeypatch, [7, 6, 5], calls)
    results = []

    def go():
        start.wait(timeout=5)
        results.append(wd._school_champion_index(1, "girls"))
    ts = [threading.Thread(target=go) for _ in range(16)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=10)
    assert len(results) == 16
    assert len(calls) == 1
    assert all(r is results[0] for r in results)


def test_a_new_season_evicts_the_older_generation(monkeypatch):
    wd._reset_school_champion_index()
    calls = []
    _patch(monkeypatch, [7], calls)
    wd._school_champion_index(1, "girls")
    wd._school_champion_index(1, "boys")
    _patch(monkeypatch, [8], calls)
    wd._school_champion_index(1, "girls")
    keys = sorted(wd._schoolchamps_cache)
    assert keys == [(1, "boys", 7), (1, "girls", 8)]


def test_a_build_that_straddles_a_reset_is_not_published(monkeypatch):
    wd._reset_school_champion_index()
    calls = []
    _patch(monkeypatch, [3], calls)
    real_fold = wd._fold_school_champion_index

    def racing_fold(wid, g):
        wd._reset_school_champion_index()       # a start_new mid-build
        return real_fold(wid, g)
    monkeypatch.setattr(wd, "_fold_school_champion_index", racing_fold)
    out = wd._school_champion_index(1, "girls")
    assert out                                   # the caller still gets its answer
    assert (1, "girls", 3) not in wd._schoolchamps_cache
    wd._reset_school_champion_index()
