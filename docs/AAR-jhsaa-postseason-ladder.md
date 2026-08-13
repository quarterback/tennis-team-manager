# AAR — the JHSAA postseason: Sectionals → Wards → Regionals → Zonals → wild cards → State

**Date:** 2026-08-13
**Status:** Landed. Owner spec (playoff-run research; other states' formats).
**Scope:** `app/jhsaa.py` (`POSTSEASON`, `PROTECTED`/`WARD_FIELD`/`WILDCARDS`,
`ladder_scale`, `sectional_field`, `run_sectional`, `run_rounds` (new),
`run_state`, `rating_duals(prestate=)`, `power_index(prestate=)`,
`FLIGHT_WEIGHTS` +D3/D4, `run_season`), `app/world.py` (`_finish_label` /
`_round_label`, `jhsaa_state_rounds` round_names, `jhsaa_postseason_result`,
`run_jhsaa`, `_season_row`), `app/web/state.py` (`jhsaa_school_view`),
`templates/jhsaa_school.html`, `tests/test_jhsaa_ladder.py`.

## The owner's spec

Three separate mechanisms, deliberately decoupled — the design error to avoid
here is cascading any one of their numbers through the others:

**1. Sectionals — broad access and field reduction.** Every non-protected team
enters. The shape is flexible per classification (byes and play-in rounds as
needed); the only fixed requirement is the output: exactly 32 teams for Wards.
48 entrants → 16 byes, 16 matches, 32 out. 57 → 7 byes, 25 matches, 32 out.
83 (7A boys, measured) → two rounds, 83 → 42 → 32.

**2. The pre-state ladder — fixed for every classification and both genders:**

| Stage | Field | Result |
|---|---|---|
| Wards | 32 Sectional survivors | 16 Ward champions |
| Regionals | 16 Ward champions + 16 protected | 16 Regional champions |
| Zonals | 16 | 8 Zonal champions — automatic State qualifiers |

The protected 16 enter at Regionals: district champions first, then the best
remaining cutoff TOSS until the seats are filled. (This retired
`AUTO_PER_DISTRICT` and with it 7A's old top-two-per-district rule — a strong
district now earns extra protected seats through TOSS instead of every district
getting a flat multiplier.) Regionals+Zonals are two rounds of one seeded
32-draw — no reseeding between them, the association's standing rule.

**3. Wild cards — selected after Zonals, resizing nothing upstream.** TOSS is
recomputed over every completed pre-state match (`power_index(prestate=True)`);
the top 8 teams that did not win a Zonal join the 8 Zonal champions in a fresh
16-team State draw: R16 → QF → SF → Final. Only those rounds are formally the
State Tournament.

The pre-state rounds therefore do two jobs at once: direct qualification by
winning a Zonal, and résumé-building for the wild-card spots. A team can lose
its Zonal and still play into State on its full postseason body of work —
verified live: a protected team that lost at Zonals wild-carded into State and
finished Octofinalist.

## Numbers on the real association

Every classification fits the full-size spec — protected 16 + Sectional
entrants ≥ 32 holds even for the smallest (4A boys, 63 programs: 16 + 47).
Measured, boys, one seeded run:

| Group | Sectional entrants | Sectional shape | Ward | Regionals | Zonal champs | WC | State |
|---|---|---|---|---|---|---|---|
| 7A | 83 | 83 → 42 → 32 | 32 | 32 | 8 | 8 | 16 |
| 6A | 58 | 58 → 32 | 32 | 32 | 8 | 8 | 16 |
| 5A | 55 | 55 → 32 | 32 | 32 | 8 | 8 | 16 |
| 4A | 47 | 47 → 32 | 32 | 32 | 8 | 8 | 16 |
| 3A | 54 | 54 → 32 | 32 | 32 | 8 | 8 | 16 |
| 2A-1A | 65 | 65 → 33 → 32 | 32 | 32 | 8 | 8 | 16 |

Byes exist only in Sectionals; Wards through the Final is exact halving.
`ladder_scale` shrinks every number together (powers of two, same shape, shared
by both genders) for pools too small for the full size — the two-district test
fixture, not any real classification.

## Mechanics worth knowing

- **One phase per stage** (`POSTSEASON = ("sectional", "ward", "regional",
  "zonal", "state", "toc")`) — the archive is the only place stages can be told
  apart afterwards, and each new phase inherited the 1S/4D shape, strict
  best-nine lineup, and cutoff-TOSS exclusion for free by joining the tuple.
- **Two TOSS computations.** The cutoff TOSS (seeding, district tiebreak,
  protection) is the regular season only, unchanged. The post-Zonal recompute
  adds the completed pre-state stages. That required D3/D4 flight weights
  (postseason 1S/4D lines) in `jhsaa.FLIGHT_WEIGHTS` — same decay as the
  existing doubles column; the cutoff TOSS never reaches them.
- **Stage dicts carry their own `round_names`** — `jhsaa_state_rounds` reads
  them back instead of guessing from team counts, since Wards and Regionals
  both enter at 32. The State bracket stays count-banded (Octofinals /
  Quarterfinals / Semifinals / Championship), which also covers old
  single-bracket archives.
- **`jhsaa_postseason_result(grp, school)`** walks state → prestate → ward →
  sectional and names the stage a run ended at; ledger rows read "Sectionals" /
  "Wards" / "Regionals" / "Zonals" instead of a blank, plus a `wildcard` flag
  for State entrants who didn't win a Zonal.
- **Order inside `run_season`:** every group's ladder runs through Zonals
  BEFORE any group's wild cards are picked — the recompute is gender-wide (the
  results graph crosses classifications), so it can only run once all Zonals
  are done. Records still snapshot after the whole postseason (the 131/137
  invariant), now with four more stages in front of the old boundary.
- **`run_toc` unchanged** — six classification champions, and State still
  produces exactly one each.

## Verification

- 109 JHSAA tests pass: 79 pre-existing + 18 TOC + 12 rewritten ladder tests
  (fixed shape and proportionality, protected = champions + TOSS fill and skip
  exactly Sectionals+Wards, byes-free from Wards on, state field = Zonal
  champions ∪ wild cards, per-stage phases in `world_jhsaa_dual`, stage-named
  finishes, cutoff TOSS excludes all postseason, the wild-card recompute sees
  more duals than the cutoff, records cover every dual).
- Full-size run archived through the real world rung; every `/jhsaa*` page
  renders; school pages segment the card by stage (Sectionals / Wards /
  Regionals / Zonals / State Tournament / TOC) with per-stage opponent seeds.
