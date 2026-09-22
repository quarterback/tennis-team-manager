# AAR — the JHSAA Program Coefficient and results-driven tiers

**Owner report (2026-09):** the talent tiers "don't really correspond with where
strength is in my save"; they should be "managed in bulk according to relatively
recent results or my own preferences." The rolled defaults were drawn at random by
roll weight and never looked at a season.

The owner then wrote the metric: a UEFA-coefficient-style longitudinal score,
per program per gender, **ranked within a classification only**, built from
road-to-state and State-bracket results and nothing else.

## The metric (`app/jhsaa_coefficient.py`)

- **Season total** = Σ road-round WINS by phase (Areas 0.10 · Sectionals 0.25 ·
  Wards 0.25 · Regionals 1 · Zonals 2 · Epiregional 1 · Super Regionals 0.5 ·
  Semi-State 0.5 · Divisionals 1 · Semi-Conference 0.5 · Conference 1 · Special
  Challengers 2 · State Specials 0.5 · Metastate 1) + ONE State-finish lookup
  (champion 50 · runner-up 40 · semifinalist 20 · quarterfinalist 12 · octofinalist 8
  · any other State entry 2 · Parastate 1) + a flat TOC bonus of 4.
- ‼️ **THE ROAD ACCUMULATES, AND MUST NOT IMITATE DEPTH AT STATE (owner rule
  2026-09).** The first schedule priced every rung at 1, 2 or 3 and this document
  described the consequence as a property — *"round wins sum regardless of path, so
  a recovery-ladder run banks more road points than a clean Zonal title"*. It was a
  defect. Measured on the owner's 2090 export: **4.5% of ordered pairs (girls),
  5.1% (boys) had the program with the SHALLOWER State run outscoring the deeper
  one**, and the deepest road haul banked before State was **11** against a
  first-round exit's 4. Owner: the prices "ought to be at levels of significance and
  then cumulative rather than aggregating as if each round is somehow equal prior to
  state." Re-graded as above, and with the top widened below:
  **zero inversions in either gender** and a road ceiling of **4**.
  Recovery rungs are now priced BELOW the
  round they are a second chance at, which is the correction in one line.
- ‼️ **AND THE TOP HAD TO MOVE WITH IT.** 20 · 22 · 30 meant reaching the FINAL beat
  losing the semifinal by 2 while the semifinal beat the quarters by 8 — the schedule
  stopped discriminating exactly where the association's season is decided, and that
  residual flatness is what the road could still invert (36 pairs survived the road
  re-grade alone; widening the top took it to 0). Now 20 · 40 · 50. ‼️ The gaps do
  NOT widen monotonically (entry→octo 6, octo→quarter 4); the guarantee is
  `FINAL − SEMI > SEMI − QUARTER`, and a test asserting monotone gaps was written
  first and was simply false.
- ‼️ **THE ROAD BOUND IS A LEGAL PATH, never `sum(road_points().values())`.** The
  ladder is a route — Super Regionals takes Regional LOSERS, the Conference takes
  Semi-State losers — so no program can bank both halves and the naive sum (11.6) is
  a number nobody reaches. The longest chain one program can assemble is 4.10:
  the local rungs, a Regionals loss into the full recovery run, and the Metastate on
  a low seed. A test asserting the naive sum was written first and failed, correctly.
- ‼️ **A RUNG WITH NO PRICE SCORES NOTHING AND READS LIKE A PROGRAM THAT NEVER
  PLAYED IT.** The Metastate did exactly that on arrival: not a road unit, and its
  losers are deliberately absent from the State draw's field, so neither half of the
  scorer could see them. It needed its archive key adding to `_ROAD_KEYS` as well as
  a price — a table entry the walk never visits is not a price.
- **Coefficient** = Σ over the trailing nine seasons of season total × weight:
  ×1.0 for the newest three, ×0.6 for the next three, ×0.3 for the last three.
- **Ranked within the program's CURRENT `group`**, with its whole history — a
  reclassification never fragments or resets it. No cross-class board exists.
- **Bootstrap:** fewer than 3 archived seasons in the WHOLE source data → seeded at
  the exact Q1 of the established programs' coefficients in its current class.
- **Trend** = this coefficient minus the same program's coefficient as of the
  previous archived season.

## How it is computed

- `season_points(arc)` is ONE pass over ONE archived season crediting every
  program it names (the title board's idiom), pure over the archive dict, so the
  arithmetic is pinned by hand-built seasons in `tests/test_jhsaa_coefficient.py`.
  Road wins are priced by the round's ARCHIVED NAME through `jhsaa`'s own
  constants (`jhsaa_title_stages`' rule), so a renamed round moves its price
  rather than silently scoring nothing. A game with no opponent is a materialised
  bye, not a win. The State finish reads `world.jhsaa_state_result`'s `place`
  (teams alive), never a label string; a Parastate exit is the named round.
- Per-season points are memoised per `(world, year, gender)` — an archived season
  is immutable — and the ranked result per `(world, gender, newest year, play-up
  version)`, since the class a program ranks IN is today's. Both cleared by
  `world.reset()`.

## Surfaces

- **`/jhsaa/coefficient`**, a fourth entry on the Rankings sub-rail, class-scoped
  by the rail: rank, coefficient, trend, seasons of history, and the nine window
  seasons' points with their weights.
- **The explorer's Suggested tier** (`jhsaa.suggested_bands`): the bridge from a
  class-scoped, per-gender ranking to an association-wide per-school tier is the
  program's PERCENTILE within its class (class-blind by construction), averaged
  over the genders it sponsors, then dealt onto the non-volatile tiers by ROLL
  WEIGHT so the suggested distribution is what the tier table says. Volatile
  tiers are never suggested. A "suggestion differs" facet and a "each program's
  suggested tier" choice under Set tier make the review-and-apply loop the
  explorer's ordinary selection gesture.
- A class with NO established program (a save younger than three seasons) yields
  no suggestion: every row there sits at one seeded value ordered by name, which
  says nothing.
- **The research export carries it** (`jhsaa_coefficient.csv` in every JHSAA
  bundle, `research_export.build_jhsaa`): one row per program per
  championship_group AS OF the export's season, with rank, coefficient, trend,
  this season's points, seasons of history, the bootstrap flag, the window and a
  `[world_year, points, weight]` breakdown. It reads the same memo the page does
  (a fold, never a resimulation) and keys `program_id` on the roster identity so
  a renamed program is one row across its history. The export's `year` is the
  SEASON year and is mapped back to the archive's world-year exactly as the
  season loader does (`year - BASE_YEAR - 1`) before it becomes `as_of` — pass
  the season year straight through and the window silently ends one world-year
  short of nothing, since no archive sits at 2082. The manifest's `domain_rules`
  sentence DERIVES every price from the module's constants; a retyped price list
  is the committee sentence's mistake again. Two review findings shaped it:
  the table is keyed on the ARCHIVE PATH (`injected`), never on "a world
  exists" — an injected season beside a live save would otherwise package
  another archive's standing under that season's manifest; and it emits ONLY
  programs with a `programs.csv` row, re-ranked within the group among them
  (the `percentiles()` rule), because `ranked()` keeps a program that stopped
  sponsoring the gender and its id would have no entity row to join. Pinned
  through the archive path in `tests/test_jhsaa_toc.py`.
