# DESIGN — Carrying accumulated JHSAA history into a future integrated save

Status: **documented path, not built** (owner: "not a priority, just something I'd
been thinking about"). Build it when asked.

## The ask

The owner is simming JHSAA-only seasons (the lab, `scripts/jhsaa_lab_server.sh`),
archiving every year. At some point they want to return to the full integrated
play-to-clinch universe and start a college save **with all of that high-school
history already in place** — established programs, records, champions, awards —
because "it's more fun to play the high school with a history and established
programs than not."

## Why it is very doable — the verified facts

1. **A JHSAA season is a pure function.** `jhsaa.run_season(gender, year, seed=0,
   salt=salt)` depends only on the season year, the salt, and static
   `data/jhsaa/schools.json` — no college state at all. The same salt reproduces
   the same seasons, players and results anywhere.
2. **The archive is two tables, keyed only on `(world_id, year, gender)`.**
   `world_jhsaa` (one summary JSON row per gender-year) and `world_jhsaa_dual`
   (one row per team-dual). Nothing in them references a seed, a college table, or
   the lab/real distinction. Copy the rows, rewrite `world_id`, and every JHSAA
   page reads them.
3. **Players are regenerated, not stored.** A roster/career is rebuilt from
   `(salt, school, gender, entry year, seat)` — so history "carries" players for
   free **as long as the destination save uses the SAME salt** as the lab world
   that played the seasons.
4. **The rung self-skips.** `world.jhsaa_done(world)` marks a year done by the
   presence of `world_jhsaa` rows — imported rows are indistinguishable from
   played ones.

## The mechanism (when built): `scripts/jhsaa_import_history.py`

Given a lab DB (source) and a fresh real save (destination):

1. **Assert the salts match** (`world.active_salt` both sides) — hard abort
   otherwise. With a different salt the archive would describe seasons whose
   players the destination can never rebuild: awards and player links would point
   at strangers. This is the one non-negotiable precondition, so the real save
   must be created with the lab's salt (`world.start_new` already takes `salt=`).
2. **Copy `world_jhsaa` + `world_jhsaa_dual`** rows into the destination,
   rewriting `world_id` to the destination world's id. Years keep their zero-based
   indices (0..N-1).
3. **Copy the era gates**: `worldconfig` keys `jhsaa_name_era` and `jhsaa_dev_era`
   from the lab save. These self-configure from the archive on first read, so an
   import BEFORE any read would actually self-heal — but copying them is explicit
   and safe against a read that slipped in first (a wrong era silently renames /
   re-rates archived cohorts).
4. **Advance the destination world's year pointer to N** so the college sim's
   year 0..N-1 aren't replayed over the imported history. This is the one piece
   needing a small code change: `world.get_or_create` always builds the college
   universes at year 0. Options, in order of preference:
   - **(a) Start-at-year support**: a `start_year=N` parameter on
     `start_new`/`get_or_create` that inserts the world row at `year=N` and
     builds `world_roster` base rosters keyed to year N. Cleanest; base roster
     generation is already year-parameterized through the derived year seed.
   - **(b) Import-then-advance**: create the save normally, import the rows under
     years −N..−1 (negative indices are never generated but read fine through the
     `(world_id, year)` keys — verify the season-year conversion
     `BASE_YEAR + year + 1` renders sensible labels). Avoids the code change but
     bends the year arithmetic; only take this if (a) proves invasive.
5. **Verify**: `/jhsaa` shows N archived seasons; a program page shows its full
   `jhsaa_school_history`; a player card from year 0 resolves; the first
   `/world/advance` plays season N+1 (not season 0 again) and its seniors land on
   the recruit board.

Notes:
- Renames are code-level (`import_jhsaa.RENAMES` + `former_names.json`), shared by
  both saves automatically — the relabel-on-read layer needs nothing.
- Do NOT try to have an agent "write history into a save" from exported CSVs —
  the structured archive plus a matching salt already reproduces everything,
  including the players, exactly.
- The lab world and the real save must never share a database file (see
  `docs/PLAN-jhsaa-standalone-lab-mode.md` — `gtt._active_world_seed` binds to the
  OLDEST world row). The import is a copy between two files, never a merge into
  a shared one.
