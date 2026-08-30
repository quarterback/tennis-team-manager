# Proposal — Player Development Model Redesign

**Status:** Design proposal / decision record  
**Scope:** JHSAA high school and NCAA college player development  
**Date:** 2026-08  
**Purpose:** Preserve the full reasoning behind two viable redesign directions before implementation, so the design can be revisited later without reconstructing the conversation or intent from code comments.  
**Direction:** **Option C (§22)** — starting ability / career peak / yearly
capacity / exposure. Options A (§5) and B (§6) are retained as the record of what
was considered and rejected.  
**Related baseline:** `docs/REPORT-development-model-baseline.md`  
**Related reproducibility scripts:** `scripts/dev_model_baseline.py`,
`scripts/dev_model_access_experiment.py`, `scripts/oregon_lineup_shape.py`

> ‼️ **§21 AMENDS THIS DOCUMENT AND WINS WHERE THEY DISAGREE.** Sections 1-20 are
> the proposal as written before the access models were A/B'd against real
> rosters and against six seasons of real OSAA results. §21 records what those
> measurements showed. It changes which constant does the work (§21.2), supplies
> the real-world targets the redesign is graded against (§21.3a), replaces the
> headline success metric (§21.4), and **withdraws two claims an earlier draft of
> §21 made** — an odometer guardrail (§21.5) and a roster-persistence blocker
> (§21.6), both corrected by the owner. Read §21 alongside §12 (measurement plan)
> and §17 (implementation questions).
>
> ‼️ **§22 IS THE CHOSEN MODEL** and supersedes §16's Option B preference. §21's
> measurements still stand as the description of the problem; §21.3a's Oregon
> figures are context, NOT tuning targets (see §22.7).

---

# 1. Why this proposal exists

The current tennis development systems do not produce enough variation in *career shape*.

This is not primarily a problem of insufficient growth. The high-school model already generates meaningful year-over-year rating gains. The problem is that most players improve on broadly similar age-linked schedules, so they rise together rather than overtaking one another. The ladder therefore remains much more stable than the underlying amount of development would suggest.

The college system has a different surface symptom but a related structural problem: players begin with a large share of their fixed ceiling already available, while the ordinary development rate closes so little of the remaining gap that many four-year college careers barely change.

The result in both systems is a narrower range of possible player stories than desired.

The redesign should create players who can plausibly be:

- elite immediately as freshmen;
- nearly finished products when they arrive;
- steady developers;
- early bloomers;
- late bloomers;
- one-year spike developers;
- stagnant players;
- high-upside players who never realize most of that upside;
- ordinary players who become useful because they develop earlier than peers;
- highly rated players whose development plateaus;
- players who meaningfully reorder their school ladder over time.

The core philosophical change is this:

> **For this game, the relevant “peak” is the best version of the player that appears while the player is in high school or college. The model does not need to preserve unused talent for a hypothetical later professional career.**

The small pro sidecar is not important enough to justify designing high-school and college development around a future reveal. The high-school and college games should get to use the player’s interesting development while that player is actually present in those games.

---

# 2. Baseline findings

The redesign should be judged against measured behavior, not only against constants.

The baseline report found the following.

## 2.1 High-school development quantity is not the main problem

Across observed cohorts, freshmen gained roughly:

- **Girls:** +8.5 OVR over two years
- **Boys:** +9.7 OVR over two years

The distribution was not completely flat: approximately p10 +2 to p90 +16.

That is enough raw movement to create meaningful careers.

The problem is that returning teammates swap ladder order only **7.7%** of the time.

In other words:

> Players improve, but they mostly improve in parallel.

This makes a player’s first-season rank unusually predictive of their later rank.

## 2.2 Grade-access bands remain strongly ordered

The newer JHSAA development trajectory improved overlap relative to the old lockstep model, but not enough.

Measured maturity distribution under the new model:

| Grade | Mean | p10 | p50 | p90 |
|---|---:|---:|---:|---:|
| 9 | 0.572 | 0.432 | 0.559 | 0.748 |
| 10 | 0.679 | 0.553 | 0.675 | 0.817 |
| 11 | 0.766 | 0.670 | 0.763 | 0.869 |
| 12 | 0.865 | 0.785 | 0.869 | 0.935 |

Only:

- **1.3% of freshmen exceed the senior median**
- **13.4% of freshmen exceed the junior median**

This is better than the original lockstep model, where freshman-over-senior-median was effectively zero, but seniority remains built into the arithmetic.

## 2.3 Seniority dominates No. 1 singles

Measured No. 1-seat shares:

- **Girls seniors:** 85.7%
- **Boys seniors:** 81.5%
- **Freshmen:** approximately 1.5%

That is too age-deterministic for a sport where unusually advanced younger players should occasionally be among the best players in a school, league, or state.

## 2.4 A large amount of ceiling is hidden behind maturity

When rosters are ranked by ceiling rather than current ability, freshman lineup presence rises from roughly **31.9% to 54.8%**.

That is approximately **1.7× as many freshmen**.

This does not mean all of those freshmen should play varsity. It demonstrates that the system has substantial underlying talent that cannot become competitively relevant because the grade-based access structure suppresses it.

## 2.5 A meaningful population still does not play

Approximately **25.4% of players never reach a varsity lineup during the observed three-season window**.

This mattered when JHSAA did not have a JV system. Tying development to playing time would have trapped buried players:

`no varsity opportunity → no development → no varsity opportunity`

That constraint has changed.

JV now gives most rostered players a competitive environment, making it possible for participation to influence development without condemning every non-varsity freshman to stagnation.

## 2.6 Ceiling is effectively immobile

Across observed high-school players, ceiling changes for only about **1.0%** of players and the mean change is approximately **+0.02**.

In practical terms, ceiling is fixed.

Therefore almost all surprise must currently come from maturity/access.

But maturity/access is strongly grade-ordered.

That leaves very little room for unexpected player development.

## 2.7 The talent-compression transition must be controlled for

There is a live cohort boundary from the talent-compression change.

Older cohorts were generated under the hotter talent distribution, while new cohorts are generated under compressed ceilings. This means apparent grade differences in POT/ceiling during the transition are partly generation-history differences rather than development differences.

Any before/after development analysis through the transition must control for **entry year**.

The compression transition should be fully cleared after the final pre-compression cohort graduates.

---

# 3. Current model architecture

There are presently two different development systems in the same repository.

---

## 3.1 College / core prospect model

The core `app/development.py` model uses concepts inherited from the baseball design:

- fixed per-attribute potential;
- maturity/access applied to potential to create current ability;
- interest-rate tiers;
- scouting fog;
- deterministic development;
- no regression;
- no annual talent-change rerolls.

Current development closes a fraction of the remaining current-to-potential gap:

```python
frac = interest_rate * GROWTH_K * tier_mult * scale
current[a] += frac * (potential[a] - current[a])
```

The important difference from the baseball design is that:

- **potential is fixed**
- **access/current moves**
- there is no later reveal where a static access lens drops away.

The ordinary interest-rate calibration is also very weak.

Approximate share of remaining gap closed per year:

| Tier | Population | Approx. gap closed/year |
|---|---:|---:|
| Ordinary | 75% | 0.6%–6.0% |
| Late bloomer | 20% | 7.8%–18.7% |
| Super-bloomer | 5% | 23.0%–42.2% |

A median ordinary player can therefore spend four college seasons changing very little.

College freshmen also enter with a high maturity band, roughly 0.83–0.90, so college does not have the same severe freshman suppression as high school. Its problem is more often **development that is too weak to create meaningful career transformation**.

---

## 3.2 High-school model

JHSAA does not call `Prospect.develop()`.

Players are regenerated deterministically from player identity, school, gender, entry year, and roster seat. Development is represented by reading the same underlying ceiling through a grade-dependent maturity trajectory.

The current new-era HS model rolls a full trajectory at entry:

- arrival band;
- finish band;
- minimum rise;
- minimum annual step;
- curve-shape exponent;
- ready-player path;
- rare prodigy floor.

The broad curve categories are:

- steady
- early
- late
- spike

This is already closer to the desired philosophy than the legacy lockstep system because the career path is determined at entry rather than rerolled each season.

However, it still assumes:

- almost everyone meaningfully rises;
- later grades generally access more;
- finish bands remain tightly grade-ordered;
- stagnation is not a first-class outcome;
- a genuinely elite freshman still tends to be interpreted as an unfinished version of a future senior.

That is the core behavior this proposal addresses.

---

# 4. Shared design principles

Both redesign options below should follow the same principles.

## 4.1 Development is not a reward for winning

Team quality must not determine development.

A player on a 2–20 team should not develop more slowly simply because the team loses.

A player going 4–20 in varsity should still gain more developmental value from playing than a comparable player sitting all season.

The model should measure **competitive exposure**, not success.

No development component should directly use:

- wins;
- win percentage;
- team record;
- league finish;
- TOSS;
- State team qualification.

---

## 4.2 Playing time should matter

Participation should work like an odometer.

The conceptual ordering is:

```text
sitting < JV participation < varsity participation
```

JV should be worth less than varsity, but materially more than sitting.

The simplest form is fixed appearance value:

```text
JV appearance      = small exposure unit
Varsity appearance = larger exposure unit
```

The system should use a saturating or capped season total so that 35 matches is not wildly more valuable than 25 matches.

Illustrative only:

```text
JV appearance      = 0.5 exposure
Varsity appearance = 1.0 exposure
Normal exposure cap = 20–25 varsity-equivalent units
```

The exact constants require simulation rather than design-by-example.

---

## 4.3 Playing time accelerates realization; it does not manufacture ceiling

Participation should help a player access growth already available to that player.

It should not convert an ordinary ceiling into an elite one.

Conceptually:

```text
development character
    determines available growth

playing exposure
    determines how much of that growth is realized

current ability
    receives the realized growth
```

This distinction allows:

- a stagnant player to play constantly and still improve little;
- an explosive developer to realize more of a major growth window if they are playing;
- a buried JV player to progress toward varsity rather than remain frozen;
- an already-developed prodigy to gain little because there is little relevant growth remaining.

---

## 4.4 Stagnation must be a real career outcome

The current model effectively guarantees meaningful growth.

The redesign should allow players whose competitive-career ability barely changes.

Examples:

```text
42 → 42 → 43 → 43
```

or:

```text
51 → 51 → 52 → 52
```

This is different from regression.

The player does not get worse. The player simply fails to add much.

---

## 4.5 Development character should be assigned at generation

The baseball design’s strongest principle should remain:

> Surprise should come from discovering what kind of developer the player always was, not from the universe rerolling the player every offseason.

Therefore the redesign should avoid OOTP-style annual talent-change randomness.

Randomness can exist at generation in:

- growth amount;
- timing;
- plateau length;
- access schedule;
- career peak;
- stagnation probability;
- spike timing;
- response to competitive exposure.

Once generated, the path should be deterministic except for explicitly designed exceptional-event mechanics.

---

## 4.6 High school and college should use the talent while they have it

The game does not need to hold back development because a player might theoretically be better after graduation.

For design purposes:

- HS potential/peak should describe the meaningful high-school window.
- College potential/peak should describe the meaningful college window.

A freshman who is already elite can simply be elite.

A sophomore can peak.

A junior can plateau.

A senior can bloom late.

There is no requirement that the player’s chronological final season be their best season.

---

## 4.7 State individual advancement may provide a small exceptional-development allowance

Regular match success should not influence development.

Individual State competition is a separate case because it represents concentrated, high-level competitive exposure.

The proposed mechanic is **not a raw rating award for winning**.

Instead, a sufficiently deep individual-State run may raise the normal annual realization cap by a small amount.

Conceptually:

```text
normal seasonal development cap = X
individual-State breakthrough allowance = X + small extra capacity
```

If the player has no latent growth available, the allowance does nothing.

The tournament therefore cannot create talent ex nihilo.

The allowance can scale by flight:

- strongest for S1;
- smaller for S2/S3;
- smaller or differently calibrated for doubles flights;
- mixed doubles can be assigned an appropriate tier.

This should remain modest.

---

# 5. Option A — Explicit competitive-career trajectory model

## 5.1 Core idea

At generation, explicitly create the player’s entire relevant high-school or college development story.

Each player receives:

1. **starting ability**
2. **competitive-career peak**
3. **peak timing**
4. **development character / curve**
5. **playing-time responsiveness**

The model does not need an adult/pro ceiling to drive development.

Potential, if retained for UI or recruiting, can represent either the career-window peak or a broader upside estimate that is not guaranteed to be realized.

---

## 5.2 Development characters

A small explicit taxonomy can define typical curve shapes.

Suggested conceptual types:

| Type | Character |
|---|---|
| Ready | Arrives near peak; little subsequent growth |
| Early | Large early jump, then plateau |
| Steady | Moderate improvement throughout career |
| Late | Little early movement, large late growth |
| Spike | One concentrated development jump |
| Stagnant | Minimal improvement |
| Failed promise | Has apparent upside but realizes little of it |
| Exceptional | Rare large multi-year growth path |

These types do not need to be displayed to the user.

They are internal player identity.

---

## 5.3 Example trajectories

All examples are illustrative.

### Ready / prodigy

```text
61 → 63 → 64 → 64
career peak = 64
```

This player is already one of the best players in the state as a freshman.

The engine does not force the player to become a 70+ senior.

---

### Early developer

```text
44 → 57 → 59 → 60
career peak = 60
```

This creates a sophomore breakthrough.

---

### Steady developer

```text
36 → 43 → 49 → 55
career peak = 55
```

This resembles the conventional career arc.

---

### Late developer

```text
31 → 33 → 41 → 58
career peak = 58
```

This produces the senior who suddenly becomes important.

---

### Spike developer

```text
33 → 35 → 53 → 55
career peak = 55
```

This allows one dramatic offseason to reshape a roster.

---

### Stagnant player

```text
43 → 43 → 44 → 44
career peak = 44
```

Playing can help the player realize the small amount available but cannot create a major leap.

---

### Failed promise

```text
34 → 36 → 38 → 40
scouting/upside signal may suggest much more
competitive-career peak = 40
```

This is useful if the system retains a distinction between theoretical upside and realized-career peak.

---

## 5.4 How playing time interacts with Option A

The trajectory defines the **available intrinsic gain** for the season.

Playing exposure determines what share of that gain is actually realized.

Example:

```text
trajectory says sophomore target gain = +10

no play     → realizes +6
full JV     → realizes +8
full varsity→ realizes +10
```

Exact values would be calibrated.

The player is not punished by team losses.

---

## 5.5 Advantages of Option A

### Career stories are explicit

It naturally creates the exact archetypes the game wants.

The model can deliberately guarantee that all desired trajectory types exist in sensible proportions.

### Seniority can be broken cleanly

Nothing requires later grade to mean greater ability.

A ready freshman can be better than a stagnant senior without needing extreme ceiling differences.

### “Peak with me” is represented directly

The model explicitly asks:

> What is this player’s best high-school/college version?

That matches the design philosophy exactly.

### Easy to reason about in historical analysis

A player’s career can later be classified as early, late, stagnant, etc.

This may make long-term analysis and storytelling especially legible.

---

## 5.6 Risks / costs of Option A

### Adds a new concept: competitive-career peak

This is conceptually clean but adds another quantity that must coexist with existing `potential`.

The code and UI would need a clear answer to whether `potential`:

- becomes career peak;
- remains theoretical ceiling;
- becomes hidden;
- or is replaced.

### Can become over-authored

Explicit categories can make career shapes feel designed if distributions are too obvious.

The generator must still produce enough continuous variation inside each category.

### Requires more migration work

The current college and high-school systems are built around fixed potential and access/current.

Option A is the stronger conceptual break.

---

# 6. Option B — Individualized randomized access schedule

## 6.1 Core idea

Keep the existing fixed-potential concept, but stop tying access tightly to grade.

Each player receives a hidden, deterministic **year-by-year access schedule** at generation.

Example:

```text
9th  0.78
10th 0.81
11th 0.92
12th 0.93
```

Another player:

```text
9th  0.46
10th 0.48
11th 0.50
12th 0.51
```

Another:

```text
9th  0.52
10th 0.74
11th 0.76
12th 0.89
```

Current ability is derived from the player’s fixed talent ceiling through the individual access schedule rather than a statewide grade band.

Conceptually:

```text
current ability
    = potential × player-specific access
      modified by realized development / playing exposure
```

The important change is that **grade no longer determines the access band**.

Grade only tells the engine which point in this particular player’s generated schedule applies.

---

## 6.2 What Option B preserves

This is much closer to the current architecture.

It preserves:

- fixed potential;
- access/maturity as a concept;
- deterministic player identity;
- no regression;
- no annual rerolls;
- existing potential-based recruiting/scouting compatibility.

The redesign occurs mainly in how access is generated and updated.

---

## 6.3 Career shapes emerge from access schedules

The same career archetypes can appear without explicit labels.

### Ready player

```text
access:
0.90 → 0.92 → 0.93 → 0.94
```

A high-ceiling player can be elite immediately.

---

### Early bloomer

```text
0.52 → 0.78 → 0.81 → 0.83
```

---

### Steady

```text
0.52 → 0.62 → 0.72 → 0.82
```

---

### Late

```text
0.48 → 0.51 → 0.58 → 0.84
```

---

### Spike

```text
0.49 → 0.51 → 0.79 → 0.82
```

---

### Stagnant

```text
0.66 → 0.67 → 0.67 → 0.68
```

---

### High theoretical ceiling, low realized access

```text
potential = 70
access:
0.43 → 0.45 → 0.48 → 0.51

current:
30 → 32 → 34 → 36
```

This player never meaningfully realizes the nominal ceiling during high school.

That is acceptable under the new philosophy.

---

## 6.4 How playing time interacts with Option B

There are two plausible internal implementations, but the design intent is the same:

### Interpretation 1 — playing advances access toward the scheduled target

Each season has a generated target access.

Baseline development moves the player part of the way toward it.

JV and varsity participation allow the player to get closer.

Example:

```text
scheduled sophomore access = 0.72

sitting        → reaches 0.64
full JV        → reaches 0.68
full varsity   → reaches 0.72
```

### Interpretation 2 — playing provides a small additive access realization value

The player has a generated baseline access for the year, then accumulated exposure adds a bounded amount.

Example:

```text
base access = 0.68
JV exposure = +0.02
varsity exposure = +0.04
annual cap = generated schedule / realization ceiling
```

The first interpretation is conceptually cleaner because playing cannot push a player arbitrarily above the generated career shape except through explicit exceptional-event allowances.

---

## 6.5 Advantages of Option B

### Smaller conceptual break

It keeps the current fixed potential + access architecture.

### Closest to the baseball access philosophy

A player may possess significant potential while accessing very different amounts of it during the relevant competitive career.

### Naturally supports stagnation

A player can simply draw a nearly flat access schedule.

### Naturally supports prodigies

A freshman can draw 0.90 access without implying they must be much better as a senior.

### Keeps POT useful

Existing recruiting, scouting, and talent systems can continue to use potential with fewer downstream changes.

### Reduces age determinism directly

The current problem is that grade bands impose order.

Option B removes the strong grade band while retaining the surrounding system.

---

## 6.6 Risks / costs of Option B

### Potential can retain misleading semantics

If a player has POT 75 but their generated access schedule never exceeds 0.55 during high school, users may interpret the player as a failed development case rather than a player whose theoretical ceiling simply was not relevant to the HS window.

That may be acceptable if POT is understood as upside rather than guaranteed destination.

### Schedule generation must be carefully distributed

If access schedules are too unconstrained, the model can become random-looking.

The distributions should produce recognizable tendencies without reinstating grade lockstep.

### Needs explicit handling of “peak with me”

Because fixed potential survives, the code must not implicitly feel obligated to force players toward it by graduation.

The generated access schedule must be authoritative even when large unused potential remains.

---

# 7. Playing-time odometer design

This mechanic applies to either Option A or Option B.

## 7.1 Principle

Playing contributes to development because competitive participation creates developmental exposure.

The system does not care whether the player wins.

The system cares that the player played.

---

## 7.2 Sources of exposure

### Varsity

Highest ordinary appearance value.

A varsity match means the player competed at the school’s top level.

### JV

Lower appearance value.

JV should be developmentally useful because it prevents buried players from being structurally frozen.

### Sitting

No appearance-based bonus.

The player still receives whatever intrinsic/base development their generated trajectory supplies.

---

## 7.3 Fixed values vs opponent-adjusted values

The preferred philosophy is fixed participation value.

Do **not** use:

- opponent rating;
- match result;
- line result;
- team result;
- game score;
- strength of schedule.

Those would turn development into a performance or opportunity-quality feedback loop.

The odometer should be intentionally simple.

---

## 7.4 Saturation

Appearance value should saturate.

The purpose is to distinguish:

- no season;
- partial season;
- meaningful season;
- full season.

It is not to make the difference between 31 and 34 appearances developmentally enormous.

A capped or diminishing-return function is preferable.

---

# 8. Individual State development allowance

This is separate from the participation odometer.

## 8.1 Why State is different

Individual State is not being treated as a reward for winning.

It is a rare high-level developmental event.

A player advancing through several State rounds experiences unusually concentrated competition at their own flight.

That can justify a small amount of extra growth realization.

---

## 8.2 Mechanic

The State run can modestly raise the player’s normal seasonal realization cap.

It should not directly add OVR.

Example concept:

```text
normal available realized growth = 5
S1 deep-run allowance = +1 additional realizable point
```

If the player has no available latent growth, no additional point appears.

---

## 8.3 Flight weighting

The allowance can decline by flight.

Illustrative hierarchy:

```text
S1 > S2 > S3
D1 > D2 > D3
mixed assigned separately
```

This does not need to be linear.

A State title itself does not need a giant effect.

The mechanism should remain mild.

---

# 9. High school vs college

The same philosophy can govern both levels while allowing different constants.

## High school

The redesign should primarily solve:

- age-lock;
- senior dominance;
- insufficient ladder reorder;
- talented freshmen suppressed by maturity;
- buried players developing identically whether they play or not.

The four-year HS window should contain a wide range of peak timing.

## College

The redesign should primarily solve:

- ordinary players changing too little;
- weak interest-rate calibration;
- insufficient career transformation;
- development being mostly invisible over four seasons.

College players may arrive more developed on average than HS freshmen, but the same career-shape diversity should exist.

A college freshman can be:

- already near peak;
- a major future developer;
- stagnant;
- an early star who plateaus;
- a late senior breakout.

---

# 10. What should not be introduced

This proposal does **not** call for:

- win-based development;
- regression;
- annual random talent rerolls;
- team-quality development bonuses;
- coach decisions determining whether a player has any development path at all;
- mandatory senior-year peaks;
- mandatory realization of full potential;
- development tied to State team qualification;
- arbitrary OVR bonuses for championships.

---

# 11. Era gating and migration

Any implementation must be era-gated.

Existing archived players and seasons should not be silently rewritten.

The current repository already uses `dev_era()`-style gating.

A new development model should therefore apply only to cohorts entering at or after a defined development era.

Expected transition:

```text
Year 1: freshmen only
Year 2: freshmen + sophomores
Year 3: freshmen + sophomores + juniors
Year 4: full HS population
```

College convergence will lag depending on how graduating HS players feed into NCAA generation and persistence.

The existing talent-compression era must be treated separately from the development-model era.

They are independent changes:

- **talent compression** changes how many high-end players are generated;
- **development redesign** changes when and how those players realize ability.

Analysis during the overlap must control for both cohort boundaries.

---

# 12. Measurement plan

The redesign should be evaluated using the baseline script and several new measures.

## 12.1 Ladder reordering

Baseline:

**7.7% of returning teammates swap ladder order.**

The new model should materially increase this.

This is one of the strongest measures of whether development creates different careers rather than parallel growth.

---

## 12.2 No. 1-seat age distribution

Baseline:

- girls seniors: 85.7%
- boys seniors: 81.5%
- freshmen: ~1.5%

The redesign should reduce senior lock-in.

The goal is not equal distribution by grade.

Seniors should still be better on average.

The goal is meaningful overlap.

---

## 12.3 Freshman access overlap

Baseline:

- 1.3% above senior median maturity
- 13.4% above junior median

The redesign should allow more advanced freshmen without reheating the talent generator.

---

## 12.4 Development spread

Continue measuring OVR gain distributions.

The target is not necessarily greater mean growth.

The target is greater heterogeneity:

- more near-zero careers;
- more early jumps;
- more late jumps;
- more meaningful reorder.

---

## 12.5 Playing-time effect

Compare otherwise similar players by accumulated exposure:

- no appearances;
- JV-heavy;
- mixed JV/varsity;
- varsity-heavy.

Expected direction:

```text
sitting < JV < varsity
```

Do not measure development against win percentage.

---

## 12.6 Stagnation rate

Measure the share of players whose current ability changes only minimally over multi-year windows.

This should become a visible population rather than an accidental rarity.

---

## 12.7 Underclass elite population

Continue tracking:

- OVR 50+
- OVR 55+
- OVR 60+
- OVR 65+
- OVR 70+

by grade and gender.

The development redesign must not undo talent compression by creating too many elite underclass players.

It should change **when** rare talent becomes visible, not dramatically increase **how much rare talent exists**.

---

## 12.8 Career peak timing

For Option A, this is explicit.

For Option B, infer the year of maximum current OVR.

Track the share peaking:

- freshman year;
- sophomore year;
- junior year;
- senior year.

Senior should remain common, but no longer nearly universal.

---

# 13. Comparison

| Question | Option A — explicit career trajectory | Option B — randomized access schedule |
|---|---|---|
| Keeps fixed POT architecture | Partially / optional | Yes |
| Directly models “peak with me” | Yes | Indirectly |
| Supports freshman phenoms | Yes | Yes |
| Supports stagnation | Yes | Yes |
| Supports early/late/spike growth | Yes | Yes |
| Breaks grade lockstep | Yes | Yes |
| Easy migration from current code | Less | More |
| Preserves recruiting/scouting POT semantics | Requires decision | Mostly |
| Career archetypes explicit | Yes | Emergent |
| Risk of over-authored trajectories | Higher | Lower |
| Risk of confusing unused POT | Lower if POT redefined | Higher |
| Closest to current HS architecture | No | Yes |
| Closest to baseball access vocabulary | Moderate | High |
| Likely implementation complexity | Higher | Lower |

---

# 14. Option A in one sentence

> Generate the player’s entire relevant competitive career at entry: starting ability, career-window peak, timing, and development shape; playing time determines how much of that generated growth is realized.

---

# 15. Option B in one sentence

> Keep fixed potential, but replace grade-based maturity with a player-specific year-by-year access schedule; playing time determines how fully the player realizes each year’s access opportunity.

---

# 16. Current decision posture

The current preference is **Option B**.

The reasons are:

1. It preserves more of the existing tennis architecture.
2. It directly attacks the measured problem: grade-based access ordering.
3. It preserves POT for recruiting/scouting systems.
4. It can produce ready players, stagnation, early/late bloomers, and spikes without adding a separate career-peak field.
5. It is conceptually close to the original potential/access philosophy.
6. It allows a player to graduate with substantial unused theoretical potential without treating that as an error.
7. It can incorporate JV/varsity exposure naturally as access realization.

Option A should remain documented because it is the cleaner conceptual model if the fixed-POT semantics later become cumbersome.

---

# 17. Likely Option B implementation questions

These are implementation questions to resolve after the design choice, not reasons to reopen the design.

## 17.1 How is the access schedule generated?

The schedule should be highly individualized but not arbitrary.

It needs distributions that create:

- ready;
- steady;
- early;
- late;
- spike;
- stagnant;

without requiring those labels to be stored explicitly.

## 17.2 Must access always rise?

Probably not necessarily by meaningful amounts, but regression is outside the current philosophy.

Flat or nearly flat schedules are sufficient for stagnation.

If strict non-decrease is retained:

```text
0.61 → 0.61 → 0.62 → 0.62
```

already produces stagnation.

## 17.3 How much can one year jump?

This requires calibration against desired roster churn.

A spike must be large enough to reorder ladders.

## 17.4 How does exposure modify access?

Preferred interpretation:

> The generated schedule defines available access; participation determines how close the player gets to that scheduled opportunity.

This is safer than adding uncapped access points for every appearance.

## 17.5 Can exposure pull development forward?

This is potentially useful.

A heavy varsity season could allow a player to realize some access earlier than a comparable player who sits, without changing the eventual four-year access ceiling.

This would make playing materially consequential while preserving generated player identity.

## 17.6 How is JV persisted?

The development engine must use actual archived/known JV participation counts, not infer that a player “must have played” simply because they were below the varsity line.

## 17.7 How should college differ?

College can use the same architecture with:

- higher arrival access on average;
- different access-schedule distributions;
- different exposure values;
- different cap behavior.

The architecture can be shared even if constants differ.

---

# 18. Decision record

## Decision

**Pending. Current preference: Option B.**

## If Option B is selected

Record:

- development-era start year;
- HS schedule-generation distributions;
- NCAA schedule-generation distributions;
- JV exposure value;
- varsity exposure value;
- exposure saturation/cap;
- State individual allowance table;
- whether access may be pulled forward by heavy exposure;
- how POT is described in UI/documentation;
- baseline comparison after first full cohort.

## If Option A is selected later

Do not reconstruct it from chat history. This document is the retained alternative.

The central Option A principle is:

> The relevant peak is explicitly generated for the four-year competitive career, and the engine is not obligated to preserve or model post-graduation upside.

---

# 19. Design principles to preserve in future revisions

1. **Development is player character, not annual reroll noise.**
2. **Winning does not cause development.**
3. **Playing matters.**
4. **JV is developmentally useful.**
5. **Varsity exposure is more valuable than JV exposure.**
6. **Participation value saturates.**
7. **Stagnation is legitimate.**
8. **Freshman excellence is legitimate.**
9. **Senior-year peak is not mandatory.**
10. **Unused theoretical potential at graduation is acceptable.**
11. **Individual State can modestly expand realization capacity, not manufacture ratings.**
12. **Talent compression and development timing are separate systems.**
13. **Archives must remain stable through era gating.**
14. **Measure roster-order churn, not just average OVR gain.**
15. **The game should use interesting talent while the player is actually in the game.**

---

# 20. Summary

The existing tennis development models produce too much age ordering and too little career-shape variation.

High school has enough raw growth, but players rise together. College has the same fixed-ceiling architecture with development rates too weak to produce many meaningful transformations.

Two viable redesigns are preserved here:

### Option A — explicit career trajectory

Generate a competitive-career peak and a full development shape directly.

### Option B — individualized randomized access schedule

Keep fixed potential, but generate a player-specific four-year access path that can be ready, early, steady, late, spiky, or stagnant.

Both models add competitive-exposure realization:

```text
sitting < JV < varsity
```

with no win-based development.

Both allow a modest individual-State cap-break allowance.

The current preference is Option B because it preserves the existing architecture while directly removing the grade-band mechanism that currently locks roster order.

The success criterion is not “players gain more OVR.”

The success criterion is:

> **Players with similar talent should be capable of having materially different high-school and college careers, and actual participation should help determine how much of those careers they realize.**

---

# 21. Measured amendment — what the A/B testing showed

Added after §1-20 were written. Every number here comes from
`scripts/dev_model_access_experiment.py` run over the 2057-2059 research exports:
**the same programs, the same people, the same fixed ceilings and the same grades,
with only the access model swapped.** Nothing else varies, so a metric that moves
is attributable to the access model alone — not to the talent generator, not to
cohort drift, not to roster composition.

`M0` re-implements the shipped `jhsaa._dev_maturity` and reproduces the measured
baseline to within a few tenths (7.3% vs 7.7% swaps, senior No. 1 share 87.4% vs
85.7%). That agreement is what licenses reading the other rows as real
differences rather than harness artefacts.

## 21.1 Option B's mechanism has already shipped

§6.1 describes Option B as "each player receives a hidden, deterministic
year-by-year access schedule at generation." That is precisely what
`jhsaa._dev_maturity` has done since the 2026-08 trajectory pass: an arrival
roll, a finish roll and a curve-shape exponent, rolled once per player off their
own identity and walked per grade. Grade already only selects a point on *that
player's* schedule; it does not set a band.

**So the measured baseline in `docs/REPORT-development-model-baseline.md` — 7.7%
teammate swaps, 1.3% of freshmen above the senior median, 85.7% senior No. 1
share — IS Option B, at its current constants.**

This is good news for cost and risk: B needs no new architecture. But it means
the decision record must specify **which constants move and by how much**, or the
change ships as a no-op. "Adopt Option B" is not an implementable instruction.

## 21.2 One constant carries nearly all the weight: the finish band

`DEV_FINISH` is `(0.76, 0.94)` — narrow — while arrival spans `0.40-0.82`. The
schedules therefore **converge**: almost everyone lands near 0.87 of their
ceiling as a senior. That has a consequence the proposal does not draw out:

> Under a fixed ceiling and a converging access schedule, the senior-year ladder
> is ceiling-ordered — and the ceiling is fixed at generation. **The senior ladder
> is therefore determined at birth**, and every shape in `DEV_SHAPES` only varies
> the route to a predetermined finish.

Widening the finish so schedules stop converging is the single
highest-leverage change available:

| access model | all-pair | near-5 | top-11 | **No. 1 held** | bench→lineup | Fr No.1 | Sr No.1 | mean OVR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **girls** | | | | | | | | |
| M0 shipped | 7.3% | 25.0% | 10.3% | **90.7%** | 35.4% | 1.3% | 87.4% | 35.4 |
| M1 wide finish `.60-.99` | 8.5% | 27.0% | 12.1% | 82.5% | 32.1% | 2.1% | 83.4% | 33.9 |
| M2 wide finish + arrival | 8.9% | 28.6% | 12.5% | 84.8% | 30.0% | 3.8% | 81.1% | 34.5 |
| M3 M2 + peak timing | 10.8% | 30.4% | 12.6% | 82.3% | 31.6% | 3.0% | 78.4% | 35.3 |
| OPT-A (one parameterisation) | 10.9% | 28.5% | 13.8% | 79.7% | 32.5% | 0.8% | 81.2% | 37.7 |
| *CHAOS — upper bound, illegal* | *36.3%* | *47.1%* | *40.6%* | *24.2%* | *41.7%* | *17.2%* | *51.0%* | *32.3* |
| **boys** | | | | | | | | |
| M0 shipped | 7.6% | 27.4% | 11.4% | **85.0%** | 34.3% | 1.8% | 83.0% | 39.0 |
| M1 wide finish | 8.7% | 28.7% | 13.5% | 82.0% | 31.0% | 2.2% | 79.1% | 37.4 |
| M2 wide finish + arrival | 9.1% | 30.1% | 13.5% | 75.1% | 29.6% | 6.9% | 75.4% | 38.1 |
| M3 M2 + peak timing | 11.1% | 31.4% | 13.8% | 80.8% | 30.6% | 3.8% | 69.8% | 38.8 |
| OPT-A (one parameterisation) | 12.2% | 31.4% | 16.0% | 79.5% | 34.4% | 0.7% | 77.0% | 40.7 |
| *CHAOS — upper bound, illegal* | *36.9%* | *47.3%* | *41.7%* | *20.5%* | *41.4%* | *22.6%* | *42.5%* | *35.8* |

**§6.6 lists the consequence of this as a RISK — "POT 75 but access never exceeds
0.55, users may read them as a failed development case". Reclassify it as the
primary mechanism.** §4.6 ("unused theoretical potential at graduation is
acceptable") already licenses it; §6.6 then treats the same fact as a hazard. It
is the feature, and it is where the behaviour change comes from.

Note the cost: widening the finish downward drops mean OVR about a point. The
band's **centre must be raised to compensate** — this is a spread change, not a
level change, and the level must be held.

Framed against §13's comparison table: **widening the finish IS Option A's
decoupling, implemented inside Option B's architecture.** It makes a player's
senior ability depend on something other than their ceiling, which is the one
structural thing A can do that B was assumed not to. That removes most of A's
advantage without adding a career-peak field.

## 21.3 Option B's reach, and the real-world target it has to reach

`CHAOS` in the table above redraws access freely each year. It violates both the
no-reroll rule (§4.5) and monotonicity (§17.2), so it is not a candidate — it
exists only to bound what **any** fixed-ceiling access model can do:

* best legal Option B calibration: ~9% all-pair swaps, ~75-85% No. 1 retention,
  **75-81% senior No. 1 share, 4-7% freshman**
* unconstrained bound: 36% swaps, 20-24% retention, 51%/42.5% senior share

An earlier draft of this section left "what should the senior share be?" as an
open owner question. It is not open — it is measurable, and §21.3a answers it.

## 21.3a MEASURED TARGETS — six seasons of real OSAA results

Source: `quarterback/or-tennis-data`, 2021-2026, ~295k varsity regular-season
appearances over 11,135 players. Reproduce with
`scripts/oregon_lineup_shape.py <clone>`. The script computes both metrics the
same way `dev_model_access_experiment.py` computes them for the sim, so the two
sides are directly comparable.

‼️ **The data has no grade field, and the one that looks like it is not one.**
`grade` is current status (99% read "Graduated") and `graduatedDate` is largely a
bulk data-entry stamp — deriving grade from it puts 30.8% of appearances outside
grades 9-12. Grade is inferred from each player's appearance span instead, which
has no unbiased single form, so the script brackets it. Read the EXACT pass
(players with a full four-season career, where both bracketing assumptions agree
and nothing is inferred) as the target:

**Share of No. 1 singles, by grade**

| | 9 | 10 | 11 | 12 |
|---|---:|---:|---:|---:|
| **Oregon boys** (exact cohort) | 5.3% | **19.7%** | 32.3% | **42.7%** |
| **Oregon girls** (exact cohort) | 6.3% | **27.0%** | 30.1% | **36.6%** |
| Oregon, upper bound on seniors | 1.6-2.5% | 10-13% | 27.8% | 56.8-60.5% |
| **sim, 2059 boys** | 1.7% | **4.6%** | 12.2% | **81.5%** |
| **sim, 2059 girls** | 1.5% | **3.3%** | 9.4% | **85.7%** |

**Share of every varsity line, by grade**

| | 9 | 10 | 11 | 12 |
|---|---:|---:|---:|---:|
| Oregon boys (exact cohort) | 15.8% | 24.8% | 29.1% | 30.3% |
| Oregon girls (exact cohort) | 15.3% | 26.8% | 29.0% | 28.9% |

**Ladder churn** — this measure needs no grade at all, so none of the inference
caveats touch it. A school-season's No. 1 is the player with the most No. 1
singles appearances; retention asks how often that player, when back on the
roster the next season, is still No. 1:

| | boys | girls |
|---|---:|---:|
| **Oregon: a returning No. 1 keeps the seat** | **63.6%** (n=294) | **63.4%** (n=328) |
| sim (shipped model) | 85.0% | 90.7% |
| best Option B calibration tested | 75.1% | 84.8% |
| Oregon: No. 1s who were on last year's roster | 81.4% | 83.9% |

### What this changes

1. **The target is ~63% No. 1 retention.** More than a third of returning No. 1s
   get passed in real life. The sim passes 10-15%. Every Option B calibration
   tested lands 75-85%, so **B alone does not reach the target** — it closes
   roughly half the gap on the boys' side and less on the girls'.
2. **The biggest miss is SOPHOMORES, not freshmen.** Real sophomores hold 20-27%
   of No. 1 singles; the sim gives them 3-5%. That is a 5-8x gap, against
   freshmen's 3-4x. The redesign has been framed around freshman suppression;
   the data says the second year is where the model is most wrong. A calibration
   that opens up freshmen without opening up sophomores will miss the target
   while appearing to succeed.
3. **The real lineup is nearly flat by grade** — 15/25/29/30 across four grades,
   against the sim's 32%/49%/66%/81% participation rates. Real varsity tennis is
   not a seniority queue.
4. **Seniors are still the largest single block** (37-43% of No. 1s, and the
   upper bound says no more than ~60%). The goal is not parity — it is that
   seniority stops being near-deterministic.

## 21.4 §12.1's headline success metric is malformed

The all-pair teammate swap rate is dominated by pairs 15+ OVR apart who will
never cross, so it largely measures roster size. Under the **shipped** model,
pairs that could actually cross already reorder at a healthy rate:

| metric | girls | boys |
|---|---:|---:|
| all-pair swaps (the §12.1 metric) | 7.3% | 7.6% |
| swaps among pairs within 5 OVR | **25.0%** | **27.4%** |
| swaps among top-11 pairs | 10.3% | 11.4% |
| **returning No. 1s who keep the seat** | **90.7%** | **85.0%** |

**Replace §12.1's 7.7% target with No. 1 retention**, which now has a real-world
number to hit (63%) rather than a direction to move in. Keep near-pair and
top-11 swaps beside it as diagnostics.

## 21.5 The playing-time odometer — an earlier draft got this wrong

A previous version of this section argued that the odometer is positive feedback
on ladder position and proposed a guardrail that the bench-to-lineup promotion
rate must not fall. **Both the argument and the test behind it were wrong, and
the owner corrected them (2026-08).**

The test modelled exposure as a single binary — top 11 = varsity, everyone else
one undifferentiated "JV" bucket — which is not the proposed mechanic. What the
design actually says:

* **The JV ladder is itself a ladder.** Kids play each other all season for
  position at every level. A JV player near the varsity line who takes some
  varsity matches is ahead of a kid who spent the whole year at JV, and that
  difference is real and earned.
* **Split time is its own state**, not a rounding error between two buckets. The
  exposure model needs at least: varsity regular / split / JV regular / did not
  play — with the ordering inside the JV group meaning something.
* **Promotion is not supposed to be guaranteed or pinned to a rate.** Owner:
  "there are no guarantees that because you played a lot 9th grade year that
  you'll play 10th and 11th or 12th. I've had to bump many seniors out of the
  lineup when the team gets better and we get 9th graders who surpass them."
  Churn is inevitable and a bench-to-lineup rate is an outcome of what makes
  sense for the team, not a quantity to hold fixed.

So the guardrail is withdrawn. The odometer's correct check is §21.3a's
retention target: exposure must not push No. 1 retention back **up** toward the
shipped 85-90%. That is the failure mode worth watching, and it is measured
against real data rather than against a made-up floor.

The odometer test in `scripts/dev_model_access_experiment.py` is retained but is
**explicitly a two-bucket strawman** and its numbers should not be read as an
evaluation of the proposed mechanic. A graded exposure model is still to be
built and measured.

## 21.6 Roster persistence is NOT a blocker

An earlier draft of this section argued that because `jhsaa.build_roster`
regenerates players from `(school, gender, entry year, seat)`, a playing-time
term would break generation purity and change the function's cost class.

**The owner has settled this (2026-08): the save is 30 years deep, the archive
works, and reading a prior season's participation is not a problem.** The
concern is withdrawn as a design blocker.

Two implementation notes survive, as ordinary care rather than as objections:

* resolve the exposure record **once per roster build** and thread it down,
  never once per seat — the `AAR-jhsaa-playup-fingerprint-query-storm` rule
  applies here as it does to every other per-school lookup;
* the exposure count must filter on `level`, since JV and varsity share
  `world_jhsaa_dual` (`AAR-jv-duals-leaked-into-the-research-export`).

## 21.7 Amended recommendation

Option B, with these changes to §16-§18:

1. **The primary mechanism is the non-converging finish band**, not "individual
   access schedules" (which already exist). Widen `DEV_FINISH` toward `.60-.99`
   and raise its centre to hold the association's level. §6.6's unused-potential
   "risk" is the intended behaviour — the owner has confirmed this is exactly
   the baseball model's design and exactly what is wanted.
2. **§12.1's success metric becomes No. 1 retention, targeting ~63%** (§21.3a),
   with near-pair and top-11 swaps as diagnostics.
3. **Sophomores are the primary target population**, not freshmen (§21.3a).
4. **Option B alone will not reach 63% retention.** It reaches 75-85%. Either
   accept that as a first step and re-measure, or take Option A's start/peak
   decoupling for the rest of the distance. This is now a real decision with a
   real number behind it rather than a preference.
5. **The exposure model needs a graded ladder** — varsity / split / JV / none,
   with ordering inside JV — and the two-bucket test in the experiment script
   does not evaluate it.

---

# 22. Option C — starting ability / career peak / yearly capacity / exposure

**Owner direction, 2026-08. This supersedes §16's Option B preference and §5's
Option A. Options A and B stay above as the retained record of what was
considered.**

## 22.1 The model

Four parts, each drawn once at generation:

```
PLAYER
├── STARTING ABILITY        where they are on day one
├── CAREER PEAK             the best they could be during THIS career window
├── YEARLY CAPACITY  Y1..Y4 how much improvement they can realise each year
└── EXPOSURE                what they actually played, scaling realisation
                              ↓
                    realised gain = capacity × exposure
                              ↓
                        clamped at career peak
```

The break from every earlier model is that **starting ability and career peak
are drawn separately.** They correlate; neither is derived from the other. So
the model stops assuming a freshman is unfinished *because* they are a freshman:

```
61 / 63    already a finished player
51 / 70    elite upside
38 / 64    a project
44 / 47    basically done at fourteen
31 / 55    ordinary, with room
```

Career peak is **not a debt the engine owes the player by senior year.** A
34/67 player whose capacities come up mediocre finishes 34 → 37 → 43 → 49 and
simply never becomes what they might have been. No regression is needed for
that; it is just unrealised capacity.

**There is no privileged senior development year.** The largest growth year may
fall in any grade. Career shapes — ready, early, steady, late, spike, stagnant —
are emergent from the capacity draws and are never labelled or stored.

## 22.2 Exposure is a cumulative odometer, not a category

Do not classify a player once as "JV" or "varsity". Accumulate appearance value
across the season (a varsity appearance worth more than a JV one), then convert
the total into a realisation factor. Split-time players land between the two
without needing a category of their own, and the JV ladder matters because a JV
No. 1 who plays every dual banks more than a JV player who barely appears.

Illustrative factors: did not play 0.55 · limited JV 0.70 · full JV 0.80 ·
split 0.90 · full varsity 1.00. Multiplying the player's **own** capacity means
exposure never homogenises anyone: a stagnant player with +1 capacity gets about
+1 whatever they play, while an explosive sophomore with +12 gets ~12 on varsity,
~10 on JV and ~6-7 sitting. Adolescence happens either way, which is why the
floor is 0.55 rather than zero.

## 22.3 What this replaces

Remove, as different spellings of "older player = more access":

* grade maturity bands (`_MATURITY`, `_dev_maturity`'s grade walk)
* `DEV_MIN_RISE`, `DEV_MIN_STEP`, `DEV_FINISH`
* the interest-rate gap-closing model (`GROWTH_K`, `TIERS`, `tier_mult`)

## 22.4 One engine, two sets of constants

High school and college stop being philosophically different systems. Same four
parts; college simply draws starting ability closer to career peak on average
(HS ~40-95% of peak, college ~65-90%). College still produces finished freshman
stars, stagnant players, sophomore jumps and senior breakouts.

## 22.5 Individual State overflow

Retained from §8. A deep individual-State run raises that season's realisation
cap slightly above the generated capacity — `+7` capacity, `+1.5` allowance,
`+8.5` maximum — and only if there is room below career peak. It cannot
manufacture ability, and it is weighted by flight (S1 > S2 > S3, D1 > D2 > D3).

## 22.6 Calibration evidence

Measured over the real 2059 rosters, projecting every freshman's full four-year
career (`scripts/dev_model_access_experiment.py` was extended for this; the
figures below are from the same harness and the same real ceilings).

‼️ **A clamping artefact to avoid.** A first parameterisation drew starting
ability as a blend of a peak-anchored term and an independent population draw,
then clamped it at peak. For low-peak players the independent draw routinely
exceeded peak, so the clamp set start = peak and manufactured a **26% "ready"
share and 53% of players with no real growth year** — an artefact of the clamp,
not a design choice. Draw the start FRACTION grade-free and multiply
(`start = peak × frac`) instead; nothing is ever clamped at generation.

Three parameterisations, against the §6 spec's own growth-year targets:

| config | 9→10 | 10→11 | 11→12 | none | ready | stagnant | one big leap | mean ability 9/10/11/12 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **owner spec §6 target** | **30%** | **27%** | **28%** | **15%** | | | | |
| V1 peak ×.85-1.10, start .40-.95 | 31% | 24% | 17% | 28% | 9% | 3% | 41% | girls 31.5/35.4/38.7/41.2 |
| V2 peak ×.90-1.15, start .35-.92 | 38% | 29% | 19% | 14% | 3% | 2% | 56% | girls 31.1/36.1/40.2/43.2 |
| V3 peak ×.95-1.20, start .32-.90 | 44% | 32% | 20% | 4% | 0% | 0% | 63% | girls 31.4/37.6/42.6/46.2 |

(boys land within a point or two of the same shape; today's actual means are
girls 28.7/33.5/37.4/45.9, boys 31.2/36.7/41.6/49.2)

**V1 is the closest starting point** — 31/24/17 against the 30/27/28 target,
with a 9% ready share and 3% stagnant.

### ‼️ 22.6a THE SPEC'S OWN GROWTH-YEAR TARGET WAS WRONG (owner rule, 2026-08)

§6's illustrative split (30% / 27% / **28%** / 15%) treats the senior year as
carrying roughly the same share of breakouts as the two before it. **It does
not.** Owner: *"breakouts are usually sophomore and junior breakouts, senior
year tends to be incremental not a massive leap, so the leaps happen before
then."*

So V1's 17% senior share is **not** the model under-weighting the senior year —
it is the model getting the shape right, and an earlier draft of this section
wrongly filed it as a defect needing a fix. **Do not widen the start-to-peak gap
or drift capacity upward with grade to "correct" it.** Both were proposed here
and both are withdrawn.

The corrected target, stated as magnitude rather than only as which year is
biggest:

> **Leaps happen in years 1 and 2. Year 3 is incremental — real, visible, but
> small. No player should be waiting on a senior-year jump.**

Measured per-year gain under V1 (girls; boys within 0.2 of every figure):

| transition | mean | p50 | p90 | biggest-year share | players leaping +8 or more |
|---|---:|---:|---:|---:|---:|
| 9 → 10 | 3.9 | 2.4 | 10.8 | 31% | 19% |
| 10 → 11 | 3.3 | 2.0 | 10.0 | 24% | 16% |
| 11 → 12 | **2.5** | **1.2** | 8.5 | 17% | 11% |

That is the intended profile: the senior year's median gain is about +1, half
the sophomore year's, while its p90 stays high enough that a late bloomer
remains possible without being the norm.

**The front-loading is emergent, not authored.** Capacity is drawn independently
per year with the same probability of a big year in all four; the taper falls
out of the clamp, because by year 3 most players have already closed their
start-to-peak gap and a late big draw has nowhere to land. Nothing in the model
says "seniors grow less" — which is exactly the property wanted, since the ramp
is not being re-introduced in the other direction either.

If the taper should be sharper, an explicitly front-weighted big-year
probability (V4: .34 / .34 / .26 / .12) moves the senior share 17% → 13% and its
median gain 1.2 → 1.0. That is a knob if wanted, not a requirement — V1 already
produces the described shape on its own.

### Still open

**This is a LEVEL change as well as a shape change.** V1 lifts freshmen ~3
points and drops seniors ~5 (girls 31.5/35.4/38.7/41.2 against today's
28.7/33.5/37.4/45.9). The flattening is the intent, but the association's
overall standard moves with it, and the peak multiplier is the knob that sets
where it lands. Choose the senior-year level deliberately rather than accepting
whatever the peak band produces.

Stagnation is real but rare at these settings (2-3%). If stagnant careers should
be a visible population rather than a curiosity, lower the big-year probability
or widen the small-capacity band; the shape census in the harness measures it
directly.

## 22.7 What is NOT a target

Ladder churn and No. 1 retention (§21.3a, §21.4) are **not** optimisation
targets for this model (owner, 2026-08). Roster order is handled dynamically
elsewhere — the ladder re-forms through the season, and the transfer model adds
its own mobility. Players surpassing players above them already happens today;
it is simply "more predictive and less common" than it should be, and this
model's job is to make it less predictive by giving two similar players
genuinely different capacity draws. The Oregon figures stay in §21.3a as
context for how flat a real lineup is, not as a metric to tune against.

---

# 23. Career peak is a soft target, not a wall (owner rule, 2026-08)

Owner: *"letting it roll OVER 100% … I'm not concerned about what happens to
these people after high school … every level we're simming, high school or
college, is the highest level to me, so worry less about gate capping."*

Right in principle: nothing should be held back at one level to reserve headroom
for a level the owner does not care about. But **"cap" means three different
things here and only one of them should be removed.**

## 23.1 The three caps

| # | cap | what it does | verdict |
|---|---|---|---|
| 1 | **the career-peak clamp** (§22) | stops a player exceeding their own generated peak | **soften, do not remove** — see §23.2 |
| 2 | **talent compression** (`development.compress_talent`, `TALENT_CAP` 66.5 boys / 58.7 girls) | squashes generated CEILINGS above a knee | **this is the one the rule is really about** — §23.3 |
| 3 | **the 20-80 scale** (`GRADE_MAX`, `clamp_grade`, `overall_to_str`) | the grade scale itself | a technical wall, not a design choice — §23.4 |

## 23.2 ‼️ REMOVING THE PEAK CLAMP DESTROYS THE SENIOR TAPER

This is the important finding, and it is a direct collision with §22.6a.

The sophomore/junior-leaps-then-incremental-senior profile that §22.6a
establishes as correct **is produced by the clamp.** Capacity is drawn
identically in all four years; late years grow less only because most players
have already reached their peak and a big late draw has nowhere to land. Remove
the clamp and there is nothing left making a senior year different from a
freshman year.

Measured over the real 2059 freshmen, sweeping how much of a gain still lands
once a player is past peak (0.00 = today's hard clamp, 1.00 = no cap at all):

| overflow | 9→10 | 10→11 | 11→12 | **Y3 ÷ Y1** | players finishing over peak | Sr mean | Sr p99 | Sr max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **0.00** (clamp) | 3.9 | 3.3 | 2.5 | **0.62** | 0% | 41.2 | 62 | 81 |
| **0.15** | 4.0 | 3.5 | 2.8 | **0.69** | 34% | 41.8 | 63 | 83 |
| **0.30** | 4.1 | 3.7 | 3.1 | **0.75** | 39% | 42.4 | 65 | 84 |
| 0.50 | 4.2 | 4.0 | 3.5 | 0.82 | 41% | 43.1 | 68 | 85 |
| **1.00** (no cap) | 4.5 | 4.6 | **4.5** | **1.00** | 43% | 45.1 | 76 | 94 |

(girls; boys within 0.2 on every gain column and 0.01-0.07 on the ratio)

At full overflow the senior year gains **exactly as much as the freshman year** —
the seniority-leap pattern §22.6a rules out, reintroduced by the back door.

**Recommendation: overflow 0.15-0.30.** A third of players finish above their
career peak — so peak reads as a projection rather than a wall, which is what
the rule asks for — while the taper survives at 0.69-0.75. Only the players with
genuine late capacity punch through, which is the right population to let
through.

## 23.3 The cap the rule is actually about

If the intent is "a high-school player should be as good as high-school tennis
needs, not held down because a college sim exists", the lever is **talent
compression**, not the peak clamp. `compress_talent` squashes generated ceilings
above a per-gender knee toward `TALENT_CAP` (66.5 boys / 58.7 girls) with a
1-in-500 elite exemption; `trim_prospect_ceiling` enforces it after generation.

‼️ **It was added for a real reason** (`docs/AAR-talent-compression.md`, owner
rule 2026-08): at ~850 JHSAA programs plus a 2,500/gender national pool, the
same distributions produced five times the lottery tickets and the tail piled
onto the 80 clamp — *"players maxing out my college scales, which was never
supposed to happen."* Relaxing it means accepting that graduates arrive in the
college sim above the scale it was tuned for, or rescaling on the hand-off.
That is a legitimate choice under this rule, but it is a **different decision
from §23.2** and should be made deliberately rather than as a side effect.

## 23.4 The 20-80 scale is a hard wall regardless

`clamp_grade` bounds attributes at `GRADE_MAX` (80), `GRADE_CEIL` reaches 90 for
pros only, and `overall_to_str` maps 20-80 onto the STR band 31-57. At full
overflow the sweep above produces a top senior of **94 (girls) / 98 (boys)** —
outside the scale entirely, where it would be silently clipped and where STR
stops meaning anything. Any uncapping past this point is a code change across
display, STR and the engine's grade normalisation, not a constant.

Note that even the hard-clamp row already tops out at 81 for girls, so this
boundary is live today.

## 23.5 Level, and the knob that should set it

Overflow also raises the association's level: senior mean 41.2 → 45.1 (girls) at
full overflow, which lands close to today's 45.9. That makes overflow look like
a fix for the level drop flagged in §22.6 — **it is the wrong knob for it.** The
peak multiplier sets the level without touching the taper; overflow sets the
level by flattening the taper. Use the multiplier for level and overflow for
whether peak is a wall.

---

# 24. Free the high-school scale; translate at graduation (owner rule, 2026-08)

Owner: the Jefferson rating scale was doing two jobs — representing how good
someone is *within high-school tennis*, and guaranteeing that graduates fit onto
the college scale. Those are separated. **JHSAA becomes internally unconstrained;
a translation layer converts players only when they enter the college pool.**

```
JHSAA PLAYER  current HS ability · development · achieved HS level
     ↓ graduation
TALENT TRANSLATION   percentile-primary, non-linear, + a small absolute term
     ↓
COLLEGE PROSPECT  college-scale current · college-scale potential
```

Consequences, all intended: `compress_talent` and `trim_prospect_ceiling` stop
applying to JHSAA generation; the career peak becomes a projection a player may
exceed (§23); a Jefferson player may legitimately be an 84 or a 96, and that
number means something only inside the JHSAA. `hs_exit_ovr`, `hs_percentile` and
`college_entry_ovr` are all carried, so the player stays a 96-rated Jefferson
monster historically while college receives a properly scaled 61.

**College potential is generated fresh at import, not translated from HS peak.**
Dominating high school and being nearly finished is a legitimate outcome; so is
leaving slightly worse with far more college growth. HS potential governs
nothing about college potential.

## 24.1 ‼️ The scale headroom already exists — correcting §23.4

§23.4 said uncapping past 80 is "a code change across display, STR and the
engine's grade normalisation". **That was wrong**, and the code is already most
of the way to this design:

* `player_attributes.GRADE_CEIL` is **100**, not 80. `GRADE_MAX` (80) is only the
  NORMALISATION REFERENCE.
* `grade_to_unit` has **no upper clamp** by deliberate design: grade 80 → 1.0 and
  anything above normalises above 1.0.
* The pro tier already generates into the 80-100 headroom and reads above 80 on
  court, because the engine clamps the resulting PROBABILITY, not the input.

So a 96-rated high schooler needs no new plumbing; the path the pros use already
exists. Two real limits remain:

1. **100 is a hard clamp.** `clamp_grade` bounds at `GRADE_CEIL`, so the "103
   generational player" would silently clip. Either keep the HS scale under 100
   or raise `GRADE_CEIL` deliberately.
2. **`overall_to_str` is linear and unclamped** (20-80 → STR 31-57), so a 96
   displays as STR ~64, above the band STR was defined for. Fine if JHSAA never
   shows STR; a decision if it does.

## 24.2 ‼️ THE REAL COUPLING IS THE MATCH ENGINE, NOT THE DISPLAY

`engine.fast` plays on a HINGED gap (`effective_gap`): the real gap below a knee,
accelerated `gap_accel`× beyond it. The gap is a difference of unit-normalised
drivers — i.e. **grade difference ÷ 60** — so it is denominated in the same
20-80 reference the HS scale is about to stop respecting. The high-school
profile's knee is **0.02** with accel **1.8** (against the college calibration's
0.06), so HS matches accelerate very early and very hard.

Widen the ability distribution and every gap grows in unit terms, pushing more
matches past that knee. The 2027-08 upset recalibration
(`docs/AAR-jhsaa-upset-variance-recalibration.md`) was tuned against the
COMPRESSED distribution.

This is measurable today, because the export contains both regimes either side
of the `talent_era` boundary at entry 2057. Comparing **ceilings**, which are
fixed at generation and so carry no grade confound (an earlier pass compared
current ability and was dominated by the fact that uncompressed cohorts are
mostly seniors — a real trap in this dataset):

| | mean | sd | p90 | p99 |
|---|---:|---:|---:|---:|
| girls uncompressed (entry ≤2056) | 53.0 | **15.88** | **75** | 78 |
| girls compressed (entry ≥2057) | 47.8 | **10.95** | **57** | 58 |
| boys uncompressed | 56.9 | 16.06 | 77 | 78 |
| boys compressed | 52.9 | 12.93 | 65 | 66 |

And what that does to the matchups that matter most — best player of one program
against best player of another, in engine unit terms:

| | median gap | **p90 gap** | **share inside the HS knee (0.02)** |
|---|---:|---:|---:|
| girls uncompressed | 0.033 | **0.183** | **39.7%** |
| girls compressed | 0.017 | **0.033** | **87.0%** |
| boys uncompressed | 0.017 | 0.133 | 63.5% |
| boys compressed | 0.017 | 0.033 | 88.4% |

**Uncompressing multiplies the p90 best-vs-best gap by about 5.5× (girls) and
4× (boys), and drops the share of marquee matchups that keep their volatility
from 87% to 40%.** State finals and No. 1 singles — the matches most worth
watching — get markedly more lopsided. Nothing errors; the scoreboard just
stops producing close matches at the top.

### The fix is small, and it belongs in the same change

`gap_knee` is a quantity in unit terms pinned to a 20-80 reference. If the HS
scale is freed, **the HS profile's knee (and possibly its accel) must be
rescaled with it**, or the upset calibration silently changes as a side effect of
a talent-generation decision. Freeing the scale and re-tuning the hinge are one
change, not two, and `scripts/jhsaa_upset_calibration.py` already exists to
verify it.

The same reasoning applies to anything else denominated against the 20-80
reference and tuned on the compressed distribution: `jhsaa.REST_GAP` (10 OVR),
`jhsaa.LADDER_SWING` (±7 OVR), `jhsaa.PAIR_SUM_TOL`, and the
`development.FOG_*` bands. Grep for OVR-denominated constants before shipping.

## 24.3 The translator

Percentile-primary is right, and for the reason given: it survives future changes
to Jefferson talent generation. If the best player in a generation is later an 87
instead of a 103, "top 0.2% of graduating Jefferson players" still means the same
thing and college needs no redesign. A small absolute-quality term on top lets a
genuinely great graduating class send stronger players without letting JHSAA
rating inflation reach the college scale.

Three implementation requirements:

1. **‼️ THE TRANSLATION MUST BE ARCHIVED, NOT RECOMPUTED.** A percentile is a
   function of the whole graduating population, so re-deriving it later would
   only match by chance — the same rule that makes `jhsaa` archive its TOSS
   index per school per season rather than recomputing it, for the same reason.
   Store `hs_exit_ovr`, `hs_percentile` and `college_entry_ovr` on the prospect
   at graduation and read them back forever.
2. **Version the mapping.** Once translated players are in college rosters, a
   changed curve must not retroactively re-rate them. Stamp the translator
   version alongside the stored values; this is the `dev_era()` idiom again.
3. **Define the reference population explicitly** — graduating JHSAA seniors of
   that gender and year, and state whether JV-only players are in it. A thin or
   unusual class needs a stated fallback rather than a percentile over forty
   people.

## 24.4 What the HS model reduces to

```
starting ability
+ randomised yearly development capacity
× competitive exposure
= changing HS ability
```

No universal maturity access. No requirement to approach potential. No hard
career-peak clamp. No college-driven talent compression. No 80-point ceiling
imposed because STR expects one. Graduation performs the normalisation.

---

# 25. The JHSAA matchup curve — seven-point competitive bands (owner spec, 2026-08)

Owner spec. OVR differences are read as five competitive bands; volatility is
preserved inside the peer band and favourite strength rises progressively across
each band above it.

| band | OVR gap | favourite should win |
|---|---|---|
| peers | 0-6 | ~50-62% |
| modest advantage | 7-14 | ~62-75% |
| clear advantage | 15-21 | ~75-87% |
| strong mismatch | 22-28 | ~87-95% |
| major mismatch | 29+ | ~95%+ |

## 25.1 ‼️ THE HINGE WAS NEVER THE PROBLEM — `skill_slope` WAS

§24.2 recommended rescaling `gap_knee`. **That was the wrong diagnosis**, and
measuring the actual match outcomes rather than the gap arithmetic shows why.

Favourite win rate under the shipped HS profile, base 45 OVR, real engine, real
`jhsaa.MATCH_FORMAT`:

| OVR gap | shipped (slope 6.0, knee 0.02) | slope 6.0 with the hinge REMOVED |
|---:|---:|---:|
| 3 | **94.7%** | **92.9%** |
| 6 | **100.0%** | **92.9%** |
| 10 | 100.0% | 99.3% |

A three-point gap is already a 95% favourite, and removing the hinge entirely
barely moves it. The gap is a per-*game* hold edge compounded over ~20 games and
two or three sets, so `skill_slope` 6.0 saturates the match long before any knee
matters. **The requested peer band is unreachable by touching the hinge; the
whole curve has to come down.**

## 25.2 The calibration

Two changes, both in `engine.fast.HS_PROFILE`:

1. **`skill_slope` 6.0 → 0.9**, **`tb_slope` 4.5 → 0.68** (same ratio).
2. **Replace the single `gap_knee`/`gap_accel` hinge with a banded piecewise map**
   on `|gap|`, continuous, with band edges at **6 / 14 / 21 / 28 OVR** (÷60 in
   engine units) and per-band slopes **1.0 / 1.0 / 1.5 / 2.2 / 3.0**. The peer
   band is identity, so volatility inside it is preserved exactly.

`gap_knee` and `gap_accel` become unused under the HS profile; the college
calibration keeps its own hinge untouched.

Measured (n=2000 per point):

| OVR gap | band | target | **calibrated** |
|---:|---|---|---:|
| 0 | peer | 50% | **50.1%** |
| 3 | peer | | 55.2% |
| 6 | peer | ~62% | **60.5%** |
| 10 | modest | | 66.9% |
| 14 | modest | ~75% | **73.2%** |
| 18 | clear | | 80.7% |
| 21 | clear | ~87% | **85.5%** |
| 25 | strong | | 92.0% |
| 28 | strong | ~95% | **95.2%** |
| 34 | major | | 99.1% |
| 40 | major | ~95%+ | 99.9% |

Every band lands within about 1.5 points of its target, and the progression is
monotonic across all five.

Two alternatives were fitted and are slightly hotter through the middle
(1.0/1.1/1.7/2.6/3.6 and 1.0/1.2/1.9/3.0/4.4); if the upper bands should bite
harder, those are the next steps up. `scripts/dev_model_access_experiment.py`'s
sibling harness in the scratchpad fitted these; fold it into
`scripts/jhsaa_upset_calibration.py` when implementing.

## 25.3 Recorded consequence: the scoreline profile

`engine.fast.HS_PROFILE`'s comment and `docs/AAR-jhsaa-scoreline-realism.md`
record that its dials were fitted to real Oregon SET-SCORE distributions (6-0 the
most common set at 26.4%, 7-6 at 3.9%, 13.8% three-setters). Flattening the curve
changes that distribution: at a 6-OVR gap, 6-0 sets fall from 27.6% to ~2%, 7-6
rises from 0.6% to ~12%, and three-setters go from 0.9% to ~50%.

**The owner has ruled that this is not a constraint (2026-08): the band spec is
what is wanted.** Recorded here so a future reader does not treat the divergence
from that AAR as a regression — it is a superseding decision, and the scoreline
benchmark's targets should be restated or retired rather than defended.

Note the two are not necessarily in permanent conflict. The steep curve produced
blowout-shaped scorelines because, on the COMPRESSED talent distribution, real
matched-line gaps are small (median 3.5 OVR). Once §24 frees the HS scale and
gaps widen, a flat curve over wider gaps may reproduce a blowout-shaped
distribution on its own. **Re-run `scripts/jhsaa_scoreline_benchmark.py` after
the scale change, not before** — measuring it on today's compressed distribution
answers a question that will no longer apply.

## 25.4 Sequencing

§24 (free the scale) and §25 (rebband the curve) are **one change**. The bands
are denominated in OVR points, so what they mean depends on the talent
distribution they run over: on today's compressed distribution the median
matched-line gap is 3.5 OVR, so the 0-6 peer band swallows more than half of all
matched lines and shipping §25 alone would reintroduce exactly the upset volume
the 2026-08 profile was written to remove. On a freed scale the peer band is
genuinely narrow. Ship together, then measure.
