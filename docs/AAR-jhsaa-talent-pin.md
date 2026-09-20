# AAR — the talent pin: a player already in the building is never regenerated from today's tier

**Owner rule 2026-09.** "I just didn't want what happened to ever be able to
happen again mechanically."

## What happened

Between the build that played 2088 and the build that played 2089, the ceiling
of almost every returning JHSAA player moved. Same pid, same name, same style,
same hometown, a different person underneath:

| 2088 → 2089, same pid | programs |
|---|---|
| whole roster shifted up by a near-constant | 642 |
| whole roster shifted down | 500 |
| mixed | 549 |
| unchanged | 98 |

Median shift 11 points; within a program the shift was the same for every
player of a cohort (Agate's freshmen all moved 19). That is the signature of the
program's talent TIER changing, not of development: `career_ability` only ever
adds, and on a clean database the same code builds 2088 and 2089 for the same
program with zero ceiling difference.

The tier map is a git-tracked data file plus per-save override rows, re-resolved
on every roster build. The owner's working copy of `data/jhsaa/talent_bands.json`
(edits accumulated over 2084–2088) was replaced by the repo's copy when they took
a code update — the same event as the realignment map, one week earlier — and no
row in the database held what the enrolled cohorts had been generated with. The
2089 export fits the committed seed file for 1,509 of 1,791 programs; the 2088
export fits it for 997.

The editor's cutover rows (`set_program_band`, `bulk_edit_band_seed`) pin the
CURRENT answer at year 0 before an edit, so they protect enrolled cohorts against
the edit they belong to. They cannot protect against the file itself changing
under them, a table edit that removes a tier key (assigned programs fall to the
roll), `roll_talent_bands.py --reroll`, an archetype edit, or a retune of the
band constants: every one of those is a change to the RECIPE, and a player was
nothing but the recipe's output.

## The fix

`world_jhsaa_talent` — one row per (world, pid): the `talent` scalar the seat was
generated with (post-compression, the value handed to `generate_prospect`), the
ORIGIN program's ident, entry year, seat, the tier key the recipe resolved at the
time, and the archive index it was pinned at.

- **Written** by `jhsaa.record_talents` inside `world.run_jhsaa`, after each
  gender's season is archived, for every player on every roster (transfers and
  exchange students included, since they came through `_gen_seat`). `INSERT OR
  IGNORE`: first value wins, nothing here can move an existing pin.
- **Read** by `jhsaa.pinned_talents(gender, ident)` — one indexed query per
  program per build, memoised until the next record or `reset_schools()` —
  threaded into `_gen_seat` like `expo_years`. The recipe still runs in full (so
  the seat rng consumes exactly what it always did), and its answer is REPLACED
  by the pin before `generate_prospect`. New entrants have no row and draw from
  the inputs of the day, which is the only way a tier edit is meant to reach a
  roster.
- **Backfilled** once per save by `jhsaa.backfill_talent_pins`: a save with an
  archive and no pins rebuilds its newest archived season's rosters as the recipe
  produces them today — which is what that season played, nothing having moved
  since it was archived — and pins them before the next season's rosters are
  built. The owner's 2089 is therefore held as played; 2090's returning players
  are the 2089 people.
- **Cleared** by `world.reset()` with the rest of the archive.

Unpinned, nothing changes to the bit: a database with no world, or no row for a
program, builds exactly as before.

## What a pin does and does not fix

- A pinned player's CEILING is theirs for good. Current ability is derived from
  it by the career model (`_career_plan` is seeded on the seat, `career_ability`
  is monotone), so the whole trajectory is stable against tier, table, file and
  roll changes.
- A `blue_blood` toggle on an enrolled program still shifts the seat rng (the
  redraw consumes a draw inside `_ceiling`), so that one archetype edit can still
  move enrolled players' attribute SHAPE. Archetypes are durable by rule and
  rarely edited; noted, not fixed.
- Development-rate levers (`coaching`, `neglect`, `feeder`, exposure) act on
  current ability, not the ceiling, and are unchanged: a coaching tag added later
  still speeds up enrolled players, which is the stated intent of that lever.
- A change to `career_ability` itself (the formula) is a code decision and still
  reaches everyone. Persisting each season's realised ability as well would close
  that; not done — the owner asked for the tier fault to be impossible, not for
  the model to be frozen.

## What is moddable

- `world_jhsaa_talent.talent` is the player's true ceiling. Edit a row and the
  player regenerates at that ceiling from the next build — a deliberate,
  per-player, per-save adjustment that survives every file and tier change. The
  `tier` column is audit only.
- Delete a program's rows and its enrolled players re-draw from the recipe of
  the day (the pre-pin behaviour, on purpose).
- `pinned` appears as the tier on a rebuilt seat (`Prospect.jhsaa["tier"]`), with
  `generated_talent` beside it — what the recipe WOULD have given today — so a
  diff between the two is the size of the drift the pin absorbed.

## Not done, by owner decision

The 2088→2089 transition stands as played (2089 was complete before this
landed). No reconstruction, no repair of individual players. And no new
variability mechanic came in with this: the intended model is unchanged (OVR
grows or holds, POT is the ceiling, coaching moves rate, tier moves incoming
talent). Any future OVR or POT movement must be a NAMED mechanic with its own
knob — never a rebuild under a different program setting.

## Addendum (same day): the CREATION draw is pinned, the environment is not — and POT is an estimate

Owner rulings after the first pass:

1. **No ability floor and no incremental engine.** A future change to the
   development formula is a future decision; nothing is built against it now.
2. **A program toggle must not redraw an enrolled player, and must still shape
   their growth.** The archetype does two different things and they were being
   conflated: at CREATION it sets the ceiling and the attribute shape (the
   blue-blood redraw takes an extra dice draw inside `_ceiling`); in every LATER
   season it is the development environment (`coach_factor` on the yearly
   capacity). So the pin row now also records `kind` (the archetype the seat was
   drawn under) and `start` (the feeder head start it walked in with), and a
   pinned seat runs the ceiling routine under its creation archetype — the seat
   rng consumes exactly what it did at creation — while `coach_factor` keeps
   reading the archetype of the day. Untagging a blue blood leaves every
   enrolled player byte-identical and draws the next class untagged; adding
   `coaching` speeds up the enrolled players from this season on and never
   lowers anybody. (A player coached past their drawn peak still lifts the
   DISPLAYED ceiling to meet OVR — the residual CLAUDE.md already accepts.)
3. **POT is an estimate** (`jhsaa.pot_display`, `_stamp_pot_estimate`,
   `POT_MISREAD_SD` 6 / `POT_PRIOR` 1). The hidden ceiling is fixed and pinned;
   what a page shows is the staff's read of it: one misread per player, drawn
   once and seeded on the pid (never re-rolled — a fresh roll every season would
   be the instability the pin removed), scaled by `PRIOR / (PRIOR + knowledge)`
   where knowledge is the exposure odometer's realisation over the seasons
   already played — time in the building and participation, never results,
   opponents or the flight played. A freshman carries the whole misread; three
   full seasons cut it to a quarter. Never below OVR, never above the scale.
   Display only: the engine, the career model and the college hand-off all read
   the true ceiling. Every JHSAA POT column is labelled "Pot est." and the
   export carries `potential_grade` (the estimate) beside `ceiling_grade` (the
   fixed value), with the manifest saying which to analyse. `POT_ESTIMATE_ENABLED`
   is the kill switch.

Moddable: `world_jhsaa_talent.kind` / `.start` beside `.talent`; a NULL reads
as today's value (rows written before the columns existed). `POT_MISREAD_SD`
sets how wrong a program can be about a freshman, `POT_PRIOR` how fast it
learns.
