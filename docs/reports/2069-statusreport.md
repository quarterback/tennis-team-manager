# 2069 season review — the reform year, measured

**Scope.** All 24 classification-genders, 2069 JHSAA research exports. Match-level
analysis over ~155,000 flights. Written as the baseline for 2070, when 8A and 9A move
from the 1S/4D postseason format to 4S/5D.

**Why this season matters.** 2069 is the first year carrying both structural reforms at
once: the per-point gap-response curve and the Epiregional seeding round. Everything
below is the measurement of what those two changes actually did, and what state the
association is in going into a third change.

---

## 1. The gap-response curve: favorite-win exact, three-set model misspecified

The per-point slope array replaced the banded table for 2069. Validating the projections
made from 2068 data against what 2069 actually produced:

| gap | favorite win obs (B / G) | projected | error | three-set obs (B / G) | projected | error |
|---|---|---|---|---|---|---|
| 1 | 52.1 / 52.7% | 52.4% | −0.3 / +0.3 | 49.2 / 49.2% | 47.0% | **+2.2** |
| 3 | 59.1 / 58.1% | 55.8% | +3.3 / +2.3 | 47.2 / 48.9% | 44.2% | **+3.0 / +4.7** |
| 5 | 63.1 / 62.8% | 64.2% | −1.1 / −1.4 | 47.4 / 47.9% | 39.0% | **+8.4 / +8.9** |
| 8 | 73.4 / 73.9% | 73.4% | +0.0 / +0.5 | 42.2 / 42.3% | 33.7% | **+8.5 / +8.6** |
| 10 | 79.3 / 79.4% | 78.1% | +1.2 / +1.3 | 39.4 / 37.9% | 31.3% | **+8.1 / +6.6** |
| 12 | 84.3 / 83.5% | 85.7% | −1.4 / −2.2 | 34.5 / 34.4% | 28.1% | +6.4 / +6.3 |
| 15 | 88.9 / 89.4% | 89.8% | −0.9 / −0.4 | 29.9 / 29.5% | 24.9% | +5.0 / +4.6 |
| 18 | 94.2 / 95.2% | 95.0% | −0.8 / +0.2 | 22.0 / 20.2% | 20.0% | +2.0 / +0.2 |
| 21 | 97.9 / 96.5% | 97.1% | +0.8 / −0.6 | 13.0 / 16.3% | 19.5% | −6.5 / −3.2 |

**Favorite-win: the array is correct.** Median absolute error 0.9 points across 18
gap-gender observations, maximum 3.3. Gap 8 landed on 73.4% against 73.4% projected.
The curve does what it was specified to do and needs no further tuning.

**‼️ Three-set frequency does not scale the way the projection assumed.** The error is
not noise — it is a clean inverted-U centred on gaps 5–10 at roughly **+8.5 points**,
falling to near zero at both tails and going negative above 21. The projection modelled
three-set frequency as an inverse power law on cumulative separation. It is not that.

The finding underneath: **at small and mid gaps, raising win probability does not
proportionally shorten matches.** The better player converts more often and still needs
a third set to do it. Match length and match outcome only couple tightly above roughly
18 points of separation.

This matters at volume. Gaps 5–10 carry ~20,000 flights per gender per season — the
most common competitive band in the association. 2069 produced meaningfully more
three-setters there than forecast. Nothing is broken; the forecast model was wrong, not
the engine.

**For anyone re-fitting this later:** do not carry the power-law assumption forward. Fit
three-set frequency separately from favorite-win, and expect it to be flat-ish through
the mid-single digits.

## 2. The Epiregional: the seeding fault is closed

2068 baseline: seed 8 went to a team ranked 19th–27th in its class in **20 of 24
fields**, because a Zonal title bought a top-eight line regardless of merit. The girls
8A No. 1-ranked team was seeded 12th; the champion was seeded 31st.

2069, after the Epiregional round and merit byes:

| | boys | girls |
|---|---|---|
| overall mean \|seed − rank-order\| | **2.02** | **2.01** |
| worst class | 8A (2.8) | Group 1 (3.2) |
| best class | 7A, Group 3 (1.2) | 1A (1.1) |

Against a 2068 range of 3.5–5.1 in the worst classes. The two genders agree to two
decimal places, which is what a mechanism operating identically on both should produce.

The seed-8 pathology is substantially resolved. Its rank-order distribution across the
24 fields now runs 4, 7, 7, 7, 7, 8, 8, 9, 9, 10, 10, 10, 10, 11, 13, 14, 17, 17, 21, 25
— median 9.5, against a 2068 median in the low twenties. Residual divergence
concentrates in the 40-team classes and Group 1, which is expected: more seed lines,
more room to mis-sort.

**The floor-protection mechanism visibly worked.** Weller Independent won 3A girls from
seed 8 while ranked 17th — a Zonal champion who would not have rated a top-eight line on
merit, converting the guaranteed line into a state title. That is the Epiregional
functioning as designed, not a seeding failure.

## 3. Postseason outcomes: chalk restored, one survivor

| | 2067 | 2068 | 2069 |
|---|---|---|---|
| champions seeded 10th or worse | 9 / 24 | 3 / 24 | **1 / 24** |
| champions seeded top-4 | — | — | **17 / 24** |
| median champion seed | — | B 3 / G 7 | **2** |

**Boys are now near-deterministic**: zero champions seeded 10th or worse, five No. 1
seeds, median seed 2, and Jesuit finished 36-0 in 9A. Every boys champion but one was
seeded 5th or better.

**Girls retain real variance**: median champion seed 4, and **Cottonrock Point won 4A
from the 15 seed at 23-14** — a .621 team taking a state title, and the only double-digit
seed to win anything in either gender.

The three-season arc is monotone: seeding uncorrelated with strength and 37.5% of titles
to double-digit seeds (2067) → curve steepened, seeding still broken (2068) → both
reforms live, chalk near-total on the boys side (2069).

**The association bought accuracy and sold variance.** That was the intent and the
mechanisms delivered. The open judgement for the board: the girls distribution — median
seed 4, one genuine outsider champion — looks like a healthier competitive spread than
the boys distribution at median seed 2 with nothing above 9. If a correction is ever
wanted, it does not belong in the curve, whose favorite-win numbers are correct. It
belongs in seeding, where 2.0 mean divergence may be *more* accurate than a sport wants.

## 4. Talent luck: residual variance is now noise

Fitting an empirical win curve from 2069's own flights and pricing every program against
the separation each of its flights was actually contested at:

- dispersion of talent luck: **sd = 0.035 (boys) / 0.033 (girls) per flight**
- extremes: **+23.4** (Jefferson Science, 9A) to **−21.8** (St. Sebastian Prep, 3A) flights
  against expectation over a season
- n = 875 boys programs, 912 girls programs

Across ~180 flights a season, one sigma is about ±6 flights and the extremes sit at
roughly ±3.4σ — the shape of a normal over 875 draws.

**There is essentially no systematic overperformance left in this association.** Talent
luck has become noise around zero rather than a signal, which is the expected end state
once outcomes track the one number the engine reads. Pre-reform, programs routinely won
flights their rosters had no business winning.

One case worth the note: Jefferson Science ran **+23.4 flights over expectation and still
lost the 9A final** to a 36-0 Jesuit. The most overperforming roster in the state could
not overcome the best roster in the state. That is the clearest single illustration of
what the curve changed.

## 5. Flight leverage: no weak link in 1S/4D

Share of each flight's matches played inside a one-point dual:

| flight | matches (boys) | share in 1-point duals |
|---|---|---|
| S1 | 12,399 | 42.7% |
| D1 | 12,399 | 42.7% |
| D2 | 12,399 | 42.7% |
| D3 | 11,456 | 42.5% |
| D4 | 11,319 | 42.4% |
| S2 | 9,934 | 42.1% |
| S3 | 9,797 | 41.9% |
| S4 / S5 (1A pilot) | 943 | 44.9% |

**Every flight sits inside a 0.8-point band.** No position is systematically more or less
pivotal than any other — there is no throwaway flight and none that decides
disproportionately. The S4/S5 lines from the 1A 2S/3D pilot run slightly hotter, which is
consistent with a shorter format concentrating leverage.

Dual margin distribution (both genders, near-identical):

| margin | share |
|---|---|
| 1 | 42.7% |
| 3 | 33.2% |
| 5 | 19.0% |
| 7 | 5.1% |

**42.7% of duals are still decided by a single flight.** Team-level closeness survived
the curve change intact, because a dual aggregates seven flights and most are contested
between near-peers. The change was surgical: individual matches became more decisive,
team results did not.

## 6. Roster construction — and the finding that bears on 2070

Regressing dual win rate on roster shape, 875 boys / 912 girls programs:

| predictor | boys r | girls r |
|---|---|---|
| top-11 mean OVR | **+0.587** | **+0.592** |
| top player OVR | +0.536 | +0.552 |
| depth (7th–11th mean) | +0.487 | +0.481 |
| internal spread (1st − 11th) | +0.274 | +0.321 |

Team quality outpredicts star quality in both genders. The design premise holds.

**‼️ The within-class result is the one that matters for the 2070 change.** Correlation
of internal spread with win rate, by classification:

| class | boys | girls |
|---|---|---|
| 9A | +0.244 | +0.432 |
| 8A | +0.210 | +0.187 |
| 5A | +0.277 | +0.396 |
| 3A | +0.452 | +0.439 |
| 1A | **+0.496** | **+0.538** |

Spread is positively correlated with winning everywhere, but the effect roughly **doubles
from 8A to 1A**. In the small classes, one dominant player over a weak tail is a winning
build. In 8A/9A it barely helps.

The mechanism is opponent depth. In 1A your best player beats everyone and your tail is
rarely punished, because opposing tails are equally thin. In 8A/9A the field is deep
enough that a weak tail is exposed in every dual.

**This is the strongest empirical support for the two-format association.** The classes
moving to 4S/5D are precisely the ones where balance already pays and top-heaviness
already does not; the change pushes further along a gradient they are already on. The
classes keeping 1S/4D are the ones where a single star remains the optimal build. Matching
format to the competitive reality of each tier is what the data says the association is
doing, rather than imposing one shape on two different environments.

## 7. What to measure in 2070

The 8A/9A move to 4S/5D is the only change, so its effects are cleanly separable from
the 2069 baseline above.

- **Depth vs top-end correlation, 8A/9A only.** Backtesting on 2064–68 rosters projected
  depth correlation rising from +0.561 to +0.683 and top-player correlation *falling*
  from +0.586 to +0.465. If top-player correlation does not fall, the singles expansion
  is concentrating power rather than distributing it and the premise needs revisiting.
- **Within-class spread correlation in 8A/9A.** Currently +0.210 / +0.244 (boys) and
  +0.187 / +0.432 (girls). It should fall toward or below zero. That is the direct test
  of whether the format changed how a program is best built.
- **One-point dual rate in 8A/9A against the 42.7% association baseline.** Nine flights
  instead of five should reduce it. A collapse below ~30% means the format traded away
  more closeness than intended.
- **Flight leverage across the new S4 and D5 positions.** Under 1S/4D every flight sat
  within 0.8 points of 42.7%. If the new flights come in materially lower, they are
  decorative rather than competitive.
- **Preparation of the players the new format dresses.** 4S/5D uses 14 where the league
  format uses 11. The varsity-only export cannot answer this: it filters to `level='v'`,
  so bottom-of-lineup players read as having no matches when they have full JV seasons
  and, since 2068, a JV state tournament. **Any preparation analysis needs JV data, not
  the varsity export.** An earlier pass produced a "15% of state participants are
  unprepared" figure from varsity appearances alone; that number is wrong and should not
  be cited.
- **TOC reversion.** 8A/9A champions arrive at the Tournament of Champions on 1S/4D,
  having played 4S/5D all season. 1S/4D is a subset — the doubles lineup is unchanged and
  three singles positions drop out — so the friction is real but bounded. Worth checking
  whether 8A/9A TOC results decline relative to their pre-2070 baseline.
