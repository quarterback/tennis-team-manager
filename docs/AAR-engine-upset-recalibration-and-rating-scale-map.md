# AAR — Engine upset recalibration, realism eval harness & rating-scale map

## Segment summary

Started as a question — *how good/realistic are the sim engine's outcomes, can we
run some tests?* — and became (1) a reusable **realism evaluation harness**, (2) a
deliberate **flattening of the win-rate curve** to make college tennis more
upset-prone, and (3) a **STR↔UTR↔WTN scale reference** on the Lineup Lab page.
The throughline, set by the user: *most college matches are within a margin of
error; results — not ratings — should decide them.* All work on
`claude/tennis-sim-engine-tests-tpbdfx` (PR #119); affected tests green.

## What was done

### 1. Realism eval harness (`scripts/eval_realism.py`)
The existing suite asserts invariants/determinism, not realism. Added a harness
that runs full simulated regular seasons and measures the two things the design
doc (`docs/match-engine-and-ratings.md` §6) says define realism:
- **Favorite win-rate bucketed by UTR gap** — the §4 calibration check.
- **Talent distribution** in UTR-equivalent units (percentiles, starter/team-#1
  medians, top-12 #1 spread), plus sanity checks (international share).

Run as `python3 scripts/eval_realism.py D1:men D1:women` (or `-m`). ~20–35s/division.

**Baseline finding (pre-change):** the engine's *calibration* was already solid
and consistent across all six division/gender combos, but the curve was steeper
than desired (favorite ~70% overall; 1.5–2 gap ~75%, 3+ ~94%). Also surfaced that
the doc's stated "D1-men ability p50 ≈ 11.6" is really the **team-#1** figure —
the full-roster median is ~7.7 (depth/walk-ons pull it down). Not a bug; the
absolute scale sitting a few UTR below real life is a documented playability
tradeoff. The user confirmed the elite ceiling (UTR ~15) is fine as-is — **no
talent change**.

### 2. Flatter win-rate curve (`engine/fast.py`)
The single dial. Lowered `skill_slope` **2.2 → 1.5** (and `tb_slope` 1.65 → 1.13,
holding the original 0.75 ratio) so the talent gap bites more gently. Picked
empirically with a sweep harness (`scripts/calibrate_slope.py`) against the user's
target curve; 1.5 was the best fit and held identically across D1 men/women.

Emergent D1 curve by UTR gap, **before → after**:

| ΔUTR gap | before | after | user target |
|---|---|---|---|
| 1–1.5 | 68% | 63% | toward the 0–0.5 floor |
| 1.5–2 | 75% | 69% | high-60s/low-70s |
| 2–3 | 84% | 77% | high-70s |
| 3+ | 94% | 87% | 86–89% |
| overall | 70% | 65% | — |

**Known limitation (by design):** a single logistic can't make 1–1.5 a true
coin-flip *and* keep 3+ near 87% — lowering the slope drags both down together. So
1–1.5 settles at ~63% (≈10 pts above the 0–0.5 floor), as flat as the dial reaches
without collapsing the high-gap buckets. This is the engine's *one* competitiveness
dial; everything else comes from the dense talent distribution (the user's point:
elite players are bunched within a margin of error, so upsets emerge naturally).

### 3. STR↔UTR↔WTN scale map (`app/web/server.py`, `templates/intel_lineups.html`)
A collapsed-by-default `<details>` toggle on the Lineup Lab page mapping the game's
native **STR 31–57** to **UTR 1.00–16.50** (upward-facing) and **WTN 40→1**
(inverse). Reference only — stays out of the way until expanded, so it never
disturbs the lineup chart. Rows are **derived from the canonical band**
(`app.str_rating.STR_MIN/STR_MAX`), not hardcoded, so the table can't drift from
the engine. Endpoints are exact; off-anchor UTR/WTN values are approximate
(separate proprietary systems). Conversion: `UTR = 1 + (STR−31)/26 × 15.5`,
`WTN = 40 − (STR−31)/26 × 39`.

### 4. Scripts runnable as documented (`scripts/*.py`) — Codex review on PR #119
Running a file as `python3 scripts/eval_realism.py` puts `scripts/` (not the repo
root) on `sys.path`, so `import app` failed. Added a one-line repo-root `sys.path`
bootstrap to both harnesses so the documented direct-script invocation works (and
`-m` still does too).

## Design principles (kept)
- **One competitiveness dial** (`skill_slope`/`tb_slope`); no situational
  match-time hacks. Talent decides; randomness is the residual.
- **Density, not the engine, drives upsets** — the elite band is naturally bunched,
  so we did NOT cap the talent ceiling to manufacture parity.
- Displayed scale stays internal STR 31–57; UTR/WTN are reference-only comparisons.
- Reference UI is additive and collapsed — never disturbs the working view.

## Validation
- Affected suites (`test_season`, `test_engine`, `test_dual`, `test_bracketing`,
  `test_str_rating`, `test_roster`) → **35 passing** after the slope change. The
  bracket-not-noise floor (`favs >= 8`) holds: team duals aggregate 7 points, so
  they're far less upset-prone than single matches.
- Lineup Lab page render-tested (200; scale panel + anchor rows present; chart
  intact). Scale rows verified against the reference table (STR 53 → UTR 14.12 /
  WTN 7.0).
- Curve re-measured with `scripts/eval_realism.py`; doc §4 table updated.

## What I did NOT change / growth
- **Talent scale untouched** — absolute UTR-eq still sits a few points below real
  life (a playability tradeoff); the user confirmed the elite ceiling is fine.
- The doc's "p50 ≈ 11.6" phrasing (really the team-#1 line, not roster median)
  is now clarified in §4 prose but the §5 line could still read more precisely.
- 1–1.5 bucket can't be pushed to a true coin-flip with one logistic; would need a
  non-logistic curve or per-flight terms (deliberately avoided — that's rigging).
