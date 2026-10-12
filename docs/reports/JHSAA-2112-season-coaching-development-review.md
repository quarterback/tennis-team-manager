# JHSAA 2112: Realignment, Coaching Careers, and the First Development-Stock Cohorts

*Internal association research report · 2038 world / 2112 JHSAA season · boys and girls · prepared October 2026*

**Source:** `play-to-clinch-jhsaa-2038-both.zip`, both `2112/boys/` and `2112/girls/` research bundles, reconciled with the separately supplied `2112-jhsaa-season-review.md`. Historical and design comparisons use [`JHSAA-development-panel-review-2103-2111.md`](JHSAA-development-panel-review-2103-2111.md), [`AAR-jhsaa-attribute-development-stock.md`](../AAR-jhsaa-attribute-development-stock.md), and [`AAR-jhsaa-coach-bond-annuity.md`](../AAR-jhsaa-coach-bond-annuity.md).

**Status:** Research from the exported save, not a new simulated experiment. No development coefficient, coach rating, bond formula, competitive result, or archived save was changed. The research bundle was supplied for analysis; the complete ZIP is **not** part of this Git repository. All individual skill ratings below are **internal calibration measures**, not ratings intended to be shown in the game world.

## The main finding

2112 gives us a useful first reading of the *coach* system and an unusually difficult year in which to interpret it. The bond and annuity are populated for 1,962 current head coaches. Veteran development coaches at weak programs do retain credible bond ratings. Long-serving coaches earn annuity credits, and the export records the annual achievements behind them. Competitive strength, however, moved sharply under realignment, so an improvement measure based on year-over-year winning percentage needs to be interpreted in that context.

The attribute-development system is at an earlier stage. The export contains 15,284 players with a new developmental-stock profile, but only **44** have accumulated coached skill gains, almost all because they played in earlier middle-school seasons. This is an **entry-year baseline**, not a test of what an excellent four-coach staff can do over a high-school career. The initial 44 gains are traceable and, in this file, reach actual attributes without meaningful loss during final application. The more consequential design question is the *joint distribution of effort and trainability*: very large coaching budgets disproportionately sit with players whose work-ethic score is more ordinary.

The next serious test is the 2112 entering class as sophomores in **2113**, juniors in **2114**, and seniors in **2115**, then the 2112 seventh-graders through **2117**. It must ask whether schools teach *different capabilities*, whether a marginal beginner can make an exceptionally large but credible leap, and whether those skills matter in singles and doubles results. A State semifinal or final is an actual competitive outcome, not a prize that the development model should award directly.

### Association snapshot

| Measure | Boys | Girls | Combined / reading |
|---|---:|---:|---|
| Programs represented in `programs.csv` | 965 | 1,002 | **1,967** |
| 2112 head-coach season records | 960 | 1,002 | **1,962**; five boys' programs have no head row |
| Rostered players | 28,641 | 29,803 | **58,444** |
| Players with new development-stock profiles | 7,506 | 7,778 | **15,284** (26.2% of current rosters) |
| New-stock players with reported coached gains | 21 | 23 | **44**, or 0.29% of stock-profile players |
| Eligible for head-coach bond annuity | 234 | 255 | **489** (24.9% of current heads) |
| Covered by veteran-development protection | 317 | 338 | **655** (33.4%) |
| District-to-district/class realignment changes, from historical comparison | 318 | 332 | **650** changed classification |

The export names the simulated season **2112** inside the **2038** world. The `jhsaa_realignments.csv` event uses calendar year **2038**, so filter realignment events on `season_year=2038`, while the program-history, player and coach-season research tables use **2112**. Mixing those clocks silently eliminates the realignment sample.

## The competitive season that coaches actually faced

The realignment changed the level of opposition for about a third of programs. **Seven distinct champion programs** won titles in a newly assigned class: Barley Gap in both genders, Brackwood Pass girls, Bush boys, Penobscot boys, Mt Jacqueline boys, Mabry Township boys and Elk Bluff West girls. Counting victories rather than distinct programs, that is **eight championship results**. The supplied season review correctly distinguishes schools from individual boys/girls championships when tracing realignment; this report uses **eight title results** for the association-wide table.

Canal View's boys won Group 1 and the Tournament of Champions, the first public-school TOC winner since Chaparral in 2108. Romero-Finniski's girls went **33–0**, won 11B and claimed a second consecutive TOC. Six programs won a first State title in the historical archive: **Millworks, Windward and Mabry Township (boys); Santa Cruz del Norte, Severn and New Casper (girls)**. Several runs matter to the coaching discussion because they offer ordinary program-building stories beyond serial State champions: Millworks reached its first 4A title as a seventh seed through the Divisionals, and Mabry Township won Group 3 as a ninth seed.

### The State champions

| Championship group | Boys | Girls |
|---|---|---|
| 9A | L.B. Johnson | Seawall |
| 8A | Bush | Santa Cruz del Norte |
| 7A | Penobscot | Severn |
| 6A | Clover | Orellana Heights |
| 5A | Crater View | Grand Fond |
| 4A | Millworks | Gagarin |
| 3A | Windward | Brackwood Pass |
| 2A | Mt Jacqueline | New Casper |
| 1A | Barley Gap | Barley Gap |
| Group 1 | Canal View | Canal View |
| Group 2 | Virginia City | Saltbush |
| Group 3 | Mabry Township | Elk Bluff West |
| 10B | Chaminade | Evans Larsen Day |
| 11B | Romero-Finniski | Romero-Finniski |
| **TOC** | **Canal View** | **Romero-Finniski** |

The season review's broader competition evidence adds useful texture. Fourteen of the 28 State finals were decided by a single team point. The public/private TOC qualifiers divided by gender: Chaparral and Mendoza won on the boys side; Mercy Academy Valley and Marigny advanced among the girls. Mercy Academy Valley, a 10B runner-up, reached the girls' TOC final. No Circuit winner won State for the first time since 2107; Tunnelton was the deepest Circuit winner, reaching the 4A boys' final. These details describe how hard exceptional competitive accomplishments were, rather than assuming every title follows ordinary school strength.

The participation result also belongs in this account: **1,764 of 14,034 seniors (12.6%)** had no varsity appearance, versus **1,510 of 13,621 (11.1%)** in 2111. Realignment changed many lineups' legal sizes after the graduating class was assembled. It is a reason to use actual exposure and match participation when evaluating player development instead of treating a roster position as a constant across classifications. Among younger players there were **548 seventh-graders and 1,079 eighth-graders**; the season review reports that 58% and 64%, respectively, appeared in varsity duals. These are also the cohorts that can realize coached gains before their ninth-grade year.

## The head-coach population and the new bond

The bond is **earned program credibility**, expressed as a small multiplier on development teaching offers. It is distinct from each coach's permanent technical grades, specialty portfolio and the existing Changeover/Tactics/Singles match effects. It never gives a player ability merely for winning a dual. A new coach can remain an excellent teacher even before accumulating a bond history.

**The timing is essential:** `jhsaa_coach_seasons.csv` records the bond a head **entered 2112 with**. It summarizes up to five **completed seasons before 2112**. The 2112 State and TOC titles, district performance, and new winning percentage change are subsequent accomplishments; they will affect the applicable later bond calculation, rather than automatically appearing in the bond column alongside this season's final record.

The archive contains a substantial cohort of recently appointed heads: **552** had zero completed consecutive head seasons at their present program; **478** had no earlier head-coaching seasons available to produce a bond score. A neutral 1.0 for those coaches is a starting position, not a poor evaluation of the season they just coached. Coaches who return to a head job or change programs can have prior career history despite zero current-program tenure.

### How bond is earned in the implemented code

| Completed-season evidence | Points used in the bond calculation |
|---|---:|
| Winning percentage, ties worth half a win | 0 to 20; a .500 year earns 10 |
| Year-over-year winning-percentage improvement | −10 to +10, at 50 points per unit of change |
| District title | +12 |
| Road-to-State **unit trophies** won | +5 each, excluding the district title already counted |
| State entry / deepest finish | +4 appearance, +11 quarterfinal, +17 semifinal, +23 final, or +30 champion; highest reached tier only |
| Tournament of Champions title | Additional +8 |
| Consecutive head years at this program | +0.8 per year, capped at +8 |
| Annuity once eligible | +25% of **positive achievements** that season, excluding tenure and ordinary `.500` win credit |

These are reputation **points**, not a 25% OVR grant. The coach's prior five annual scores receive recency weights **1.0, 0.8, 0.6, 0.45, 0.3**. The average is referenced against **16**, scaled by **45**, shrunk toward neutral for short histories and converted to a nominal **0.85–1.15** multiplier. The code counts *Road-to-State unit trophies*, not the separate weighted unit values in `jhsaa_coefficient.py`; that distinction should remain explicit in analysis. The archived win/loss figures used here include postseason results, rather than a separate regular-season-only record.

### What the 2112 bond distribution actually looks like

| Metric for all 1,962 current heads | Observed result |
|---|---:|
| Mean / median bond | **1.0269 / 1.0059** |
| 10th percentile / 90th percentile | **0.9928 / 1.0875** |
| Minimum / maximum | **0.9638 / 1.1071** |
| Heads below neutral 1.0 | **261** |
| Heads exactly neutral 1.0 | **633** |
| Heads at the observed upper plateau, approximately 1.1071 | **116** |
| Heads with a nonblank prior-season achievement score | **1,484** |

The code nominally allows 1.15 but the five-season history shrink prevents an established head with a full five prior years from reaching it. Even with a maximum underlying score, the factor `5/(5+2)` makes the ceiling `1 + .15 × 5/7 = 1.1071`. **116 heads** were already at that plateau; **88** of them had an active annuity. At this point another annuity achievement can raise their *auditable point score* without further changing the multiplier used by the staff. This is an intentional mathematical consequence of the present formula, not evidence that their championships are uncounted. It is a meaningful calibration choice for future review: preserving a firm cap protects the simulation, while a softer or higher plateau would make additional elite achievements affect teaching more visibly.

Tenure is associated with stronger entering bond, although this is an observational association that mixes team history, career success, survival in the job and veteran protection:

| Completed consecutive head seasons at current program | Heads | Median 2112 bond | Current-year mean win percentage |
|---|---:|---:|---:|
| 0 | 552 | 1.0000 | .367 |
| 1–4 | 513 | 1.0064 | .479 |
| 5–9 | 408 | 1.0272 | .532 |
| 10+ | 489 | 1.0668 | .578 |

### The annuity rewards sustained commitment; veteran protection safeguards good teachers

A coach **older than 40** with **ten consecutive completed head-coaching seasons at one program** becomes annuity-eligible. Positive accomplishments beginning with the **eleventh season** receive a 25% reputation supplement. A move to a different program resets this program-specific qualification. The coach's career record remains theirs.

A separate protection covers **development-focused coaches aged 55 or older**: a practice/teacher/JV-whisperer coaching profile, or Development quantile of at least .75, qualifies. They retain a bond of at least 1.0 and at least their prior earned head-coaching bond even at a losing program. Their teaching grades remain the same, and they can still earn a higher bond. A coach can qualify for either protection, both, or neither.

| Current head-coach category | Number | Share of 1,962 |
|---|---:|---:|
| Annuity and veteran protection | 182 | 9.3% |
| Annuity only | 307 | 15.6% |
| Veteran protection only | 473 | 24.1% |
| Neither | 1,000 | 51.0% |

The export records a **positive annuity bonus earned in the most recent completed year for 452 heads**. Of those, **429** remain annuity-eligible entering 2112; **23** earned the bonus in that preceding year but no longer qualified at their current program, consistent with the annuity being tied to a particular head-coaching tenure. The fields `bond_annuity_active` and `bond_latest_annuity_bonus` therefore answer **different questions** and should not be treated as interchangeable.

Among the 655 veteran-protected current heads, **201 coached teams with a 2112 winning percentage below .350**. Their entering bond never fell below 1.0; the median was **1.0**, while some retained much more of their previously earned reputation. That is the precise behavior requested for experienced development coaches who choose to work in weak programs.

## Coaches worth following, for different reasons

These examples join the 2112 head row and historical program row using stable `program_id`. Records and titles are *2112 outcomes*; bonds describe the seasons **entering** 2112. They are examples of the mechanics, not claims that the 2112 records were caused by the coaches' bond.

**A veteran at a struggling program: Maxwell Salama, Southern Pacific Tech boys.** Southern Pacific Tech finished **0–21**, but Salama carried a **1.1031** entering bond, 18 completed seasons at the school, an active annuity and veteran protection. The model does not suddenly judge him incapable of teaching tennis because his present team cannot win. Whether his students actually acquire useful skills must be answered from subsequent player ledgers, not inferred from bond.

**A promoted program in trouble: Lilly Flores, Chickasaw girls.** Chickasaw fell from **25–8** in Group 2 to **5–18** in Group 1. Flores entered with a **1.0967** bond, 18 completed head seasons, and both protections. It is an especially revealing 2112 case: a competition-level change can destroy a winning percentage without proving that the coaching staff has ceased to be effective. The record should influence future earned achievement calculations, while the veteran rule preserves Flores's established developmental standing.

**A young first-time champion: Owen Gibson, Millworks boys.** At **35**, with four completed head seasons and a **0.9833** entering bond, Gibson took Millworks to a **24–6** season and its first 4A State title as the **seventh seed**. The new competitive achievement should be credited in the next calculation. It illustrates why a young coach's reputation must be allowed to develop instead of being predetermined by age or tenure.

**Two ways to win at the same school: Elijah Swartz and Mia Orosco, Barley Gap.** The boys were **26–1**, the girls **27–3**, and both won 1A after moving down. Swartz, the boys' head, was **70** with 18 completed seasons, an annuity and a **1.1071** bond. Orosco, the girls' head, was **34**, with four completed seasons, no annuity and a **0.9788** entering bond. The school earned two championships under coaches at different points in their careers; their future scores should reflect this year's results while continuing to treat age, reputation and technical teaching skills separately.

**A title does not require a reputation head start: Kessler Church, Mabry Township boys.** Mabry Township won Group 3 from the **ninth seed**, ending **24–10**. Church was a newly assigned head with neutral **1.0** bond in the export. His team achieved something meaningful before he had a current-program bond history. This is an important guard against reading an earned multiplier as a ranking of intrinsic coaching ability.

**A proven elite program: Mia Huang, Canal View boys.** Huang entered with **1.1071** bond, 16 completed head years, annuity eligibility and veteran protection. Canal View won the Group 1 title and TOC. This case also exposes the upper-plateau question: the coach can earn another exceptional season's annuity credit without gaining more headroom in the current bond conversion.

**Ordinary district success without a State berth:** only **four** current 2112 head-coached programs have a district title and no State appearance. Among long-serving heads, **Trey Morris at San Borondón girls** (16–15, 18 seasons, bond **1.0479**) and **Noah Fontenot at Shiloh girls** (14–11, 18 seasons, bond **1.0420**) are more useful examples of the owner's view that sustained district success still defines a good coach. Because this particular season has only four such title/no-State cases, long-term recognition of district builders should be studied across multiple years rather than concluded from one cross-section.

### Younger coaches with development opportunities

Mimi Eisner's **Arlington girls** improved from **4–19 to 22–12** in her first head season and reached State. Her entering bond was **1.0**. **Aaliyah Falco's Kilbride girls** climbed from **7–20 to 25–3** and reached a quarterfinal; Falco had six completed head seasons and entered with a **0.9908** bond. **Harley Christofferson's Trois Ilets girls** went from **0–23 to 17–17** after the school moved from 9A to 5A; Christofferson had veteran protection and a **1.1000** bond. These are three different trajectories. The first two show what should flow into *future* young/mid-career achievement scoring; the third shows why realignment must be distinguished from improved underlying coaching.

## Realignment is a live test of the fairness of year-over-year scoring

The separate season review reports **318 boys and 332 girls** program-classification changes when matching program histories from 2111 to 2112. Of these, 161 boys / 168 girls moved upward and 157 boys / 164 girls moved downward, counting the three schools that returned from 11B to public classification among the upward moves. The event ledger also has **329 2038 realignment transactions for each gender**; use matched year-to-year classification in `jhsaa_program_history.csv` to count actual differences in each gender's competition, because the transaction log describes league-wide actions and private-school moves differently.

| Program movement | Mean 2111 win percentage | Mean 2112 win percentage | Typical change |
|---|---:|---:|---:|
| Boys moved up | about .602 | about .504 | about −.10 |
| Girls moved up | about .610 | about .527 | about −.08 |
| Boys moved down | .321 | .410 | about +.09 |
| Girls moved down | .332 | .408 | about +.08 |

Calculated from season records for the matched programs (equal weight per program, not aggregate wins divided by aggregate matches). The source review gives rounded figures for the full movement classes; internal checks on directly comparable class pairs give the same pattern. These are **descriptive**, not the causal effect of realignment in isolation.

This matters to the bond because its year-on-year component awards or subtracts up to ten reputation points for a winning-percentage change. A promoted team that goes from .600 to .500 loses **five improvement points** before any corresponding change in teaching quality. A demoted team can earn five without changing its coaches. The 2112 wins will enter the **2113** bond calculations. Veteran teachers are partly protected by their floor; younger head coaches are more exposed to these classification effects, exactly when the user wants room for young coaches to build their careers.

**Calibration experiment, not an authorized code change:** compare the current raw year-on-year result with a class-adjusted alternative that subtracts the average result of all programs experiencing the same kind of move. A coach doing better than their *new-class peers* deserves consideration even if the raw win rate falls. District achievements, actual State progress, and sustained seasons should remain credited in their own channels. Evaluate the two versions before deciding whether to alter the implemented scoring.

## The development-stock rollout: what this export really tests

The new attribute coaching model has **two distinct sources of improvement**. The existing maturity and early-POT system drives its own player development events. Coaching separately converts a player's hidden development stock into specific skills through individual teachers and player responsiveness. Neither needs to override the other. The old generic additive OVR dividend was superseded; each coach's categories and actual attribute gains matter.

The new profile describes **51 attributes**, grouped into eight coached skill families (serve, return, baseline, net, movement, touch, physical and mental) and one uncoached set of intangibles. It stores the player's natural attribute targets, trainable ceilings, stable work ethic and category responsiveness, an extra raw development stock, and a weighted OVR-equivalent coaching budget. The overall rating is recalculated from the actual learned attributes; Changeover remains a distinct in-match effect.

### Who is in the 2112 stock system

| Current school grade | Players with new-stock profile | Interpretation |
|---|---:|---|
| 7th | 548 | First early-participation cohort in the current export |
| 8th | 562 | Mix of first-time and returning early participants |
| 9th | **14,087** | Core new entering ninth-grade cohort |
| 10th | 0 | Continuing old-model cohort under the rollout cutoff |
| 11th | 87 | Newly appearing juniors: 86 list first-year program tenure and one has missing tenure; none has archived staffed development or a transfer marker in this export |
| 12th | 0 | Continuing old-model graduating class |
| **Total** | **15,284** | 26.2% of current players |

The juniors are worth a data-contract note: *grade does not always prove how long a player has been enrolled*. These 87 have stock profiles but no prior archived staff offers; they appear as new roster additions. Future longitudinal queries must use `player_id`, year and actual tenure rather than assuming every eleventh-grader has two prior seasons in the new model. Previously archived seventh/eighth-graders on the old model remain protected by their existing talent pins, following the PR #496 cutoff fix.

Of the 15,284 stock-era students, **15,240 have no prior staffed season in their stock ledger**. The remaining **44** carry one or two earlier staffed seasons, from **2110 and 2111**, and are the entire group with coached gains. All 44 are current eighth- or ninth-graders with prior early participation. New ninth-graders have not yet had a completed season of coaching under the ordinary high-school cycle.

### The developmental capacity that exists before coaching

| Internal stock-era calibration measure | Median | 90th percentile | Maximum |
|---|---:|---:|---:|
| Work ethic, 0–1 | **0.477** | **0.699** | 0.982 |
| Weighted trainable ceiling above ordinary natural target | **9.967 OVR** | **16.241 OVR** | 29.738 OVR |
| Extra *spendable* coaching OVR budget | **7.864 OVR** | **13.302 OVR** | 27.232 OVR |

The raw `stock_total` and individual raw attribute gains use different units from OVR. Do not add raw points to OVR values. The coaching budget is **permission to acquire additional skill**, not a prediction that it will all be used, and it does not include every part of the ordinary natural growth curve. The high-school model can create a player whose natural improvement is very large and who has further coachable attributes beyond it. Actual exceptional careers require the capacities to coexist with effort, instruction and exposure.

**The design is working in one intended direction:** weaker current players generally have more unused developmental room. Among stock players starting at an internal current rating of 40 or below, the median coaching budget is about **9.01 OVR**. For those starting at 60 or above, it is about **4.58**. This is internal research, not a public scouting distinction.

### The important tension: extreme effort and extreme unused capacity rarely coincide

Among **14,087 stock-era ninth-graders**, work ethic and coaching budget have a **Pearson correlation of approximately −0.405**. That correlation is descriptive; it follows in part from how work-ethic evidence is drawn from existing training-drive/coachability potential, while trainable headroom is larger for players with lower natural attribute targets. More coachable raw room and stronger work-related traits therefore do not automatically occur together.

| Ninth-grade research screen | Count |
|---|---:|
| Work ethic ≥ .65 **and** extra coaching budget ≥ 12 OVR | **80** |
| Work ethic ≥ .70 **and** extra coaching budget ≥ 12 OVR | **26** |
| Work ethic ≥ .70 **and** extra coaching budget ≥ 15 OVR | **2** |
| Work ethic ≥ .75 **and** extra coaching budget ≥ 15 OVR | **0** |
| Work ethic ≥ .75 **and** extra coaching budget ≥ 12 OVR | **5** |

This is the principal *generator-calibration question* from 2112. The user wants rare, credible careers where an inexperienced ninth-grader learns tennis quickly enough to become an important varsity or State-level singles/doubles competitor. The current population contains many pupils with extensive unused headroom and many with strong effort. Their extreme overlap is exceptionally rare. **That does not establish that the desired careers are impossible**: natural development and coaching are additive *paths of skill acquisition*, and even a player with a .65–.70 effort score can absorb substantial training. But future calibration should identify whether the exceptional **joint profile**, not merely the marginal distributions of effort and headroom, produces the careers the design is intended to admit.

### Actual instruction measured so far

The entire 2112 development ledger contains **877 coach-by-category attempts for 44 players**, distributed across seasons **2110 (287)** and **2111 (590)**:

| Attempt result | Attempts | Reading |
|---|---:|---|
| Landed attribute gains | **427** | Instruction produced some awarded raw attribute points |
| Seeded instruction did not take | **346** | Recorded as `declined`; no points awarded |
| Teaching quality below floor | **103** | Recorded as `floor`; no points offered |
| Blocked by remaining capacity/budget | **1** | Seeded instruction took but could not be allocated |
| **Total** | **877** | Every outcome remains visible in the export |

The successful offers allocated approximately **464.0 raw attribute points** across the 44 students. A separate weighted measure reports **10.416 cumulative coached OVR** across those students, with median individual coached gain **0.218 OVR**, mean **0.237**, and maximum **0.654** (Robbie Spicer, Millport boys, ninth grade). These are **very early** gains, not high-school career increases. Assistants collectively accounted for about **178.2** of those raw points; heads for **285.8**. Because this is a selected set of 44 early participants, that head/assistant split is an initial audit of allocation rather than an association-wide estimate of staff value.

**Accounting check against the profile file.** For each of those 44 players, I joined their 51 rows in `jhsaa_development_profiles.csv`, compared `coached` to `current − baseline` by attribute, and multiplied both by the exported attribute's normalized OVR weight. The reported allocation totaled **10.4158 weighted OVR** and the attributes reflected **10.4153 weighted OVR**. **No player lost even 0.01 weighted OVR** at the final ceiling check. The difference is consistent with the per-file rounding. In other words, the earlier theoretical concern about coaching points being discarded after final clipping **does not appear as an observed failure in this 2112 export**. Continue that same check as students approach their ceilings in later years; this first group has little cumulative coaching history.

The ledger's landed raw points were concentrated in touch (80.2), mental (69.2), serve (61.4), baseline (58.5), movement (58.2), return (51.0), physical (44.5) and net (41.0). These numbers show different skills being taught. They cannot yet establish which skills most improve singles or doubles outcomes, because there are too few coached students and no full before-and-after match comparison.

### Internal watchlist for the four-year career test

These are **research-only** examples of low current ability, substantial unused coaching headroom, and above-average work ethic in the ninth-grade entry cohort. They are *candidates to follow*, not forecasts of future championships. Keep the stable `player_id` when comparing later exports; school names or player names may change.

| Player and current school | `player_id` | Current internal rating | Natural target | Trainable ceiling | Work ethic | Extra coaching budget |
|---|---|---:|---:|---:|---:|---:|
| **Mary Giorgio**, Amalia Escobedo girls | `32161d6653980f91` | 29 | 46.6 | 64.8 | .698 | 18.23 |
| **Juliana Mejia**, Stone Meadows girls | `a2e10fec2603fa78` | 30 | 40.5 | 58.9 | .677 | 18.00 |
| **Lucas Maines**, Svenja Ekström boys | `54f1b90d92b6df8e` | 41 | 41.5 | 61.6 | .654 | 17.53 |
| **Luke Armstrong**, Rita Moreno North boys | `c98e9a92984247c9` | 34 | 55.7 | 72.3 | .689 | 16.12 |
| **Ava Mason**, Jean Lindgren girls | `d8171821c7abade6` | 29 | 56.1 | 72.8 | .673 | 16.03 |
| **Manolis Makris**, Tunnelwood boys | `b8b25b628f929d19` | 21 | 52.5 | 69.0 | .659 | 16.01 |

What makes the watchlist interesting is the **difference between starting skill, natural trajectory and what targeted instruction could add**. Compare where each student actually develops — e.g., Lucas Maines has strong latent serve/baseline trainability, while Luke Armstrong has much stronger net trainability. Their possible roles need not be identical. The watchlist deliberately does **not** claim these are the highest-potential players in the association or that State success can be predicted from an attribute ceiling.

## How to evaluate the model as the cohorts age

The full 2103–2111 development panel documented **325,145 year-to-year transitions across 133,683 players**, with a median ordinary yearly gain of **2 OVR**. It is the pre-stock comparison, not a verdict about this new engine. The already-documented matched synthetic replay found an approximately **+3.46 coached OVR mean over three years** with four complementary elite coaches against **+0.40** under an average staff, but that was a controlled *staff-variation prototype*, not an actual archived career or State tournament outcome.

### The immediate next season: 2113

2113 will be the first meaningful large-sample test for the **14,087 ninth-graders who held a new profile in 2112**. Compare the same `player_id` between exports; do not compare two successive ninth-grade classes as if they were the same players. For each new sophomore calculate:

- Change in the **actual current attribute vector**, in the eight coachable categories, and the corresponding weighted OVR difference. Keep the intrinsic natural trajectory and coaching-added contribution in separate columns.
- Each teacher's offers, `landed` / `declined` / `floor` / `blocked` outcomes, reported development-stock spending and **verified** actual attribute points received.
- Staff teaching portfolio, technical category quality, bond on the relevant season, player-coach fit and work ethic, plus the recorded `played` exposure share.
- The player who has no coached gain, who gets a broad spread of small gains, and who changes dramatically in one useful category. Compare *players with similar initial attributes and trainability*, not simply successful versus unsuccessful schools.
- The head-coach **2113** entering bond against 2112 competition achievements and annuity credits. A first-time title winner should see their result influence the subsequent score, subject to the recency weighting and score saturation. Watch whether promoted programs are penalized for a changed competitive level.

### The complete career: 2115 seniors, 2117 early entrants

The 2112 ninth-graders reach senior year in **2115**, and the current seventh-grade early entrants in **2117**. Build a player-season panel for both groups, with a stable `player_id`, current school and grade, completed seasons and transfers, original work/trainability profile and spendable budget, category-by-category natural growth and coaching growth, and actual singles/doubles participation.

Measure the population center **and its extreme tail**: career increases of **+20, +30, +40 and +50 weighted OVR**, the 90th/99th percentiles, variance by original skill and available capacity, graduate ability distribution, fraction of training stock utilized, and percentage of players hitting technical caps. Do not interpret a raw +40 career as proof of coaching unless a meaningful portion is attributable to taught categories rather than ordinary maturity or early-POT events.

For the extraordinary beginners, require a defensible chain: **low starting skill → ample latent developmental capacity → strong response to instruction → specific skills learned → more varsity matches / better flight results → genuine State-level competition**. A singles semifinal and a doubles final are different trajectories. In particular, a high-impact doubles coach should be able to shift net play, poaching, volley touch and doubles chemistry even when the player's singles abilities are more ordinary. Audit the fast match engine to ensure changes reach its singles/doubles pathways; the game should decide the actual postseason result.

### Coaches, annuities and program careers

Use the season table to create a longitudinal **coach-career panel**. The key is `coach_id`; head eligibility is calculated at each program `program_ident`, not by the current school name. For each head season retain age, head tenure at that program, entering bond, achievement score, years of annuity qualification, bonus from the previous completed season, veteran status, final win percentage and district/road/State/TOC outcomes. Link to actual player development via the `jhsaa_development_ledger.csv` `coach_id` and its **teaching season**, taking care that a transferred player's current exported `program_id` may no longer be the historical program where instruction occurred.

The questions to examine in sequence are substantive:

**Can a low-win development coach actually develop talent?** Compare veteran specialists on low-win teams to others with similar player stock, training opportunity and coaching technical ratings. The bond floor preserves reputation; the actual student-skill results must validate development impact.

**Does the ten-year annuity reward builders rather than simply protect already dominant programs?** Compare each qualifying coach's ninth/tenth years with their eleventh and later years. Count the raw annuity points, and separately the **change in bond actually reaching teaching offers**. At the current plateau a positive annuity can have no additional marginal multiplier. Stratify by district success, State outcomes, school move and team strength.

**Do young coaches gain a credible path upward?** Track incoming heads with initially neutral scores, including those who improve losing programs. Compare the unadjusted year-on-year point component with a realignment-relative estimate before changing that rule. Look for future achievement credit instead of expecting a 2112 win to show up in a 2112 entering bond.

**Does specialist staff composition matter beyond one effective coach grade?** Repeat the matched-player, fixed-seed tests using actual 2112 coach portfolios; remove each head and assistant in turn, compare overlapping versus complementary portfolios, and test a change in one assistant without changing the player's latent stock. Track distinct *attributes* developed, not only OVR. Preserve a separate matched experiment in which lineup opportunities are allowed to change as a consequence of coaching.

## Calibration decisions to revisit — not changes made by this report

**Head-coach bond plateau.** With five history seasons, about **5.9% of current heads** are already at **1.1071**. Of annuity holders, **88 of 489 (18.0%)** are at that same plateau. Decide whether the annuity's value should remain principally an earned score at the very top, or whether a gentler score-to-bond curve should preserve marginal room while protecting the development economy. Run a full-world test before raising the multiplier ceiling.

**Winning percentage under realignment.** The 2112 promotion/demotion effect is large enough to materially move the ±10 year-on-year point component. Evaluate class-relative improvement as a *shadow metric* alongside the live formula, including young coaches and promoted district champions. Do not silently substitute it into historical bond awards.

**Extreme work ethic × trainability.** The negative association between starting potential-related work traits and unused coaching budgets may make the intended rare four-year transformation less likely than the separate marginal distributions suggest. Test cohorts under genuine coaching and exposure first. If the rare career is systematically absent, adjust how latent work/learning disposition and additional skill trainability coexist, **without** replacing the user's separate natural-development system or producing universal superstars.

**Coaching-point accounting over a full career.** The first 44 coached students show no consequential gap between recorded and realized gains. This particular failure has **not** appeared in 2112. As players near trainable ceilings, repeat the per-attribute `coached` versus `current−baseline` check each season to determine whether the final-cap clipping can leave recorded budget spending ahead of actual skill. Only investigate a code adjustment if the long-run evidence warrants it.

**Evidence of real competitive conversion.** Gains in an attribute alone are an intermediate output. Match and flight results, ranking changes, singles/doubles choices, varsity participation, individual State qualification and bracket outcomes tell us whether a player became meaningfully better at tennis. Use class and postseason-format context rather than equating all 28 championship fields.

## Source definitions and reproducibility

All combined counts were independently computed from **both** `2112/boys` and `2112/girls` directories. The source zip is the October 2026 research export, world **2038**, JHSAA season **2112**. CSV rows are not independent for every purpose: program history repeats years, coach-season files repeat coaches across years, and attribute profiles repeat players **51 times**. Every denominator below describes its actual unit.

| Question | File / exact join | Filter or calculation |
|---|---|---|
| Current player population | `players.csv` | One row per `player_id` per gender; stock when `work_ethic` is populated |
| Current heads and bond | `jhsaa_coach_seasons.csv` | `season_year == 2112` **and** `slot == head`; read bond as **entering** this season |
| Annuity / veteran groups | Same | `bond_annuity_active`, `bond_veteran_protected`; count intersection once |
| Head technical profile | `jhsaa_coaches.csv` | Join on `coach_id`; current technical grade is distinct from archived bond |
| Previous/current program outcome | `jhsaa_program_history.csv` | One row each for `season_year in {2111,2112}`, joined on stable `program_id`; parse archived season `record` |
| Realignment events | `jhsaa_realignments.csv` | Event timestamp `season_year == 2038`; reconcile with **actual** 2111→2112 classification change in program history |
| Coaching offers | `jhsaa_development_ledger.csv` | One row per player × historical coaching season × coach × category; include failed attempts |
| Actually realized skill | `jhsaa_development_profiles.csv` | Match on `player_id` and `attribute`; compare `coached` to `current−baseline`; weighted total uses **exported** `ovr_weight` |
| Cohort tracking | Successive years' `players.csv` and profile/ledger tables | Match `player_id` across exports, retain `grade`, enrollment and transfers, and never join by player or school display name |
| Competitive results and exposure | `duals.csv`, `lines.csv`, `line_players.csv`, `jhsaa_individual_history.csv` | Follow varsity results (`level=v`) and actual player/flight participation; JV separate |
| Context beyond coaching | Supplied `2112-jhsaa-season-review.md` | Championship routes, first-time historical titles, Circuit, qualifiers, realignment and participation; checked against corresponding export tables when available |

**What cannot be established from one export:** a ninth-to-twelfth-grade effect of the new model; an individual causal coaching effect; independent verified changes in specific students' ability from 2111 to 2112 if no prior new-stock profile exists; the eventual prevalence of beginners who reach State; and whether class-relative bond scoring is preferable to the current raw calculation. Any subsequent analysis must identify the later exports it actually used rather than republishing this first-year cross-section as a longitudinal result.

**Bottom line:** The 2112 system has a populated, auditable coaching reputation economy, and it is beginning to create new developmental profiles. It already honors two important program careers — younger coaches accumulating achievements and veteran teachers whose usefulness should survive a difficult season. The significant next question is no longer whether those ratings exist; it is **whether people who can teach different skills actually change which players become competitive**, in a way the game can explain from its own records.