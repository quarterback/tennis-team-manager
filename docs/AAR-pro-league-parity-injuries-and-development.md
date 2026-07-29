# AAR — the pro league had no injuries and no development (and why that kept getting waved off)

**Date:** 2026-07-29
**Status:** FIXED for both. Coaches + franchise prestige remain open (see "What's left").
**Scope:** `injuries.table_schema` / `unavailable` / `recover` / `roll_new` (new — the
shared store), `seasonmode._unavailable` / `_recover_team` / `_roll_new_injuries` (now
delegations), `gtt_seasonmode` (`gtt_injuries` table, `_inj_scope`, `_lineup` filter,
`_play_and_store` roll, `PRO_GROWTH` + the develop branch), `tests/test_injuries.py`,
`tests/test_gtt.py`.

## Symptom

Owner: *"THE PRO GAME NEEDS TO WORK LIKE THE COLLEGE GAMES' DURABILITY WHY IS IT
SEPARATE IT'LL ALWAYS BE BROKEN"*, then the part that matters most:

> *"the pro league lacks everything because past agents have told me it wasn't
> necessary and i've asked for this before and gotten not very far"*

## What was actually true

Measured, not assumed — grep across `seasonmode`/`world`/`season` vs `gtt_seasonmode`:

| System | College | Pro |
|---|---|---|
| Injuries / durability | yes | **zero references** |
| Player development | yes | **zero calls to `develop()`** |
| Aging / decline / retirement | — | yes (pro-only) |
| Results-based STR convergence | yes | yes |
| Doubles | yes | yes |
| Honors / MVP / Hall of Fame | yes | yes |
| Transactions / waiver wire | — | yes (pro-only) |
| Per-dual chaos form | — | yes (pro-only) |
| Coaches | 77 refs | **zero** |
| Franchise prestige | 69 refs | **zero** |

So "lacks everything" was close but not exact: the pro league has real systems college
doesn't (waiver wire, chaos form, aging). What it lacked were the two that make players
**change over time** — and without those, nothing else you add to it can feel alive.

## Root cause 1 — injuries: the rules lived in the wrong module

The dice were already shared in `app/injuries.py`. The **store and the rules** —
availability, the recover/grace clock, rolling on whoever actually competed — were
private helpers (`_unavailable`, `_recover_team`, `_roll_new_injuries`) inside
`seasonmode`. There was nothing for the pro league to call, so it called nothing.

This is not a design split anyone chose; it's a module boundary drawn in the wrong
place. It stayed invisible because **nothing errors when injuries simply never
happen** — durability quietly stopped meaning anything the moment a player graduated.

## Root cause 2 — development: a calibration trap that makes the fix look pointless

`gtt_seasonmode` never called `develop()`. Its only per-year change was age+1, retire,
and `decline()` once past `PEAK_AGE` (28). A pro drafted at `ENTRY_AGE` (22) was
**frozen at their college exit level until 29, then only got worse.** Every graduate
carries a ceiling out of college that was never approached again.

The important part is why this is easy to wave off. Measuring the obvious growth curve
on a **raw generated prospect** looks fine — big remaining gap, visible movement. But
the actual pro population is **graduates**, who have already spent four years of growth
and have a much smaller gap. On graduates, the same curve is worth:

```
scale 1.0/yr, ages 22→28, measured on 5 real graduates:
  55→56   52→58   41→42   45→49   39→41      (+1..+4 OVR across a WHOLE prime)
```

+1 OVR over six years is indistinguishable from nothing. **Anyone who calibrated on raw
prospects and then sanity-checked against the real league would conclude that pro
development "isn't necessary" — the measurement agrees with them.** That is the most
likely shape of the answers the owner got before, and it is a measurement error, not a
judgement call.

With `PRO_GROWTH = 2.0` on the same graduates: `+2..+10`, the spread coming from each
player's own remaining gap and interest rate — some break out, some plateau.

## The fix

1. **One injury implementation.** The store moved into `app.injuries` as
   `unavailable` / `recover` / `roll_new`, taking the caller's table and key columns.
   College passes `injuries` keyed `(season_id, school)` — behaviour unchanged, its
   helpers are now three-line delegations. The pros pass `gtt_injuries` keyed
   `(_inj_scope(league, year), franchise id)`. Separate rows, identical rules.
   `gtt._lineup` filters the injured so a reserve is pulled up exactly as college depth
   works; a club too thin to field a healthy lineup plays its hurt players rather than
   forfeiting, because the sim needs a full card.
2. **The new table is cleared with its league.** `gtt_injuries` is keyed by an
   opaque `_inj_scope` int rather than `league_id`, so it needs explicit cleanup:
   `delete_league` drops that league's whole scope range and `reset()` wipes the
   table. Missing this is the same id-reuse trap this repo already hit with
   `world_cups` — SQLite hands the rowid back to the next league, and a new save
   reuses the default seed, so pids AND scopes repeat exactly; stale season-ending
   rows would have benched players in a league that never injured them.
3. **Pros develop**, tapering linearly to zero at `PEAK_AGE` — the mirror of decline's
   scale growing past it — scaled by the tunable `PRO_GROWTH`.

## Verification

- A full simulated pro season now produces injuries with the same shape as college
  (out 1–6 duals, or season-ending); an injured pro is dropped from the lineup and a
  reserve promoted.
- College injury behaviour unchanged: all 21 pre-existing injury tests pass against the
  shared store.
- Pro growth is visible in OVR, never exceeds the ceiling, and is fully spent at the
  peak.
- Deleting a league and resetting the tour both leave `gtt_injuries` empty.

## Rule

**Absence is the hardest bug to see.** Nothing errors, no test fails, and every number
on screen looks reasonable — a league where nobody is ever hurt and nobody ever improves
renders perfectly. When a subsystem is reported as "lacking", diff it against its
sibling by grep before forming an opinion; the answer is a table, not a judgement.

**A new persistent table is not done until its teardown is.** Every id this repo
keys on is recycled by SQLite after a reset, and a new save reuses the default seed —
so "the ids will differ" is never true here. Add the DELETE to both the per-entity
delete and the whole-tour reset in the same change that adds the CREATE.

**And calibrate on the real population.** A growth/decay curve tuned on freshly
generated prospects will be silently near-zero on graduates, who have already spent most
of their headroom. If a change measures as "no effect", check what population you
measured on before concluding it isn't needed.

## What's left

- **Coaches — the real remaining hole.** Franchises have none at all, so
  `coaches.development_multiplier` has nothing to attach to and every pro develops at
  exactly the same rate. This is the piece that makes the development above mean
  something per-club.
- **Franchise prestige** — smaller; matters if free agents should prefer winners over
  the highest bidder.
