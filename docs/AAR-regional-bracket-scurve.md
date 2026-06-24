# AAR — Regional (S-curve) NCAA bracket structure

**Date:** 2026-06-24
**Scope:** new `app/regions.py`; `seasonmode._region_play_in`, `_region_r16`,
`_region_main_draw`, `_region_main_draw_64`, `_advance_ncaa_round`; `ncaa_field`
labels via `web/state.ncaa_bracket_view`; `templates/ncaa_bracket.html`;
`tests/test_regions.py`.

## What changed — old vs new

### Old: a flat national bracket
The national field was selected/seeded into **one flat bracket**:
- **96 (D1):** top 32 seeds got byes; seeds 33–96 played a **flat play-in** (33 v 96,
  34 v 95, …), winners merged with the byes into a flat 64-team draw seeded by
  `_seed_positions(64)`.
- **64 (D2/D3/D4):** a flat 64 draw via `_seed_positions(64)`.

The standard seeding *implicitly* produced four quarters, but there was no explicit
region concept: no S-curve grouping the owner controlled, no region identity, and
the play-in paired by global seed (33 v 96) rather than within a region.

### New: four S-curve regions
The field is split into **four balanced regions** (basketball-style), and the
region champions meet in the national semifinals. Same Committee Seed Score feeds
selection/seeding (unchanged) — this is purely how the seeded field is *placed*.

- **S-curve split (`regions.scurve_regions`).** The national seed list is dealt to
  regions A/B/C/D one seed line at a time, serpentine: line 1 → A,B,C,D; line 2 →
  D,C,B,A; line 3 → A,B,C,D; … So each region gets exactly one team per seed line
  and total strength is **perfectly balanced** (on 1–96 every region sums to 1164).
- **96-team region (D1):** 24 teams. Seeds 1–8 bye; seeds 9–24 play the **regional**
  opening round (9 v 24, 10 v 23, … 16 v 17); the 8 winners join the byes to form a
  standard 16-team region bracket (1 v w16/17, 8 v w9/24, …).
- **64-team region (D2/D3/D4):** 16 teams, **no play-in** — a direct 16-team region
  bracket. Same methodology, one fewer round.
- **National layout (`MAIN_DRAW_ORDER = [A,D,B,C]`).** The four region brackets are
  concatenated so the #1 and #2 overall seeds' regions sit in opposite halves
  (region ranks A=1,B=2,C=3,D=4 → semis A/D and B/C). Because the existing
  round-advancement just pairs adjacent winners up the tree, **no advancement or
  rendering code had to change** — only the *placement* of round 1 (and, for 96,
  round 2 after the play-in).

### Why this layout (per the owner's directive)
Regions, **not** isolated host-site pods: pods make the draw too dependent on
host placement and can trap higher seeds in unfair local matchups. The goal is
balanced regions, clear seed paths, fewer weird first-round matchups, and readable
national bracket logic — optimised for competitive balance, not geography.

## Bracketing conflict-avoidance (preserved)
The existing penalty machinery (`_pair_penalty` / hill-climb) still runs, now
**scoped within a region**: same-conference and rematch openers are swapped away
inside each region's play-in (`_deconflict_playin`) and 16-bracket
(`_region_r16` swaps which play-in winner faces which bye; `_seed_bracket` swaps
within seed bands for the 64 case). Seed integrity is preserved — teams only trade
with same-line/lower-seed peers, never moving across seed lines.

## Cosmetic region names
Region names are **rotating labels only — never geography**. `regions.region_names`
draws four distinct names per season (deterministic from the season seed, so they
rotate year to year) from a fixed pool of Learned League league names
(`regions.LEAGUE_NAMES`, ~160 names). A "Bayou" or "Pacific" region carries no
geographic meaning and never influences placement. The bracket view attaches the
region label to each team (`web/state._region_map`) and the reveal/seed-sheet show
a small region chip.

## Verified
- S-curve matches the spec exactly and is perfectly balanced (`test_regions.py`).
- Full **D1** (96) postseason drives to completion: rounds 32 (play-in) → 32 → 16
  → 8 → 4 → 2 → 1; the four semifinalists come from four distinct regions.
- Full **D2** (64) postseason: 32 → 16 → 8 → 4 → 2 → 1; four distinct-region
  semifinalists.
- `test_bracketing` / `test_season` / `test_ita` (17) green.

## Gotchas for the next agent
- Region membership for labels (`web/state._region_map` via
  `regions.region_index_of`) and bracket placement BOTH derive from the same
  Committee-Seed-Score order, so labels are truthful. If you re-seed by a different
  metric on one side, the chips will lie about the bracket halves.
- `MAIN_DRAW_ORDER = [0,3,1,2]` is what makes region champs meet correctly; the
  play-in is region-major in `bpos` (region r, game g → r*8+g) so winners come back
  grouped by region for the main draw — don't reorder those without updating both.
- Past seasons drawn under the old flat structure still render; their region chips
  are derived cosmetically from the seed list and may not line up with the old
  bracket halves. New seasons are genuinely regional.
