# Scoreline Realism, Explained: Why the 2053 Engine Bagels More Than Oregon Does

The in-app Scoreline Realism page benchmarks every archived set score against five seasons of real Oregon high school tennis (41,932 varsity matches) and reports a "distance from Oregon" score per phase. As of the 2053 season, the whole-association number sits at 10.3 (girls) and 11.3 (boys), driven almost entirely by one line: the sim bagels opponents 6-0 more often than Oregon's real data does, across every phase, every season measured.

The instinct is to read that gap as a miscalibration. It isn't. It's the correct output of a talent architecture that Oregon's real data was never built to represent, and the numbers say so once you look past the top-line distance score.

## The comparison everyone reaches for first

| | Sim % | Real % | Diff |
|---|---|---|---|
| 6-0 | 36–37 | 26.4 | **+10–11** |
| 6-1 | 18.6–18.8 | 21.5 | −2.7 to −2.9 |
| 6-2 | 13.8–14.0 | 17.4 | −3.4 to −3.6 |
| 6-3 | 11.6–11.7 | 13.4 | −1.7 to −1.8 |
| 6-4 | 10.1–10.4 | 12.3 | −1.9 to −2.2 |
| 7-5 | 4.4–4.5 | 5.1 | −0.6 to −0.7 |
| 7-6 | 4.3–4.4 | 3.9 | +0.4 to +0.5 |

Oregon is a real, single benchmark, but it describes a specific talent structure: roughly 300 varsity programs across 8 classifications statewide. Jefferson runs 1,800+ programs across 24 classifications, and its rosters are engineered to carry real D1/ITF-track talent at the top of the lineup alongside beginners at the bottom of the same roster — a talent compression that hasn't existed in real U.S. high school tennis at scale since elite juniors still played scholastically, decades ago. Oregon is a useful, convenient real-world dataset to tune against. It was never meant to be a target the sim should converge on exactly, because Jefferson's talent design was never trying to look like Oregon's.

## The real test: does the engine respect its own talent gaps?

Same-roster spread, 2053 season, current_grade scale (20–77):

| | Median roster spread | p90 roster spread |
|---|---|---|
| Boys | 44 pts | 51 pts |
| Girls | 42 pts | 49 pts |

The **median program**, not an outlier, carries a 42–44 point internal talent gap between its best and worst rostered player. Classification-bound formats (league, postseason) still routinely produce matchups with large rating gaps just from ordinary scheduling.

So the question isn't "does the sim match Oregon's score distribution" — it's "does a large rating gap actually produce a lopsided result." Pulling S1 outcomes against opponent rating gap for 2053 boys:

| Rating gap | 6-0 rate |
|---|---|
| 0–4 (even) | 7.3% |
| 5–14 | 44.2% |
| 15–24 | **94.1%** |
| 25–34 | **100.0%** |

Once the gap crosses 15 points, a bagel is nearly automatic. Above 25, it's total. That's the engine doing exactly what it should with the talent architecture it's been given.

## What changed vs. the pre-2053 era

The same test run against three historical seasons tells the real story:

| Era | 15–24 gap → 6-0 rate | 25–34 gap → 6-0 rate |
|---|---|---|
| 2027 | 8.0% | 8.6% |
| 2035 | 9.5% | — |
| 2052 | 12.2% | 33.3% |
| **2053** | **94.1%** | **100.0%** |

For 26 seasons, a rating gap of up to a quarter of the entire scale barely moved the needle on outcomes — the engine was absorbing real skill differences into set-to-set variance almost regardless of size. That's the "too close" era: upsets too prevalent, teams beating opponents they had no business beating. The 2053 recalibration didn't chase Oregon's distribution for its own sake. It fixed the actual bug — rating gaps not converting into results — and the Oregon dataset (plus ITF/assumed real-world benchmarks) was simply the tuning tool available to validate the fix against, alongside the internal gap-to-outcome test above.

## Reading the four phases correctly

| Phase | Distance (boys / girls) | Why |
|---|---|---|
| League season | 11.7 / 10.3 | Classification-bound. Baseline volume format; large gaps still occur naturally within a class of 70–90 programs. |
| Postseason | 6.4 / 7.2 | **Best-calibrated phase in both genders.** Seeding compresses matchups toward comparable strength as rounds advance — the format itself narrows the gap distribution, and the score distribution follows. |
| Showcases | 21.3 / 23.7 | **By design, not a bug.** Showcases are the one format that's explicitly interclass — a 9A blueblood can face a 1A program. Classification acts as a talent firewall everywhere else; showcases remove it on purpose, to let the state see itself play across the whole ladder. Given the gap-to-outcome curve above, cross-classification pairings are close to guaranteed to produce large gaps, so a much higher blowout rate is the expected, correct output — not something to tune away. |

## The boys/girls difference

Boys run consistently ~1 point hotter than girls on every phase (37.2% vs 36.2% overall 6-0 rate, 11.3 vs 10.3 distance). This isn't noise — it mirrors real-world UTR/WTN spread, where the boys talent pool carries a higher ceiling than the girls pool. The sim is encoding a real asymmetry, not drifting from parity.

## Bottom line

Every number on the Scoreline Realism page is internally consistent once you stop reading it as "how close to Oregon" and start reading it as "does classification correctly bound the talent gap, and does the engine respect the gap it's given":

- League and postseason track close to Oregon because classification bounds the gap, the same way Oregon's own class system does.
- Postseason is closer still because seeding narrows the gap further as rounds advance.
- Showcases are the outlier because they're the one format built to remove the classification bound entirely, on purpose.
- Boys run hotter than girls because the talent architecture itself has a higher boys ceiling, matching real UTR/WTN patterns.

Nothing here needs fixing. The distance-from-Oregon number is a useful gut check for the classification-bound formats, and a poor fit for the one format that was never supposed to look like classification-bound tennis in the first place.
