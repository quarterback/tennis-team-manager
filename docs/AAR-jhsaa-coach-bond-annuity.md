# AAR — Coach bond, program loyalty annuity, and development specialists

**Status:** merged into `main` in [PR #496](https://github.com/quarterback/tennis-team-manager/pull/496), including the two code-review corrections. Real-save calibration remains pending. Tests are committed; this AAR does not claim they were run successfully.

**Owner direction (October 2026).** Coaching is a separate, attribute-specific development system. Do not make ordinary maturity or POT events override coaching. Do not change the coach's historical teaching ratings as an alleged "retroactivity" fix; that is explicitly out of scope. Make the head's bond a measure of the credibility earned by *building a program*. Coaches at low-win schools must have a path to sustained development credibility. Add a **bond annuity** for older, loyal heads: a coach over 40 who has completed **at least ten consecutive years as head coach of the same school** earns extra credit on *successful seasons after* that threshold. A qualified coach earns it starting with season eleven. A move resets eligibility at the new school but does not wipe their career reputation.

## What bond controls

Bond is **not the coach's talent**. Teaching grades and portfolios still control which player attributes a coach can teach. Bond scales the staff's teaching offers modestly; it never adds player ratings directly and has no direct effect on match outcomes. The existing Changeover advice effect is untouched.

The existing coaching and player-development tracks remain separate. The attribute-stock model awards skills based on the player's trainability, work, exposure, coach fit and coach specialty. Bond only influences the reliability of that instruction. Players with little remaining headroom cannot acquire skills past their personal caps through bond alone.

## What earns reputation each year

The last five completed seasons count, with recency weights **1.0, 0.8, 0.6, 0.45, 0.3**. Older years remain visible in history but leave the moving bond calculation. A coach's initial bond is 1.0.

| Completed-season result | Reputation points |
|---|---:|
| Season winning percentage | 0–20 (a .500 year = 10) |
| Year-over-year winning percentage change | -10 to +10 (a +.200 change = +10) |
| District championship | +12 |
| Each Road-to-State *unit trophy won* | +5 |
| Made State | +4 |
| State quarterfinal | +11 instead of +4 |
| State semifinal | +17 instead of +11 |
| State final | +23 instead of +17 |
| State champion | +30 instead of +23 |
| TOC champion | Additional +8 |
| Consecutive head seasons at the school | +0.8 per year, capped at +8 |

Only the **best State-finish tier** is scored in a given year; there is no stacking of first-round, quarterfinal and championship prizes. A State appearance is still valuable. A district title remains valuable even when the team does not make State. Road units are counted from the existing season's `unit_wins` record, excluding the separately scored district title; there is no need to win a State title to build a good record.

Improvement compares a program's archived season winning percentage against its previous archived season, **even when the previous head coach was someone else**. The archive's published season record includes postseason; this is **not a separately calculated regular-season-only winning percentage**. Missing history contributes zero improvement credit rather than an invented result. The lookup follows the permanent program identity through school renames; see the review fixes below.

The five-year weighted score is compared against an ordinary reference score of **16** and mapped to the existing **0.85–1.15** bond range, with a small-history adjustment that keeps newly appointed coaches closer to **1.0**. These reference constants are *first-pass balance choices*, not data-fitted rankings. `BOND_NEUTRAL_SCORE`, `BOND_SCORE_SPAN` and the five-year weights are the calibration controls.

**A coach at a weak school is not required to win a championship.** Year-on-year improvement, district wins when available, tenure and the veteran-development protection supply alternative forms of value. On a 4–20 program, steady progress toward 8–16 or 10–14 can improve the head's earned score even without a State berth. Consistently winning districts is a sustained positive achievement.

## The ten-year bond annuity

Eligibility is **all** of the following for the season being played:

- Head coach is **older than 40** (age 41 or greater).
- Has already finished **10 or more consecutive seasons as head of this same program**.
- Is still its head coach. Assistant seasons do not count, and transferring head jobs resets the program-specific streak.

Once eligible, each *new successful season* receives **25% extra reputation points** on the parts that represent positive results: winning percentage *above .500*, positive year-on-year change, district championship, Road-to-State unit wins, State finish and TOC championship. Merely being there does not generate an annual 25% windfall. The ordinary tenure points are **not** multiplied.

For illustration, imagine a coach's eleventh season includes a district championship (+12), two Road-to-State units (+10) and a .600 winning percentage (+12, of which +2 exceeds the .500 baseline). Their **annuity supplement** on those components is 25% of (12 + 10 + 2) = **+6**, before adding any positive year-on-year change or State/TOC credit. A season with no successful achievements earns only its ordinary record and tenure points, **no unearned annuity bonus**.

The annuity's effect enters the head's **next** bond calculation. It cannot award development retroactively to the just-finished season. It remains eligible at the same school while the coach continues the qualifying head-coaching streak.

## Veteran development coaches

Coaching grades were *already* fixed when the coach was generated, so nothing changes those permanent skills. For the **earned bond rating**, a coach who is at least **55** and is a development specialist cannot drop below **1.0** or below the bond they had in their preceding head-coached season.

A development specialist is initially identified by a `practice`, `teacher`, or legacy `jv_whisperer` coaching profile, **or** a stored Development quantile of 0.75 or higher. This is a derived career category, not a new coach attribute roll. The qualifying coach can continue earning a higher bond, but poor team results no longer erode a reputation already established.

That permits a veteran teacher to move to a struggling program without sacrificing their developmental effectiveness. A younger coach's bond remains responsive to changing results, allowing their career reputation to develop.

The veteran protection and the annuity are **independent**: an experienced coach can qualify for either, both, or neither. A development coach over 55 need not complete ten years at the same program to receive veteran protection. A non-development coach over 40 with ten consecutive seasons may receive the annuity.

## How to track whether it works

The `jhsaa_coach_seasons.csv` research export includes one head-coach row per program per season. The archived record contains:

- `bond`: the reputation multiplier used entering that season.
- `bond_score`: five-season recency-weighted earned achievement score.
- `bond_age`, `bond_tenure`, `bond_annuity_active`: whether the coach qualified that season and why.
- `bond_development_coach`, `bond_veteran_protected`: whether the no-decline veteran protection applies.
- `bond_latest_annuity_bonus`: extra points earned in the **most recent completed season**, not necessarily the current one.
- `bond_recent_years_json`: exact underlying prior-season scores, including win percentage, year-on-year change, district, road units, State, TOC, tenure, annuity eligibility and bonus.

The `jhsaa_development_ledger.csv` remains the source for actual teaching offers, including those that **failed**, and how many attribute points were awarded by each coach. The `jhsaa_development_profiles.csv` records current attribute skills, natural targets and trainable caps for players. Join on `coach_id` and `player_id`, not names. Together, they can answer: *Did this coach's bond rise? Which assistants taught which skills? Did the players actually get better?* The change is measurable without treating championships as the only definition of success.

**Baseline comparisons worth running on full exports:** heads with 10+ years versus newer heads; qualifying coaches before/after the annuity; veterans 55+ at losing programs; successful long-tenured district coaches without State titles; and first-time heads improving low-performing programs. Read the distribution by gender and championship group. A winning record at a good team and substantial improvement at a weaker one should both be visible, with different component scores.

## Early-participant continuity

The separate `stock_cohort_eligible` change checks the player's **archived talent pin** as well as the entry-year cutoff. A seventh- or eighth-grader whose first archived season used the old model has a pin with `stock=None`, so they **keep the old model** through senior year even if their ninth-grade entry year crosses the new development-era boundary. A never-before-rostered student uses the new rules normally. An existing new-model player retains their pinned stock profile. Transfers continue using the origin's pin.

This change protects the student's history without inventing new rolls or altering unrelated development rules.

## What was intentionally left alone

The maturity/POT development track, the attribute-stock calculation, the separate singles and doubles skill teaching rules, technical coach grades, and the live match-day Changeover/Tactics/Singles effects are unchanged. No historical coaching-grade correction was made. The bond has no new effect on results beyond its existing modest influence on future attribute acquisition.

**Testing added:** `tests/test_jhsaa_bond_annuity.py` covers the ten-year/over-40 condition, post-qualification success bonus, changing schools, district success, veteran protection, effect-JSON persistence, middle-school pin protection **and school renames across seasons**. `tests/test_jhsaa_stock.py` also tests the bond research-export fields. The tests are present in the merged source; the full suite was not run as part of this documentation update. Review full-world calibration after the first new-era graduates; the point weights are not calibrated against real-save exports yet.

---

## Merge and code-review record

**Implementation:** [PR #496](https://github.com/quarterback/tennis-team-manager/pull/496) implemented the head-coach bond, ten-year annuity, veteran development-coach protection, middle-school cohort cutoff protection, and export fields. It has been merged into `main`.

**Review fix — syntax error:** A leftover line, `D_K * s)), 4)`, made `app/jhsaa_coaches.py` fail to import. Commit [`0c34724`](https://github.com/quarterback/tennis-team-manager/commit/0c34724df91b0576e55a97bfdf4fca37205e8590) deleted it. This was a stray expression, not part of the scoring design.

**Review fix — renamed programs:** Initially, year-over-year improvement looked up the prior season by its current display name. After a rename, the archived season still used the old name, so the comparison silently returned zero. `_bond_season_row` now looks up the previous head-coach record by the permanent program `ident`, using the historical school name recorded in that season; an exact-name fallback handles old archives without a coach-history record. This was also fixed in [`0c34724`](https://github.com/quarterback/tennis-team-manager/commit/0c34724df91b0576e55a97bfdf4fca37205e8590).

**Regression test:** Commit [`fbf876d`](https://github.com/quarterback/tennis-team-manager/commit/fbf876d93a0395ddecc46bca4d6c4db4baf5d044) added `test_year_over_year_improvement_uses_program_identity_after_rename`. It checks both a returning head coach and a replacement head coach. The same program moving from 6–14 (.300) under its old name to 13–7 (.650) under its new name must register a +.350 change, earning the maximum +10 year-over-year points. The test confirms the *calculation*, not a bonus for renaming.

**Middle-school cutoff:** `app/jhsaa.py:stock_cohort_eligible` examines the existing talent pin as well as the ninth-grade entry year. An already-archived seventh- or eighth-grader with no stock profile stays on the old development rules through graduation; a new entrant uses the new stock-era rules. This doesn't mix the coaching track with maturity or early-POT development.

**Deliberately unchanged:** The owner declined work to snapshot historical coaching grades to address a hypothetical retroactivity concern. This PR does **not** implement that change. It also does not change player maturity, early-POT, technical skill ratings, player stock allocation, or match-time Changeover/Tactics/Singles effects.

## Where to follow the results

All head-coach annuity and bond calculations can be followed in the end-of-season research export `jhsaa_coach_seasons.csv`. Use `coach_id` to follow a coach, `program_ident` for a school (rather than its display name), and sort by `season_year`. Use `slot=head` because the head-coach annuity is not earned during assistant-coach seasons.

| Column | Interpretation |
|---|---|
| `bond` | Multiplier **entering** the season, bounded to 0.85–1.15 |
| `bond_score` | Recency-weighted achievement score from up to five **prior completed seasons** |
| `bond_age`, `bond_tenure` | Age and consecutive completed head-coaching seasons at this particular program |
| `bond_annuity_active` | Coach qualified entering this season: age over 40 and at least ten completed consecutive head seasons at the program |
| `bond_development_coach` | Whether the coach is a development specialist based on existing profile or Development quantile |
| `bond_veteran_protected` | Whether a development specialist aged 55+ retains a neutral-or-better bond floor and their previously earned bond |
| `bond_latest_annuity_bonus` | Extra reputation awarded for the **most recently completed** season |
| `bond_recent_years_json` | Per-season breakdown: win percentage, prior percentage, YOY change, district win, Road-to-State units, State finish, TOC title, tenure and annuity points |

The exact scoring is in `app/jhsaa_coaches.py`: `_bond_annual_points` awards 0–20 for win percentage, −10 to +10 for year-over-year improvement, +12 per district title, +5 per Road-to-State *unit trophy*, a single nonstacking State finish tier of +4/+11/+17/+23/+30, +8 for a TOC title, and up to +8 for tenure. Qualifying annuity seasons add **25% of positive achievement credit**, excluding the ordinary .500-win baseline and tenure credit. `head_bond_details` weights the last five seasons at 1.0/0.8/0.6/0.45/0.3, shrinks short histories toward neutral, and maps into the 0.85–1.15 bond range. Bond is an influence on later coaching offers, **not a direct win or attribute grant**. A veteran development specialist (55+, practice/teacher/JV-whisperer profile or Development quantile at least .75) cannot have their bond reduced below 1.0 or below the preceding archived head-coaching bond.

The separate `jhsaa_development_ledger.csv` shows each coach's teaching attempts, failures, and gains for particular players. `jhsaa_development_profiles.csv` shows the players' natural and trainable skill targets and realized current attributes. Together, these let the owner ask not only whether bond grew, but whether that head and staff actually developed athletes. The research bundle, rather than a new interface, is the current audit surface.

**Still to calibrate:** run the new rules against real coach-career and player-development exports. Compare long-serving district winners, veteran teachers at low-win programs, first-time coaches improving weak teams, and State/TOC winners; make sure the 0.85–1.15 mapping distinguishes them without forcing successful development coaches to win major titles. The scoring values above are implemented first-pass settings, not validated outcomes.
