# AAR — Recruit rating clarity: the board reads today, not the ceiling

**Date:** 2026-08-12
**Scope:** `Prospect.today_grade()` / `.scouted_read()` (`app/development.py`);
`juniors._recruiting_score`, `juniors.grade_letter` (`app/juniors.py`);
`recruiting.talent_caliber` (`app/recruiting.py`); `state.recruit_profile`
(`app/web/state.py`); the recruit profile page (`app/web/templates/recruit.html`).
Design record: `docs/DESIGN-recruit-rating-clarity.md` (read that first for the full
back-and-forth — this AAR is the condensed "what shipped").

## The problem it fixes

The recruit profile page put five overlapping numbers in front of the owner for one
recruit — hero `OVR 33` (true current ability), rating-card `OVR 100` (a board
grade), `Composite 0.9979` (the same board grade, reformatted), `TennisEye 2★`
(results), and a `Scouting` panel repeating two of those numbers a third time under
new names. Two distinct failures, from a live example (Raegan Bahr, Class of 2027):

1. **Presentation:** `OVR` meant two different things on one page (a 20-80 true
   grade in the hero, a 0-100 rank-derived grade in the card). Composite was
   `recruit_grade()`'s own output redisplayed. "Current"/"Depth" in the Composite
   card and "Shared service"/"Your department" in the Scouting panel were the exact
   same two numbers, relabeled twice more.
2. **Mechanic:** the board's star/grade was built from `scouting_report("service")`
   — a noisy guess at the recruit's *hidden ceiling* — completely decoupled from her
   demonstrated performance. A recruit whose results read as clearly average (2★
   TennisEye) could render as a "5★ Blue Chip" on the primary board. Confirmed in
   both directions with a second live example (Elina Vesnina): current ability 72,
   STR 51.7, `TE RANK #1` of 2,500 — buried as a 2★ board grade.

Owner's framing, verbatim: *"it just doesn't make sense for teams to miss on players
who are CLEARLY worse than their ratings. What you want them to do is miss on kids
who are deceptively good for their age/skill/moment who eventually stagnate or get
worse or get injured — rather than assume a college program is dumb enough to
recruit a kid as a 5-star who is really a 2-star talent."*

## What changed

### The public signal now fogs TODAY, not the ceiling
New `Prospect.today_grade()`: current ability blended with demonstrated
junior-circuit results (STR, mapped onto the same 20-80 scale), weighted by
`TODAY_RESULTS_W` (0.4) and scaled by `junior_str_reliability` — a thin or absent
junior résumé is judged on current ability alone, same reliability-gating idea
`recruiting.perceived_caliber` already used. New `Prospect.scouted_read(source)`:
`today_grade()` blurred by a light, per-recruit-fixed offset (`TODAY_FOG_MIN/MAX`
4-10, far lighter than `scouting_report`'s ceiling-fog of 7-31) — deterministic per
`source` so it's stable across page loads, same pattern as the method it replaces.

`scouting_report()` (the old ceiling-based fog) is **untouched** — still correct,
still exercised by `test_development.py::test_two_ceiling_reports_independent_within_fog`
— it's simply no longer called from any production path. Nothing else in the repo
calls it (verified by grep).

### The board and the AI stay the same number
`juniors._recruiting_score` and `recruiting.talent_caliber` both switched from
`scouting_report("service")` to `scouted_read("service")` — the property the owner
confirmed matters (the board display and what every AI program's
`perceived_caliber` actually perceives must be identical) holds exactly as before,
just pointed at the new formula. A 2★-performing recruit can no longer randomly
land a 5★ grade, because the fog is now over a real, roughly-observable quantity.

### TennisEye becomes the truth panel; the ceiling gets one deliberate home
TennisEye's rank/star/tier computation is **unchanged** (still `tenniseye_rankings`,
still results-based, still the same `TIER_CUTOFFS` pyramid) — results were always
real, never fogged, so no fog needed removing. What changed is presentation:
`juniors.grade_letter()` renders the same tier as a letter (A+ through F) instead of
stars, so it's never visually confusable with the board's fogged stars at a glance;
its grid swaps `POINTS` (a raw count the owner found meaningless on its own) for
`POT` — the literal, unfogged `ceiling_overall()` — giving the hidden ceiling one
deliberate, legible home instead of leaking out unmarked in the hero next to two
fogged guesses at itself.

### Cut
- **Composite card** — `recruit_grade()`'s own `rating`/`composite` output,
  redisplayed as a second card. `recruit_grade()` itself is untouched (still used
  elsewhere, e.g. the recruiting board's per-row grade) — only the profile page
  stopped rendering it.
- **Scouting panel's fog rows** ("Shared service," "Your department," "4-year
  projection") — the first two were the same `scouting_report` calls the Composite
  card used, a third label on identical numbers; the third (`project(4)`) didn't
  self-explain its purpose without the mechanism spelled out, which fails the
  "no more microcopy" bar the same numbers already had. TEST (academics, unrelated
  to tennis ability) survives; the panel is renamed **Academics** since that's now
  accurate.

### Renamed for clarity, not decorated
Hero `OVR` → `CUR` (true current ability) freed the word `OVR` to mean one thing —
the board card's grade — instead of colliding with the hero. Hero `ceiling` → `POT`
(true potential), shown in both the hero (quick glance) and TennisEye (detail) —
decided as intentional repetition of a summary stat, not the redundancy this whole
pass targets (that was always *contradictory* numbers sharing a label, not a number
appearing twice in agreement with itself).

## A worked check (from the design doc, still holds)

Rank 12 of 2,500 through `recruit_grade()`'s curve → composite `0.99794…` → the old
Composite card would have shown `0.9979`, matching the OVR card's `100` exactly —
literally the same number, which is why deleting one of the two cards lost nothing.

## Files
`app/development.py` (new `today_grade`/`scouted_read`, `TODAY_RESULTS_W`,
`TODAY_FOG_MIN`/`MAX`) · `app/juniors.py` (`_recruiting_score` repointed,
`grade_letter` added) · `app/recruiting.py` (`talent_caliber` repointed) ·
`app/web/state.py` (`recruit_profile` view keys) ·
`app/web/templates/recruit.html` (hero, rating cards, Scouting→Academics) ·
`tests/test_juniors.py`, `tests/test_web_recruiting.py` (updated for the new
formula/copy) · `tests/test_recruit_signing.py` (see below).

## The one real regression this surfaced (not a bug in the redesign)

`test_local_territory_pull_binds_locals_but_not_elites` failed on the first full
run: a Puerto Rico recruit generated with `talent=78` (a high ceiling) no longer
reliably escaped a low-budget local D2 for a mainland power. Root cause, confirmed
by reading `generate_prospect`: `current = potential * maturity`
(`maturity ∈ [0.45, 0.95]` by default), so a `talent=78` recruit's *current* ability
is frequently mid-tier, not elite — she's the exact "obscured gem" archetype this
whole redesign exists to produce, now correctly read as non-elite by a perception
system that (by design) never sees the hidden ceiling. **This is the redesign
working, not breaking** — the test encoded the old ceiling-based elite-recognition
assumption. Fixed by giving the test's elite case a high `maturity_range` (0.90-0.95)
so her current ability actually sits near her talent, restoring the test's real
intent (budget floor still gates a low-budget program away from a recruit who
currently *reads* elite) without relying on the ceiling leak the rest of this AAR
removes. `test_elite_recruits_sign` (the broader "no genuinely good player vanishes"
invariant) held with no changes — this was narrowly about ceiling-based elite
*recognition*, not the signing system generally.

## Notes for the next agent
- If you add a new place that needs "how good is this recruit," call
  `scouted_read`/`talent_caliber`, never `scouting_report`/the old ceiling read —
  the latter is intentionally orphaned from production, kept only because it's
  still a valid, tested utility that a future truth-telling surface (`scout_intel`)
  could reuse.
- `TODAY_RESULTS_W` (0.4) is the only dial for "how much results move the public
  read" — the owner asked for this to be more than the old 0%, not for a specific
  number; revisit if the board still feels too talent-anchored or too results-swingy.
- The recruiting board LIST page (`recruiting.html`) still shows `recruit_grade()`'s
  numeric composite per row — untouched, out of scope for this pass (the owner's
  complaints were specifically about the profile page). It automatically inherited
  better-ordered ranks from the formula change, since `recruit_rank` feeds it.
