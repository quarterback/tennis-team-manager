# JHSAA 2083 Lineup, Style, and Slot-Efficiency Audit

**Status:** reference report for matchup strategy, roster composition, doubles pairing, style interactions, and program-level flight efficiency from the 2083 boys+girls research export.

This report combines two related 2083 analyses:

1. a lineup-strategy / roster-composition audit focused on stacking, doubles pairing, and expected-value variance; and
2. a style-field / style-vs-style / slot-efficiency audit using `players.csv`, `lines.csv`, `line_players.csv`, and `duals.csv`.

Throughout this report, every school is identified with its championship classification when discussed in prose. Team contests are called **duals**, individual positions are **slots** or **lines**, and individual singles/doubles contests are **matches** or dual **points**.

---

## 1. Dataset and method

The 2083 bundle contains 35,620 JHSAA players across both genders. The matchup sample used here contains 78,071 varsity singles matches and 99,746 varsity doubles matches.

For singles, the rating input is the player's `current_grade`.

For doubles, the rating input is the mean `current_grade` of the two players in the pair.

Expected win probability is estimated from rating differential while controlling for home/away, gender, and slot. Program-slot residuals are therefore:

> **actual win rate − rating-based expected win rate**

A positive residual means a program is producing more wins at that slot than its underlying player grades predict; a negative residual means the opposite.

For style analysis, the comparison is always made after controlling for rating differential. This matters because a raw style win percentage can simply be a proxy for stronger players happening to carry one label.

---

# Part I — Matchup strategy and roster composition

## 2. Singles stacking: style is not a meaningful reason to reorder S1–S3

The 2083 data does not support aggressive singles reshuffling based on style labels.

The largest adjusted singles style edge in the full dataset is only about **1.6 percentage points**. That is far smaller than the effect of even modest `current_grade` differences.

The practical rule is therefore:

> **Singles order should remain ability-first. Style should not be used as a primary reason to move an S1 player to S2 or an S2 player to S3.**

If two players are nearly identical in rating, style can be used as a minor tiebreaker, but the expected-value gain is small enough that lineup stability generally matters more.

This also means that apparent S1/S2/S3 anomalies should be investigated at the player/program level rather than explained away as style effects.

### Example: Mission Terrace (7A boys)

Mission Terrace (7A boys) produced one of the largest singles residuals in the association at S2:

- 28 S2 matches
- actual win rate: **78.6%**
- rating-based expected win rate: **48.4%**
- residual: **+30.2 percentage points**

Brandon Brua handled S2 in 25 of those 28 matches. He is a counterpuncher with a current grade of 73.

The association-wide counterpuncher effect is nowhere near +30 points. This is therefore not a style explanation. It is a player/slot or matchup-construction anomaly worth tracking across seasons.

Possible explanations include:

- Brua's actual match performance being materially better than `current_grade` captures;
- S2 being unusually favorable relative to Mission Terrace's overall lineup shape;
- opponent construction creating favorable second-singles matchups;
- or an extreme but real hot season.

---

## 3. Doubles pairing has a real composition effect

The doubles data is much more actionable than singles style data.

Among similarly rated pairs, the strongest pair constructions are:

1. **all-court + all-court**
2. **all-court + serve-first**
3. **serve-first + serve-first**
4. **balanced + serve-first**

The weakest pair constructions are:

1. **aggressive-baseliner + counterpuncher**
2. **aggressive-baseliner + aggressive-baseliner**
3. **counterpuncher + counterpuncher**
4. **aggressive-baseliner + balanced**

The effect is not large enough to override a major rating gap, but it is large enough to matter when choosing between similarly rated players for D1/D2 or deciding which four players should be paired together.

The most useful rule is:

> **Ability first, pair composition second.**

A ten-point rating difference overwhelms style. A one- or two-point rating difference does not.

---

## 4. Doubles matchup friction can produce 6–7 percentage-point swings

Some pair-vs-pair combinations are materially stronger than the average composition effect.

After rating control, several recurring matchups showed large edges:

- all-court + all-court vs aggressive-baseliner + aggressive-baseliner: **+7.2 pp**
- serve-first + serve-first vs balanced + counterpuncher: **+7.1 pp**
- all-court + all-court vs aggressive-baseliner + balanced: **+6.9 pp**
- all-court + balanced vs aggressive-baseliner + counterpuncher: **+6.4 pp**
- all-court + serve-first vs counterpuncher + counterpuncher: **+6.2 pp**
- serve-first + serve-first vs aggressive-baseliner + counterpuncher: **+6.2 pp**

Those are large enough to matter in a close dual.

The interpretation is not that the labels themselves magically determine the result. Rather, pair construction appears to capture some combination of complementary movement, net coverage, serve/first-ball pressure, and reduced redundancy.

The negative combinations look more like **pairing friction**: two players whose preferred patterns do not complement each other efficiently.

---

## 5. Program-level doubles construction: Robledo (7A boys)

Robledo (7A boys) is the cleanest example of persistent doubles overperformance rather than one anomalous pair.

| Slot | Actual win % | Expected win % | Residual |
|---|---:|---:|---:|
| D1 | 75.8% | 59.8% | **+16.0 pp** |
| D2 | 81.8% | 65.6% | **+16.3 pp** |
| D3 | 77.4% | 61.4% | **+16.0 pp** |
| D4 | 71.0% | 62.6% | +8.4 pp |

Three separate doubles slots beat their rating expectation by almost exactly the same margin.

That is far less likely to be random than a single hot pair.

Repeated combinations included:

- Graham Johnson + Jace McDowell — **all-court + all-court**
- Elliot Dement + Noah Shedd — **all-court + all-court**
- Grant Meadows + Elliot Dement — **counterpuncher + all-court**

The first two combinations belong to the strongest pair type in the association.

**Strategic read:** Robledo (7A boys) looks like an actual doubles-construction success. Its lineup is extracting more dual value from its grades than a rating-only model expects.

---

## 6. Program-level doubles friction: Temescal (8A girls)

Temescal (8A girls) is the opposite case.

At D1:

- average pair current grade: **53.5**
- average opponent pair current grade: **50.2**
- expected win rate: **60.6%**
- actual win rate: **31.4%**
- residual: **−29.2 pp**

The rest of the doubles card is much closer to expectation:

- D2: −6.7 pp
- D3: −1.4 pp
- D4: −3.0 pp

So this is not simply "Temescal (8A girls) is bad at doubles." It is specifically a D1 problem.

Common D1 constructions included:

- balanced + aggressive baseliner
- counterpuncher + aggressive baseliner
- counterpuncher + balanced

Two of those are among the weakest association-wide pair types.

The style composition does not explain all 29 percentage points of underperformance, but it is directionally consistent with a structurally poor D1 pairing.

**Strategic read:** Temescal (8A girls) should be a priority for a lineup-permutation audit. The likely gain is not from changing player talent; it is from reallocating the available doubles players.

---

## 7. Expected-value variance and underdog-friendly slots

Program-slot residuals identify positions where actual results diverge sharply from rating expectation.

Large positive residuals can indicate:

- effective lineup construction;
- favorable role placement;
- a player whose match performance exceeds the current rating;
- or a high-variance slot where the program consistently converts close opportunities.

Large negative residuals can indicate:

- pairing friction;
- a player being placed too high;
- a lineup shape that creates unfavorable matchups;
- or simple regression risk after an unusually poor run.

For dual strategy, the highest-value swaps are therefore not broad "stacking" moves. They are **targeted corrections at extreme residual slots**.

The most obvious 2083 candidates include:

- Temescal (8A girls) D1 — major underperformance
- Quincy (Group 3 girls) S1 — major underperformance
- Mission Terrace (7A boys) S2 — major overperformance
- Robledo (7A boys) D1–D3 — broad doubles overperformance

---

# Part II — Style-field audit

## 8. Active style values

There are exactly five active `players.style` values and **zero nulls** across 35,620 players.

| Style | Players | Share |
|---|---:|---:|
| serve_first | 7,218 | 20.26% |
| balanced | 7,191 | 20.19% |
| counterpuncher | 7,178 | 20.15% |
| all_court | 7,042 | 19.77% |
| aggressive_baseliner | 6,991 | 19.63% |

The distribution is essentially uniform.

Gender-specific distributions are also flat:

- boys range from 19.62% all-court to 20.34% counterpuncher;
- girls range from 19.58% aggressive-baseliner to 20.29% serve-first.

There is therefore no population imbalance large enough to explain the head-to-head results.

---

## 9. Singles style-vs-style differential

Adjusted win differential in percentage points, with row style as the focal player and column style as the opponent:

| Focal \ Opponent | Aggressive baseline | All court | Balanced | Counterpuncher | Serve first |
|---|---:|---:|---:|---:|---:|
| Aggressive baseline | 0.0 | **+0.8** | +0.7 | +0.9 | +0.6 |
| All court | -0.8 | 0.0 | -0.9 | **-1.6** | +0.5 |
| Balanced | -0.7 | +0.9 | 0.0 | -0.2 | +0.6 |
| Counterpuncher | -0.9 | **+1.6** | +0.2 | 0.0 | -0.3 |
| Serve first | -0.6 | -0.5 | -0.6 | +0.3 | 0.0 |

The largest adjusted effect is:

> **counterpuncher vs all-court: +1.6 percentage points**

That matchup appeared 5,989 times from the focal perspective. Counterpunchers won 51.7% versus a rating-based expectation of 50.2%.

Other small effects:

- aggressive baseliner vs counterpuncher: +0.9 pp
- balanced vs all-court: +0.9 pp
- aggressive baseliner vs all-court: +0.8 pp

The singles conclusion is strong:

> **Style has little practical effect on singles outcomes once rating is controlled.**

---

# Part III — Doubles pair-type efficiency

## 10. Pair composition residuals

| Pair composition | N | Actual | Expected | Adjusted |
|---|---:|---:|---:|---:|
| all_court + all_court | 7,693 | 51.2% | 48.1% | **+3.1 pp** |
| all_court + serve_first | 16,153 | 52.1% | 49.2% | **+2.9** |
| serve_first + serve_first | 6,603 | 53.0% | 50.2% | **+2.9** |
| balanced + serve_first | 16,341 | 51.6% | 50.2% | **+1.4** |
| all_court + balanced | 16,259 | 50.4% | 49.4% | **+1.0** |
| all_court + counterpuncher | 15,920 | 50.2% | 49.6% | +0.6 |
| counterpuncher + serve_first | 20,703 | 50.1% | 49.7% | +0.4 |
| aggressive baseliner + all-court | 15,703 | 49.5% | 49.5% | 0.0 |
| aggressive baseliner + serve-first | 14,906 | 49.7% | 49.8% | -0.1 |
| balanced + balanced | 7,719 | 48.4% | 48.8% | -0.5 |
| balanced + counterpuncher | 15,527 | 50.5% | 51.6% | **-1.2** |
| aggressive baseliner + balanced | 15,871 | 48.5% | 50.2% | **-1.7** |
| counterpuncher + counterpuncher | 6,272 | 48.5% | 51.0% | **-2.5** |
| aggressive baseliner + aggressive baseliner | 8,067 | 47.9% | 51.0% | **-3.2** |
| aggressive baseliner + counterpuncher | 15,755 | 47.8% | 51.3% | **-3.4** |

The effect appears in both genders independently, which makes it more credible than a single-population artifact.

---

# Part IV — Program-level slot efficiency

## 11. Largest positive residuals

| Program | Class | Slot | Matches | Actual | Expected | Residual |
|---|---|---:|---:|---:|---:|---:|
| Cheney | 5A boys | S2 | 24 | 66.7% | 34.4% | **+32.3 pp** |
| Mission Terrace | 7A boys | S2 | 28 | 78.6% | 48.4% | **+30.2** |
| Gallego Bay | 3A girls | S2 | 26 | 65.4% | 35.5% | **+29.9** |
| River Oaks | 8A girls | D3 | 21 | 47.6% | 19.0% | **+28.7** |
| Skypark | Group 2 boys | S3 | 27 | 81.5% | 54.2% | **+27.3** |
| Driftwood | 4A boys | D2 | 27 | 48.1% | 21.4% | **+26.7** |
| Ryken | 4A boys | D2 | 33 | 78.8% | 53.6% | **+25.2** |
| Kennedy | Group 1 girls | D2 | 36 | 80.6% | 56.4% | **+24.2** |
| Vespertine | 8A boys | D3 | 34 | 67.6% | 43.6% | **+24.0** |
| Kernwood Lutheran | 1A boys | D2 | 29 | 44.8% | 21.9% | **+22.9** |
| Prune Springs | 4A boys | D1 | 33 | 72.7% | 50.0% | **+22.7** |
| Valley Christian | 6A girls | D1 | 32 | 96.9% | 79.7% | **+17.2** |

---

## 12. Largest negative residuals

| Program | Class | Slot | Matches | Actual | Expected | Residual |
|---|---|---:|---:|---:|---:|---:|
| Quincy | Group 3 girls | S1 | 29 | 24.1% | 55.2% | **-31.1 pp** |
| Cortland | 9A boys | D4 | 22 | 18.2% | 48.6% | **-30.5** |
| Temescal | 8A girls | D1 | 35 | 31.4% | 60.6% | **-29.2** |
| Benchlands | 5A boys | S1 | 27 | 33.3% | 62.2% | **-28.9** |
| Amelia | 9A girls | D1 | 26 | 19.2% | 47.2% | **-28.0** |
| Echo | 2A boys | S2 | 24 | 8.3% | 36.0% | **-27.7** |
| Dovetail | Group 3 girls | D3 | 26 | 15.4% | 42.5% | **-27.1** |
| Bannock | 9A boys | D2 | 26 | 0.0% | 26.0% | **-26.0** |
| Twin Mills | 9A girls | S1 | 31 | 51.6% | 75.3% | **-23.7** |
| Barkley | 2A boys | D2 | 35 | 37.1% | 59.3% | **-22.2** |
| Barclay | 3A boys | D2 | 33 | 63.6% | 82.9% | **-19.3** |
| Lyle | 1A boys | D3 | 26 | 15.4% | 41.5% | **-26.2** |

---

## 13. Quincy (Group 3 girls): upper-lineup underperformance

Quincy (Group 3 girls) is the clearest broad negative example.

- S1: 24.1% actual vs 55.2% expected
- S3: 33.3% vs 54.4%
- D1: 44.8% vs 62.0%

Arianna Hernandez handled S1 in 21 of 29 matches at current grade 68 and balanced style.

Balanced style does not carry anything close to a -31-point singles penalty association-wide.

**Strategic read:** Quincy (Group 3 girls) is getting materially less value from its upper lineup than its grades predict. This is a lineup/role or player-performance problem, not a style-tax explanation.

---

# Governing conclusions

## 14. What is actionable

### Singles

Do **not** broadly stack or shuffle S1–S3 on style alone.

The largest style effect is too small to justify sacrificing rating order.

### Doubles

Use pair composition as a secondary optimization layer.

Among comparably rated candidates, prefer:

- all-court + all-court
- all-court + serve-first
- serve-first + serve-first
- balanced + serve-first

Be cautious with:

- aggressive-baseliner + counterpuncher
- aggressive-baseliner + aggressive-baseliner
- counterpuncher + counterpuncher
- aggressive-baseliner + balanced

### Program auditing

The most useful new analytic surface would be a per-program slot table:

`slot | actual W% | expected W% from grade | residual | N`

This immediately surfaces where a program is extracting unusual value or leaving value unused.

### Priority programs for future lineup review

- **Robledo (7A boys):** repeatable doubles overperformance across D1–D3; likely positive construction signal.
- **Temescal (8A girls):** D1 pair appears structurally inefficient relative to player grades.
- **Mission Terrace (7A boys):** S2 massively outperforms rating expectation; player/role anomaly worth tracking.
- **Quincy (Group 3 girls):** upper-lineup underperformance across multiple slots.

---

## 15. Follow-up work

The next useful step is not another global style table. It is a **program-specific lineup permutation tool** that can:

1. take a program's available players;
2. enumerate plausible S1–S3 and D1–D2 configurations;
3. score them against a named opponent using rating-based win probabilities;
4. add the empirically observed doubles pair-composition adjustment;
5. return expected dual points and team-win probability for each lineup.

That would turn the descriptive findings in this report into an actionable pre-dual strategy surface.