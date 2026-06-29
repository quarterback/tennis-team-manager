# AAR: full roster in My Program lineup + conference-name abbreviation

**Date:** 2026-06-29
**Scope:** `web/templates/my_program.html` (lineup ladder); `web/templates/player.html`
+ `teams.html` (conference header); `web/state.my_program_view` (already carried the
data) and the STR-rank-card builder (`conf_abbr`); `web/server.teams` (passes
`conf_abbr`).

## What prompted it

Looking at a D4 women's program (Monmouth IL, MIAC), two things were wrong:

1. The "Singles lineup" on My Program showed only part of the roster. D4 rosters
   are 16 deep (3 funded + 13 walk-ons, per CLAUDE.md), but the ladder rendered 6
   starters and only 4 bench, so 6 players were invisible and unmanageable.
2. Full conference names ("Minnesota Intercollegiate Athletic Conference")
   overflowed the tight header boxes on the player STR card, the team page header,
   and the My Program header.

## What changed

**Roster.** `my_program.html` built the ladder as `mp.starters + mp.bench[:4]`. The
view (`my_program_view`) already returns the complete `starters` and `bench`, so
the slice was the only cap. Changed to `mp.starters + mp.bench`: every roster player
now renders with reorder arrows, so the whole D4 roster is manageable. D1 (12) and
D2 (10) are unaffected in spirit, they just show their full, shorter benches.

**Conference abbreviation.** The data model already has `conf_abbr` (MIAC, NESCAC,
ODAC, ...) alongside the full `conf`. The tight boxes were rendering the full name.
Switched them to `conf_abbr or conf` (fall back to the full name for conferences
whose abbr equals their name, e.g. Liberty League), and kept the full name as a
`title=` tooltip on hover:
- `my_program.html` header: `{{ mp.conf_abbr or mp.conf }}` (view already had it).
- `teams.html` header: `{{ conf_abbr or conf }}`. `teams()` now passes
  `conf_abbr = (prog.conf_abbr if prog else "") or conf`.
- `player.html` STR card: `{{ ranks.conf_abbr or ranks.conf_name }}`. The STR-rank
  builder now carries `conf_abbr` in its entry tuple and returns it.

## The detour that mattered: the branch was behind main

I could not find the My Program template at first because the working branch was
several merges behind `origin/main`. The My Program page came from PR #128
(team-tab), and FontAwesome icons / flag SVGs from PR #131, none of which were in
the checkout. Fix: `git rebase origin/main`, then the files existed. The branch now
also carries the boot-cache-warm commit on top.

While rebasing I learned main had independently shipped a readiness gate for the
crash-on-reload problem: a `/api/ready` endpoint, a `LOADING_HTML` interstitial, and
a `_prime_world` before_request that serves the loader instantly and warms the world
in a background thread (`_warming` / `_warmed_salt`). That is the same problem the
boot-warm commit targets, solved at the request layer. They compose (boot warm opens
the gate before the first visitor arrives), but if we only want one, main's gate is
the load-bearing piece.

## Gotchas for the next agent

- **A leaked `tennis.db` makes web tests fail in a confusing way.** The default DB
  path is `<repo>/tennis.db` (gitignored, untracked). If any manual run creates a
  world there, every page test then hits main's readiness gate: `wd.exists()` is
  true but the fresh test process has not primed, so `_prime_world` returns the
  `LOADING_HTML` loader and assertions like `b"Recruiting" in body` fail. The tests
  are fine; the DB is dirty. Remove `tennis.db` (and `-wal`/`-shm`) and re-run. To
  avoid leaking it, always set `TENNIS_DB_PATH` to a scratch file in manual runs.
- **Confirm "is this my change or pre-existing" with a worktree, not a stash.** A
  `git stash` does not remove already-committed work, so it cannot isolate a
  committed change. `git worktree add <tmp> origin/main` and run the test there for
  a clean baseline. (That is how this turned out to be the dirty DB, not the code.)
- **`conf_abbr` is not always a short code.** Some conferences store abbr == full
  name (Liberty League, Landmark, Centennial). `conf_abbr or conf` is safe but is a
  no-op for those; do not assume abbreviation always shortens the string.
- The roster ladder is intentionally uncapped now. If a future division has a very
  long bench and the page gets unwieldy, paginate or scroll the bench rather than
  re-slicing, so the manager can still reach every player.
