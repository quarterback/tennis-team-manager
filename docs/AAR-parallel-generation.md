# AAR — Parallel world build + junior circuit (use the cores)

**Date:** 2026-06-27
**Scope:** Spread the two heavy, CPU-bound generation steps — the year-0 world
build and the per-gender junior circuit — across processes, so a multi-core
machine actually speeds up world creation and the first advance. Determinism is
preserved exactly.

## Why

The heavy work is single-threaded Python holding the GIL, so it ignored every
core but one — adding cores or RAM did nothing. But the work is embarrassingly
parallel: the 8 universes' rosters and the two genders' junior circuits are
independent and **salt-deterministic**, so each can be rebuilt in a child process
byte-for-byte identically.

## What's parallel

| Step | Where | Unit of work | Measured |
|---|---|---|---|
| Year-0 world build | `world.get_or_create` | one universe (×8) | **18.7s → 7.2s** (2.6× on 4 cores) |
| Junior circuit | `world.prime_recruit_classes`, called at the top of `advance_week` | one gender's enriched class (×2) | **73s → 41s** (1.8× on 2 used cores) |

Both are byte-identical to the serial build — pinned by `tests/test_parallel_gen.py`.

## How (`app/parallel.py`)

- `pmap(fn, items)` maps a top-level fn over items across a **spawn** process pool
  (fork is unsafe under gunicorn's threaded worker — inherited locks deadlock),
  results in input order. **Always has a serial fallback**: one worker, one item,
  or any pool error → runs inline. Correctness never depends on multiprocessing,
  only speed.
- `workers_for(n)` = `min(cores, n, cap)`, overridable with `GEN_WORKERS` (the test
  suite sets `GEN_WORKERS=1` to stay serial/fast; ops can pin it too).

### Build
`_build_universe((salt, cfg, division, gender))` rebuilds one universe and returns
its rosters as serialized dicts; the parent inserts them. Capped at
`_BUILD_WORKER_CAP = 4` because each worker holds a full universe (~3.5k rich
prospects) in RAM — raise it alongside machine memory, not just cores.

### Junior circuit
`_build_board_class((salt, cfg, gender, grad_year))` runs the (expensive) circuit
for one gender and returns the enriched prospects serialized. The parent
reconstructs the class with `prospect_from_dict` and **re-runs `rank_class`** (which
`recruit_class` runs too), then caches it with `circuit_done=True` — so the
following per-gender signing is a cache hit instead of running men's then women's
circuit back to back. Best-effort: only engages with 2+ uncached classes AND 2+
cores; otherwise the classes just build lazily during signing as before.

## Two correctness subtleties (both handled)

1. **Config in children.** Children get the parent's `worldconfig.snapshot()` and
   prime it directly (`worldconfig.prime_cache`), so generation never depends on a
   child being able to read the DB (it can't, if the volume isn't mounted — and a
   silent fallback to defaults would desync the rosters).
2. **Round-trip vs `__post_init__`.** `prospect_from_dict` re-runs `__post_init__`,
   which recomputes a default `recruit_stars` for an unrated (0-star) tail recruit
   (0 → 1). Re-running `rank_class` after reconstruction re-assigns stars/rank/tier
   deterministically, erasing that artifact; the circuit's junior fields (now real
   `Prospect` dataclass fields) round-trip losslessly.

## Notes / future
- The Fly machine size is unchanged (2 cpus / 4 GB) — the win is free on current
  hardware and scales if cores are added. If you raise `cpus` past ~4, raise
  `memory` too (build holds `min(cores,4)` universes at once) or lower
  `_BUILD_WORKER_CAP`.
- Within a single circuit (one gender) the work is still serial; the next lever, if
  ever needed, is parallelizing the independent events within a circuit week.
- Loading overlay (AAR-less, see base.html) already makes the remaining wait read
  as "working", so this is pure speedup, not a correctness dependency.
