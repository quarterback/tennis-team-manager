# The JHSAA graduate's college career — design contract

**Status:** Model 2 is active in \`app/jhsaa_college.py\` (\`ACTIVE_MODEL = 2\`), implemented in \`app/jhsaa_college_v2.py\`, merged through [PR #498](https://github.com/quarterback/tennis-team-manager/pull/498) (November 2026). This document records the owner's design intent and the behavioral rules the abbreviated system must preserve. The detailed implementation, revisions and measurements live in [AAR — alumni career model 2](AAR-jhsaa-alumni-career-model-2.md) and [the model-1/model-2 validation report](reports/REPORT-jhsaa-alumni-career-model-2-validation.md).

## Why this is a game system worth preserving

The JHSAA is its own high-school simulator. Its graduates should still have lives after high school: the player whose strong senior season leads to a college bench role; the ordinary high-school contributor who thrives at a smaller college; the doubles specialist; the recruit who works their way into a lineup; the prospect who stalls; the injured player; the senior who stops playing; and the athlete whose transfer changes their career.

The owner explicitly chose **finished, abbreviated college careers** in the JHSAA-only save rather than running the full collegiate simulation in the background. Full college seasons were measured at roughly ten minutes a year with D1 alone, and substantially more with all four divisions. The JHSAA can take about eighteen minutes to simulate a high-school season already. This career model supplies the meaningful consequences of a college experience — destination, four-year progression, participation, individual results, honors, transfers and endings — from a small, repeatable, stored record.

**The purpose is to create plausible variety rooted in the player's history and the college's competitive environment.** Players of comparable high-school ability can have very different college careers because of their choices, development, teammates, opportunities, health and the level of tennis they face. Every outcome can be traced through the generated seasons. The career is an epilogue to the JHSAA save; it never secretly advances a college world.

## How it works, in sequence

1. **Graduation snapshot:** \`jhsaa_college.capture_snapshots\` preserves the leading seniors' high-school identity, exit level, ceiling and estimate, singles/doubles records and most-used flights, matches and postseason experience, honors, style/trait, relevant skills, academic rating, nationality, hometown and stable school identity. Previous classes have a reduced-data route through the alumni index; the generator handles missing inputs explicitly.
2. **College level:** The exit rating is measured against leading Jefferson graduates from prior classes and mapped onto the existing college game's recruiting distribution. Player-level and program-level talent use the same compression. The number who continue to college and the divisions they enter change with the strength of each graduating class.
3. **Destination:** Actual colleges from \`ncaa.load_division\` recruit within their level. D1 reads projected ability, D2 emphasizes current ability, D3/D4 balance both. Students weigh program quality, likely playing time, academics and geography according to an individual aspiration. Preserve D4 academic admission requirements, service-academy nationality requirements and the intentional differences between the men's and women's college talent tables.
4. **Four-year environment:** Each program has stable, season-specific roster seats across cohorts. Stored Jefferson alumni already attending the program occupy real places in its depth chart. Two alumni at the same college in the same year cannot both be assigned its No. 1 singles position. The player's position comes from their singles and doubles ability relative to that depth chart, with limited seniority preference where players are close.
5. **Development:** Five weighted shapes — steady, early, late, stalled and regress — determine the distribution of individual college growth across four seasons. The available growth follows the college game's maturation scale and the high-school player's *relative* headroom among peers of similar ability. Lineup rank can improve, remain steady or decline as the cohort changes around the player.
6. **Results:** The generator records singles and doubles positions, matches and W-L separately; opponents are drawn from plausible conference and nearby competitive programs, at comparable positions. Injury and partial availability reduce opportunities and can change the subsequent career. Honors require results that clear conference- or division-sensitive comparisons, with D1 and lower-division criteria handled explicitly.
7. **Decision after a season:** Stay, pursue a move for opportunity, transfer to stronger competition after success, stop playing tennis while remaining enrolled, leave college, suffer an injury-related ending, or occasionally turn professional. Each decision has a cause. A four-year graduate and a player who stopped competing in sophomore year produce different records.
8. **Durable career:** Store the completed career once in \`world_jhsaa_college\`, keyed by the player's stable identity. The entry includes its model version, college stints, year-by-year roles and results, transfers, departure reason, honors and derived career arc. The Class, All, College and High School alumni views, the student's own College panel and the research export read those records. The lightweight generated career does not affect actual JHSAA results or the playable NCAA game.

The **career arc** is derived from what happened, not chosen in advance as a label. An early starter, late developer, reserve, doubles specialist, transfer success and injury-affected player are outcomes of the same system, rather than separate scripted biographies.

## The opportunity-transfer invariant

**A transfer for more playing time must usually produce a substantially bigger playing role, especially when the player moves to a lower competitive level.** The program the athlete is leaving and the prospective destination must be evaluated against their **next-season depth charts**, at the player's current ability. The decision is about what the move *buys*.

A D1 reserve moving to D2 should ordinarily find a regular singles place; moving further down to D3 may produce a top-of-lineup player. A lower-lineup D1 starter moving down can become a No. 1–3 singles player. A doubles-only player should gain meaningful singles opportunities or a leading doubles pairing. The athlete keeps their demonstrated ability; the receiving school's competitive level and teammates determine the new role. **Do not preserve the old position merely because that was the player's position at the previous school.**

The implemented \`project_role\` and \`meaningful\` methods provide the rule:

| Career situation before seeking a move | Requirement for an opportunity transfer |
|---|---|
| Reserve | Project a *clear* singles place, at least two places above the last lineup position, and at least 12 more matches than staying projects |
| Doubles-only contributor | Gain a clear singles place with at least 8 more projected matches, **or** move to No. 1 doubles when staying would not provide it |
| Lower-lineup singles starter | Project a top-three singles place, at least two positions higher than the stay projection, with at least as many matches |

The destination search reaches further down the competitive ladder than first-time recruiting. It considers only destinations passing the appropriate role-improvement check. With no qualifying opportunity, the player stays and meets the next season's decisions. The ultimate role is assigned by the same \`_standing\` depth-chart calculation used in \`play_season\`: there is no second arbitrary role-award system.

**An upward transfer follows a different rule.** A lower-division star seeking stronger competition may accept a lower lineup place at D1 or another higher-level destination. Do not impose the opportunity-transfer improvement requirement on that decision.

The transfer record preserves \`reason\` (opportunity/up), \`role_before\`, \`role_after\`, \`before\`, \`stay\`, \`projected\`, \`played\`, \`change\` and \`improved\`. The \`change\` data includes singles position, doubles pair, starts, matches and whether a new singles opportunity was gained. Both the school previously attended and the destination must remain attached to the same student's career.

### Observed behavior, with the evidence labeled

The AAR reports **one synthetic twelve-class validation**, with **2,298 generated careers** and **422 transfers that have a following season**. These were synthetic graduating-class inputs, not a played college season or a calibration against real NCAA transfers.

| Move in that validation | Cases | More matches after transfer | Match volume before → after |
|---|---:|---:|---:|
| Reserve, seeking opportunity | 343 | 99.1% | 3 → 41 |
| Doubles-only, seeking opportunity | 9 | 100% | 24 → 45 |
| Lower-lineup singles starter, seeking opportunity | 54 | 72% | 30 → 42 |
| Successful starter, transferring up | 16 | 25% | 45 → 38 |

All **73 D1 reserves transferring to D2** in that run appeared in singles the next season. All **8 lower-lineup D1 starters moving to D2** were assigned singles No. 1 or No. 2. There was one D1-reserve-to-D3 move, and one D2-to-D1 move, in that sample.

These results demonstrate the implemented *direction* of the transfer logic; they do not prove long-run rates or every individual outcome. The specific four transfer-path regression tests originally requested were **not written** when the owner directed the earlier agent to stop testing. Keep that verification gap visible; do not claim it is closed.

## What counts as a plausible career

The game can recognize the following outcomes without allocating them as fixed class quotas:

- A strong high-school player joins a prestigious D1 program, sits behind other recruits, becomes a doubles specialist or eventually earns a regular singles place.
- A D1 reserve transfers into a smaller D2 program and becomes a starter near the top of the lineup, gaining full seasons of actual participation.
- A D2 or D3 player develops into a division-level standout. Conference honors and All-American honors depend on performance relative to that division's field.
- A successful lower-division athlete transfers upward for a more competitive environment and accepts fewer starts.
- A player stays at the same college for four years as a reliable contributor, improves late, stagnates, loses a role, suffers an injury, or leaves the team while continuing college.

The five growth shapes supply different development timing. The destination and depth chart supply different *opportunities* to convert ability into competitive results. The transfer system changes the relationship between ability and opportunity; it should visibly affect actual match participation (singles/doubles starts and matches), lineup placement and eventual honors.

## Competitive recognition and gender-specific talent

Keep the existing men's and women's college talent distributions. The resulting signing rates should emerge from those distributions and the recruiting decisions.

Honor criteria belong to each division's competitive field, including the singles/doubles distinction. The model-2 AAR records the fixes made after zero D1 All-Conference recognition and zero D1 All-Americans initially appeared. The observed post-fix synthetic baseline includes approximately **0.9 girls' and 0.6 boys' D1 All-American careers per class**, and an ordinary college career can still earn no honors. Honors are earned from competitive results and relative ability, with All-Conference eligibility a prerequisite for All-American recognition in the same discipline. Do not reinstate impossible thresholds or simply grant awards to satisfy an arbitrary percentage.

The lower-division All-American pool is intentionally deeper than D1's. A D1-caliber player choosing a lower division, or moving down for opportunity, should have a credible path to strong results and divisional recognition.

## Boundaries, future changes and verification

- **Preserve the time budget.** Career generation is a few seconds per class; no actual college season, national standings, bracket or transfer market is simulated. The program-year context is a stable depth chart, not a generated college team record.
- **Preserve write-once history.** New constants apply to future, as-yet-unwritten careers. Earlier rows remain as recorded. Retrospective regeneration requires an explicitly approved migration with a source-preserving process.
- **Preserve identity.** Track a player by pid, a high-school program by stable identity, and college stints through their actual school and dates. All schools attended must appear in the student's career and the relevant college listings. The data export must reflect the stored career.
- **Preserve causality within the model.** Players arrive at a college, their ability evolves, a depth chart supplies opportunities, matches produce results, and transfers change the setting for subsequent opportunities. Results, honors and career descriptions should follow this sequence.
- **Preserve the distinction between simulated facts and measured validation.** A precomputed fictional career is the game's result; a synthetic twelve-class run checks its distribution. No claim of real-world college placement accuracy follows from the latter.
- **Test transfer opportunity explicitly.** Still needed: D1 reserve → D2 regular starter, D1 reserve → D3 leading player, lower-lineup D1 starter → D2 top three, and D2 star → D1 depth. Assert the *played* next-season role and the transfer's before/stay/projected/played record. Read the actual rendered alumni page for transfer careers, not only the generator object.
- **When tuning**, inspect real graduating snapshots and multiple classes of both genders. Report signing rates, bench exposure, singles/doubles starts, transfers by origin/destination level, successful role changes, early departures, honors and the top and bottom of the career distribution. Keep rare exceptional outcomes possible without forcing them into every graduating class.

## Read next

- [AAR — alumni career model 2](AAR-jhsaa-alumni-career-model-2.md): implemented code, owner decisions, exact thresholds, historical changes, issues encountered, measured outputs and known testing limits.
- [AAR — JHSAA simulation separation and first alumni tracker](AAR-jhsaa-sim-separation-and-alumni-tracker.md): why the high-school and college simulations were separated and why careers are generated as a finished artifact.
- [Validation report — alumni career model 2](reports/REPORT-jhsaa-alumni-career-model-2-validation.md): synthetic class distributions and example careers.
- \`app/jhsaa_college_v2.py\`: current career/depth/transfer implementation.
- \`app/jhsaa_college.py\`: graduation snapshots, persistence, model selection and alumni views.
- \`tests/test_jhsaa_college_v2.py\`: current model-2 tests; the AAR lists gaps in the owner-approved test work.
