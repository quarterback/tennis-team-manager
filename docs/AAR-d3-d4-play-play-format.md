# AAR — Division III/IV "play-play": D3/D4 finish every match

**Date:** 2026-07-25
**Scope:** `engine.dual.simulate_dual` (new `play_all` flag), `season._dual_record`,
`season.dual_between`, `season.run_season`.

## Owner's rule (locked)

D3 and D4 **regular-season and ITA** duals are played to completion — **every**
singles match finishes, instead of abandoning the dead rubbers once a side
reaches the 4-point clinch. Motivation: **fuller player stats**. D3/D4 are the
feeder tiers, and a player looking to move up (portal, division jump) is judged
on a complete match record, not a half-season of "abandoned after clinch."

This mirrors the real **ITA/NCAA Division III scoring-format pilot** (mandatory
for 2024-25 non-conference duals and the 2025 D3 Championships): 7-point format,
"play-play" — all doubles and all singles played to completion unless both
coaches opt into clinch-play.

Scope decisions the owner made:

- **Divisions:** D3 **and** D4 (our academic-first D3 analog). D1/D2 keep
  clinch-play, which matches their real format.
- **Which duals:** regular season **+ the ITA opener** (the data that feeds the
  fall portal). **Postseason — conference tournaments and NCAAs — stays
  clinch-play**, keyed off the existing `best_six` postseason marker. Real
  championships may opt into clinch to save time/energy, and it keeps title
  duals decisive.

## Why this is safe (it never changes a result)

The engine already simulates **all six** singles up front; the clinch loop only
decided which ones to *mark* abandoned. So `play_all` just stops discarding
results that already exist:

- **RNG / determinism unchanged** — no new draws.
- **Winner unchanged** — the 4th point locks the dual. With only 7 points on
  offer, once one side has 4 the loser can reach at most 3, no matter how many
  dead rubbers finish. `winner = 0 if points[0] > points[1] else 1` still lands
  on the clincher.
- **Only the margin fills in** — a clinched 4–1 becomes the true 6–2 (etc.), and
  every player lands a completed match on record.

## How it works

`simulate_dual(..., play_all=False)`: the singles resolution loop abandons the
in-progress matches once `max(points) >= clinch` **only when `not play_all`**.
With `play_all=True` every match is counted and recorded (and, at fast fidelity,
gets box stats — abandoned lines never did).

Wiring (`season.py`):

- `dual_between` (season mode's dual entry point):
  `play_all = a.division in ("D3","D4") and b.division in ("D3","D4") and not best_six`.
  `best_six` is `True` only for CT/NCAA (`seasonmode._sim_round`), so regular
  season and ITA (both `best_six=False`) play out; postseason clinches.
- `run_season` (standalone single-division sim): `play_all = division in ("D3","D4")`
  — all of its duals are regular-season.
- The cross-division `world_crossmatch` exhibition also routes through
  `dual_between`; a D3-vs-D4 exhibition therefore plays out too. That table is
  **display-only** (team-page cross-division results) — it never feeds
  `compute_ratings` — so the only effect is a fuller shown margin.

Doubles already play all three out in this sim, so they were already D3-correct;
no change there.

## Knock-on effects (intended, not bugs)

- **D3/D4 Power Index shifts.** `rating.py` drops abandoned lines before computing
  game-share / flight-share (`rating.py:161`); with play-play more lines complete,
  so those shares reflect the whole dual. More accurate, but D3/D4 ratings will
  not match the pre-change numbers.
- **Fuller player corpus.** `_build_corpus` skips non-completed lines, so D3/D4
  players now accumulate more singles results → richer STR convergence and
  records. This is the point.

## Do NOT "fix" these

- A D3/D4 regular-season or ITA dual showing **5–2, 6–2, 7–0** is correct — the
  clinch is at 4, but these divisions **play on**. Do not clamp the total back to
  4 or re-enable abandonment for D3/D4 outside the postseason.
- Do **not** extend play-play to D1/D2 or to D3/D4 **postseason** — the owner
  scoped it to D3/D4 regular season + ITA only.

## Tests

- `test_dual.test_dual_play_all_completes_every_match` — winner identical, all six
  singles completed, margin ≥ the clinched total, per-line outcomes consistent.
- `test_dual.test_dual_order_of_finish*` — order-of-finish ordinals (all six under
  play-play) are a clean 1..N and deterministic.
- `test_season.test_d3_plays_every_match_while_d1_clinches` — end-to-end wiring:
  D3 abandons zero singles, D1 still abandons dead rubbers.
