# The development model as it stands — baseline, 2026-08

*Measured before any redesign, so a later change has something to be compared against.*
Sources: the shipped code, and three consecutive live JHSAA seasons (2057, 2058,
2059, both genders — research exports, ~17.8k girls' and ~17.3k boys' players a
season). Reproduce the numbers with:

```
python3 scripts/dev_model_baseline.py <dir holding YEAR/GENDER/players.csv>
```

`players.csv` carries a stable `player_id`, `grade`, `current_grade` and
`potential_grade`, so three consecutive seasons let the same person be followed
across a real career rather than inferred from the constants.

> ⚠️ Nothing here is a bug report. Every number below is what the constants say
> the model should do. The point of the document is that several of those
> constants do something different from what the code comments around them
> claim, and the gap only shows up in aggregate.

---

## 0. There are TWO development models, and they share almost nothing

| | college / pros / juniors | JHSAA |
|---|---|---|
| where | `app/development.py` | `app/jhsaa.py` (`_dev_maturity`, `_gen_seat`) |
| state | players PERSIST; growth banks into `world_roster` at rollover | players are REGENERATED every season from `(school, gender, entry year, seat)` |
| mechanism | `Prospect.develop()` closes a fraction of the gap to a fixed ceiling | the same fixed ceiling read at a higher MATURITY each grade |
| driver | `interest_rate × GROWTH_K × tier_mult` | an arrival→finish curve with a per-player shape exponent |
| fog | two-source `scouting_report` + a lighter `scouted_read` | none — the OVR is shown |

`Prospect.develop()` is **never called for a JHSAA player**. The two halves of
the sim reached the same destination — "nobody regresses, everyone improves, the
variation is fixed at generation" — by different routes, and they are tuned
independently.

---

## 1. The core model (`app/development.py`)

This is the owner's baseball-sim model ported, down to the vocabulary
(`interest_rate`, `tier`, `tier_mult`, `fog`, `consensus_seed`).

**Generation** (`generate_prospect`, `development.py:528`)
1. a `talent` mean → 49 per-attribute **`potential`** ceilings, `gauss(talent, 6)`;
2. shaped by playstyle (`_apply_style_profile`), weight-normalised so shape moves
   and overall does not;
3. squashed at the top (`compress_talent` tanh above a knee, then
   `trim_prospect_ceiling`), with a 1-in-500 elite exemption;
4. a **`maturity`** draw → `current = potential × maturity` — the *access lens*;
5. an **interest tier**: ordinary 75% / late bloomer 20% / super-bloomer 5%,
   multipliers 1.0 / 1.3 / 1.6;
6. a `fog` ∈ [7, 31].

**Growth** (`Prospect.develop`, `development.py:429`)

```
frac = interest_rate × GROWTH_K (0.12) × tier_mult × scale
current[a] += frac × (potential[a] − current[a])
```

Exponential gap-closing toward a ceiling that never moves. Deterministic, no
mid-career rerolls, no regression. Staggered across a 16-week season
(`stagger_scale`) so mid-season snapshots differ while the year-end total is
identical for everyone, and scaled by the coach's ±30% development multiplier.

### 1a. Three divergences from the model it was ported from

**The potential/access relationship is inverted.** In the baseball model
potential GROWS yearly and access is STATIC, so `displayed = P × A` and a hidden
gem stays hidden for four years. Here potential is frozen at generation and
access is the thing that moves. Consequences: there is no static lens, so there
is no hidden gem; and there is no reveal — the pro engine plays the same
`current` the college engine did, so nothing drops on signing.

**The rates are calibrated to near-zero.** The tier rate ranges are multiplied by
`GROWTH_K = 0.12`:

| tier | share of class | gap closed per year |
|---|---|---|
| ordinary | 75% | **0.6% – 6.0%** |
| late bloomer | 20% | 7.8% – 18.7% |
| super-bloomer | 5% | 23.0% – 42.2% |

A median ordinary player — three-quarters of every class — with a 60 ceiling
entering at 51.9 finishes senior year at **52.7**. That is **+0.8 OVR across a
four-year career**. The median super-bloomer reaches 57.5.

**There is no inverse cap.** What makes the baseball curves dramatic is
`cap_base = C_MAX × (1 − normalised P)` — low-potential players get *larger*
yearly steps, so a 30 can climb to 70. Nothing here does that. Growth is strictly
proportional to the remaining gap, so a low-ceiling player has a small gap and
therefore the smallest absolute growth. Low-ceiling players are frozen.

### 1b. And college freshmen arrive with the lens already open

`ncaa._CLASS_MATURITY` is `Fr (0.83, 0.90)` → `Sr (0.93, 0.99)`. A college
freshman already shows ~86% of their ceiling. With §1a's rates on top, the entire
college development arc is worth 1–5 OVR. **The college problem is not "wait
until senior year" — it is that class year barely means anything at all.**

---

## 2. The JHSAA model (`app/jhsaa.py`)

Rosters are not persisted, so "development" is: same fixed ceiling, read at a
higher maturity each grade. Two era-gated regimes (`dev_era()`):

* **Legacy** `_MATURITY` — lockstep bands, 9th .40–.48 → 12th .70–.78, one
  uniform draw mapped into each grade's band. The whole association climbs in
  step and the ladder never reorders. This is the model the 2026-08 pass replaced.
* **New era** `_dev_maturity` (`jhsaa.py:1258`) — a whole trajectory rolled once
  at entry on its own rng stream: arrival .40–.64 (or .66–.82 for the 24%
  `DEV_READY_RATE` "arrive ready" share), finish .76–.94, `DEV_MIN_RISE` 0.16,
  `DEV_MIN_STEP` 0.045/yr floor, `DEV_CAP` 0.98, and a curve **shape** exponent
  (steady 38% / early 36% / late 21% / spike 5%). Plus a 1% `PRODIGY` maturity
  floor of .84–.93 that persists all four years.

Structurally this is the closer of the two to the owner's philosophy — a full
path fixed at entry, deterministic, no rerolls. It is parameterised as a
*maturity curve* rather than an interest rate, and it has no fog layer at all.

---

## 3. What the live association actually produced

All figures from the 2057-2059 exports; §3.1 and §3.4-3.6 are the 2059 season.

### 3.1 Access by grade — the bands barely overlap

| grade | n (girls) | mean | p10 | p50 | p90 | mean cur | mean ceiling |
|---|---|---|---|---|---|---|---|
| 9 | 4,774 | 0.614 | 0.455 | 0.596 | 0.800 | 28.7 | 47.8 |
| 10 | 4,265 | 0.706 | 0.569 | 0.702 | 0.842 | 33.5 | 47.9 |
| 11 | 4,349 | 0.781 | 0.675 | 0.781 | 0.885 | 37.4 | 48.1 |
| 12 | 4,367 | 0.870 | 0.791 | 0.875 | 0.938 | 45.9 | 52.9 |

Boys are within a point of these on every row (0.607 / 0.696 / 0.774 / 0.867).

> **13.4% of freshmen reach the junior median access; 1.3% reach the senior
> median.** (Boys 13.8% / 1.1%.) The trajectory model widened the bands — the
> legacy lockstep model put 0.0% of freshmen above the senior median — but not
> nearly enough to break grade order.

### 3.2 A cohort confound to be aware of when reading §3.1

Mean ceiling by ENTRY year shows a clean step at 2057:

| entry | 2054 | 2055 | 2056 | 2057 | 2058 | 2059 |
|---|---|---|---|---|---|---|
| girls | 53.0 | 53.3 | 52.9 | **48.0** | 47.8 | 47.8 |
| boys | 57.0 | 56.7 | 56.8 | **53.7** | 53.0 | 52.6 |

That is `talent_era` — the 2026-08 talent-compression rule — phasing in, not a
development effect. **The 2059 seniors' +5 (girls) / +4 (boys) ceiling advantage
over the freshmen in §3.1 is entirely this**, and it disappears once the
association is fully compressed (from 2060). Any before/after comparison spanning
this boundary must control for entry year.

### 3.3 Careers move a real amount — the ceiling does not

Same player, 2057 → 2059:

| entered span as | n (girls) | mean | p10 | p50 | p90 |
|---|---|---|---|---|---|
| grade 9 | 4,349 | +8.5 | +2.0 | +8.0 | +16.0 |
| grade 10 | 4,367 | +9.3 | +3.0 | +8.0 | +17.0 |

Boys +9.7 and +10.2. So the *quantity* of high-school development is healthy —
roughly +4 to +5 OVR a year, with a genuine spread from +1 to +8. The ceiling
over the same span moves for **1.0–1.1% of players, mean +0.02** — i.e. it is
fixed, exactly as designed.

### 3.4 But the ladder does not reorder

**Returning teammates swap ladder order 7.7% of the time (girls) / 7.8% (boys)**
year over year, over ~180k pairs. Everyone climbs by a similar amount at a
similar time, so nearly every relative ordering established in a player's first
season survives to their last. 76.2% of girls (74.7% boys) present all three
seasons post their best roster rank in the final year.

### 3.5 The consequence: seniority is arithmetic, not tendency

2059, against the 11-player varsity lineup:

| grade | in the lineup (share of grade) | share of No. 1 seats |
|---|---|---|
| | girls / boys | girls / boys |
| 9 | 31.9% / 31.5% | **1.5% / 1.7%** |
| 10 | 49.2% / 47.9% | 3.3% / 4.6% |
| 11 | 66.3% / 65.6% | 9.4% / 12.2% |
| 12 | 80.7% / 80.3% | **85.7% / 81.5%** |

Seniors hold ~85% of the No. 1 seats in girls' tennis and ~82% in boys'. A
freshman is the best player at their school roughly once in sixty programs.

### 3.6 How much is hidden

Rank each roster by CEILING instead of current ability and the lineup holds
**2,614 freshmen (54.8%) instead of 1,523 (31.9%)** — girls; boys 2,494 (53.4%)
vs 1,469 (31.5%). **1.7× the freshmen who deserve to be on court are not.**

### 3.7 A quarter of the association never plays

Of the 8,716 girls (8,464 boys) present in all three seasons, **25.4% (25.8%)
never once reached the 11-player lineup in any of them.** That is the population
the owner is describing as "never going to play", and it is currently a
population whose development is entirely unobservable — nothing about it is
visible, nothing about it feeds back, and nothing about it can surprise anybody.

### 3.8 Ceiling and current sort a roster equally hard

Mean within-program standard deviation: current **10.73**, ceiling **10.81**
(boys 11.62 / 11.86). They are the same size. So a program's ceiling spread is
not narrow in absolute terms — the reason the maturity ladder wins is that
maturity is *correlated with grade* while ceiling is not, and a systematic
grade-ordered term beats an uncorrelated one of the same magnitude every time.

---

## 4. Why underclassmen cannot surprise you, in one paragraph

A player's ceiling is drawn once at generation and never moves — §3.3 confirms it
empirically in both models. The only uncertain quantity is what fraction of a
known ceiling is currently visible, and that fraction is a tight, grade-ordered
band (§3.1). So the sim's talent is fully determined at birth and revealed on a
schedule that is nearly the same for everybody. Surprise requires the CEILING to
be mobile — in the baseball model potential grows, and grows *fastest for the
players with the least of it*. Neither model here has any mechanism by which a
player can turn out to be better than they were born, only a mechanism by which
they arrive at what they were born with at a slightly different time.

A secondary point, worth naming before any redesign: **development is currently
100% independent of playing.** The college coach multiplier is the only feedback
loop anywhere in either model. Nothing about a season's results, playing time,
opponent quality or lineup position changes any player's trajectory.

---

## 5. Scoreboard against the source model

| mechanic | college | JHSAA |
|---|---|---|
| potential / access split | inverted — access closes, potential fixed | maturity-as-access, potential fixed |
| interest rate | present, calibrated to ~noise (§1a) | **absent** — a shape exponent instead |
| inverse cap (low ceiling grows fastest) | **absent** | **absent** |
| two-source scouting fog | present, plus a lighter "today" read | **absent** |
| no regression, no rerolls | yes | yes |
| reveal on turning pro | **absent** — no lens ever drops | n/a |

---

## 6. Constants a redesign will touch

* `development.TIERS`, `GROWTH_K`, `MATURITY_MIN/MAX`, `FOG_MIN/MAX`
* `development.compress_talent` / `trim_prospect_ceiling` and `talent_era()` —
  any ceiling-mobility mechanic has to compose with the compression rule
* `ncaa._CLASS_MATURITY`
* `jhsaa.DEV_ARRIVAL`, `DEV_READY_RATE`, `DEV_READY_ARRIVAL`, `DEV_FINISH`,
  `DEV_MIN_RISE`, `DEV_MIN_STEP`, `DEV_CAP`, `DEV_SHAPES`, `PRODIGY_*`
* `jhsaa.ladder_score` / `LADDER_SWING` — the ladder is what turns ability into a
  seat, and §3.4 is as much about the ladder as about development

**‼️ Anything touching JHSAA generation must be era-gated** (`dev_era()` /
`talent_era()` / `name_era()`, all the same idiom). Players are regenerated from
seed, so an ungated change re-rates every archived season's ladders, player cards
and awards. §3.2 is what a phased era boundary looks like in the data — plan for
four seasons of mixed cohorts and design the measurement to control for it.

---

## 7. Files

* `scripts/dev_model_baseline.py` — the measurement, re-runnable against any
  export set.
* Prior art worth reading first: `docs/AAR-jhsaa-development-curves-and-rest-staffing.md`
  (the 2026-08 trajectory pass — the change that produced §3.1's current bands),
  `docs/AAR-talent-compression.md` (§3.2's era boundary),
  `docs/AAR-coach-development-growth.md` (the one feedback loop that exists),
  `docs/AAR-jhsaa-order-of-ability.md` / `jhsaa.ladder_score` (§3.4).
