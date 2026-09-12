# 2080 JHSAA Scheduling, Résumé Compression, and Playoff Performance

**Status:** analytical baseline before the planned talent-band and scheduling reforms.

**Data basis:** 2080 JHSAA research export, all classifications and both genders, interpreted alongside the current JHSAA scheduling rules.

## Executive summary

The 2080 data supports the owner's theory that the current schedule generator compresses regular-season records by matching programs too aggressively to opponents of similar strength.

This has two related effects:

1. **strong upper-classification teams are forced into disproportionately difficult schedules and can look mediocre by raw win-loss record;**
2. **average or weak lower-classification teams face materially weaker opponents and can produce much stronger records despite comparable absolute roster quality.**

This helps explain why some .500-ish teams struggle to qualify for the postseason and then perform well once admitted. The phenomenon is not caused only by postseason-format changes. It begins in regular-season opponent selection.

The scheduling code currently draws non-district opponents first by geography and then by **nearest roster strength**, under a same-classification / one-class-apart gate. That choice systematically reduces mismatch frequency and pushes teams toward equilibrium records.

This report establishes the 2080 baseline before program talent bands and any scheduling reform. The two reforms should be evaluated together: broadening talent distributions without reducing strength-matched scheduling would cause the scheduler to partially erase the new cross-program variance.

---

## 1. Current scheduling actively suppresses mismatch

The current non-district scheduling rule is not neutral with respect to team quality. Opponents are selected on:

1. geography;
2. then nearest roster strength;
3. while remaining in the same classification or one classification away.

This is visible in the 2080 schedule itself.

### Early non-district scheduling

- opponent-strength correlation: **0.84**
- median top-11 strength gap: **2.3 OVR**

### Regular district scheduling

- opponent-strength correlation: **0.64**
- median top-11 strength gap: **4.3 OVR**

The result is that a large share of the season is structurally arranged around near-peer competition.

This is useful if the sole objective is competitive duals. It is harmful if the simulation is also trying to reproduce the scoreline distribution, schedule variance, résumé ambiguity, and playoff-selection problems of real high-school tennis.

---

## 2. The same absolute-quality team produces radically different records by classification

A useful way to isolate the scheduling effect is to hold absolute roster quality approximately constant and compare teams across classifications.

For programs with a top-11 average OVR between **50 and 55** in 2080:

| Classification | Average opponent OVR | Average regular-season win % | Made State |
|---|---:|---:|---:|
| 9A | **57.5** | **.312** | 0% |
| 8A | 56.8 | .330 | 7% |
| 7A | 56.3 | .388 | 20% |
| 6A | 54.4 | .428 | 33% |
| 5A | 52.6 | .495 | 46% |
| 4A | 50.3 | **.582** | **97%** |
| 3A | 48.8 | .629 | 96% |
| 2A | 47.4 | .653 | 100% |
| 1A | 45.1 | **.747** | **100%** |

This is an extreme résumé gradient for teams of similar absolute quality.

A 52-OVR team is:

- a roughly **.300 team in 9A**;
- essentially **.500 in 5A**;
- roughly **.750 in 1A**.

Part of that difference is appropriate: classification defines the competitive environment, so a 52-OVR roster should be relatively stronger in 1A than in 9A.

But the scheduling mechanism amplifies the difference because the upper-classification team is also disproportionately scheduled against strong peers.

The 9A team in this band faces an average opponent of 57.5 OVR. The 1A team faces 45.1.

Raw record therefore contains both team quality and scheduler-induced opponent matching.

---

## 3. The pattern persists at a higher talent band

Programs with top-11 average OVR between **55 and 60** show the same structure:

- 9A: **.437** average win percentage; 32% make State
- 8A: .452; 40%
- 7A: .482; 63%
- 6A: .565; 89%
- 5A: **.647**; 91%

Again, similar absolute roster quality produces very different records and postseason access depending on classification and schedule environment.

This is the empirical basis for treating a .500 upper-classification team differently from a .500 lower-classification team.

---

## 4. Why .500 teams can become dangerous postseason teams

The owner's observation is that some teams with mediocre regular-season records struggle to reach the postseason and then perform unexpectedly well once admitted.

The 2080 data supports a two-part explanation.

### A. Schedule-strength compression

A strong team can finish near .500 because it spent the season playing other strong teams.

Its record understates its absolute playing level.

This is especially likely in the upper classifications, where similar-strength matching combines with a generally stronger talent environment.

### B. Postseason format change

The regular season and postseason do not always ask the same roster question.

Examples:

- a 6A team can accumulate a mediocre regular-season record in the universal 3S/4D league format;
- then enter a 1S/4D postseason where a different portion of the roster determines the dual;
- a team whose regular-season depth profile was merely average may be unusually well-shaped for the championship card.

The schedule can therefore understate the team's quality, and the postseason format can then expose a different competitive strength.

These are separate mechanisms and should not be conflated.

---

## 5. State participation among .400-.600 teams

Across the recent 2078-2080 period, teams in the broad .400-.600 regular-season band reached State at very different rates by classification:

- 9A: **56%**
- 8A: **65%**
- 7A: **69%**
- 6A: **67%**
- 5A: **47%**
- 4A: **77%**
- 3A: **68%**
- Group 1: **74%**

These are not simply bad teams being admitted. Many subsequently won State matches.

The important point is that a raw .500 résumé is not carrying a uniform meaning across the association.

---

## 6. This is directly connected to the scoreline-realism problem

The separate 2080 talent-band analysis found that the association produces too few blowouts:

- 6-0 sets: **4.1%** in JHSAA versus **26.4%** in the Oregon comparison sample
- 6-1: **11.0%** versus **21.5%**
- median varsity-flight OVR gap: **6.0**
- flight gaps >=30: only **0.6%**
- duals with team-strength gap >=20: only **1.2%**

Program talent bands are intended to increase cross-program talent heterogeneity.

But the current schedule generator would partially neutralize that change by continuing to seek the nearest-strength opponent available.

A newly created bottom-tier 9A school would preferentially be paired with other weak 9A/8A schools.

A newly created elite 9A school would preferentially be paired with other elite teams.

The talent distribution would widen while the schedule continued narrowing realized matchups.

Therefore the scheduling change is not optional if the objective of the talent-band work includes more realistic scoreline variance.

---

## 7. What should change conceptually

The association should not abandon structure.

Districts, geography, rivalries, classification boundaries, showcases, and postseason qualification all have independent reasons to exist.

The problem is specifically the role of **nearest strength** as a normal non-district scheduling principle.

Future scheduling should permit materially more cross-strength play.

That means allowing outcomes such as:

- a top-five program playing a No. 60 program;
- a poor team occasionally drawing an elite opponent;
- mid-level teams encountering both weaker and stronger opponents;
- local/geographic opponents being retained even when the strength gap is substantial.

The schedule should create a distribution of opponent quality rather than repeatedly solving for the closest available match.

---

## 8. Why heterogeneous schedules improve the rating systems

When schedules are deliberately strength-normalized, raw win-loss records compress toward the middle.

That makes schedule-adjusted rating systems do less meaningful work because much of the schedule-strength problem was already solved before competition began.

A more heterogeneous schedule makes tools such as ATR, TOSS, strength of schedule, court share, and expected-win models more valuable.

A 15-14 9A team with a top-20 underlying rating can then be interpreted as:

> a strong team that happened to play a difficult schedule.

That is preferable to:

> a strong team that is 15-14 because the scheduling algorithm intentionally kept feeding it similarly strong opponents until its record equilibrated.

The first is a genuine résumé problem for the selection/rating system to solve. The second is an artifact of schedule construction.

---

## 9. The target is not random scheduling

Removing nearest-strength matching does not require opponents to be selected uniformly at random.

A plausible scheduling hierarchy could continue to prioritize:

1. district obligations;
2. geography/locality;
3. rivalry and recurring series;
4. same/adjacent classification where appropriate;
5. availability;
6. a broad strength distribution rather than nearest-strength minimization.

Showcases may remain intentionally strength-sensitive because they serve a different purpose and should be evaluated separately.

The important policy distinction is:

> **ordinary scheduling should expose program inequality; showcase scheduling may intentionally organize competition around comparable programs.**

---

## 10. Baseline metrics to preserve before the reform

Future analysis should retain these 2080 measures as the scheduling baseline:

### Opponent matching

- early non-district opponent-strength correlation: **0.84**
- early median top-11 gap: **2.3 OVR**
- regular/district strength correlation: **0.64**
- regular median top-11 gap: **4.3 OVR**

### Same-absolute-strength résumé gradient

For top-11 OVR 50-55:

- 9A opponent OVR: **57.5**; W% **.312**
- 5A opponent OVR: **52.6**; W% **.495**
- 1A opponent OVR: **45.1**; W% **.747**

### Scoreline-realism baseline

- 6-0 share: **4.1%**
- 6-1 share: **11.0%**
- flight gaps >=20: **5.0%**
- flight gaps >=30: **0.6%**
- duals with team gap >=20: **1.2%**

These should be recomputed after the talent-band and scheduling changes.

---

## 11. Required post-change analysis

Once both program talent bands and revised scheduling are active, measure:

1. opponent-strength correlation by schedule phase;
2. distribution of top-11 strength gaps by schedule phase;
3. schedule-strength variance within each classification;
4. record versus absolute roster quality by classification;
5. record versus ATR/TOSS/court-share strength;
6. postseason qualification rate for .400-.600 teams by classification;
7. State win rate of teams below .550 regular-season record;
8. State performance of teams with strong underlying ratings but weak records;
9. 6-0 / 6-1 scoreline rates;
10. mismatch frequency across talent-band combinations;
11. showcase results separately from ordinary scheduling.

The goal is not for every team's record to perfectly reflect its quality.

The goal is for résumé differences to arise from a real schedule rather than from an algorithm that systematically seeks equilibrium opponents.

---

## 12. Governing interpretation

The 2080 evidence supports the following model:

> **The current system compresses both match scorelines and team records because program talent is too homogeneous across schools and ordinary non-district scheduling then further matches teams to near peers.**

Program talent bands address the first source of compression.

Scheduling reform must address the second.

Together, they should create:

- a genuine bottom tier;
- a genuine elite tier;
- more cross-strength competition;
- more realistic blowout scorelines;
- wider schedule-strength distributions;
- more meaningful differences between raw record and underlying team quality;
- better evidence for computer ratings and at-large selection;
- and a clearer explanation for dangerous .500 teams when they do reach State.

This report should be used as the pre-reform baseline for any future scheduling or program-talent analysis.
