# AAR — GTT in-season add/drop waiver wire

## What changed

The pro league (GTT) now runs a weekly **add/drop waiver wire** during the
regular season. Each franchise can release a slumping fringe player and sign a
free agent off a standing pool. There are **no trades** — every move is a
one-sided drop-to-the-wire plus a sign-off-the-wire — and moves are
**gender-locked** and **ability+performance-driven**, never random.

The shape, per the design:

- **Reserve roster.** Each club now carries `RESERVE_MEN`/`RESERVE_WOMEN` (2 per
  gender) of bench depth *beyond* the `LINEUP_MEN`/`LINEUP_WOMEN` (3 per gender)
  that actually play. The roster target per gender is `TARGET = LINEUP + RESERVE`
  (5). The reserve is the cut bait: it absorbs the churn so the lineup core is
  never disturbed.
- **A real wire.** A surplus of free agents (`WAIVER_POOL_MEN`/`_WOMEN`, 6 per
  gender) is kept available league-wide. The off-season intake now draws roster
  need *plus* this pool, and league creation seeds a founding free-agent pool so
  the wire is live from the inaugural season.
- **Gender-locked, no trades.** A move only ever swaps within one gender group
  and never changes a club's per-gender count, so a woman can only be replaced by
  a woman and a man by a man — enforced by construction.

## How the wire decides (ability + performance, not noise)

The signal is the results-based STR from `league_player_str`, which folds a
player's actual pro results back into their rating — so a genuine slump shows up
as a falling number, and class still tells. Each franchise, each gender, each
week:

1. Look only at the club's **weakest** rostered player (always a reserve, since
   the lineup is the top 3 by STR).
2. Compare it to the **best available free agent** of the same gender.
3. Sign the free agent **only if it clears the weakest player by `WAIVER_MARGIN`
   (0.40)** — a clear upgrade. Otherwise stand pat.

Because only the weakest reserve is ever eligible and a clear margin is required,
**franchise starters (never the weakest) are never cut**, and **churn stays low**
(the best free agents are claimed in the early weeks, after which the wire fills
with cut players and upgrades dry up — the loop is self-limiting). It is fully
**deterministic**: a function of the data with no RNG, so the same world+seed
reproduces the same transactions.

## Timing / no-deadlock

`_process_waivers` runs in `advance()`’s regular-season branch **after** the
week’s duals are committed and the connection closed, then opens its own
connection. This is what lets `league_player_str` see the week's fresh results
(it is cached by completed-dual count) without a mid-transaction second
connection on the shared SQLite file. It is skipped after the final regular-season
week (there is no next lineup to shape going into the playoffs).

## Data + views

- New table `gtt_transactions(league_id, year, week, fid, gender, add_pid,
  drop_pid, add_str, drop_str)` logs every move.
- `free_agents(league_id)` — the current wire, best STR first within gender.
- `transactions(league_id, year)` — the season's add/drop log with names.
- `franchise_roster` now flags each player `reserve` and labels reserves `RES`.

## Web

- **League Hub** gains an **Add/drop wire** panel (recent moves league-wide:
  week, franchise, ▲ added / ▼ dropped with STR).
- **Franchise page** dims reserve rows, explains the lineup/reserve split, lists
  the club's own transactions, and shows the **Free agents** wire.

## Constants (`app/gtt_seasonmode.py`)

- `LINEUP_MEN = LINEUP_WOMEN = 3`, `RESERVE_MEN = RESERVE_WOMEN = 2`
- `TARGET_MEN = TARGET_WOMEN = 5` (= LINEUP + RESERVE)
- `WAIVER_POOL_MEN = WAIVER_POOL_WOMEN = 6`
- `WAIVER_MARGIN = 0.40`

(The old `GRAD_FREE_AGENT_SLACK` is superseded by the per-gender `WAIVER_POOL_*`
and was removed.)

## Verification

- `tests/test_gtt_season.py` (16 tests) — adds: reserve depth beyond the lineup;
  founding free-agent pool seeds the wire; add/drop is gender-locked and keeps
  rosters whole; every signing clears its drop by the margin; no franchise
  starter is cut; add/drop is deterministic across identical seeds.
- A full 8-team season produces modest churn (~15 moves) with every roster still
  exactly 5 men / 5 women, and the hub + franchise pages render the wire.
- World and single-gender determinism suites stay green.

## Out of scope (by request)

No trades. The wire is an auto-GM process across all clubs (GTT has no single
managed franchise); a user-driven manual add/drop UI was not built.
