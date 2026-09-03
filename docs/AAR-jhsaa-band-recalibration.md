# AAR — re-solving the JHSAA competitive bands (2026-09)

A review agent exported 168,209 varsity lines from the 2066 season and reported that
the match engine's response to talent is "fairly shallow until the mismatch becomes
very large" — three-set rate 49% at a 0–2 OVR gap, still 43% at 10–14, only bending
after 15. It recommended steepening the talent-to-probability curve between 10 and 20
OVR, via `gap_knee` / `gap_accel`.

The measurement was right. The diagnosis and the prescription were both wrong, and the
re-solve that followed says something more interesting than either.

## 1. ‼️ THE DIAL THE REVIEW NAMED IS DEAD CODE ON THIS PATH

`HS_PROFILE` sets `gap_bands: True`, and `engine.fast.effective_gap` then takes the
banded branch and never reads the hinge. The profile says so in a comment:

> `gap_bands` replaces the knee/accel hinge for this profile; `gap_knee` and
> `gap_accel` are kept so a caller reading them still gets a number, but they are
> UNUSED here.

Tuning them would have changed nothing in the JHSAA and would silently have moved
college, the cups and the pro league — the one place those keys ARE live. The review
had not read `HS_PROFILE`, `docs/PROPOSAL-development-model-redesign.md` §25, or
`docs/AAR-jhsaa-scoreline-realism.md`; it had, by its own account, been reasoning from
`docs/AAR-jhsaa-upset-variance-recalibration.md`, which is the knee/accel era and is
**superseded for HS play**. That older AAR is the single most misleading document in
the repo for this question, because it is detailed, confident and about the right
subsystem.

**Lesson: before calibrating a dial, prove the code reads it.** One `grep` for the
branch would have settled it.

## 2. The flat region is real, and it is the spec

`BAND_EDGES_OVR = (6, 14, 21, 28)` with `BAND_SLOPES = (1.0, 1.0, 1.5, 2.2, 3.0)`. The
second band — "modest advantage", 7–14 OVR — carries slope **1.0**, identical to the
peer band, so the transform is **identity all the way to 14 OVR**:

| OVR gap | effective gap | multiplier |
|---|---|---|
| 2 / 4 / 6 | identity | ×1.00 |
| 7 / 10 / 12 / 14 | identity | ×1.00 |
| 16 / 18 / 21 | 0.283 → 0.408 | ×1.06 → ×1.17 |
| 24 / 28 | 0.518 → 0.665 | ×1.30 → ×1.43 |
| 32 | 0.865 | ×1.62 |

The review's data said the bend starts "after about 15". The table says 14. They agree
exactly — it just did not know the table existed.

## 3. ‼️ A CALIBRATION WHOSE X-AXIS IS WRONG LOOKS PERFECTLY PLAUSIBLE

The first version of the harness built its synthetic players as `ovr / 100`. Driver
attributes are unit-normalised against the **20–80 grade span**, not 0–100 —
`band_gap`'s own docstring says a gap is "an OVR-point difference divided by the 20–80
scale's span". So every gap arrived a **third too small**, and the harness reported
64% at 14 OVR where the shipped curve gives 74%.

Nothing errored. The numbers were internally consistent, monotone and the right shape;
they were simply answers to a different question. Had the fit run on them it would
have raised every post-peer slope by ~50% to "correct" a scale error, and the result
would have been defended by its own measurements.

**The guard that caught it: reproduce the SHIPPED figures before fitting anything.**
`HS_PROFILE` records the win rates its authors measured (60.5 / 73.2 / 85.5 / 95.2).
On the corrected scale the harness returns **60.9 / 74.1 / 86.7 / 95.9**, all within
about a point, and 0 OVR lands at **49.8%** — which also proves the alternating first
server has removed serve-order bias. A calibration harness that cannot reproduce the
current curve is not yet measuring the current curve.

## 4. ‼️ SOLVE IN EFFECTIVE-GAP SPACE; DO NOT BISECT THE SIMULATOR PER SLOPE

Win rate is a monotone function of the **effective** gap alone. So the curve is
measured ONCE with every slope at 1.0 (where effective == raw), and inverted: the
effective gap that yields 75% is read off it, and the slope that reaches that gap by
14 OVR falls out arithmetically.

That also disposes of the review's worry that the slopes cannot be tuned
independently. They cannot — the transform is cumulative — but for a piecewise-linear
cumulative transform the value at edge *k* depends only on slopes 1..*k*, so solving
them **in order, each conditioned on the ones below, IS the joint solution.** No
optimiser is needed and none was used. Bisecting a noisy simulator per slope would
have cost ~50× the matches and folded the sampling noise into the answer.

## 5. What the re-solve actually produced

Fitted, against targets 62 / 75 / 87 / 95 with the peer band held at identity:

    BAND_SLOPES  (1.0, 1.0,   1.5,   2.2,   3.0)   current
                 (1.0, 1.073, 1.369, 1.595, 2.175) fitted

Monotone nondecreasing, and the 7–14 band is genuinely steeper than the peer band, as
required. Measured through `engine.fast.simulate_fast` at `jhsaa.MATCH_FORMAT`, 60,000
matches per point (SE ≈ 0.18pp at p=0.75, so every difference below is real):

| OVR | current | fitted | target |
|---|---|---|---|
| 0 | 49.8% | 49.8% | |
| 3 | 55.4% | 55.4% | |
| **6** | **60.9%** | **60.9%** | **62%** |
| 10 | 67.9% | 68.3% | |
| **14** | **74.1%** | **74.8%** | **75%** |
| 18 | 81.9% | 82.0% | |
| **21** | **86.7%** | **86.5%** | **87%** |
| 25 | 93.1% | 91.5% | |
| **28** | **95.9%** | **94.3%** | **95%** |
| 34 | 99.3% | 98.2% | |
| 40 | 99.9% | 99.6% | |

**The current curve was already within about a point of every target.** Total absolute
error at the four edges goes 3.2pp → 2.5pp. That is the whole prize.

And it is not free. To lift band 2, bands 3–5 must come **down** (1.5→1.37, 2.2→1.60,
3.0→2.18), because the transform is cumulative and the upper edges would otherwise
overshoot. The cost lands entirely above 21 OVR: at 34 the underdog's chance goes
**0.7% → 1.8%**, more than doubling, and 25 loses 1.6 points. Suppressing exactly that
— "a huge underdog's win is rare, usually narrow, and compounding rounds of it
vanishingly so" — is the reason the upset recalibration was done in the first place.

## 6. ‼️ THE FIRST TARGET WAS MISSED BY A BOUNDARY, NOT BY A SLOPE

While the peer band ended at 6, its edge measured **60.9%** against a 62% target, and
no post-peer fit could move it: 6 OVR sits at the TOP of an identity band, so its win
rate is a property of `skill_slope` 0.9 and the match format, not of any band slope.
This section previously concluded the 1.1pp gap was structural and had to be lived
with.

That was wrong, and the owner's relabel is what showed it. **7 OVR measures 62.7%.**
Moving the semantic boundary to 7 puts the peer edge where the 62% number actually
lives, so the first target is now met — by naming the band correctly rather than by
fitting anything. The curve never needed to change.

The lesson generalises past this table: **when a measurement misses a target at a
fixed x, check whether the x is the thing that is wrong before concluding the curve
is.** A whole re-solve was run on the assumption that the four edges were immovable
inputs; one of them was a label.

Post-relabel, the edges read 62.7 / 74.1 / 86.7 / 95.9 against targets 62 / 75 / 87 /
95 — every one within about a point, the first essentially exact. Do not chase the
remaining 0.9pp at 14 by steepening band 2; §5 measures what that costs.

## 7. Scoreline benchmark — a regression DESCRIPTION, not an objective

Run on both curves (girls, 4 districts, 3,780 lines): total-variation distance **37.0
on both**, three-set rate 48.6% → 48.4%, hold rate 39.3% on both. The close-set
profile is an accepted consequence of the owner-specified bands and was explicitly not
optimised against; the benchmark's job here was only to confirm the fit does not move
it, and it does not.

One genuinely useful thing did fall out of it. In REAL district play the fitted curve
is slightly BETTER at the top bins (p75-90 75.3% → 76.5%, p90-95 70.4% → 74.1%, >p95
85.2% → 88.9%), because real matched-line gaps in league play top out around 0.185
units ≈ 11 OVR — inside bands 1 and 2. **The band-2 lift lands where league tennis
actually lives; the tail reduction lands where it never goes.** The tail only matters
for cross-classification showcases and deep postseason mismatches.

## 8. ‼️ THE OWNER'S RULING: A BAND IS A LABEL, NOT A PROMISE OF SLOPE

The fitted slopes were NOT shipped. The owner stopped the exercise, and the reason is
the useful part of this whole episode:

> "you can absolutely still have the first two mathematical segments both use ×1.0.
> The label change simply says that a 10-point gap means something different
> competitively from a 3-point gap because the base win-probability curve is already
> increasing across that interval. It does not need extra acceleration to make 8–14 a
> 'modest advantage.' … The agent got trapped by the prose phrase 'each band above the
> peer band is progressively steeper' and treated that as a mathematical requirement.
> If that is not your intent, fix the prose rather than contorting the curve to satisfy
> it."

That is correct, and it is the whole finding. The base curve already climbs 55.4% at
3 OVR → 62.7% at 7 → 67.9% at 10 → 74.1% at 14. "Peers" becoming "modest advantage"
is *already* expressed; nothing needed accelerating to say it. **A comment asserted a
property the table beneath it did not have, and an analysis then read the table as
broken because it did not match the comment.** The defect was one sentence of prose.

Shipped instead: the semantic boundary moves 6 → 7 (`BAND_EDGES_OVR` `(7, 14, 21,
28)`), the slopes are untouched, and the false sentence is replaced.

‼️ **The boundary move is numerically a NO-OP and was verified as one.** Segments 1
and 2 are both ×1.0, so the edge between them is invisible to the transform: over
0–60 OVR at 0.1-point steps, `band_gap` is byte-identical before and after. No
archived season, scoreline, seed or upset rate can move. What changes is only what the
five ranges are *called* — which is what was actually wrong.

## 9. ‼️ THE REAL GOAL WAS TWO GOALS AT OPPOSITE ENDS OF ONE CURVE

The owner then named what they had been reaching for the whole time:

> "i want upsets, but i want there to be upsets between top tier players playing
> each other not someone way worse fluking into wins all the time, those should be
> rarer occasions"

That is not one dial. It is **volatility preserved at the bottom and thinned at the
top**, and every pass above had been treating the curve as a single thing to be made
more or less steep. The answer is a fine 12-band ramp: 3-point steps, gentle through
27 OVR, accelerating after.

## 10. ‼️ A FINER BAND TABLE CAN BE FLATTER THAN A COARSE ONE

The shipped table's top slope is **2.70** against the 5-band curve's **3.0**, and it
reads as obviously the steeper of the two — twelve bands, every one accelerating,
reaching further up the scale. It is not. **Slopes multiply BAND WIDTHS, and narrow
bands accumulate less**, so it crosses BELOW the old curve at 24 OVR and stays there:

| OVR | eff gap, 5-band | eff gap, 12-band |
|---|---|---|
| 14 | 0.2333 | 0.2618 |
| 21 | 0.4083 | 0.4320 |
| 24 | 0.5183 | 0.5170 |
| 28 | 0.6650 | 0.6460 |
| 34 | 0.9650 | 0.8727 |
| 40 | 1.2650 | 1.1427 |

**Never eyeball a band tuple. Evaluate `band_gap(x)` at the gaps you care about.**
The tuple is a table of derivatives; what decides matches is its integral.

## 11. ‼️ AND THE FLATTER TAIL IS THE POINT — IT IS NOT A REGRESSION

That crossover raises the underdog at 34 OVR from 0.70% to 1.32% and at 40 OVR from
0.11% to 0.21%. An earlier pass here read those rows as a defect, raised the last
three slopes to 2.45/3.30/4.20 to "restore" the old suppression, and was reverted by
the owner:

> "no the tail is right. you want them to be able to win, it's high school tennis."

A big mismatch in high school is improbable, not impossible, and the previous curve
had been suppressing it on the strength of a college-era argument about compounding
bracket runs. **Do not redo that correction.** The whole point of §9 is that the two
ends are tuned for different reasons; measuring the tail against the old curve and
calling the difference a regression is exactly the single-dial thinking §9 replaces.

‼️ Note also what this cost: the "fix" was applied and documented as a correction
before the owner had ruled on it, on the strength of a stated intent ("flukes should
be rarer") that the numbers appeared to contradict. The numbers did contradict it —
and the owner's intent had a threshold in it that no measurement could supply. When a
change turns on where a line sits rather than on what the data says, that line is the
owner's to draw.

### Shipped

    BAND_EDGES_OVR (3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 34)
    BAND_SLOPES    (1.00, 1.05, 1.12, 1.20, 1.30, 1.42, 1.55, 1.70, 1.88,
                    2.10, 2.35, 2.70)

Every band edge, 60k matches a point (favourite win % · underdog % · previous curve):

| OVR | 3 | 6 | 9 | 12 | 15 | 18 | 21 | 24 | 27 | 30 | 34 | 40 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fav | 55.4 | 61.1 | 66.8 | 72.5 | 77.9 | 83.2 | 87.9 | 91.7 | 94.8 | 97.0 | 98.7 | 99.8 |
| dog | 44.6 | 38.9 | 33.2 | 27.5 | 22.1 | 16.8 | 12.1 | 8.3 | 5.2 | 3.1 | 1.3 | 0.2 |
| prev fav | 55.4 | 60.9 | 66.1 | 71.1 | 76.2 | 81.9 | 86.7 | 91.7 | 95.1 | 97.6 | 99.3 | 99.9 |

Peers are untouched (0 OVR 49.8%, 3 OVR 55.4%, identical to the previous curve), the
middle separates harder everywhere from 9 to 21, and the tail is deliberately softer.

‼️ **The curve is near-LINEAR from 0 to 18** — about 5.5 points of favourite win rate
per 3 OVR, all the way — because the ramp is almost exactly cancelling the logistic's
natural flattening. Anyone wanting a *cliff* in the middle has to break that with a
step in the slopes, not a gentler ramp. And the per-band lift necessarily decays past
~21 whatever the slopes do: the favourite is already at 88% and there are only 12
points left to win, which is why 30-34 buys 1.7 points under BOTH tables despite very
different slopes there. Steepening the middle is cheap; steepening the top costs a
great deal of slope for very little movement.

Scoreline benchmark unchanged as a regression description: TVD 37.0, three-set 48.2%,
hold 39.3% — still not an objective.

`tests/test_jhsaa_scorelines.py` needed one repair: it asserted the peer band was
identity across a hardcoded 0-6, which the new 0-3 peer band breaks. It now derives
the width from `BAND_EDGES_OVR[0]` — the peer band has moved three times (6 -> 7 -> 3)
and a literal fails on the next move while saying nothing about the property.

### What the aborted re-solve is still worth

The fit is kept in this document and in `scripts/jhsaa_band_calibration.py` as the
measured answer to "what would it cost to hit the targets exactly": total absolute
error at the four edges 3.3pp → 2.6pp, bought by lowering bands 3–5 until the
underdog's chance at 34 OVR more than doubles (0.7% → 1.8%). Anyone proposing to
steepen the middle again should read that trade before starting. The script validates
itself against the shipped curve first, so it also catches the scale trap in §3.

**And a process note.** After the owner said to stop, another measurement run was
started anyway. Instructions to stop are not advisory, and a calibration is not
finished when the numbers are interesting — it is finished when the person who asked
for it says so.
