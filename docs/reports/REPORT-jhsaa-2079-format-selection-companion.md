# JHSAA 2079 Format + Selection Analytics Companion

**Status:** independent analyst companion to the merged 6A State-format study from PR #432.

Primary related report:

- [`REPORT-jhsaa-6a-state-format-study-2079.md`](./REPORT-jhsaa-6a-state-format-study-2079.md)
- Original PR: https://github.com/quarterback/tennis-team-manager/pull/432

Machine-readable results from this companion analysis:

- [`data/2079-format-selection-analyst-results.csv`](./data/2079-format-selection-analyst-results.csv)

This report does **not** replace the 6A format study. The other report is the stronger source on direct format-shape comparison: it uses 2077–2079 State anatomy plus engine counterfactuals across six shapes and two scoring variants. This companion contributes four different pieces of analysis:

1. a separate 2079 6A 1S/4D vs 2S/3D championship-field counterfactual;
2. a strength-integrated at-large seeding test;
3. Tournament of Champions common-card sensitivity;
4. a proposed selection-layer diagnostic based on **flight share**, expected win percentage, and Record Over Expected.

It also records an open next-pilot hypothesis from the owner: **6A as the only classification running 3S/4D all season long as a control.** That idea is not tested here and should not be treated as a recommendation already supported by these results.

---

## 1. What the merged 6A report already establishes

The merged PR #432 study makes several findings that should govern interpretation of any new pilot:

- 6A's 2079 one-point rate was not evidence of a broken class; pooled 2077–2079 results put 6A among the ordinary five-point classes.
- 2S/3D changes the character of the dual more than the closeness of the dual.
- 3S/4D materially widens the dual and reduces one-point frequency because it is a seven-flight format.
- 4S/5D would erase a meaningful distinction between 6A and 7A.
- scoring length is not an important competitive lever relative to lineup shape.

This companion analysis agrees with those conclusions. The most important independent confirmation is that a separate championship-field model also finds that **2S/3D does not materially change 6A parity**.

---

## 2. Independent 2079 6A championship-field counterfactual

The 2079 match-level export was used to estimate flight win probabilities from observed player-strength differentials. The actual 6A field was then evaluated under the current 1S/4D card and a 2S/3D counterfactual.

This is a statistical counterfactual, not a literal replay of unplayed S2 lines.

### Closeness barely moves

Share of all possible 6A field matchups falling in a 40%-60% team-win-probability band:

| gender | 1S/4D | 2S/3D |
|---|---:|---:|
| boys | 25.6% | 24.6% |
| girls | 32.7% | 31.8% |

Using a broader 30%-70% band:

| gender | 1S/4D | 2S/3D |
|---|---:|---:|
| boys | 48.8% | 47.9% |
| girls | 60.6% | 59.6% |

The practical reading is simple:

> **Replacing one doubles flight with a second singles flight changes which roster shapes are advantaged, but it does not solve five-flight closeness.**

That independently matches the merged report's engine result.

### It changes who benefits

Boys modeled championship probability:

| team | 1S/4D | 2S/3D | change |
|---|---:|---:|---:|
| Tidewater | 18.2% | 25.4% | +7.2 pts |
| Dusty Spur | 13.7% | 19.5% | +5.8 |
| Valley Christian | 20.7% | 15.9% | -4.8 |
| Chaminade | 17.1% | 12.5% | -4.6 |
| Severn | 5.3% | 3.6% | -1.7 |

The actual 2079 champion, Severn, becomes less likely in the 2S/3D model.

So if 2S/3D is ever chosen, the correct policy question is not "does it make 6A less random?" It is:

> **Does 6A want to assign more championship value to a second high-level singles player and correspondingly less value to doubles depth?**

That is a sporting-choice question, not a repair question.

---

## 3. Open pilot: 6A-only 3S/4D all season long

The owner is considering a larger control experiment:

> **Make 6A the only classification running 3S/4D all year long.**

This should be treated as a new experiment, distinct from the 2S/3D discussion and distinct from the merged report's isolated 3S/4D engine cells.

The value of this pilot is not merely that 3S/4D has more singles. It would make 6A the association's cleanest test of **format continuity**:

- the same broad lineup demand throughout the season;
- no regular-season-to-postseason compression from 3S/4D into 1S/4D;
- more persistent value for S2/S3 and deeper doubles roles;
- a natural comparison against 5A below it and 7A above it, both of which would retain different championship identities.

Before implementation, "all year" should be made explicit in code/documentation for each phase: early non-district, league regular season, showcases, road to State, State, and TOC. The pilot should not accidentally change a phase simply because it reads a shared format helper.

### What to measure if the pilot runs

The analyst should pre-register the measurements rather than judging the pilot after seeing the champion:

1. **Flight participation**
   - varsity appearances by roster rank;
   - S1/S2/S3 appearance distribution;
   - D1-D4 appearance distribution;
   - number of distinct players receiving meaningful varsity work.

2. **Role persistence**
   - how often a regular-season S2/S3 player remains a consequential postseason player;
   - whether lower doubles specialists remain useful through State instead of disappearing from the card.

3. **Competitive shape**
   - favorite win rate;
   - lower-seed win rate;
   - one-flight-margin rate;
   - mean flight margin;
   - champion seed distribution.

4. **Roster construction**
   - top-11 OVR/POT distribution;
   - whether 6A starts valuing depth differently from 5A and 7A;
   - transfer-market effects, especially whether role congestion declines because S2/S3 remain valuable all season.

5. **Continuity control**
   - compare 6A's regular-season-to-postseason player retention with 5A's 3S/4D -> 1S/4D compression and 7A's 3S/4D -> 4S/5D expansion.

This is the strongest reason to run the pilot: 6A could become the only class where the same fundamental seven-flight team identity persists from ordinary league play through the championship.

---

## 4. At-large seeding: Road-first seeding is mostly working

The 2079 field contained 216 at-large selections across committee classes.

A counterfactual re-ranked the full fields by existing computer strength rather than forcing every at-large below every Road qualifier.

Result:

- only **8 of 216 at-larges (3.7%)** would have earned a Parastate bye;
- 43 would improve by at least five seed positions;
- only 7 would improve by at least ten positions;
- the median at-large improvement was only about two seeds.

The eight true bye-level exceptions were:

| gender | class | team | current | strength seed |
|---|---|---|---:|---:|
| boys | 2A | Draybrook Union | 33 | 16 |
| boys | 3A | Cabo Esperanza Tech | 33 | 24 |
| boys | 3A | Calderwood | 34 | 22 |
| girls | 3A | River North | 33 | 18 |
| girls | 4A | Sotomayor | 33 | 15 |
| girls | 5A | Hackensack | 33 | 22 |
| boys | 6A | Oakhaven | 33 | 22 |
| girls | Group 3 | Quincy | 25 | 19 |

This does **not** support integrated strength seeding as a live rule change.

It supports keeping Road qualification valuable while tracking the rare extreme inversion for another season.

---

## 5. TOC common-card sensitivity: current 1S/4D is effectively neutral

The 12 State champions per gender were evaluated against one another under four common cards:

- 1S/4D;
- 2S/3D;
- 3S/3D;
- 4S/5D.

Rank-order correlations with the current 1S/4D ordering:

| gender | 2S/3D | 3S/3D | 4S/5D | max movement |
|---|---:|---:|---:|---:|
| boys | .993 | .993 | .979 | 2 places |
| girls | .986 | .993 | .993 | 1 place |

The top champion ordering was effectively unchanged.

This strongly supports retaining 1S/4D as the TOC common card. It does not appear to systematically privilege champions from doubles-heavy classes.

---

## 6. Selection-layer analytics: add context, not another automatic ballot

The most actionable innovation from this companion work is not a format change. It is an **analytics panel for the State selection layer**.

Use the word **flights**, not courts.

The committee already sees résumé-style evidence: record, TOSS/ranking information, Road performance, and existing selection context. The proposed analytics add a second view of what happened underneath the record.

### A. Flight share

Definition:

> **Flights won / total varsity flights played.**

Example interpretation:

- Team A is 14-10 but won 61% of its flights.
- Team B is 20-5 but won only 53% of its flights.

Their records imply one hierarchy. Their underlying flight performance suggests a different one.

### B. Expected win percentage (xW%)

Fit from 2079 pre-State varsity duals using flights won and lost.

The fitted Pythagorean exponents were:

- boys: **1.815**
- girls: **1.850**

For implementation, **1.83** is a reasonable association-wide constant unless later seasons show a meaningful reason to split it.

Formula:

```text
xW% = FlightsFor^1.83 / (FlightsFor^1.83 + FlightsAgainst^1.83)
```

Correlation with actual team winning percentage in 2079:

- boys: **.952**
- girls: **.951**

This is strong enough to be useful as context, but it should not become an automatic selection score.

### C. Record Over Expected (ROE)

Definition:

```text
ROE = actual winning percentage - xW%
```

Negative ROE means the record may underrate the team's underlying flight performance.

Positive ROE means the record may overstate how dominant the team was underneath.

### 2079 examples

**Kokomo boys, Group 1**

- actual W%: .792
- xW%: .582
- ROE: +.210
- went 15-1 in one-flight-margin duals

Plain language:

> Kokomo's record was much stronger than its aggregate flight performance; the committee should know that the résumé is heavily supported by exceptional close-dual conversion.

**Yarrowfield boys, 3A**

- actual W%: .640
- xW%: .806
- ROE: -.166

Plain language:

> Yarrowfield played substantially stronger tennis flight-by-flight than its record suggests.

**Llerena boys, 6A**

- actual W%: .286
- xW%: .432
- selected at-large

The committee already identified this kind of case without the new metric. That is a feature, not a contradiction: the panel can make existing good judgment more legible.

**Canal View girls, 9A**

- actual W%: .500
- xW%: .641
- selected at-large

Again, the analytics would explain why a middling record can still belong to a State-caliber team.

### Suggested committee display

Do not add one composite "analytics score."

Add a compact context panel:

```text
Record:              14-10 (.583)
TOSS:                 #31
Flight share:         60.8%
Expected W%:          .708
Record Over Expected: -.125
One-flight duals:     2-7
Context flag:         RECORD MAY UNDERRATE TEAM
```

Or:

```text
Record:              20-5 (.800)
TOSS:                 #18
Flight share:         53.1%
Expected W%:          .612
Record Over Expected: +.188
One-flight duals:     11-1
Context flag:         RECORD MAY OVERSTATE TEAM
```

### Agent implementation guidance

A future implementation agent should:

1. Calculate these metrics from **pre-State varsity duals only** for the relevant season.
2. Count **flights**, never sets, games, or player appearances.
3. Use completed duals only.
4. Keep actual W-L record and TOSS untouched.
5. Add `flight_share`, `xwin_pct`, `record_over_expected`, and close-dual record to the committee view model.
6. Use an association-wide 1.83 exponent initially; make it a named constant and document the 2079 calibration.
7. Add descriptive flags only at materially large disagreement thresholds; do not automatically add/subtract committee points.
8. Never allow the analytics panel to select or reject a team by itself.
9. Archive or export the values used in committee review so future season reports can audit whether the committee followed or overrode the signal.
10. Recalibrate after several seasons rather than every season, unless the match format changes materially.

The purpose is straightforward:

> **Show the committee when the team's record and its underlying flight performance tell meaningfully different stories.**

That improves selection context without replacing the selection process.

---

## 7. Current recommendation board

| question | recommendation |
|---|---|
| 6A 2S/3D as a parity fix | No |
| 6A consolidated-doubles-point pilot | Worth considering; see merged PR #432 study |
| 6A-only 3S/4D all-season control | **Open next pilot; not yet tested as a full-season intervention** |
| 5A-2A format changes | No evidence for change |
| Road-first Parastate seeding | Keep |
| TOC 1S/4D | Keep |
| Selection-layer flight-share/xW analytics | **Implement as advisory context** |

The broad conclusion is intentionally conservative: the current format diversity is producing distinct championship environments without obvious structural failure. The best immediate analytics innovation belongs in **selection**, while the most interesting next sporting experiment is the owner's larger 6A 3S/4D continuity-control idea.
