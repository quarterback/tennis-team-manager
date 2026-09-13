# AAR — the JHSAA Program Coefficient and results-driven tiers

**Owner report (2026-09):** the talent tiers "don't really correspond with where
strength is in my save"; they should be "managed in bulk according to relatively
recent results or my own preferences." The rolled defaults were drawn at random by
roll weight and never looked at a season.

The owner then wrote the metric: a UEFA-coefficient-style longitudinal score,
per program per gender, **ranked within a classification only**, built from
road-to-state and State-bracket results and nothing else.

## The metric (`app/jhsaa_coefficient.py`)

- **Season total** = Σ road-round WINS by phase (Sectionals 1 · Wards 1 ·
  Regionals 2 · Zonals 2 · Epiregional 1 · Super Regionals 2 · Semi-State 2 ·
  Divisionals 2 · Semi-Conference 2 · Conference 2 · Special Challengers 3 · State
  Specials 3) + ONE State-finish lookup (champion 30 · runner-up 22 · semifinalist 20
  · quarterfinalist 12 · octofinalist 6 · any other State entry 4 · Parastate 0) +
  a flat TOC bonus of 4. Round wins sum regardless of path, so a recovery-ladder
  run banks more road points than a clean Zonal title.
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
