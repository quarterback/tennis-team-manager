# AAR — The Epiregional: State seeding and byes moved onto merit

Owner rule 2026-09. Branch `claude/state-seeding-bye-reform`.

## The fault

A Zonal title did two things: it qualified a team for State, and it placed that
team on one of the top eight seed lines, with whatever bye that line carried.
Qualification was earned on court. Placement was not — it depended on which Zonal
a team happened to be drawn into, and Zonals vary a lot in strength.

Measured on the 2068 export, all 24 classification-genders:

| | |
|---|---|
| worst-placed team in a State field carried seed 8 | 20 of 24 fields |
| class rank of those seed-8 teams | 19th–27th (up to 37th) |
| girls 8A rank-1 team's seed | 12 (did not win its Zonal) |
| girls 8A champion's seed | 31 |
| boys 7A (the best case) top-8 class ranks | 1, 2, 3, 5, 6, 7, 8, 9 |

## The rule now

1. **The Epiregional** (`jhsaa.run_epiregional`, phase `"epiregional"`, sits in
   `POSTSEASON` right after `"zonal"`). The eight Zonal champions of a class play
   one round among themselves, paired 1v8 / 2v7 / 3v6 / 4v5 on the seeding ATR
   *among those eight*. The higher seed hosts. Four win, four lose, **all eight stay
   in State** — this round decides placement only. Played straight after the
   Zonals and before the recovery rounds, so its duals are in the pre-State
   results graph the recovery fields and the final seeding are rated on.
2. **Bye lines** (`jhsaa.state_seed_order`). Lines 1-8 are the four Epiregional
   winners plus the best four of *everyone else* on the seeding ATR — an
   Epiregional loser included, so a season where the champions really are the
   eight best hands them all eight lines. The eight are ordered 1-8 on ATR among
   themselves: an Epiregional win guarantees a **top-eight** line, not a top-four
   one. Lines 9+ are everyone else on ATR, whatever their door in.
3. **The draw keeps its shape.** `run_state(..., champions=STATE_BYES)` is fed the
   ordered field; the bye budget and the expansion rule are untouched, so a 24
   still gives eight single byes, a 40 eight double byes through the Qualifiers
   Round, and a 32 no byes at all (placement only there).

## The seeding ATR (`jhsaa.seed_atr`, `SEED_ATR_TOSS_WEIGHT` 0.6 / `SEED_ATR_WIN_WEIGHT` 0.4)

A z-score blend **within one class-gender field** — never over the gender. Both
terms are standardised over the list handed in before they are weighted, so 0.6
means six-tenths of a TOSS standard deviation against four-tenths of a
win-percentage one. Deliberately a **second formula** beside the existing
`atr`/`ATR_TOSS_WEIGHT` (0.5, raw blend): that one ranks the Semi-Conference and
Conference pools and is archived on every standings row, and retuning it would
move the recovery ladder.

Why not TOSS alone: over 2065-2068, 9A picked the same four merit teams either
way; 8A disagreed every season, always in the same shape (TOSS rating a 22-11
above a 24-3). A bye should require having won matches.

## The units

Each Epiregional dual is a named unit off the NCAA tournament's cosmetic pool
(`regions.region_names`, fed a blake2s digest of gender/year/class/salt) — "Cascade
Epiregional". Labels only, rotating by year and class. They count on the Title
Board (`EPI`) and on a program's honours line like every other unit.

## Layers changed

- **Event** (`app/jhsaa.py`): `POSTSEASON`, `EPIREGIONAL_NAME`, `seed_atr`,
  `epiregional_names`, `run_epiregional`, `STATE_BYES`/`EPIREGIONAL_BYES`,
  `state_seed_order`; `run_season` plays the round after the Zonals and seeds
  State through `state_seed_order`.
- **Archive** (`app/jhsaa.py` → `app/world.py`): a new per-group key
  `epiregional` in `run_season`'s output and in the `world_jhsaa` summary
  (`.get` on read — older seasons carry no key). Its duals are ordinary
  `world_jhsaa_dual` rows at `phase='epiregional'`. `_JH_STAGE_KEYS`,
  `_unit_wins` and `jhsaa_title_stages` carry it.
- **Surface** (`app/web/state.py`, `templates/jhsaa_bracket.html`): the bracket
  page renders the round as **its own panel** above the Road to State folds, with
  the eight bye lines and how each was earned. Never a column of the tree: four
  duals producing four placements is not a halving, and `_bracket_canvas` links
  columns on exactly that halving (the JV qualifying round's lesson). The school
  page tags the dual `EPIREGIONAL` with its play-in seed.
- **Export** (`analytics/ptc_analytics/aggregate.py`): the road label.

## Tests

`tests/test_jhsaa_epiregional.py` runs the round and the seeding on real rosters
with an explicit eight-champion field at every field size (24/32/40): eight in,
four winners, all eight still in the field, bye totals 8/8/0, round sizes exactly
the current shapes, ATR standardised within the field, rematch guard,
determinism. `tests/test_jhsaa_ladder.py` covers the wiring on an archived
season (every class crowns eight, so the play-in path always runs there).

## Traps

- **`play_dual` credits the record.** A test that pre-computes an expected order
  must do so *before* playing the round, and a determinism check must copy the
  field: the second run on mutated records is a different input.
- **A rematch is impossible by construction** (two Zonal champions came from
  different Zonals and Regionals feed Zonals positionally), but the swap repair
  is kept so the rule is stated in code rather than assumed of the draw upstream.
- **All eight bye lines carry the same bye.** The prompt's "four single byes" for
  the merit teams in a 40 would break the halving; the owner's amendment is the
  status-quo shape.
