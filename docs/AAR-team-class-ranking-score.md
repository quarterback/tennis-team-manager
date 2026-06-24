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
RankScore    = sqrt(1000 / NationalRank)   # #1 → 31.6, #10 → 10, #100 → 3.2, #1000 → 1
RecruitScore = RankScore × STR             # STR = str_value() (the figure shown on the recruit page)
```

The formula evolved over a few passes:
- `100 / rank` (the original fidelity table) made a single #1 recruit ~100× a #100
  and dominate the top-3 average, so a lone superstar + filler beat deep classes.
- `sqrt(1000 / rank)` **softens** that to a ~10× span (#1 → 31.6 vs #100 → 3.2).
- The **star multiplier was dropped** (owner call): rank and STR already track
  ability, so the extra 7/5/4/3/2/1 tier weight was redundant and over-steepened
  the gaps. STR is now `str_value()` (the STR the recruit page displays) so the
  score is transparent against what the user sees. `_star_value` is kept in the
  module, unused, for a quick re-add.

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
