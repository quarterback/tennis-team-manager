"""Process-pool helpers for the CPU-bound, embarrassingly-parallel generation
work (year-0 world build, the per-gender junior circuit).

The sim is salt-deterministic, so each unit of work (one universe's rosters, one
gender's recruit class) can be rebuilt independently in a child process and the
result is byte-identical to building it inline. We use a SPAWN context — the web
worker runs gunicorn with threads, and forking a threaded process risks inherited
locks/deadlocks; spawn pays a re-import cost but is safe.

`pmap` always has a serial fallback: if there's one worker, one item, or the pool
fails to start for any reason, it runs inline. Correctness never depends on
multiprocessing being available — only speed does.
"""
from __future__ import annotations

import os
from typing import Callable, Iterable, List


def cpu_count() -> int:
    try:
        return max(1, os.cpu_count() or 1)
    except Exception:
        return 1


def workers_for(n_items: int, *, cap: int | None = None) -> int:
    """How many worker processes to use for `n_items` units of work. Bounded by
    cores, the item count, and an optional cap (memory ceiling — each worker holds
    a full unit in RAM, so the build caps lower than the circuit)."""
    w = min(cpu_count(), max(1, n_items))
    if cap is not None:
        w = min(w, cap)
    # Honour an explicit override (tests / ops): GEN_WORKERS=1 forces serial.
    env = os.environ.get("GEN_WORKERS")
    if env:
        try:
            w = max(1, min(w, int(env)))
        except ValueError:
            pass
    return max(1, w)


def pmap(fn: Callable, items: Iterable, *, workers: int | None = None) -> List:
    """Map `fn` over `items` across processes, results in input order. `fn` must be
    a top-level (importable) function and both args and return value picklable.
    Falls back to serial on a single worker, a single item, or any pool error."""
    items = list(items)
    if not items:
        return []
    w = workers if workers is not None else workers_for(len(items))
    if w <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    try:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=min(w, len(items)), mp_context=ctx) as ex:
            return list(ex.map(fn, items))
    except Exception:
        # Pool unavailable (sandboxed env, fork restrictions, OOM on spawn, …):
        # never fail the request over a perf optimisation — just run inline.
        return [fn(x) for x in items]
