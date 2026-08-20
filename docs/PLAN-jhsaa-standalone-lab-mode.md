# PLAN — Standalone JHSAA-only mode: full-fidelity seasons, decoupled from college/pro

Status: planned, not yet implemented. Owner intends to build this next.

## Context

The owner wants to run full JHSAA (Jefferson high-school) seasons for offline data
analysis without being forced to build/advance the college and pro sims to get them.
Today, a rich JHSAA season only exists as a side effect of a full college "world":
`world.run_jhsaa()` runs once, automatically, at week 0 of `world.get_or_create()` —
which also unconditionally builds the entire D1-D4 college universe (men's and
women's, all divisions) first, even though nothing about JHSAA generation or
archival needs it. Getting a second independent JHSAA season today means creating
an entire second college world just to throw away.

Two requirements were established during scoping, both must hold with **zero loss
of fidelity** versus what `/jhsaa` already shows:

1. **Browsable at full fidelity** — the exact same districts, brackets, honors,
   rankings, and player cards the live `/jhsaa` section already renders. Not a new,
   simplified page.
2. **Importable into an external analytics tool** — CSV/JSON output usable in
   pandas/Excel/etc., with the same richness as `/research/export` already produces.

Investigation found both are achievable with **no changes to the display layer at
all** (`app/web/state.py`'s JHSAA view functions and every `jhsaa_*.html` template
are already correct and already seed-parametric), and the CSV/JSON export path can
be satisfied with **zero risk to the real save** — no database, world, or Flask
process involved at all for that half. The only real design work is a small,
targeted addition to world creation so a legitimate JHSAA-only "world" can exist
cheaply, without dragging in an unused college universe.

## Key facts established

- `jhsaa.run_season(gender, year, *, seed=0, salt="")` (`app/jhsaa.py:3948`) is
  already fully decoupled — a pure function of scalars plus static
  `data/jhsaa/schools.json`, already including the TOC internally
  (`out["toc"] = run_toc(...)`, `app/jhsaa.py:4086`).
- `world.run_jhsaa(seed, world)` (`app/world.py:3549`) only needs `world["id"]` and
  `world["year"]` (plus the salt) to archive a full season into `world_jhsaa` /
  `world_jhsaa_dual`. It never touches `world_roster` or any college table.
- The entire browsable JHSAA UI (`/jhsaa`, districts, brackets, honors, player
  cards) reads through `app/web/state.py` functions that already take `seed` as an
  explicit parameter (`jhsaa_view`, `jhsaa_scope_view`, `jhsaa_player_view`, etc.,
  `app/web/state.py` ~3982-4727) — only the Flask *routes* in `app/web/server.py`
  hardcode `DEFAULT_SEED`.
- The cost we want to skip is entirely contained in one branch:
  `world.get_or_create` (`app/world.py:379-411`) — when no row exists for a seed,
  it inserts the row, then unconditionally builds all 8 `(division, gender)`
  college universes via `pmap(_build_universe, tasks, ...)` before returning. Once
  a row exists, every later call takes the cheap "row exists" fast path.
- **The export half needs none of the above.** `research_export.export_zip("jhsaa",
  year=.., gender=.., season=<dict>)` (`app/research_export.py:377`,
  `build_jhsaa` at `:99`) accepts an **injectable `season=` dict** shaped exactly
  like `jhsaa.run_season()`'s return value, bypassing the archive entirely. So:
  ```python
  season = jhsaa.run_season(gender, year, seed=seed, salt=salt)
  zip_bytes = research_export.export_zip("jhsaa", year=year, gender=gender, season=season)
  ```
  produces the *identical* CSV/JSON bundle `/research/export` gives today
  (`programs.csv`, `players.csv`, `duals.csv`, `lines.csv`, `line_players.csv`,
  `jhsaa_standings.csv`, `jhsaa_championships.json`, `jhsaa_awards.json`,
  `manifest.json`) with **no database, no world, no Flask process** — pure
  in-memory Python. Zero risk to the real save.
- **The one genuinely dangerous shared piece of state, if a lab world ever shared
  the real save's database:** `gtt_seasonmode._active_world_seed`
  (`app/gtt_seasonmode.py:828-846`) resolves "the active world" via
  `SELECT seed FROM world ORDER BY id ASC LIMIT 1` — the oldest row, completely
  unfiltered. A college-less row becoming that oldest row would silently corrupt
  GTT/cup rostering. This is avoided entirely by never sharing the database.
- Everything background/health/boot-related (`_prime_world` before_request hook,
  `warm_caches`, `/api/ready`) is scoped to `DEFAULT_SEED` (2026) only — invisible
  to anything using a different seed in a different database file.

## Recommended approach: separate scratch database, CLI-driven, no shared-DB risk

Reuse the exact pattern the test suite and calibration scripts already use in this
codebase (per `CLAUDE.md`'s "THE SUITE MUST NOT SHARE A DATABASE WITH THE APP"
section): point `TENNIS_DB_PATH` at a disposable file, fully isolated from the
real save. This sidesteps every risk around `_active_world_seed`, `reset()`
scoping, and "ONE WORLD PER SAVE" corruption — a lab world is never in the same
database as the real save, so none of that shared-state code can ever see it.

### 1. `app/world.py` — cheap-build path (small, contained change)

- Add `skip_college: bool = False` to `get_or_create(seed, salt=None,
  skip_college=False)`. When `True`, the "fresh league" branch still does
  `INSERT INTO world (seed, year, week, salt) VALUES (?,0,0,?)` (so a legitimate
  row exists — every reader that does `SELECT * FROM world WHERE seed=?` keeps
  working unmodified) but skips the `pmap(_build_universe, tasks, ...)` /
  `world_roster` insert loop entirely.
- Add the same flag through `start_new(seed, salt=None, skip_college=False)`
  (`app/world.py:500`, currently just `reset(seed); return get_or_create(seed,
  salt=salt)`).
- New thin wrapper `get_or_create_jhsaa_only(seed=DEFAULT_SEED, salt=None)` that
  calls `get_or_create(seed, salt=salt, skip_college=True)` — keeps the flag out
  of ordinary call sites so nobody accidentally skips a real college build.
- Since each lab run lives in its own database file, there's no need for a seed
  reservation range or a `kind` marker column — isolation comes from the separate
  file, so the lab world can simply use `DEFAULT_SEED` (2026) inside its own
  scratch DB. This avoids touching `gtt_seasonmode._active_world_seed`,
  `reset()`'s DELETE scoping, or `cleanup_stray_worlds.py` at all.

### 2. New CLI — `scripts/jhsaa_lab.py` (primary deliverable)

```
python3 scripts/jhsaa_lab.py --db /tmp/jhsaa_lab_001.db --genders boys,girls \
    --seed 2026 --salt myrun --export-dir /tmp/jhsaa_lab_001_export
```

- Sets `TENNIS_DB_PATH` in the environment **before** importing `app.world`/
  `app.jhsaa` (mirroring `conftest.py`'s existing convention), so
  `dbpath.resolve_db_path()` resolves to the scratch file for the process's whole
  lifetime.
- For each gender: `season = jhsaa.run_season(gender, season_year, seed=..,
  salt=..)`.
- **Export path** (satisfies "importable into the analytics tool"): immediately
  `research_export.export_zip("jhsaa", year=season_year, gender=gender,
  season=season)` and write the zip (or the unpacked CSV/JSON files) to
  `--export-dir`. This needs nothing else — no DB archive required for this half.
- **Browse path** (satisfies "not a degraded experience"): `w =
  world.get_or_create_jhsaa_only(seed, salt=salt)` then `world.run_jhsaa(seed, w)`
  to archive the same season into that scratch DB's `world_jhsaa`/
  `world_jhsaa_dual`.
- To browse the archived season with the full, unmodified, real `/jhsaa` UI
  (districts, brackets, honors, rankings, player cards — everything, at 100%
  parity, zero new templates or routes): run a **second instance** of the existing
  app with `TENNIS_DB_PATH=/tmp/jhsaa_lab_001.db` pointed at that file and visit
  `/jhsaa` normally. Because the lab world was created at `seed=2026` inside its
  own disjoint file, every existing `DEFAULT_SEED`-based route, and
  `/research/export` itself, works completely unmodified against it too — a nice
  fallback if the CLI's own export step is ever insufficient.
- Support looping over multiple `--salt`/`--seed` values in one invocation (each
  against its own `--db` path, or sequentially reusing one DB with `world.reset()`
  between runs if only the latest result needs to be kept) for generating many
  independent seasons for statistical/Monte Carlo analysis — following the
  existing loop structure in `scripts/jhsaa_upset_calibration.py`, which already
  demonstrates calling `jhsaa.run_season` directly across many salts from a bare
  CLI script with no Flask/world involvement.

### 3. Not building (deliberately out of scope for now)

- **No new web route or template.** Both stated requirements are met by the CLI +
  the existing app run against the scratch DB — building a same-database
  "`/jhsaa-lab`" in-app preview route would require a `kind` marker column,
  filtering `gtt_seasonmode._active_world_seed`, and re-scoping `reset()`'s DELETE
  statements — real risk to the real save's world-binding invariants for a
  convenience (skip a second `TENNIS_DB_PATH` process launch) that the CLI +
  second-instance approach already covers safely. Revisit only if switching
  processes to browse a lab result proves genuinely too much friction in practice.
- **No `kind`/marker column, no seed-reservation range, no
  `gtt_seasonmode.py` changes.** None of the shared-state risk exists once lab
  worlds never share a database file with the real save.

## Files touched

- `app/world.py` — add `skip_college` param to `get_or_create`/`start_new`, add
  `get_or_create_jhsaa_only`. `run_jhsaa` is reused completely as-is.
- `scripts/jhsaa_lab.py` — new CLI, the actual deliverable. Modeled on
  `scripts/jhsaa_upset_calibration.py`'s direct-call pattern and
  `conftest.py`'s `TENNIS_DB_PATH`-before-import convention.
- Nothing in `app/web/state.py`, any `jhsaa_*.html` template, or
  `app/gtt_seasonmode.py` needs to change.

## Verification

1. Unit-level: with `TENNIS_DB_PATH` pointed at a fresh scratch file, call
   `world.get_or_create_jhsaa_only(2026)` and confirm `world_roster` has zero rows
   for that world (college build genuinely skipped) while the `world` row itself
   is valid (`load_world(2026)` returns it).
2. Call `world.run_jhsaa(2026, w)` and confirm `world_jhsaa`/`world_jhsaa_dual`
   are populated exactly as a normal world's would be (same row shapes).
3. Point a second local instance of the app at that scratch DB
   (`TENNIS_DB_PATH=... python3 -m app.web.server` or however it's normally run)
   and browse `/jhsaa`, a district page, a bracket, and a player card — confirm
   full parity with the real app's JHSAA section, and confirm college-side pages
   fail gracefully or are simply not visited (never crash the process — check
   `/api/health`/`/api/ready` still pass, since those are `DEFAULT_SEED`-scoped
   inside this now-disjoint file and should just report on this world normally).
4. Run `scripts/jhsaa_lab.py` end-to-end and confirm the exported CSV/JSON bundle
   opens correctly in a spreadsheet tool / pandas, with the same columns
   `/research/export`'s existing JHSAA bundle produces.
5. Confirm the real save's `tennis.db` is never touched by any of the above (the
   whole point of the scratch-DB approach) — run the CLI, then check the real
   save's `world` table row count / mtime is unchanged.
6. Run the existing JHSAA test suite (`tests/test_jhsaa_routes.py`,
   `tests/test_jhsaa_toc.py`) to confirm the `skip_college` addition to
   `get_or_create`/`start_new` doesn't change default (non-lab) behavior at all —
   the flag defaults to `False` everywhere it isn't explicitly passed.
