# Match Engine & Player Ratings — Model, Calibration, and Open Work

A living reference for how matches are decided, how player talent is built and
rated, and where the ranges should sit. Numbers here are measured from the code;
re-run the snippets in "How to evaluate" to refresh them as the model evolves.

## Design philosophy

**Talent decides matches; randomness is only the residual.** We do not hand-tune
situational dials (fatigue multipliers, grit boosters, form nudges, serve
texture) to manufacture a target upset rate. A single calibrated skill signal —
the gap in `overall`, the bounded average of a player's whole attribute table —
drives every game. Every attribute still matters, but through `overall`, not via
bespoke match-time hacks. We judge the engine by what emerges over a season, and
we keep college matches competitive by getting the **talent distribution** right
(dense, realistic bands), not by rigging individual games.

The STR-gap targets below are **calibration guidance** (a sanity check that the
rating scale and slope are sensible), not win-rate quotas.

---

## 1. How a match is decided

Two fidelities share one match/scoring core (`engine/match.py`, formats in
`engine/format.py`):

- **Full** (`engine/rally.py`) — point by point (serve, ace, rally, error), used
  for showcase/exhibition matches. Talent-rich; also models pressure/clutch.
- **Fast** (`engine/fast.py`) — game-level; each game is one Bernoulli draw on a
  hold probability. **The season runs in fast mode** (thousands of matches/week).

Fast-mode hold probability (`engine/fast.py:_hold_prob`):

```
hold = logistic( hold_base_logit               # server's natural hold edge (0.9)
               + skill_slope * (Δ overall)      # the talent gap (3.6)
               + context_slope * Δ(venue/wind/heat/crowd comfort) )  # 0.18
```

Tiebreaks use `tb_slope` (2.7). That's the whole model — `overall` + environment
+ the residual coin-flip. No stamina/grit/form terms; those attributes act only
through `overall`.

Dual format (`engine/dual.py`): 3 doubles (8-game pro sets, 2/3 → **1 team
point**) then 6 singles (best-of-3, no-ad), first to **4 of 7** clinches; courts
abandoned after the clinch are DNF (real college convention). No-ad is the
default (`engine/format.py`).

---

## 2. The player attribute system

**49 rich attributes** (`app/player_attributes.py:RICH_ATTRS`), graded 20–80,
grouped: serve/return, groundstrokes, point construction, net/doubles,
movement/physical, mental, hardcourt conditions, team/program fit.

These collapse into **9 engine drivers** (`derive_driver_grades`), each an
average of related rich attributes:

| driver | composed from |
|---|---|
| serve_power | first_serve_power, second_serve_quality, strength |
| serve_placement | first_serve_accuracy, second_serve_quality, serve_variety |
| return_game | return_quality, return_aggression, return_depth |
| forehand | forehand_power, forehand_control, pattern_execution |
| backhand | backhand_power, backhand_control, slice_control |
| movement | footwork, speed, agility, balance |
| **stamina** | stamina, recovery, heat_tolerance |
| **mental** (grit) | composure, focus, clutch, resilience, competitiveness |
| **consistency** (pusher) | groundstroke_consistency, shot_tolerance, discipline |

The engine `Player.overall` is the **unweighted mean of the 9 drivers** — so each
driver (hence each attribute group) carries roughly equal weight in match
performance. (A separate weighted `overall_grade` over the 49 rich attrs,
`OVERALL_WEIGHTS`, feeds the *ability* STR prior.)

> Note: grit, stamina, and consistency are real drivers and feed `overall`. A
> player who is genuinely fitter/grittier has a higher `overall` and wins more —
> naturally, without a dedicated multiplier.

---

## 3. STR — the rating

`app/str_rating.py` (UTR-style, results-based): per match a rating comes from the
opponent's STR + games-share; a player's STR is a recency-weighted average of
their last ~30 matches, reliability rising to 1.0 after ~5. **STR is an output**
(it then orders lineups and rankings); it does not feed match probability.

- Display band: **STR 31–57** (game-native; `_STR_PER_UTR ≈ 1.677`, so the band
  spans ~15.5 UTR points). Ability prior: `overall_to_str(grade)` maps grade
  20–80 → 31–57.
- Empirical map (engine overall → ability STR): **STR ≈ 31.0 + 25.94 × overall**,
  i.e. **1.0 STR ≈ 0.0385 overall**.
- Measured ability spread (D1 men): mean **40.1**, sd **4.5**, range **31–54**.

---

## 4. Calibration: STR gap → win probability

Targets (your domain guidance; the article's "~80%+ to the higher-rated" holds in
aggregate):

| ΔSTR | intended |
|---|---|
| ≤ 1.5 | toss-up, decided by attributes (~50–68%) |
| ~2 | ~75% favorite |
| ≥ 3 | ~90% favorite |

**Achieved** with `skill_slope = 3.6` (flat-attribute pairing, single match):
ΔSTR 1→62%, 1.5→68%, 2→**75%**, 2.5→79%, 3→84%, 4→90%, 5→95%.

**Realized over a full simulated D1-men season** (emergent, talent vs talent):

| ΔSTR gap | favorite wins | n |
|---|---|---|
| 0–0.5 | 56% | 1110 |
| 0.5–1 | 63% | 1056 |
| 1–1.5 | 68% | 1060 |
| 1.5–2 | 73% | 975 |
| 2–3 | 80% | 1814 |
| 3–5 | 91% | 3558 |
| 5+ | 98% | 3656 |
| **overall** | **83%** | — |

Sanity: at **equal `overall`**, win rate is ~50% regardless of grit/stamina/
consistency profile — confirming no outcome-rigging.

**The one dial:** `skill_slope` (with `tb_slope`). Raise → favorites win more;
lower → more competitive. Everything else about competitiveness comes from the
talent distribution (next section).

---

## 5. Ratings vs the real world (UTR anchors) — open calibration

Reference UTR (late 2025), our real-life anchor:

| cohort | top men/boys | top women/girls | gap |
|---|---|---|---|
| Pro | ~16.4 | ~13.2 | ~3.2 |
| **College** | **~14.3** | **~11.6** | **~2.7** |
| U18 / HS | ~13.9–14.8 | ~11.1–11.9 | ~2.7 |

Key real-world properties to mirror:

1. **Men/women ceilings differ by ~2.5–3.** Today talent generation is
   **gender-agnostic** (`app/development.py:generate_prospect` → `talent =
   gauss(46, 9)`, no gender term; `app/ncaa.py:_talent_from_strength` likewise).
   → *Proposed:* a gender talent shift so the women's distribution sits a fixed
   offset below men's.
2. **A governor on the top.** Even the best college players sit well below the
   pro/theoretical ceiling, and within the college pool the top ~1% should reach
   only ~the 90th percentile of the scale, with rare exceptions beyond. Today the
   best ability STR (~54) already sits near the 57 ceiling; the top is not
   reserved. → *Proposed:* compress/soft-cap the top of the talent→STR mapping so
   the ceiling is rarely approached.
3. **Dense decimal bands.** Tens of thousands of players cluster in narrow
   ranges; that density (not match-time dials) is what keeps same-level matches
   competitive — and it's why decimals matter. The current sd (~4.5 STR) is
   moderately dense; the top of real college tennis is *extremely* tight
   (#1–#25 men within ~0.6 UTR). → *Proposed:* verify/tighten per-cohort density.
4. **Optional:** remap the STR *display* onto a UTR-like scale (≈1–16.x) so the
   numbers read like real life. Larger ripple (templates, awards copy);
   deferred unless wanted.

These are **not yet implemented** — they're the next calibration pass, to be
evaluated across a season the same way as §4.

---

## 6. How to evaluate (reproduce the numbers)

- **STR→win curve (flat talent):** construct two `engine.state.Player`s with all
  drivers at `o` and `o+Δ`, run `engine.fast.simulate_fast(..., fmt=PRESETS["ncaa_dual"])`
  over many seeds; Δoverall ≈ ΔSTR / 25.94.
- **Season distribution:** `seasonmode.create_season` → `advance` through the
  regular season; bucket completed singles lines by the two players' `str_value`
  gap and tally favorite wins (the §4 table).
- **Tests:** `pytest -q` — the engine/dual/season/seasonmode suites assert
  structure (clinch at 4, ≤7 points, determinism, higher seeds usually advance)
  and stay green across re-tuning.

## 7. Growth areas

- Gender-differentiated talent + the governor + density pass (§5).
- Distinct *playstyles* emerging from the attribute mix (big server, grinder,
  shot-maker) — only if they arise from talent/structure, not bespoke dials.
- Doubles as its own model (currently synthetic pair-average).
- Optionally surface form/momentum in the UI without it altering match odds.
