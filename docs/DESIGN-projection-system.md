# DESIGN — The Honest Analyst vs. the Omniscient Engine

**A viability & design reference for DARKO/LEBRON-style projection systems across three sims**

Status: **design document only — nothing here is built.** This is the saveable
reference for whether (and how) the mental models behind real-world basketball
analytics systems — DARKO (darko.app) and LEBRON (bball-index) — can be applied
to the data our fictional sports sims already generate. It covers all three
games, with **tennis-team-manager as the first build target**, hybrid-baseball
(O27) as the data-rich lab where the method is easiest to work out, and
viperball third.

Written 2026-07-02 against the state of all three repos on branch
`claude/darko-projection-system-m4ri1q`. Every file/line cited was verified
this session.

---

## 1. Thesis: the honest analyst vs. the omniscient engine

DARKO and LEBRON exist to solve one problem: **true talent is hidden, and
observed results are noisy.** Is this breakout real? Is this slump decline or
variance? A real-world modeler builds an estimator of hidden talent from noisy
box scores — and can *never* check the answer, because the answer doesn't
exist anywhere.

Our sims are different in a way that is both a technical advantage and a
fiction opportunity: **the engine knows the answer.** Every player in all three
games has hidden true ratings (tennis: 51 attributes on a 20–80 scale with
`current` vs. hidden `potential`; O27: 20–80 scout-scale ratings; viperball:
eleven 0–100 ratings plus hidden potential stars). The observed stats are
generated *from* those ratings through the engine's noise.

So the design rule for everything in this document:

> **Projections consume only what a fan could see** — box lines, match
> results, schedules, ages, class years, transactions. The hidden ratings are
> never an input. They are the **validation scoreboard** ("Truth Bench", §6):
> a private answer key for measuring how good the honest analyst's estimates
> are. No real-world system has ever had this.

Why this is the right choice (vs. letting the projection peek at ratings, as
tennis's `app/scout_intel.py` god-mode Analytics Bureau already does):

- It makes the tool *interesting*. A god-mode readout is a debug view. An
  honest estimator is a character — an in-universe stats site trying to guess
  what the engine knows, and being measurably right or wrong.
- It makes hyperparameter tuning trivial. DARKO uses a differential-evolution
  optimizer to pick its decay rates because it can only score itself on
  out-of-sample prediction. We can grid-search decay rates directly against
  truth (§6).
- The gap between honest estimate and truth is itself a displayable stat
  ("the market is sleeping on this player").

---

## 2. The mental models, de-basketballed

What follows is DARKO/LEBRON translated out of basketball into sim-general
terms. These eight ideas are the whole toolkit; every proposed tool in §3–§5
is a composition of them.

### 2.1 Per-stat exponential decay (no arbitrary windows)

DARKO weights *every game a player has ever played* by `β^t` (t = days ago),
with β chosen per stat. This kills the arbitrary-endpoint problem ("last 10
games", "this season") — there is no cliff where old data suddenly stops
counting; it just fades. Fast-moving stats (usage, minutes) get fast decay;
sticky stats (free-throw%) get slow decay.

**Already in the codebase:** tennis's STR rating does exactly this —
`HALF_LIFE = 12.0` matches, weight `0.5 ** (age / HALF_LIFE)` per match
(`app/str_rating.py:36,82`). What STR lacks is the *per-stat* part: it decays
one composite rating, not components.

### 2.2 The Kalman intuition: carry an estimate *and* an uncertainty

Strip the filter theory; the useful residue is two lines:

```
surprise   = observed − predicted
new_est    = old_est + gain × surprise        where gain = prior_var / (prior_var + obs_noise)
```

The update is big when you're uncertain (new player, post-transfer) and the
observation is informative; small when you're confident and the observation is
noisy (one match, high-variance stat). Tracking `(mean, variance)` per player
per stat — instead of a bare mean — is the single biggest structural upgrade
over every rating any of the three sims currently computes. It's what makes
the rest possible: uncertainty bumps (§2.6), rookie priors (§2.7), calibration
scoring (§6).

### 2.3 Aging curves, fit empirically per stat

DARKO fits an independent aging curve for every stat, because skills age
differently (athleticism first, craft last). All three sims already *have*
aging — but prescriptively, inside the engine (tennis `app/development.py`
growth tiers; O27 `o27v2/development.py` `_ATTR_AGE_PROFILE` at :67, where
speed/power decay fastest and contact/eye/command are stickiest; viperball
`engine/development.py` `_PRO_AGE_CURVES`). The honest analyst doesn't get to
read those. Instead: fit age effects from observed career data with the
**delta method** — for every player observed at both age A and A+1, average
the stat change; that's the curve at A. O27's age-stamped
`player_career_lines` table makes this a single SQL query. The fitted curve
becomes a drift term applied to every player's estimate at season rollover.

(Bonus meta-experiment, O27: compare the empirically fitted curve to the
engine's actual `_ATTR_AGE_PROFILE`. "Can the analyst rediscover the engine's
aging law from box scores alone?" is a genuinely novel validation no
real-world system can run. §4.4.)

### 2.4 Context adjustments — only where the schedule makes them matter

DARKO adjusts for home court, rest, opponent, and league-wide seasonality,
re-estimated continuously. The transferable principle is the *re-estimated*
part — O27 already has this as a house convention (park factors, linear
weights, WP tables all re-derived from league data per render, never
hardcoded). The caution is the *only where needed* part: DARKO needs opponent
adjustment because NBA schedules are unbalanced. A round-robin league doesn't.
Rule of thumb per game: college schedules (tennis, viperball CVL) are
unbalanced → opponent strength matters (tennis STR already anchors every match
rating on opponent STR, which *is* the opponent adjustment). Balanced pro
schedules → skip it until the Truth Bench shows it earns its keep.

### 2.5 Correlated updates: believe a spike more when its siblings move

DARKO is "more credulous" of a 3P% jump if FT% jumped too, because they share
a latent cause (shooting touch). General form: when two observed stats load on
the same hidden skill, a simultaneous move in both is stronger evidence than
either alone. Cheap implementation (no covariance matrices): define 2–3
sibling groups per game and let a confirmed sibling move scale the gain up
(e.g. ×1.25) on the other. O27: exit velocity ↑ + hard-hit% ↑ ⇒ believe the
power spike in HR rate. Tennis (post box-stat persistence): ace rate ↑ +
service-hold% ↑ ⇒ believe the serve improvement.

### 2.6 Regime changes widen uncertainty

DARKO raises its learning rate when a player changes teams. Same lever
everywhere: any fan-visible discontinuity — transfer portal move, promotion
to a new division/league, position/archetype change, return from long injury
— multiplies the variance (e.g. ×2), which via §2.2 automatically makes the
next few observations count more. Tennis has the richest set of visible
regime events of the three games (fall portal, preseason portal, division
moves, medical redshirts).

### 2.7 Rookie priors: start wide, learn fast — or import a feeder résumé

DARKO has no NCAA data, so rookies start at a near-uniform prior and get
learned on the fly. Two of our sims can do *better* than DARKO here, because
they have fan-visible feeder data: tennis has the junior circuit (`app/
junior_circuit.py` runs real matches through the engine; `junior_str` is a
results-based pre-college rating) and viperball has the CVL→WVL graduate
pipeline (`engine/player_career_tracker.py`). The pattern: initialize a
newcomer at *feeder rating translated by an empirically fit league-conversion
factor*, with variance reflecting the translation's historical error. O27's
youth/college pipeline can seed the same way. Where no feeder data exists:
league-mean-for-age, maximum variance.

### 2.8 LEBRON in one paragraph — and where it does/doesn't apply

LEBRON blends two witnesses to a player's value: a **box prior** (what the box
score says they should be worth) and **luck-adjusted regularized on-off**
(what the score did when they were on vs. off the floor), weighted by sample
reliability. The blend matters in basketball because ten players interact and
the box score misses defense/spacing. **Fit check per game:** baseball-shaped
sports credit almost everything individually — in O27 the box *is* the impact,
so the DPM analog is just the projected components rolled up through linear
weights (no on-off exists in a 27-out continuous half). Tennis is even more
individual — a player's "impact" on a dual is their line result, already
STR's input. **Viperball is the one genuine LEBRON candidate**: 11-a-side,
two-way players, laterals and kick coverage that box stats undercount, and a
per-play EPA stream to build on/off from (§5.3).

### 2.9 The right-sizing manifesto

Say it explicitly so future sessions don't over-build: **no gradient-boosted
trees, no differential-evolution optimizers, no Kalman library.** DARKO's ML
apparatus exists because the NBA is small-sample, unbalanced, and unlabeled.
Our sims are none of those: we can generate a thousand seasons of training
data on demand, and we have labels (the hidden ratings). The full method is:

    exponential decay  +  shrinkage to a prior  +  empirical aging bins
    +  variance tracking  +  a handful of ×k adjustments (§2.4–2.7)

with every constant (half-lives, shrinkage k, regime multipliers) picked by
**grid search over 3–5 candidates scored on the Truth Bench**. That is the
entire modeling stack. Anything fancier must first beat this on the bench.

---

## 3. tennis-team-manager — first build target: **STR+**

### 3.1 Why tennis first, and why it's cheap

The owner plays tennis right now — and the repo has already built most of the
foundation. `app/str_rating.py` is, unprompted, a DARKO cousin:

| DARKO idea | STR today (`app/str_rating.py`) |
|---|---|
| Exponential decay | `HALF_LIFE=12` matches, `WINDOW=30` (:35–36, :82) |
| Opponent adjustment | every match rating anchored on opponent STR (:50–58) |
| Reliability / confidence | `reliability = min(1, wsum/RELIABILITY_K)` (:88) |
| Shrinkage to a prior | `raw = rel×raw + (1−rel)×prior` (:90) |
| Population consistency | `converge_ids()` fixed-point solve (:94) |

The live per-season version (`seasonmode.season_player_str`) already runs this
over `lines_json` match data. So the tennis project is an **extension, not an
invention**. Its working name: **STR+**.

### 3.2 The one prerequisite: persist the box stats

The engine computes real box stats at full fidelity — aces, double faults,
winners, unforced errors, break points (`MatchResult.stats` in the engine's
match path) — and then **drops them for season play**. Only per-set game
scores survive into `duals.lines_json` (serialized in `app/season.py:249-293`;
the `match_stats` table in `app/db.py` is a legacy standalone-match path,
unused by seasons). Without those components, STR+ can decay and regress only
the composite; with them, it gets the per-stat layer that makes it DARKO-like.

**Fix (small):** either a new `match_box_stats` table keyed by
`(season_id, dual_id, slot, pid)`, or extend each `lines_json` line entry with
a `stats` dict per player. The lines already carry `home_pid`/`away_pid`, so
the join key exists. Backfill is impossible (stats aren't stored), so this
ships first and data accumulates from then on — one more reason it's step 1.

### 3.3 STR+ design

Everything observed-only. Four additions to STR, in build order:

1. **Variance tracking.** Carry `(mean, var)` per player instead of
   `(mean, reliability)`. Reliability becomes derived (`var → rel`), existing
   UI keeps working. Enables §2.2 updates and all uncertainty features below.
2. **Per-skill sub-ratings** (needs §3.2): decay-weighted serve rating (ace
   rate, hold%), return rating (break%), steadiness (UE rate), clutch (break
   points, deciding sets — note `lines_json` already has per-set scores, so
   third-set records are computable today). Composite STR stays the headline;
   sub-ratings explain *where* it's moving. Sibling groups (§2.5): serve =
   {ace rate, hold%}; steadiness = {UE rate, games lost from winning
   positions}.
3. **Empirical class-year aging term.** Fit Fr→So→Jr→Sr deltas from
   `Prospect.history` career entries (per-season w/l and line data persisted
   in `world_roster`) via the delta method (§2.3), keyed off
   `world._base_class` to strip `RS-` tags. Apply as a drift at rollover —
   the analyst's expectation of summer development, to be confirmed or
   refuted by fall results.
4. **Regime-change variance bumps** (§2.6): fall/preseason portal move,
   division change (riser/cascade), medical-redshirt return. All fan-visible
   via the transfers surfaces.

### 3.4 Tennis's unique validation: a three-way contest

Tennis alone has **three independent estimates of the same hidden quantity**,
all already in the codebase or specified here:

1. **Truth** — `current` attribute overalls (hidden; `app/development.py`).
2. **The scouts** — `scouting_report()` fog-blurred reads, and the
   recruiting-stars vs. TennisEye results-stars contrast (`app/juniors.py`).
3. **The honest analyst** — STR+, box/results only.

The Truth Bench question "does the honest analyst beat the scouts?" is an
in-fiction storyline (analytics department vs. scouting department) *and* a
real measurement. The god-mode Analytics Bureau (`app/scout_intel.py`, `/intel`
routes) already computes talent-vs-placement gaps; STR+ slots in as the third
column, and Bureau reports can rank players by |analyst − truth| to show where
box-watching fails (small samples, injury-masked results, weak schedules).

### 3.5 Tennis UI surfaces (§7 patterns × existing idioms)

- **Active leaderboard**: extend `/rankings`-style tables with STR+ columns +
  uncertainty band; a "risers/fallers this week" cut mirrors the existing
  movement polls (`seasonmode`, AP-poll deltas).
- **Trajectory chart**: the `/player/<pid>` page already has `player_journey`
  (rank progression) — add the STR+ talent-over-time line with a shaded
  variance band; portal moves/injuries as vertical event markers.
- **Scatterplot**: seed vs. results is already the TennisEye-vs-stars
  contrast; generalize to pick-your-axes (STR+ vs. scout stars; serve vs.
  return sub-rating) on a new page under `/intel`.
- **Methodology page**: the site already has `/methodology`; STR+ gets a
  section there, DARKO-About-style.

### 3.6 Tennis viability verdict

**High — the cheapest path to a working system.** Foundation (STR) exists and
is calibrated; the blocker is one persistence gap (§3.2) that's a small,
additive schema change. Effort guess: persistence ~1 session; STR+ core +
bench ~1–2 sessions; UI ~1 session. Risk: `lines_json` post-clinch abandoned
lines (`completed=False, partial`) need a weighting rule (count partials at
reduced weight, like STR's opponent-reliability discount).

---

## 4. hybrid-baseball / O27 — the method lab: **TRACER**

*(True-talent Rate Accumulation with Contextual Empirical Regression — the
O27 true-talent tracker.)*

### 4.1 Why O27 is where the method gets worked out

O27 has the best data of the three by a wide margin, already relational and
queryable:

- **`game_pa_log`** (`o27v2/db.py:507-560`): one row per ball-in-play with
  contact quality, `exit_velocity` / `launch_angle` / `spray_angle`,
  `pitch_type`, ball-strike count, fielder credit, and full pre/post
  base-out-score stamps — RE24/WPA-grade event data without engine replay.
- **`player_career_lines`** (`db.py:1090`): per-season lines **stamped with
  age**, stable `player_id` across seasons — exactly the delta-method aging
  dataset (§2.3).
- A mature analytics module (`o27v2/analytics/`) with linear weights, xwOBA
  and its luck delta, RE24, empirical WP/WPA/LI, Luck Ledger resampling,
  park-adjusted wRC+ — i.e., the *descriptive* half of a projection system
  is done, including the house convention of re-deriving all constants from
  league data.

What's missing is precisely the DARKO layer: nothing in the repo projects
forward, decays history, or carries uncertainty.

### 4.2 TRACER design

Per player, per stat: decayed weighted rate over full history →
shrunk toward a park/league prior by `n_eff / (n_eff + k)` (the repo already
does this shape for wERA, shrunk toward a 9-out league prior, and for
Fielding OAA reliability regression) → aging drift (§2.3) → variance tracked
throughout.

**Stat menu, split by signal speed** (each gets its own grid-searched
half-life, per §2.1):

- *Fast-stabilizing process stats* (short half-life, low obs noise): K%, BB%,
  mean EV, hard-hit%, LA distribution, stay/run choice rates, swing-split
  conversion.
- *Slow outcome stats* (long half-life, heavy shrinkage): BABIP, HR/FB, RISP
  performance, wERA components.

**Adjustments:** park (reuse wRC+ machinery); sibling groups (§2.5): {EV,
hard-hit%} → HR rate, {K%, swing-1 conversion} → contact skill; team/park
change and streak-state discontinuities as variance bumps (§2.6); rookie
priors seeded from the youth/college pipeline where visible (§2.7). Opponent
adjustment: check schedule balance first; likely skip (§2.4).

**Roll-up ("xRun Impact" — the Box DPM analog):** projected component rates →
existing `o27v2/analytics/linear_weights.py` → one projected-wOBA/run-value
number per player per sim date. Per §2.8 there is no on-off in this sport, so
box roll-up *is* the impact metric — the doc says this explicitly so nobody
tries to bolt an on-off term onto a sport that can't have one.

### 4.3 The one convention deviation: `talent_snapshots`

House style is "re-derive everything per render." Trajectories (§7) need
*history of estimates*, which can't be re-derived cheaply per page load. New
table: `talent_snapshots(player_id, sim_date, stat, mean, var)`, written by
the sim loop or a post-day hook. This is a deliberate, called-out deviation;
everything else in TRACER stays re-derivable. New stats get registered in
`docs/stats-reference.md` and covered in `tests/test_stat_invariants.py`, per
repo convention; the build closes with a `docs/aar-<slug>.md`.

### 4.4 O27 Truth Bench extras

Beyond the shared harness (§6): the **aging-recovery test** — fit aging curves
from `player_career_lines` alone and compare shape/peak/decline-onset per
attribute family against the engine's `_ATTR_AGE_PROFILE`
(`o27v2/development.py:67`). Also the cleanest place to grid-search
half-lives, because seasons are cheap to generate (`manage.py sim N`) and the
data volume is highest.

### 4.5 O27 UI surfaces

- `/projections` active leaderboard beside `/leaders`, with the Native↔XO
  toggle pattern.
- `/player/<id>/trajectory`: talent-over-time in house style —
  **server-rendered inline SVG** (as in `sp_chart.html`,
  `distributions.html`), mean line + variance band, season boundaries and
  team changes as markers. This page slots naturally next to the existing
  `/player/<id>/o27i` percentile page.
- Pick-your-axes scatter: extend `/compare`; the flagship preset is
  *observed wOBA vs. TRACER-projected wOBA* — the luck quadrant chart
  (over-performers top-left, sleepers bottom-right), which is the projection
  system's version of the existing xwOBA luck delta.
- Methodology section on `/analytics`; Markdown export route (house pattern)
  so projections are LLM-ingestable like everything else.

### 4.6 O27 viability verdict

**Very high — zero data gaps.** All inputs exist today at event grain with
ages and stable ids; the analytics module has an obvious `projections.py`
seat. Effort guess: TRACER core ~2 sessions; bench + tuning ~1; UI ~1–2. Open
questions for the build session to resolve: (a) is the schedule balanced
enough to skip opponent adjustment? (b) is there an engine ratings→expected-
rates mapping usable to score projections in stat units (if not, Truth Bench
falls back to rank correlation, which is sufficient).

---

## 5. viperball — third target: extraction first, then **VTR** and **COBRA**

### 5.1 The prerequisite that gates everything: an analytics extraction layer

Viperball's SQLite is a generic JSON blob store (`engine/db.py`: `saves` /
`save_history`, everything serialized whole). Per-play logs with EPA, per-game
GameLogs, and `SeasonStats` (~60 fields, retaining game logs) all exist — but
inside blobs, unqueryable. **Phase 0 is an ETL** that walks saves and emits
flat per-player-per-game rows (SQLite tables or parquet) with stable player
ids via `engine/player_career_tracker.py`. Scope it as its own workstream;
nothing below starts until it lands.

### 5.2 VTR — Viper Talent Rating (the DARKO analog)

Decayed, shrunk, role-specific per-game rates: EPA/play on carries and
laterals, kick-pass efficiency, ZBR components for zerobacks, coverage rates
(`SeasonStats` already tracks `points_allowed_in_coverage` /
`coverage_snaps`), success rate and explosiveness from `engine/epa.py`.
Archetype-group priors (Zeroback/Viper/Flanker/Keeper) instead of one league
prior. Aging drift from `_PRO_AGE_CURVES`-shaped empirical fits on career
tracker data (§2.3). **Rookie priors are viperball's best trick (§2.7):**
CVL→WVL translation factors fit from graduates who played in both — the sim
has the "college data" DARKO wishes it had.

### 5.3 COBRA — Composite On/off + Box Rating Adjustment (the LEBRON analog)

Viperball is the one game where LEBRON's two-witness blend genuinely applies
(§2.8): 11-a-side, two-way players, box-invisible work (lateral chains, kick
coverage). Design: box prior from WAR/ZBR/VPR (`engine/viperball_metrics.py`),
impact witness from on-field EPA differential while a player participates,
**luck-adjusted by stripping the Delta-Yards field-position component exactly
as `engine/dtw.py` ("Deserve To Win") already does at team level**, blended by
snap-count reliability. **Feasibility gate (state the finding either way in
the build session): do per-play logs record participants?** If plays don't
name the players on the field, on-off is unbuildable and COBRA degrades
gracefully to luck-adjusted box only (still worthwhile — that's "Box DPM").

### 5.4 Viperball UI + verdict

Surfaces go in the server-rendered stats_site (`stats_site/router.py`) beside
the existing `/kenpom`, `/luck`, `/ratings` pages: `/projections` leaderboard,
`/trajectories`, scatter presets (VTR vs. WAR; DTW-luck vs. Pythag-luck).
Ranking-composite note: `engine/ranking_composite.py` has 38 team ranking
algorithms; VTR-aggregated-to-team makes a fitting 39th.

**Verdict: medium — highest ceiling, most prerequisite work.** The analytics
culture is the strongest of the three (EPA, DTW, KenPom-style efficiencies all
exist) and COBRA would be the most novel tool in any of the games, but the
blob-store ETL is real work and the participation-logging question could
halve COBRA's scope. Effort guess: ETL ~1–2 sessions; VTR ~2; COBRA ~2
(if participation data exists).

---

## 6. The Truth Bench — shared validation harness

One as-of replay script per repo (working name `analytics/truth_bench.py` in
each): recompute the honest projections using **only data dated ≤ t**, join to
the engine's hidden ratings snapshot at t, score. Run over a sweep of t across
generated seasons.

**Truth fields per game** (project *current* talent, never hidden potential —
the analyst estimates what a player is, not their ceiling):

| Game | Truth |
|---|---|
| tennis | `current` attribute composite / engine-driver overalls (`app/development.py`) |
| O27 | 20–80 ratings on `players` (contact, power, eye, speed, pitcher_skill, command, …) |
| viperball | the eleven 0–100 `PlayerCard` ratings |

**Score menu (same four everywhere):**

1. **Rank quality**: Spearman correlation of projected talent vs. truth
   composite at each t (within position/archetype group where roles differ).
   Works even without a ratings→stat-units mapping.
2. **Predictive accuracy**: MAE (or log-loss for win/loss) on the *next N
   observed events* vs. three dumb baselines — season-to-date mean, career
   mean, last-K window. **The projection must beat all three or it doesn't
   ship.** This is the honest, DARKO-style score that needs no truth at all.
3. **Calibration**: do 80% intervals cover truth (and future outcomes) 80% of
   the time? This is what variance tracking (§2.2) buys, and what no bare
   rating can be scored on.
4. **Game-specific extra**: O27 aging recovery (§4.4); tennis three-way
   analyst-vs-scouts-vs-truth (§3.4); viperball COBRA-vs-raw-WAR at
   predicting next-season team results.

**What the bench is *for*, day to day:** hyperparameter selection. Every
constant in §2.9's stack — per-stat half-lives, shrinkage k's, regime
multipliers, sibling gains — is a 3–5-point grid search scored on the bench.
This replaces DARKO's optimizer outright, and it's the concrete payoff of
owning the engine.

---

## 7. Presentation surfaces (the darko.app patterns)

The darko.app nav is a checklist of surfaces worth having, independent of the
math. Mapped to house idioms per game in §3.5/§4.5/§5.4; the general patterns:

1. **Active Leaderboard** — *current* talent estimates as of today, not
   season-to-date averages. The defining page: it answers "who is good *right
   now*" and updates every sim day. Always show the uncertainty alongside the
   estimate.
2. **Trajectories** — the graph: talent-over-time per player, mean line +
   shaded variance band, event markers (transfers, injuries, team changes,
   season boundaries). This is the page that shows a breakout *as it is being
   believed* — the variance band narrowing around a rising line. Requires
   snapshot persistence (§4.3's `talent_snapshots` pattern, per game).
3. **Scatterplot, pick-your-axes** — the exploration tool. Flagship preset in
   every game: *observed production vs. projected talent* — the luck quadrant
   (lucky over-performers vs. sleeping breakouts). Others: sub-skill vs.
   sub-skill; projection vs. scout grade (tennis).
4. **Methodology page** — darko.app's "What is DARKO?" page is half the
   product: it makes the numbers trustworthy and the system a character. Each
   game already has a home for it (tennis `/methodology`, O27 `/analytics` +
   `docs/stats-reference.md`, viperball `/ratings-glossary`).
5. *(Skipped deliberately:)* darko.app's Longevity and Lineups pages are
   basketball-specific (minutes/lineup projections); no analog earns its keep
   in these sports. Playing-time prediction is DARKO's own weakest stat — we
   lose nothing.

---

## 8. Cross-game viability summary & roadmap

| | tennis | O27 | viperball |
|---|---|---|---|
| Existing foundation | STR (decay+prior+reliability) ✅ | full descriptive analytics suite ✅ | EPA/DTW/38 rankings (team-level) ✅ |
| Event-grain data | per-set/per-line (no box stats persisted) ⚠️ | per-BIP with physics + state ✅✅ | per-play w/ EPA, but in JSON blobs ⚠️ |
| Career data w/ ages | Prospect.history ✅ | age-stamped `player_career_lines` ✅✅ | career tracker ✅ |
| Prerequisite work | persist box stats (small) | none | ETL extraction layer (medium) |
| Novel payoff | analyst-vs-scouts contest | aging-law recovery; luck quadrant | COBRA (the true LEBRON analog) |
| Verdict | **High — cheapest win** | **Very high — zero gaps** | **Medium — highest ceiling, most prep** |

**Roadmap** (each phase independently shippable; order per owner priority —
tennis first because it's the game being played right now):

- **Phase 1 — tennis**: box-stat persistence → STR+ (variance, sub-ratings,
  aging term, regime bumps) → Truth Bench three-way → leaderboard/trajectory/
  scatter UI. AAR per repo convention.
- **Phase 2 — O27**: TRACER core + `talent_snapshots` → Truth Bench +
  half-life grid search (tune before displaying) → UI + `stats-reference.md`
  registration + invariants + AAR. O27 is also where method questions
  discovered in Phase 1 get answered cheaply (most data, fastest season
  generation).
- **Phase 3 — viperball**: extraction ETL → VTR (+ CVL→WVL rookie
  translation) → COBRA (gated on the participation-logging finding).

**Open questions each build session must resolve (or re-flag):** O27 schedule
balance (§4.6a); engine ratings→expected-rates mapping availability (§4.6b);
viperball per-play participant logging (§5.3); tennis partial-line weighting
(§3.6).
