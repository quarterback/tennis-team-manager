# AAR — Cross-division non-conference scheduling (NOT DONE — deferred)

> **Status: not implemented.** This documents *why* the My Program scheduler only
> lets you add same-division non-conference opponents, what would break if we lifted
> that, and the path to do it properly if we revisit. No code changed for this.

## What was wanted

In the Clubhouse non-conference planner the opponent picker only lists teams in your
own division+gender. The owner (rightly) pointed out that's unrealistic — a dual is
just two teams on court, and **D3↔D4** especially should be able to play each other
out of conference (our "D4" is a synthetic split of real-world D3, so cross play
there is completely natural). Desired UX: a **searchable, any-division** team picker.

## Why it's not just a UI filter

The match **engine** is already division-agnostic — `engine.dual.simulate_dual` /
`season.dual_between` will happily play any two programs (the editor's "drop a D1
player on a D3 roster and run a dual" proves it). The blocker is **season
bookkeeping**: each `(division, gender)` is its **own season** (own `duals`,
`standings`, rankings, Power Index, `injuries` rows), and the scheduler/sim assume
both teams live in that one season.

Concrete breakage points (so a future attempt knows exactly what to touch):

- **Opponent lookup is division-scoped.** `seasonmode._programs(division, gender)`
  (`app/seasonmode.py:377`) builds `{school: Program}` for one division; the dual
  player does `dual_between(progs[home], progs[away], …)`
  (`app/seasonmode.py:479`). A cross-division opponent name isn't a key → **KeyError
  at sim time** (the season would crash, not just mis-schedule).
- **The eligibility guard.** `eligible_nonconf_opponents`
  (`app/seasonmode.py:1961`) filters to `load_division(division, gender).programs`.
  That's the visible restriction, but removing it alone just exposes the KeyError
  above.
- **A dual lives in exactly one season.** `nonconf_duals` / the `duals` table are
  keyed by `season_id`; the opponent's *own* season has no row for the match. So
  records/standings are inherently **one-sided** unless we write into both seasons.
- **Injuries are per-season.** `_roll_new_injuries(conn, sid, away, …)`
  (`app/seasonmode.py:495`) writes to *this* season's `injuries` table keyed by
  school — rolling injuries on a guest opponent here would corrupt the wrong season.
- **Power Index has no rating for an outsider.** Rankings/PI are computed from a
  division's own duals using same-division opponent ratings; a cross-division
  opponent has no entry in that pool, so quality-of-win is undefined (would need a
  fallback rating, e.g. the opponent's cross-division strength / Power-6).

## The path, if we revisit

Two tiers, pick by appetite:

- **Guest-opponent model (cheap, low-risk).** Allow cross-division eligible
  opponents; add a **global** program resolver used at sim time when `away`/`home`
  isn't in the division map (a name→Program index across all universes, like
  `ncaa._global_index` does for players); count the result **only on the coached
  team's** record + PI (opponent rating falls back to its cross-division strength);
  **skip** injury rolls on the guest. The opponent's own season is untouched. This
  sidesteps all two-season reconciliation and is the recommended first step.
- **Two-sided model (full, large).** Inject the dual into *both* seasons and keep
  them in sync across re-sims, with consistent records/standings/PI on both sides.
  This is the realistic version but a real project — touches scheduling, the sim
  loop, standings, rankings, and injuries on both seasons.

Plus the easy, independent win regardless of tier: replace the opponent `<select>`
with a **type-to-filter searchable picker** (nicer for 100+ team divisions). That
part has no engine risk and could ship on its own.

## Takeaway

Not done on purpose — the payoff (cross-division non-conf, mainly D3↔D4) is real, but
the same-division assumption is baked into the per-division season architecture, so
doing it right means either accepting one-sided "guest" results or reconciling two
separate seasons. Filed for a future pass; the guest-opponent slice is the sane
starting point.
