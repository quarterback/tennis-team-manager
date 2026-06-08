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
  spans ~15.5 UTR points — i.e. **2 STR ≈ 1.2 UTR**; the extra resolution means
  the model leans less on decimals than UTR does). Ability prior:
  `overall_to_str(grade)` maps grade 20–80 → 31–57.
- Empirical map (engine overall → ability STR): **STR ≈ 31.0 + 25.94 × overall**,
  i.e. **1.0 UTR ≈ 0.065 overall**.
- After the §5 calibration, D1-men ability sits at **UTR-eq p50 ≈ 11.6, p99 ≈
  14.2** (dense, high), not the old flat mean of ~UTR 5.

---

## 4. Calibration: UTR gap → win probability

Targets are in **UTR magnitude** (the band is ~1.677 STR/UTR, so these are ~2.5 /
3.35 / 5 STR):

| ΔUTR | intended |
|---|---|
| ≤ 1.5 | comes down to attributes (~55–65%) |
| ~2 | ~75% favorite |
| ≥ 3 | ~90% favorite |

**Achieved** with `skill_slope = 2.2`, `tb_slope = 1.65` (flat pairing, single
match): ΔUTR 1→62%, 1.5→69%, 2→**75%**, 3→84%, 4→91%, 5→95%. (A single logistic
can't be both flat-low and steep-high, so we anchor on 2 UTR → 75% and let
cross-flight gaps run ~90%+.)

**Realized over a full simulated D1-men season** (emergent, talent vs talent),
bucketed by UTR gap:

| ΔUTR gap | favorite wins | matches |
|---|---|---|
| 0–0.5 | 55% | 2509 |
| 0.5–1 | 61% | 4394 |
| 1–1.5 | 66% | 3312 |
| 1.5–2 | 72% | 2198 |
| 2–3 | 82% | 1824 |
| 3+ | 90% | 295 |
| **overall** | **66%** | — |

The per-gap curve matches the targets — but note the **match counts**: ~10k of
~14.5k matches fall in the 0–1.5 UTR band (55–66%), and only 295 have a 3+ gap,
because the talent is densely packed (§5). So the overall favorite rate is just
**66%** — college tennis where most matches are within a margin of error and
outcomes aren't predetermined. *Density, not the engine, drives the
competitiveness.*

Sanity: at **equal `overall`**, win rate is ~50% regardless of grit/stamina/
consistency profile — no outcome-rigging.

**The one engine dial:** `skill_slope` (with `tb_slope`). Everything else about
competitiveness comes from the talent distribution (next section).

---

## 5. The talent distribution (one scale) — implemented

Reference UTR (late 2025), our real-life anchor: pro men ~16.4 / women ~13.2;
**college men ~14.3 / women ~11.6**; U18/HS ~13.9–14.8 / ~11.1–11.9. The shape we
want is **bulb-like**: a high floor (bad players don't play college tennis — even
D3 is all-state-relative), a dense mass of similar talent, only a few elites — so
that at the top of each classification many players sit within a margin of error
and just play, outcomes not predetermined.

**One talent scale** (`app/ncaa.py:_talent_mean(strength, division, gender)`)
feeds everything — rosters, recruits, stars (STR is the separate results rating).

- **Rosters** (`_base_roster`): per-program talent from `_talent_mean` (D1>D2>D3,
  men a ceiling above women), tight within-program spread (σ≈2.5 → dense
  lineups), and **class-scaled maturity** (`_CLASS_MATURITY`, Fr→Sr 0.83→0.99) so
  college ability is realized with headroom for freshmen. The grade-80 / STR-57
  clamp is the **governor** — the best sit near, but rarely at, the top.
  Resulting D1-men ability: UTR-eq p50 ≈ 11.6, p99 ≈ 14.2; D1 women ≈ 9.3 / 12.1;
  D3 lower. Top-12 programs' #1s span just **~0.8 UTR** (a margin of error), and
  elite-vs-elite duals go to the higher-rated only ~69%.
- **Recruits** — **one national pool per gender** (`get_recruits`, thousands),
  split nationally / by state / internationally; **every program D1–D3 recruits
  from the same pool**, ranks and stars are national (no per-division pools or
  stars). Drawn from the same `_talent_mean` scale (centred on a mid D2 program),
  tight σ → thin margins between tiers, with development headroom (juniors stay at
  the low maturity range, so they grow into rosters and the distribution persists
  year over year). The world's annual signing pool (`world.national_class`) uses
  the identical scale.
- **Stars are a function of talent** — rank within the (gender) class, a full
  pyramid (`juniors.TIER_CUTOFFS`): Blue Chip ~1.5%, 5★ ~2.5%, 4★ 8%, 3★ 18%,
  2★ 28%, 1★ 27%, unrated 15%. Thin gaps between tiers; talent develops, so a
  lower star can still become elite, and allocation lets real talent fall to a
  smaller program.
- **STR** stays results-based (§3): assumed from the ability prior at first, then
  earned by match play.

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

- **Recruiting allocation** — model which programs sign which recruits (talent
  can fall to a smaller school); today's roster/recruit talent is calibrated but
  the matching is simple.
- **Multi-year stability** — sim several years and confirm the distribution holds
  as recruits develop and replace graduates (the scales are aligned for this, but
  it wants a dedicated eval).
- Distinct *playstyles* emerging from the attribute mix (big server, grinder,
  shot-maker) — only if they arise from talent/structure, not bespoke dials.
- Doubles as its own model (currently synthetic pair-average).
- Slightly widen the men/women top gap (currently ~2.3 UTR vs ~2.7 real) if
  desired; the lever is `_TALENT` women bases in `app/ncaa.py`.
