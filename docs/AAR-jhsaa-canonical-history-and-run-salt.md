# AAR — the canonical JHSAA history and the per-run dice salt

Owner request 2026-09, on top of the display-year offset
(`docs/AAR-display-year-offset-and-lab-integration.md`): the ~73 simmed lab
seasons become THE association's past **in perpetuity** — backdated so the
final played season renders as 2026-27 and the history reads 1955–2027 behind
it — and every future run starts FROM that history rather than re-simulating
it. Two owner decisions fix the shape:

1. **Continue on top.** The frozen seasons are the fixed past; new lab seasons
   stack forward (2028, 2029, …) on the same world. A "new run" resets the lab
   database to the canonical snapshot and sims a NEW future from it.
2. **Fresh dice per run.** Each reset stamps a per-run salt so re-runs diverge;
   the canonical past — read from the archive, never re-simulated — is
   untouched by construction.

## The pieces

- **`scripts/jhsaa_canonical.py freeze`** — sets the lab save's display offset
  to its world year (the `attach_college` arithmetic, without a college build)
  and snapshots it to `~/.tennis-team-manager/jhsaa_canonical.db`. One-time;
  refuses to overwrite an existing snapshot and refuses to restack an offset.
- **`scripts/jhsaa_canonical.py new-run`** — moves the current lab db aside
  (timestamped, with its `-wal`/`-shm` sidecars — NEVER deleted), restores the
  canonical snapshot, stamps a fresh `jhsaa_run_salt`. Run with the lab server
  stopped. Every copy is the SQLite backup API (the WAL rule).
- **`jhsaa.run_salt()` / `run_seed_offset()`** — a worldconfig value
  (`jhsaa_run_salt`), memoised per DB path (the era idiom, cleared by
  `reset_schools()`). `run_season` folds it into the dice-salt string
  (`{salt}|run|{rs}`) that every play path seeds from — the regular season,
  the JV season, the JV state seed, captains, the epiregional unit names —
  and into the seed offset the seed-parameterised draws add (the postseason's
  `gseed` family, both individual-tournament runs, and the world rung's mixed
  doubles via `run_seed_offset()` at the call). It also keys the `run_season`
  memo.

## The design rule everything hangs on

**The world salt keys WHO EXISTS; the run salt keys only WHAT HAPPENS.**
`build_roster`/`make_pid` seed on the world salt, so a new salt there is a
whole association of strangers — which is exactly what the "Start a fresh
world" button is for and exactly what a canonical reset must never do. So
`district_teams` keeps the bare world salt, unconditionally, and the run salt
reaches nothing that generates a person. Pinned over a real scaled season in
`tests/test_jhsaa_run_salt.py`: two runs' rosters are identical pid-for-pid
and name-for-name while their results differ.

**Empty is the identity.** `run_salt() == ""` (every save that never ran the
reset) gives `dice == salt` and `run_seed_offset() == 0` — the pre-feature
code path to the byte, pinned. Archived seasons need no protection beyond
this: the archive is READ, never re-simulated, so a run salt only ever touches
seasons that have not been played yet.

**Stamp it only at the reset, never mid-save.** The recruit hand-off
(`graduating_class`) relies on `run_season`'s memo serving the SAME season the
rung archived; a salt that moved between the two would hand the college board
a season that never happened. `new-run` stamps it on a freshly restored
snapshot whose newest season predates any new sim, so rung and hand-off always
agree.

## Lab surfaces that had to learn the offset

The original sweep assumed a LAB save always has offset 0; freezing breaks
that assumption, so:

- the boot line's jhsaa-only branch (`server.create_app`) now prints
  `display_year(jhsaa_season_year(w))` — this is the line the repo says to
  read FIRST when a save looks wrong, and an identity year there beside
  displayed years everywhere else IS the forked-universe scare it exists to
  prevent;
- `jhsaa_lab.html`'s "latest is …" takes `|cal`.

The lab page's "Start a fresh world" button still calls `world.reset()`, which
clears the offset AND the run salt (value and memo — a fresh world has no
canonical past to be a "run" of), so a brand-new world starts genuinely blank.

## Interaction with the college integration

A frozen lab save already carries an offset anchored on ITS newest season.
`integrate_lab_world.py` / `attach_college` deliberately RE-ANCHOR to the
world year at attach — the first college season is 2026-27 by design — so
seasons added after the freeze push the canonical seasons' displayed years
further back in the integrated save. The integrate preflight now says so out
loud instead of silently restacking.

Tests: `tests/test_jhsaa_run_salt.py` (identity, roster invariance, result
divergence, determinism under a salt, memo keying, worldconfig plumbing).
