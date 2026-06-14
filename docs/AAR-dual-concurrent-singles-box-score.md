# AAR — Dual box score: team labels + concurrent singles with partial scores

**Date:** 2026-06-14
**Scope:** Make the dual-match box score read like a real college tennis result:
1. Every player shows which school they play for.
2. The six singles play *concurrently* — they finish in a varied order (not court
   1→6), and a clinch leaves the in-progress courts **unfinished with a partial
   score**, not a blank "not played".

Commits (branch `claude/fervent-archimedes-xo35i7`):
- `b378063` Dual simulator box score: label each player's school
- `<this round>` Dual: singles play concurrently; abandoned courts keep partial score

---

## 1. Player → school labels

### Why
Reported in-session against the Dual Simulator: a box score between two
unfamiliar teams listed only player names, so you couldn't tell who played for
whom. Season-mode box scores already tagged each side with its school
(`bl-court-team`); the standalone dual simulator did not.

### Fix
- `app/web/sim.py` `_sides()` now carries the home/away school onto each side.
- `dual_result.html` renders it under the name with the same `bl-court-team`
  treatment season mode uses.

GTT duals render a different (left = home / right = away, franchise in the
header) layout and were already unambiguous, so they were left alone.

---

## 2. Concurrent singles, varied finish order, partial scores

### Why
The reported behaviour, in the user's words: matches "always played" — they just
don't always finish, and an unfinished match still has a score that the engine
threw away. Two concrete problems:

- **The abandoned set never varied.** Singles resolved in court order (S1→S6),
  accruing points until a side hit 4, then the *remaining* (always
  highest-numbered) courts were marked not-completed. So it was always the top
  courts left hanging.
- **Abandoned courts showed "not played".** In reality those matches were in
  progress when the dual clinched — they have a score; the box score just
  discarded it and printed "Not played — dual clinched".

### Model
The six singles run at the same time, so they finish in an order set by how long
each took — a 6-0 6-1 rout is off the court well before a 7-6 6-7 7-6 grind —
**not** by court number. Implemented in `engine/dual.py`:

1. Simulate all six singles to completion.
2. Give each a running length = total games played + a tiny seeded jitter
   (`_match_length`), and resolve them in that finish order.
3. Accrue team points as matches finish. The moment a side reaches 4, every match
   still in progress is **abandoned at its current score**: `_partial_score`
   keeps completed sets verbatim and splits the in-progress set proportionally to
   its eventual score (e.g. a court that would end `6-2` shows `4-1` if stopped
   ~⅔ through). `DualLine.partial` carries those home-perspective set tuples;
   `completed=False` still flags it.

### Why the dual winner is invariant
A clinch needs 4 of the 7 lines (1 doubles point + 6 singles). Exactly one team
can hold ≥4 of 7, and the team with ≤3 can never reach 4 — so the ≥4 team always
reaches 4 first under *any* finish order. Finish order therefore changes only
**which** courts are abandoned and the **exact clinch score** (4-0…4-3), never
who wins. Standings and bracket results are unaffected.

### Season-mode playing-time guarantee
`forced_appearances` guarantees every roster player one dual where they appear,
and the appearance only "counts" if their line lands in the completed-match
corpus. The old code relied on "S1-S3 always complete" (true under court-order
resolution) to seat forced players safely. Concurrent finish order breaks that
invariant, so `simulate_dual` gained a **`priority_finish`** argument — court
indices that finish first. `app/season.py` passes the courts holding
guaranteed-appearance players; since the first three singles to finish always
complete (a clinch can't happen on doubles + two singles), a small priority set
is a hard completion guarantee. The STR corpus still counts completed lines only,
so ratings are never fed partial-match data.

### Surfacing
Abandoned lines now carry player identity + partial score through both view
layers (`app/web/sim.py`, `app/season.py`) and render in both box-score templates
(`dual_result.html`, `season_dual.html`) as the player, team, and score-so-far,
labelled **"Unfinished"** instead of "not played". The winner checkmark only
appears on completed lines, so an unfinished court reads as "partial score, no
checkmark on either side".

---

## Measurement
3,000 random D1-men pairings (fast sim):

| Abandoned singles | Share | Clinch score |
|---|---|---|
| 0 (all nine played out) | 27% | 4-3 |
| 1 | 30% | 4-2 |
| 2 | 27% | 4-1 |
| 3 (earliest possible) | 16% | 4-0 |

**~73% of duals clinch before all courts finish.** Three is the ceiling (a clinch
needs 4 of 7 points, doubles supplies ≤1, so ≥3 singles always complete). Random
pairings over-weight blowouts; a real conference schedule of closer teams would
shift toward more all-played 4-3s.

## Tests
`test_dual.py` (clinch-at-4, total ≤7, determinism), `test_season.py`,
`test_seasonmode.py`, and the web season/singles/doubles suites all pass
unchanged — they assert outcomes/determinism, not which courts complete.

## Known follow-up (not done)
On very narrow screens the `.bl-final` column (which holds the "Unfinished"
label) is hidden by the existing mobile rule, so an unfinished court is conveyed
only by its partial score and the absence of a winner checkmark. A small
always-visible "unfinished" cue near the court number would make it explicit on
phones.
