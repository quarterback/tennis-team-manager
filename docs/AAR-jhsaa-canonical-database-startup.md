# AAR — one canonical JHSAA lab database, fail closed

## Incident and invariant

The long-running JHSAA lab universe grew to multiple gigabytes while historical
launch forms could select a path argument, inherit `TENNIS_DB_PATH`, or use a
reboot-volatile `/tmp` file. Those choices looked like ordinary gameplay and a
wrong or newly created universe looked plausible.

**Normal JHSAA gameplay has one canonical local database:
`~/.tennis-team-manager/jhsaa_lab.db`. If that database cannot be used, the app
stops. It never creates or falls back to another JHSAA database.**

## Implementation

`scripts/jhsaa_lab_server.sh` now accepts only an optional port. It rejects an
inherited non-canonical `TENNIS_DB_PATH` and always exports the canonical path.
This is also an application invariant: `app.dbpath.resolve_db_path()` invokes
the lab preflight before returning any path when `JHSAA_LAB_MODE` is active.
Only the deliberately named `JHSAA_LAB_DEV_OVERRIDE=1` path preserves isolated
calibration and test databases.

The preflight uses SQLite URI `mode=ro`, so inspecting a missing path cannot
create it. It reports known alternates (including `/tmp/jhsaa_lab.db` and
`/private/tmp/jhsaa_lab.db`) with size, world pointer, salt, and archive range.
It never changes an alternate. A missing canonical file plus any alternate
fails closed for manual recovery. An existing canonical file is opened in
place or startup is fatal; it can never enter the general resolver's fallback.

Before schema bootstrap or cache warming, the preflight prints the absolute
canonical path, byte size, `world.id`, seed, year, week, salt, and archive
minimum/maximum/distinct count. It also derives the lab consistency invariant
from `advance_jhsaa_lab`: after initial year 0 and every successful advance,
archive years must be exactly contiguous `0..world.year`. A mismatch is
diagnosed without repair.

## Deliberate non-features and traps

No database is copied, merged, deleted, migrated, repaired, or backed up. In
particular, this does not make a full SQLite copy on season advance; a roughly
4 GB file makes that unacceptable. Manual recovery stays manual.

The guard must remain in `dbpath`, not only the shell. Module-level `WORLD_DB`
values resolve before `create_app`, so a guard placed after bootstrap would be
too late. Conversely, alternate inspection must remain read-only: replacing
URI `mode=ro` with ordinary `sqlite3.connect(path)` reintroduces the very
missing-file creation this change prevents.
