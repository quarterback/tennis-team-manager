# REPORT — 2084 doubles partner continuity: validation

**Question raised.** Partners per doubles player read 4 in 2073, 3 through
2074-2083, and 4 again in 2084; long-term pairs fell from ~1,300 to 705. Did the
partner-continuity code (`jhsaa._established_units` / `partner_chemistry`,
owner rule 2026-09) stop firing, get reset by the style-plane release, or fail to
recognise pairs from prior seasons?

**Answer.** No regression in the code. The arrangers that choose pairings did not
change between the commit that ran 2083 and the one that ran 2084 (the
style-plane diff touches the match engine and an era-gated draw only), and a
same-seed season played on both trees produces the same churn.

## Same-seed A/B (small real association, boys, seed 0, 340 programs)

| tree | avg partners | pairs ≥ 6 lines | established (≥ 6, non-losing) | pairs ≥ 10 |
|---|---:|---:|---:|---:|
| pre style plane (`c6f4f87~1`) | 3.94 | 1,747 | 913 | 925 |
| HEAD, `style_era` pinned to 2084 (the lab save's case) | 3.95 | 1,761 | 909 | 920 |
| HEAD, v2 profile for every cohort | 3.97 | 1,784 | 941 | 921 |
| HEAD, coach misread off (`COACH_READ` 0) | 4.00 | 1,787 | 899 | 883 |
| HEAD, `PARTNER_ESTABLISHED_MIN` 3 | 3.83 | 1,822 | 971 | 997 |

The rule fires (~2.7 established pairs per program on a four-flight doubles
lineup) and neither the coach evaluation layer's misread nor the establishment
bar is the lever: the residual churn is structural. A season plays four doubles
shapes (early 5S/2D, league 3S/4D, showcase 1S/4D, the postseason format), the
doubles pool is a different slice of the ladder in each, and the bench rotation
and rest staffing move the pool's edge every dual.

## The 2084 export itself (`play-to-clinch-jhsaa-2084-both.zip`)

| scope | boys | girls |
|---|---:|---:|
| all varsity doubles lines, MEAN partners | 3.87 | 3.90 |
| all varsity, MEDIAN | 4 | 4 |
| league (3S/4D) lines only, MEAN | 3.62 | 3.67 |
| league only, MEDIAN | **3** | **3** |
| JV lines included, MEAN | 4.28 | 4.29 |
| varsity pairs with ≥ 10 lines together | 2,400 | 2,588 |
| varsity pairs with ≥ 15 lines together | 1,154 | 1,315 |

"3" and "4" are both true of 2084 depending on whether the read is a median or a
mean and whether it is scoped to league play or to the whole varsity season, and
"~1,300 long-term pairs" matches the ≥ 15-line count here. A series that shows 3
for ten years and 4 in one year is therefore most likely two different reads
(scope or statistic), not a change in the sim; the 2073 baseline in
`AAR-jhsaa-partner-continuity-and-7a-pilot.md` was itself a **median**.

## Cross-season memory

`TeamSeason.pair_counts` is season-scoped by design and the AAR says so: "nothing
persists across years". The success-based lock never recognised prior-season
pairs, in 2074 or in 2084. Carrying last season's pair record forward is the
open change the coach-evaluation AAR already names (`pair_counts` seeded from
last season) and is an owner decision, not a bug fix.

## What to do before 2085

Nothing in the code. If the series is to be tracked, fix the read: one statistic
(mean or median), varsity only (`level = 'v'`), and one scope (league only, or
every varsity phase), and re-read 2074-2083 the same way.
