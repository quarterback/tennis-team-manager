# AAR — Career mode: the coached team's lineup reaches the court

Part of the team-takeover/career mode (see `DESIGN-team-takeover-career-mode.md`).

## The problem
The season engine deliberately derives each team's played singles ladder from
live-results **STR + a season-stable coach-preference noise** (`season.coach_lineup`),
not from any stored order. The editor's `set_lineup` override reorders
`ncaa.build_roster` output (so team pages and `squad_and_ladder` reflect it), but
`coach_lineup` re-scores the roster by STR and **ignored the pin for duals**. So a
"set your lineup" feature built on `set_lineup` alone would be cosmetic — the
simulated matches would not change. That's the exact dead-feature trap career mode
exists to remove.

## The fix (gated, opt-in, no-penalty)
`coach_lineup` now accepts an optional `pinned: list[str]`. When present, the
pinned-and-available players lead the ladder in the coach's order; everyone else
falls in behind by the usual STR score, and the per-dual bench rotation is skipped
(the coach decides who plays). Injuries still apply first (a hurt pin pulls up the
next body) and the playing-time guarantee (`forced`) still applies.

The pin is supplied **only for the human-coached program**, by `_coached_pin(prog)`
inside `season.dual_between` (the single call site of `coach_lineup`, used by both
the base and live sims). `_coached_pin` returns `None` unless `prog` matches
`worldconfig.user_program()` AND that program has a `set_lineup` override; otherwise
the team plays the normal auto ladder.

## Why this is safe
- **Single seam.** `coach_lineup` is called in exactly one place (`dual_between`),
  so gating there covers every path with no other call-site changes.
- **No new determinism risk.** `dual_between` already reads per-save overrides
  (`build_roster` pulls moves/lineups) and per-save injury/forced sets are already
  passed in. The pin is the same kind of per-save input. With no coached program —
  spectator mode, the default — `_coached_pin` is always `None` and behavior is
  byte-identical to before.
- **No disadvantage for inaction.** A coached team whose coach never set a lineup,
  a team you don't coach, and a pure spectator world all keep the auto ladder. A
  pin only ever helps/hurts the team that explicitly set it, by its own choice.
- **Cheap.** For the ~all non-coached teams `_coached_pin` is a cached identity
  check (worldconfig's in-process cache) with no DB read; only the coached team's
  own duals touch `overrides.get_lineups()`.

## Web surface
The Clubhouse (`/my-program`) shows the ladder in `build_roster` order (which honors
the pin, unlike `team_roster`'s ability re-sort) with ▲/▼ controls posting to
`/my-program/lineup` (school taken from the saved program, never the form). An
"Auto lineup ⇄ Custom lineup" badge plus "Reset to auto" (`clear_lineup`) make the
opt-in explicit. Each edit calls `reset_all()` to rebuild, exactly like the editor.

## Tests
`tests/test_career_lineup.py`: pin reaches the court when coached; pin ignored
without a coached program (spectator); pin ignored for a team you don't coach;
coaching without touching the lineup is identical to auto (the no-penalty contract).
