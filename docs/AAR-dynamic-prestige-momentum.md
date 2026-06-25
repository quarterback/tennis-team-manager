# AAR — Dynamic prestige (YoY momentum from over/under-performance)

**Date:** 2026-06-24
**Scope:** `overrides.get_prestige_momentum` / `set_prestige_momentum_batch`;
`ncaa.load_division` (applies momentum); `recruit_economy.program_budget` (budget
tier now follows prestige both ways); `world._update_prestige_momentum` +
`_finalize_year` hook; `seasonmode.ncaa_participants` / `ncaa_semifinalists`;
`tests/test_prestige_momentum.py`.

## Old vs new

**Old:** `program.prestige` was a **static** trait — conference prior + per-school
bump — recomputed identically every load. A program's standing never changed no
matter how it performed year to year.

**New:** prestige **drifts year over year** by how a program *over- or
under-performs its own expectation*. A low-major that keeps beating its prestige
climbs (and recruits up a budget tier); a blue-blood that slides falls. The base
(conference) prestige is still the **starting point** each program reverts toward —
momentum is a signed delta on top of it.

## Owner's choices (locked)
- **Signal:** overperformance vs expectation (self-correcting), NOT raw results.
- **Aggressiveness:** aggressive — multi-tier swings allowed (`PRESTIGE_MOM_CAP =
  0.20`, ≈ two budget tiers).
- **Granularity:** per **(school, gender)** — men's and women's evolve separately.

## How it works
At each world rollover (`world._finalize_year`, before the next class is recruited),
for every program in every active universe:
- `result` = end-of-season **Power-Index percentile** in its division + a small
  pedigree bonus (made the NCAA field +0.03 / Final Four +0.06 / national title
  +0.10, + conference title +0.02, capped at +0.10).
- `expect` = the program's **current prestige percentile** in its division.
- `m ← clamp(DECAY·m + GAIN·(result − expect), −CAP, +CAP)` with
  `GAIN = 0.10`, `DECAY = 0.85`, `CAP = 0.20`.

`load_division` adds `m` to the base prestige, clamped to the division band. The
momentum is **persisted** (reuses the `roster_overrides` table, `kind='prestige_dyn'`,
key `school|gender`) so it compounds season to season and survives restarts; a new
league (`world.reset` → `overrides.clear_all`) wipes it.

**Budget plumbing change:** `program_budget` now keys the D1 band on
`_prestige_tier(prestige)` **directly** instead of `max(conf_tier, prestige_tier)`.
Verified the two agree at baseline for 396/398 D1 programs (the 2 exceptions —
strong D2-promoted schools — already funded up via the old `max`, so no change
there). Dropping the `max` is what lets a *falling* program's budget tier drop
below its conference, which the owner wanted ("same for bad teams").

## Why this shape
- **Self-correcting:** as a program's prestige rises, its expectation bar rises, so
  it only keeps climbing if it keeps overperforming the *new* standard — no runaway.
- **Strength follows, not jumps:** momentum changes *recruiting* (budget tier +
  appeal), not on-court latent strength (which still tracks the conference prior).
  A rising program gets better recruits → better rosters over years — organic, not
  an instant rating bump.
- **Decay handles flukes:** a one-off Cinderella nudges up ~+0.08 but regresses next
  year unless it sustains; sustained excellence compounds to the cap over ~3–5 years.

## Verified
- Application: +0.18 momentum on Middle Tennessee → prestige 0.56→0.74, tier
  low→major, budget 6.0→12.5; −0.18 on Stanford → 0.93→0.75, top→major, 24.3→13.4.
  Both multi-tier, both directions. Clears cleanly to baseline.
- Computation on a real completed D1 season: biggest climbers are low/mid-major
  overachievers (East Texas A&M / Southland +0.78, Liberty / CUSA +0.67); biggest
  sliders are underachieving higher-prestige programs (San Diego, WashU, Villanova).
- 47 economy/season/world tests + 2 new momentum tests pass; world rollover tests
  green (the new hook runs inside `_finalize_year` without breaking determinism —
  momentum derives from results, which are deterministic apart from injuries).

## Gotchas for the next agent
- Prestige is **no longer static** — `load_division` returns momentum-adjusted
  prestige whenever the `prestige_dyn` store is non-empty. Tests that assert a
  specific prestige must clear it (the new tests do).
- Momentum is keyed `school|gender`; `_update_prestige_momentum` writes the whole
  map in one batch each rollover. Programs in no active universe keep their prior
  value (carried forward), they don't decay to zero.
- `CAP/GAIN/DECAY` in `world.py` are the tuning knobs. Raising `CAP` widens the
  possible swing; lowering `DECAY` speeds mean-reversion.
