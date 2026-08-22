# AAR — Per-player development curves (era-gated) + talent-aware rest staffing

Owner rules 2026-08. Two changes to the JHSAA driven by one live-save report: six
seasons in, rosters were senior-heavy, underclassmen waited two-plus years to
play at all, "player development for the younger players isn't happening and I
don't even get to know how good they are."

## 1. What was actually wrong: development was LOCKSTEP, not absent

Every JHSAA player already "developed" — maturity rises with grade — but the old
model (`_MATURITY` bands 9:(0.40,0.48) … 12:(0.70,0.78)) mapped ONE uniform draw
into each grade's band. Everyone climbed the same four steps in the same order,
so:
- the ladder almost never reordered between seasons (a freshman behind a senior
  stayed behind that senior for four years — "waiting your turn" was arithmetic);
- no freshman outside the 1-in-100 `PRODIGY` roll could arrive ready to play;
- a player's whole trajectory was invisible until seniors above them graduated.

## 2. The fix: a rolled four-year TRAJECTORY per player (`jhsaa._dev_maturity`)

At entry, on its own rng stream (`jhsaa-dev` — the prodigy-roll idiom, never the
main roster rng, which would shift every later draw and regenerate everyone):
- **arrival** from a wide band, with `DEV_READY_RATE` (0.24) arriving at
  `DEV_READY_ARRIVAL` (0.66-0.82) — real ready-to-play freshmen, ordinary rather
  than prodigious;
- **finish** from a wide senior band (`DEV_FINISH`), at least `DEV_MIN_RISE`
  above arrival;
- **shape** (`DEV_SHAPES`): steady / early bloomer / late bloomer / senior-year
  spike — players PASS each other between seasons, which is what moves a ladder;
- **`DEV_MIN_STEP`** (0.045/yr) is the program-wide floor: every kid on a roster
  visibly improves every year, playing time or not.

**‼️ The bands are DELIBERATELY NOT MEAN-PRESERVING.** The first draft held each
grade's mean to the legacy bands (freshman ~0.44 of ceiling). The owner — a real
high-school coach — rejected that as too conservative and dictated the shipped
numbers ("you need them able to contribute and play … the whole point of a high
school sim is to watch 4-year player development"). Freshmen now average ~0.57 of
ceiling, seniors ~0.85: a level shift on top of the spread. Do not "correct" it
back down to match the legacy means.

**‼️ ERA-GATED (`jhsaa.dev_era()`, the `name_era()` idiom exactly).** Players are
regenerated from seed, so an ungated curve change re-rates every archived
season's rosters — ladders, player cards and awards would disagree with the
seasons actually played. Cohorts with entry year < era keep the legacy bands
byte-for-byte (pinned by `test_pre_era_cohorts_stay_on_the_legacy_bands`); the
era self-configures once per save from the newest archive (+2, the index→calendar
conversion `name_era` uses) and persists in `worldconfig` (`jhsaa_dev_era`),
memoised on the DB path, cleared by `reset_schools()`. `_gen_seat` passes the
computed maturity as a degenerate `(m, m)` band so `generate_prospect` consumes
the SAME one uniform draw in both eras.

**Knock-on: honorable mention grew, and the runaway guard clipped it.** More
underclassmen (and rested-in bench players, §3) log real matches, so deeper
classes legitimately clear the HM merit threshold in larger numbers; the deepest
hit `HM_MAX_MULT`'s cap exactly — which turned a documented "runaway guard,
never a target" into a slot count. The guard was raised 2.5 → 3.5. If HM sizes
ever hug the new cap, the same reasoning applies again: fix the guard, not the
merit bar.

**Stale-test find:** `test_7a_gets_a_fourth_team…` still named 7A as the class
with a Fourth All-State team; since the nine-class realignment the largest class
is 9A and `aw.AS_TIERS` is the authority. The test now reads the constant.

## 3. Talent-aware rest staffing (`jhsaa._rest_count`)

Colorado's big programs field V2/V3 squads; everywhere else the same depth is
exercised by coaches SITTING starters against overmatched opponents. The owner
did not want V2 squads, injuries, or a fatigue model in the JHSAA — this is the
in-lieu mechanism.

- **Trigger**: a strength gap that must ALWAYS hold (`REST_GAP` 10 OVR on the
  top-nine mean, `_strength`) + the opponent's record — .300 or worse once they
  have `REST_MIN_SAMPLE` (6) duals; before that the gap alone decides (early
  season has no records). A weak-LOOKING roster that is actually winning is
  never rested on.
- **Effect**: with probability `REST_RATE` (0.75), 1 — sometimes 2 (`REST_TWO`)
  — starters sit **from the TOP of the ladder** and everyone shifts up a rung,
  so the card still reads as the ladder (the owner's clear-ladder requirement)
  and two more bench players reach real courts than `_ROTATE_*` alone provides.
- **‼️ Never in the postseason** (the frozen Order of Ability is strict — both
  the rule and the owner's explicit "never fire in the playoffs") **and never at
  a showcase** (the point of the weekend is playing your best against power
  programs). Both hold by construction: the rest check lives only in `_lineup`'s
  regular-season branch, below the postseason and showcase returns.
- **Guarded on the bench** (`spare = len(order) - need`): resting past the bench
  would wrap the same player onto two lines of one dual — the exact fault
  `ROSTER_FLOOR` exists to prevent.
- `play_dual` now passes each side's opponent into `_lineup` (`opp=`); no other
  caller exists. Extra rng draws shift the rotation stream for future seasons
  only — the archive is append-only and never re-simulated.

Pinned by `tests/test_jhsaa_rest.py` (fires on record+gap, record overrides the
eye test, top-rested ladder slice stays contiguous, postseason/showcase never
rest, short roster never wraps) and `tests/test_jhsaa_development.py`.

## Lessons

- **"Development isn't happening" can mean "development is UNDIFFERENTIATED."**
  Every player was growing; nobody was growing *differently*, so nothing the
  owner could watch ever changed order. Variance, not rate, was the missing
  ingredient — and half of the fix (arrival overlap) isn't development at all.
- **When the owner hands you numbers, take the numbers and record the intent.**
  The mean-preserving draft optimized for an invariant (association level) the
  owner was happy to spend for the actual goal (four playable years).
- **A threshold behind a cap is a cap.** The HM guard sat un-binding for a year
  and became the effective rule the moment the distribution moved. When a
  distribution changes, re-check every "should never fire" limit downstream.
