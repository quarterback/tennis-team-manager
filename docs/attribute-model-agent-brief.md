# Brief: implementing the rich player-attribute model

For the agent that will build out the full `PlayerAttributes` model. Decision
already made: **rich model + derived drivers** — the ~50 attributes are the
persistent player model; the match engine keeps reading a *small derived set*,
so the engine isn't rewritten. And **hardcourt under conditions (indoor /
outdoor / wind / heat / crowd), NOT clay/grass surfaces.**

This repo already has a working sim. Your job is **additive/refactor without
breaking it.** Read this whole file first, then the files named below.

## The model to implement
The user's spec (serve/return, groundstrokes, point construction, net/doubles,
movement/physical, mental, **conditions not surfaces**, team/program fit) plus:
- derived shots as computed properties, not stored: `drop_shot`, `lob`,
  `passing_shot`, `slice`.
- non-numeric traits: `handedness`, `backhand_style`, `play_style`,
  `temperament`.

## Hard constraints — DO NOT BREAK THESE INTERFACES
Many modules consume players through a few methods. Keep them working (same
names, same return types) or update every caller:

- `engine/state.py`: `Player` has 9 driver attributes in `ATTRS`
  (`serve_power, serve_placement, return_game, forehand, backhand, movement,
  stamina, mental, consistency`), each a float in **[0,1]**. `engine/rally.py`
  reads these to drive serve/rally probabilities, and the pressure/clutch model
  reads `mental`. **Keep `engine.Player` as the engine's input** and **derive
  its 9 fields from the rich attributes** (e.g. `serve_power ← f(first_serve_power,
  second_serve_quality)`, `return_game ← f(return_quality, return_aggression)`,
  `mental ← f(composure, focus, clutch, resilience, competitiveness)`,
  `movement ← f(footwork, speed, agility)`, `consistency ← groundstroke_consistency`,
  …). This is the "derived drivers" decision.
- `app/development.py` `Prospect` — these are used across `app/ncaa.py`,
  `app/season.py`, `app/juniors.py`, `app/web/*`, `app/league.py`. **Preserve:**
  - `engine_player() -> engine.Player` (derive the 9 drivers here)
  - `current_overall() -> int`, `str_value() -> float`, `project(years) -> int`
  - `develop_year()`  (now develops the rich attributes; overall/STR follow)
  - `scouting_report(source) -> int`, and fields `interest_rate, tier,
    tier_mult, fog, consensus_seed, committed, pro, hometown, region, domestic,
    grad_year, recruit_rank, recruit_tier, recruit_stars, pid, class_year`
  - module fn `overall_to_str(g)` and band `STR_MIN, STR_MAX = 31.0, 57.0`
- `app/str_rating.py`: STR is on the **31–57 band**; it's results-based and
  independent of attributes — leave it alone, just keep `str_value()`/STR in band.

If you keep `current`/`potential` as per-attribute dicts but over the rich
attribute set, `current_overall()` becomes a weighted sum over the rich attrs
(define weights that sum to 1); `engine_player()` derives the 9 drivers from
them. That's the cleanest path.

## Determinism — CRITICAL
- **Never use Python `hash()` for seeds** — it's salted per process
  (`PYTHONHASHSEED`) and breaks cross-run determinism. Use `random.Random(seed)`
  with **string seeds**, or `hashlib.blake2s`. (`app/development.make_pid` and
  `app/ncaa._roster_seed` already do this — follow that pattern.)
- All player generation must be reproducible from a seed. Existing generators:
  `engine.random_player`, `app/development.generate_prospect`,
  `app/ncaa.build_roster`, `app/juniors.generate_class`.

## Conditions (not surfaces)
- Add a lightweight **match context** (indoor/outdoor, wind, heat, crowd) and
  thread it into the engine where the clutch/serve/rally tables are computed
  (`engine/match.py` sets `state.pressure`; `engine/rally.py` reads attributes).
  Condition attributes (`indoor_comfort, outdoor_comfort, wind_tolerance,
  heat_tolerance, crowd_pressure`) modulate serve-in %, error rates, and the
  pressure term. Default context = outdoor, calm — so existing behavior/tests
  barely move unless a context is supplied.
- Dual/season can pick a context (e.g. indoor for late-season/championships).
  Keep it optional with sane defaults so `simulate_match`/`simulate_dual`
  signatures stay backward-compatible (new keyword arg, defaulted).

## Scale guidance
- The current dev model uses a **20–80 grade** scale (`GRADE_MIN/GRADE_MAX`) and
  maps to engine [0,1] via `grade_to_unit`. Keep that scale for the rich attrs
  so `overall_to_str`, scouting fog, and the STR band keep working unchanged.

## Tests to keep green (run `pytest` — currently ~40 pass)
- `tests/test_engine.py` (determinism, scoring invariants, clutch),
  `tests/test_development.py`, `tests/test_str_rating.py`,
  `tests/test_season.py`, `tests/test_juniors.py`, plus the roster/league/web
  tests added with the two new features. Update tests that assert specific
  attribute lists; do NOT weaken determinism/scoring invariants.

## Files to read
`engine/state.py`, `engine/rally.py`, `engine/match.py`, `app/development.py`,
`app/str_rating.py`, `app/ncaa.py`, `app/season.py`, `app/juniors.py`, and the
existing tests. Mirror the house style (dataclasses, single `random.Random`,
heavy docstrings explaining the "why").

## Suggested order
1. Define the rich `PlayerAttributes` (dataclass) + traits + derived-shot
   properties, on the 20–80 scale, with a `derive_drivers()` → the 9 engine
   fields.
2. Refactor `Prospect` to hold the rich attrs (current/potential) while
   preserving every method/field above.
3. Add the conditions context to the engine (defaulted).
4. Update generators to populate rich attrs deterministically.
5. Fix/extend tests; keep determinism + scoring invariants.
