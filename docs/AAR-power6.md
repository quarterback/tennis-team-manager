# AAR — Power 6 (roster strength)

## Problem
There was no at-a-glance read of a team's roster strength. The preseason ranking
order was computed from roster ability but the underlying number was never shown
anywhere — an aggregate that didn't surface, so it was unhelpful.

## What changed
Added **Power 6** — a UTR-style roster-strength number from a program's top-6
singles players' STR. `state._power6(prog)` = mean of the top-6 STR × 2, so it
lands on an easy, spread-out scale where the strongest rosters clear 100 (a raw
sum on our ~50 STR scale read as a meaningless ~300; a plain mean was ~50). It's
populated even preseason (STR falls back to ability before any results).

Surfaced in two places, always (not just preseason):
- **Rankings page** — a Power 6 column plus a "Power 6" sort option.
- **Team page** — in the header beside Power Index.

`LiveRow` carries `p6`; the teams route passes it through (the header `row` comes
from a different `RankRow` that lacks it).

## Notes
The scale (mean × 2) was a product decision — it doesn't track UTR's exact band,
it's just an easy-to-read number. Kept the name "Power 6".

## Verification
Top D1-women programs land ~98–100, LSU's screenshot lineup ≈ 93; the column
sorts and both pages render with the value present.
