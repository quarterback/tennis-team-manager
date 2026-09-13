# JHSAA 2081 — Talent Tier, Scheduling, and Transfer-Market Validation

**Status:** first full-season validation report after PR #436 (`JHSAA program talent tiers; non-district draw stops matching on strength`) and the smaller 2081 transfer intake.

This report should be read beside:

- `docs/AAR-jhsaa-program-talent-tiers.md`;
- `docs/reports/REPORT-2080-schedule-strength-resume-compression.md`;
- `docs/reports/REPORT-2078-2080-jhsaa-longitudinal-review.md`;
- `docs/reports/DOCTRINE-2078-jhsaa-transfer-policy.md`.

2081 is a transition season. The scheduling change applies immediately, but the talent-tier change is **cohort-era gated**: only the new freshman cohort is generated from program bands in the existing save. The remaining three grades are legacy classification-generated cohorts. Whole-roster measurements therefore should not be compared to the fresh-save calibration as though the rollout were complete.

---

## 1. Executive findings

### A. The scheduling change worked immediately

Early non-district strength matching fell dramatically.

| metric | 2080 boys | 2081 boys | 2080 girls | 2081 girls |
|---|---:|---:|---:|---:|
| early opponent-strength correlation | .844 | **.434** | .822 | **.448** |
| early median team-strength gap | 2.27 | **5.45** | 2.27 | **5.50** |
| early duals with 20+ OVR team gap | 0.1% | **3.1%** | 0.2% | **1.8%** |
| regular opponent-strength correlation | .614 | **.488** | .623 | **.496** |
| regular median team-strength gap | 4.45 | **5.27** | 4.18 | **5.09** |

The ordinary non-district schedule is no longer manufacturing near-peer records by construction.

### B. The first talent-band cohort behaves exactly as designed

Freshman program means lost the old classification ladder and gained much more between-program variance.

| metric | 2080 boys freshmen | 2081 boys freshmen | 2080 girls freshmen | 2081 girls freshmen |
|---|---:|---:|---:|---:|
| SD of program freshman mean OVR | 8.26 | **10.63** | 7.44 | **10.63** |
| correlation: 1A→9A class level vs freshman mean | **.967** | **-.017** | **.982** | **.115** |
| range among 1A–9A class freshman means | 12.77 | **3.86** | 11.02 | **3.45** |

In 2080, boys freshman means rose from roughly 32 in 1A to 45 in 9A. In 2081 the class means are essentially flat, roughly 35–39 across the ladder. Girls show the same collapse of the class-talent relationship.

That is the intended model:

> **program band determines ability; classification determines roster size/depth.**

### C. Whole-roster talent distribution has not changed much yet — correctly

Because only one of four cohorts is band-generated:

| metric | 2080 boys | 2081 boys | 2080 girls | 2081 girls |
|---|---:|---:|---:|---:|
| top-11 team-strength SD | 8.26 | 8.16 | 7.73 | 8.02 |
| median best-minus-11th spread | 35 | 35 | 33 | 32.5 |
| programs under 30 top-11 mean | ~0% | 0.2% | 0.1% | 0.3% |

Do **not** interpret this as the tiers failing. The freshman cohort already shows the structural change. The association should converge toward the fresh-save distribution over the next three graduating cycles.

### D. The smaller 2081 transfer market dramatically outperformed generic 2080 clearing

The 2081 intake was 572 moves rather than 900:

- 360 deep clearing;
- 140 role liberation;
- 60 feeder/down-flow;
- 12 reload/up-flow.

Every mover appears at the intended 2081 destination.

| mechanism | movers | median dest. rank | top 11 | 10+ varsity apps | median varsity apps | median singles apps |
|---|---:|---:|---:|---:|---:|---:|
| deep clearing | 360 | **8** | **79.2%** | **86.1%** | **22** | 0 |
| role liberation | 140 | **2** | **99.3%** | **98.6%** | **27** | **26** |
| feeder/down-flow | 60 | **6.5** | **93.3%** | **91.7%** | **27** | 1 |
| reload/up-flow | 12 | **2** | **100%** | **100%** | **32** | **28.5** |

The deep-clearing result is the key comparison. In 2080 generic clearing produced only about 40% top-11 placement, 41% with 10+ varsity appearances, and a median of six varsity appearances. The reduced, destination-verified 2081 market produced **79% top-11 placement and a median 22 varsity appearances**.

The lesson is now stronger than it was after 2080:

> **Move fewer players, but require a real destination role.**

---

# Talent-tier rollout

## 2. The class-based freshman talent ladder disappeared immediately

The 2080 freshman class still reflected `_TALENT` by classification.

### Boys class means, grade 9

2080 examples:

- 1A: 32.2
- 5A: 40.5
- 7A: 43.0
- 9A: 45.2

2081:

- 1A: 35.9
- 5A: 38.2
- 7A: 37.0
- 9A: 37.6

The 1A→9A correlation moved from **.967 to -.017**.

### Girls class means, grade 9

2080 examples:

- 1A: 30.1
- 5A: 36.4
- 7A: 38.6
- 9A: 40.1

2081:

- 1A: 36.1
- 5A: 38.3
- 7A: 36.5
- 9A: 37.3

The class correlation moved from **.982 to .115**.

This is the cleanest possible implementation validation. It shows that PR #436 did not merely widen the old class bands. It replaced classification ability with program-level talent identity while leaving class-based roster-size depth intact.

## 3. Elite freshmen now appear throughout the classification structure

The strongest 2081 freshmen are scattered across the ladder rather than clustering at 8A/9A.

Examples:

### Boys

- Byron Muagututi'a — 94 OVR, 2A
- Chief Knapp — 93, 5A
- Jorge Cook — 91, 9A
- Bryson Fidler — 90, Group 1
- Kaleb Briones — 90, 1A
- Amari Blaylock — 90, 7A

### Girls

- Nanna Bah — 97 OVR, Group 2
- Yasmin Krogh — 93, Group 3
- Kendall Schmidt — 91, Group 1
- Cecilia Farrer — 91, 8A
- Amelia McCracken — 90, 3A

The first band-era freshman cohort already includes a class Player of the Year: **Alayna Harris, Star Valley Regional, Group 2 girls, grade 9**.

The point is not that small classes should own the elite tail. It is that enrollment no longer mechanically decides where elite individual talent can exist.

## 4. Whole-program extremes are beginning to appear but are still mostly legacy/blended rosters

The full-team floor moved only slightly in 2081 because three legacy cohorts remain. The top end became more volatile, with several programs posting unusually high top-11 means, but those rosters mix returning legacy players, normal development, transfers, and the first band cohort.

Do not attribute any single 2081 varsity roster entirely to its talent tier yet.

The correct rollout checkpoints are:

- 2081: one band cohort;
- 2082: two;
- 2083: three;
- 2084: first fully band-generated four-grade roster population.

The fresh-save calibration from the AAR remains the appropriate expectation for the completed state, not for 2081.

---

# Scheduling and scoreline realism

## 5. Ordinary schedules stopped normalizing strength

The strongest immediate effect of PR #436 is schedule structure.

### Early phase

Boys:

- strength correlation .844 → **.434**
- median gap 2.27 → **5.45**
- 20+ gaps 0.1% → **3.1%**

Girls:

- .822 → **.448**
- 2.27 → **5.50**
- 0.2% → **1.8%**

### All varsity duals

Boys:

- median team gap 4.18 → **5.00**
- 20+ gap duals 1.18% → **2.34%**
- 30+ gap duals 0.05% → **0.24%**

Girls:

- median gap 4.00 → **5.00**
- 20+ gap duals 0.71% → **2.04%**
- 30+ gap duals 0.02% → **0.17%**

This is a real change even before the full talent-band distribution exists.

## 6. Scorelines moved in the intended direction, but modestly

Using a consistent export-wide varsity score calculation:

| metric | 2080 | 2081 |
|---|---:|---:|
| 6-0 sets | ~4.00% | **~4.27%** |
| 6-1 sets | ~10.64% | **~10.89%** |
| 6-4 sets | ~23.28% | **~22.98%** |
| three-set matches | 41.06% | **40.14%** |

The early non-district phase moves more visibly:

- boys 6-0: 3.75% → **4.21%**;
- boys 6-1: 9.86% → **10.94%**;
- girls 6-0: 3.66% → **4.13%**;
- girls 6-1: 10.19% → **10.89%**.

This is the correct direction but nowhere near the fully banded fresh-save calibration or the Oregon reference. That is expected: the schedule changed immediately, but only one roster cohort changed.

Do not retune the point engine from 2081 alone.

## 7. The .500-team résumé phenomenon persists — but its interpretation is changing

Removing ordinary non-district strength matching did **not** eliminate the fact that similarly strong teams carry different records by classification.

For boys teams with a top-11 mean of 50–55 in 2081:

- 9A average opponent strength: ~60.0; average W%: **.249**
- 5A: ~54.8; **.422**
- 4A: ~52.5; **.509**
- 1A: ~46.4; **.713**

Girls show the same gradient.

This does **not** mean the scheduling change failed. Three legacy cohorts still make upper classifications stronger on average, and district play plus the same/adjacent-class gate remain intact. Ordinary strength matching was only one source of résumé compression.

The important difference is conceptual:

> a difficult résumé is now increasingly an emergent property of the actual competitive environment, rather than a scheduler deliberately finding a same-strength opponent.

This should be re-measured through 2084. As legacy class-generated cohorts graduate, the class-strength gradient itself should weaken if the program-band model is functioning as intended.

### 2081 examples of dangerous mediocre-record State teams

The pattern remains visible in postseason results:

- **Okefenokee boys, 8A:** 13-16, seed 48, reached the State quarterfinal;
- **Bend Senior girls, 8A:** 14-14, seed 48, reached the quarterfinal;
- **Ransoms Landing girls, 1A:** 22-15, reached the State final;
- **Averill girls, 4A:** 18-14, reached the State final;
- **Calasanz Prep boys, 4A:** 18-13, reached the quarterfinal.

The user theory remains supported: raw record alone can badly understate tournament danger. The weird postseason formats contribute, but schedule ecology clearly contributes as well.

---

# 2081 transfer-market validation

## 8. Role liberation is now the strongest repeatable mechanism

2081 role liberation:

- 140 movers;
- median destination rank: **2**;
- 99.3% top 11;
- 98.6% with 10+ varsity appearances;
- median 27 varsity appearances;
- median 26 singles appearances;
- **126 of 140 moved from a doubles-primary 2080 role to a singles-primary 2081 role**.

Examples:

- Charles Johnson: Malpais D1 → Lago Vista S1, 36 singles appearances;
- Luke Inman: Bellacosta D2 → Harlan S1, 30 singles appearances;
- Michael Naomoto: De La Salle D2 → Carondelet S1, 29 singles appearances;
- Radu Nedelcearu: Montclair D2 → Okefenokee S1, 29 singles appearances;
- Harper Payton: Dry Lake D2 → Observatory S1, 29 singles appearances;
- Peter Marshall: Forest Park D1 → Huerta S1, 27 singles appearances.

This is exactly the career-liberation mechanism the doctrine was trying to create.

## 9. Deep clearing improved because the market got smaller

2080 generic deep clearing had become the weakest transfer mechanism:

- median destination rank 13;
- ~40% top 11;
- ~41% with 10+ varsity appearances;
- median six varsity appearances.

2081 cut the mechanism nearly in half, from 717 to 360, and imposed a stronger destination-role screen.

Result:

- median rank **8**;
- **79.2%** top 11;
- **86.1%** with 10+ varsity appearances;
- median **22** varsity appearances;
- only ~2% received no varsity use.

This is strong evidence that 2080's problem was not that congestion clearing was inherently bad. It was that the market had expanded beyond the population of players who actually had meaningful better destinations.

## 10. Feeder/down-flow worked well

The 60 feeder movers produced:

- median destination rank 6.5;
- 93.3% top 11;
- 91.7% with 10+ varsity appearances;
- median 27 varsity appearances.

All 12 designated feeder hosts made State.

Notable team results:

- Portola-Caverly boys: State finalist;
- Raahe boys: Group 3 finalist;
- Lieksa girls: Group 3 finalist;
- Seamus Town girls: 2A quarterfinal;
- Sutter Basin girls: 2A quarterfinal.

The feeder model remains useful when the destination is a specific role rather than a generic smaller-class landing spot.

## 11. Reloads remained extremely high leverage

All 12 reload players finished top 11; median destination rank was 2 and median singles use 28.5.

The four reload hosts:

| program | 2080 mean rank | 2081 mean rank | 2081 record | postseason |
|---|---:|---:|---:|---|
| Telfair Country Day boys | 83.1 | **3.6** | 28-4 | State |
| Plainfield boys | 78.8 | **2.1** | 34-4 | State |
| Bernal Heights girls | 79.2 | **8.7** | 20-5 | State |
| Rogue Valley girls | 82.6 | **3.6** | 29-3 | **State semifinal** |

As in 2079–2080, a three-player top-end reload can transform a roster immediately.

## 12. Rebuild hosts improved, but the results were gender-asymmetric

### Boys rebuild hosts

Median computer-rank improvement: **about 40 places**.

Seven of nine made State.

Examples:

- D. Eisenhower: mean rank 82.1 → 25.9; class rank 9;
- Huerta: 82.3 → 28.6;
- Harlan: 73.9 → 26.2;
- Lago Vista: 76.1 → 30.2;
- Tamarack: 82.0 → 42.0.

Okefenokee is especially interesting: only 13-16 and mean rank 48.3, but entered State as seed 48 and reached the **quarterfinal**.

### Girls rebuild hosts

Median mean-rank improvement: **about 22 places**.

Only two of nine made State.

Best examples:

- Dogpatch: 63.0 → 22.4;
- Observatory: 69.9 → 36.0.

Several others improved substantially without becoming State-level teams.

This mechanism should remain, but 2081 says the host-selection model should be checked separately by gender rather than assuming identical conversion.

## 13. Re-transfer should remain exceptional

Only 17 prior-year movers were moved again under the failed-placement exception.

Their 2081 results were weaker than first-time movers:

- median destination rank 10;
- 64.7% top 11;
- median 18 varsity appearances.

That is still useful enough to justify the failure exception, but it supports the rule against routine annual player churn.

## 14. Transfer honors were meaningful without dominating the elite layer

At least 28 transferred player IDs appeared in 2081 All-State selections.

Examples include:

- Zion Hughes, Telfair Country Day;
- Edgar Diggs, Cheney;
- multiple feeder arrivals at Portola-Caverly, Michaeux, Windrow, Raahe, Lieksa, Vermeer and Seamus Town;
- Kayleigh Strong, Bernal Heights;
- Magdalena Weaver, Rogue Valley.

No 2081 transfer mover won a class Player of the Year award or an Individual State championship.

That is a healthy outcome: the transfer system changed roles and team contexts without simply manufacturing the association's elite individual honors.

---

# Donor integrity

## 15. Source-program decline is the main transfer warning from 2081

Recipient outcomes were excellent, but donor results show a signal worth acting on.

Median change in computer mean-rank from 2080 to 2081:

### Boys

- non-donors: approximately **0 places**;
- one departure: -6.1;
- two departures: -0.9;
- three departures: -5.2;
- four departures: **-6.9**.

### Girls

- non-donors: **+1.7**;
- one departure: -4.7;
- two departures: ~0;
- three departures: **-11.9**;
- four departures: **-10.2**.

This is observational, not causal: graduation, cohort variation and ordinary development all contribute. But the contrast with non-donors is large enough to treat as a source-integrity warning.

Examples of four-departure programs that also fell sharply include North Coast boys and Quarry Workers girls. These declines cannot be assigned entirely to transfers from the export alone, but they are exactly the kind of source outcome the doctrine says to monitor.

### 2082 implication

Do not automatically lower the global donor cap from four solely from one season. Instead:

1. preserve the four-player hard ceiling;
2. make the **fourth departure harder to approve**;
3. require a stronger explicit internal replacement chain for departure three and especially four;
4. report donor post-transfer top-11 strength and ranks 5–14, not only mover outcomes.

---

# State and committee environment

## 16. State became somewhat more hierarchical in 2081

Combined boys/girls State results:

| metric | 2080 | 2081 |
|---|---:|---:|
| lower-seed wins | 33.4% | **30.9%** |
| one-point duals | 45.4% | **41.7%** |
| No. 1-seed champions | 7/24 | **11/24** |
| top-four champions | 18/24 | **19/24** |
| deepest team champion seed | 29 | **10** |

This is directionally consistent with a system beginning to tolerate more true inequality, but 2081 has only one band-generated cohort. Treat it as an early signal rather than a settled causal effect.

The association still produced **eight first-time State champions**, matching 2080:

### Boys

- Olive Head, 8A;
- Forge Hollow, 3A;
- Toussaint, Group 2.

### Girls

- Starfield, 6A;
- North Averill, 5A;
- Veles Park, 3A;
- Burdensome, Group 2;
- Uplands, Group 3.

Notable continuity:

- Gagarin boys won a **third consecutive 4A title** (2079–2081) and eighth overall;
- Banfield Day girls repeated in 1A;
- Nora Caudill, Grace Christian, completed the extraordinary **four-year sweep of 1A girls Player of the Year**, winning as freshman, sophomore, junior and senior.

## 17. Individual State remained orderly

| metric | 2080 | 2081 |
|---|---:|---:|
| No. 1 individual champions | 82/144 | 72/144 |
| top-four champions | 128/144 | 120/144 |
| mean champion seed | 2.39 | 2.55 |
| deepest champion | 21 | 11 |

There was somewhat less No. 1 dominance but also no extreme No. 21-type champion this year.

## 18. At-large validation fell sharply

Association-wide committee bids remained 240.

- 2080: 106/240 won at least once, 44.2%; 135 total wins.
- 2081: **82/240 won at least once, 34.2%; 103 total wins.**

This may be another early sign of a wider hierarchy: the bottom of the fields is less interchangeable with the middle than in the compressed 2078–2080 environment.

### Group 2

The 40-team cut line remains well calibrated by computer consensus:

- boys best omitted team: mean rank ~40.1;
- girls: ~41.6.

But only **4 of 16 Group 2 at-larges** won a State match in 2081, down from 10 of 16 in 2080.

Do not reverse the expansion from one season; the selection cutoff remains correct. Continue measuring competitive value of seeds 33–40 as band cohorts accumulate.

### Group 3

Group 3 remains the least convincing expansion.

- 2081 at-larges winning ≥1: **3 of 16**;
- boys best omitted: ~33.9;
- girls best omitted: ~31.1.

The field still solves some selection errors, but the additional teams continue to contribute little tournament value. The previously proposed **28-team / 8-committee-bid** counterfactual remains worth testing.

---

# Governing conclusions after 2081

## Talent tiers

1. **The implementation is validated at the cohort level.** The freshman class no longer has a meaningful classification-to-ability relationship.
2. Do not retune the band ranges from whole-roster 2081 numbers. Three legacy cohorts remain.
3. Recompute the same freshman diagnostics every year through 2084.
4. The critical completed-rollout target remains between-program team-strength variance and the scoreline distribution, not parity.

## Scheduling

1. Keep ordinary non-district strength matching removed.
2. Geography and the same/adjacent-class gate are enough structure for ordinary cards.
3. Keep deliberate peer-matching where it belongs: challenge/showcase/recovery mechanisms.
4. Continue measuring .500-ish teams separately; the phenomenon persists and remains relevant to postseason evaluation.

## Transfers

1. Keep the total market substantially below the 2078–2080 900-player era unless the data produces a new backlog.
2. **Role liberation is the primary mechanism.**
3. Keep deep clearing selective; 2081 proves that shrinking the candidate pool dramatically improves conversion.
4. Keep feeder placements role-verified.
5. Keep reloads rare and explicit; they remain extremely powerful.
6. Tighten the internal-replacement requirement for third/fourth departures from the same donor.
7. Do not normalize re-transfer; the failed-placement exception is enough.

## Postseason

1. Keep Group 2 at 40 for now; cut-line quality remains correct despite weaker 2081 at-large performance.
2. Group 3 remains unresolved and should still receive the 28-team/8-committee counterfactual test.
3. Do not react to the single-year decline in upset/one-point rates yet. The full talent-tier transition is incomplete.

---

## Required 2082–2084 longitudinal measurements

Each new season should append at least:

### Talent tiers

- freshman program-mean OVR SD;
- freshman class-vs-OVR correlation;
- whole-program top-11 SD;
- programs under 30 / 30–40 / 40–60 / 60+;
- median and p90 best-minus-11th spread;
- top-11 distributions by program tier if exported/available.

### Scheduling

- early opponent-strength correlation;
- early and regular median team gaps;
- 20+ and 30+ team-gap rates;
- set-score mix by phase;
- record and opponent strength for fixed team-strength bands by classification.

### Transfers

- conversion by mechanism;
- D→S role conversions;
- donor rank/strength changes by departure count;
- source replacement player grade/OVR;
- rebuild/reload persistence;
- prior-mover re-transfer outcomes.

### Postseason

- lower-seed rate;
- one-point dual rate;
- committee validation by classification;
- seeds 33–40 in Group 2;
- seeds 29–32 in Group 3;
- field cutoff against computer consensus.

2081 should be treated as **Year 1 of a four-year structural transition**, not as the final calibrated state.