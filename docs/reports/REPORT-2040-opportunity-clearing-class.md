# REPORT: 2040 Opportunity Clearing Transfer Class

**Run date basis:** 2039 JHSAA season exports (boys and girls)
**Effective:** 2040 season
**Market:** Opportunity clearing (one of four; see `BRIEF-jhsaa-opportunity-clearing-market.md`)
**Volume:** 10,731 placements — 5,129 boys, 5,602 girls
**Artifacts:** `clearing_2040_boys.csv`, `clearing_2040_girls.csv`, `clearing.py`

---

## 1. What this class was for

This is the low-end market only. It handles bad, marginal, lower-middle and
buried players whose problem is a lack of useful playing opportunity. It is
deliberately separate from blocked talent, reserve-cohort mobility, and the
top-end portal, which were run (or will be run) as different jobs.

It is also the first run built on the **sequential clearing** design rather
than the 2039 approach. The 2039 wave thickened 1A–3A effectively but let too
much talent skip the middle: **54% of its moves went five or more classes
down.** This class was built specifically to stop that.

---

## 2. The competitive ladder used

The nine classifications are not nine equal competitive steps. The market ran
on seven levels:

```
L1  9A / 8A      (lateral with each other)
L2  7A / 6A      (lateral with each other)
L3  5A
L4  4A
L5  3A
L6  2A
L7  1A           (terminal market)
```

An 8A destination is not a demotion for a 9A player. The first real step down
from the 7A/6A band is 5A.

---

## 3. Eligibility

Eligibility is **relative to the source competitive level**, not an absolute
OVR or POT cutoff. A player is in the pool if, on their program's returning
ladder (seniors removed):

- they project outside the varsity playing group (rank 12 or worse), **or**
- they sit 9th or worse *and* played 4 or fewer varsity matches in 2039.

The second clause is what JV made possible. Before JV, "buried" was inferred
from ladder position. Now a No. 15 with a full JV season is distinguishable
from a No. 15 who barely played, and varsity participation can be used
directly.

**Pool size:** 5,157 boys, 5,604 girls (10,761), before second-order
displacement added a few hundred more.

**Pool character:**

| | Boys | Girls |
|---|---|---|
| Median OVR | 28 | 25 |
| Zero varsity matches in 2039 | 929 (18%) | 945 (17%) |

Explicitly **excluded** from this market: genuinely strong blocked talent,
elite JV players who would be major varsity players elsewhere, established
varsity players making competitive moves, family-driven transfers, and
reserve-cohort players.

---

## 4. The algorithm

```
for level in [ [9A,8A], [7A,6A], [5A], [4A], [3A], [2A], [1A] ]:
    pool = carry + players native to this level
    match on exact class, then laterally inside the level
    apply placements
    recalculate every affected ladder
    incumbents pushed out of varsity re-enter as candidates at their own level
    repeat until stable (max 4 rounds)
    carry = unresolved
place all remaining at 1A
```

### Destination scoring

Higher is better; `None` disqualifies:

| Factor | Weight |
|---|---|
| Projected seat at destination | `(11 − seat) × 3` |
| Exact same classification | +25 |
| Lateral inside the level | +12 |
| Improvement over destination's No. 11 | `(ovr − their #11) × 1.5` |
| Destination short of a full varsity group | +20 |
| Destination roster under 16 | +10 |
| Destination already carrying low-end depth | `−1.2` per sub-varsity player at 30+ OVR |
| Arrivals already assigned to that destination | `−6` each |

The last two implement the brief's rule that a program already carrying
enormous low-end depth is a *lower* priority destination, not a higher one.
That inverts the "most open slots wins" heuristic used in earlier waves.

### Seat thresholds by grade

- **Rising seniors:** must land inside the varsity 11.
- **Sophomores and juniors:** may land as far as seat 14 — varsity fringe or
  upper JV with a materially shorter path. JV makes that an acceptable outcome.

This split was the single most important tuning decision. The first run applied
the top-11 requirement to everyone, which starved the lateral market and pushed
3,901 boys downward. Relaxing it for underclassmen cut downward movement by
59% in one change.

### Senior guarantee and repair

The brief requires a senior's varsity place to be checked against the **final**
roster, not at assignment. The first run broke **622 boys and 568 girls**
senior guarantees, because later arrivals silently bumped seniors placed
earlier.

A repair loop now runs after the market closes: any senior sitting outside the
top 11 on the final ladder is removed and re-placed, and re-placement requires
**headroom at seat 10 or better** so a subsequent arrival cannot bump them
again. Up to six passes.

**Result: 863 boys and 881 girls rising seniors placed, 100% inside varsity on
the final ladder.**

### Standing exclusions

Ronald Reagan is hard-excluded as a destination (permanent doormat rule). Zero
placements there. Never place a player at their current school.

---

## 5. Results

### 5.1 The middle no longer gets skipped

| Levels dropped | Boys | Girls | Combined | Share |
|---|---|---|---|---|
| 0 (same level) | 3,575 | 4,280 | 7,855 | **73%** |
| 1 | 640 | 565 | 1,205 | 11% |
| 2 | 473 | 386 | 859 | 8% |
| 3 | 254 | 167 | 421 | 4% |
| 4 | 122 | 89 | 211 | 2% |
| 5 | 51 | 102 | 153 | 1% |
| 6 | 14 | 13 | **27** | 0.3% |

Twenty-seven players out of 10,731 crossed six competitive levels, and only
after every level above failed to find them a role. In 2039 that band was the
majority of the wave.

### 5.2 Same-class retention by origin

| From | Boys placed | Same class | Girls placed | Same class |
|---|---|---|---|---|
| 9A | 643 | 73% | 708 | 73% |
| 8A | 663 | 66% | 648 | 72% |
| 7A | 579 | 72% | 628 | 78% |
| 6A | 625 | 71% | 709 | 75% |
| 5A | 523 | 60% | 541 | 68% |
| 4A | 490 | 64% | 499 | 73% |
| 3A | 563 | 58% | 694 | 73% |
| 2A | 594 | 62% | 668 | 69% |
| 1A | 449 | 100% | 507 | 100% |

1A is 100% by construction: it is the terminal market and has nowhere to spill.

Lateral moves *within* a band (9A↔8A, 7A↔6A) were rare — 35 boys, 65 girls.
Exact-class matching absorbed nearly all of the level-1 and level-2 demand
before the lateral pass was needed. Worth watching in future runs: if the
exact-class bonus is too strong, genuine lateral redistribution never fires.

### 5.3 Net flow by classification

| Class | Boys net | Girls net |
|---|---|---|
| 9A | −173 | −186 |
| 8A | −217 | −153 |
| 7A | −96 | −78 |
| 6A | −61 | −68 |
| 5A | **+9** | **+46** |
| 4A | **+47** | **+88** |
| 3A | −70 | −156 |
| 2A | −87 | −154 |
| 1A | **+648** | **+661** |

The intended shape. The top four classes shed surplus, **5A and 4A now retain
and absorb** rather than acting as a waypoint, 3A and 2A remain net exporters
because their own surplus clears downward, and 1A is the terminal sink.

The 2039 failure was 5A/4A running net-negative while 1A–3A absorbed
everything. That is now inverted at 5A and 4A.

### 5.4 Outcome quality

| | Boys | Girls |
|---|---|---|
| Placed | 5,129 | 5,602 |
| Median projected seat | 12 | 12 |
| Landing inside varsity 11 | 2,289 (45%) | 2,463 (44%) |
| Rising seniors placed | 863 | 881 |
| Seniors inside varsity | **100%** | **100%** |

### 5.5 Grade mix

| Grade in 2039 | Boys | Girls |
|---|---|---|
| 9 → 10 | 2,686 | 2,958 |
| 10 → 11 | 1,580 | 1,763 |
| 11 → 12 | 863 | 881 |

Heavily weighted to underclassmen, which is expected: rising seniors who were
buried had usually already been cleared in prior waves or had graduated.

### 5.6 Load distribution

- **779 of 780 boys programs** and **863 of 864 girls programs** receive at
  least one player. Effectively the entire association participates.
- Maximum arrivals at any single program: **18**.
- Ronald Reagan: **0** arrivals.

---

## 6. Decisions made during the run, and why

**Seat threshold split by grade.** The brief permits younger players a wider
range of useful outcomes; seniors have one priority. Encoding that as
`seat ≤ 11` for seniors and `seat ≤ 14` for everyone else is what let the
market clear laterally instead of cascading.

**Senior repair loop rather than senior-first ordering alone.** Sorting seniors
first was not sufficient, because displacement is second-order: a senior placed
in round 1 can be bumped by a round-3 arrival at the same program. Only a
post-close check against the final ladder catches it. Requiring seat ≤ 10 on
re-placement leaves the headroom that prevents recurrence.

**Low-end depth as a penalty, not a bonus.** Earlier waves treated open roster
spots as demand. The brief is explicit that a program already carrying lots of
low-end depth should be a lower-priority destination. Implemented as a per-head
penalty for sub-varsity players at 30+ OVR.

**Arrival cap of 6 per program per pass.** Prevents any single weak program
absorbing an entire class. The observed max of 18 comes from a program
receiving across multiple levels and from the repair pass.

**Four-round stability limit per level.** Second-order displacement can in
principle chain indefinitely. Four rounds converged in practice; unresolved
candidates carry to the next level rather than looping.

---

## 7. Known limitations

1. **Lateral within-band matching barely fired** (100 moves total). The
   exact-class bonus of +25 versus lateral +12 may be too wide. If the intent
   is genuine 9A↔8A redistribution, narrow that gap.
2. **Seat projection is static.** A destination's ladder is recalculated as
   arrivals land, but no allowance is made for the destination's own outgoing
   players in later levels. Minor, since most programs both send and receive.
3. **No geography weighting.** The brief does not require it for this market
   and it was omitted deliberately. If feeder-style legibility matters later,
   it is a scoring term away.
4. **Displacement is modelled, migration of the displaced is capped.** An
   incumbent bumped out of varsity re-enters at their own level, but if
   unresolved they carry down like any other surplus rather than being
   protected.
5. **JV evidence is used only as a filter, not as a ranking signal.** The
   brief's eventual goal is distinguishing "competitively active but
   varsity-blocked" from "genuinely underused." Currently only varsity match
   count is used. JV win rate is available and unused.

---

## 8. What to measure after the 2040 season

Per the brief's measurement list, the questions this class should be judged on:

**Player outcomes** — varsity participation before/after, JV participation
before/after, final ladder position, classification movement, senior varsity
success rate, and how many remain functionally invisible.

**Program outcomes** — roster size, top-11 strength, JV depth, lateral
arrivals, arrivals from higher levels, players displaced downward.

**Competitive-level outcomes** — median roster size, median top-11 strength, JV
participation, inflow/outflow, competitive variance, and specifically
**whether 4A–7A remain healthy rather than hollowed out**. That is the
hypothesis this design exists to test; 5A and 4A running net-positive is the
pre-registration.

**Pinned cohort.** The 10,731 player_ids in the two output files are a fixed
set. Track that exact set forward rather than recomputing the eligible
population each season — recomputing lets incoming freshmen refill the pool and
hides the effect entirely.

---

## 9. Design principle

The low-end market does not ask how far down the pyramid a player can go.

It asks: **what is the highest competitive level at which this player can find
a genuinely useful role?**

Search laterally first. Move down only when the current level has no home.
Recalculate after every move. Keep cascading until everybody has one.
