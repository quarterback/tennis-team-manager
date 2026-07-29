# AAR — two advance buttons desynced the universes (women's rankings looked "wrong")

**Date:** 2026-07-29
**Status:** FIXED (root cause reproduced on a real world; the duplicate control is
gone, and there is a repair path for saves that already drifted).
**Scope:** `web.server.season_advance` (DELETED — the bug), `web.server.world_advance`
(now the only advance route), `season.html` / `base.html` (one button),
`seasonmode.season_progress` (new), `world.universe_progress` /
`universes_in_sync` / `resync_universes` (new), `/world/resync` + the World-hub
banner, `scripts/resync_universes.py`, `tests/test_universe_sync.py`.

## Symptom

Owner reported the rankings page as wrong: on **D1 Women** "it's not counting all
womens conference games and the records seems far fewer than how many matches men
play." Both boards said **Week 10 · Regular season**, both showed 75 programs over
32 conferences, and yet:

| | top-team RECORD | top-team CONF REC |
|---|---|---|
| D1 Men | 25-2, 25-4, 25-0 … | 14-1, 14-3, 15-0 |
| D1 Women | 15-2, 15-2, 16-2 … | 2-1, 2-1, 2-1 |

Owner's follow-up is the important half of the diagnosis: *"they're doing this
constantly."* Not a one-off — a standing trap in the UI.

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

## Root cause — TWO advance buttons, one clock

`world.advance_week` is the game clock: it steps **every** active universe together,
runs the cross-division slate, drips the recruiting class, and increments the world
week.

The app shipped **two** advance controls, and on `/season` they sat about twenty
pixels apart in the same toolbar row:

1. the header's "Advance week" (`POST /world/advance`) — the correct one, on every
   page;
2. the Season Hub's own "Advance week →" (`POST /season/advance`), which did:

```python
sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
sm.advance(sid)          # ← one universe, on its own
```

Two identical-looking buttons, one of them wrong, and no way to tell them apart.
That is why it kept happening: every click of the in-page one stepped only the
universe the page was showing. The world week never moved, and no other universe
moved. Click it enough times on D1 Men — the hub's default `u` — and the men's
universe runs its whole season while the women's (and D2/D3/D4, and the world clock)
stay put. Nothing errors; both boards keep rendering honestly; they're just **from
different weeks**, and the header prints one shared "Week 10" over both.

Reproduced exactly on a real world: six `sm.advance` calls on D1 men alone turned a
synced week-9 world into men `24-5 / 12-3` against women `13-1 / 0-0`.

Collateral damage from the same path:

* **The fall portal gets skipped.** `sm.advance` on a `fall_portal` season passes it
  straight through to `regular` — that pass-through is only correct standalone. Under
  a world, the portal is a HOLD the world driver releases.
* **No recruiting drip, no cross-division slate, no `prime()`** — those live in
  `advance_week`, so a solo-advanced universe simulates weeks on stale rosters and
  signs nobody.

## The fix

1. **One route.** `/season/advance` is **deleted**. `world_advance` is the only POST
   route in the app that moves a college season forward. Its no-world branch (a
   standalone season in dev/tests) advances the selected universe, because with no
   world there is nothing to fall out of step with — and nothing to build.
2. **One button.** The Season Hub's duplicate is gone; the header's button is the
   single advance control. It lost nothing: `_game_context` now returns the world
   `stage` plus an `action` label, so the header reads "Run NIT Kickoff" /
   "Run conf tournaments" / "Advance NCAA round" / "Finalize season" the way the
   in-page button used to, and links to `/fall-portal` while the world holds there
   (posting an advance at the barrier is a no-op — that button was dead).
3. **Detection.** `sm.season_progress(sid)` returns an orderable
   `(phase rank, regular week, bracket round)`; `world.universes_in_sync()` is true
   when every active universe compares equal. The World hub shows a banner when they
   don't.
4. **Repair.** `world.resync_universes()` steps the laggards until they stand level
   with the furthest-along universe — the world clock is untouched, because the
   leader already consumed those weeks. A universe holding at the `fall_portal`
   barrier is reported, never forced (only the world driver may release it).
   Reachable from the banner (`POST /world/resync`) or
   `python3 scripts/resync_universes.py --fix`. Verified on the reproduced world:
   6 steps, leader untouched, women's board back to `25-2 / 13-1`.
5. **Regression guards** (`tests/test_universe_sync.py`): exactly one non-GTT POST
   route with "advance" in its rule, and `sm.advance(` appears exactly once in the
   whole `app/web` tree (world_advance's standalone branch).

## Rule

**One world, one clock — and one button.** `world.advance_week` is the ONLY thing
that may move a universe forward in a save that has a world, and `/world/advance` is
the only route that calls it. Do not add a second advance surface, however scoped or
convenient it looks: a per-universe `sm.advance` outside the world driver silently
forks the save into universes at different weeks, and every cross-universe surface
(rankings, bracket projection, the portal, the polls) then compares fields that
played a different number of duals. `sm.advance` stays direct only for the
standalone/no-world path and the calibration scripts.

The deeper lesson is the UI one: **a wrong action that looks identical to the right
one will be taken, repeatedly.** Deleting the duplicate was the fix; making it call
the right thing would only have hidden it.
