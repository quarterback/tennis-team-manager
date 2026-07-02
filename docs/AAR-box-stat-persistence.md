# AAR — Box-stat persistence: real per-match stats without touching outcomes

**Date:** 2026-07-02
**Scope:** New `engine/boxstats.py` (conditioned stat replay); `game_flow`
recording in `engine/fast.py` + `engine/doubles.py`; `box_stats` wiring in
`engine/dual.py` → `season._dual_record` → `dual_between`; per-line `stats`
in `lines_json`; `seasonmode.player_season_stats` + stat-carrying
`player_log`; player-page and box-score surfacing; `tests/test_box_stats.py`.

## The ask

The sim was missing stat fidelity: the engine models aces, double faults,
winners, unforced errors, serve/return points and break points — but **none of
it existed for season play**, so there was nothing to check the statistics or
the engine against (and nothing for a future projection/true-talent layer to
consume; see the DARKO/LEBRON design work — box-stat persistence is its
prerequisite for this repo).

## Why the obvious fix was wrong

Two facts collided:

1. Season duals are simulated with the **fast game-level model**
   (`season._dual_record` → `simulate_dual(fidelity="fast")`), which draws one
   Bernoulli per game and returns **empty `PlayerStats`**. The full point
   engine computes everything — but season play never runs it.
2. You cannot just switch the season to the full engine. The fast model's flat,
   upset-prone calibration is a deliberate design decision (see `fast.TUNE`'s
   comment block: favorite rate ~65%, tuned by UTR gap). Measured head-to-head
   over 2,000 matches per gap (ncaa_dual format), the full engine is far
   chalkier:

   | overall gap | fast favorite % | full favorite % |
   |---|---|---|
   | 0.03 | 58.8 | 75.3 |
   | 0.06 | 60.7 | 77.4 |
   | 0.10 | 63.9 | 82.3 |
   | 0.15 | 70.6 | 90.3 |

   Flipping season play to full fidelity would silently rewrite competitive
   balance across every division. Not an option.

## Design: fast decides, the point engine narrates

`engine/boxstats.py` keeps both truths:

1. **The fast model stays authoritative for outcomes.** Its rng draw sequence
   is untouched (recording consumes no extra draws), so every scoreline —
   season, tournament, historical replays — is bit-identical to before. It now
   also records a `game_flow`: `[server, winner]` per game plus tiebreak
   `[first_server, winner]` per set (`MatchResult.game_flow` /
   `DoublesResult.game_flow`, `None` at full fidelity).
2. **The overlay replays each recorded game through the REAL point engine**
   (`match.play_game` / `play_tiebreak`, and the four-player
   `doubles._play_game` / `_play_tiebreak` — same serve/rally tables, same
   pressure/clutch model), **conditioned on the recorded winner by rejection
   sampling**: resim the game until the required side wins it, keep that
   attempt's stats, discard the rest. Set/game/server bookkeeping mirrors the
   real drivers so the pressure model sees true context (break/set/match
   points).

Result: per-player stats drawn from the engine's true conditional
distributions, **exactly consistent with the persisted scoreline** — every
hold, break and tiebreak in the stats matches the score (the tests assert
`break_points_converted == breaks in the recorded flow`, per player in
singles, per side in doubles). Deterministic given the seed (the overlay rng
is derived via `boxstats.stat_seed`, decorrelated from the outcome rng).

Known conditioning caveat: a recorded outcome that is *extremely* unlikely
under the point model (a break at an enormous talent gap) can exhaust
`MAX_TRIES` (2000); the last attempt is kept, so that one game's stats could
disagree with the score. At realistic roster gaps a game needs ~1–4 attempts;
at the worst cross-division mismatches ~100. I did not observe an exhaustion
in testing.

## What gets persisted

- Every **completed** line of a season dual now carries `"stats"` inside the
  dual's `lines_json` — no schema migration, and every existing lines_json
  reader is untouched (they ignore unknown keys). Singles:
  `{"home": {...}, "away": {...}}`. Doubles: two dicts per side, ordered
  exactly like `home_pids`/`away_pids`. **Abandoned lines stay stat-less** —
  same rule as the record/STR corpus, which only counts completed lines.
- Keys are compact (`ace, df, fsi, fsp, ssp, svw, svt, rtw, rtt, bpf, bps,
  bpc, win, ue, pts`); the single source of truth for the mapping is
  `engine.state.STAT_KEYS`, with `PlayerStats.to_dict/from_dict` doing the
  round trip. ~6 KB per dual.
- This rides `dual_between` (gated by `season.BOX_STATS = True`), so **every
  persisted phase gets stats**: REG, conference tournaments, NCAA bracket, ITA
  Kickoff/Indoor — and the world driver's cross-division duals, since they go
  through `dual_between` too.
- Old saves keep working: pre-stats duals simply have no `stats` key and don't
  contribute to aggregates ("partial-season totals" rather than errors).
- `app/db.py save_match` now persists `match_stats` whenever stats exist
  (previously keyed on `fidelity != "fast"`), so an overlaid fast match
  round-trips too.

## What did NOT get stats (deliberately)

- **`run_season`'s bulk path** (legacy league page / web `state.py` season
  cache) — in-memory, never persisted, and stat cost there buys nothing.
- **`bracket.play_dual`** — returns only the advancing program; no record.
- **Juniors / HS / individual circuits and GTT** — bulk volume on their own
  paths; GTT has its own store and can adopt the same overlay later.
- The `run_season` default is `box_stats=False`; season mode passes the flag
  explicitly through `dual_between`.

## Cost

Overlay ≈ 1.7 ms per singles match, ~1.3 ms per doubles line → ~12 ms per dual
on top of ~1 ms for the fast sim itself. A season-mode week advance sims a few
hundred duals per universe, so this is seconds, not minutes, per advance.
`season.BOX_STATS = False` reverts to scoreline-only persistence if it ever
matters.

## Surfacing

- **Player page** (`/player/<pid>`): "Season Box Stats" panel — singles and
  doubles blocks: aces/DFs, 1st-serve %, serve/return points won (with raw
  counts), winners/UEs, BPs saved and converted, match counts. Fed by
  `seasonmode.player_season_stats` (one pass over lines_json, cached by
  completed-dual count like the other per-player aggregates).
- **Season box score** (`season_dual.html`): per-side stat strip under each
  line — `A · DF · W · UE · 1st-serve %`, pair totals on doubles lines.
- `seasonmode.player_log` entries now carry the player-POV per-match `stats`
  dict (compact keys) for anything downstream (career views, projections).

## Validation

- `tests/test_box_stats.py` (9 tests): overlay leaves scorelines/winners
  bit-identical; determinism (stats included); full-fidelity no-op; singles
  stat identities (serve/return cross-totals, points balance, aces ≤ serve
  points won, DFs ≤ second serves, BP saved ≤ faced); **breaks-in-stats ==
  breaks-in-score** for singles and doubles; JSON round-trip; season-layer
  persistence (completed lines carry pids-keyed stats, abandoned don't);
  aggregation equals a manual re-aggregation of raw lines_json; player_log POV
  stats sum correctly.
- Full suite run (`python3 -m pytest -q`): green — engine, season, seasonmode,
  ratings, web tests all unaffected, as expected given the untouched outcome
  rng.
- Manually rendered `/player/<pid>` and `/season/dual/<id>` against a played
  D2 season (Flask test client): both panels present with live numbers.

## What I did not change

- No engine tuning: `fast.TUNE`, `rally.TUNE`, `doubles.TUNE` untouched.
- No change to which lines count for records/STR (abandoned lines are still
  excluded everywhere).
- No new tables — stats live in `lines_json` next to everything else the box
  score already reads. If a projection layer later wants indexed queries, a
  `match_box_stats` table can be derived from lines_json at any time.
- Doubles "who struck the error" attribution inside a rally is a coin flip
  between partners (`doubles._play_point` already worked that way at full
  fidelity) — inherited, not new.

## Addendum — why the full engine tilts even near-equal matchups
*(kept here as reference data for any future refactor that wants full-engine
outcomes in season play)*

The calibration table above is not a bug in the full engine and not a small
gap to "tune away" — it is structural. Competitive balance is the ONLY reason
season play didn't just switch to the full engine (the ~5x speed cost would
have been tolerable).

**1. One weakly-tilted coin vs. 150 compounding ones.** The fast model
collapses talent into a single number — the `overall` gap — applied once per
game through a deliberately flat logistic (`skill_slope` 1.5). A match is ~20
weakly-tilted coin flips, so a small talent edge stays a small result edge
(0.03 gap → 58.8% favorite). The full engine resolves ~150 points, and the
gap tilts *every point through several channels at once*: first-serve %
(`serve_placement`), ace probability (`serve_power` vs `return_game`), rally
win probability (`rally_slope` 3.2 on the rally-skill diff), unforced-error
suppression (`consistency`), and clutch on the big points (`mental` gap, and
BP/SP/MP points are exactly where matches are decided). A ~52% per-point edge
compounds binomially into a 75%+ per-match edge — same 0.03 gap → 75.3%
favorite. Small edges never stay small over 150 trials.

**2. It tilts on profile, not just level.** Two players with identical
`overall` but different shapes (big serve vs grinder, clutch vs fragile,
serve-power vs return-game mismatches) are NOT a coin flip in the full engine
— the sub-skill channels don't cancel. The fast model, reading only `overall`,
treats them as one. So "close in ability" in the rating sense still gets
tilted by everything else the point model knows about.

**3. What the overlay does with this.** The hybrid is deliberate: the flat
fast model keeps *match outcomes* at the tuned college-tennis upset rate,
while the conditioned replay lets the same profile channels express themselves
in the *stats* — the big server piles up aces, the clutch player saves break
points — inside whatever scoreline the fast model decided. Engine texture
without engine compounding.

**4. If a future refactor wants full-engine outcomes anyway.** The honest
path is flattening the full engine's per-POINT slopes until its emergent
per-MATCH favorite curve reproduces the fast model's tuned targets (the
`fast.TUNE` comment block: ~63/69/77/87% by UTR-gap band, ~65% overall) —
i.e. retune `rally.TUNE` (`rally_slope`, `ace_swing`, serve-plus terms,
`clutch_logit`) against simulated season-scale samples, not per-point
intuition. Beware: per-point flattening also flattens the STAT distributions
(fewer aces for big servers, etc.), so the current split — flat model for
outcomes, steep model for stats — is genuinely two different jobs, and any
unification has to pick one texture or re-derive both. Note the repo has been
here before from the other direction: see
`docs/AAR-engine-upset-recalibration-and-rating-scale-map.md` — the flat
game-level model IS the prior answer to upset calibration.
