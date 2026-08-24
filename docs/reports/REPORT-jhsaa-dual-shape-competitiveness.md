# Report — what a dual's SHAPE does to how close it finishes

Measured 2026-08, on the 1A field, alongside the 2S/3D postseason pilot
(`docs/AAR-jhsaa-1a-2s3d-postseason-pilot.md`). It exists because the owner stated a
design preference — *"this is also why I prefer the 1/4 format over something more
traditional"* — and a preference that decides the association's championship format
is worth having numbers under rather than leaving in a chat log.

**Short version: the preference is right, and the reason for it is not the obvious
one.** Doubles-forwardness is not what makes 1S/4D close. **Court count is.**

---

## Method

Every 1A program with a roster deep enough to dress the widest shape (11), ranked by
`ladder_score`, paired **adjacently by team strength** — the evenly-matched pairings a
bracket's later rounds actually produce, and the only place a format can change
anything (mismatched duals agree across shapes 85-90% of the time; see the AAR).

Each pairing replayed under **20 distinct seeds per shape**, every shape seeing the
same seed, so the comparison is paired. 920 duals per shape (girls), 860 (boys).
Lineups are the frozen-order top N in ladder order for each shape. `FIDELITY="fast"`,
high-school no-ad scoring, 2039 rosters.

### ‼️ ODD COURT COUNTS ONLY — and this was a real bug in the first run

The first version of this comparison included **3S/3D (6 courts)** and **7S/1D (8
courts)** and produced nonsense that looked plausible: ~30-38% "nailbiters" against
~60-68% for the odd shapes, with upset rates jumping to 66%.

Two independent faults, both silent:

1. **`margin` shares the parity of the court count.** In a 7-court dual the margin is
   odd (1, 3, 5, 7), so `margin <= 1` means "decided by one court". In a 6-court dual
   the margin is even (0, 2, 4, 6), so `margin <= 1` means **`margin == 0`** — the test
   silently stopped measuring closeness and started measuring **ties**.
2. **An even-court dual can tie, and `engine.dual` reports a tie as an away win**
   (`winner = 0 if points[0] > points[1] else 1`). That is the exact trap documented
   for `jv_outcome` in CLAUDE.md, and it inflated the upset rate.

Even shapes are not legal in this association anyway — **every JHSAA format is odd by
design so a dual cannot be tied, and there is no tie-breaking logic anywhere** — so
they were dropped rather than special-cased. Worth stating because the contaminated
table read as a strong result: it appeared to show traditional shapes producing far
fewer close matches, which is the answer someone hoping for it would have shipped.

---

## Results — evenly-matched 1A pairings

`1-court` = share of duals decided by a single court (the minimum possible margin at
an odd court count). `margin%` = mean margin as a share of total courts, which is how
you compare a 5-court dual to a 7-court one at all. `best plyr` = the share of the
dual one court represents, i.e. the most a single player can be worth.

### Girls (46 pairings × 20 = 920 duals per shape)

| Shape | Courts | Dresses | **1-court** | Upset | margin% | best plyr | doubles share | |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **1S/4D** | 5 | 9 | **68%** | 49% | 34% | 20% | 80% | current postseason |
| **2S/3D** | 5 | 8 | **73%** | 48% | 32% | 20% | 60% | the 1A pilot |
| 3S/4D | 7 | 11 | 60% | 44% | 28% | 14% | 57% | the league card |
| 5S/2D | 7 | 9 | 60% | 45% | 28% | 14% | 29% | traditional |
| 6S/1D | 7 | 8 | 58% | 46% | 29% | 14% | 14% | very traditional |

### Boys (43 pairings × 20 = 860 duals per shape)

| Shape | Courts | Dresses | **1-court** | Upset | margin% | best plyr | doubles share | |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **1S/4D** | 5 | 9 | **67%** | 48% | 35% | 20% | 80% | current postseason |
| **2S/3D** | 5 | 8 | **67%** | 49% | 35% | 20% | 60% | the 1A pilot |
| 3S/4D | 7 | 11 | 59% | 51% | 29% | 14% | 57% | the league card |
| 5S/2D | 7 | 9 | 58% | 50% | 29% | 14% | 29% | traditional |
| 6S/1D | 7 | 8 | 59% | 47% | 29% | 14% | 14% | very traditional |

---

## What the numbers actually say

### 1. The preference is empirically correct

A five-court shape finishes on a single court **67-73%** of the time; a seven-court
shape **58-60%**. Mean margin as a share of the dual is **32-35%** against **28-29%**.
Both genders, same direction, ~1,800 duals a cell. **1S/4D and 2S/3D produce
materially closer championship duals than any traditional shape tested**, and the
owner's preference for it over "something more traditional" is well founded.

### 2. ‼️ BUT THE MECHANISM IS COURT COUNT, NOT DOUBLES

The intuitive story — *doubles is the volatile discipline, so a doubles-forward shape
produces closer matches* — **is not what the data shows.** Hold the court count at
seven and sweep the doubles share from 57% to 14%:

| 7-court shape | doubles share | 1-court (girls / boys) |
|---|---:|---:|
| 3S/4D | 57% | 60% / 59% |
| 5S/2D | 29% | 60% / 58% |
| 6S/1D | 14% | 58% / 59% |

**Flat.** Quadrupling the singles content of a seven-court dual moves closeness by
~2 points, inside noise. Meanwhile dropping from seven courts to five moves it by
**8-13 points** at a constant doubles share (compare 3S/4D at 57% doubles to 2S/3D at
60% doubles: 59-60% → 67-73%).

The reason is ordinary sampling, not tennis: **a dual is an average over its courts,
and fewer courts average less.** Five roughly even coin-flips land 3-2 more often than
seven land 4-3. The doubles-forward character of 1S/4D is a *separate* design property
(it decides who plays, and how a roster is built) — it is not what makes the format
close.

### 3. This is the strongest argument FOR the pilot's specific shape

If closeness comes from court count, then **2S/3D is the only way to add a real second
singles seat without giving the property up.** It holds the dual at five courts and
adds the singles court by taking one from doubles. Every alternative fails:

- **2S/4D** (6 courts) — can tie; the association has no tie-break and wants none.
- **3S/3D** (6 courts) — same problem.
- **2S/5D / 3S/4D** (7 courts) — drops straight to the 58-60% band, i.e. gives up the
  thing that makes the postseason feel the way it does.

So the pilot is not a compromise toward tradition. It is the *maximum* singles content
available at five courts, which is exactly where the owner drew the line.

### 4. Upset rate is flat across every shape (44-51%)

No shape tested is meaningfully more or less "fair" in the evenly-matched band — as
you would expect, since these pairings are near-even by construction. Format choice
buys *closeness*, not *chaos*. (The mismatched band, where a format could hand a
tournament to underdogs, is covered in the AAR: 85-90% concordance, ≤3-point upset
movement.)

### 5. A note on roster cost

`Dresses` is worth reading beside the rest: **2S/3D (8) costs the same roster spot as
6S/1D (8)**, and 1S/4D (9) costs the same as 5S/2D (9). The one-player cost of the
pilot is not a price paid for being unconventional — it is what any 8-player shape
costs, traditional or not. The league card's 3S/4D is the outlier at eleven.

---

## Caveats

- **Ladder is pure ability** (no season played), so this measures the SHAPE, not a
  particular year's results.
- **1A only.** The court-count mechanism should generalise — it is arithmetic, not a
  property of 1A — but the absolute rates depend on how flat the field is, and 1A's is
  flatter than most (see the AAR's boys/girls strength-spread table).
- **Evenly-matched pairings only** in this table, deliberately: that is where a format
  can change an outcome at all.
- Reproduce with `scripts/jhsaa_1a_format_pilot_calibration.py` for the pilot's own
  numbers; this cross-shape sweep was a one-off measurement and its parameters are
  recorded above rather than committed as a script — if it is re-run, **re-read the
  odd-court-count warning first.**
