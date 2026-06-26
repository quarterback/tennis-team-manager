# AAR — Junior circuit is lazy board enrichment, not on the world-advance path

**Date:** 2026-06-26
**Scope:** Why the app "spun / wouldn't load" after the recruit-pool expansion, and how
the junior circuit is now wired. Fixes a production crash-loop.

## Problem (the spin)

The single most expensive compute in the app is `junior_circuit.run_junior_circuit` — a
full simulated junior season (singles + doubles, week by week, with per-recruit
development) over the **entire** `RECRUIT_POOL` (~2,500/gender). On a clean world this
was **~50s per gender**.

It was being run from inside `world.recruit_class`, which is the class the **simulation's
signing logic** resolves through (`national_class` → `recruit_class`). So the circuit
fired on the **world-advance hot path**: the first `advance_week` signed both genders and
paid the circuit **twice → ~110–120s in one request**.

Production runs `gunicorn --workers 1 --timeout 120` (Procfile / Dockerfile). That single
blocking request:
- sat right at / over the **120s worker timeout** → gunicorn killed the worker
  **mid-build**, so the class was never cached;
- on restart the next request rebuilt from scratch and died again → a **permanent
  crash-loop** where the app never loads;
- meanwhile the one worker was 100%-busy (GIL-bound), so every other request — including
  Fly's `/api/health` check — spun.

The recruit pool was bumped 1,000 → 2,500 on 2026-06-22 ("Expand rosters + source
walk-ons from a demand-sized recruit pool"). That 2.5× made an already-heavy circuit
cross the timeout — hence "broke from the last deploys."

## Key fact

The simulation's signing logic does **not** use the junior circuit at all. `_pick_school`
/ `national_class` rank on `rank_class` (`_recruiting_score` = ability + scouting) and the
budget economy. The junior circuit only feeds the **web board** (`points_rankings`,
résumé/finishes, `junior_tier`). So the circuit had no business on the signing path.

## Changes

### 1. `recruit_class` no longer runs the circuit (`app/world.py`)
It now builds the class + `rank_class` only — exactly what signing needs. This is the hot
path (world advance), and it's now fast (first advance ~17s for gen+rank+signing, ~5s
after).

### 2. New `world.board_class` runs the circuit lazily (`app/world.py`)
The web board accessor (`web/state.get_recruits`) now calls `board_class`, which returns
the **same cached class object** and runs `run_junior_circuit` + `points_rankings` on it
once, in place. `run_junior_circuit` is already idempotent via `klass.circuit_done`, so
repeat board views are free. The cost is paid only when a recruiting/junior board is
actually viewed — ~50s the first time per gender, then cached.

### 3. Gunicorn timeout 120 → 300 (`Procfile`, `Dockerfile`)
A safety margin so the one-time board build completes and caches instead of being killed
mid-build. Normal play (advance) no longer goes anywhere near it.

## Net effect

- World advance: **117s → ~17s** first step, **~5s** after. Health checks pass during
  normal play.
- First recruit-board view: **~50s once per gender**, then cached (sub-second).
- No more crash-loop; board results are byte-for-byte unchanged (same circuit, same
  inputs — only *when* it runs moved).

## Notes / gotchas

- Board determinism is unchanged: the circuit still runs over the full pool with the same
  salt-seeded RNG. This AAR moves *when* it runs, not *what* it computes.
- Do NOT re-introduce the circuit into `recruit_class` (or anything `national_class`
  touches) — that puts it back on the advance path and re-creates the spin.
- If first-board latency ever needs trimming, scope the circuit field to the
  competitively-ranked cadre (the pool's 1★/walk-on tail, added for roster turnover, does
  not need a simulated junior résumé) — but that changes the board for the tail, so treat
  it as a deliberate game-facing change, not a perf tweak.
