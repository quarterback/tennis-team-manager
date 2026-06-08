# AAR — OOM Mitigation: Recruit Cadre + Per-Universe World Seeding

## Problem

The deployed app (fly.io, ~1 GB machine) was OOM-killing its gunicorn worker on
first use — `Out of memory: Killed process (gunicorn) ... anon-rss:868780kB`,
with repeated `WORKER TIMEOUT` (>120 s). The worker booted, took a slow heavy
request, ballooned to ~868 MB, and was SIGKILLed in a loop.

## Diagnosis (measured, not guessed)

Profiled peak RSS of each path in isolation and cumulatively:

| operation | peak RSS |
|---|---|
| bootstrap | 20 MB |
| name pools load | 24 MB |
| all 6 universes' rosters | 171 MB |
| recruit board (2 genders) | 70 MB |
| world national class (2 genders) | 68 MB |
| season create + full advance | 95 MB |
| **`world.start_new()` (onboarding)** | **323 MB** |

The first-load/onboarding spike was `start_new` → `get_or_create`, which built
**all six universes' rich rosters (~17k Prospects, each with current+potential
49-attribute dicts) in one dict before saving** (~323 MB transient). On fly's
slower CPU this also blew the 120 s timeout, and during that window health-check
and browser requests hit other gthreads, each independently materialising the
~170 MB roster cache via `prime()` (no lock) — multiplying toward the 868 MB OOM.

Note: the recruit pool size was *not* the dominant cost (reducing it alone didn't
move the peak) — the rosters were.

## Fixes

1. **Per-universe world seeding** (`world.get_or_create`): build → persist → free
   one universe at a time instead of all six at once. Peak `start_new` **323 MB →
   85 MB** (−74%), same ~10 s, world identical (6 universes, 17,376 players
   reload from DB).
2. **Prime lock** (`world.prime`): double-checked `threading.Lock` so only one
   gthread builds the ~170 MB shared roster cache; concurrent requests wait and
   reuse it instead of each building their own copy.
3. **Recruit cadre** (`RECRUIT_POOL` 2600→1000, `RECRUIT_BOARD_N` 2000→1000):
   a bounded recruiting class rather than a full-blast generation, per the design
   that teams sign from a ~1000 cadre, unsigned become walk-ons, and remaining
   roster seats are backfilled with generated walk-ons.

## Result

Realistic warm worker now: `start_new` 85 MB → `prime` (all universes cached)
271 MB resident → dashboard + world hub 281 MB. Comfortably under 1 GB, and the
concurrency multiplier is gone. **137 tests green.**

## Follow-ups

Done in a second pass on this branch:

- **Year-rollover memory** — `_finalize_year` held the primed cache (~170 MB)
  *and* a second full-world copy through the heavy rollover. Now frees the primed
  cache right after `developed_rosters` + `season_player_str` (the rollover works
  on the independent copy), roughly halving the rollover peak.
- **Onboarding nationality bands** — new `app/worldconfig.py` (leaf settings
  store) persists a chosen band; onboarding offers Realistic / Worldwide /
  USA-heavy / European / Americas / Asia-Pacific, threaded through rosters,
  coaches, walk-ons and the recruit international pool. Verified: us_majority →
  US-dominant, european → FR/GB/DE, asian_pro → JP/KR/TW.
- **Unsigned-recruit → walk-on**: moot at the current sizing — the 1000-cadre is
  smaller than total openings, so every recruit signs and walk-ons backfill the
  rest (the intended behaviour already).

- **Universe selection (memory)** — onboarding now lets you pick which divisions
  (D1/D2/D3) and genders (men/women) to **run in detail**. All six are still
  seeded so every player exists, but only the chosen universes are loaded,
  primed and simulated; the rest stay dormant (and are carried forward unchanged
  at year rollover via a cheap SQL copy). Picking D1-men only drops the primed
  resident cache from ~271 MB (all six) to ~30 MB of rosters — the biggest
  remaining lever, exactly as suggested. Defaults to all six, so nothing changes
  unless you narrow it. Threaded through `world.py` (`_active_unis`, gated
  prime/advance/finalize/cross/recruiting) + `worldconfig` + onboarding.

Still open:

- **Preseason gate** — a thin page that lists the actions about to happen
  (recruiting drip, schedule, auto-shuffle lineups) and gates "advance" so you
  can optionally edit first; skip anything and the AI does it, as it already does
  for every other program. Schedule/lineup edits ride the existing editor.
