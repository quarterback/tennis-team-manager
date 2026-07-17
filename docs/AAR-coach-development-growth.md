# AAR — Coach development score drives player growth (±30%)

**Date:** 2027-07-17
**Scope:** `coaches.development_multiplier` (+ `DEV_MULT_LO/HI`, `_DEV_SCORE_LO/HI`),
`world.developed_rosters` (applies the multiplier to the weekly development drip).

## The gap this closes

Coaches carried a full development identity — `development_score`,
`teaching_skill`, `training_design`, the **Development Guru** archetype — that was
computed, shown on staff pages, and **consumed by nothing in the sim**. Player
growth was purely player-intrinsic (`interest_rate × GROWTH_K × tier_mult`).
`docs/AAR-player-coach-model-foundation.md` §next-steps listed the wire
explicitly ("connect coach development_score to year-over-year player growth once
rosters become persistent"); rosters became persistent, the wire never landed.
The post-season validation study made it visible: coach quality predicted match
outcomes at a coin flip.

## Owner's choice (locked): STRONG — ±30%

Coaching is a major roster-building axis, not a nudge: a dev-guru mid-major
visibly out-develops a lazily-coached blue blood over a class's four years.
(Offered moderate ±15% / strong ±30% / leave-display-only; owner picked strong.)

## How it works

`coaches.development_multiplier(school)` → the program coach's
`development_score` mapped linearly to a growth multiplier, then
`world.developed_rosters` applies it to every weekly development slice:
`p.develop(stagger_scale × dm)`. Same coach source the recruiting sim reads
(`program_coach`), so one identity drives both.

**Calibration matters — read before retuning.** Generated development_scores
OCCUPY roughly 40–65 (clustered near 50), not the whole 20–80 grade scale. The
multiplier is therefore anchored on the band coaches actually live in:
**35 → 0.70×, 50 → 1.00×, 65 → 1.30×**, clamped to [0.70, 1.30]. Anchoring on
20–80 instead compresses the real-world spread to ~±12% and silently downgrades
the owner's "strong" choice (the first cut of this feature made exactly that
mistake). Measured across D1 men: min 0.82×, median 1.02×, max 1.29×.

## Where it deliberately does NOT apply

- **Juniors / recruits** (pre-college development, `junior_circuit`,
  `regress_to_younger`) — no coach yet.
- **Pro decline** (GTT `decline()`) — aging, not coaching.
- **Match dice** — still no in-match coach effect; this shapes *rosters*, which
  is how coaching shows up in results.

## Effects to expect

- STR/OVR curves per program now tilt by staff quality; over seasons a strong
  developer's recruits finish closer to ceiling (a fast developer on a 20-point
  gap lands ~3 OVR / ~2 STR higher by senior year under the best coach vs the
  worst) — compounding across a roster and multiple classes.
- Dynamic prestige will pick this up organically: over-performing development →
  better results → prestige momentum → better recruiting. Watch that the loop
  stays sane over long saves (it's damped by the ±0.20 momentum cap).

## Verification

- Bounds respected across all D1 programs; deterministic per school; `""` → 1.0.
- Spread measured: 0.82–1.29× (D1 men, 379 programs).
- `developed_rosters` applies the per-school multiplier to every dev slice
  (hoisted to a per-school dict — no per-week recompute).

## Watch-outs

- Tests asserting exact developed values/rankings at a fixed seed will shift
  once (the multiplier changes every program's growth). Determinism per seed is
  unchanged.
- If coach generation variance is ever retuned, re-measure the observed
  development_score band and re-anchor `_DEV_SCORE_LO/HI` — the ±30% promise is
  about the REAL spread, not the theoretical grade scale.
