# AAR — out-of-state affiliates in implausible leagues

**Date:** 2026-08
**Status:** Landed. Owner rules 2026-08.
**Scope:** `data/jhsaa/schools.json` (league/group/one classification), new
`scripts/jhsaa_affiliate_leagues.py` and `scripts/jhsaa_border_realignment.py`.
See also `docs/AAR-jhsaa-promotions-and-affiliates.md` (how the 13 affiliates
were created) and `docs/AAR-jhsaa-league-identity.md` (leagues as their own
dataset — the same "a league is `(classification, name)`" fact bites again here).

## What started it

The 13 out-of-state affiliate schools (Boise, Bend ×4, Rock Springs, Green
River, Jackson Hole, Lower Lake, Ukiah, Baker City, Money, Spring Harvest) were
placed into whichever league their donor school's classification happened to
already occupy. Nobody had checked whether that league was anywhere near them.
It mostly wasn't: Rock Springs' league (Ambassador) spanned 519 miles with its
nearest league-mate 94 miles away; Lower Lake's (Kajaani) spanned 462 miles with
NO plausible local rival at all, nearest at 223 miles.

## Measure before moving anything

The first instinct — "an affiliate is out of state, so it must be the outlier
wrecking its league" — was wrong for most of them. Real coordinates (prep-network
`records/orgs/cities.json`, plus the gazetteer's locally-anchored 2046 Great
Basin table for the newer Wyoming/Utah ground) let this be checked directly:
compute each league's span with and without the affiliate.

| affiliate | league span | without it | affiliate adds |
|---|---|---|---|
| Baker | 274 mi | 274 | **0** |
| Bend Senior / Mountain View / Summit | 268 | 268 | **0** |
| Caldera | 276 | 276 | **0** |
| Money / Spring Harvest | 105 | 100 | 5 |
| Peregrine | 370 | 348 | 23 |
| Green River | 508 | 450 | 58 |
| Rock Springs | 519 | 442 | 77 |
| Ukiah | 225 | 130 | 95 |
| **Lower Lake** | 462 | 268 | **194** |

Most of these leagues were already that wide among their JEFFERSON members —
moving the affiliate out would have fixed nothing. Only Lower Lake was itself
the problem. **Diagnose the cause before spending a redraw on the symptom** —
the same lesson `AAR-jhsaa-1a-2a-classification-split.md` and others in this
file already teach for different subsystems.

## Round 1 — the scalpel (`jhsaa_affiliate_leagues.py`)

Based on that measurement, a first pass moved only what needed moving:
- Lower Lake → Valle Vista League (5A, plain league move)
- The four Bend schools → united in a revived, empty "Sunkist League" (8A) —
  they had been split across 6A and 7A, and **a league is
  `(classification, name)`**, so schools in different groups cannot share one
  however close they stand. Uniting them was therefore a `group` move, never
  `classification` — the same distinction `PLAY_UP`/`COMPETITIVE_MOVES` already
  enforce: `_TALENT` reads `classification`, so moving both would hand a
  relocated school a free talent upgrade instead of a harder field it has to
  earn.
- Rock Springs → Group 2 / Olympic, joining Green River and Jackson Hole who
  were already there — one school moves instead of three.

This left the owner's real ask half-answered: "all the Bend schools should be
together" and "all the wyoming schools should be together" turned out to mean
something stronger than "fix the worst outlier."

## Round 2 — the border realignment (`jhsaa_border_realignment.py`)

Owner-supplied, town-by-town, verified against the same coordinate set before
anything was written (every distance in the ask checked out within a mile or
two):

1. **California → 8A district.** Six of the eight target schools (Bardsley
   County, Paddock County, Olivet County, Olive Head, Ditch Fork, Cook City)
   turned out to be **already together** in Mariners League — the
   county-representation promotions earlier this session had put them there
   without anyone noticing it was already the district. Mariners *became* the
   California district: Ukiah joined from Summit, Lower Lake was reclassified
   in (not play-up-flagged — see below), and the four Mariners members outside
   that cluster moved to their own nearest 8A home (0–46 miles each).

2. **Lower Lake reclassified, not play-up-flagged.** Explicit owner
   instruction: change `classification` **and** `enrollment`, not the seeded
   `play_up` mechanism. This is the one school in the whole two-round pass
   whose classification actually changes — every other move is `group`-only.
   The promotions had put a real 8A cluster on top of it (30–85 miles) while
   its nearest 7A neighbor sat 86+ miles away, so 8A was a genuine fit, not a
   convenience.

3. **Wyoming → Group 1 / Ambassador, all three together.** Green River and
   Jackson Hole came UP from Group 2 by explicit group override, joining Rock
   Springs (already there from round 1).

4. **Emigrant County got its own league** — the fix that mattered most, and
   one I initially missed. My own plan was going to backfill the vacated
   Ambassador/Olympic seats with borrowed Jefferson schools, displacing four of
   them. The owner asked directly: **"why couldn't those 8 schools just be
   their own league?"** They could — the only reason they weren't already one
   league is that five sat in Group 1 (Ambassador) and three in Group 2
   (Olympic), and a league can't span two groups. Moving Aurelia/Frontier/
   Goodman up to Group 1 turned all eight into a single league, **27 miles
   across, two towns** — down from the 432/502-mile leagues they'd been
   dragging down. Cost: zero Jefferson schools moved, versus four under the
   backfill plan. They landed in Sage Plains League, which was empty (a
   `RETIRE_AND_REPLACE` donor's leftover row — the same lever that revived
   Sunkist for 8A in round 1).

5. **Olympic repaired itself for free**, pulling in the two Bridger County
   schools it should always have had (from Forks, which drops from 11 to 9,
   keeping Money and Spring Harvest together). Nothing sunset, nothing
   invented.

## The general lesson

**When several schools "should be together" and aren't, check whether the
blocker is a group mismatch before reaching for a redraw or an invented
league.** A league is `(classification, name)` — the map already told this
story once (`AAR-jhsaa-league-identity.md`, "the repetition is happening
because right now they sound like the same ontology") and it told it again
here in a different shape: schools that were geographically obvious neighbors
looked unrelated because nothing let them share a name across a group line.
The fix in every case here was a `group` override (never `classification`,
which stays the talent/enrollment basis and the one thing play-up and
`COMPETITIVE_MOVES` protect), not a new invention.

**"Their own league" is always worth checking before backfilling one.**
Filling a vacated league from the nearest Jefferson pool is the more obvious
move and was my first instinct; it costs displaced schools proportional to how
many seats need filling. Grouping the displaced schools into their OWN league
costs nothing if they're geographically coherent as a block, which a genuinely
mis-grouped cluster usually is (they were dragging their old leagues wide for
the same reason they can now be tight together).

## Verification

Both scripts snapshot every school's `classification` before writing and
refuse to write if anything outside the one explicit reclassification (Lower
Lake) drifted. `jhsaa_border_realignment.py` additionally asserts the EXACT
membership of every named league (no silently-gained ninth member) and that
both genders always agree on a league. Checked directly after each run:
`sponsor_floor` clears for every touched group in both genders; no league
exceeds `MAX_DISTRICT` 12; rosters still build with the correct affiliate
hometown/region (e.g. Lower Lake → "Lower Lake, CA" / region "California");
and no `playup` field on any school row moved.

## Left alone, on purpose

- **Baker** — 66 miles from a league-mate already, with "plenty of Idaho and
  other Jefferson schools near it" (owner). Grouping by state was the wrong
  reading of the ask; the rule is that schools in the SAME place must not be
  split, not that a state border makes a league.
- **Peregrine** — 24 miles from a league-mate; its 370-mile outlier is one far
  member of an already-348-mile league it isn't the cause of.
- **Olympic League's residual Jefferson-only sprawl** (~450 mi among its
  Jefferson members alone, pre-existing) — real, but a Jefferson redistricting
  job, not something an affiliate caused or this pass's scope.
- A proposed California/Nevada border sunset-and-replace (Serra Caverly →
  Chilcoot/Vinton analogue, Tailingford Union → Verdi analogue) was dropped
  once the "own league" fix made it unnecessary for the goal at hand; it
  remains a live idea if the owner wants that ground filled out later.
