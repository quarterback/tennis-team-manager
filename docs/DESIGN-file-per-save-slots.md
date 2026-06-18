# DESIGN — File-per-save slots (multiple named saved sims)

## Why this exists

The other sims in the family let you keep **several independent universes side
by side** — create one, name it, switch between them, delete the ones you're
done with — all from the UI. Tennis doesn't have that *yet*, and the request
("the other sim games have the ability to save and have multiple sims, but
tennis doesn't") is really about adding that **save-slot layer**.

The important framing: tennis is **not** missing persistence. It already has a
SQLite database with deep, normalized state — `players`, `matches`,
`match_stats` (`app/db.py`), week-by-week NCAA seasons (`seasons` / `duals` in
`app/seasonmode.py`), multi-season GTT career leagues (`gtt_*` in
`app/gtt_seasonmode.py`), and the unified D1/D2/D3 × M/W world (`world_*` in
`app/world.py`). What it's missing is the ability to have **more than one of
these at a time**. Today everything resolves to a single database file
(`resolve_db_path()` → one `tennis.db`), so starting a new world writes into the
same database as the last one.

This doc plans the **o27v2 file-per-save model** — each save is its own SQLite
file, with a small JSON registry tracking the slots and which one is active. We
chose file-per-save over viperball's "save_id column on every table" approach
because tennis (like o27v2) already has a normalized multi-table schema; giving
each save its own file means **zero schema churn** and trivial
delete/export/import, at the cost of not being able to query across saves (which
we don't need).

## Reference implementation

`hybrid-baseball/o27v2/saves.py` is the model to port — it's ~240 lines and does
exactly this for the baseball sim. The design below mirrors it, adapted to
tennis's module layout. Read it alongside this doc.

## The one real refactor: dynamic DB-path resolution

Everything else is additive. The only change to *existing* code is making the
active database file resolve **dynamically** instead of being frozen at import.

Today, three modules each freeze their own copy of the path at module load:

```python
# app/db.py:20, app/seasonmode.py:35, app/gtt_seasonmode.py:44, app/overrides.py:18
DB_PATH = resolve_db_path()   # evaluated once, at import
```

and `app/db.py:connect()` defaults to it:

```python
def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH)   # <- frozen default
```

To switch saves at runtime, that default has to become a **function call** that
reads the active slot from the registry.

### Good news: the codebase already anticipates a moving DB path

`seasonmode.py`, `gtt_seasonmode.py`, and `overrides.py` each guard schema
creation with a cache keyed on the path:

```python
_schema_ready_for = None   # "the DB_PATH the schema was last created for"
...
if _schema_ready_for != DB_PATH:
    _ensure_schema()
```

The comment in `seasonmode.py:87` says this is "keyed on DB_PATH so tests that
repoint the DB still get a schema." That mechanism is exactly what we need: once
the path is dynamic, the first connection against a freshly created save file
will see `_schema_ready_for != <new path>` and re-run schema init automatically.
**Switching saves re-seeds schema for free.** The only thing we must change is
turning the frozen `DB_PATH` *constant* into a *live lookup*.

### The change

1. Add `current_db_path()` (in `app/dbpath.py`, next to `resolve_db_path()`):

   ```python
   def current_db_path() -> str:
       """The active save's file, or the legacy single-DB path when no saves
       exist yet. This is the function every connection resolves through."""
       from app import saves            # local import avoids a cycle
       active = saves.active_db_path()
       return active if active else resolve_db_path()
   ```

   Falling back to `resolve_db_path()` when the registry is empty keeps the app
   working with **zero saves configured** — important for tests, bare sandboxes,
   and the one-time migration of an existing `tennis.db` (see Migration below).

2. In each of the four modules, stop freezing the constant and read the function
   wherever `DB_PATH` is used:

   - `app/db.py`: `connect(path or current_db_path())`; `init_db`/`bootstrap`
     unchanged (they already call through `connect`).
   - `app/seasonmode.py`, `app/gtt_seasonmode.py`, `app/overrides.py`: replace
     the module-level `DB_PATH = resolve_db_path()` and each `DB_PATH` read with
     `current_db_path()`. The existing `_schema_ready_for` guard then re-inits
     schema on switch with no further work.

   Net: ~4 files touched, ~28 `DB_PATH` references redirected. This is the part
   with real risk because it sits under every feature — it deserves its own
   commit and a focused test pass (see Testing). Everything after this is new,
   isolated code.

## New module: `app/saves.py`

A near-direct port of `o27v2/saves.py`. Public surface:

| Function | Purpose |
| --- | --- |
| `saves_dir()` | Dir holding `registry.json` + `save_<id>.db` files. Precedence: `$TENNIS_SAVES_DIR`, else `<dir of $TENNIS_DB_PATH>/saves`, else `app/../saves`. Created on demand. |
| `load_registry()` / `save_registry()` | Read/atomic-write `registry.json`. Corrupt/missing → safe empty default (never 500s). Write via temp-file + `os.replace`. |
| `list_saves()` | All slots, newest `last_played_at` first. |
| `get_active_id()` / `get_active_save()` | The active slot. |
| `active_db_path()` | File path of the active save, or `None` if none active. File need not exist yet. |
| `new_save(name, seed, ...)` | Register a new slot, make it active. Does **not** seed — caller runs `bootstrap()` against the now-active file. |
| `set_active(save_id)` | Flip the active pointer. |
| `rename_save` / `touch_save` | Rename; bump `last_played_at` after a sim. |
| `delete_save(save_id)` | Remove slot + its `.db`/`-wal`/`-shm`/`-journal` files. Refuses to delete the last remaining save; repoints active if needed. |
| `register_existing_file(src, name)` | Copy an existing `.db` in as a new slot (import / migration). |
| `snapshot_to(save_id, dest)` | `VACUUM INTO` a clean single-file copy for download/export (merges WAL, no sidecars). |
| `is_valid_save_db(path)` | Opens read-only, checks for a known table — guards imports. |

### Registry shape (`registry.json`)

```json
{
  "active_id": "ab12cd34ef56",
  "saves": [
    {
      "id": "ab12cd34ef56",
      "name": "My Dynasty",
      "seed": 2026,
      "kind": "world",
      "created_at": "2026-06-18T...Z",
      "last_played_at": "2026-06-18T...Z",
      "filename": "save_ab12cd34ef56.db"
    }
  ]
}
```

### Tennis-specific adaptation: `kind` instead of `config_id`

o27v2 stores `config_id` (which league template). Tennis has **several distinct
sim modes** that live in one DB — NCAA season (`seasonmode`), GTT career league
(`gtt_seasonmode`), unified world (`world`). A save can hold any/all of them, so
record a `kind`/`label` field (e.g. `"world"`, `"gtt"`, `"ncaa-season"`) plus
the `seed`, mostly for display on the Saves page. `is_valid_save_db()` should
probe a broadly-present table (e.g. `players`, created by `db.init_db()`) rather
than baseball's `teams`.

## CLI commands (`manage.py`)

Add `cmd_*` functions + subparsers, mirroring the existing dispatch pattern
(`sub.add_parser(...).set_defaults(func=...)`):

- `saves-list` → print slots (active marked).
- `saves-new --name ... [--seed N] [--kind world]` → `saves.new_save(...)` then
  `db.bootstrap()` against the now-active file.
- `saves-switch <id>` → `saves.set_active(id)`.
- `saves-delete <id>` → `saves.delete_save(id)`.
- (optional) `saves-export <id> <path>` → `saves.snapshot_to(...)`.

`cmd_initdb` (`manage.py:151`) keeps working unchanged — with no saves
configured it inits the legacy single DB; with an active save it inits that
file (because `bootstrap()` now flows through `current_db_path()`).

## Web UI (`app/web/server.py` + templates)

The existing 50+ routes **do not change** — they already read "the DB"; they
just won't know which file backs it. New surface:

- **`GET /saves`** — Saves page: list slots (name, kind, seed, last played,
  active badge), with Switch / Rename / Delete / New actions. New template
  `app/web/templates/saves.html`; aggregate in `app/web/state.py` to match how
  other pages assemble view data.
- **`POST /saves/new`** — form → `saves.new_save()` + `db.bootstrap()`, redirect
  to dashboard.
- **`POST /saves/<id>/activate` / `/rename` / `/delete`** — registry ops, then
  redirect back to `/saves`.
- **Nav + active indicator** — add a "Saves" entry to the nav and surface the
  active save's name in the header (`get_active_save()`), so it's always clear
  which universe you're looking at. Follow the nav pattern used for the Data
  Portal entry (see `docs/AAR-atp-wta-data-portal.md`).
- **`touch_save(active_id)`** after any sim-advancing POST (dual run, season
  advance, GTT advance) so the list sorts by genuine recency.

## Migration: the existing single `tennis.db`

On first run after this ships, an existing deployment has a populated
`tennis.db` and an **empty registry**. Handle it gracefully:

- With an empty registry, `current_db_path()` falls back to `resolve_db_path()`,
  so the app keeps serving the legacy DB untouched — **no forced migration, no
  data loss** if we ship the path refactor alone.
- Offer a one-time **"Adopt current database as a save"** action (and/or a
  `saves-adopt` CLI command) that calls `register_existing_file(resolve_db_path(),
  "Legacy save")` and activates it. After that, the app is fully in save-slot
  mode. Do this explicitly rather than automatically so a misfire can't strand
  the original file.

## Concurrency / Fly volume notes

- Per-file WAL is already how tennis connects (`app/dbpath.py:connect` sets WAL +
  busy timeout). Each save file gets its own WAL — no cross-save locking.
- All save files live under `saves_dir()`, which resolves under the Fly volume
  (`$TENNIS_DB_PATH`'s dir, i.e. `/data/saves`). `app/dbpath.py` already falls
  back to a writable local dir if the volume mount is dropped; `saves_dir()`
  should inherit that resilience by deriving from the same resolved path.
- Single global active pointer, no accounts — same model as o27v2. A switch is a
  process-wide change; fine for a single-user/hobby deployment, which is what
  this is.

## Testing

New `tests/test_saves.py`:

- `new_save` + `bootstrap` creates an isolated file with full schema; a second
  save is genuinely separate (write to A, switch, B is empty).
- Switching repoints `current_db_path()` and the `_schema_ready_for` guards
  re-init schema for the new file (no "no such table").
- `delete_save` refuses the last slot; repoints active when deleting the active
  one; removes `-wal`/`-shm` sidecars.
- Corrupt/missing `registry.json` → empty default, app still boots.
- Empty registry → `current_db_path()` falls back to the legacy path
  (backward-compat).
- Point `$TENNIS_SAVES_DIR` at a `tmp_path` so tests never touch real saves.

Re-run the existing determinism/season suites with an active save configured to
confirm the path indirection didn't change sim results.

## Build order (suggested commits)

1. **`app/saves.py`** + `tests/test_saves.py` — pure new module, registry ops,
   no wiring. Lands green on its own.
2. **Dynamic path** — `current_db_path()` in `dbpath.py`; redirect `DB_PATH`
   reads in `db.py`, `seasonmode.py`, `gtt_seasonmode.py`, `overrides.py`. The
   risky, under-everything commit; run the full suite.
3. **CLI** — `saves-list/new/switch/delete` (+ optional `adopt`/`export`).
4. **Web** — `/saves` page, new-save flow, nav + active badge, `touch_save` on
   sim POSTs.
5. **Migration** — "adopt current DB" action + doc note in `README.md` /
   `DEPLOY.md`.

## Effort

Medium — a few focused sessions, not a rewrite. The schema, atomic
sim-persistence, and season/career history already exist; this is a save-manager
wrapper plus one careful refactor of the connection layer. Commit 2 is where the
care goes; commits 1, 3, 4, 5 are additive.

## What this does NOT do

- No per-user accounts or auth — single global active pointer, like o27v2.
- No cross-save queries / "all-time across every league" leaderboards — that's
  the tradeoff for file-per-save. If ever wanted, it'd be a separate aggregation
  pass over snapshot files, not a schema change.
- No change to any sim engine, scoring, or existing route behavior — strictly
  *where* the bytes land, not *what* is computed.
