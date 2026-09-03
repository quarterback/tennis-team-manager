# AAR — the HS Transfers page at 11,000 moves

**Owner report (2026-09):** "why does it take so long to load the transfer page …
is it polling the whole league or something" — on a save ~40 seasons deep with
11,000+ recorded JHSAA transfers. And the correction that shaped the fix: "there
wouldn't be a need to read old transfers, they stop being relevant after the kid
graduates … once the kid has been moved it's also not data that's needed until
the kid is accessed."

It was polling the whole league. Four separate ways.

## What a plain click cost (measured, 11,000-move ledger, girls' association)

| Step | Before | After |
|---|---:|---:|
| `transfer_rows()` — the ledger with names | 20.0 s | 1.1 s (and the page no longer asks for all of it) |
| `roster_pid_index` — one gender, cold | 41.7 s | 13.1 s cold, then **patched** per edit |
| `build_roster` — one program | 50 ms | 18 ms |
| `jhsaa_transfer_version()` — per call | 20.6 ms | 0.3 ms |
| `set_jhsaa_transfer` — one Move / one batch line | 58 ms | 2 ms |

The page fired the pid-index build for BOTH genders in background threads on
every visit whose cache was cold, and the cache was cold after every edit (the
key carried the transfer fingerprint). So a click was ~20 s of ledger on the
request thread while ~85 s of roster generation fought it for the interpreter
lock — and the next click after an Apply did it all again.

## The four faults

1. **Every roster build walked the whole ledger.** `build_roster` iterated all
   11,000 records per program asking each whether it lands here this year.
   ~95% of them named a player who graduated years ago; the answer was always
   no. `enrolled_transfers(year)` now cuts the ledger ONCE per (version, year)
   to the four enrolled cohorts and indexes the inbound movers by
   `(gender, school)`, so a build reads its own school's list. Archived seasons
   read the slice for THEIR year, so old rosters regenerate as played.

2. **The version fingerprint hashed the table per call, and it is called per
   roster.** `jhsaa_transfer_version()` selected and md5'd every row: 20 ms ×
   ~900 programs per gender build. It is now a one-row stamp maintained by
   **SQLite triggers in the schema** (`overrides._SCHEMA`), so a direct
   INSERT from a script or a test bumps it too — a stamp only disciplined
   callers update is a stale cache waiting to happen. A pre-trigger save seeds
   the stamp from the full hash once.

3. **The ledger regenerated a whole Prospect per mover to print a name.**
   `_gen_seat` — attributes, career model, exposure — at ~2 ms a row, for
   every row, on every load. The name is one draw off the seat's rng, now
   factored into `_draw_name` (shared with `_gen_seat`, so the two cannot
   disagree) and read through `_seat_name` at ~0.1 ms, memoised per
   `(salt, pid)`. ‼️ The old code also passed salt `""`: the name draw is
   salted and the pid is not, so on a salted save the ledger printed
   strangers' names beside the right pids (`_resolve_member`'s documented
   trap, live on this page). `resolve_transfer_names` takes the real salt.

4. **The page rendered the all-time ledger** — thousands of History rows,
   three `url_for` each, for a tab nobody was on. `transfer_ledger()` builds
   rows with no names (a dict walk); the route resolves names only for the
   PENDING moves plus ONE season of history, picked server-side (`hy`,
   default the most recent past season; `all` still exists).

And the batch's pid index, which the page pre-warms: its key carried the
transfer fingerprint, so every edit threw the whole thing away.
`roster_pid_index` now keeps the index across versions and rebuilds ONLY the
programs the changed records name (origin and every destination —
`build_roster` reads no other record for a school). A 50-move Apply rebuilds
~100 programs (~2 s) instead of two associations (~85 s). The boot warmer
builds it once at start-up so the first visit is not the one that starts it.

## Lessons

- **A table that is "rare owner-authored overrides" grows.** The code was
  written when the ledger was dozens of rows and every path read all of it.
  At 11,000 rows the same code was correct and unusable. When a store is
  appended to every offseason, size the read to what a consumer NEEDS, and
  ask what makes a row stop mattering — here, graduation.
- **The fingerprint was the cost, again** (`AAR-jhsaa-playup-fingerprint-
  query-storm.md`'s lesson, one level up): the memo was fine, its KEY hashed
  11,000 rows. A version stamp has to cost what a dict lookup costs.
- **Keep the invalidation edge as narrow as the edit.** A transfer touches two
  or three schools; a key that drops the whole index on any edit turns every
  batch into a full rebuild. Same rule as `AAR-cache-invalidation-scope-
  lineup-stall.md`, on a different cache.
- **A background build is not free on one interpreter.** The deferred-job
  pattern keeps the worker responsive, but two 40-second CPU builds still
  share the GIL with the page that started them. Warm at boot; patch, don't
  rebuild.

Pinned by `tests/test_jhsaa_transfer_perf.py`.
