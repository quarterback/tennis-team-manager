# Report — JHSAA dual shapes: what a format does to a match

Measured 2026-08 on the 1A field, alongside the 2S/3D postseason pilot. **This is the
data record for that decision** — every number the pilot was argued from lives here.
`docs/AAR-jhsaa-1a-2s3d-postseason-pilot.md` is the narrative and the engineering
lessons; it quotes these tables rather than owning them.

It exists because the owner stated a design preference — *"this is also why I prefer
the 1/4 format over something more traditional"* — and a preference that decides the
association's championship format is worth having numbers under rather than leaving in
a chat log.

## Contents

1. [Method](#method) — and two measurement traps that each shipped a wrong answer
2. [Participation](#1-participation--what-the-pilot-costs-and-who-it-promotes) — what 2S/3D costs a roster, and who gets the new S2
3. [The pilot head-to-head](#2-the-pilot-head-to-head--1s4d-vs-2s3d) — 1S/4D vs 2S/3D, 3,560 duals
4. [The field itself](#3-the-field-itself--why-boys-and-girls-1a-differ) — boys vs girls 1A strength distribution
5. [The cross-shape sweep](#4-the-cross-shape-sweep--eight-formats) — eight formats, including 3S/2D
6. [What the numbers say](#what-the-numbers-say)
7. [Caveats](#caveats)

---

## Method

Every 1A program whose roster can dress the shape under test, ranked by
`ladder_score`, then paired two ways:

- **Evenly matched** — adjacent by team strength. The pairings a bracket's later
  rounds actually produce, and the only place a format can change anything.
- **Mismatched** — top half against bottom half, reversed. The control.

Each pairing is replayed under **20 distinct seeds**, every format seeing the same
seed, so the comparison is paired. Lineups are the frozen-order top N in ladder order,
arranged by the shipped `_arrange_state` / `_arrange_1a_postseason`. `FIDELITY="fast"`,
high-school no-ad scoring, 2039 rosters, 179 programs (93 girls / 86 boys).

**Definitions.** `1-court` = share of duals decided by a single court (the minimum
possible margin at an odd court count) — the "3-2 nailbiter" rate. `margin%` = mean
margin as a share of total courts, which is the only way to compare a 5-court dual to a
7-court one. `upset` = the weaker team by top-9 mean OVR wins.

### ‼️ TRAP 1 — one seed per pairing is not a sample

The first run used one seed per pairing (~45 duals a cell) and reported the nailbiter
rate moving in **opposite directions by gender**: boys 81%→53% against girls 63%→72%.
**That divergence does not exist.** At 20 trials it is boys 70%→68%, girls 67%→70%.

It was perfectly reproducible, which is what made it dangerous — determinism is
necessary and not sufficient. And it *looked* like a census, because it covered every
1A program: it was exhaustive over **programs** and a single draw over **outcomes**,
and the outcome is the thing being measured. **When the quantity is a rate over
simulated results, the sample size is the number of DUALS, never the number of teams.**

(A prior version was worse still: it seeded from Python's `hash()`, which is salted per
process, so ordinary re-runs moved concordance up to 8 points and upset rate up to 16.
Seeds are `hashlib.blake2s` now — the idiom the module already uses.)

### ‼️ TRAP 2 — odd court counts only

The first cross-shape sweep included **3S/3D (6 courts)** and **7S/1D (8 courts)** and
produced a strong, plausible, wrong result: ~30-38% "nailbiters" for those against
~60-68% for the odd shapes, with upset rates jumping to 66%. It appeared to show
traditional shapes producing far fewer close matches — the answer someone hoping for it
would have shipped.

Two independent silent faults:

1. **`margin` shares the parity of the court count.** In a 7-court dual the margin is
   odd (1, 3, 5, 7), so `margin <= 1` means "decided by one court". In a 6-court dual it
   is even (0, 2, 4, 6), so `margin <= 1` means **`margin == 0`** — the test stopped
   measuring closeness and started measuring **ties**.
2. **An even-court dual can tie, and `engine.dual` reports a tie as an away win**
   (`winner = 0 if points[0] > points[1] else 1`) — the exact trap documented for
   `jv_outcome` in CLAUDE.md. It inflated the upset rate.

Even shapes are not legal here anyway: **every JHSAA format is odd by design so a dual
cannot be tied, and there is no tie-breaking logic anywhere.** Dropped rather than
special-cased.

---

## 1. Participation — what the pilot costs, and who it promotes

2S/3D dresses **eight** where 1S/4D dresses **nine**. That is the whole cost of the
pilot and the reason it had been rejected before.

| | |
|---|---|
| Player cut from the postseason roster (was seat #9 of 9) | mean OVR **27.8**, median 28.0 |
| Gap from that player up to seat #8, the last who still dresses | mean **2.03** OVR, **median 1.00** |
| Programs where the cut player is within 2 OVR of dressing | **127 / 179 (71%)** |

**For 71% of 1A programs the kid who loses their postseason spot is within two OVR of
the last player who keeps one.** It is not a scrub being trimmed; it is a close call,
179 times. Accepted knowingly — a 24-team playoff where a program needs one fewer kid
to contend is worth it — but the number belongs beside the upside, not under it.

Who plays the new S2 court, by rank in the top-four anti-stacking pool:

| Rank | Programs | Share |
|---|---:|---:|
| #2 | 141 | **79%** |
| #3 | 35 | 20% |
| #4 | 3 | 2% |

The format overwhelmingly promotes the **#2 player to a real singles court** — the
stated point of the change — while leaving the coach a live choice that fires ~21% of
the time. A rule producing 100% "#2 plays S2" would have been a fixed allocation
wearing a search's clothes; this one is a real decision.

---

## 2. The pilot head-to-head — 1S/4D vs 2S/3D

Same pairings, same seeds, both shapes. 920 duals per cell (girls), 860 (boys).

| | Girls, even | Boys, even | Girls, mismatched | Boys, mismatched |
|---|---:|---:|---:|---:|
| Duals | 920 | 860 | 920 | 860 |
| **Same winner under both formats** | **70%** | **73%** | 85% | 90% |
| Upset rate, 1S/4D → 2S/3D | 47% → 50% | 49% → 50% | 16% → 16% | 11% → 10% |
| Mean margin (of 5 points), 1S/4D → 2S/3D | 1.73 → 1.67 | 1.66 → 1.76 | 2.79 → 2.72 | 3.05 → 3.09 |
| **Nailbiters (3-2), 1S/4D → 2S/3D** | **67% → 70%** | **70% → 68%** | 35% → 40% | 33% → 33% |

**In evenly-matched duals the format decides ~27-30% of outcomes.** Only 70% (girls) /
73% (boys) of close pairings produce the same winner under both shapes — the same eight
or nine kids, the same opponent, the same seed, a different answer. That is the
"flips outcomes" property the pilot was wanted for, and it lands where you want it: in
the bracket's close matches, not the blowouts.

**The nailbiter rate is a FEATURE, not a caveat** (owner, 2026-08). An evenly-matched
1A dual lands 3-2 **~70% of the time under both formats**. A five-point shape in a flat
field is coin-flip-adjacent by construction, and that is the juice a 24-team 1A bracket
is meant to have. An earlier draft filed this row under "noise, do not build a rule on
it" and buried the most characteristic number in the study.

**It does not make the association more chaotic.** Mismatched duals agree 85-90% of the
time and the upset rate barely moves in any cell (≤3 points, and *down* in boys'
mismatched). A clearly better team stays clearly better; 2S/3D reshuffles *which* close
matches flip.

---

## 3. The field itself — why boys' and girls' 1A differ

The durable gender difference in the tables above is **structural, not a format
effect**. Owner's read — *"1A teams are kind of balanced weird; boys tennis has higher
STR abilities meaning the top teams kind of separate themselves, whereas the girls are
more evenly matched by design"* — confirmed by direct measurement:

| 1A programs | Girls (93) | Boys (86) |
|---|---:|---:|
| Team strength, top-9 mean OVR | 38.52 | **42.09** |
| Spread (sd) | 4.27 | **4.64** |
| p90 − p10 | 10.78 | **12.11** |
| Best player OVR | 58.22 | **60.76** |
| Best player STR | 47.56 | **48.66** |
| Adjacent-pair strength gap (mean / median) | 0.21 / 0.11 | 0.25 / 0.11 |

Boys' 1A is both **stronger and more spread** — the good programs separate. Girls' 1A
is flatter. That shows up exactly where you would expect, in the **mismatched** cells
rather than the nailbiter row:

| Mismatched | Girls | Boys |
|---|---:|---:|
| Same winner under both formats | 85% | **90%** |
| Upset rate (2S/3D) | 16% | **10%** |
| Mean margin | 2.79 | **3.09** |

**More separation → bigger margins, fewer upsets, less room for a format to change
anything.** So 2S/3D has more leverage in girls' 1A than boys', and that is a property
of the FIELD, not of the shape. Do not read a gender gap in a future run as a format
regression without checking the strength distribution first.

---

## 4. The cross-shape sweep — eight formats

All odd court counts. Evenly-matched pairings only.

### Girls (46 pairings × 20 = 920 duals per shape)

| Shape | Courts | doubles% | Dresses | **1-court** | Upset | margin% | |
|---|---:|---:|---:|---:|---:|---:|---|
| **1S/4D** | 5 | 80% | 9 | **68%** | 49% | 34% | current postseason |
| **2S/3D** | 5 | 60% | 8 | **73%** | 48% | 32% | the 1A pilot |
| 3S/2D | 5 | 40% | 7 | 70% | 49% | 33% | the classic HS format |
| 4S/1D | 5 | 20% | 6 | 65% | 49% | 35% | singles-heavy |
| 5S/0D | 5 | 0% | 5 | 63% | 49% | 36% | no doubles at all |
| 3S/4D | 7 | 57% | 11 | 60% | 44% | 28% | the league card |
| 5S/2D | 7 | 29% | 9 | 60% | 45% | 28% | traditional |
| 6S/1D | 7 | 14% | 8 | 58% | 46% | 29% | very traditional |

### Boys (43 pairings × 20 = 860 duals per shape)

| Shape | Courts | doubles% | Dresses | **1-court** | Upset | margin% | |
|---|---:|---:|---:|---:|---:|---:|---|
| **1S/4D** | 5 | 80% | 9 | **67%** | 48% | 35% | current postseason |
| **2S/3D** | 5 | 60% | 8 | **67%** | 49% | 35% | the 1A pilot |
| 3S/2D | 5 | 40% | 7 | 62% | 52% | 37% | the classic HS format |
| 4S/1D | 5 | 20% | 6 | 62% | 53% | 38% | singles-heavy |
| 5S/0D | 5 | 0% | 5 | 61% | 53% | 38% | no doubles at all |
| 3S/4D | 7 | 57% | 11 | 59% | 51% | 29% | the league card |
| 5S/2D | 7 | 29% | 9 | 58% | 50% | 29% | traditional |
| 6S/1D | 7 | 14% | 8 | 59% | 47% | 29% | very traditional |

---

## What the numbers say

### The preference is empirically correct

Five-court shapes finish on a single court **61-73%** of the time; seven-court shapes
**58-60%**. Mean margin as a share of the dual is **32-38%** against **28-29%**. Both
genders, same direction, ~1,800 duals a cell. **1S/4D and 2S/3D produce materially
closer championship duals than any traditional shape tested.**

### ‼️ Court count dominates; doubles share is a real secondary term

**A CORRECTION TO THE FIRST VERSION OF THIS REPORT**, which concluded flatly that
doubles share does not matter, on the strength of the seven-court band alone:

| 7-court shape | doubles share | 1-court (girls / boys) |
|---|---:|---:|
| 3S/4D | 57% | 60% / 59% |
| 5S/2D | 29% | 60% / 58% |
| 6S/1D | 14% | 58% / 59% |

That band really is flat — but it sweeps doubles only 57%→14%, and the conclusion was
generalised past the range measured. **The full range at a constant five courts shows a
real gradient** (3S/2D and 4S/1D, the shapes the first pass omitted, are exactly the
controls that expose it):

| 5-court, doubles share | 80% | 60% | 40% | 20% | 0% |
|---|---:|---:|---:|---:|---:|
| shape | 1S/4D | 2S/3D | 3S/2D | 4S/1D | 5S/0D |
| 1-court, girls | 68% | **73%** | 70% | 65% | 63% |
| 1-court, boys | 67% | **67%** | 62% | 62% | 61% |

Doubles contributes roughly **6-10 points** across the full sweep — modest, real, and
not nothing.

**Court count is still the dominant term**, and it is the one that holds at constant
doubles share: 3S/4D (57% doubles, 7 courts) gives 59-60% while 2S/3D (60% doubles, 5
courts) gives 67-73% — **8-13 points for the court count alone**. Every seven-court
shape sits in a 58-60% band regardless of composition; every five-court shape sits at
61-73%.

The dominant mechanism is ordinary sampling, not tennis: **a dual is an average over
its courts, and fewer courts average less.** Five roughly even coin-flips land 3-2 more
often than seven land 4-3. Doubles adds a second-order lift on top, most likely because
a pair's result is itself noisier than a singles court's.

**Lesson, and it is the same one Trap 2 carries: do not state a conclusion wider than
the range you swept.** A three-point sweep across a narrow band read as "flat" and was
written up as a general law about doubles; the full sweep needed two more shapes and
reversed the qualitative claim.

### This is the strongest argument FOR the pilot's specific shape

**2S/3D is the only way to add a real second singles seat without giving the property
up.** It holds the dual at five courts and takes the singles court from doubles. Every
alternative fails:

- **2S/4D** (6 courts) — can tie; the association has no tie-break and wants none.
- **3S/3D** (6 courts) — same problem.
- **2S/5D / 3S/4D** (7 courts) — drops straight to the 58-60% band.

So the pilot is not a compromise toward tradition. It is the *maximum* singles content
available at five courts — and it sits at or near the **peak** of the doubles-share
curve in both genders (girls 73%, the highest of any shape measured; boys 67%, tied
with 1S/4D).

### How 3S/2D — the classic American format — compares

Asked directly (owner, 2026-08: *"I'm not gonna switch to it, but I am curious how it
compares to what we're doing"*). 3S/2D is the format a large share of US states play,
and it is a five-court shape, so it belongs in the same band as the association's own:

| | Courts | Dresses | 1-court (G / B) | Upset (G / B) | margin% (G / B) |
|---|---:|---:|---:|---:|---:|
| 1S/4D (current) | 5 | 9 | 68% / 67% | 49% / 48% | 34% / 35% |
| 2S/3D (pilot) | 5 | 8 | **73% / 67%** | 48% / 49% | 32% / 35% |
| **3S/2D (classic)** | 5 | **7** | **70% / 62%** | 49% / 52% | 33% / 37% |
| 5S/2D (7-court trad) | 7 | 9 | 60% / 58% | 45% / 50% | 28% / 29% |

**It holds up well** — level with 1S/4D in girls (70% vs 68%), about five points less
close in boys (62% vs 67%), and comfortably clear of every seven-court shape. A
legitimately competitive format in this engine, not a straw man.

What it costs is the doubles-forward character: at 40% doubles it is the point on the
curve where the association's identity starts to go. What it saves is roster — **it
dresses SEVEN**, the cheapest of any shape here, two fewer than 1S/4D. If roster depth
were ever the binding constraint (it is not; `ROSTER_FLOOR` is 16), this is the shape
that would answer it.

Not adopted and not proposed: recorded because it is the natural comparison to ask of
any format decision, and because running it is what caught the overstated "doubles
doesn't matter" claim above.

### Upset rate is flat across every shape (44-53%)

No shape tested is meaningfully more or less "fair" in the evenly-matched band — as you
would expect, since those pairings are near-even by construction. **Format choice buys
closeness, not chaos.** The mismatched band, where a format could actually hand a
tournament to underdogs, is §2: 85-90% concordance, ≤3-point upset movement.

### Roster cost is not a penalty for being unconventional

`Dresses` is worth reading beside the rest: **2S/3D (8) costs the same roster spot as
6S/1D (8)**, and 1S/4D (9) costs the same as 5S/2D (9). The one-player cost of the
pilot is what any 8-player shape costs, traditional or not. The league card's 3S/4D is
the outlier at eleven.

---

## Caveats

- **Ladder is pure ability** (no season played), so this measures the SHAPE, not a
  particular year's results. A real season moves players via `ladder_score`.
- **1A only.** The court-count mechanism should generalise — it is arithmetic, not a
  property of 1A — but absolute rates depend on how flat the field is, and 1A's is
  flatter than most (§3).
- **Evenly-matched pairings** in the sweep tables, deliberately: that is where a format
  can change an outcome at all. The mismatched control is §2.
- The pilot's own numbers (§1-§3) reproduce with
  `scripts/jhsaa_1a_format_pilot_calibration.py` (default `--trials 20`). The
  cross-shape sweep (§4) was a one-off measurement; its parameters are recorded in
  Method above rather than committed as a script. **If it is re-run, read both traps
  first.**
