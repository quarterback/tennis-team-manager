# AAR — the dbpath probe race that forked a save, and the drift diagnostic

Owner report, 2026-09, in three escalating messages over one evening: "one
school's stats are all showing 0-0" → "every school is, is it related to the
latest update?" → "it's for sure the same database but when I loaded it this
time it said it was 2027" (a 47-season save). All three were ONE bug, and the
bug was not in generation, not in the record fold, and not in any recent
commit — it was in `app/dbpath.py`, present since the initial upload, surfaced
by concurrency.

## 1. The bug: a writability probe that raced with itself

`resolve_db_path()` re-ran `_writable_dir()` on EVERY call, and the app calls
it on every DB connection (`worldconfig._conn()` among many). The probe wrote
a FIXED filename (`.write_probe`) and deleted it. Two threads or spawn workers
probing the same directory at once: both create the file, the first
`os.remove` wins, the second raises `FileNotFoundError` — an `OSError`, the
exact class the probe treats as "not writable" — and that one call silently
resolved to the fallback save in `~/.tennis-team-manager/`.

Three grades of damage, all observed:

- **Split-brain within one process**: pages read the real archive while the
  era settings (`_resolve_era` → `worldconfig`) resolved against the shadow
  DB. Every roster regenerated under the wrong `name_era` → the regenerated
  names matched nothing in the archive → every name-keyed record folded to
  0-0, while pid-keyed award chips still attached (a pid carries no salt and
  no name). That asymmetry — awards stick, records zero — was the fingerprint
  that identified the class of bug before the cause.
- **A shadow universe**: the fallback file accumulated real state (a world
  row, archived seasons, era rows), because `get_or_create` and
  `worldconfig.set` ran against it whenever a call lost the race.
- **A full flip**: a boot that lost the race at import came up INSIDE the
  shadow save — "my save says 2027".

## 2. The fix (`app/dbpath.py`), three parts, each sufficient alone

1. **Unique probe filename** per call, and a lost delete-race reads as
   writable — someone removing our probe proves the directory works.
2. **The resolution is memoised per configured path** — one decision per
   process. A probe that can flip a single connection mid-run is a fork
   machine whatever its filename.
3. **‼️ An existing save file is returned WITHOUT probing.** The repo's
   world-resolution doctrine ("don't add graceful fallbacks — every layer
   that degrades turns a should-be-crash into plausible-looking wrong data")
   applies to the FILE too: if the configured `tennis.db` exists, it IS the
   save, and SQLite failing loudly on a truly unwritable directory beats
   quietly forking the universe. The fallback survives only for a configured
   path that does not exist and cannot be created (fresh install on a
   read-only volume — the Fly case the resolver was written for).

Pinned by `tests/test_dbpath.py`: 200 concurrent resolutions land on one
file, and an existing save wins even when the probe is forced to fail.

## 3. The diagnostic (`scripts/diagnose_jhsaa_roster_drift.py`)

Written mid-hunt to answer "which per-save input moved" from the owner's
machine, since no code delta reproduced the drift (probes proved `build_roster`
byte-identical across the repo's entire history for fixed inputs — which was
itself the evidence that the cause was state, not code). What its first field
run taught, each now built in:

- **It must read exactly the save the app reads.** The owner pasted the
  placeholder path, `resolve_db_path` fell back, and the diagnostic examined
  the shadow DB while looking authoritative. It now warns loudly when the
  configured path was not used, and the instructions say to run it with NO
  `TENNIS_DB_PATH` from the game's own folder.
- **Raw config is not resolved config.** It prints each era row's stored
  value ('' = the row is missing) AND what `jh.name_era()` etc. resolve to —
  and calling the resolvers is deliberately the ONE write it can make: a
  missing row self-configures and persists, exactly as the app's next page
  load would. The docstring says "near read-only" and why; do not re-label
  it read-only without removing those calls.
- **Walk back to the newest season the school PLAYED**
  (`newest_played_season`). The current world year may not have archived
  yet; bailing there ended the first field run. The roster is regenerated at
  the OLDER season's calendar year (`BASE_YEAR + index + 1`) — compare a
  2073 archive against a 2074 roster and ordinary graduation reads as drift.
  JV-only years are not "played": every reader of `world_jhsaa_dual` filters
  on `level` (the research-export lesson), this one included.
  `tests/test_diagnose_roster_drift.py` pins all of this on hand-archived
  dual rows (the repeat-rolls idiom — one real season cannot produce "the
  current year has not archived yet").
- **The name-era sweep** forces `jh._name_era_cache` per probe and restores
  it; a hit names the era the archive was simulated under. `--set-name-era=N`
  then repairs a save whose era row was poisoned while the race was live —
  the one scar the dbpath fix cannot heal retroactively.

## 4. Lessons

- **A per-call environment probe is a per-call chance to be wrong.** Anything
  that decides "which file is the database" must decide once and stick, and
  the decision must never abandon data that already exists.
- **Diagnose the asymmetry.** "Awards attach, records zero" split the
  hypothesis space in half before any code was read: pid-keyed joins survived
  what name-keyed joins did not, so the NAMES had moved, so the inputs to the
  name draw had moved.
- **Prove the code stable before hunting state.** Building the same roster at
  the initial-upload commit, a mid-history merge, and HEAD (identical), and
  three times across processes (identical), eliminated every "the latest
  update changed generation" theory in two commands — against a pull of
  recent commits that all looked plausible.
- **A diagnostic is a product too.** Its first field run failed on the
  placeholder path, printed '' without saying "missing", and bailed on an
  unarchived year — three holes, three user round-trips. A tool built for a
  non-developer's machine earns the same hardening as a page.

## 5. Epilogue — the actual root cause was the LAUNCH, not the file

After the dbpath fix shipped, the owner found the real answer themselves: the
47-season universe was a **JHSAA lab world**, which lives in its own database
by design (`scripts/jhsaa_lab_server.sh` binds `TENNIS_DB_PATH` +
`JHSAA_LAB_MODE`), and they had been opening the app "through the college
route" — a plain launch, which reads `./tennis.db` and creates a fresh league
there when none exists. The "2027 universe" was that fresh league; the real
save was never touched. The owner, who designed the split: "this needs to be
updated somewhere because I'm the one that designed it and still forgot."

So it is written down in three places now: `create_app` announces
`save[ MODE]: <path> — world year N (season Y)` at every boot (WARNING level,
so it prints under the default logging config — read that line FIRST when a
save looks wrong), CLAUDE.md carries the guardrail beside ONE WORLD PER SAVE,
and this section is the record. The dbpath race (§1-2) was real and stays
fixed — it just was not the whole story. Two lessons stack: **a mode that
silently decides which universe you are in must say so on every boot**, and
**"the save is wrong" is a question about WHICH FILE before it is a question
about what is in it.**
