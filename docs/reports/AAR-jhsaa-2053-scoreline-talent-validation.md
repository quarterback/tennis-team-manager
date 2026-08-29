# JHSAA 2053 Scoreline Validation: Talent Architecture and High-School Realism

**Data source:** `play-to-clinch-jhsaa-2053-both.zip`  
**Season:** 2053  
**Scope:** JHSAA boys and girls, standard best-of-three lines unless otherwise noted

## Summary

The 2053 high-school scoreline profile is internally coherent. The higher 6–0 rate is not a calibration miss against Oregon. It is the scoreboard expression of Jefferson's deliberately wider talent architecture: a much larger association, many more competitive classes, stronger top-end juniors, and deeper roster tails than a normal real-world state association.

Oregon is useful as a guidepost because it demonstrates that high-school tennis is blowout-shaped. It is not the target distribution for Jefferson. Jefferson's player pool is much larger and less talent-compressed, so it should produce more bagels when mismatches occur. If Jefferson's talent distribution were compressed toward Oregon's likely range, the bagel rate would come down because fewer lines would land in the high-gap bands that now produce most 6–0 sets.

The core validation result is simple: the model now preserves close-match behavior while allowing large talent gaps to produce large score gaps.

## Association scale

| Side | Programs | Championship classes | Players |
| --- | --- | --- | --- |
| Boys | 914 | 12 | 18335 |
| Girls | 955 | 12 | 19353 |
| Total | 1869 | 24 | 37688 |

Jefferson is not a normal state-sized tennis population. It has 1,869 total programs across 24 boys/girls championship classes, with 37,688 rostered players in the 2053 export. That size creates a talent distribution Oregon cannot be expected to match.

## Roster talent spread

Current-grade spread is measured as the best rostered player minus the weakest rostered player on the same program.

| Side | Median spread | 75th pct | 90th pct | Max | Mean |
| --- | --- | --- | --- | --- | --- |
| Boys | 44 | 48 | 51 | 57 | 43.6 |
| Girls | 42 | 46 | 49 | 56 | 41.2 |

The median boys program carries a 44-point top-to-bottom current-grade gap. The median girls program carries a 42-point gap. That is the main structural reason Jefferson produces more 6–0 sets. A typical roster can contain a legitimate high-end player and a near-beginner in the same program.

## Top-end and bottom-end coexistence

| Side | Programs with 70+ CUR | Programs with 75+ CUR | Programs with ≤25 CUR | Programs with ≤20 CUR | Players with 75+ POT | Programs with 75+ POT |
| --- | --- | --- | --- | --- | --- | --- |
| Boys | 264 | 30 | 803 | 480 | 3312 | 846 |
| Girls | 155 | 16 | 873 | 537 | 2123 | 761 |

This is the key roster fact. Hundreds of Jefferson programs have high-end current players, while most programs also carry very weak roster bottoms. The association is not merely larger than Oregon; it is designed with a much wider internal skill range.

## Whole-association scoreline profile

Oregon's real match data is included here only as a benchmark. It is not the target. The useful comparison is that the close-match rates now sit in a plausible high-school range, while Jefferson's larger talent spread generates more 6–0 sets.

| Side | Best-of-3 lines | Sets | Three-set rate | 6–0 sets | 7–6 sets | Distance from Oregon |
| --- | --- | --- | --- | --- | --- | --- |
| Boys | 79698 | 170002 | 13.3% | 37.2% | 4.3% | 11.3 |
| Girls | 85730 | 183263 | 13.8% | 36.2% | 4.4% | 10.3 |
| Combined | 165428 | 353265 | 13.5% | 36.7% | 4.4% | 10.8 |

The old problem was fake parity: too many close sets, too many tiebreaks, and too many three-setters in matches where the player-quality gap should have mattered. The 2053 model does not show that problem. The close end of the distribution is stable: three-set rates and tiebreak rates are near the Oregon guidepost. The difference is at the mismatch end.

## Bagels follow the rating gap

Rating gap is the absolute current-grade difference between singles opponents, or the absolute difference between average pair current-grade for doubles.

### Boys

| Rating gap | Sets | 6–0 rate | Share of all 6–0 sets |
| --- | --- | --- | --- |
| 0–2 | 34190 | 5.9% | 3.2% |
| 2–5 | 50555 | 14.8% | 11.8% |
| 5–8 | 35851 | 40.5% | 23.0% |
| 8–12 | 27440 | 69.9% | 30.3% |
| 12–16 | 13114 | 87.9% | 18.2% |
| 16–25 | 8056 | 96.0% | 12.2% |
| 25+ | 796 | 99.9% | 1.3% |

### Girls

| Rating gap | Sets | 6–0 rate | Share of all 6–0 sets |
| --- | --- | --- | --- |
| 0–2 | 37686 | 5.7% | 3.2% |
| 2–5 | 56031 | 14.9% | 12.6% |
| 5–8 | 37664 | 40.0% | 22.7% |
| 8–12 | 29789 | 69.1% | 31.0% |
| 12–16 | 13523 | 87.7% | 17.9% |
| 16–25 | 7998 | 96.4% | 11.6% |
| 25+ | 572 | 99.5% | 0.9% |

This is the strongest validation result. The 6–0 rate is not randomly smeared across the association. It rises sharply with rating gap.

For boys, gaps of 5+ rating points account for 85.0% of all 6–0 sets. For girls, gaps of 5+ account for 84.2% of all 6–0 sets. The model is not inventing blowouts in even matches; it is converting mismatches into blowouts.

## S1 cliff check

S1 is the cleanest single-player test because it avoids doubles-pair averaging and lineup-depth noise.

### Boys S1

| S1 rating gap | Sets | 6–0 rate |
| --- | --- | --- |
| 0–4 | 13284 | 6.1% |
| 5–14 | 11362 | 44.4% |
| 15–24 | 1242 | 94.1% |
| 25–34 | 50 | 100.0% |

### Girls S1

| S1 rating gap | Sets | 6–0 rate |
| --- | --- | --- |
| 0–4 | 12530 | 6.3% |
| 5–14 | 12969 | 45.5% |
| 15–24 | 2028 | 93.2% |
| 25–34 | 92 | 98.9% |

The S1 curve is mechanically clean. Even S1 matches rarely bagel. Once the gap crosses 15 points, bagels become nearly automatic. That is the intended behavior for an association with extreme top-end talent and weak lower-end opposition. A 15–24 point gap is not a modest edge; it is a fundamentally different level of player.

## Phase and format effects

The export includes 8-game pro-set showcase lines. Those are excluded from standard set-distribution tables because they do not produce 6-x standard-set scores. The showcase rows below cover standard best-of-three showcase lines only.

| Side | Phase | Best-of-3 lines | Sets | Avg gap | Median gap | Line had 6–0 set | Three-set rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Boys | Early | 6930 | 15116 | 4.8 | 4.0 | 39.6% | 18.1% |
| Boys | Regular | 62223 | 132296 | 6.5 | 5.0 | 54.0% | 12.6% |
| Boys | Postseason | 8745 | 18821 | 4.9 | 4.0 | 47.0% | 15.2% |
| Boys | Showcase | 1800 | 3769 | 7.3 | 6.0 | 61.7% | 9.4% |
| Girls | Early | 7434 | 16212 | 4.9 | 4.0 | 40.3% | 18.1% |
| Girls | Regular | 67186 | 143216 | 6.2 | 5.0 | 52.4% | 13.2% |
| Girls | Postseason | 8950 | 19298 | 5.0 | 4.0 | 47.4% | 15.6% |
| Girls | Showcase | 2160 | 4537 | 7.7 | 7.0 | 63.6% | 10.0% |

The phase split confirms the structure.

Regular season has the widest sustained line gaps and the highest standard-season bagel pressure. Postseason compresses the field: line gaps are smaller and three-set rates rise. Showcases widen the gaps again, which is expected because they are constructed events rather than normal state-association league play.

The format effect also matters. Early-season 5S/2D lines are closer and produce more three-set matches; regular 3S/4D exposes lower singles and deeper doubles pressure, so it produces more lopsided sets.

## Set distribution by phase

| Side | Phase | Best-of-3 lines | Sets | Three-set rate | 6–0 | 6–1 | 6–2 | 7–6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Boys | Early | 6930 | 15116 | 18.1% | 25.6% | 18.4% | 16.5% | 6.1% |
| Boys | Regular | 62223 | 132296 | 12.6% | 39.0% | 18.6% | 13.5% | 4.1% |
| Boys | Postseason | 8745 | 18821 | 15.2% | 31.7% | 19.1% | 14.7% | 4.9% |
| Boys | Showcase | 1800 | 3769 | 9.4% | 47.7% | 17.5% | 11.0% | 3.5% |
| Girls | Early | 7434 | 16212 | 18.1% | 26.3% | 18.3% | 16.2% | 5.4% |
| Girls | Regular | 67186 | 143216 | 13.2% | 37.4% | 19.0% | 13.7% | 4.3% |
| Girls | Postseason | 8950 | 19298 | 15.6% | 32.3% | 18.8% | 14.6% | 5.2% |
| Girls | Showcase | 2160 | 4537 | 10.0% | 50.1% | 16.1% | 11.3% | 2.8% |

The postseason distribution is closer to Oregon because the field narrows. The regular-season and showcase distributions are more Jefferson-specific because they expose the full talent spread.

## Slot distribution

| Side | Slot | Sets | 6–0 rate | Avg gap |
| --- | --- | --- | --- | --- |
| Boys | S1 | 25938 | 27.3% | 5.5 |
| Boys | S2 | 21264 | 35.8% | 7.1 |
| Boys | S3 | 21002 | 39.7% | 7.8 |
| Boys | S4 | 2186 | 17.8% | 4.0 |
| Boys | S5 | 2200 | 19.1% | 3.9 |
| Boys | D1 | 25428 | 41.5% | 5.5 |
| Boys | D2 | 25619 | 38.1% | 5.1 |
| Boys | D3 | 23387 | 38.9% | 5.2 |
| Boys | D4 | 22978 | 43.9% | 6.0 |
| Girls | S1 | 27619 | 31.4% | 6.3 |
| Girls | S2 | 23088 | 33.1% | 6.5 |
| Girls | S3 | 22732 | 36.5% | 7.1 |
| Girls | S4 | 2384 | 18.4% | 3.8 |
| Girls | S5 | 2357 | 17.1% | 3.9 |
| Girls | D1 | 27315 | 41.8% | 5.7 |
| Girls | D2 | 27588 | 36.6% | 4.9 |
| Girls | D3 | 25309 | 36.3% | 4.8 |
| Girls | D4 | 24871 | 40.9% | 5.6 |

S1 is not the main bagel engine. The bagel load comes from lower singles, doubles, and lineup depth. That is exactly where a very large high-school association should show its separation: elite players survive at the top, but roster-depth mismatches become severe across thousands of dual lines.

## Interpretation

The 2053 calibration is a better high-school model because it produces hierarchy. It does not just randomize every line toward a plausible final score.

The important properties are:

1. Close matches remain plausible. Three-set and 7–6 rates are not inflated.
2. Rating gaps now matter. Once gaps pass the 5–8 range, the 6–0 rate rises sharply.
3. Postseason compresses talent, as it should.
4. League play exposes weak rosters, as it should.
5. Showcases create the widest standard-match gaps, as expected from constructed event logic.
6. Boys and girls behave similarly, so the result is not a one-side artifact.

## Why Oregon is a benchmark, not a target

Oregon's real data is valuable because it proves high-school tennis is not pro tennis. Real high-school scorelines are blowout-shaped. That made Oregon an effective guardrail against the previous model, which produced too many fake close sets.

Jefferson should not copy Oregon precisely. Oregon's real association has a much smaller player pool and far fewer program/classification surfaces. Jefferson has 1,800+ total teams across 24 side-specific championship classes and a deliberately broad talent model. It places D1/ITF-level juniors and barely-competitive juniors inside the same statewide ecosystem. That will produce scorelines Oregon does not produce at the same rate.

The current result should be read as:

> Oregon established the high-school direction of travel. Jefferson's own talent distribution explains why the final 2053 shape is more lopsided.

## Talent compression implication

If Jefferson's talent distribution were compressed, the 6–0 rate would fall.

The reason is visible in the gap table. Sets played at gaps below 5 points produce 6–0 rates around 6–15%. Sets played at gaps above 8 points produce 6–0 rates around 69–100%. Compressing the association would move more lines into the low-gap bands and fewer into the high-gap bands. The scoreline profile would then shift away from 6–0 and toward 6–1, 6–2, 6–3, and more three-set matches.

The current bagel rate is therefore not an isolated engine number. It is an output of roster construction, association scale, classification structure, lineup format, and phase scheduling.

## Conclusion

The 2053 scoreline model is validated against Jefferson's own design.

The previous model suppressed talent hierarchy. The current model exposes it. Oregon remains useful as a real-world sanity check, but Jefferson's scale and talent spread correctly push the association toward more blowouts than Oregon. The higher 6–0 rate is not a defect by itself. It is evidence that the match engine is finally allowing large high-school talent disparities to appear in the set scores.
