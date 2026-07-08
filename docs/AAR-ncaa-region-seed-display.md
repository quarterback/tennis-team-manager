# AAR — NCAA field shown by region seed (1–24 / 1–16), not overall 1–96

**Date:** 2026-07-08
**Scope:** `web/state.ncaa_bracket_view` (reveal field, seed sheet, played
bracket, new `_group_by_region` helper); `templates/ncaa_bracket.html`.
**Sister doc:** `docs/AAR-regional-bracket-scurve.md` (the structure this fixes
the *display* of), `blog/04-four-regions-no-pods.md`.

## Symptom
The NCAA D1 bracket page seeded the field **1–96** — the "Top seeds" sheet read
`1 Oregon … 2 Louisville … 96`, one flat national list. That is not how the
event is actually run: since the S-curve refactor the field is drawn as **four
balanced regions** whose champions meet in the national semifinals (the
real-life / basketball four-quadrant model). The bracket *was* regional; the
**labels lied** and presented it as a flat 1–96 draw.

## Fix
Display the **region seed** — the S-curve seed line, **1–24** in a 96-team D1
field and **1–16** in a 64-team field — instead of the overall committee rank.
The reveal and "Top seeds" panels are grouped by region (in `MAIN_DRAW_ORDER`,
so the two panels shown adjacent are the ones that meet in the semis), each
counting 1..N; played-bracket duals inside one region are tagged with the region
name. The overall committee rank remains only the **input** to the S-curve split
(`regions.scurve_regions`), never the displayed number. Region seed is derived,
not stored: `region_seed = (overall_rank − 1) // 4 + 1` on the seed-ordered field
(seed line k holds overall ranks 4k−3 … 4k).

## ⚠️ Why this was wrong for weeks even though the spec was crystal-clear

The S-curve spec (`AAR-regional-bracket-scurve.md`) was **not** ambiguous — it
describes four regions seeded within themselves. So why did the UI keep showing
1–96? Three compounding reasons, and they're the lesson:

1. **The regional refactor optimized for "touch as little as possible," and the
   seed-label layer was one of the things it proudly did *not* touch.** That AAR
   literally states: *"Because the existing round-advancement just pairs adjacent
   winners up the tree, **no advancement or rendering code had to change** — only
   the placement of round 1."* That was true of the **bracket geometry** and read
   as a win. But "rendering didn't change" is exactly the bug: the *placement*
   became regional while the *seed numbers* stayed on the pre-region 1–96 scale
   that `ncaa_bracket_view` had always emitted. Reusing the old renderer silently
   inherited its old seed semantics. **A structural refactor that changes what a
   number *means* must revisit every place that number is displayed — "no render
   change" is a smell, not a badge, when the refactor re-partitions the field.**

2. **Both numbers are "correct," so nothing looked broken.** Overall rank 1–96 is
   a real, legitimate quantity (it's the S-curve *input*). The page showed a true
   number — just the wrong one for a regional presentation. There was no
   exception, no `None`, no visibly wrong team; it took a human looking at the
   screen and saying "that's not how the real tournament seeds" to catch it. Bugs
   where the output is plausible get no help from the runtime.

3. **The previous work got *halfway* and that masked the gap.** The regional pass
   *did* add region **chips** to the view (`region_of`, the `rgn` label). So the
   page already said "Cardinal / Evergreen / Eclipse" next to teams — it *looked*
   region-aware. Surfacing the region **name** while leaving the region **seed**
   on the national scale is the tell: whoever wired the chips thought about
   regions for labels but not for the seed number, and the half-done state read as
   done.

4. **Nothing tested the displayed seed.** `test_regions.py` verifies the split
   math (balance, round-trip, distinct semifinal regions) and `test_seasonmode`
   verifies a champion emerges — but no test asserts what seed **number** the view
   renders. The "Verified" section of the structure AAR checked that the bracket
   *drives to completion* and that *four distinct regions* reach the semis; it
   never checked that a team's shown seed was ≤ 24. Structural correctness was
   fully covered; presentation semantics were covered by nobody.

**Takeaway for the next agent:** when a refactor re-partitions a field (national →
regional, flat → pods, etc.), the seeds/ranks/labels a user *reads* are part of
the change surface even if no rendering code errors. Grep every place the old
scale is emitted (`seed_map`, `top_seeds`, `field[...]["seed"]`) and ask "does
this number still mean what the page implies?" A clear spec does not protect a
display layer that was deliberately left untouched.

## Verified (this change)
Drove a fresh D1/men season to selection and to a champion (injuries off for
determinism), then rendered `/ncaa` through the Flask test client:
- Reveal: four region panels, each seeded **1–24**; the four #1 seeds sit in four
  distinct regions (Cardinal/Utopia/Evergreen/Eclipse in the sample world). No
  seed 96 anywhere on the page.
- Played bracket: **max displayed seed = 24**; grouped "Top seeds" sheet shows
  1–4 per region; champion card renders its region seed.
- 64-path (D2/D3/D4) falls back to seeds 1–16 by the same derivation.

## Gotchas for the next agent
- The region-seed derivation assumes the field is in **overall committee-seed
  order** (as `sm.ncaa_field` returns it) and exactly 96 or 64 teams. Off-size
  fields (`_region_map` returns `[]`) fall back to the old overall numbering on
  purpose — don't "fix" that into a divide-by-zero.
- Region seed is derived on the *view* only; `bracket.py` / `seasonmode` still
  seed and draw on the overall order (that's the S-curve input). Do **not** push
  the region seed back into selection — it would corrupt the split.
- A bubble team can drop out of the post-hoc `ncaa_field` recompute, leaving one
  played-bracket opponent unseeded (`seed = None`). Pre-existing, unrelated to
  this change; the template already guards `t.seed` truthiness. If you touch the
  round-1 tagging, keep the `None`-seed guard.
