# AAR — Box-stat balance: winners, aces, double faults, UE variety

## Segment summary

Playing the full engine surfaced four box-score complaints (owner, 2026-07):
1. **Not enough winners.**
2. **Aces too rare.**
3. **Double faults too infrequent.**
4. **Not enough variety in unforced-error totals** — every player's UE count
   looked the same regardless of who they were.

All four are point-resolution calibration, so the fix lives entirely in
`engine/rally.py:TUNE` and the winner/error split logic. Nothing about outcomes
changed: the season runs the **fast** model for scorelines, and `boxstats.py`
replays each recorded game through this same rally engine (rejection-sampled to
the persisted winner). So retuning the rally tables moves the box stats every
match shows — singles and doubles both, since `doubles.py` imports the serve/ace
helpers — without touching a single scoreline. `skill_slope`, the fast hold
curve, and the talent distribution were left alone.

Work is on `claude/tennis-engine-balance-igv65n`. Engine/box-stat/dual/doubles
suites (34) plus honors/individuals/ita/bracketing (28) all green.

## Root cause of #4 (the interesting one)

The winner-vs-error split was two **flat constants** — `winner_share = 0.42`,
`unforced_share = 0.55` — applied identically to every player. Aces already
varied by `serve_power − return_game` and double faults by `serve_placement`,
but *whether a lost rally became an unforced error* was talent-blind. So UE
totals only varied by match length and the binomial residual; a metronome and a
sprayer produced statistically identical error counts. That's the "no variety"
the owner saw. The engine's own design philosophy — *talent shifts the
distribution* — was simply not wired into the error split.

## What changed (`engine/rally.py`)

### Levels (issues 1–3) — TUNE nudges
| Tune | Before | After | Effect |
|---|---|---|---|
| `ace_first_base` | 0.16 | 0.185 | more aces |
| `ace_second_base` | 0.04 | 0.05 | more aces |
| `ace_swing` | 0.18 | 0.24 | big servers separate further |
| `second_in_base` | 0.90 | 0.855 | more double faults |
| `second_in_swing` | 0.08 | 0.10 | placement protects steady servers |
| `winner_share` (baseline) | 0.42 | 0.47 | more winners |
| `unforced_share` (baseline) | 0.55 | 0.52 | fewer cheap server UEs |

### Variety (issue 4) — the split now flexes per point
`winner_share` and `unforced_share` became **baselines**; two small helpers
(`_winner_share`, `_unforced_share`) swing the actual split by player attribute,
with three new coefficients:

- `winner_power` (0.34) — the ballstriker's groundstroke weapon (`_offense` =
  ½(forehand+backhand)) → more clean winners.
- `winner_steady` (0.34) — a steadier *opponent* gifts fewer forced errors, so
  more points must be earned with a real winner.
- `unforced_steady` (0.62) — a low-consistency *server* sprays more unforced
  errors; a metronome rarely misses.

Because a flaky player's UE now rises through **both** error branches (as the
misser when the server wins, and as the server when they lose the rally), a
player's `consistency` becomes the dominant driver of their UE total — which is
exactly the between-player spread that was missing. Wind's error contribution
was folded into `_unforced_share` (previously inline), no behavior change at
calm default.

## Measured before → after (400–600 full-fidelity matches, base 0.5)

| Stat | Before | After | Target |
|---|---|---|---|
| Ace rate / serve pt | 11.4% | 13.2% | up |
| DF rate / serve pt | 3.9% | 5.6% | up |
| Winners mean (per player/match) | 29.5 | 31.6 | up |
| Winners : UE ratio | 1.01 | 1.20 | winners lead |
| UE mean | 29.3 | 26.3 | ~steady |
| UE CV (std/mean) | 0.36 | 0.46 | more spread |
| UE/pt: low-consistency (<0.42) | — | 28.8% | — |
| UE/pt: high-consistency (>0.58) | — | 15.1% | ~2× spread |

The last two rows are the point of #4: identical-length matches now yield very
different error counts depending on who's hitting.

## Guardrails / gotchas for the next agent

- **Do not push these back to flat constants.** The per-player winner/error
  split is the whole fix for #4. If a future test wants a fixed UE rate, the
  test is the stale side — assert an *identity* (UE ≤ points lost), not a level.
- **Outcomes are the fast model's job, not this file.** These tables only feed
  the box-stat overlay + exhibition full-fidelity matches. If chalkiness needs
  tuning, that's `fast.py`/`skill_slope`, not here (see
  `docs/match-engine-and-ratings.md` §1, §4).
- Ace and second-serve tunes are **shared with doubles** (`doubles.py` imports
  `_ace_prob`, `_second_serve_in_prob`), so those two propagate automatically;
  the winner/UE split does not (doubles keeps its own `winner_share`).
- Re-measure with a full-fidelity harness (not fast) — the fast model records no
  per-player stats. Reuse the throwaway in scratchpad or `render.py`'s box.
