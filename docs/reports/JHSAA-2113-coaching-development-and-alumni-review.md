# JHSAA 2113 — Coaching, player development and college careers

*Research companion to the 2039 (2113) annual season review · both genders · November 2026*

**Purpose.** The [2113 JHSAA annual season review](../2113-jhsaa-season-review.md) reports the State championship races, players, school histories, and TOC. This companion measures three mechanisms added to the game: the **earned head-coach bond and ten-year annuity**, **individual attribute-level teaching**, and the **abbreviated collegiate career** generated for JHSAA graduates. It preserves the 2113 research baseline for comparison with 2114 and later seasons, including a newly verified accounting problem in how coached gains are reported when an attribute reaches its cap.

**Source and clock.** These findings were calculated directly from `play-to-clinch-jhsaa-2039-boys.zip` and `play-to-clinch-jhsaa-2039-girls.zip` (both `manifest.json` files identify **JHSAA 2113**). Player and coach history tables include older seasons; the college tracker includes future-dated, precomputed four-year records for 2113 graduates. The two clocks must be kept distinct. No game was resimulated, no model constant changed, and no saved career rewritten to produce this analysis.

The technical design references are [Coach Bond and Annuity AAR](../AAR-jhsaa-coach-bond-annuity.md), [Attribute Development Stock AAR](../AAR-jhsaa-attribute-development-stock.md), [2112 combined baseline](JHSAA-2112-season-coaching-development-review.md), and [Alumni Career Model 2 AAR](../AAR-jhsaa-alumni-career-model-2.md).

## The main findings

**Coaching now has enough exposure to study.** The 2112 export had 15,284 stock-profile players and just 44 with any coached gains. The 2113 export has **29,440 stock-profile players**, and **14,070** record positive coached gains. The large majority of those gains belong to the 2112 freshmen, now sophomores, and were earned from archived **2112 coaching**. This is the first substantial population on which to measure the implementation's offer-to-attribute process. It remains only an initial year of development, with no four-year stock-era graduates yet.

**Coach reputation is being carried forward.** There are **1,954 current head-coach season records** in 2113, with **492 annuity-active heads** and **682 protected veteran development heads**. Owen Gibson's bond rose from 0.9833 entering Millworks' first State title season to 1.0303 entering 2113. Veteran protection preserved Lilly Flores's Chickasaw bond through a year of poor results after promotion.

**Allocated coaching credit sometimes exceeds actual skill gained.** Across both genders, recorded coached contributions total approximately **6,651.21 weighted OVR**, but final attributes show **6,546.24** above their intrinsic baselines. The **104.96 OVR difference** is concentrated entirely in coached attributes later clipped at the trainable cap. **278 players** have over 0.10 weighted OVR of credited-but-unrealized coaching gain. This is a demonstrable issue in the exported accounting and in the implementation's returned `coached_ovr`, rather than ordinary export rounding.

**The new college epilogue is now present in a real graduating class.** The 2113 graduate data contains **245 boys and 294 girls** with Model 2 collegiate careers. Their first destinations span D1–D4; 108 distinct students transfer during those precomputed careers. Most transfers down or sideways resulted in greater recorded participation at the receiving school. Those are generated collegiate futures, not played NCAA seasons.

## Population and cohort comparison

| Measure | 2112, both genders | 2113 boys | 2113 girls | 2113 total |
|---|---:|---:|---:|---:|
| Rostered players | 58,444 | 28,698 | 29,904 | **58,602** |
| Players with stock profile | 15,284 | 14,342 | 15,098 | **29,440** |
| Players with positive credited coached gain | 44 | 6,902 | 7,168 | **14,070** |
| Entering/current head coaches in the export | 1,962 | 954 | 1,000 | **1,954** |
| Annuity active | 489 | 231 | 261 | **492** |
| Veteran development protection | 655 | 329 | 353 | **682** |

The stock-profile population has nearly doubled because another full freshman cohort now carries a pinned attribute contract. The student who arrived before the new model remains governed by the prior model throughout the student's career; the existing early seventh/eighth-grade participants keep their applicable original rules. A head coach's bond appearing on a `season_year=2113` row is its **entering-2113 value**, calculated from *completed previous seasons*.

### The new model by grade

| 2113 stock cohort | Boys with stock | Boys with gain | Girls with stock | Girls with gain |
|---|---:|---:|---:|---:|
| Grade 7 | 293 | 0 | 292 | 0 |
| Grade 8 | 484 | 258 | 542 | 284 |
| Grade 9 | 7,157 | 290 | 7,596 | 269 |
| Grade 10 | 6,359 | 6,354 | 6,629 | 6,615 |
| Grade 11 | 49 | 0 | 39 | 0 |

The **12,969** sophomores with coached gain make up 92.2% of all the students showing a gain. Their current sophomores' attributes incorporate the 2112 season's instructional offers; grade-seven newcomers lack a prior staffed season, while some early participants have already completed one or two. Only 559 current freshmen and 542 current eighth-graders have positive coaching credit. Each year should be compared by completed instructional seasons and entry cohort, rather than by grade alone.

The player-level **median positive coaching contribution** is approximately **+0.345 OVR for boys** and **+0.361 for girls**. Among students with positive gains, the 90th percentiles are **+1.008** and **+1.037**, and the observed maxima **+2.747** and **+3.050**. This additional growth is separate from the ordinary natural development trajectory. It is one coached season's early effect, not a full-career gain.

Examples of recorded high coached gains include **Samson Patrick**, a Perry Green sophomore (+2.747 OVR); **Randall Trường**, Vespertine North (+2.735); **Keira Stoll**, Harmon Valley (+3.050); and **Camilla Degroot**, Trois Ilets (+2.892). These are internal calibration values. They do not establish who will become a State singles finalist or which head coach caused the gain; the correct teaching attribution belongs to the coach identifiers on each historic 2112 ledger row.

## The actual teaching ledger

The export gives each player a separate record for instructional attempts by **coach, specialty, student and prior season**. Results are explicitly categorized, allowing a genuine audit of unsuccessful instruction alongside successful offers.

| Attempt outcome | Boys | Girls | Both |
|---|---:|---:|---:|
| Landed: credited raw attribute points | 45,206 | 47,332 | **92,538** |
| Declined: offered instruction did not take | 40,783 | 43,049 | **83,832** |
| Floor: governing teaching quality below threshold | 9,686 | 9,680 | **19,366** |
| Blocked by remaining stock/budget | 503 | 632 | **1,135** |
| **Recorded coach/category attempts** | **96,178** | **100,693** | **196,871** |

Each row is an offer category, not a unique coached player or a separate match. The dominant credited raw-attribute categories in boys were baseline, movement, touch, mental and return; girls showed baseline, movement, mental, touch and return. Serve, net and physical instruction are also present. The head and assistants all appear with distinct `coach_id` and `slot`; teaching credit can be assigned to the actual teacher rather than inherited by the head solely because the student attended that school.

This is the central distinction in the whole model:

> **Competitive bond measures the head coach's earned standing. Teaching portfolio and technical grades describe what a particular staff member can teach. The development ledger measures what the student actually received.**

A strong bond can influence whether an offer takes. It is neither a player skill nor a teaching specialty. Comparing a winning 2113 program's head bond with the current sophomores' existing coached gain is an invalid timing comparison unless the model also recovers the actual **2112 head and assistant records** and the corresponding offers. The current head may be a new hire, and the player's recorded development precedes the team's 2113 championship.

## What the 2113 attributes revealed: coaching credit clipped at the cap

The 2112 early audit checked 44 coached students and found no material gap between `coached` and the actual attribute movement above `baseline`. That finding was correct for that tiny early sample. The 2113 export has enough mature first-year instructional records to expose an accounting defect.

For each stock-profile player, we took all 51 attributes from `jhsaa_development_profiles.csv` and calculated the difference between:

1. **Credited coaching**, the per-attribute `coached` amount, summed with the exported normalized `ovr_weight`; and
2. **Realized coaching**, the current attribute minus the intrinsic `baseline`, using the identical weights.

The sum of the normalized weights in each 51-attribute profile is approximately 0.99996. Differences below one-thousandth of a point are consistent with output rounding. The results below are larger and systematic.

| Profile reconciliation | Boys | Girls | Both |
|---|---:|---:|---:|
| Credited coached OVR | 3,209.67 | 3,441.53 | **6,651.21** |
| Realized coached OVR above baseline | 3,162.75 | 3,383.50 | **6,546.24** |
| **Credited but unrealized OVR** | **46.93** | **58.04** | **104.96** |
| Players whose positive gap exceeds 0.01 OVR | 384 | 424 | **808** |
| Players whose positive gap exceeds 0.10 OVR | 131 | 147 | **278** |
| Players whose positive gap exceeds 0.50 OVR | 14 | 28 | **42** |

There were **2,463 boys' attribute rows and 2,825 girls' attribute rows** where the credited amount exceeded realized improvement by more than 0.05 raw attribute points. **Every one of those 5,288 rows lies at the final trainable cap.** This establishes where the credit was lost.

Some individual discrepancies are much larger than the association mean. **Rajeev Cole of Saltbush** has +1.353 credited coached OVR, while his final attributes show approximately +0.217 above baseline, a **1.136 gap**. **Coco Deal of Fairgrounds** has +2.783 credited against approximately +1.268 realized, a **1.515 gap**. A handful of their attributes have a baseline already equal to the cap, but the earlier teaching sequence still credited those attributes with gains.

The implementation explains why. In [`app/jhsaa_develop.py`](../../app/jhsaa_develop.py), `apply_stock()` calls `allocate_detail()` season by season using the player's **earlier** intrinsic development plus prior coached gain to establish available skill room. As the student advances, their intrinsic `baseline` grows. At the final grade, the code writes:

```python
room = max(0.0, caps[a] - baseline[a])
p.current[a] = clamp_grade(baseline[a] + min(coached[a], room))
```

It then calculates returned `coached_ovr` from **`baseline + coached` before this clipping**, and the exported `coached_attrs` retains the earlier awarded amounts. Thus the match engine uses the correctly capped actual attribute while the coach-credit and budget totals can include progress that no longer appears in the student's skill vector.

**Finding:** the simulation currently overstates *credited realized development* for some students and consumes stock for coaching that final intrinsic growth later displaces. The total discrepancy is about **1.58%** of credited coached OVR in the present sample, but individual effects can exceed one OVR point. It is a material accounting issue in the research and career-development outputs, particularly for high-ceiling students.

**Follow-up work:** add a regression fixture where past instructional offers allocate valid points, then a later intrinsic baseline reaches or exceeds the trainable cap. Require the profile's reported *realized* coached total to equal the final current-minus-baseline attribute delta; decide explicitly how the lost allocation affects stock consumption and coach credit. Maintain the separate record of offers attempted, attempted/gross credit and actually retained instruction, so researchers can audit both. Do not silently change earlier archived results or players' immutable stock pins as part of a reporting fix. No code adjustment was made in preparing this report.

## Developmental opportunity and work ethic

The intended exceptional career depends on several qualities occurring together: a relatively weak starting player, substantial skill-specific trainability, strong work and responsiveness, good instruction and actual participation. Marginal distributions alone are insufficient.

Among stock-profile **ninth-graders** in 2113, work ethic and additional coached-OVR budget have a correlation of approximately **−0.366 in boys and −0.366 in girls**. Both are less negative than the approximately −0.405 measured in the 2112 baseline, but the high-high overlap remains rare:

| 2113 ninth-grade screen | Boys | Girls | Total |
|---|---:|---:|---:|
| Work ethic at least 0.70 and extra coaching budget at least 15 OVR | 2 | 3 | **5** |
| Work ethic at least 0.75 and extra coaching budget at least 15 OVR | 0 | 0 | **0** |

There are **14,753 stock-profile ninth-graders** across both genders. A zero in the strict high-high screen does not prove that extraordinary development is impossible: natural maturation and less extreme combinations can still produce remarkable careers. It does mean the first-year research should track *joint profile rarity* rather than expecting players selected independently for high effort and high unused headroom to be common.

## Coach bond and annuity: year two

The head-coach bond converts recent competitive history into a modest multiplier on staff teaching offers. Technical coaching grades are a separate, retained property. A qualifying head is older than forty and has completed ten consecutive head-coached seasons at the same program; successful seasons from the eleventh onward receive **25% extra points on positive achievements**, with tenure and the .500 baseline excluded. A development specialist aged 55 or above has a floor at neutral bond and their previously earned bond. Movement between schools resets the *local* annuity tenure.

| 2113 current heads | Boys | Girls | Both |
|---|---:|---:|---:|
| Head season rows | 954 | 1,000 | **1,954** |
| Annuity active | 231 | 261 | **492** |
| Veteran development protection | 329 | 353 | **682** |
| Mean entering bond | 1.0292 | 1.0278 | ~1.0285 |
| Median entering bond | 1.0204 | 1.0182 | — |
| Heads at observed 1.1071 plateau | 59 | 49 | **108** |

The maximum observed 1.1071 comes from the five-season shrink factor in the implemented mapping. The configured 0.85–1.15 band therefore has a tighter attainable ordinary upper range, and a qualified annuity holder already at that plateau can earn more score without changing their actual teaching multiplier. This remains a deliberate calibration question rather than evidence of additional instructional effect.

### Examples showing the one-year clock

**Owen Gibson, Millworks boys:** entering-2112 bond **0.9833**, then a 24–6 season and the program's first 4A State title. His entering-2113 bond rose to **1.0303**, an increase of **0.0470**. Millworks went 20–6 in 2113. The new score reflects the completed championship season; it cannot be used as the bond entering the previous State run.

**Miles Hodges, Mercy Academy Valley girls:** entering-2112 bond **1.0298**, rising to **1.0690** entering 2113 after the 2112 State and TOC finalist season. Mercy then won the 2113 10B and TOC titles. Those achievements belong in the next bond period.

**Kessler Church, Mabry Township boys:** entering-2112 neutral bond **1.0000** in a first head season, then a Group 3 State title from the No. 9 seed. The entering-2113 bond is **1.0500**, a gain of 0.0500. This is a concrete path for a younger/newer coach to accumulate standing without meeting the long-service annuity requirement.

**Lilly Flores, Chickasaw girls:** her team fell 25–8 → 5–18 after moving into Group 1 in 2112, then finished **7–19** in 2113. Flores's **1.0967** bond remained at that value entering 2113 under annuity and veteran development protections. The point is preservation of reputation; the sophomores' actual acquired skills must be checked separately.

**Maxwell Salama, Southern Pacific Tech boys:** the team went **0–21 in 2112** and **4–22 in 2113**, while his protected bond remained at **1.1031** entering 2113. The young players' median coached contributions do not by themselves prove or disprove his teaching quality. A sound comparison uses the prior-season staff, students' baseline attributes and trainability, and each recorded teaching attempt.

A coach can have a strong 2113 record, earn State Coach of the Year and carry a relatively neutral entering bond if their previous five seasons were ordinary or their head tenure recently changed. The State awards are measures of that season's competitive achievements; the bond is a carried reputation affecting subsequent offers. Treat them as separate research variables.

### The actual test of teaching effectiveness

The current export supports the first **observational**, skill-specific inquiry: compare players of similar beginning ability, natural target, trainable headroom, work ethic and competitive exposure under different **actual 2112 teaching staffs**, grouped by specialty. Sum the *retained attribute gains*, not only the credited pre-cap total. Add their 2113 varsity/JV flight participation and later 2114 growth as subsequent outcomes.

A strong or protected head with a weak team's current record is a valuable test case. A high-bond championship head with a rich staff is another. Neither bond status nor a title can substitute for measuring acquired skill. Transfers and staff moves should assign historical coaching credit by **coach_id and offered season**, with the player followed by **player_id** and schools by their stable program identity.

## First real graduating class with College Career Model 2

The new standalone alumni tracker gives selected JHSAA graduates a **generated, finished collegiate career** without advancing the playable college game. The 2113 class in these exports is the first real graduation snapshot assessed under the active Model 2. The rows dated 2114–2117 are the generated four-year epilogue written at graduation, not future seasons that have already been played.

| Graduating class 2113 | Boys | Girls | Total |
|---|---:|---:|---:|
| Students with a college-career row | **245** | **294** | **539** |
| Initially D1 | 39 | 52 | 91 |
| Initially D2 | 97 | 86 | 183 |
| Initially D3 | 89 | 120 | 209 |
| Initially D4 | 20 | 36 | 56 |
| Singles starter in freshman year | 86 | 109 | 195 |
| Freshman reserve | 144 | 143 | 287 |
| Freshman doubles-only contributor | 13 | 37 | 50 |
| Finished a four-season career | 195 | 233 | 428 |
| Left the team | 40 | 40 | 80 |
| Left college | 10 | 20 | 30 |
| Injury-ended career | 0 | 1 | 1 |
| Distinct players who transferred | 56 | 52 | **108** |

The dividing rule is **absolute college-level competitive fit and player choice**, relative to the game's own gender-specific talent and recruiting scales, rather than a fixed number of D1 slots. D4 is the game's academic-first division; these are fictional career outcomes through real named college programs, and the national college world is not being run in the background.

Several actual JHSAA graduates yield distinctive college biographies in the generated data:

- **Ty Antrim**, Estuary Bay's 3A boys' Player of the Year, begins at LSU as a reserve, then transfers to Eastern Michigan. His first season has two combined match appearances; his next has **44**, with a No. 7 singles place, and he stays in the lineup through senior year.
- **Roberto Johnson**, Oakhaven's 8A boys' leading State-final singles opponent, plays doubles at Kansas, then transfers to Bloomsburg and becomes **No. 1 singles** as a junior, recording an All-Conference honor there.
- **Benjamin Woods**, Salmon Bay's 2A boys' Player of the Year and singles State champion, signs at Oregon, plays four combined flight appearances as a freshman reserve, and leaves the team. A State champion can have a short college tennis career.
- **Alexa Urban**, Mercy Academy Valley's 10B girls' Player of the Year and singles State champion, signs at Indiana, spends her freshman season as a reserve and subsequently plays No. 8–10 singles over three seasons without earning a college honor.
- **Dilara Bayram** of Redwood Glen starts at No. 8 singles at UC San Diego, transfers to Jamestown and plays **No. 1 singles** in the lower division, with increased match opportunity.

These records illustrate the intended result of the abbreviated model: a high-school athlete's competitive level, chosen destination, roster depth, development shape and subsequent decisions produce different career outcomes without generating an actual NCAA season.

### Did transfers buy opportunity?

The 2113 cohort has **109 distinct college-to-college moves** across **108 players**; one player transferred twice. Reconstructing each transfer from adjacent season rows yields:

| Division change | Transfers | Share playing more matches after the move | Mean change in combined singles+doubles matches |
|---|---:|---:|---:|
| Down to a lower competitive tier | 58 | **93.1%** | **+33.0** |
| Same division / lateral | 50 | **90.0%** | **+26.9** |
| Up a competitive tier | 1 | 0% in this one case | −5 |

Here the tiers are the game's competitive hierarchy D1 → D2 → D4 → D3; a transfer between two colleges in the same division is counted as lateral. The measure is **actual simulated match participation in the season before and after**, so injury events and variation in participation can cause a qualifying opportunity transfer to have fewer played matches than projected. The model makes the decision against the following year's depth chart before committing it.

This validates the design direction requested for transfers: a D1 reserve who moves down usually acquires a materially larger role. It does not mechanically preserve the student's previous lineup position at the receiving school. Upward moves are a separate decision and may sacrifice participation for stronger competition. The exact growth of participation is a **result of this generated cohort**, not a universal prescribed transfer rate.

## What to compare in the next export

**For 2114**, reproduce all of the 2113 metrics with the same IDs, units and filters. Focus on the 2112-entering students as juniors: how much coached growth is realized after a second staffed season, how its categories change after a coaching move, and whether unusually improved players occupy a different varsity flight or role. For the 2113 freshmen, establish their first-year instructional results; for older pre-stock students, retain the prior model's development baseline rather than treating them as failed new-model students.

**For coaches**, keep each head's entering bond next to prior completed-season outcomes, the actual annuity success bonus earned, the historical teacher assigned each category, and the actual pupil benefit. Compare long-serving district builders, veteran teachers at weak programs and new championship heads without assuming that the program's win rate measures instruction.

**For college alumni**, compare 2113 graduates to the next selected graduation class using the real snapshot rather than the synthetic Model 2 validation sample. Report the fraction of graduates with a collegiate record, initial placements, four-year participation, transfers by tier, retained versus lost playing time, single/doubles honors, and early departures. All-time career listings need stable school IDs and career rows written once. Each college future is generated when its high-school class graduates; do not mistake it for a live college season that the user advanced.

**Highest-priority technical issue:** reconcile the final per-attribute cap with the credit and remaining coaching budgets. The 2113 export supplies a reproducible real-save dataset showing the discrepancy. Write a focused AAR and regression test for any eventual code change. The previous 2112 result—44 early coached students with no material clipping—remains correct for that earlier export; the new population reveals the issue.

## Reproducibility and scope

The numbers above were calculated from the two ZIPs using `players.csv`, `jhsaa_development_ledger.csv`, `jhsaa_development_profiles.csv`, `jhsaa_coach_seasons.csv`, `jhsaa_program_history.csv`, `jhsaa_college.csv` and the current program identities. Each profile has 51 rows per student and must be grouped by `player_id`; the ledger has many attempts per student and cannot serve as a unique-player count. Current heads were selected by `season_year=2113` and `slot=head`; bond comparisons used archived 2112 and 2113 head rows joined on stable `coach_id` and `program_id`. The 2113 college cohort was selected by **`grad_year=2113`**, then grouped by player, with freshman entry from `class_year=Fr` and transfers reconstructed from adjacent college-season rows.

The sports narrative, championship ledger, realignment effects, awards, participation and 2114 returning-strength table are in [The 2039 (2113) JHSAA Tennis Season](../2113-jhsaa-season-review.md). The supplied ZIP files are research inputs and are not committed to the source repository as part of this documentation.