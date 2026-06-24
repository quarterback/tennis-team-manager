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

```
RankScore    = 100 / NationalRank      # #1 → 100, #10 → 10, #100 → 1, #2500 → 0.04
StarValue    = 7 if Blue Chip else star count   # 5★→5, 4★→4, 3★→3, 2★→2, 1★→1, Unrated→0
RecruitScore = RankScore × STR × StarValue
```

Class score = **Σ RecruitScore**; classes rank by it (tiebreak: total stars, then
school for stability).

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

- `RankScore = 100 / rank` matches the owner's full fidelity table — all 18
  anchor points (#1…#2500).
- Worked examples: #1 Blue Chip @ STR 53 → 100×53×7 = **37,100**; #40 4★ @ STR 50
  → 2.5×50×4 = **500**; #150 3★ @ STR 48 → 0.667×48×3 ≈ **96**; Unrated → 0.
- Ranking now rewards quality: a 2-man blue-chip class outscores a six-man 3★
  class, where the old star-sum put the bigger class on top.

## UI

Signing tracker shows a **SCORE** column (comma-formatted), ranks by it, and a
small 💎 blue-chip count beside programs that landed one. Per owner feedback, the
explanatory tooltip / wordy microcopy was removed — the column speaks for itself.

## Notes

- Scores are large (top classes reach the tens/hundreds of thousands) because the
  `100/rank × STR × StarValue` product compounds; that's the intended shape — the
  #1 recruit dominates — not a bug.
- The numerator lives in `_RANK_SCORE_NUMERATOR = 100.0` if it ever needs tuning.
