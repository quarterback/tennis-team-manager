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

| Flight | Oregon HS (4S/4D) | College sim (6S/3D) | JHSAA (5S/2D) |
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

## The part that doesn't transfer

The weights. Every time TOSS moves to a new format, somebody has to decide what the
flights are worth in that format, and no amount of software design does that for you.
The JHSAA's numbers came from the person who built the original model, not from
interpolating the college table or rescaling Oregon's.

That's the honest boundary of the portability claim. The **machinery** is format-
agnostic and moved for one optional parameter. The **judgement** is not, and shouldn't
be — a #2 singles win is worth a different amount in a 4-court dual than in a 10-court
one, and that difference is the actual domain knowledge the model encodes.

## Summary

- A rating model built for one real league now rates two invented ones, including a
  simulated 627-program high school association.
- The port cost one optional function parameter and one table of seven numbers.
- The portability came from two rules that were written for other reasons: score
  against contested weight, and let a missing component reduce to a simpler valid model.
- The thing you can't port is the thing worth thinking about — what each flight is
  worth in the format in front of you.
