# AAR — Transfer realism (division-respecting, one per career)

## Symptom
After a rollover, D1 starters (not just walk-ons) were transferring to D3 — the
portal let players skip divisions.

## Root cause
`transfer_portal` chose destinations by a PRESTIGE band (`PRESTIGE_BAND`), so a
low-prestige D1 program and a D3 program sat in the same band and were mutually
reachable. Division was never considered.

## Fix — destinations by division
Rebuilt the destination logic around the team's division (`_UP_DIV` / `_DOWN_DIV`
allow only adjacent levels):

- **Default: lateral within the same division** — a better-prestige program that
  wants them in the lineup (the common, realistic transfer).
- **Up only one level** (D3→D2, D2→D1) and only for a genuine #1/#2 talent
  (top-2 line, reliable, STR clearly above their level). D1 players never go up;
  no one skips a level.
- **Down only one level** (D1→D2, D2→D3) and only for the **buried** (no lineup
  spot in their own division) — so a starter never drops.
- No fit → the player **stays put** (no forced departure out of the universe;
  the old code dropped non-movers entirely).

## Fix — one engine transfer per career
`_career_transfers(p)` counts school changes in a player's history; the mover
selection skips anyone already at ≥1. The engine moves a player at most once.

## Editor is unaffected
These rules live only in `world.transfer_portal` (the auto off-season). Manual
editor moves go through `overrides.set_move`, which has no division or career
check and offers every school across all divisions — you can still place anyone
anywhere, as often as you like. Verified a manual D1→D3 move lands.

## Verification
On a real cross-division pool (post-graduation openings): zero division-skip
moves, moves are same-division or exactly one level (D1→D2, D2→D3), and a player
with a prior transfer isn't moved again. Regression test added; world +
single-gender determinism suites pass.
