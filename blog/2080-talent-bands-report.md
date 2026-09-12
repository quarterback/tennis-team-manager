# Program talent bands — the case, the data, and what changes

**Measured on the 2080 export.** 17,505 boys and 18,158 girls across 877 and 914 programs.
203,716 sets over 84,171 best-of-3 matches association-wide.

---

## 1. What we set out to explain

The Scoreline Realism page reports the association sitting **32.8 from the Oregon
baseline**, and nearly all of that distance is in two buckets:

| Set | JHSAA 2080 | Oregon (41,932 matches) |
|---|---|---|
| 6-0 | **4.1%** | **26.4%** |
| 6-1 | **11.0%** | **21.5%** |
| 6-2 | 17.4% | 17.4% |
| 6-3 | 21.5% | 13.4% |
| 6-4 | 23.4% | 12.3% |
| 7-5 | 10.9% | 5.1% |
| 7-6 | 11.6% | 3.9% |

Our distribution peaks at 6-4. Oregon's peaks at 6-0. Real high-school tennis is mostly
blowouts; ours is mostly competitive sets. The engine is stationary — every bucket moved
less than 0.3 points on 2079 — so this is a structural property, not drift.

**This document is about producing more blowouts. It is not about parity.** The knock-on
effects described in §5 are the intent, not a cost.

## 2. Where the blowouts aren't coming from

### Flight-level gaps are small

Every varsity flight in 2080, bucketed by the OVR gap between the two sides (86,223 matches):

| percentile | gap |
|---|---|
| p10 | 1.0 |
| p25 | 3.0 |
| **p50** | **6.0** |
| p75 | 10.5 |
| p90 | 16.0 |
| p95 | 20.0 |
| p99 | 27.0 |

- gap ≥ 20: **5.0%** of matches
- gap ≥ 30: **0.6%** of matches

A 6-0 needs roughly a 25-30 point gap under the current curve. Those matchups are six
tenths of one percent of the season.

### Team-level gaps are smaller still

Team strength = mean of the top 11. Across 12,460 duals:

| percentile | team gap |
|---|---|
| p50 | 4.2 |
| p90 | 11.9 |
| p99 | 20.5 |

- duals with a team gap ≥ 20: **1.2%**

### But rosters are internally very unequal

Within a single program, best player minus 11th player:

- **median 35 points**
- p90 **49 points**

**‼️ That combination is the whole finding.** Rosters are internally unequal (35-point
internal spread) but externally equal to each other (4.2-point median team gap). Both
teams decline down the ladder at the same rate, so every flight is a near-peer matchup and
the internal spread cancels out.

## 3. The real constraint: there is no bottom tier

Team strength (mean of top 11), 2080:

| band | boys programs | girls programs |
|---|---|---|
| under 30 | **0** | **1** |
| 30-40 | 43 (5%) | 103 (11%) |
| 40-50 | 258 (29%) | 331 (36%) |
| 50-60 | **365 (42%)** | **392 (43%)** |
| 60+ | 211 (24%) | 87 (10%) |

- boys: mean **53.5**, sd **8.3**, min **33**, max 76
- girls: mean **49.9**, sd **7.7**, min **30**, max 74

**71% of boys programs sit between 40 and 60.** The weakest program in the entire boys
association averages 33 — an ordinary team that isn't very good, not a genuinely
overmatched one. Weakest five: Foothills Christian 33, Elk Bluff 34, Wolf Gap
International 34, Pine Eagle 35, Free Hill 35. Strongest: Notre Dame 76, Baptist 74,
Montclair 74, Rockridge 74, Valley Christian 73.

There is no "all 20s" program. There is no "20s and 30s with a stray 40" program.

### Why: every program draws from one shared distribution

Player ratings association-wide:

| | boys | girls |
|---|---|---|
| p10 | 23 | 22 |
| p50 | 42 | 39 |
| p90 | 66 | 62 |
| p99 | 85 | 80 |
| mean / sd | 43.6 / 16.3 | 40.7 / 15.1 |
| share above 85 | **1.0%** | **0.5%** |
| share below 30 | 23.4% | 27.9% |

Grade progression is healthy and should not change — boys median rises 36 → 40 → 44 → 48
across grades 9-12 with sd stable at 15-16.5.

The population itself is fine. The problem is that **a weak program and a strong program
draw from the same pool**, so a bad school still ends up with a 60-something at the top and
a 25 at the bottom. It is the same 35-point internal spread as everyone else, shifted down
a few points.

## 4. The change

**Assign each program a talent band at generation. Draw its roster from within that band.**

Indicative shape:

| tier | draw range |
|---|---|
| bottom | 18-38 |
| lower-mid | 28-50 |
| mid | 35-65 |
| upper-mid | 45-78 |
| top | 50-95 |

**‼️ The band must persist across seasons.** Roll it once per program and store it on the
program record alongside the archetype tags (Blueblood / Coaching / Turnout / Home court),
not per season. A band that re-rolls annually makes a school's identity flip year to year
and destroys the thing it is for.

This is a different mechanism from the existing archetypes. Blueblood modifies *draws from
the shared distribution*; a talent band replaces the distribution itself for that program.

## 5. Expected effects — all intended

- **Team-strength sd widens from ~8.3 to roughly 15-18.** The floor drops from 33 into the
  low 20s.
- **Duals with a 20+ point team gap rise well above the current 1.2%**, which is the
  mechanism that produces 6-0 and 6-1 sets.
- **Bottom-tier schools get real tennis against each other.** Two 25-average programs play
  nine genuinely competitive flights — a 22 against a 26 — which does not exist today,
  because those schools currently have one good player carrying them.
- **Bottom-tier schools get blasted when a 60-average team visits**, 9-0 with 6-0 sets.
- The competitive middle (40-70, currently 48% of boys players) is untouched if the bands
  overlap as above.

## 6. What to measure afterwards

Against these 2080 baselines:

| metric | 2080 baseline |
|---|---|
| 6-0 share | 4.1% |
| 6-1 share | 11.0% |
| flight gaps ≥ 20 | 5.0% |
| flight gaps ≥ 30 | 0.6% |
| duals with team gap ≥ 20 | 1.2% |
| team-strength sd (boys) | 8.3 |
| weakest program (boys) | 33 |
| programs 40-60 (boys) | 71% |
| distance from Oregon | 32.8 |

Check the **showcase** phase separately. It already runs a different profile (6-0 at 5.2%,
three-set rate 36.4% against the association's 42.0%) and its sample moved 29% year over
year, so read it on its own rather than blended into the association total.
