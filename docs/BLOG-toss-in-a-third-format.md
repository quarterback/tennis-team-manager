# TOSS in a third format: what a rating model has to know about the sport it rates

TOSS — the Tennis Opponent-Strength System — was built to rate Oregon high school
tennis programs on [oregontennis.org](https://oregontennis.org), off real match data,
for a format of four singles and four doubles.

It now runs in three places. The same model rates:

1. **Oregon high school tennis** — 4 singles / 4 doubles, real results.
2. **A college dual-match simulator** — 6 to 10 singles, 3 to 5 doubles depending on
   division, simulated results.
3. **A simulated high school association inside that simulator** — the JHSAA of
   Jefferson, a fictional 55th state: 5 singles / 2 doubles, ~627 programs a year.

Three formats, two of them invented, one of them real. The interesting part is how
little had to change, and — more usefully — exactly *where* the change had to happen.

## The model

```
Power Index = 0.40 × APR + 0.40 × FQI + 0.20 × oGS
```

| | Measures | Needs |
|---|---|---|
| **APR** | Strength of schedule. RPI — 25% own win %, 50% opponents', 25% opponents'-opponents' | who played whom, and who won |
| **FQI / FWS** | Depth. Flight-weighted share of lines won, scaled by opponent APR ÷ league median | which flight, and who won it |
| **oGS** | Margin. Share of games won, scaled by the same opponent multiplier | the games in each line |

Read the right-hand column again, because that is the whole argument. **Two of the three
components don't know what sport they're looking at.** APR needs a results graph. oGS
needs game counts. Neither has any opinion about how many singles courts a dual has.

Only FQI does. And its format knowledge is entirely contained in one table of numbers.

## The only thing that changed

Porting TOSS into a third format required exactly one code change: the function that
computes the flight score took a weight table as a parameter instead of reading a
module-level constant.

```python
def _flight_score(lines, side, weights=None):
    w_table = FLIGHT_WEIGHTS if weights is None else weights
```

That's it. One optional argument, defaulting to the existing behaviour so the league
already using it was untouched. Everything else — the iterated strength-of-schedule
pass, the opponent multipliers, the asymmetric loss weighting, the display
normalisation — ran unmodified on a format it had never seen.

## The three tables

| Flight | Oregon HS (4S/4D) | College engine default (6S/3D) | JHSAA (5S/2D) |
|---|---|---|---|
| Singles 1 | 1.00 | 1.00 | **1.00** |
| Singles 2 | 0.75 | 0.85 | **0.75** |
| Singles 3 | 0.25 | 0.60 | **0.25** |
| Singles 4 | 0.10 | 0.45 | **0.10** |
| Singles 5 | — | 0.30 | **0.10** |
| Singles 6 | — | 0.20 | — |
| Doubles 1 | 1.00 | 0.80 | **1.00** |
| Doubles 2 | 0.50 | 0.50 | **0.50** |
| Doubles 3 | 0.25 | 0.30 | — |
| Doubles 4 | 0.10 | — | — |
| **Max per dual** | **3.95** | — | **3.70** |

The JHSAA column is worth looking at closely: it is the Oregon table. Singles 1-4 carry
Oregon's exact weights, doubles 1 and 2 carry Oregon's exact weights, the two doubles
flights that don't exist in a 5S/2D dual were dropped, and the singles flight that
Oregon doesn't have was added at the tail. The max moves from 3.95 to 3.70 — down the
0.25 and 0.10 of the dropped doubles, up the 0.10 of the added single.

The college table is the odd one out, and deliberately so: it is flatter across singles
and it ranks #1 doubles *below* #1 singles, because a college dual has one consolidated
doubles point rather than three or four independent ones. Same model, different sport-
shaped judgement.

Call that heading "engine default" and not "the college table", because it turned out
not to be the college table at all — the four divisions each play their own dual, and
this one is only what a bare call falls back to. That is the next section, and it is the
more useful half of the story.

## Two properties that make it portable, and neither was designed for portability

**1. The denominator is contested weight, not maximum weight.**

```
FWS = Σ(weights of flights won) ÷ Σ(weights of flights contested)
```

That rule exists so a forfeit doesn't punish a team for a flight nobody played. But
dividing by what was *actually contested* is also precisely what lets one implementation
score a 7-point dual and an 11-point dual without knowing which it's holding. One
mechanism, two payoffs — the second one free.

**2. A missing component degrades to a coherent model, not to noise.**

The simulated high school league stored line scores as strings (`"6-4, 3-6, 7-5"`) and
never stored game counts. With no games, oGS is 0 for every team, and the composite
collapses to:

```
0.40 × APR + 0.40 × FQI     (+ 0.20 × 0)
```

Which is proportionally identical to the two-part model — `0.50 × APR + 0.50 × FWS`.
The three-part and two-part versions of TOSS are the same model with a component
switched off, so a league with no game data doesn't get a broken rating; it gets the
older, simpler one. (We ended up parsing the games back out of the score strings
anyway, which took eight lines and made the full model work on seasons that had already
been played and archived.)

## What it actually does to a bracket

The reason to do any of this is that win-loss is a bad seeding key, and the JHSAA was
using it. Here is a state field seeded on TOSS instead:

```
seed  school                    record   APR    FQI    oGS      PI
  1   Winifred Ellison           17-5   1.000  0.674  0.521   0.7737
  2   Gold Hollow                16-6   1.000  0.623  0.509   0.7511
  3   Marcus Mercer              12-8   0.901  0.583  0.488   0.6912
  4   Claudette Freeman          18-6   0.993  0.495  0.473   0.6898
```

Seed 3 is **12-8**. Seed 4 is **18-6**. A six-game gap in the record, and the 12-8 team
is rated higher — because its flight-quality index is 0.583 against 0.495. It lost more
duals, and won more of the flights that matter in the ones it played, against a
schedule that rated out slightly lower but not enough to cover the gap.

You can argue with that. That's the point: it's a *claim about the sport*, made
legible, rather than a tally.

## The default I left behind, and what it was quietly doing

There is a fourth format, and I had not noticed it.

"College sim (6S/3D)" in that table is a lie of omission. Six singles and three doubles
is the *engine's* default dual — what a bare call plays. The four divisions each play
their own shape, and have since a redesign a release earlier:

| | Singles | Doubles | Doubles points |
|---|---|---|---|
| D1 | 10 | 5 | all five consolidate into **one** team point |
| D2 / D3 | 8 | 3 | each doubles line is its own point |
| D4 | 10 | 3 | each doubles line is its own point |

So the rating was being handed courts — #7 through #10 singles, #4 and #5 doubles —
that its table had never heard of. It did not error, because of this:

```python
w = w_table.get(ln["slot"], 0.3)     # <- the problem
```

`_flight_score` took the weight table as a parameter — the change that made the port
work — and kept a fallback for anything the table didn't name. Two defaults, and they
are not the same kind of thing. `weights=None → FLIGHT_WEIGHTS` is a **compatibility**
default: it preserves the behaviour of the caller that already existed, and it is
correct. `.get(slot, 0.3)` is a **judgement** default: it answers "what is a #9 singles
court worth?" on behalf of someone who never considered the question.

What it answered was absurd. In a D1 dual:

* **26% of the total flight weight** — 1.80 of 6.80 — was that unchosen 0.30.
* #6 singles was deliberately weighted **0.20**. #7 through #10 each fell through to
  **0.30**. So a #10 singles court counted **one and a half times a #6**.
* The flight-quality index therefore ran **backwards across the bottom half of every D1
  lineup**: the deeper the court, the more it was worth.

Nothing failed. FQI stayed in range, the table looked plausible, the bracket seeded, the
season played. A rating model has no way to tell you it is measuring the wrong thing.

The fix is two lines and one table per format. There is no fallback any more — an
unrecognised flight raises, with a message naming the table it wasn't in. A missing
weight is a missing decision, and the caller should be stopped rather than served a
number nobody picked. The tables are the owner's, same as the JHSAA's.

## What devaluing depth actually did

Worth measuring rather than asserting. One season simulated in each of the eight
division × gender universes (seed 9100), advanced to the selection window, then the
**real** selection path run twice over the same results — old table with the fallback,
new per-division tables. Everything downstream is the shipped code: `compute_ratings`,
the committee seed score, `select_field`, the S-curve split.

| | rated | field | PI rank changed | mean Δ | max Δ | seed changed | ≥ 4 lines | region changed |
|---|---|---|---|---|---|---|---|---|
| D1 men | 383 | 96 | 353 (92%) | 5.2 | 24 | 59 (61%) | 19 | 51 (53%) |
| D1 women | 383 | 96 | 347 (91%) | 5.0 | 23 | 62 (65%) | 25 | 50 (52%) |
| D2 men | 324 | 64 | 265 (82%) | 2.5 | 10 | 30 (47%) | 1 | 21 (33%) |
| D2 women | 324 | 64 | 257 (79%) | 2.5 | 15 | 26 (41%) | 3 | 18 (28%) |
| D3 men | 233 | 64 | 150 (64%) | 1.1 | 5 | 32 (50%) | 5 | 27 (42%) |
| D3 women | 238 | 64 | 173 (73%) | 1.3 | 7 | 29 (45%) | 2 | 23 (36%) |
| D4 men | 191 | 64 | 161 (84%) | 2.0 | 10 | 36 (56%) | 5 | 29 (45%) |
| D4 women | 196 | 64 | 153 (78%) | 2.4 | 13 | 39 (61%) | 5 | 32 (50%) |

The size of the shift tracks **how much of each format the fallback was guessing at**,
which is the result you want if the diagnosis is right. D1 had four unweighted singles
courts and two unweighted doubles — the whole bottom half inverted — and moved most:
9 in 10 programs changed rank, by five places on average and by as much as 24. D2 and
D3 had only #7 and #8 singles falling through, and moved least. D4 sits between: ten
singles like D1, but its doubles were already weighted.

**The bubble barely moved, and the bracket moved a lot.** Across 576 field slots, seven
teams changed places:

| | in | out |
|---|---|---|
| D1 men | Johns Hopkins (seed 73) | Arizona State (was 78) |
| D1 women | Kentucky (73) | Johns Hopkins (was 78) |
| D2 men | Albany State (55) | Colorado Mesa (was 54) |
| D2 women | Maryville (55) | Rockhurst (was 55) |
| D3 men | TCNJ (53) | SUNY New Paltz (was 51) |
| D3 women | — | — |
| D4 men | Colorado College (58) | Emerson (was 59) |
| D4 women | Babson (53) | Bates (was 53) |

One swap per tournament, at the very last seed line, and D3 women's field did not change
at all. Meanwhile **313 of those 576 seats changed seed** and **251 changed region**.

That gap is the interesting part, and it is a property of the selection design rather
than of the rating. The committee score is 45% Power Index *rank*, 30% ITA résumé points,
15% automatic-bid pedigree, 10% recent form — so a five-place move inside a 383-team
table barely nudges a 0–100 rank score, and conference champions are in regardless. The
rating was wrong in a way that showed up almost entirely in **where teams were placed**,
not in **who got placed**. A model can be badly wrong and still pick nearly the right
field, because the field is mostly decided by things it doesn't touch.

Which is a good argument for measuring the seeds and not just the cutline. If I had only
checked who made the tournament, this would have read as a rounding error.

## The part that doesn't transfer

The weights. Every time TOSS moves to a new format, somebody has to decide what the
flights are worth in that format, and no amount of software design does that for you.
The JHSAA's numbers came from the person who built the original model, not from
interpolating the college table or rescaling Oregon's.

That's the honest boundary of the portability claim. The **machinery** is format-
agnostic and moved for one optional parameter. The **judgement** is not, and shouldn't
be — a #2 singles win is worth a different amount in a 4-court dual than in a 10-court
one, and that difference is the actual domain knowledge the model encodes.

And this is why the fallback had to go rather than get a better number. A default weight
is a way of pretending the judgement transferred when it didn't. The model now carries a
table for every dual it is asked to rate, and refuses to guess at one it isn't.

## Summary

- A rating model built for one real league now rates two invented ones — a
  627-program simulated high school association and a four-division college league whose
  divisions play four different duals, from 8+3 to 10+5.
- The port cost one optional function parameter. Everything else was tables.
- The portability came from two rules that were written for other reasons: score
  against contested weight, and let a missing component reduce to a simpler valid model.
- The same parameter that made it portable left a `0.30` default behind, which quietly
  became **26% of a D1 dual's flight weight** and made #10 singles count 1.5× a #6. Make
  the compatibility default; refuse the judgement default.
- Measure the shift, and measure the right thing: devaluing depth moved **9 in 10 D1
  programs** in the rankings and reseeded **61%** of the tournament field, while changing
  who was *in* that field by exactly one team. Checking only the cutline would have said
  nothing happened.
- The thing you can't port is the thing worth thinking about — what each flight is
  worth in the format in front of you.
