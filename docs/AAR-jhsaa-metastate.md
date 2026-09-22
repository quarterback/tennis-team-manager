# AAR — the Metastate: a second qualifying layer in front of the Parastate

Owner rule 2026-09. `app/jhsaa.py` (`METASTATE_GROUPS`, `run_state_parastate(meta=)`),
`app/world.py` (the archive key and the finish walk), `app/web/state.py` (the stage
and the chip), `tests/test_jhsaa_metastate.py`.

## What was wrong

The Parastate put the `2 × bids` lowest seeds together and paired them high-low. In
a 48-team class that is seeds 17-48, so the field's seeds 17-24 drew seeds 41-48 —
and **won 279 of 288 of those duals over six seasons**. A round the top half cannot
lose is not a qualifying round; it is a formality that costs the weakest eight teams
their only dual of the tournament.

## The shape

The metas take the bottom `bids` seeds and pair them among **themselves** first. The
`bids / 2` winners then meet the next `bids / 2` seeds in the Parastate, and the
survivors join the byes in the State draw.

| Class | Bids | Metastate | Parastate | State draw |
|---|---:|---|---|---|
| 9A, 8A, Group 1 | 16 | seeds 33-48, 8 duals | 25-32 + 8 winners | 24 byes + 8 |
| 7A-2A, Group 2 | 8 | seeds 33-40, 4 duals | 29-32 + 4 winners | 28 byes + 4 |
| 1A, Group 3 | 8 | *none* | 17-32, 8 duals | 16 byes + 8 |

**The arithmetic closes on the road field at every allocation**: the draw is
`(road − bids / 2) + bids / 2 = road`, so the State bracket is the shape that class
already played and no bracket geometry changed. Pinned as a pure fold over the
tables, so it needs no season and cannot rot behind a fixture.

Nobody who makes the field today is shut out and the same number of teams reach the
draw. What changed is who plays whom: the weakest seeds play each other, and seeds
17-24 (a 48) or 25-28 (a 40) bye to the State draw.

## Decisions

- **1A and Group 3 are OUT** (owner). They crown from 32 off a 24-team road and keep
  the single-Parastate progression, their at-larges entering the Parastate directly.
  `METASTATE_GROUPS` is a TUPLE and not a derivation off the road size — "road == 32"
  happens to separate the two today and would silently enrol 1A the day its road
  moved. Membership is the whole change, the `WIDE_GROUPS` idiom.
- **The name** is Metastate, shortened **metas** in prose as the Epiregionals are
  epis and the Super Regionals supers, and SINGULAR because it joins the
  Parastate's family rather than the road's plural rungs: Parastate, Metastate.
  ‼️ It shipped first as **Maxiregionals** and the owner replaced it — a review had
  flagged that name as the fourth "-regional" round beside Regionals, Super
  Regionals and Epiregionals, which is the league-naming rule's ambiguity one level
  down; the answer was not a shortening convention but a name from the right
  family. The rename was safe only because no season had been played on it: the
  phase string is archived in `world_jhsaa_dual.phase`, so renaming it after a save
  had run would have needed a relabel on read, never a migration.
- **A meta exit is NOT a State appearance** (owner). This is the one substantive
  break with the Parastate, where every entrant *is* a State participant because the
  Parastate is a round OF the State event.

## ‼️ The finish is bought by the PHASE, and nothing else

`world.jhsaa_state_result` reports `made_state` off membership of the draw's
`field`. So the only way to keep a meta loser out of the State record is to keep it
out of that list: the metas are their own **phase** (`metastate`, in `POSTSEASON`
directly in front of `state`) with their own archive key, and `run_state_parastate`
returns a `field` of everyone who started at the Parastate or later.

Membership of `POSTSEASON` then carries the postseason dual format, the lineup
freeze, the class's own calendar lane and exclusion from TOSS, exactly as it does for
every other rung — the `special_challenger` idiom.

The finish walk tries the metas **before the Specials**, because a Specials WINNER is
a State qualifier and can be seeded into the metas; tried later, its year would read
as ending a round earlier than it did. A meta WINNER is in the draw's field and never
reaches the walk at all.

**Consequence, accepted:** a program's career state-trip total folds seasons counted
two ways — an honest record of a rule that changed, the way an NCAA expansion is.
Seasons archived before the metas read unchanged (`.get` on the key, never a
migration).

## ‼️ Two degradation faults, found by a small world

Both were invisible at full size and would have shipped.

1. **The metas ate the bye lines.** Sized `min(meta, len(field))`, a short field (a
   fixture's two districts a class, a save whose road ran dry) put its WHOLE field
   into the metas: every team played one, half were out before the Parastate, and the
   survivors all byed into a draw the association never plays. The round now convenes
   only when the field seats the byes AND the meta block (`len(field) − meta >= byes`).
2. **And skipping them broke the Parastate.** `byes` is passed as `road − bids / 2`,
   which is only right *because* the metas are about to halve the at-large block. Skip
   them and that bye line is too high by exactly the half they would have removed, so
   the Parastate ran out of entrants and quietly stopped convening too — the round
   vanished from a short world's archive and its bracket page stopped describing a
   Parastate at all. The allocation is handed back (`byes − meta // 2`) whenever the
   metas do not convene, which makes a short field **byte-identical** to the
   pre-change call. Pinned.

The lesson is the section's own, running the other way: usually the path a real save
takes every season is the one a small world never reaches. Here a small world reaches
a path a real save never does, and a guard written only for the full-size shape let
it through.

## ‼️ The divisibility guard forbids the fault, not the shapes played

A first draft asserted `bids % 4 == 0` on a muddled reading of the halving. The
arithmetic needs `bids` **even** and nothing more: an ODD allocation is what stops
`bids / 2` being a whole number of seeds and sends both rounds down the degraded
odd-field path. 16 and 8 are even and so is the 4 Group 3 ran through 2079, so `% 4`
would have blocked a shape the association has actually played — the
`check_rename_keys` lesson, a guard written from the incident rather than the fault.

## Rendering

The metas are a **stage**, the top one on the bracket page's reverse-chronological
fold, above the Specials. Never a tree column: eight duals feeding a separate
Parastate field is not a halving and `_bracket_canvas` links columns on exactly that
halving — the Epiregional's reason and the JV qualifying round's lesson. Their chip
is **META** and not STATE, because a STATE chip would say the opposite of what the
ledger says. The Match Center names the phase rather than falling through to
"Invitational".

‼️ The render is covered by a HAND-ARCHIVED season, because the real-season fixture is
a small world where the metas correctly do not convene — a round nothing renders is
indistinguishable from a round that was not played.

## ‼️ A new phase is four maps, and three of them fail quietly

Adding the phase and its finish branch is the easy half. Three separate maps have to
learn the phase, none of them near the branch, and **not one of them raises when it
does not**:

| Map | What it does | What a missing entry looks like |
|---|---|---|
| `jhsaa_postseason_result` | the finish walk | — (this is the branch) |
| `world._season_row` | assembles the stage dict the walk reads | empty `state_finish` on the ledger row, the program history and the best-season fold |
| `jhsaa_school.html`'s heading map | the schedule's phase band | a blank band over a block of duals |
| `state._SEEDS` | the opponent seed per stage | the seed silently drops off every dual of that stage |

The finish branch shipped unreachable: `_season_row` builds its stage dict one key per
stage and had no `metastate` key, so the archive held the stage and every metas loser
read back with nothing. **A key the walk never receives is a branch that cannot fire**
— and the unit test could not see it, because it hand-built the stage dict the
production path was failing to build. The replacement test goes through `_season_row`.

The schedule maps were worse than a metastate problem: the **Epiregional**, the
**Semi-Conference** and the **Special Challengers** had never been added to the heading
map either, each one a whole postseason stage rendering a blank band. Three phases
drifted the same way before anyone noticed, so the agreement between `_KIND`, the
heading map and `_SEEDS` is now swept rather than trusted
(`test_every_schedule_kind_has_a_heading_and_a_seed_map_entry`). A **SHOWCASE** is the
one kind with no `_SEEDS` entry, and legitimately: it is not a draw.

## Closed: the coefficient now prices it

It scored ZERO at first, and that was left open deliberately rather than invented: a
metastate exit is not in the State bracket's field and not a road unit anybody wins,
so a team that qualified and lost there rated identically to a team that missed the
postseason — roughly 8 programs a class a season in a 48, 4 in a 40.

The owner set the price in the same pass that re-graded the whole schedule (2026-09):
a **metastate win is 1** on the road side, and a **Parastate exit is 1** rather than
the 0 it had always been, so the qualifying ladder reads as one progression into the
draw — Metastate 1, Parastate 1, first round 2, Octofinals 8. The metastate needed
its archive key adding to `_ROAD_KEYS` as well as a price: a rung the walk never
visits is unpriced however many numbers the table holds. See
`docs/AAR-jhsaa-program-coefficient.md`.

## Not done, by design

- **No title-board column.** A meta is not a unit anybody wins, so there is no title
  to count; `jhsaa_title_stages` is untouched.
- **No unit names or statewide numbering.** The Specials and the Challenges number
  their duals because a program's ledger names the unit it played in; a meta dual is
  a qualifying pairing inside one classification's own field.
