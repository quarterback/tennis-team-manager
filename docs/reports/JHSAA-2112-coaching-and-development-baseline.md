# JHSAA 2112 — Coaching bond, annuity and player development: the first longitudinal baseline

*Internal research report · 2038 world / 2112 JHSAA season · both genders · October 2026*

**Status: observed baseline, not a completed longitudinal evaluation.** Analysis of the supplied 2038 both-gender JHSAA research ZIP, using the 2112 season review for competitive context and the merged October 2026 code/AARs to explain what each measure means. This document preserves the first usable research snapshot of the new coach bond, program-loyalty annuity and attribute-specific teaching model. See [the complete 2112 annual review](../2112-jhsaa-season-review.md) and [the expanded competitive analysis](JHSAA-2112-season-analysis.md).

## What this report is trying to determine

> **Bond is earned competitive reputation; teaching ability is what a coach knows how to teach; player development is what a student actually learned. These are related, but different facts.**

This distinction is the heart of the design and of the research. A coach who regularly wins districts may be an accomplished program builder. A coach who develops a beginner into an excellent doubles player may be a first-rate teacher even when the program loses. A veteran teacher should be able to move to a weaker program without the simulation treating the move as a sudden loss of skill. A young coach should have a path to earn standing through improvement and competitive achievement. Strong programs with complementary staff should be capable of producing extraordinary player gains, but those gains must be explained by what individual coaches teach and what players can absorb.

The data needs three separate answers:

- **Competitive achievement and standing:** How did the head coach's programs perform, what recognition did the head earn and what bond entered the season?
- **Teaching expertise and opportunity:** Which coach taught which attribute categories, how strong was the relevant instruction, which players were receptive, and which offers took?
- **Actual learning and eventual competition:** What attribute gains reached the players, what did they retain, and what happened to their varsity opportunities, singles/doubles matches and postseason careers?

The first category is observable association-wide in 2112. The second is structurally observable, but meaningful new-era exposure is only beginning. The third cannot yet be assessed over four-year or six-year careers.

## What was built

The named-coach system already held the head coach, up to three assistants, coaching archetypes and technical grades. PR #493 added a **developmental stock** for each newly eligible player, individual natural targets and trainable ceilings across 51 attributes, separate teaching portfolios for each coach, work ethic, coachability, person/teacher fit, and a finite seasonal/career budget. PR #495 carried the complete player, coach, teaching-offer and attribute-detail records into research exports. PR #496 added an earned **head-coach bond**, a **tenure-based annuity**, protection for older development specialists, research fields and a cohort-cutoff fix for seventh/eighth-graders already on the old rules.

Those changes are documented in [the attribute development AAR](../AAR-jhsaa-attribute-development-stock.md), [the bond and annuity AAR](../AAR-jhsaa-coach-bond-annuity.md) and [the 2103–2111 player-development panel and design history](JHSAA-development-panel-review-2103-2111.md).

**No player receives extra match points simply because a respected coach is present.** Bond changes how reliably the staff's *teaching offers* translate into skill development. The existing match-day Changeover, Tactics and Singles mechanics remain separate. Natural growth, maturity events and early-POT gains form another separate development track; neither natural growth nor coaching should be described as overriding the other.

## How the head's bond is earned

The coach starts at a neutral **1.0000**. The game scores completed seasons, emphasizes the most recent five, and calculates the bond entering the following season. The inputs are competitive achievements and sustained service, not a direct observation of how well individual players learned.

| Completed-season evidence | Points in the implemented version |
|---|---:|
| Season winning percentage, including the archived overall season record | 0–20; a .500 season is 10 |
| Improvement in winning percentage against the same program's previous season | −10 to +10, calculated as 50 × the percentage-point change |
| District title | +12 |
| Each Road-to-State **unit trophy** won | +5; the district title is excluded from this count |
| State appearance | +4 |
| State quarterfinal finish | +11 instead of +4 |
| State semifinal finish | +17 instead of +11 |
| State finalist | +23 instead of +17 |
| State champion | +30 instead of +23 |
| Tournament of Champions champion | +8 in addition to the State achievement |
| Consecutive head seasons at that school | +0.8 per season, capped at +8 |

The State finish entries are **one non-stacking tier**. The Road-to-State input is the archive's count of *unit honours won*, not a direct sum of the fractional prices in the separate Program Coefficient system. Importantly, winning percentage comes from the **archived whole-season W-L record**; it should not be described as a regular-season-only measure. A program's previous season is found using its permanent identity, even when the school was renamed or its head coach changed. The name-lookup bug and the stray module syntax error were fixed in PR #496.

The past-five-season weights are **1.00 / 0.80 / 0.60 / 0.45 / 0.30**. The weighted mean is compared with **16 points**, divided by a **45-point span**, and shrunk toward neutral for coaches with few seasons using *n / (n + 2)*. The resulting teaching-offer multiplier is bounded between **0.85 and 1.15**. These numbers are implemented **first-pass calibration choices**, not observed real-world coaching coefficients.

The actual largest bond in the 2112 export is **1.1071**. With five counted seasons, the small-history factor itself is 5/7, so the positive side of the 1.15 nominal range is not attainable in this ordinary five-season calculation; 1 + 0.15 × 5/7 ≈ 1.1071. This is why interpreting 1.1071 as a *weak* top coach would be mistaken.

### The ten-year bond annuity

A head qualifies **after completing ten consecutive seasons at the same program**, provided the head is **older than 40** entering the next season. The eleventh season is the first season whose new success receives the extra annuity credit. Assistant seasons, coaching a different program and a break in the same-program head-coaching streak do not satisfy this local tenure requirement.

The annuity adds **25% to the positive achievement portion** of that qualifying season: win-percentage points *above* the .500 baseline, positive year-on-year improvement, district titles, Road-to-State unit titles, State finish and TOC title. The ordinary tenure points are not multiplied. A coach whose season has no positive achievements does not receive a fictitious success bonus simply for being loyal. A change of school resets the **program-specific annuity**; the coach retains career history and other standing.

For example, in an eligible year with a .600 record, a district championship and two road-unit trophies, the annuity-bearing amounts are (12 − 10) + 12 + 10 = **24** points, earning **6 extra annuity points**, before any positive year-on-year change or State result. These extra reputation points enter the **next** bond calculation, not the just-completed season.

### The protected veteran teaching coach

A **development specialist aged 55 or older** has a bond floor of 1.0 and cannot fall below the previously earned archived head-coaching bond. This does **not** mean every coach over 55 has protected reputation. The specialist must have a practice/teacher/JV-whisperer identity **or** a Development grade quantile at least 0.75.

This rule is independent of the annuity. A longtime competitive coach can earn the annuity without being a development specialist; a veteran specialist can retain reputation at a losing program without having served ten years there. Their underlying **technical coaching grades** remain distinct from bond and are not improved or reduced by this result.

### What the bond is not

It is not the coach's Development grade, the strength of their net or serve instruction, the player’s work ethic, the team’s present talent, the team's actual on-court win probability, or a direct player OVR reward. Bond is a modest *multiplier on eligible teaching offers*. A head with bond 1.10 cannot teach volleying well unless the head or assistants actually bring usable net instruction, and a player with little remaining net trainability cannot receive infinite skill points from an excellent reputation.

The distinction also protects interpretation of losing records: a coach with low competitive bond may still be an effective specialist. A veteran with a high bond after moving into a rebuilding program may have **earned standing**, not evidence that this new roster already improved because of that person.

## The 2112 association-wide coaching baseline

The 2112 export covers **965 boys programs and 1,002 girls programs**. It contains **960 boys' head-coach season records and 1,002 girls' head-coach records for 2112**: **1,962 named heads** in the current-season coach table. The other five boys programs do not have a current-season head row in this export. The table below uses only **slot = head and season_year = 2112**; the complete coach-seasons CSV also has historical assistant and head rows, which must not be mistaken for 2112 active positions.

| Measure | Boys | Girls | Combined |
|---|---:|---:|---:|
| 2112 head-coach records | 960 | 1,002 | **1,962** |
| Annuity active entering 2112 | 234 | 255 | **489** |
| Protected veteran development heads | 317 | 338 | **655** |
| Development-specialist heads, any age | 569 | 583 | **1,152** |
| Average entering bond | 1.0276 | 1.0263 | **1.0269** |
| Median entering bond | 1.0091 | 1.0036 | **1.0059** |
| Lowest entering bond | 0.9677 | 0.9638 | **0.9638** |
| Highest entering bond | 1.1071 | 1.1071 | **1.1071** |

About **24.9%** of the named heads are annuity-qualified; about **33.4%** receive veteran development protection. **182** satisfy both conditions. These are overlapping classifications, not additional kinds of staff, and they do **not** prove the protections caused better instruction. There are **633** exact-neutral 1.0 bonds and **116** at the observed 1.1071 upper end. **478** heads have no scored past season in the five-season bond calculation; their blank bond-score field must not be confused with a score of zero.

A head's current coaching record and this entering-season bond are on **different clocks**. The 2112 titles, collapses and improvements affect later bond calculations. Evaluating this column as though it were scored from the 2112 postseason is a one-year attribution error.

### The annuity is visible, but not proof of development

Annuity-qualified heads have an average bond around **1.061**, while the others average around **1.016**. Longer-tenured heads also tend to have stronger prior competitive records; this is **descriptive selection**, not an estimate of the annuity's causal contribution. There is no pre-annuity counterfactual in this single export.

The average bond by championship group is not uniform: **9A ≈ 1.0506, Group 1 ≈ 1.0401, Group 3 ≈ 1.0099 and 11B ≈ 1.0084** in this sample. Competitive histories and program composition differ. Group averages must not be used as player-development rankings or as grounds to punish weaker groups.

### The four coaching biographies worth keeping

**Lilly Flores, Chickasaw girls.** Chickasaw fell from **25–8 in Group 2 to 5–18 in Group 1** after realignment. Flores enters 2112 with **bond 1.0967**, is **72**, has **18 completed head seasons** at this program, and has both the **annuity** and **veteran teaching protection**. This is the intended distinction between today's difficult competitive circumstances and an accumulated coaching reputation. It **does not establish** that this particular roster has already developed more than its peers.

**Maxwell Salama, Southern Pacific Tech boys.** His current team went **0–21**, while his entering bond is **1.1031**, with **18 seasons**, age **66**, annuity eligibility and veteran teaching protection. A single terrible year therefore need not erase accumulated credibility. We need player evidence, not just that bond, to determine whether Salama is still teaching well.

**Mia Huang, Canal View boys.** Canal View went **38–3**, won Group 1 and then the Tournament of Champions. Huang enters with **bond 1.1071**, age **66**, **16 seasons** at the school, an active annuity and veteran protection. This is an example where competitive achievement and earned reputation align. The TOC victory is a **2112 achievement**; it is not already incorporated in the pre-2112 bond.

**Owen Gibson, Millworks boys.** Millworks went **24–6** and earned its first recorded State title, winning 4A as a seventh seed through the Divisionals. Gibson enters with **bond 0.9833**, age **35**, four completed head seasons and no annuity. This does **not** mean Gibson failed as a coach in 2112. It means the bond reflects the preceding five-year record. The championship is the beginning of a potentially different future trajectory, and the 2113 export should capture its effect.

Other useful comparisons: **Kessler Church** began his first recorded head season at Mabry Township with a neutral 1.0 bond and won Group 3 from a ninth seed; **Mia Orosco**, 34, began Barley Gap girls' 1A title season at **0.9788**; **Gavin Berry**, 35, entered L.B. Johnson boys' third consecutive 9A title season already at **1.1071** without annuity status. The system permits earned reputation among younger coaches, while the annuity rewards service along a different path.

## Technical teaching is a second dimension

The coaching portfolio is a set of skills, such as serve, return, baseline, net/doubles, movement, touch, physical preparation or mental preparation. Each head or assistant has particular portfolio categories with an intensity, and an actual *teaching quality* in each category derived from their named ratings. Strong assistants contribute independently. Several coaches emphasizing the same skill have diminishing overlap; a complementary staff can open more areas of growth.

For longitudinal analysis, use **jhsaa_coaches.csv** to see the portfolio and the eight teaching-quality columns, not the head's bond. Use **jhsaa_development_ledger.csv** to determine which specific coach offered instruction to which specific player in which season, whether it took, and how many raw attribute points landed. A strong teacher's career contribution should be measured from these paired player records; team wins cannot be substituted for that evidence.

The head's entering bond scales teaching offers, but **the identity of the teacher matters**. The current school head need not be the person who taught a returning player in a prior season. A subsequent coach change is not a reason to reassign older gains to today's head.

## First results from the player stock system

The 2112 export contains **58,444 players** in total, **15,284 of whom have the new stock profile**. Most new-era players are freshmen or younger:

| Player grade in 2112 | New-model players |
|---|---:|
| Seventh | 548 |
| Eighth | 562 |
| Ninth | 14,087 |
| Eleventh | 87 |
| **Total** | **15,284** |

The 87 eleventh-graders have international/non-US or missing nationality entries and **zero previously staffed seasons** in their new-stock record. They are consistent with new arrivals rather than ordinary established four-year cohorts; the export alone does not reconstruct each student's arrival transaction. Already-archived middle-school students from the older development era retain the prior model by design.

**Only 44 players — 21 boys and 23 girls — have a positive recorded coached gain in this export.** They are **32 ninth-graders and 12 eighth-graders**. Most freshmen have no completed prior coached school season under the new model to credit. This is not evidence that 15,240 players were poor students or that their staffs failed.

For those 44 players, recorded extra coached OVR has **median +0.2165**, **mean +0.2367**, and an observed **maximum +0.654**. These are small **early increments**, not four-year results. Separately, the cohort's initial extra coached-OVR **budget** averages roughly **8.26** and reaches about **27.23** at its maximum. A latent budget is an *opportunity*, not a promise that a player will receive it. The full career's ordinary natural growth is a separate source of improvement.

The detailed teaching ledger records **877 coach/category/season attempts** belonging to **44 unique players**: **427 landed**, **346 declined**, **103 fell below the teaching floor**, and **one was blocked**. A landed row is an instructional attempt **not** an additional unique developed player. The eight categories represented in the credited raw-attribute gains include touch, mental, serve, baseline, movement, return, physical and net. This already proves that the recorded coaching activity is **attribute-specific**, rather than one universal team-rating boost.

### Following an actual player's instruction

**Raven Cressy, Nicodemus girls (eighth grade)** has **+0.457 extra coached OVR** in this export. Her learning includes return depth, return quality, baseline control and other technical attributes. The **2111 ledger** credits baseline, return and serve instruction primarily to **Daniella McManus**, with contributions from **Trinity Pappas**, **Jaida Brock** and **Samantha Sanchez**. The head shown for Nicodemus in the **2112 coach-season table is Avery Molina**. This is exactly why future studies must **join the development ledger to the coach who taught that player in that archived season**, not assign all historic growth to the coach currently holding the job.

**Amaya Niu, Aurelia girls (ninth grade)** has **+0.379 extra coached OVR**; the coached attribute vector is weighted toward return quality, depth and aggression, with touch, mental and additional skills. Her recorded earlier coaches include **Vivian Porter**, **Khloe Butler** and **Sloane Pfeifer**, performing different kinds of instruction. Those are legitimate *teaching-record* examples. They are not yet evidence of a transformative singles or doubles career.

An important practical distinction: **raw attribute points and weighted OVR are different units**. Summing the ledger's raw points and calling that a player-rating increase would be wrong.

### Do coached points actually reach the player?

The player-attribute profiles credit approximately **464.02 raw coached attribute points** across the 44 active cases, versus approximately **464.01 raw points of visible attribute improvement above the intrinsic baseline**. The small differences at individual cells are consistent with export rounding. **This 2112 export shows no material loss between credited and realized raw improvement**; there are no players with more than 0.01 raw attribute points of accumulated positive accounting discrepancy when the rounded records are compared.

This finding addresses an earlier proposed concern about coached points being spent but clipped at a player's maximum. The code's accounting is worth stress-testing on **older, heavily coached players near their ceilings**, but the actual young-cohort evidence in 2112 does **not** substantiate a meaningful shortfall. Do not record a hypothetical future edge case as a defect already demonstrated by this dataset.

## What the first snapshot cannot decide

**Bond and teaching effectiveness are not interchangeable.** This export is not a completed test of whether high-bond coaches develop more students than low-bond coaches, because nearly all new-model students have no recorded prior instructional development. Only 44 show gains, some under staffs and head coaches different from today's. Comparing the bond of their **current** head with those existing gains would be misleading.

The following questions remain unanswered:

- Do coaches at struggling programs produce strong attribute gains, after comparing players with similar initial ability, stock, work ethic, trainability, exposure and remaining headroom?
- Do high-Development teachers produce gains in their specialties regardless of the head's competitive bond?
- Does an elite complementary staff consistently produce more **kinds** of new skills than four overlapping specialists?
- When a veteran moves schools, do incoming players benefit from preserved teaching quality even if the new team struggles?
- Do long-serving annuity heads earn measurably larger future bond only in genuinely successful years, as implemented?
- Does a ninth-grade beginner occasionally reach State-level singles or doubles competition by senior year, without a universal inflation in the middle of the player population?

These are longitudinal questions. Do not answer them by treating the 2112 season's competitive winners as proof of better development.

## Longitudinal research protocol — keep using this section

**Baseline:** archive this 2112 ZIP and the reports separately from future files. The research ZIP is roughly **64 MB compressed** and is not included as source in this documentation commit. Its season scope is **2112**, world year is **2038**, and the exports cover both genders. Subsequent 2113, 2114, 2115 and later bundles should be compared on identical definitions and stable IDs. The older 2103–2111 development panel was collected before these new coaching features and is a reference for **natural trajectory and inflation**, not an experimental control for the new annuity.

**Follow the same coach.** From each season's jhsaa_coach_seasons.csv select head rows for the requested season, grouped by (gender, coach_id); join program_ident to track program tenure and moves. Compare bond, score, age, tenure, annuity status, veteran protection, most recent bonus and detailed prior-year component JSON. A transfer of the same coach to another program resets *local* annuity eligibility, not coach_id.

**Follow the same school.** Join the programs, season histories, coach seasons and relevant coach awards on program_id / program_ident and gender, never the mutable school display name. Compare W-L, district titles, State finishes, classification and head tenure; realignment changes the competition and can overwhelm normal year-on-year improvement comparisons. The current bond's preceding-season W-L already follows stable identity through renames.

**Follow the same student.** Join players.csv, jhsaa_development_profiles.csv and jhsaa_development_ledger.csv by **player_id** across exports. Track their grade, entering program, transfer path, initial ability, natural target, trainable ceiling, work ethic, category receptivity, coaching budget used and remaining, and **current skill attributes**. Separate *natural ability change* from *coaching-acquired* attribute change. Verify the player who was coached in a given year actually had the matching archived coach_id in the ledger.

**Connect the teaching to the outcomes.** For a coach and matched pupil cohort, sum **realized** raw gains and weighted-OVR gains only over attributes the actual engine uses; compare categories (especially serve/baseline versus net/doubles), duration together, prior room to improve, and student work ethic. Then consult varsity participation, individual matches, flight assignments, honours and eventual State singles/doubles results. Coaches should not be judged by the mere existence of a win, nor by indiscriminate total OVR inflation.

**Compare four different populations:** newer coaches in rebuilding programs; ten-year annuity coaches with sustained district strength; age-55+ protected teaching specialists at weak programs; and elite competitive heads with deep State or TOC careers. Match as closely as practical on initial team strength, classification, program history, coach profile, age and student stock. Record transfers, realignment, class format and early-participation rules as explanations for changing opportunity.

### Suggested recurring tables and tests

Keep per-season cohort measures for *both genders*: eligible stock players; players with at least one prior staffed season; players with a landed offer; offers landed/declined/floor/blocked; total **realized** development and headroom; annual and cumulative gains by grade and skill category; skill-specific changes after coach/staff moves; median/p90/p99 by player potential and effort; 20+/30+/40+/50+ career trajectories and State singles/doubles participation; cohort inflation and senior 80+/90+ backend **calibration only**.

For coaches, retain bond median/p10/p90, fraction annuity/veteran, age/tenure bands, bond distribution by competitive tier and grade-specific teaching quality. Record **actual bonus points earned** separately from whether the annuity flag is on. A one-time snapshot of eligible coaches does not demonstrate that the annuity raised their subsequent achievement; follow year-to-year movement.

**A chronological guard:** the exported 2112 bond is the value **entering 2112**; 2112 competitive achievement appears in the calculation for the subsequent season. Compare 2112 outcomes to 2113 bond, and 2112 teaching opportunities/roster exposures to later player skills. Historical coach_seasons rows in this ZIP do not all carry bond scores, because the feature did not exist during earlier archived seasons. Blank is **not** zero and should not be backfilled with invented retrospective bond values.

### Decisions and research cautions carried forward

The coach-rating-history concern raised during implementation review was intentionally left outside scope at the owner's direction. The middle-school age/cohort cutoff **was fixed**. Both changes must not be misrepresented as outstanding open work.

The annuity point weights and the realized bond range deserve later review, but changing them based on this one snapshot would be premature. The more consequential proof will be whether the new player-development system produces distinct, high-value skills and occasional spectacular careers under the right teachers **without** making the entire population unnaturally strong.

**Current conclusion:** the annuity and veteran protections visibly classify coaches as intended; the 2112 export supports concrete examples of earned standing surviving poor team results. The teaching system visibly creates skill-specific offer records and tiny early gains. Neither the long-run instructional advantage of high-bond coaches nor the rate of beginner-to-State transformations is yet established.

## Files and provenance

- [The complete 2112 internal season review](../2112-jhsaa-season-review.md) — the supplied in-world season narrative, championship ledger, realignment and alternate outcomes.
- [Expanded 2112 season analysis](JHSAA-2112-season-analysis.md) — competitive conclusions, program trajectories and coaching context.
- [Coach bond and annuity AAR](../AAR-jhsaa-coach-bond-annuity.md) — exact current formula, age/tenure rules, implementation fixes and export columns.
- [Attribute development stock AAR](../AAR-jhsaa-attribute-development-stock.md) — per-attribute player creation, coaching portfolios, matched-player synthetic replay and implementation.
- [Historical 2103–2111 development panel](JHSAA-development-panel-review-2103-2111.md) — original long-term player development benchmark.
- Supplied research bundle: play-to-clinch-jhsaa-2038-both.zip, containing boys and girls subfolders for 2112. The counts above were recomputed from their CSVs, not from a future simulated season. No real-save rerun, parameter retune or code change was performed for this report.
