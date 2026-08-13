# JHSAA Tennis Postseason Architecture Analysis
**Prepared for:** Tournament Director & Postseason Strategist, JHSAA
**Date:** August 13, 2026
**Subject:** Structural Findings from 2027 Season Data Across All Six Classifications

---

## Executive Summary

This report presents a complete structural analysis of the JHSAA tennis postseason landscape based on 2027 TOSS Power Index rankings, state bracket outcomes, and district champion assignments across all six classifications (7A, 6A, 5A, 4A, 3A, 2A-1A) and both genders. The analysis was conducted to inform the design of a preliminary postseason stage that extends meaningful competition without introducing geographic unfairness.

The data reveals that JHSAA’s classification structure is **non-monotonic**: 2A-1A is structurally equivalent to 7A/6A in competitive density, while 3A (especially Girls) represents a distinct thin-depth tier. Auto-bid distortion is exclusively an upper-classification problem. The qualification cliff ranges from statistical noise (0.000–0.004) at large classifications to meaningful quality gaps (0.012–0.026) at mid-tier classifications. These findings establish the empirical foundation for any preliminary stage architecture.

---

## I. Classification Structure & Competitive Density

### Program Counts and Bracket Sizes

| Classification | Boys Programs | Girls Programs | State Bracket (B/G) | Qualification Rate (B/G) |
| :--- | :--- | :--- | :--- | :--- |
| 7A | 99 | 105 | 32 / 32 | 32% / 30% |
| 6A | 74 | 89 | 32 / 32 | 43% / 36% |
| 5A | 71 | 75 | 24 / 24 | 34% / 32% |
| 4A | 63 | 68 | 24 / 24 | 38% / 35% |
| 3A | 60 | 52 | 24 / 24 | 40% / 46% |
| 2A-1A | 95 | 103 | 32 / 32 | 34% / 31% |

### Key Finding: Non-Monotonic Classification Structure
The expected linear decline in competitive depth from 7A down to 2A-1A does not hold. The actual competitive hierarchy is:

-   **Tier 1 (Large Pool):** 7A, 6A, 2A-1A — 74–105 programs, 32-team brackets, tight qualification cliffs (0.000–0.004), high format-transition volatility
-   **Tier 2 (Moderate Pool):** 5A, 4A — 63–75 programs, 24-team brackets, wider qualification cliffs (0.004–0.026), moderate volatility
-   **Tier 3 (Thin Pool):** 3A (especially Girls) — 52–60 programs, 24-team brackets, variable cliffs, low volatility, champions consistently from #1 seeds

**2A-1A is structurally a large classification.** With 95 boys and 103 girls programs, it exceeds every classification except 7A in program count. Its cutoff TOSS values (0.650/0.653) are nearly identical to 7A (0.667/0.674) and *higher* than 6A Boys (0.620). Any preliminary architecture must treat 2A-1A as functionally equivalent to 7A/6A, not to 3A.

---

## II. Qualification Cliff Analysis

### Cliff Tightness by Classification

| Classification | Boys Gap | Girls Gap | Character |
| :--- | :--- | :--- | :--- |
| 7A | 0.003 | 0.000 | Statistical noise |
| 6A | 0.002 | 0.001 | Statistical noise |
| 5A | 0.004 | 0.001 | Statistical noise |
| 4A | 0.012 | 0.026 | Meaningful quality gap |
| 3A | 0.009 | 0.012 | Transitional |
| 2A-1A | 0.004 | 0.003 | Statistical noise |

### Cutoff TOSS Values (Last Team In)

| Classification | Boys Cutoff | Girls Cutoff |
| :--- | :--- | :--- |
| 7A | 0.667 | 0.674 |
| 6A | 0.620 | 0.634 |
| 5A | 0.676 | 0.661 |
| 4A | 0.647 | 0.645 |
| 3A | 0.676 | 0.595 |
| 2A-1A | 0.650 | 0.653 |

### Key Findings
1.  **The cliff is a structural constant at Tier 1 classifications.** Gaps of 0.000–0.004 represent ranking noise, meaning dozens of interchangeable teams exist at the margin. A narrow preliminary expansion (e.g., top 36) would still produce arbitrary exclusions.
2.  **4A represents a genuine quality threshold.** The 0.012/0.026 gaps indicate the last team in is measurably stronger than the first team out. The "first team out" injustice is less severe here than at larger classifications.
3.  **3A Girls has crossed a structural threshold.** With only 52 programs and a 0.595 cutoff TOSS (0.08 below 7A Girls), nearly half the classification qualifies and the bottom of the bracket occupies spots that would be held by significantly stronger teams in larger classes.
4.  **Below-cutoff TOSS at #48 declines ~20% from 7A to 4A** (0.607→0.498 boys; 0.623→0.502 girls), confirming the talent depth gulf between Tier 1 and Tier 2/3.

---

## III. District Champion Auto-Bid Distortion

### Distortion Severity Matrix

| Classification | Boys Distortion | Girls Distortion | Max Displacement |
| :--- | :--- | :--- | :--- |
| 7A | Yes (#32 JD qualified) | Severe (#46 HG → #31 seed) | 14 ranks (Girls) |
| 6A | None | Moderate (#33 IC over #32) | 1 rank (Girls) |
| 5A | None | None | 0 |
| 4A | None | None | 0 |
| 3A | None | None | 0 |
| 2A-1A | None | None | 0 |

### Key Findings
1.  **Auto-bid distortion is exclusively an upper-classification phenomenon.** Across eight brackets from 5A through 2A-1A, no district champion was ranked outside the qualifying field. Every district champion earned their spot on merit.
2.  **Distortion is asymmetric by gender.** It is severe in girls' brackets and mild-to-nonexistent in boys' brackets at the same classification. In 7A Girls, a #46-ranked district champion earned a state seed; in 7A Boys, the displacement was only 1 rank.
3.  **The corrective function of a preliminary stage is classification-dependent.** It is most valuable at 7A, moderately valuable at 6A Girls, and structurally unnecessary below 6A. At lower classifications, a preliminary stage serves purely as season extension and format validation.
4.  **At 3A Girls, the auto-bid is nearly redundant.** With 46% of programs qualifying, most district champions would qualify on ranking alone regardless.

---

## IV. Postseason Format Transition Volatility (5S/2D → 1S/4D)

### Champion Seed Lines

| Classification | Boys Champion Seed | Girls Champion Seed |
| :--- | :--- | :--- |
| 7A | #4 | #17 |
| 6A | #4 | #2 |
| 5A | #2 | #1 |
| 4A | #8 | #12 |
| 3A | #1 | #1 |
| 2A-1A | #4 | #11 |

### Largest Overperformances by Classification

| Classification | Boys | Girls |
| :--- | :--- | :--- |
| 7A | #31 → Semifinalist | #17 → Champion |
| 6A | #25 → Round of 16 | #23 → Quarterfinalist |
| 5A | #16 → Semifinalist | #9 → Runner-up |
| 4A | #20 → Semifinalist | #12 → Champion |
| 3A | #18 → Runner-up | #6 → Runner-up |
| 2A-1A | #27 → Runner-up | #11 → Champion |

### Key Findings
1.  **Format transition creates genuine, unpredictable volatility at Tier 1 classifications.** Champions have come from seeds #2, #4, #11, and #17. Top seeds have lost in the Round of 32 multiple times. The 1S/4D shift produces measurable upsets that regular-season rankings cannot reliably predict.
2.  **Volatility diminishes as depth thins.** At 3A, both champions were #1 seeds. The compressed middle band (#17–#24 spread of only 0.019 in 3A Boys) means apparent overperformances are actually statistical noise within an extremely tight competitive band.
3.  **Volatility returns at 2A-1A.** Despite being the lowest classification designation, the large program pool restores format-transition upset potential. #27 Bahía Azúl reaching the boys' final and #11 Ferris Union winning the girls' title confirm that deep rosters produce uneven doubles strength regardless of classification label.
4.  **Any preliminary stage MUST use the 1S/4D format.** Using the regular-season 5S/2D format would measure the wrong competitive skill and fail to validate true championship contenders. Caswell Depot's 7A Girls title run from #17 seed proves the current system allows deep runs, but a preliminary round using 1S/4D would have validated that strength before the state bracket.

---

## V. Geographic Distribution Patterns

### Most Concentrated Districts by Classification

| Classification | Most Concentrated District | Teams in Top Bracket | Notes |
| :--- | :--- | :--- | :--- |
| 7A Boys | Halbrook Basin | 8 of 32 | Extreme |
| 7A Girls | Halbrook Basin | 7 of 32 | Extreme |
| 6A Boys | Vance | 7 of 32 | High |
| 6A Girls | Harborline | 7 of 32 | High |
| 5A Boys | Balanced | 3–5 per district | Most balanced |
| 5A Girls | Harborline/Gold Valley | 4–5 each | Moderate |
| 4A Boys | Halbrook | 7 of 24 | Most extreme single-district concentration in dataset |
| 4A Girls | Ferris | 6 of 24 | High |
| 3A Boys | Juniper Highlands/Gold Valley | 6 each | Balanced across 5 districts |
| 3A Girls | Ashbury Metro/Gold Valley | 7 each | Two districts = 58% of bracket |
| 2A-1A Boys | North Range | 7 of 32 | Distributed across 8 districts |
| 2A-1A Girls | Cascade Divide/North Range/Sage Plains | 5–6 each | Distributed across 9 districts |

### Key Findings
1.  **Geographic clustering is real but inconsistent.** No single pattern holds across all classifications. Halbrook Basin dominates 7A; Harborline dominates 6A Girls; Ferris dominates 4A Girls; 2A-1A is the most geographically distributed bracket in the dataset.
2.  **Clustering does not correlate with classification size.** 2A-1A (largest combined pool) is the most distributed; 4A Boys (mid-size) has the most extreme single-district concentration.
3.  **Pure statewide S-curve seeding automatically prevents elite collisions.** In every bracket, the top 8–16 teams are separated by significant TOSS gaps. No district champion ranked in the top 8 has ever been displaced. Protecting top seeds from each other in preliminary rounds requires no geographic logic—only proper seeding.
4.  **Geographic optimization parameters would need to be classification-specific** if pursued, since clustering patterns differ fundamentally across brackets.

---

## VI. TOSS Distribution Patterns

### Elite Tier Compression (Top 8 Spread)

| Classification | Boys | Girls |
| :--- | :--- | :--- |
| 7A | 0.065 | 0.104 |
| 6A | 0.105 | 0.146 |
| 5A | 0.093 | 0.098 |
| 4A | 0.038 | 0.108 |
| 3A | 0.099 | 0.107 |
| 2A-1A | 0.086 | 0.072 |

### Middle Band Compression (#9–#16 Spread)

| Classification | Boys | Girls |
| :--- | :--- | :--- |
| 7A | 0.031 | 0.036 |
| 6A | 0.051 | 0.031 |
| 5A | 0.016 | 0.036 |
| 4A | 0.041 | 0.037 |
| 3A | 0.042 | 0.038 |
| 2A-1A | 0.034 | 0.025 |

### Key Findings
1.  **The #9–#16 band is consistently the tightest competitive zone across all classifications.** Spreads of 0.016–0.051 mean these teams are functionally interchangeable. This is where seeding precision matters most and where preliminary round results would have highest impact on state bracket fairness.
2.  **2A-1A Girls has the tightest elite tier in the dataset** (0.072 top-8 spread, 0.025 middle-band spread). Despite being the lowest classification designation, its competitive parity exceeds even 7A.
3.  **4A Boys has an anomalously compressed elite tier** (0.038) relative to its wider qualification cliff (0.012). The top teams are closely matched but there is a genuine drop-off after #24.

---

## VII. Implications for Preliminary Stage Architecture

### What the Data Establishes as Constraints

1.  **Field size cannot be uniform across classifications.** Tier 1 (7A, 6A, 2A-1A) can support large preliminary fields (24–32+ competitive teams beyond state bracket). Tier 2 (5A, 4A) supports moderate fields (12–20 teams). Tier 3 (3A Girls) has marginal viability (~10 additional competitive teams).
2.  **The preliminary stage serves different functions at different classifications.** At 7A/6A, it corrects auto-bid distortion AND extends the season. At 5A–2A-1A, it extends the season and validates 1S/4D format readiness. At 3A Girls, its value proposition is limited.
3.  **Protecting top seeds is trivially solvable with pure S-curve seeding.** No geographic or regional sorting mechanism is needed to prevent #1 vs. #2 collisions. The NJ problem does not exist under statewide TOSS seeding.
4.  **The 1S/4D format is non-negotiable for preliminary rounds.** Regular-season format would invalidate the stage as a championship qualifier.
5.  **Gender asymmetry must be acknowledged.** Auto-bid distortion, qualification rates, and competitive depth differ significantly between boys and girls at the same classification. Identical structures may produce unequal outcomes.

### Open Questions Requiring Architectural Decisions

1.  Whether to use a uniform preliminary structure across all classifications or tier-specific structures
2.  How many teams advance from prelims to state bracket at each classification
3.  Whether preliminary results should affect state seeding or serve only as qualification gates
4.  Whether district champions should receive byes within the preliminary stage or enter at the same point as at-large teams
5.  How to handle 3A Girls' thin viable field (smaller prelim, no prelim, or merged structure)

---

## VIII. Data Appendix: Complete Classification Summaries

### 7A Boys (99 programs, 32 qualified)
-   Cliff: 0.003 | Cutoff: 0.667 | Champion: #4 | Biggest Overperformer: #31→SF
-   Auto-bid distortion: Yes (#32 JD over #31 CC)
-   Dominant district: Halbrook Basin (8 of 32)

### 7A Girls (105 programs, 32 qualified)
-   Cliff: 0.000 | Cutoff: 0.674 | Champion: #17 | Biggest Overperformer: #17→Champion
-   Auto-bid distortion: Severe (#46 HG → #31 seed, 14-rank displacement)
-   Dominant district: Halbrook Basin (7 of 32)

### 6A Boys (74 programs, 32 qualified)
-   Cliff: 0.002 | Cutoff: 0.620 | Champion: #4 | Biggest Overperformer: #25→R16
-   Auto-bid distortion: None
-   Dominant district: Vance (7 of 32)

### 6A Girls (89 programs, 32 qualified)
-   Cliff: 0.001 | Cutoff: 0.634 | Champion: #2 | Biggest Overperformer: #23→QF
-   Auto-bid distortion: Moderate (#33 IC over #32, 1-rank displacement)
-   Dominant district: Harborline (7 of 32)

### 5A Boys (71 programs, 24 qualified)
-   Cliff: 0.004 | Cutoff: 0.676 | Champion: #2 | Biggest Overperformer: #16→SF
-   Auto-bid distortion: None | Most balanced geographic distribution

### 5A Girls (75 programs, 24 qualified)
-   Cliff: 0.001 | Cutoff: 0.661 | Champion: #1 | Biggest Overperformer: #9→RU
-   Auto-bid distortion: None

### 4A Boys (63 programs, 24 qualified)
-   Cliff: 0.012 | Cutoff: 0.647 | Champion: #8 | Biggest Overperformer: #20→SF
-   Auto-bid distortion: None | Most extreme single-district concentration (Halbrook, 7 of 24)

### 4A Girls (68 programs, 24 qualified)
-   Cliff: 0.026 | Cutoff: 0.645 | Champion: #12 | Biggest Overperformer: #12→Champion
-   Auto-bid distortion: None | Widest cliff in dataset

### 3A Boys (60 programs, 24 qualified)
-   Cliff: 0.009 | Cutoff: 0.676 | Champion: #1 | Biggest Overperformer: #18→RU
-   Auto-bid distortion: None | Tightest #17–#24 band (0.019 spread)

### 3A Girls (52 programs, 24 qualified)
-   Cliff: 0.012 | Cutoff: 0.595 | Champion: #1 | Biggest Overperformer: #6→RU
-   Auto-bid distortion: None | Highest qualification rate (46%), lowest cutoff TOSS

### 2A-1A Boys (95 programs, 32 qualified)
-   Cliff: 0.004 | Cutoff: 0.650 | Champion: #4 | Biggest Overperformer: #27→RU
-   Auto-bid distortion: None | Most geographically distributed (8 districts represented)

### 2A-1A Girls (103 programs, 32 qualified)
-   Cliff: 0.003 | Cutoff: 0.653 | Champion: #11 | Biggest Overperformer: #11→Champion
-   Auto-bid distortion: None | Largest girls' classification, tightest elite tier (0.072)

---

*End of Report*
