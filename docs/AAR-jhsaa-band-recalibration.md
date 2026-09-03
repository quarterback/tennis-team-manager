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

## 6. ‼️ THE 6-OVR MISS IS STRUCTURAL AND CANNOT BE FITTED AWAY

6 OVR sits at the TOP of the peer band, which is identity by owner rule. Its 60.9% is
therefore a property of `skill_slope` 0.9 and the match format, not of any band slope
— no post-peer fit can move it, and the 1.1pp gap to the 62% target is the price of
the peer band being identity. Worth stating so a future pass does not chase it by
steepening band 2 (which would overshoot 14 to reach a number it cannot touch).

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

## 8. Verdict

The engine is behaving as specified. The re-solve is valid and satisfies every stated
constraint, but it trades ~0.7pp of aggregate target accuracy for materially more
upset at 25–40 OVR, and the owner has no target up there to justify the trade. Filed
with the fitted numbers so the decision is on the record either way;
`scripts/jhsaa_band_calibration.py` reproduces all of it and should be re-run before
any future retune, since it validates itself against the shipped curve first.
