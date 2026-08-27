# AAR — the broken State brackets: phantom byes, and the State Specials round

**Date:** 2026-08
**Status:** Landed. Owner rules 2026-08.
**Report:** "the 9A bracket is broken for some reason" → "it's all the brackets!" —
teams advancing round after round without playing, cards overlapping, on every
classification's State page.

## What the owner saw

On the 9A boys' State bracket, four programs (Jesuit, Mar Vista, Crater View,
Marshfield Prep…) carried BYE after BYE through four straight rounds, their cards
drawn on top of the real quarterfinal column. Every classification on the 32-team
field table showed some version of it.

## What was actually wrong — two faults stacked on a third

### Fault 1: `run_state` sent a 32-team field down the 40's qualifying path

The expanded-field branch was gated on

```python
if len(field) > 2 * c and size - len(field) != c:
```

— "expand unless the padding byes are exactly the champions." That condition is
TRUE of a 32-team field (a bracket exactly full, zero byes) and of every
under-filled field, so five classifications were shipped through a Qualifiers
Round that exists only because a 40 cannot fit one bracket. The owner's design
was always simpler (owner, 2026-08): **"32 can happen with no byes… 32-16-8-4-2
works fine, with the 8 zonal champions as the top 8 seeds."** There is no reason
for three "Octofinals" columns when the field is a power of two — you just don't
have byes.

The gate is now the rule stated directly: expand only when the padding byes would
**outnumber** the champions (`size - len(field) > c`), i.e. only when they could
not all be the champions' own privilege. 24 → 8 byes, plain draw. 32 → 0 byes,
plain draw. 40 → 24 byes in a 64, and only then does qualifying earn its place.

### Fault 2: the road delivered 28 teams to a 32-team table

The qualifying expansion did not invent the byes out of nothing: the recovery
ladder had delivered only **20 of its 24 earned berths**, so `run_state` received
28 teams and padded. The `_recovery` machinery projects the correct arithmetic
(Semi-State 12 + Divisionals 6 + Conference 6 + 8 Zonal champions = 32) and the
live path fails to match its own projection — a candidate pool built smaller than
the format assumed, an eligibility walk skipping a loser tier, or a parity trim
turning one missing body into one missing berth. The existing
`recovery filled N of M` warning had been logging exactly this and nobody was
downstream of it.

### Fault 3 (background): 32 was never a designed shape

`STATE_FIELD` moved 9A/8A/7A — and later 6A/5A/Group 1/Group 2 — from 40 to 32 to
clear the Semi-Conference's 76-sponsor floor after the Great Basin split and the
Heritage Valley migration thinned those classes. The table moved; nobody checked
that the road OR the draw knew how to produce or host a 32. The docs' own line —
"a 40 IS a 24 with a Qualifiers Round in front of it" — silently had no third
case.

## The fix, in three parts

1. **The draw** (`run_state`): a field that fits one bracket plays one bracket.
   Byes, when a field is short, go to the top seeds in the FIRST round only —
   never chained. Verified over every field size 17-40, rendered through the real
   bracket pipeline (`tests/test_jhsaa_state_draw_shapes.py`): zero bye chains,
   every column halves into the next, round names correct.

2. **The render** (`state._jh_split_state`): a team that byed the opening Qualies
   round appears only in the second, so reading `pre[0]` alone filed it with the
   double-bye champions — the main draw's field over-counted and rounds were
   named off a team count that never existed ("Round of 20", Octofinals twice).
   The qualifying field is now read off EVERY preliminary round.

3. **THE STATE SPECIALS** (owner design, 2026-08) — the field-integrity rule:

   ```text
   missing = STATE_FIELD[group] - qualified
   if missing > 0:
       take 2 × missing eligible eliminated teams
       play `missing` State Specials duals
       winners take the missing berths
   ```

   Field-size agnostic by construction — it knows nothing about 24, 32 or 40:
   28-of-32 is 8 playing for 4; 35-of-40 is 10 for 5; a future 64 reconciles the
   same way. Selection walks the postseason BACKWARD by latest elimination
   (Conference losers first, then Semi-Conference, and so on down to Areas), with
   **ATR ordering within a tier, never across one** — the recovery ladder's own
   body-ranking rule, because this decides who gets one final chance to play for
   a berth, not a seed. Its pool is deliberately BROADER than the Conference's
   (every non-qualified postseason loser), so it cannot inherit the same
   shortage.

   It is **not another rung of the ordinary ladder**. The Conference is supposed
   to fill the field; in a healthy class the arithmetic cannot come up short, so
   the Specials convening AT ALL is logged loudly every time. Firing once in
   several years — membership, parity and qualification lining up badly — is the
   round doing its job; firing regularly means an upstream rung is losing berths,
   and THAT is what needs diagnosing. If even its pool runs dry (a class with
   fewer postseason teams than the field wants — a broken fixture or a tiny test
   world), the best `2·missing − pool` enter directly with a warning (the
   `sc_head` idiom): a short State field is the one outcome worse than an
   unearned entry.

   New phase `"state_special"` (a phase is the archive's identity for an event),
   archived per group beside the recovery rounds, wired through every reader:
   finish walk, unit wins, the title board ("SPEC"), the road ladder for
   best-season depth, the schedule tag, and the seeds map. Two owner rulings on
   the details:
   - **A Specials loser's finish reads "Specials"** (`STATE_SPECIAL_FINISH`),
     not the event heading "State Specials" — the way "Semi-State" is not "the
     Semi-State Round". It supersedes the rung that sent the team in.
   - **The duals are numbered STATEWIDE per season, starting at 1**
     (`renumber_state_specials`) — the Divisions' pattern exactly, and for the
     Divisions' reason: how many there are depends on what the road failed to
     deliver that year (usually nothing), so the numbers are assigned at the
     world rung once both genders are known. Girls first, boys after,
     classifications bottom-up; roman on the honours chip like every unit.

## What to learn

- **A field-size table is not a format.** Moving `STATE_FIELD` to a number the
  draw and the road had never been designed for shipped without either being
  checked, because each layer trusted the other to care. When a constant is a
  DECISION table, every consumer of the decision needs re-verifying when a value
  changes — the per-division flight-weights rule, one level up.
- **A draw must refuse to disguise a qualification failure.** `run_state` padding
  a short field with byes converted "the ladder lost four berths" into "four
  teams advance unplayed", which looks like a rendering bug and hides the real
  fault. The Specials round makes the reconciliation EXPLICIT and on-court; the
  short-field warning names the group.
- **The warning was already firing.** `recovery filled 20 of 24` had been in the
  logs the whole time. A warning nobody is downstream of is a comment.
- **Test the render, not just the archive.** The archive was internally
  consistent through all of this — only the drawn tree was wrong, which is why it
  was found by eye. `test_jhsaa_state_draw_shapes.py` renders every field size
  through the real pipeline and asserts no team byes twice running and every
  column halves.
