# AAR — what a program IS, and the tournament that proved it wasn't working

Three passes over the JHSAA talent model, in the order they happened, because each one
only became visible once the previous one was measurable.

---

## 1. The Tournament of Champions was a measuring instrument before it was a feature

Asked: *"would it be worth it to replicate the old New Jersey Tournament of Champions in
JHSAA tennis or not?"*

Answered by playing it. Five classification champions from three archived seasons, 60
runs each through a real `seeded_draw`:

| | titles | reached final |
|---|---|---|
| 7A | 55.3% | 88.3% |
| 6A | 39.2% | 78.1% |
| 5A | 2.5% | 15.6% |
| 4A | 2.5% | 16.1% |
| 3A-1A | **0.6%** | 1.9% |

Recommendation: don't build it. Three of five entrants were ceremonial.

That was the right read of the numbers and the wrong read of the problem. The owner's
response reframed it: *"the talent distribution is unfairly distributed right now
disproportionately to the big schools when in reality that's not how tennis works."*

> A feature that measures badly is sometimes telling you about the model, not about
> itself. The TOC was a fair test that the world failed.

## 2. The talent ladder was backwards, and only a position-by-position measurement showed it

`_TALENT` was an even −5/−4 step per classification with the spread NARROWING as the mean
fell. Measured (boys, mean current OVR):

| | #1 | #9 | #1→#9 drop | best #1 seen |
|---|---|---|---|---|
| 7A | 54.4 | 31.1 | 23.2 | 60.0 |
| 3A-1A | 42.0 | 22.8 | **19.2** | **51.0** |

The number ones were **12.4** apart and the number nines only **8.3** — the TOP fell
faster than the DEPTH — and the drop from #1 to #9 was *flatter* at a small school. A
3A-1A program could not produce a 60 at all.

Real high-school tennis is the opposite. Good players turn up everywhere; enrollment buys
**depth**. In Oregon's 2026 boys table the smallest classification finished No. 9
statewide and four of the top eight were 5A.

The fix is one mechanism, not two: let the mean fall and the spread **widen**. Twelve
ceilings are drawn and the best nine dress, so a wide draw lifts the number one a long way
and drags the number nine down. After: top-end gap **4.5**, depth gap 8.3, the drop now
*rises* as schools shrink, and every classification reaches a 59-61 number one.

Validated on a played season, not on the bands: statewide TOSS boys had **6A No. 1, 5A
No. 2**, 4A's best at No. 5 and 3A-1A's at No. 11, with the medians still indexing
downward (131/126/146/180/183). Thinner, not equal.

> One knob, two effects, because the selection step (best 9 of 12) does the work.
> Reaching for a second parameter to model "depth" separately would have been the
> obvious move and the wrong one.

## 3. A program is more than its classification

Archetypes, stored in an editable table and never branched on a school name:

| | top9 | gr9 | gr12 |
|---|---|---|---|
| untagged | 38.4 | 26.5 | 42.4 |
| blue_blood | 46.7 | **31.2** | 53.6 |
| development | 44.9 | 27.4 | 51.9 |
| doubles | 38.0 | 26.3 | 41.9 |

* **blue_blood** generates better and CLUSTERS — 70% of seats keep the better of two
  draws, which lifts the middle of a lineup far more than a flat mean shift. It shows on
  day one, and it beats a development programme on balance. That is what makes it one.
* **development** has ordinary freshmen and the best seniors: `mean` is 0, the gain is
  potential plus a maturity bonus starting at ZERO for ninth-graders and compounding by
  grade. It can beat a blue blood outright — the owner's point, *"that's the point,
  leveling the playing field"* — but it earns that over four years.
* **doubles** generates identically and wins doubles. Measured over 25 duals: singles
  **84-41 either way**, doubles 31-19 → 36-14.
* **upstart** is a temporary run, not a promotion — ~10 live statewide, expiring by
  itself, deliberately not storable.

Two corrections the measurements forced:

**Locality.** The upstart draw originally filtered tagged schools out of the POOL, so
tagging one school changed which OTHERS drew an upstart — `rng.sample` was sampling from
a different list. Tagged schools are now skipped at application. *A tag must only ever
affect the school it is on.*

**A wrong invariant of my own.** I wrote a test asserting a blue-blood 3A-1A must stay
under an ordinary 7A, "so the modifier doesn't flatten the classification model". That is
exactly the thing the talent model exists to allow. What actually needs pinning is that
the class ladder survives INSIDE each tag.

> When you write the test for a rule you just implemented, check whether you are pinning
> the rule or pinning your first guess at it.

## 4. Some freshmen arrive finished

~1 in 100 shows up with most of their ceiling already accessible. Deliberately NOT a
potential bonus — an ordinary 28-ceiling player arriving at 25 is as valid as a 75 arriving
at 67, and both occur. It is a maturity FLOOR that persists all four years, so they start
near their ceiling and barely grow: the early bloomer their classmates catch.

Rolled on its own rng stream, not the roster one. Drawing it from the main sequence would
shift every subsequent draw and regenerate every player in the association; keyed
separately, the only rosters that change are the ones that gain a prodigy.

## 5. And then the TOC was worth building

Same instrument, rerun after the rebalance — boys titles 22 / 30 / 18 / 22 / 8% by class.
A real tournament. So it shipped: `/jhsaa/toc`, its own bracket per gender, the five
champions **seeded on the TOSS Power Index rather than on classification**, the two
lowest-rated playing into a four-team semifinal.

The first archived running has the boys' 4A champion seeded No. 2 and winning it, and the
girls' 4A champion seeded No. 2 behind a 7A. Which is the entire point of the event, and
would have been impossible three commits earlier.

## Files

* `app/jhsaa.py` — `_TALENT`, `ARCHETYPES`, `_program_mod`, `upstarts`, `_doubles_lift`,
  `PRODIGY_RATE`, `run_toc`
* `app/overrides.py` — the editable archetype table
* `app/web/state.py`, `app/web/server.py`, `templates/jhsaa_toc.html`
* `tests/test_jhsaa_talent_shape.py`, `tests/test_jhsaa_archetypes.py`
