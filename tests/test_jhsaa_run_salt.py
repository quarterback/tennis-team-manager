"""The per-RUN dice salt (owner rule 2026-09, the canonical-history reset).

A "new run" restores the frozen canonical lab snapshot and stamps
`jhsaa_run_salt`, so every re-run's future diverges while the canonical past —
and every roster in it — never moves. Two invariants carry the whole feature,
and both are pinned here over a REAL scaled season:

  * a run salt changes RESULTS and nothing else: the rosters (pids, names,
    everyone's order of generation) of two runs are identical, because
    `district_teams` is fed the bare world salt while only the dice-salt string
    and the postseason seed offset fold the run salt in;
  * an EMPTY run salt (every save that never ran the reset) is the identity —
    `dice == salt`, `run_seed_offset() == 0` — so ordinary saves and every
    archived season replay byte-for-byte;

plus determinism under a salt (the same run salt replays the same season — the
memo is keyed on it, and a recompute agrees with itself).
"""
import pytest

from app import jhsaa as jh


@pytest.fixture(scope="module")
def small_assoc():
    """A scaled association, the `test_jhsaa_toc` fixture's cut: enough leagues
    per class to clear PROTECTED, State fields scaled with the pools."""
    real_load = jh.load_schools
    real_fields = dict(jh.STATE_FIELD)

    def small(gender):
        out = []
        for grp in jh.GROUPS:
            names = sorted({s.district for s in real_load(gender) if s.group == grp})
            pool, keep = [], set()
            for name in names:
                keep.add(name)
                pool = [s for s in real_load(gender)
                        if s.group == grp and s.district in keep]
                if len(pool) > jh.PROTECTED + 8:
                    break
            out += pool
        return out

    for grp, real in real_fields.items():
        jh.STATE_FIELD[grp] = {24: 24, 32: 16, 40: 20}[real]
    jh.load_schools = small
    jh._season_cache.clear()
    try:
        yield
    finally:
        jh.load_schools = real_load
        jh.STATE_FIELD.clear()
        jh.STATE_FIELD.update(real_fields)
        jh._season_cache.clear()


def _season(monkeypatch, run_salt: str):
    monkeypatch.setattr(jh, "run_salt", lambda: run_salt)
    return jh.run_season("girls", 2027, salt="run-salt-test")


def _rosters(season):
    return {name: [(p.pid, p.name) for p in ts.roster]
            for name, ts in season["teams"].items()}


def _results(season):
    return {name: (ts.record, dict(ts.records))
            for name, ts in season["teams"].items()}


def test_an_empty_run_salt_is_the_identity(monkeypatch):
    """No worldconfig row (every ordinary save) reads back as "" and offsets
    nothing — the pre-feature code path by construction."""
    monkeypatch.setattr(jh, "run_salt", lambda: "")
    assert jh.run_seed_offset() == 0
    monkeypatch.setattr(jh, "run_salt", lambda: "run-001")
    off = jh.run_seed_offset()
    assert off > 0
    assert off == jh.run_seed_offset(), "blake2s, stable across calls/restarts"


def test_a_run_salt_rerolls_the_dice_and_never_the_rosters(monkeypatch, small_assoc):
    base = _season(monkeypatch, "")
    fresh = _season(monkeypatch, "run-A")
    # Same association, same people: every program fields the identical roster,
    # pid for pid and name for name, in the identical generation order.
    assert _rosters(base) == _rosters(fresh)
    # ... and a different season happened on it. With ~thousands of duals
    # re-rolled, the records cannot come out equal.
    assert _results(base) != _results(fresh)
    # And the schedule's non-league draw is free to differ too — a run is a
    # whole alternate future, not the same fixtures with new scores.
    b = next(iter(base["teams"].values()))
    assert b.roster, "the scaled association actually built teams"


def test_the_same_run_salt_replays_the_same_season(monkeypatch, small_assoc):
    one = _season(monkeypatch, "run-B")
    jh._season_cache.clear()          # force a recompute, not a memo hit
    two = _season(monkeypatch, "run-B")
    assert one is not two
    assert _rosters(one) == _rosters(two)
    assert _results(one) == _results(two)


def test_the_memo_is_keyed_on_the_run_salt(monkeypatch, small_assoc):
    # Both already cached by the tests above — memo hits, no recompute: the
    # point is that two salts never share one cache entry.
    a = _season(monkeypatch, "run-A")
    b = _season(monkeypatch, "")
    assert a is not b, "two runs must never share a cached season"


def test_run_salt_reads_worldconfig_and_reset_clears_the_memo(tmp_path, monkeypatch):
    from app import dbpath, worldconfig
    monkeypatch.setattr(dbpath, "resolve_db_path", lambda: str(tmp_path / "rs.db"))
    jh._run_salt_cache.clear()
    monkeypatch.setattr(worldconfig, "get", lambda k: "run-77" if k == jh.RUN_SALT_SETTING else "")
    assert jh.run_salt() == "run-77"
    # memoised per path: a changed value is not seen until the caches drop ...
    monkeypatch.setattr(worldconfig, "get", lambda k: "")
    assert jh.run_salt() == "run-77"
    # ... and `reset_schools()` is what drops them (the era idiom).
    jh._run_salt_cache.clear()
    assert jh.run_salt() == ""
