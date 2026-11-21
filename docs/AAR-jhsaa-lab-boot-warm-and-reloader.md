# AAR: the JHSAA lab spent its first minutes warming a college game it doesn't have

## Report

Owner, 2026-11, on an 86-season lab save (7.5 GB): "why is the high school game
so slow". The server log showed the tell: after the first couple of pages, even
the 304 responses for static CSS took two to four seconds to come back. A 304
does no work, so the process was busy with something else and requests were
waiting on the GIL.

## What was running

1. **Two copies of the boot warm.** `main()` ran Flask with `debug=True`, which
   starts the reloader: a parent process that only watches files, and a child
   that serves. `create_app()` runs in both, so both started the background
   warm. The parent's warm served nobody.
2. **College work in a high-school save.** The warm's first steps were
   `wd.warm_caches()` (college roster prime plus the national recruit boards)
   and `warm_championships()`. On a JHSAA-only world the recruit boards are
   built in spawned worker processes, each of which re-imports the app and
   re-runs the lab preflight against the whole database (the extra
   `JHSAA LAB BOOT` lines in the log), and with the association switch on, a
   board for an archived season replays that season to name its seniors. None
   of it feeds a page the lab opens.
3. **The shell created college seasons.** `_game_context()` (the top bar, on
   every page) called `sm.get_or_create` for each active college universe, so
   the first page of a year on a save with no college season built one on the
   request thread. That is how a lab save came to show "NIT Kickoff Weekend"
   and a "Run pro offseason" button.

## Fix

- `create_app(boot_warm=...)`; `main()` passes `False` in the reloader parent
  (no `WERKZEUG_RUN_MAIN`), and the JHSAA lab (`JHSAA_LAB_MODE`) runs with no
  reloader at all.
- The warm skips `warm_caches()` and `warm_championships()` when
  `wd.is_jhsaa_only()`. The JHSAA steps (scouting census, transfer pid index)
  still run.
- `_game_context()` and `warm_championships()` read the season with
  `sm.find_season` and never create one. A missing season is simply not
  counted.

## Not changed, and worth knowing

- The JHSAA warm steps still hold the GIL for roughly a minute after boot
  (two whole-association roster builds per gender). Pages opened in that
  window are slower than pages opened after it.
- The save is 7.5 GB at 86 seasons, which matches an archive whose box scores
  were never compacted (about 69 MB a season uncompressed against about 15 MB
  compressed). `scripts/migrate_jhsaa_boxscores.py` reports what it would do
  and changes nothing without `--apply`; `--vacuum` returns the space.

No tests run, by request. Syntax checked only.
