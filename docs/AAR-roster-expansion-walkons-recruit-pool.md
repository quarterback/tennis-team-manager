# AAR — Roster expansion, walk-on sourcing, and a recruit pool sized to demand

**Date:** 2026-06-21
**Scope:** Roster capacity, where walk-ons come from, and the recruit-pool size. Fixes
"teams sign only ~8 and good players go unsigned."

## Problem

Every roster was capped at 8 (`ROSTER_SIZE`), and the recruit pool was a bounded 1,000
per gender — far below the ~2,200 annual roster turnover. So programs filled the gap
with **auto-generated walk-ons**, and genuinely good juniors went unsigned because
there were no slots and no pool depth.

## Changes

### 1. Roster capacity is per-division (`ncaa.roster_cap`)
| Division | core (funded) | + walk-on slots | = cap |
|---|---|---|---|
| D1 | 8 | 4 | **12** |
| D2 | 6 | 4 | **10** |
| D3 / D4 | 3 | 13 | **16** |

Threaded through `_base_roster`, `world._normalize` / `refill_walkons` / portal
`open_slot`, and `league` (`_normalize` / `open_slot` / `_refill`). The match lineup is
still 6 singles + doubles, independent of roster size.

### 2. Walk-on sourcing by division (`ncaa.autogen_walkons`)
- **D1 / D2:** walk-on depth comes from the recruiting pool ONLY — never
  auto-generated. A program that doesn't sign enough simply carries fewer walk-ons
  ("up to" the cap, not a requirement).
- **D3 / D4:** may auto-generate walk-ons — but only after real pool recruits are
  exhausted (below).

### 3. No junior goes unsigned (`world.assign_pool_walkons`)
New rollover step, after signings and before auto-gen: every recruit still unsigned
after the season is **claimed as a walk-on by a D3/D4 program with an open slot**
(best leftover → strongest programs). `refill_walkons` then auto-generates ONLY the
seats still empty after that. Order in `finalize_rollover`:
`intake_signings → assign_pool_walkons (leftover → D3/D4) → refill_walkons (auto-gen rest)`.

### 4. Recruit pool sized to turnover (`world.RECRUIT_POOL = 2500`)
Was 1,000. Turnover demand is ~2,200/gender/year (D1 12 + D2 10 + D3/D4 core, ÷4
classes). 2,500 covers it with a small tail, so D1/D2 fill their cores AND walk-on
depth from real recruits, and the leftover sweep feeds D3/D4 before any auto-gen.

## Verified

- Base rosters: D1 12, D2 10, D3/D4 16 (core + walk-on splits as above).
- Rollover diagnostic: leftover juniors land in D3 as walk-ons (`pool_walkons` > 0)
  with **zero** auto-gen when the pool covers the seats; D1 fills from signings only.
- Tests updated to the per-division caps (they asserted the old fixed 8).

## Not yet verified end-to-end
A full multi-year in-app world run (to confirm D1/D2 reliably reach cap from the live
drip, and pool/junior-circuit performance at 2,500) — worth a look in-app; the harness
has hit SQLite lock/timeout on long world sims before.
