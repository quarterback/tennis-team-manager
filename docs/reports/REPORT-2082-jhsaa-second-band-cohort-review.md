# JHSAA 2082 — second talent-band cohort review

**Status:** first full review of the second post-PR-436 JHSAA season, using the complete 2082 boys/girls research export and comparing directly with 2080 and 2081.

2082 is analytically valuable because the association is now halfway through the talent-band transition. Grades 9 and 10 are band-era cohorts; grades 11 and 12 are still legacy classification-generated cohorts. That makes the new and old systems visible side-by-side inside the same rosters.

The central result is that the new model is working exactly where it should: program-to-program variance is widening, within-program cohort spread stays narrow, classification no longer predicts the ability of new cohorts, matchup gaps are widening sharply, and scorelines are finally moving in response. At the same time, whole-team variance is only beginning to move because half the roster population is still legacy-generated.

---

## 1. Two band-era cohorts now exist, and the split is extremely clean

Program-mean freshman strength:

| | 2080 | 2081 | 2082 |
|---|---:|---:|---:|
| Boys SD of program freshman means | 8.26 | 10.63 | **11.05** |
| Girls SD | 7.44 | 10.63 | **10.95** |
| Boys median within-program freshman spread | 31 | 23 | **23** |
| Girls median spread | 28 | 24 | **24** |

The 2081 cohort signal did not regress. The second band-era cohort reproduces it almost exactly: greater variance **between programs**, narrower spread **within programs**.

2082 by grade makes the regime boundary explicit:

### Boys

| Grade | Program-mean SD | Median within-program spread | Correlation with 1A→9A class |
|---|---:|---:|---:|
| 9 | **11.05** | **23** | **-0.01** |
| 10 | **11.56** | **23** | **0.01** |
| 11 | 9.50 | 34 | 0.49 |
| 12 | 9.65 | 34 | 0.55 |

### Girls

| Grade | Program-mean SD | Median within-program spread | Correlation with 1A→9A class |
|---|---:|---:|---:|
| 9 | **10.95** | **24** | **0.02** |
| 10 | **11.51** | **25** | **0.00** |
| 11 | 8.86 | 31 | 0.52 |
| 12 | 9.26 | 30 | 0.56 |

This is the strongest validation of the design available so far.

> **Grades 9–10 behave like program-band cohorts. Grades 11–12 still behave like classification cohorts.**

The new cohorts have almost no class/talent relationship and much more program-to-program variance. The old cohorts retain the previous class gradient and much wider internal ladders.

---

## 2. Whole varsity rosters are now starting to move

Because only half the player population is band-era, aggregate team strength should not yet look like a fresh save. But unlike 2081, the movement is now visible.

Top-11 team-strength SD:

| | 2080 | 2081 | 2082 |
|---|---:|---:|---:|
| Boys | 8.26 | 8.16 | **8.83** |
| Girls | 7.73 | 8.01 | **8.65** |

The low tail is also appearing:

- boys weakest top-11 program: 33.4 → 29.7 → **27.6**;
- girls: 29.9 → 25.4 → **24.6**.

Programs under 30 remain rare because two legacy cohorts still lift most rosters, but they now exist. The full distribution should widen much more in 2083 and especially 2084.

---

## 3. Classification no longer determines the new talent pool

Among ordinary 1A–9A programs, 2080 freshman class means still climbed materially with classification. By 2082 they are almost flat.

### Boys freshman class means, 2082

- 1A 37.0
- 2A 38.9
- 3A 36.1
- 4A 35.9
- 5A 36.1
- 6A 36.7
- 7A 36.7
- 8A 35.5
- 9A 38.2

Range: **3.35 points**.

### Girls

Range: **2.94 points**.

That is the intended model: classification changes depth through roster size; it does not give each individual draw a stronger ability distribution.

---

## 4. Matchup composition is changing much faster than headline scorelines

Line-level OVR-gap distribution across all varsity matches:

| Gap band | 2080 | 2081 | 2082 |
|---|---:|---:|---:|
| 0–6 | 54.83% | 51.33% | **45.12%** |
| 7–14 | 33.49% | 34.60% | **35.51%** |
| 15–21 | 8.69% | 10.25% | **13.28%** |
| 22–28 | 2.31% | 2.90% | **4.52%** |
| 29+ | 0.67% | 0.92% | **1.57%** |

Useful rollups:

- 15+ gap matches: **11.68% → 14.07% → 19.37%**;
- 22+: **2.99% → 3.82% → 6.09%**;
- 29+: **0.67% → 0.92% → 1.57%**.

That is the structural change the old system could not produce.

---

## 5. Scoreline realism is now moving materially in year two

Across both genders, all varsity phases:

| Set | 2080 | 2081 | 2082 |
|---|---:|---:|---:|
| 6-0 | 4.05% | 4.32% | **4.91%** |
| 6-1 | 10.75% | 11.02% | **11.83%** |
| 6-2 | 17.42% | 17.52% | **17.98%** |
| 6-3 | 21.64% | 21.65% | **21.36%** |
| 6-4 | 23.53% | 23.25% | **22.50%** |
| 7-5 | 10.98% | 10.82% | **10.45%** |
| 7-6 | 11.64% | 11.43% | **10.97%** |

Three-set match rate:

- 2080: **41.06%**
- 2081: **40.14%**
- 2082: **37.81%**

2081 only nudged the aggregate distribution because one cohort was not enough to change the matchup population much. 2082 shows the compounding effect: larger gaps are materially more common and the scoreline mix follows.

The engine still should not be retuned yet. There are two more legacy cohorts to graduate.

---

## 6. Non-district scheduling is no longer normalizing the association

Using regular non-district duals and current top-11 strength:

### Boys

| | 2080 | 2081 | 2082 |
|---|---:|---:|---:|
| Opponent-strength correlation | .749 | .502 | **.340** |
| Median team-strength gap | 2.91 | 4.82 | **6.09** |
| 20+ team gaps | 0.50% | 2.54% | **5.68%** |

### Girls

- correlation: .773 → .502 → **.350**;
- median gap: 2.73 → 4.73 → **6.09**;
- 20+ gaps: .35% → 1.72% → **5.33%**.

This matters because 2082 now contains both mechanisms at once: the scheduler stopped matching on strength in 2081, and the actual program-strength distribution is now beginning to widen underneath it.

---

## 7. The old classification résumé gradient is beginning to compress

For boys programs with top-11 strength between 50 and 55:

### 2081

- 1A: average opponent 45.2, regular-season W% .738
- 9A: opponent 59.8, W% .259

### 2082

- 1A: opponent 46.2, W% **.686**
- 9A: opponent 57.9, W% **.308**

The gradient remains substantial because the upper half of each roster is still legacy-generated and league/classification structure remains real. But it is moving in the expected direction: lower-class schedules are getting harder relative to their own absolute quality, and upper-class schedules less exclusively elite.

2083–2084 will tell us how much of the old record distortion was legacy talent structure versus unavoidable classification competition.

---

# Competitive season

## 8. State became more hierarchical again

| Metric | 2080 | 2081 | 2082 |
|---|---:|---:|---:|
| Lower-seed State wins | 33.4% | 30.9% | **26.6%** |
| One-point State duals | 45.4% | 41.7% | **37.2%** |
| No. 1 seed champions | 7/24 | 11/24 | **9/24** |
| Top-four champions | 18/24 | 19/24 | **19/24** |
| First-time champions | 8 | 8 | **8** |
| Deepest champion seed | 29 | 10 | **9** |

This is consistent with the stated purpose of the talent-band change: more program inequality, not engineered parity.

It is also not ossification. Eight programs won their first championship for the third straight season.

---

## 9. Eight first-time champions again

### Boys

- Pacific Gate — 8A, seed 9, rank 1, 37-4
- Monte Blanco — 3A, seed 3, rank 2, 24-3
- Ashbrook — Group 3, seed 2, rank 2, 33-6

### Girls

- Averill — 4A, seed 9, rank 6, 28-8
- Bush — 5A, seed 2, rank 3, 29-5
- Goldbank County — 3A, seed 1, rank 1, 38-2
- Kishwaukee — Group 2, seed 4, rank 5, 37-4
- Riverview — Group 3, seed 9, rank 6, 29-4

Pacific Gate is the biggest one-year championship rise: 16-14, class rank 37 and out in Challengers in 2081 → 37-4, rank 1 and 8A champion.

---

## 10. Repeat champions and dynasties remain real

Eight 2081 champions repeated in 2082:

- Baptist boys 7A
- Baptist girls 7A
- Cliffside boys 9A
- Mater Dei girls 9A
- Porterfield boys 2A
- Pine Eagle girls 2A
- Banfield Day girls 1A
- Toussaint boys Group 2

Baptist swept 7A again and now owns:

- boys: **14 titles**;
- girls: **15 titles**.

Mater Dei followed its historic 45-0 2081 season with **35-1 and another 9A title**, now eight total.

Banfield Day swept the 1A titles in 2082, with the boys winning from seed 2 and girls from seed 1.

There were no undefeated programs this season, so the historical "every undefeated season won State" streak remains intact without a new case.

---

## 11. The first band-era players are already becoming stars

Several of the prominent 2081 freshmen are now sophomore award winners:

- **Nanna Bah**, Jackson Hole: 97/97 freshman in 2081; 100/100 sophomore in 2082; **Group 1 girls POY**, 32-2.
- **Amelia McCracken**, California Canyons: 90/90 freshman; 92/92 sophomore; **3A girls POY**, 29-4.

The second band-era freshman class immediately added more:

- **Sachin Ralte**, Clinton: grade 9, 88/95, **7A boys POY**, 34-4.
- **Carson Perez**, Quarmont: grade 9, 98/98, **3A boys POY**, 29-4.

This is important context for the program-band model: elite players are now emerging across classifications without needing the classification itself to create their ability level.

---

## 12. Individual State became more orderly overall, but still produced deep winners

State individual championships only (144 flights):

| | 2080 | 2081 | 2082 |
|---|---:|---:|---:|
| No. 1 champions | 82 | 72 | **75** |
| Top-four champions | 128 | 120 | **129** |
| Mean champion seed | 2.39 | 2.55 | **2.25** |
| Deepest champion | 21 | 11 | **16** |

Notable deep 2082 winners include:

- Kernwood County boys 6A S1 — seed **16**;
- Riverside girls 5A D1 — seed **14**;
- Grant girls Group 1 S2 — seed 9;
- Foothills Christian girls 1A D3 — seed 9.

Team State is becoming more hierarchical, but individual State retains meaningful tail events.

---

# Committee / field behavior

## 13. At-large validation declined for a second year

Association-wide committee teams:

| | 2080 | 2081 | 2082 |
|---|---:|---:|---:|
| At-larges | 240 | 240 | 240 |
| Won ≥1 State match | 106 | 82 | **77** |
| Validation rate | 44.2% | 34.2% | **32.1%** |
| Total State wins | 135 | 103 | **97** |

This is likely connected to the widening competitive hierarchy: the bottom of a field is becoming less interchangeable with its middle.

The field cutoffs themselves remain mostly close to their nominal sizes, so this is not yet a reason for wholesale contraction.

Group 2 in 2082:

- boys: 2 of 8 at-larges won;
- girls: 1 of 8;
- best omitted consensus ranks remain around 40–42.

That still supports the 40-team field as a selection architecture, even though the new bottom seats are becoming less competitive.

Group 3 remains unresolved:

- boys: 4 of 8 at-larges won, producing seven total wins;
- girls: 0 of 8 won.

The old question remains open: 32 improves selection coverage, but a compact 28-team field with more committee discretion may still provide better competitive density.

---

# Transfer persistence

## 14. The smaller 2081 transfer class was not only efficient; it was durable

The 2081 class contained 572 moves. Most were rising seniors, so only **92** remained in high school for 2082.

All 92 are found in the 2082 player population.

**91 of 92 remain at the school they transferred to.**

The lone repeat mover is Rori Haulcy, who moved from Cole Valley to Green River.

Among returning 2081 movers who stayed at the destination:

### Deep clearing

- 50 returning players;
- median destination rank: **4**;
- 88% top 11;
- 94% with 10+ varsity appearances;
- median 25.5 varsity appearances.

### Role liberation

- 21 returning players;
- median rank: **1**;
- 100% top 11;
- 100% with 10+ varsity appearances;
- median 25 varsity appearances;
- median 25 singles appearances.

### Feeder

- 14 returning players;
- median rank 3;
- 100% top 11;
- 100% 10+ varsity;
- median 26 appearances.

### Reload

- 6 returning players;
- median rank 1;
- 100% top 11;
- 100% 10+ varsity;
- median 24 singles appearances.

The 2081 policy change therefore solved both first-year conversion and second-year persistence.

---

## 15. Reloads were much more durable this cycle

All four 2081 reload hosts remained State teams in 2082:

| Program | 2081 class rank | 2082 class rank | 2082 result |
|---|---:|---:|---|
| Telfair Country Day boys | 2 | **7** | Octofinalist |
| Plainfield boys | 1 | **13** | Round of 32 |
| Bernal Heights girls | 8 | **9** | Round of 32 |
| Rogue Valley girls | 3 | **8** | Octofinalist |

This contrasts with the 2079 reload cycle, where three of four targets collapsed out of State the following year.

Part of the difference is cohort composition: several 2081 reload arrivals were juniors and remained as senior anchors in 2082. The mechanism still behaves like top-end roster shock, but it can persist when the imported class is not entirely graduating.

---

## 16. Rebuild durability remains uneven

The 18 weak-program rebuild hosts had very mixed second-year outcomes.

Some remained or became credible:

- D. Eisenhower boys: State again, quarterfinalist;
- Tamarack boys: State again;
- Tower Grove boys: 11-15/rank57 → **21-10/rank29**, State;
- Dogpatch girls: 18-12/rank21 → **19-8/rank5**, State.

Others collapsed sharply:

- Harlan boys: 20-10/rank14 → **1-29/rank85**;
- Jefferson Science boys: rank41 → **82**;
- Lago Vista boys: rank23 → **79**;
- North Coast girls: rank50 → **85**;
- Ferris girls: rank63 → **84**;
- Tower Grove girls: rank58 → **86**.

This reinforces the existing distinction: concentrated rebuild cohorts can create structural residue, but they are not guaranteed to transform the underlying pipeline. Program bands may eventually give us a cleaner explanation for which hosts can sustain a rebuild and which naturally revert.

---

# Governing conclusions after 2082

1. **Do not alter the talent-band architecture.** The year-two evidence is unusually clean: grades 9–10 are band-shaped; grades 11–12 are legacy-shaped.
2. **Do not retune the match engine yet.** The matchup-gap distribution is still moving rapidly as the new cohorts enter.
3. **Continue tracking the 2080→2084 sequence.** 2083 should be the first season where most varsity contributors are band-era; 2084 is the first fully converted four-grade population.
4. **Keep strength out of ordinary non-district matchmaking.** The old résumé normalization is visibly unwinding.
5. **Treat declining at-large validation as a real signal but not yet a field-size mandate.** Competitive hierarchy is widening faster than field architecture has adapted.
6. **The smaller transfer market remains the correct doctrine.** The 2081 cohort retained roles extraordinarily well into 2082.
7. **Role liberation remains the strongest transfer mechanism.** Returning role movers are overwhelmingly S1-level players at their new schools.
8. **Reloads remain powerful and can persist when the age structure permits it.**
9. **Rebuild hosts need a durability model.** The new talent-band identity data may become useful for distinguishing temporary cohort rescue from programs whose future pipeline can sustain the intervention.

The most important 2082 result is that we no longer have to infer whether the new talent model is working from aggregate scorelines. The age split proves it directly: the two new cohorts have the intended band signature, the two old cohorts retain the legacy class signature, and the whole association is moving in the predicted direction as the population turns over.
