# AAR — JHSAA split squads (rule 2097)

## What it is

From the 2097 season a deep, top-tier JHSAA program may split its JV into a
**V2** and a **V3** squad. The squads take **non-district** dates against other
programs' varsity (V1) teams, on the model of Cherry Creek's multi-varsity
program. Squads are JV in every other sense. Their players keep the JV season,
the JV individual events and the JV Team State Tournament, and nothing a squad
does reaches a player's varsity record, the ladder, an award or a rating.

## Who fields squads

Both gates must pass (`jhsaa.squad_eligible`). The decision is made once per
season, before the first dual (`field_squads`):

1. **Talent tier.** The program's current tier is in `SQUAD_TIERS`
   (`power`, `elite`, `dynasty`). It is resolved through `program_band`, which
   keys on the stable program ident (`School.ident`), never the display name.
   The volatile tiers never qualify.
2. **Depth.** A program needs this many *healthy* players below the varsity
   eleven (`SQUAD_DEPTH`):
   - V2: 11
   - V3: 18

   V2 dresses JV ranks 1-11 and V3 dresses ranks 12-18, so a program with a V3
   always has a V2.

Programs that fail either gate keep the existing JV model untouched.

## Formats and lineups

- V2 plays **3S/4D** and V3 plays **3S/2D** (`SQUAD_FORMATS`). Both have an odd
  number of flights, so a squad dual can never be drawn.
- The V1 opponent plays the squad's format. Its lineup is the healthy top of its
  live ladder with captains seated, and it gets no rest or rotation relief
  (`_squad_v1_lineup` bypasses `_rest_count` and the bench rotation).
- Every squad dual is recorded at `phase="regular"`, whichever non-district window
  it falls in.
- Ordinary JV duals keep their elastic formats.

## Scheduling

Squads join the pool of `_nondistrict_pairs` in all three non-district windows
(early, mid-season, late tune-up). In each window a squad carries its school's
own allowance, and in the late window that is the school's quota minus the
squad's duals so far. The pairing rules:

- A squad never plays its own school, and never a V1 from its OWN class (league
  mate or not).
- A squad may play another program's squad. That dual is JV on both sides: no
  credit, no rating, at the smaller squad's format (3S/2D if either is a V3).
- There is no classification gate otherwise, for anyone (owner rule 2097). The
  old ±1 gate on non-district pairing is gone association-wide.

On the calendar, a squad dual is dated once, on the V1's varsity calendar.
`jh_match_key` names the squad side `School#V2`, which gives each squad its own
date cursor, separate from its school's varsity cursor.

## Where results live

- **V1 side.** The dual is an ordinary varsity non-district result: `_credit`,
  W-L, points and an injury roll. The schedule row carries `opp_squad`. The
  schedule shows the school name as it always has, plus a V2 or V3 chip. The
  word "varsity" is never added.
- **Squad side.** Results go on a `SquadTeam`, which is its own type (like
  `JVTeam`) and so has nowhere to put `records` or `matches`. After the JV season
  they are folded onto the school's JV team (`_fold_squads`):
  - The squad rows appear on the JV schedule tab with a V2 or V3 tag, the way JV
    rows are tagged, and count in the aggregate JV record (`jhsaa_jv_record`).
  - Squad W-L is kept on `squad_wins`, `squad_losses` and `squad_ties`, never on
    `JVTeam.wins` or `losses`. Those two fields are what the JV Regions and JV
    State draws seed on, so squad results stay out of JV seeding.
  - Squad duals never count toward `JV_DUAL_CAP`.

## Ratings

- **TOSS** (`rating.compute_ratings`): a squad dual carries `squad_side` and
  `squad_factor`. Only the V1 side is rated. Its opponent terms (the APR's SOS,
  the loss forgiveness, and the FQI/oGS multiplier) read the squad's school's V1
  value × 0.61 for a V2 opponent and × 0.39 for a V3 opponent. Every other dual
  has a factor of 1.0 and runs the old arithmetic unchanged.
- **OOWP** (`district_oowp`) applies the same discount.
- **ATR** and the seeding score are built on TOSS, so they inherit the discount.
- The squad's own record is never read by any rating.
- **The nine computer ratings** (`jhsaa_ratings.dual_rows`) exclude squad duals
  entirely.

## Archive and exports

- `world_jhsaa_dual` gains two columns, `squad` and `opp_squad`, both
  `TEXT DEFAULT ''`, with a migration. Both are `''` on every other row.
- **Both rows keep the box score.** One row is varsity (the V1) and the other is
  JV (the squad), so they sit at different levels and the home-row counterpart
  lookup cannot bridge them.
- `jh_match_key` returns level `"sq"` for both rows of a squad dual. It is still a
  5-tuple.
- **Folds that credit both sides.** Several whole-season folds read `home=1` rows
  and credit both teams off that one row: underplayed, record context, career by
  school, career wins, and exposure. For squad duals they now also read the V1
  row when the squad hosted, and they credit only the V1 (`_JH_V1_ROWS` and
  `_jh_credit_sides`).
- **Folds that describe V1-vs-V1 play** exclude squad rows (`_JH_NO_SQUAD`):
  scoreline realism, gap bands, flight efficiency, head-to-head and prior
  meetings, and the Coach of the Year expectation fit.
- **Research export.** Each squad dual is written once, off the V1 row, with a
  `squad` column. Its home/away program ids follow the actual venue.
- **Analytics sidecar.** The Clinch Report sidecar drops rows with
  `squad != ''`, the same way it drops JV.

## Verification

- **Pre-2097 identity.** I ran a girls 5A+4A 2096 regular season plus JV season
  on `main` and on this branch, with `PYTHONHASHSEED` pinned, and hashed every
  schedule, record, JV record and TOSS component. The two digests are identical.
  The hash seed has to be pinned because the JV slate already seeds off Python's
  salted `hash()`, so two unpinned runs never match, on any branch.
  `test_before_2097_the_season_is_identical_whoever_would_qualify` pins the gate
  itself: it forces every program into a squad tier at 2096 and asserts nothing
  changes.
- **Tests.** `tests/test_jhsaa_split_squads.py` covers both gates, the year gate,
  the formats, no relief for the V1, the pairing rules (league mates allowed,
  big-program squads may drop below the ±1 gate, others may not), the discount values
  in TOSS and OOWP, bit-identity at factor 1.0, the exclusion from the computer
  ratings, the exclusion from JV seeding, and the archive columns, migration,
  match key, calendar, schedule rows and head-to-head.

## Smoke run — girls 9A-5A, 2097 (regular season + JV season)

| | |
|---|---|
| Programs | 396 |
| Tier-eligible (power/elite/dynasty) | 38 |
| Programs fielding V2 | 31 |
| Programs fielding V3 | 14 (all 14 also field V2; 17 are V2-only) |
| Squad duals vs V1 | 220 (V2 151, V3 69); every squad plays 6 non-district duals in all |
| Squad-vs-squad duals | 25 (JV both sides) |
| Share of V1 non-district **dates** (V1 schedule rows) | 9.5% (220 of 2,312) |
| Share of unique V1 non-district **duals** | 17.4% (220 of 1,266) |
| V1 programs that met a squad | 177 (max 4 each) |
| Squad wins vs V1 | 95 of 220 (V2 76/151 = 50%, V3 19/69 = 28%) |
| JV invitationals lost to the 16-dual cap | none: all 31 squad programs still reached 16 JV duals |

For comparison, the ungated version put squads in 118 of 145 programs and took
about 70% of V1 non-district dates. The two gates cut that to 31 of 396 programs
and about 10% of dates.

## Notes

- **Players can come up twice.** A V1 may meet both a school's squad and that
  school's own V1 in the same season. The squad dual has its own match key, so
  the two duals never collide on the calendar or in the archive.
- **Squad programs still play a full JV slate.** The squad players are drawn
  from the same pool as the JV, and the program's ordinary JV schedule is
  unchanged. That is the "full JV ecosystem access" the rule asks for.
