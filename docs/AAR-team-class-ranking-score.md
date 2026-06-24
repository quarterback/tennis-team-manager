# AAR — Team class rankings: rank × STR × star-value scoring

**Date:** 2026-06-23
**Scope:** `state.signing_tracker` (`_recruit_score` / `_star_value`) and the
signing-tracker template. Ranking only — no change to recruiting/selection.

## Problem

The signing tracker ranked classes by **`total_stars` = sum of `recruit_stars`
(1–5)**, tie-broken by class size then **alphabetically by school**. Two structural
flaws (owner-flagged on the live D1 board):

- **Blue-chips and 5★ were indistinguishable.** `star_rating()` caps at 5, so the
  best recruit in the country and a borderline 5★ both contributed exactly 5.
- **Flat linear sum.** Three 4★ (12) outranked two blue-chips (10); quantity
  tie-broke before quality; the long tail sat in alphabetical order.

## The formula (owner-specified)

Per recruit:

**Final formula** (`_class_score`): take a program's top 3 recruits by national
rank, then

```
ClassScore = 0.1 × Σ STR(top3) × sqrt(1000 / average rank(top3))
```

STR is `str_value()` (the figure the recruit page shows). e.g. Arizona State
(#8/#18/#29 @ ~52) → `0.1 × 156.3 × sqrt(1000/18.3)` = **115.4**; Ole Miss
(#3/#21/#80) → **82.5**.

### How it got here (the iteration)
1. `100 / rank × StarValue × STR`, summed over the class — flat tiers, blue-chips
   indistinguishable from 5★, padding rewarded.
2. `sqrt(1000 / rank)` to soften the rank curve; **average** of top-3; **star
   multiplier dropped** (rank + STR already track ability).
3. Owner observed a single high-ranked recruit still dominated (STR's tight ~49–53
   band can't move a product the rank factor swings 10× over). Two fixes weighed —
   a 50/50 rank/STR blend (made ASU ≈ Ole, a near-tie) vs **sum-STR × average-rank**
   (made ASU clearly win). Chose the latter, **depth-first**: it uses *combined*
   STR (rewards three studs over one + filler) and *average* rank (a low-ranked
   third commit drags the class down, so a lone superstar can't carry it).
4. Scaled `× 0.1` so scores read on a ~100 line (uncapped — elite classes exceed
   100). `_star_value` stays in the module, unused, for a possible re-add.

**Class score = the AVERAGE RecruitScore of a program's TOP 3 recruits** (by
RecruitScore) — a class is judged by its headliners, not padded by depth. Classes
rank by it (tiebreak: total stars, then school for stability). A class with fewer
than three signees averages over however many it has.

`_RANK_SCORE_NUMERATOR = 1000` (inside the sqrt) if the curve ever needs tuning.

### Input mapping (the part that needed care)

The game has two tier systems; the **consensus board** is authoritative here:
- **NationalRank** = `recruit_rank` — assigned by `juniors.rank_class`.
- **Tier / stars** = `recruit_tier` / `recruit_stars` — also set by `rank_class`
  via `tier_for_rank` (quantile cutoffs: Blue Chip ≤1.5%, 5★ ≤4%, 4★ ≤12%,
  3★ ≤30%, 2★ ≤58%, 1★ ≤85%, else Unrated). So `StarValue = 7 if recruit_tier ==
  "Blue Chip" else recruit_stars` reproduces the owner's table exactly, including
  the blue-chip premium that `recruit_stars` (capped at 5) can't express.
- **STR** = `junior_str` (the board STR shown for recruits), falling back to
  `str_value()` if a signee has no junior-circuit STR.

## Verified

- `RankScore = sqrt(1000/rank)`: #1 → 31.6, #10 → 10, #100 → 3.2, #1000 → 1.0,
  #2500 → 0.63.
- Class ordering (top-3 average) reads right: **two blue-chips + a 4★ (≈ 4.4k)**
  > **one blue-chip + filler (≈ 4.0k)** > **three 5★/4★ studs (≈ 3.3k)** > an
  eight-deep 3★ class (low) — quality and a couple of elites win, padding doesn't.

## UI

Signing tracker shows a **SCORE** column (comma-formatted), ranks by it, and a
small 💎 blue-chip count beside programs that landed one. Per owner feedback, the
explanatory tooltip / wordy microcopy was removed — the column speaks for itself.

## Notes

- Scores are large (top classes reach the tens/hundreds of thousands) because the
  `100/rank × STR × StarValue` product compounds; that's the intended shape — the
  #1 recruit dominates — not a bug.
- The numerator lives in `_RANK_SCORE_NUMERATOR = 100.0` if it ever needs tuning.
