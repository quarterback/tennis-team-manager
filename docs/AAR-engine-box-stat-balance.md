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

## Pass 2 — "it still feels random" (talent fingerprints)

Owner follow-up: the levels were right but stats still read as luck. Root cause
was structural: **each box stat keyed off a single driver** (aces = serve−return,
DF = placement, winners = forehand+backhand, UE = consistency), and `stamina`
touched the full point engine not at all. Over ~60 points a one-driver signal is
swamped by binomial noise, and a cannon server facing a good returner posted few
aces — which reads as random.

Fix: give each stat a **basket** of drivers and raise the signal.

- **Aces** now lead on *absolute* serve power, with the return only partly
  offsetting (`ace_return_weight` 0.55, `ace_swing` 0.24→0.30) — a true cannon
  stays an ace machine regardless of opponent.
- **Double faults** read placement **and** composure (`second_in_nerve` 0.10,
  `second_in_swing` 0.10→0.14) — nervy servers dump seconds in normal play, not
  only on break points.
- **Winners** read a shot-maker basket — weapons + court coverage + nerve
  (`winner_power` 0.34→0.46, `winner_move` 0.24, `winner_nerve` 0.16).
- **Unforced errors** stay consistency-led but a good mover retrieves would-be
  errors (`unforced_move` 0.24).

Correlation of each stat with the talent that should drive it (single match,
2,400 player-lines):

| Stat vs its talent | Pass 1 | Pass 2 |
|---|---|---|
| Ace vs raw serve_power | 0.54 | **0.67** |
| DF vs placement | −0.41 | **−0.50** |
| Winners vs shot-maker composite | ~0.40 | **0.53** (and 0.51 vs `overall`) |
| UE vs defensive composite | — | **−0.72** |

These are strong for one match; they rise further over a season as noise
averages out. We deliberately stop here rather than chase r→1 — a deterministic
box score is exactly what the owner does *not* want (talent shifts the
distribution; it doesn't script the line).

## Pass 3 — the engine now SEES the rich attributes (owner directive)

Owner: *"the engine should be seeing the rich attributes!"* Correct — passes 1–2
tuned the split but still fed on the **9 collapsed drivers**. A player's 49 rich
attributes (`app/player_attributes.py:RICH_ATTRS`) were averaged into 9 drivers
at `Prospect.engine_player()` and the texture was gone before a point was played.
So a big *first* serve was invisible if `strength` dragged the `serve_power`
driver down; `court_vision`, `passing_precision`, `discipline`, `rally_patience`
never touched a stat.

Fix — carry the rich table onto the engine and read it directly:

1. **`engine.state.Player` gained `rich: dict | None`** — the 49 attrs as [0,1]
   units. `Prospect.engine_player()` now populates it; synthetic `random_player()`
   leaves it `None`.
2. **Per-role baskets on `Player`** (`ace_power_first`, `return_solidity`,
   `second_serve_in_skill`, `serve_composure`, `attack`, `steadiness`,
   `court_cover`, `go_for_it`). Each reads the *specific* attributes that produce
   that outcome, and **falls back to the matching driver when `rich` is None** —
   so synthetic players (and every existing test) behave exactly as before.
3. **`rally.py` reads the baskets** instead of drivers: aces ← first-serve
   power + variety; DF ← second-serve quality + composure; winners ← weapons +
   passing + approach + vision + court coverage + nerve; UE ← consistency +
   tolerance + discipline + patience + coverage.

### The distribution trap this exposed (important)

Passes 1–2 were calibrated on synthetic `base=0.5` players. **Real rosters don't
sit at 0.5** — measured basket centers: **D1 ≈ 0.68, D2 ≈ 0.49, D3 ≈ 0.42**. With
the swings anchored at 0.5, every D1 player got a large positive winner swing and
negative error swing → **W:UE 3.2, aces 16%, DF 2%** on real rosters. The whole
prior calibration had been measuring the wrong population.

Fix: a **`swing_ref` (0.60)** anchor — the talent level the winner/error/ace
swings are measured against — and re-tuned bases/coeffs against **real rosters**.
A player at the reference gets the baseline; stronger bends toward winners/aces,
weaker toward errors. This also produces sensible **cross-division texture** for
free.

### Realized on real rosters (single match, ~1,600 duals/division)

| | ace% | DF%/pt | winners | UE | W:UE | UE CV |
|---|---|---|---|---|---|---|
| D1 | 11.3 | 2.7 | 31.4 | 20.1 | 1.56 | 0.55 |
| D2 | 8.3 | 6.6 | 17.9 | 32.9 | 0.54 | 0.43 |
| D3 | 7.5 | 8.2 | 12.9 | 34.4 | 0.38 | 0.45 |

D1 hits winners and aces, lower divisions grind and spray — emergent from the
attribute distribution, not hand-set per division.

### Correlation of each stat with its driving attributes (real rosters, ONE match)

| Stat vs its rich basket | drivers (pass 2) | rich (pass 3) |
|---|---|---|
| Aces vs serve power+variety | ~0.54 | **0.60** |
| Double faults vs 2nd-serve quality | ~−0.50 | **−0.60** |
| Winners vs weapons basket | ~0.40 | **0.84** |
| Unforced errors vs steadiness basket | ~−0.72 | **−0.88** |

Winners and UE now track the *actual* rich profile at r≈0.85 in a **single**
match — the strongest lever against "it feels random," and it climbs further over
a season.

### Notes
- **Determinism / outcomes unchanged.** Reading different attribute *values* does
  not change the rng draw sequence; the fast model still decides every scoreline,
  the overlay is still rejection-sampled to it. Box-stat identity + determinism
  tests pass.
- **Doubles** serve/DF read rich via the shared serve-in helpers, and **aces now
  route through the shared `rally._ace_prob`** (damped by a single
  `doubles.TUNE["ace_scale"]` 0.60 for the crowded net) — previously doubles had
  its own stale ace constants on raw drivers and never called the helper it
  imported (caught in review). Doubles ace rate ≈ 6.6% (vs singles 11.3%), now
  reads the rich serve basket. Its net/poach *rating* logic still uses drivers —
  a clean follow-up if desired (touch carefully: those feed doubles seeding).
- Four divisions exist (D4 is the academic tier); it sits between D2/D3 in
  strength and falls in line without separate tuning.
- `tests/test_doubles_lineup.py::test_pinned_doubles_uses_a_non_singles_specialist`
  fails on a dense roster (the 8th player slips into the coached six under lineup
  noise) — **pre-existing**, reproduces on the parent commit, unrelated to this
  work.

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
