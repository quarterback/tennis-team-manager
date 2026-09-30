# JHSAA 2029 Season Retrospective and Association Report

The uploaded research export is internally labeled `2103`; this report treats it as canonical **2029**, following the same historical retrofit used by the repo's 2028 season review (`docs/reports/2028-jhsaa-season-review.md`, where internal `2102` = canonical 2028).

This is not just a recap of champions. It evaluates the season against the rule changes that were supposed to be live before the run, and against the 2028 baseline.

## Executive findings

- The new **10B/11B Non-Public structure actually ran as a separate competitive world**, adding two State championships per gender, pod standings, class awards, individual/JV infrastructure, and private-school representation in the expanded TOC.
- The **16-team pilot signal repeated**. Lower seeds won 33.3% of boys State matches and 29.3% of girls State matches in 4A, 3A, 2A, 1A and Group 3, versus 21.8% and 22.2% in the other seven public classes. The exact 2028 gender split did not repeat, but the small-field classes remained substantially more volatile.
- The old twelve public classes became slightly more top-seed-driven at the title level: **20 of 24 public champions were top-four seeds**, up from 18 of 24 in 2028.
- The expanded **16-team Tournament of Champions worked exactly as a tournament object**: two qualifier duals per gender, then fifteen TOC duals with no byes. Canal View won the boys TOC; Mater Dei won the girls TOC.
- The private split immediately changed where elite programs win. Defending 2028 powers that had lived in public classes now appear in the new private classes: **Hazel Country Day won boys 10B** and **Mater Dei won girls 10B**.
- The new early-participation regime remained consequential without returning to the old whole-cohort flood. The current rosters contain **269 boys and 295 girls in grades 7–8**; **198 boys and 217 girls appeared in varsity competition**.
- The revised rising-freshman portal became dramatically narrower: **70 boys and 68 girls** moved in the current cohort, down from 428 boys and 452 girls in the 2028 portal. The smaller market still placed everyone in varsity competition in this season.
- V2/V3 play is not theoretical. The export contains **592 boys split-squad varsity duals** (386 V2, 206 V3) and **638 girls split-squad varsity duals** (429 V2, 209 V3).

## State champions

| Class | Boys champion | Seed | Girls champion | Seed |
|---|---|---:|---|---:|
| 9A | Pacific Gate | 2 | Seawall | 1 |
| 8A | Oakhaven | 3 | East Moscow | 3 |
| 7A | Mendoza | 10 | Mendoza | 2 |
| 6A | Ferris County | 5 | Casco | 10 |
| 5A | Bush | 2 | Trois Ilets | 1 |
| 4A | Barclay | 1 | Grizzly Gulch | 2 |
| 3A | Villard | 1 | Lonepine | 4 |
| 2A | Antler County | 4 | Purcell Crossing | 4 |
| 1A | Mt Jacqueline | 1 | Barley Gap | 2 |
| Group 1 | Canal View | 1 | La Grande | 2 |
| Group 2 | Nyssa | 2 | Elgin | 5 |
| Group 3 | Ninemile | 1 | Garden City | 1 |
| 10B | Hazel Country Day | 1 | Mater Dei | 6 |
| 11B | Sage Summit | 4 | High Desert Christian | 11 |

Among the original twelve public classifications, the median champion seed was 2 in both genders. Ten of twelve boys champions and ten of twelve girls champions were top-four seeds. In 2028, ten boys champions but only eight girls champions were top four, so the public-title layer became more orderly even while the smaller fields remained upset-heavy round by round.

The new Non-Public championships immediately produced two different profiles. Boys 10B was chalk at the top — No. 1 Hazel Country Day over No. 2 Westfield Friends — while girls 11B was the largest title upset in the new classes, with No. 11 High Desert Christian winning the championship.

## State structure: the 16-team pilot repeated its signal

2028 produced a striking difference between the five 16-team pilot classes and the other seven public classes. That distinction survived another season.

| State format | 2028 boys lower-seed | 2029 boys lower-seed | 2028 girls lower-seed | 2029 girls lower-seed |
|---|---:|---:|---:|---:|
| 16-team pilot | 29.3% | **33.3%** | 38.7% | **29.3%** |
| Other seven public classes | 19.8% | **21.8%** | 19.8% | **22.2%** |

The repeat matters more than reproducing the exact percentages. In both seasons, the five 16-team classes were clearly less seed-stable than the larger public fields. What changed is the gender pattern: 2028 girls were exceptionally volatile; 2029 boys were slightly more volatile than girls.

One-position State results tell a similar story. The 16-team classes produced one-position finals in **37.3% of boys matches and 46.7% of girls matches**, compared with **24.1% and 27.6%** in the other seven public classes. The girls pilot remained especially close even though its upset rate fell.

Across all fourteen 2029 classes, lower seeds won 92 of 378 State duals in each gender: **24.3% boys and 24.3% girls**. The symmetry is incidental, but it is a useful association-level baseline now that 10B/11B add 46 State matches per gender beyond the old 332-match public slate.

## The Non-Public split changed the competitive map

The repo's September change (`33b79ee`, later refined in PR 477 and follow-up fixes) made a private school's championship group **10B or 11B**, with an owner-drawn pod as its district, while preserving `old_group` and `old_league` for annual non-conference games against the public league it would otherwise occupy.

The 2029 export shows that architecture throughout:

- boys: 57 programs in 10B and 55 in 11B;
- girls: 60 programs in 10B and 56 in 11B;
- both classes produce their own State fields and champions;
- both classes produce State Coach of the Year awards;
- the private programs appear in the TOC as private-class champions rather than as public-class members.

The competitive consequence is immediate. Hazel Country Day, the 2028 boys 8A champion and TOC champion, did not simply disappear from the top of the association when the private split arrived: it won the inaugural 10B boys title. Mater Dei, the 2028 girls 9A champion, won girls 10B and then the overall TOC.

There is one structural warning inside the pod implementation. The owner rule describes pods of roughly 8–10 schools, but sponsorship filtering leaves **Sunkist League with only two active 10B teams in each gender** in this export. Most pods sit near the intended range, but the active-tennis league layer can still become extremely thin even when the underlying school pod was drawn correctly. That is a schedule/standings quality issue worth deciding explicitly rather than treating the pod map alone as sufficient.

## Tournament of Champions: the expansion worked

The adopted TOC change created fourteen automatic champion entries plus two qualifier winners: one public runner-up qualifier and one private runner-up qualifier, producing a byeless sixteen-team bracket.

That is exactly what the archive contains.

### Boys qualifiers

- Westfield Friends defeated Paddock Episcopal 3–2 in the private qualifier.
- Orchard Union defeated Wells 3–2 in the public qualifier.

The sixteen-team tournament then ran fifteen duals. Canal View beat Mendoza, Orchard Union and Barclay before defeating Pacific Gate **4–1** in the final.

### Girls qualifiers

- Ashbury Latin defeated Evans 4–1 in the private qualifier.
- Wells defeated Plainfield 4–1 in the public qualifier.

Mater Dei beat Grizzly Gulch 5–0, Purcell Crossing 5–0, Lonepine 4–1 and Seawall **3–2** to win the TOC.

This is a meaningful contrast with 2028. Hazel Country Day swept both TOCs in the prior season. In 2029 the boys TOC moved to a Group 1 champion, while the girls TOC stayed with an elite private power that had just been moved into 10B. The expanded format therefore did not merely give two extra teams decorative access; qualifier winners entered a normal sixteen-team championship tree.

## Repeat titles and movement at the top

Several public boys powers carried 2028 success straight into 2029:

- Pacific Gate repeated in 9A.
- Barclay repeated in 4A.
- Villard repeated in 3A.
- Mt Jacqueline repeated in 1A.

Hazel Country Day also repeated as a State champion in practical competitive terms, but in a different championship structure: 2028 8A became 2029 10B after the private-school split.

Girls were much less repetitive. Mater Dei is the clearest continuity case, moving from the 2028 9A title to the 2029 10B title. The rest of the girls championship map turned over heavily.

The new season also created notable first or long-awaited titles in the archived program record. Among boys champions, Antler County, Ferris County, Mendoza, Nyssa and Sage Summit had no prior State title in the available ledger. Ninemile's previous boys title was forty-one archived seasons earlier. On the girls side, Casco, High Desert Christian, Lonepine, Mendoza, Purcell Crossing and Trois Ilets won their first available State titles, while East Moscow and Garden City ended twenty-two-season waits.

## Portal: a different market, not merely a smaller number

The 2028 report documented 880 rising-freshman moves: 428 boys and 452 girls. The current repo rule is much narrower. A portal candidate must be an early participant entering ninth grade, lack a projected V1 seat at the current 1A/2A/Group 3 program, and have a destination that projects them onto V1.

The 2029 ledger contains only:

| | Boys | Girls |
|---|---:|---:|
| Current portal moves | **70** | **68** |
| Median projected V1 seat | 7.0 | 7.5 |
| County moves | 49 | 50 |
| Same-area moves | 5 | 5 |
| Neighbor-area moves | 16 | 13 |

That is an 84% reduction from the previous year's total portal volume, but it is consistent with the new premise: this is no longer a broad movement market for rising freshmen. It is a targeted playing-time clearing mechanism for the small early-participant population.

Every current-year mover in the export appeared in varsity competition. Among those players, 59 boys and 59 girls reached at least ten varsity appearances; 37 boys and 42 girls reached at least twenty. So the narrower rule is still placing players into real varsity work.

The longitudinal caveat is important: because the portal eligibility model itself changed, 2028-to-2029 volume should not be interpreted as a market collapse. It is a policy discontinuity.

## Early participation: small cohorts, high varsity conversion

2028 finished with 240 boys and 275 girls in grades 7–8; 172 boys and 181 girls played varsity.

The 2029 export has:

| | 2028 | 2029 |
|---|---:|---:|
| Boys grades 7–8 | 240 | **269** |
| Boys with varsity appearance | 172 | **198** |
| Girls grades 7–8 | 275 | **295** |
| Girls with varsity appearance | 181 | **217** |

Varsity conversion therefore rose from about 71.7% to 73.6% for boys and from about 65.8% to 73.6% for girls.

That supports the intended distinction behind the revised early-seat rule: early participation is rare enough not to occupy huge chunks of every eligible roster, but an early participant is not merely being warehoused on JV.

The maturity layer is also now genuinely populated in the export. The current player tables contain 1,647 boys and 1,714 girls with at least one archived bloom grade. That is enough data to begin longitudinal analysis, but the repo's own warning remains correct: same-season bloom status is not a clean causal test of whether the maturity mechanism improves outcomes, because the event itself changes subsequent development.

## Split squads: V2/V3 are now part of the varsity ecology

The 2097 split-squad change allows a program's V2 or V3 group to face another school's V1, with the result counting as a varsity result for the V1 side and giving the lower squad meaningful competition.

The 2029 archive contains:

| | V2 duals | V3 duals | Total |
|---|---:|---:|---:|
| Boys | 386 | 206 | **592** |
| Girls | 429 | 209 | **638** |

This is enough volume that V2/V3 is no longer an edge subsystem. It is now affecting player participation, opponent schedules and the pathway between JV depth and varsity-quality competition.

## JV layer

The qualifying JV State structure also ran at full size: 120 State qualifiers per gender, consistent with the thirty-region, four-qualifier model.

- Boys JV State champion: **Mercy Academy Valley**
- Girls JV State champion: **Jackson Hole**

The useful 2029 story is less the champions than the interaction between levels. The expanded JV/V2/V3 ecology is generating substantial play and is now substantial enough to evaluate as part of the association rather than as a side system.

## Coach of the Year layer

The new coach-award system produced one State Coach of the Year in all fourteen groups per gender, including 10B and 11B. The inaugural Non-Public winners were:

- Boys 10B: Aubree Arevalo, Cardinal Echevarria
- Boys 11B: Asher Libby, Sage Summit
- Girls 10B: Alec Thurlow, Ashbury Latin
- Girls 11B: Milena Chinwike, Evans

The notable structural point is that the award system followed the new championship map. Private coaches are not being evaluated inside the public classes they historically occupied.

The repeat-winner penalty should be evaluated longitudinally after several seasons under the current scoring constants; one season cannot tell whether the new `-5, -4, -2, -1, 0` recency shape is too strong or too weak.

## What 2029 validates

Observed and working:

- 10B/11B exist as actual competitive classes, not just alternate State-bracket labels.
- Private-class champions, awards and TOC access all function.
- The 16-team public pilot again produces materially more volatile State brackets.
- The sixteen-team TOC qualifier design produces exactly two qualifiers and a byeless fifteen-match championship.
- The narrower early-participant portal still converts moves into varsity participation.
- Early participation remains visible at varsity level with much smaller cohorts than the original whole-cohort implementation.
- V2/V3 has enough schedule volume to matter as a real competitive layer.
- JV State qualifying produces the intended 120-team main field per gender.
- Coach awards now cover all fourteen championship groups.

Not validated:

- Pod size alone as a guarantee of healthy tennis leagues; at least one 10B pod has only two active teams per gender after sponsorship filtering.
- Any causal claim that the 16-team format itself creates volatility. The two-season association is now stronger, but class populations and competitive distributions still differ.
- Long-term maturity effects. The data now exist, but the correct test is longitudinal.
- Long-term portal development. The 2029 portal is operating under a substantially different eligibility rule from the 2028 cohort.

## 2028 → 2029 in one table

| Measure | 2028 | 2029 |
|---|---:|---:|
| Championship classes | 12 | **14** |
| Public State duals / gender | 332 | **332** |
| Non-Public State duals / gender | — | **46** |
| Public top-four champions | 18 / 24 | **20 / 24** |
| 16-team lower-seed wins, boys | 29.3% | **33.3%** |
| 16-team lower-seed wins, girls | 38.7% | **29.3%** |
| Other-public lower-seed wins, boys | 19.8% | **21.8%** |
| Other-public lower-seed wins, girls | 19.8% | **22.2%** |
| Portal moves, boys | 428 | **70** |
| Portal moves, girls | 452 | **68** |
| Grade 7–8 boys | 240 | **269** |
| Grade 7–8 girls | 275 | **295** |
| TOC field | previous format | **16, no byes** |

## Association judgment for the next run

The season-level redesign is doing most of what it was built to do. The private-school problem is now structurally legible instead of being hidden inside public-class results; the TOC expansion works; the small-field experiment continues to generate a distinct State environment; the portal has been converted from a large transfer market into a targeted opportunity mechanism; and V2/V3 has become a real part of the ecosystem.

The main structural decision still worth watching is thin private pods. If a pod is an organizational unit of 8–10 schools but only two sponsor a gender's tennis team, the tennis league is functionally a two-team district. The association should either accept that explicitly, merge thin tennis pods for standings purposes, or draw tennis pods from sponsors rather than from all private schools.

Everything else can proceed to another season with measurement rather than redesign.

## Method

Primary data: uploaded JHSAA boys/girls research export, internally `2103`, treated as canonical 2029.

Comparison baseline: `docs/reports/2028-jhsaa-season-review.md`.

Repo rules checked directly against the current JHSAA design and AAR documents, especially:

- `docs/DESIGN-jhsaa-high-school-season.md`
- PR 477 and commit `33b79ee` for the Non-Public pods / old-league model
- the adopted TOC qualifier implementation (`toc_qualifier`)
- export domain rules in each `manifest.json`

State upset calculations use the archived State field order as seed order.
