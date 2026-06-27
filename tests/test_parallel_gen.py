"""Parallel generation must be byte-identical to serial.

World build (per-universe) and the junior circuit (per-gender) are farmed to
worker processes; the sim is salt-deterministic, so a child rebuilds a unit
identically to building it inline. These tests pin that guarantee — the speedup
must never change a single generated value.
"""
import json
import random

import app.world as W
from app import worldconfig
from app.juniors import generate_class, rank_class, points_rankings, RecruitClass
from app.junior_circuit import run_junior_circuit


def _serial_universe(d, g, salt):
    import app.ncaa as ncaa
    ncaa.WORLD_SALT = salt
    W.reset_caches()
    uni = W._seed_year0(d, g)
    return {s: [W.prospect_to_dict(p) for p in r] for s, r in uni.items()}


def test_build_worker_matches_serial():
    """The build worker output == an inline _seed_year0 build, for the same salt."""
    salt = "pgtest"
    cfg = worldconfig.snapshot()
    d, g = "D4", "women"
    serial = _serial_universe(d, g, salt)
    W.reset_caches()
    rd, rg, par = W._build_universe((salt, cfg, d, g))
    assert (rd, rg) == (d, g)
    assert json.dumps(par, sort_keys=True) == json.dumps(serial, sort_keys=True)


def test_pmap_pool_matches_serial(monkeypatch):
    """The actual process pool (spawn) returns the same data as serial."""
    monkeypatch.setenv("GEN_WORKERS", "2")
    from app.parallel import pmap, workers_for
    salt = "pgpool"
    cfg = worldconfig.snapshot()
    tasks = [(salt, cfg, "D4", "women"), (salt, cfg, "D4", "men")]
    res = {(d, g): uni for (d, g, uni) in pmap(W._build_universe, tasks,
                                               workers=workers_for(len(tasks)))}
    for (d, g) in (("D4", "women"), ("D4", "men")):
        assert json.dumps(res[(d, g)], sort_keys=True) == \
            json.dumps(_serial_universe(d, g, salt), sort_keys=True)


def test_enriched_class_reconstruction_is_lossless():
    """How prime_recruit_classes rebuilds a class from a worker's serialized
    prospects (prospect_from_dict + rank_class) must reproduce the original
    enriched class byte-for-byte — including the junior-circuit résumé."""
    k = generate_class(random.Random(3), n=80, grad_year=2027, gender="male")
    rank_class(k)
    run_junior_circuit(k, seed="rt")
    points_rankings(k)
    before = {p.pid: W.prospect_to_dict(p) for p in k.recruits}

    k2 = RecruitClass(grad_year=2027, gender="male",
                      recruits=[W.prospect_from_dict(d) for d in
                                (W.prospect_to_dict(p) for p in k.recruits)])
    rank_class(k2)                       # what the parent re-runs after reconstruct
    after = {p.pid: W.prospect_to_dict(p) for p in k2.recruits}

    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)
