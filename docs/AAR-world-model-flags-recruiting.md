# AAR — International world model, flags & the recruiting board

**Date:** 2026-06-07
**Scope:** Port o27 baseball's player-identity *primitives* (countries,
hometowns, per-nation talent) into the tennis sim, surface them on the player
cards the way baseball/viperball do (flags + birthplace), and build out the
recruit profile into a real College List / Dreamsheet / Timeline board.

## Why
The name-generation engine had already been lifted from o27 (`generators/`),
but the rest of the international model hadn't: players carried a `country`
code that nothing displayed, roster players had **empty** hometowns, and
recruit "hometowns" were synthetic placeholders (`Springfield, JP`). The
recruit profile page was a stub. Baseball's primitives are richer and more
realistic, so we ported the data + math rather than reinventing, then dressed
it in the viperball card look.

## What shipped

### Data (generators/data/names/)
- **`hometowns.json`** — copied from o27 (89 nations' real city pools), plus
  CL/PE/RO/BG added for tennis coverage. Keyed by ISO 3166-1 alpha-2.
- **`nation_talent.json`** — NEW, tennis-shaped. Per-nation `investment`
  (elite-spike driver) + `grassroots` (average-lift driver), 0–100, default
  50/50 when a code is absent. Re-weighted for tennis reality (ESP/USA/FRA/ITA
  at the top), *not* baseball's cricket-conversion arc.
- **`regions.json`** — added the **`tennis_global`** preset: the developed
  tennis bloc carries ~88% of draws, with a deliberate **≥10% rest-of-world
  reserve** (measured 11.6%) so talent keeps emerging outside the majors.

### Engine (generators/)
- **`nation_talent.py`** — static (JSON-only) port of o27's model: `ratings`,
  `talent_shift`, `elite_probability`, `roll_elite`, `describe`. The live
  season-to-season DB drift store was intentionally dropped.
- **`flavor.py`** — `roll_hometown`, `roll_birthday`, `roll_secondary_country`
  (dual-citizen tag, ~4%), plus the `country_name` / `country_abbrev` /
  `flag_emoji` display map (ported from o27's `_COUNTRY_DISPLAY`).

### Wiring (app/)
- `development.generate_prospect` now applies the nation talent_shift + elite
  roll to ceilings and **rolls a hometown/birthday/secondary nationality** for
  every prospect — so roster players (build_roster, league refill) and recruits
  all carry wired identities.
- `juniors.generate_class` draws **real** city hometowns (`City, ST` domestic /
  `City, ABBR` international) and uses `tennis_global` (minus US) for the
  international board.
- `ncaa.build_roster`, `league._refill`, `web.sim.build_team` switched to the
  `tennis_global` preset.

### Recruiting subsystem (app/recruiting.py) — NEW
Deterministic-per-`pid` **College List** (offer + interest temperature +
StrikePrediction commit-% + Finalist/Top-School status), **Dreamsheet**, and
**Recruiting Timeline**. Board depth scales with the recruit's star rating
(blue-chips ~14 offers, 3-stars ~3).

### Display (app/web/)
- `formatters.py` — `flag` (emoji for real codes, `<img>` for custom art like
  ZR), `flags` (dual-citizen → **two flags**), `country_name`/`country_abbrev`,
  registered as Jinja filters.
- Recruit profile rebuilt in the viperball idiom: flag(s) + abbrev by the name,
  `Born City, ABBR`, StrikePrediction banner, College List / Dreamsheet /
  Timeline panels, and a marquee-attribute bar block. Flags added to the
  recruiting board, team roster, and player card too.

## The "talent emerges anywhere" guarantee
Two mechanisms, both verified by tests:
1. The `tennis_global` preset reserves 11.6% of draws for non-major regions.
2. Unlisted/minor nations default to neutral 50/50, which yields a **mid-band**
   elite probability (~0.55%, ~1 in 182) — not the floor — so a small nation
   still rolls the occasional gem and spans skill levels.

## Validation
- `pytest tests/` → **71 passed** (was 62; +9 in `tests/test_world_model.py`).
- New tests cover neutral-default talent, major lift/spike ordering, hometown +
  country display, the ≥3% dual-citizen rate, non-major-market emergence with a
  spread of stars, and the recruiting board's shape/determinism/empty-school
  fallback.
- Manually rendered an international recruit profile: College List, Dreamsheet,
  Timeline, StrikePrediction, Attributes, `Born`, Finalist all present; a
  dual-citizen recruit renders both flags.

## Follow-up: Serbian pool
The scraped `serbian` name buckets were polluted (team names like "Borussia"/
"Chicago", cities, and mixed-in Bosniak/Albanian names) and no region mapped to
`RS`, so Serbia — a tennis power well out of proportion to its size — never
generated. Replaced the three buckets with curated authentic Serbian lists
(70 male / 60 female firsts, 90 `-ić` surnames incl. Đoković/Janković/
Ivanović), added a `serbia` region (RS), an `RS` nation-talent row (74/54),
an `RS` hometown pool, the `RS → Serbia/SRB` display entry, and weighted
`serbia` at 0.03 in `tennis_global` (rest-of-world floor still 11.3%).

## Merge reconciliation with parallel season-mode work
A parallel branch landed on `main` (season mode, a dual-sim rewrite onto real
rosters, a teams-by-conference index, and a `generators/origins.py` that gave
roster players synthetic-placeholder hometowns + a **high school**). Reconciled:
- Kept **my** richer system as the source of truth for hometowns (real
  per-nation city pools + flags + nation talent) — dropped `pick_origin`'s
  synthetic hometown/region override in `ncaa.build_roster`.
- Kept **their** `high_school` field, but moved its generation into
  `flavor.roll_high_school` called from `generate_prospect`, so *every*
  prospect (recruits included, not just rosters) now gets a high school.
- Player page is now season-mode-driven (`info` dict): added flag(s),
  `Nationality`, `Born`, and `High School` to it; surfaced `high_school` +
  `secondary_country` through `seasonmode._pid_index`.
- Took their `sim.py` (the old `build_team` my preset edit touched is gone;
  squads now come from `build_squad`, which still flows through the
  `tennis_global` preset via `build_roster`).
- `generators/origins.py` is left in place but is now unused (superseded by
  `flavor.roll_hometown` + `roll_high_school`).

Post-merge: `pytest tests/` → **77 passed**; all web routes render (player card
shows flag + Nationality + Born + High School; recruit profile keeps College
List / Dreamsheet / Timeline).

## Not done (deliberately)
- No live nation-talent drift (static JSON only).
- US recruit `City, ST` pairs the drawn city with the drawn state
  cosmetically; they aren't geographically matched (same as the prior behavior,
  now with real city names).
