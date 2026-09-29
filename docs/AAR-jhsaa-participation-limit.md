# AAR — the JHSAA individual participation rule (rule 2101) and the early-participation seat cut

Owner spec 2026-09. Code: `app/jhsaa.py` (`PARTICIPATION_LIMIT`, `_use_date`,
`_within_limit`, `jv_available`, `EARLY_SEAT_RATE`, `early_seat_seasons`),
`app/world.py` (`_jh_busy`, `_jh_jv_dates`). Tests: `tests/test_jhsaa_participation.py`,
`tests/test_jhsaa_early_participation.py`.

## 1. Too many middle schoolers

Rule 2100 rostered EVERY seat of the next two freshman classes early, so about a
third of a 1A/2A/Group 3 roster was in 7th or 8th grade. Owner: the talent is fine,
the share is not. Decision: ~5% of the roster (0-2 per program), cut PER SEAT at the
same odds in both grades, era-gated.

- `EARLY_SEAT_RATE` (0.07): each seat of a gated cohort rolls once per early grade on
  its own rng stream; a 7th-grade hit is grandfathered into 8th (the existing rule),
  so 8th-graders outnumber 7th-graders by construction. Measured on the real
  association: ~1 early participant per gated roster.
- `early_seat_era()` (`jhsaa_early_seat_era`, in `ERA_SETTINGS`) gates on the SEASON:
  a season archived with whole cohorts rebuilds byte-identical, and a cohort that
  played 7th grade whole plays 8th grade whole.
- The cohort is still SIZED at its first early season (`cohort_horizon`) whether or not
  any seat comes — the size must not depend on the roll.

## 2. The participation rule

> A player may participate on no more than 24 regular-season competition dates across
> all JHSAA team levels combined. V1, V2, V3 and JV count toward the same limit. A
> player may represent only one team level on a competition date. Postseason
> competition does not count.

Measured on the 2100 export: ~27% of early participants over 16 regular-season duals,
maximum 34; a player took 21 V1 + 21 JV duals because nothing joined the ledgers.

- ONE shared budget per player: `TeamSeason.dates`. Every level's play function
  charges it (`_use_date`) and every level's staffing reads it (`_lineup`,
  `_squad_v1_lineup`, `squad_pool`, `jv_available`). A spent player's regular season
  is over; the postseason neither charges nor excludes.
- A competition DATE, not a dual: a showcase day's duals fold to one date via
  `date_key` (pod one Saturday, tiered two days; the JV pod likewise).
- Resting toward the limit: `dates_planned` (league + allowance + one showcase) is set
  at the top of `play_regular_season`; against a WEAKER side `_within_limit` rests a
  starter whose remaining budget is short of the remaining slate, never below the
  lineup. Showcases and squad V1 sides skip only spent players.
- The JV season is staffed after varsity from `jv_available`, so a varsity call-up
  costs a JV date — the exact mechanism the rule exists for.
- One level per date is a CALENDAR guarantee (the sim has no clock): the JV date pass
  keeps a program's JV dates off its varsity and squad dates, and a squad shares its
  school's varsity cursor.
- `PARTICIPATION_ENABLED` is the kill switch.
