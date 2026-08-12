# DESIGN — Recruit rating clarity: what the fog should hide (and what it shouldn't)

**Status:** exploration only — nothing in this doc is built, and no direction has been chosen.
This is a saveable reference for a design conversation in progress, not a spec.
**Date:** 2026-08-12
**Scope:** `/recruit/<pid>` profile page and the recruiting-rating pipeline —
`app/development.py`, `app/juniors.py`, `app/recruiting.py`, `app/world.py`,
`app/junior_circuit.py`, `app/web/state.py`, `app/web/templates/recruit.html`.

## Why this doc exists

Triggered by a live screenshot of Raegan Bahr (Class of 2027, D1 Women) that put four
overlapping numbers in front of the owner for one recruit: hero `OVR 33` (true current
ability), rating-card `OVR 100` (a board grade), `Composite 0.9979` (the same board
grade reformatted), and `TennisEye 2★` (a results-based star, on the *same* pyramid
as the board's 5★ "Blue Chip"). Two separate problems surfaced:

1. **Too much information doing the same job, explained badly.** OVR and Composite are
   one function's two return values wearing two card headers. "Current"/"Depth" in the
   Composite card and "Shared service"/"Your department" in the Scouting panel are the
   *same two numbers*, relabeled twice more. See the full field-by-field trace of the
   current implementation (formulas + exact `file:line` for every number on the page):
   the artifact published in this session, and the condensed version below.
2. **The mechanic itself doesn't hold up.** A recruit whose demonstrated performance
   reads as clearly average (2★ TennisEye) can render as a "5★ Blue Chip" on the
   primary board, because the board's star/grade is built from a noisy guess at her
   *hidden ceiling* (`ceiling_overall()`), not from anything about her current level or
   what she's actually done. The owner's objection is not "the labels are unclear" (that
   alone would be fixable with better tooltips) — it's that **a player whose current
   ability reads as a 2★ should never be capable of showing up as a 5★ under any
   fogging scheme.** Explicitly: *"I DO NOT WANT MORE MICROCOPY"* — the fix under
   discussion is structural (fewer, differently-organized numbers), not more
   explanatory text bolted onto the existing structure.

## How today's numbers actually work (condensed)

Four systems, currently tangled together on one page:

| System | Built from | Fogged? | Drives |
|---|---|---|---|
| **Ground truth** | `current_overall()`, `ceiling_overall()` — real 20–80 attribute grades | No | The match engine; hero banner display only |
| **Board rating** (OVR card, Composite card, stars, Blue Chip tier, `recruit_rank`) | `scouting_report("service")` = `ceiling_overall() + random offset, fixed per recruit` (`app/development.py:373-376`), then `recruit_grade(rank, class_size)` (`app/juniors.py:113-127`) — a percentile curve over *rank*, not ability | Yes, but fogging the **hidden ceiling** | The public star/grade display, **and** the AI's actual signing decisions (`talent_caliber`, `app/recruiting.py:250-255`) |
| **Results** (TennisEye, Ranking History, junior points/STR) | A real simulated junior-circuit season, solved STR + accomplishment points (`app/junior_circuit.py`) | No — it's what actually happened | TennisEye's separate star tier (`app/juniors.py:291-320`), the AI's per-coach `perceived_caliber` blend (`app/recruiting.py:266-281`, `app/world.py:1262`) |
| **Decorative** | `scouting_report("dept")` — a second random sample of the same ceiling, different seed string | Yes | Nothing. Only call site is the display line (`app/web/state.py:1678`). |

Net effect: the number that decides whether a recruit *looks* like a star (board
rating) is a random guess at a completely different, invisible quantity (ceiling) than
the number that shows what she's *actually done* (TennisEye/results). The two can — and
in the example, do — point in opposite directions, and nothing in the presentation
explains that they're allowed to.

## The complaint, in the owner's words

> "The PROBLEM here is that a player whose ABILITY is only a 2-star WOULD NOT be a
> 5-Star under any circumstances and that's where it kills my immersion... it just
> doesn't make sense for teams to miss on players who are CLEARLY worse than their
> ratings. What you want them to do is miss on kids who are deceptively good for their
> age/skill/moment who eventually stagnate or get worse or get injured or something
> like that — rather than assuming a college program is dumb enough to recruit a kid as
> a 5-star who is really a 2-star talent."

## The model the owner is describing

1. **Bust:** a kid who is genuinely, honestly great *right now* relative to peers —
   strong current signal, strong results, a deserved high rating — but has little
   ceiling left above where they already stand. They sign, they don't grow much, and
   they *were* a real 5-star the whole time — they just had nowhere left to go. Nothing
   about their current level was ever misjudged; the miss is entirely about trajectory.
2. **Gem:** equal-or-lesser current ability, ordinary or obscured results, but a large
   hidden gap to ceiling. Rated modestly — *honestly* — today, gets underrecruited or
   passed over, then outgrows the rating in the right program.
3. **Coach-unlock:** a big-ceiling player's growth is further gated by landing with the
   right developmental coach. **Already built, no new mechanic needed:**
   `app/coaches.py:493-502 development_multiplier` — a coach's `development_score`
   (35–65 band) maps to a ±30% growth-rate swing, applied in `world.developed_rosters`.
4. **Injury/decline as additional derailment:** also already built and deliberately
   non-deterministic — `app/injuries.py`, `docs/AAR-injuries.md` (real entropy, not
   seed-based, by explicit owner decision).

Items 3 and 4 are not gaps — they already exist and already work exactly as this model
needs. What's misaligned is only the piece that decides how good a recruit *looks* on
the way in.

## The tension the owner flagged, and why it resolves

*"If the AI can see current ability, doesn't that mean the AI 'knows' how good a
player is, which we don't want?"*

No — because rating **current ability honestly** and staying **blind to ceiling** are
independent axes, and only the second one needs to stay foggy for the "AI misses"
mechanic to work. Real-world recruiting services are, in fact, reasonably good at
grading a senior's *current* level (they watch the tape) and famously bad at
projecting who develops in college — that's not a design compromise, it's the honest
version of what a scouting service actually is. Under this model:

- The board (and the AI) can carry an honest — even still slightly noisy — read of
  *today's* quality. A little noise here is fine and realistic (small samples, home
  cooking, a bad day), but it's noise *around the true current level*, not noise
  standing in for a completely different hidden quantity.
- Nobody except the owner (god-mode / `scout_intel`) ever sees the ceiling.
- The entire interesting "miss" — the one worth having — lives in trajectory: growth
  headroom (ceiling − current), coach fit, injury, decline. All either already exist
  or are direct extensions of what exists.
- A recruit whose current ability reads as a 2★ **cannot** render as a 5★ grade,
  because the grade would no longer be built from a random sample of a number
  (ceiling) that has nothing to do with the performance numbers sitting next to it.

This is also, incidentally, the real-world recruiting-bust narrative: nobody is ever
surprised that a "5-star recruit" really was a very good high schooler. The surprise is
always about what happened *after* signing.

## Structural options on the table (nothing decided)

**A — Single letter grade.** One evaluative grade (A–F or A–D), built from current
ability + results, lightly fogged (an imperfect read of *today*, not of the invisible
ceiling). Ceiling is never publicly rendered in any form — it only ever surfaces
through what actually happens to the player after signing. Replaces OVR / Composite /
TennisEye with one number. Simplest option; kills the redundancy complaint outright.
Loses the "trust-the-eye vs. trust-the-tape" texture the current two-star system has.

**B — Grade (A) + the existing results ledger, kept as-is.** Same single grade as (A),
plus keep `Junior Results` / `Junior Match Record` (raw points, matches, tournament
finishes) untouched. That panel is a record of fact, not a verdict, so it doesn't
duplicate the grade even after collapsing OVR/Composite/TennisEye into one number.

**C — Two verdicts, both honest.** A "Grade" (holistic — scouted eye + results
blended, fogged) and a separate, more results-weighted "Performance" grade (closer to
today's TennisEye, little or no fog) — structurally similar to today's board/TennisEye
split, but *both* axes are now about the same real thing (current quality), just
weighted differently, so they can diverge without ever producing an absurd
5-star/2-star contradiction. Keeps the stars-vs-tape tension; keeps two things to read
instead of one.

**D — Minimum change.** Keep the current ceiling-based board number; only relabel it
truthfully. Included for completeness — it fixes the "explained badly" half of the
complaint but explicitly does **not** fix the mechanic: a fogged read of ceiling can
still make a 2★ performer render as a 5★ prospect. Not what the owner is asking for,
based on this conversation.

Independent of A–D: how much weight results get vs. a scouted "eye" component in
whichever grade(s) survive is its own dial, and the owner wants results to count for
more than they currently do in the *public* signal (today, results only drive
TennisEye — a side rating nothing else reads — while the AI's actual signing math
already blends results in via `perceived_caliber`).

## Decision (same session, continued)

Converged past the A–D menu above onto a concrete shape — closest to A/C's spirit, but
split by *role* rather than by weighting:

- **OVR stays** — card shell, position, "national board" framing, star tier, and the
  NATL/region/points-rank cells are all unchanged — but the grade it displays stops
  being `scouting_report("service")` (ceiling + noise) and becomes **current ability +
  results, lightly fogged**. This is the in-universe, imperfect, *public* verdict: what
  a scout believes about her today, allowed to be a little wrong, but never decoupled
  from what she's actually shown. The rank-based cells (`recruit_rank`,
  `state_rankings`, `points_rankings`) are untouched — this changes the grade's input,
  not any ranking list.
- **Composite is cut.** It was `recruit_grade()`'s own `rating` reformatted as a
  decimal — a second card for one number. Gone.
- **The Scouting panel loses its fog rows** — "Shared service," "Your department," and
  likely "4-year projection" (see open item below) were the same two random ceiling
  guesses as the old Composite card, one level down. **TEST stays** (real, unfogged,
  gates D4 admissions). **JHSAA high-school results stay** (a real record, not a
  rating).
- **TennisEye's role flips from "a second public rating" to "the truth panel."** Its
  rank/star/tier computation is untouched (results-based, same pyramid,
  `tenniseye_rankings()`) — results were always real, never fogged, so branding this
  card "the truth" needed no fog removed, only reframing. What changes is its grid:
  **junior points ("mean nothing to me") is replaced by `ceiling_overall()`** — a
  straight swap, still three cells (TE RANK / CEILING / STR). This becomes the one
  deliberate, legible home for the hidden ceiling — not leaked unmarked in the hero
  next to two fogged guesses at itself.

## Still open (owner deciding)

1. The hero banner currently repeats `ceiling` in its sub-line. Now that TennisEye is
   ceiling's deliberate home, does the hero drop it (one home only), or keep it as an
   above-the-fold glance?
2. `4-year projection` (`project(4)` — ground truth, no fog) loses its home once
   Composite and most of the Scouting panel go. Cut entirely, added as a fourth
   TennisEye cell, or placed somewhere else?
3. OVR's visual format (0–100 number + stars + rank-cell row) — confirmed staying as
   today, or does the earlier letter-grade (A–F) idea replace it?

## Sources

`app/development.py:238, 291-292, 298-299, 319-332, 366-376` ·
`app/juniors.py:99-127, 138-144, 243-320` ·
`app/recruiting.py:236-310` ·
`app/world.py:1262` ·
`app/junior_circuit.py:593-660` ·
`app/web/state.py:1596-1688` ·
`app/web/templates/recruit.html` ·
`app/coaches.py:493-502` ·
`app/injuries.py` ·
`docs/AAR-fog-of-war-recruiting.md` (2026-06-27) ·
`docs/AAR-tenniseye-results-star-rating.md` (2026-06-26) ·
`docs/AAR-recruit-redesign-analytics-bureau.md` (2026-06-14) ·
`docs/AAR-injuries.md` ·
`docs/AAR-coach-development-growth.md`
