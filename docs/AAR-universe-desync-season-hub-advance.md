# AAR — the Season Hub's advance desynced the universes (women's rankings looked "wrong")

**Date:** 2026-07-29
**Status:** FIXED (root cause reproduced on a real world; prevention + repair below).
**Scope:** `web.server.season_advance` (the bug), `seasonmode.season_progress` (new),
`world.universe_progress` / `universes_in_sync` / `resync_universes` (new),
`/world/resync` + the World-hub banner, `scripts/resync_universes.py`.

## Symptom

Owner reported the rankings page as wrong: on **D1 Women** "it's not counting all
womens conference games and the records seems far fewer than how many matches men
play." Both boards said **Week 10 · Regular season**, both showed 75 programs over
32 conferences, and yet:

| | top-team RECORD | top-team CONF REC |
|---|---|---|
| D1 Men | 25-2, 25-4, 25-0 … | 14-1, 14-3, 15-0 |
| D1 Women | 15-2, 15-2, 16-2 … | 2-1, 2-1, 2-1 |

## What was NOT wrong

Everything the rankings page computes was correct **for the duals that had actually
been played**:

* `web.state.ranking_rows` → RECORD from `sm.power_index` (the REG + ITA ranking
  corpus), CONF REC from `sm.standings` (`round='REG' AND is_conf`). Both count
  every qualifying dual; neither filters by gender.
* `sm._gen_regular_schedule` is gender-agnostic — it takes only `div` and the seed.
  D1 men and D1 women have **identical** conference structures (379 programs, the
  same 32 conferences, the same sizes), so the two schedules come out byte-identical:
  25 duals/team, 11–17 of them conference, spanning 11 weeks.
* Advancing a fresh world 10 weeks with both genders active produces **identical**
  dual counts per gender (verified: 1623 final REG duals, 48 ITAK, 15 ITAI, both).

Also worth knowing, because it looks like a bug and isn't: **conference play doesn't
start until schedule week 4–5.** Non-conference is front-loaded (`place()` gates each
team's conference duals behind *its own* last non-conf week). With D1's 6 ITA lead
weeks, a universe at world week 10 is only ~4 regular weeks in and has played almost
nothing but non-conference. **The women's board was the CORRECT one for week 10. The
men's board was the anomaly** — a full 25-dual season, conference slate and all,
already in the books.

## Root cause — two advance buttons, one clock

`world.advance_week` is the game clock: it steps **every** active universe together,
runs the cross-division slate, drips the recruiting class, and increments the world
week. The header's "Advance week" uses it.

The **Season Hub** had its own button (`season.html` → `POST /season/advance`), and
it did this:

```python
sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
sm.advance(sid)          # ← one universe, on its own
```

Every click stepped only the universe the page happened to be showing. The world
week never moved, and no other universe moved. Click it enough times on D1 Men —
which is the hub's default `u` — and the men's universe runs its whole season while
the women's (and D2/D3/D4, and the world clock) stay where they were. Nothing errors;
both boards keep rendering honestly; they're just **from different weeks**, and the
header prints one shared "Week 10" over both.

Collateral damage from the same path:

* **The fall portal gets skipped.** `sm.advance` on a `fall_portal` season passes it
  straight through to `regular` — that pass-through is only correct standalone. Under
  a world, the portal is a HOLD the world driver releases.
* **No recruiting drip, no cross-division slate, no `prime()`** — those live in
  `advance_week`, so a solo-advanced universe simulates weeks on stale rosters and
  signs nobody.

## The fix

1. **Prevention — one clock.** `/season/advance` now drives `advance_week()` (via a
   shared `_advance_world()` helper, so the awards hold is identical to
   `/world/advance`). With no world at all (standalone season / tests) there is no
   other universe to desync from, so the single season advances as before.
2. **Detection.** `sm.season_progress(sid)` returns an orderable
   `(phase rank, regular week, bracket round)`; `world.universes_in_sync()` is true
   when every active universe compares equal. The World hub shows a banner when they
   don't.
3. **Repair.** `world.resync_universes()` steps the laggards until they stand level
   with the furthest-along universe — the world clock is untouched, because the
   leader already consumed those weeks. A universe holding at the `fall_portal`
   barrier is reported, never forced (only the world driver may release it).
   Reachable from the banner (`POST /world/resync`) or
   `python3 scripts/resync_universes.py --fix`.

## Rule

**One world, one clock.** `world.advance_week` is the ONLY thing that may move a
universe forward in a save that has a world. If you add a surface that advances a
season, route it through `advance_week` — a per-universe `sm.advance` outside the
world driver silently forks the save into universes at different weeks, and every
cross-universe surface (rankings, bracket projection, the portal, the polls) then
compares fields that played a different number of duals. `sm.advance` stays direct
only for the standalone/no-world path and the calibration scripts.
