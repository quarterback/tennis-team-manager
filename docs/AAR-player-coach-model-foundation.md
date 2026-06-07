# AAR - Player and Coach Model Foundation

## Segment Summary

This segment built the first real data-model layer for career/recruiting mode. The goal was to avoid jumping straight into season UI before the sim had meaningful people underneath it: players with rich tennis profiles, admissions-only academics, and coaches with their own recruiting/development identities.

The implementation stayed additive. The match engine still consumes the same compact `engine.Player` shape and the same nine core drivers, while richer career-mode data now translates into those drivers.

## Player Model Decisions

### Rich Attributes, Derived Drivers

Added `app/player_attributes.py` with a broad 20-80 attribute model covering:

- Serve and return
- Groundstrokes
- Point construction
- Net and doubles tools
- Movement and physical traits
- Mental traits
- Hardcourt conditions
- Team/program fit

The engine still reads only:

- `serve_power`
- `serve_placement`
- `return_game`
- `forehand`
- `backhand`
- `movement`
- `stamina`
- `mental`
- `consistency`

Those are derived from the rich model through `PlayerAttributes.derive_drivers()`.

### No Surfaces, Only Conditions

Kept the model hardcourt-based. Instead of clay/grass ratings, players now have condition traits:

- `indoor_comfort`
- `outdoor_comfort`
- `wind_tolerance`
- `heat_tolerance`
- `crowd_pressure`

`engine.MatchContext` threads those conditions into full and fast match simulation with default neutral outdoor behavior.

### Academic Rating

Added `academic_rating` to `Prospect` as an admissions-only 59-99 index. This is intentionally not an intelligence number and does not affect match play. Its purpose is to support future admissions gates and academic-school recruiting logic.

## Coach Model Decisions

Added `app/coaches.py` as a separate domain model.

### Core Coach Attributes

Coaches use 20-80 ratings for skills such as:

- `teaching_skill`
- `charisma`
- `match_tactics`
- `lineup_management`
- `training_design`
- `fitness_program`
- `mental_coaching`
- `talent_evaluation`
- `academic_support`
- `program_builder`

### Recruiting Skill Categories

Recruiting is its own nested skill model, including:

- `salesmanship`
- `relationship_building`
- `loyalty`
- `player_development_pitch`
- `talent_projection`
- `academic_pitch`
- `domestic_scouting`
- `international_scouting`
- `persistence`
- `trustworthiness`

This gives recruiting more texture than one generic number.

### Pipelines

Coaches can have formal pipelines by region and country. Country pipelines override broader region pipelines. These represent actual access networks and should feed future recruiting odds.

### Origin Affinity Is Separate

Coach origin is not a pipeline. Coaches now have:

- `home_country`
- `home_region`

Shared country/region creates `origin_affinity(prospect)`, a separate favorability nudge for a recruit deciding between offers. It is deliberately not included in `pipeline_grade()`.

### Archetypes

Coaches now have archetypes:

- `coaching_lifer`
- `former_pro`
- `recruiting_closer`
- `development_guru`
- `tactician`

Archetypes lightly shape generated attributes and provide a small recruiting-fit flavor.

## Determinism / Stability

- Coach generation uses stable seeded RNG.
- `coach_for_program()` creates repeatable placeholder coaches by school and season seed.
- Replaced a previous Python `hash()`-based roster seed in `app/ncaa.py` with `blake2s` for cross-run determinism.

## Tests / Verification

Added or updated tests for:

- Rich player attributes deriving valid engine drivers
- STR staying on the 31-57 band
- Academic rating staying on the 59-99 admissions band
- Academic rating not affecting match ability
- Match context determinism
- Coach scores and recruiting fit
- Formal pipelines vs origin affinity
- Coach source preference: high school, international, blend
- Coach archetypes
- Deterministic generated coaches

Local verification performed:

- `py_compile` on touched files
- full repo `compileall`
- smoke tests for player generation, academic rating, match context, dual context, coach pipelines, source preferences, origin affinity, archetypes, and deterministic coach generation

Full `pytest` was not available in the local runtime because the downloaded target install resolved `pytest` as a namespace package without the normal callable entry point.

## Next Recommended Work

1. Add a program admissions profile, especially for Ivy/top-D3/high-academic schools.
2. Build the recruit decision model that combines school prestige, playing time, scholarship, admissions fit, coach recruiting fit, origin affinity, and pipelines.
3. Add coach persistence to career saves instead of relying on generated placeholder coaches.
4. Surface coach archetype, origin, pipelines, and recruiting style in the web UI.
5. Connect coach `development_score` to year-over-year player growth once rosters become persistent.
