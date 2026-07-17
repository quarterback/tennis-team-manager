# VALIDATION — NCAA post-season as a test set (engine calibration study)

**Date:** 2027-07-17 · **Harness:** `scripts/postseason_validation.py` · **Engine:** fast model
**Corpus:** 1,136 NCAA-tournament duals / 5,309 completed singles courts — D1–D4 ×
men/women × 2 world seeds (2026, 2027), full seasons simulated end to end.

> Companion doc to `docs/AAR-postseason-best-six-lineups.md` (a lineup bug this
> study's box scores surfaced) and the interactive report artifact. Re-run any
> time with `python3 scripts/postseason_validation.py D1:men D1:women D2:men
> D2:women D3:men D3:women D4:men D4:women --seeds 2` (add `--full` for the
> point-by-point engine); outputs `duals.csv`, `singles.csv`, `summary.json`
> under `scripts/out/postseason/`.

## Verdict: well-calibrated

Talent tells, but college tennis stays upset-prone — and the engine lands the
balance its design doc promises. No retuning needed as of this run.

## 1. Calibration — favorite win% by talent gap (singles courts)

Favorite = higher OVR player; gap in UTR-equivalent units (÷1.677 STR). The
engine's own design targets (engine/fast.py TUNE docstring) alongside:

| UTR gap | measured | target | n |
|---|---|---|---|
| 0–0.5 | 53.0% | — | 934 |
| 0.5–1.0 | 55.4% | — | 1,116 |
| 1.0–1.5 | **63.8%** | 63% | 963 |
| 1.5–2.0 | **70.6%** | 69% | 653 |
| 2.0–3.0 | **77.6%** | 77% | 826 |
| 3.0+ | **86.9%** | 87% | 817 |
| overall | **66.7%** | ~65% | 5,309 |

Every targeted bucket sits within ~1.6 points of its design target.

## 2. Reliability — are the tails too fat? (No.)

Courts grouped by the engine's own implied win-prob for the favorite (exact:
Monte-Carlo of the real fast model, 6,000 sims per rating gap, outcomes labeled
by the ENGINE favorite):

| engine says | actually won | n |
|---|---|---|
| 40–50% | 49.4% | 168 |
| 50–60% | 56.7% | 2,288 |
| 60–70% | 70.7% | 1,612 |
| 70–80% | 79.3% | 749 |
| 80–90% | 88.4% | 361 |
| 90–100% | 94.7% | 131 |

Worst band error ≈ +5.7 pts (mid-band favorites slightly over-perform); the top
band shows no blow-off — a clearly better player is not leaking losses.

## 3. Upsets — right shape, right size

Dual upset = lower top-6-OVR roster wins: **38.3% overall**, falling
monotonically with the gap — 55.4% (gap 0–5) → 42.9% (5–10) → 41.5% (10–20) →
27.8% (20–40) → 18.4% (40+). All eight division×gender universes land in a
35–43% band; no chalk-only or chaos outlier.

## 4. Scoreline realism

- Dual margins: 4–3 **29%**, 4–2 **27%**, 4–1 **27%**, 4–0 **17%** — a third of
  tournament duals go the distance.
- Singles: 65.1% straight sets / 34.9% three-setters.
- **Doubles-point leverage: the side that takes the doubles point wins 71.0% of
  duals** (n = 1,136).

## 5. What predicts a dual winner

| metric | accuracy |
|---|---|
| top-6 engine rating | 61.9% |
| committee seed | 61.9% |
| top-6 OVR / top-6 STR / Power 6 | 61.7% |
| coach match-tactics grade | **47.0% (coin flip)** |

Two structural facts explain this table:

1. **OVR ≡ STR at the court level.** The fast model decides every game from one
   signal — the gap in `player.overall` — and STR is
   `overall_to_str(current_overall())`, a monotone transform of the same
   attribute table. They cannot disagree on a singles favorite; they diverge
   only when summed across a team (which is why all team metrics cluster).
2. **Coaching never touches the match dice.** There is no per-match coach /
   form / archetype modifier — coaching acts upstream (development, recruiting,
   lineups). The coin-flip result is the design working, not a bug.

## Caveats

- **Run-to-run variance is real and by design:** injuries roll on
  `random.SystemRandom`, so dual-level figures (upset rate, predictor accuracy)
  wobble a few points between runs of the same seeds. The 5,309-court
  calibration and reliability tables are the robust signal.
- These are **fast-model** numbers. The world-hub Engine toggle (or `--full`)
  runs the point-by-point engine; overlaying its curve on §1 is the natural
  next check (the fast model was *tuned* to this curve; the full engine
  *derives* it from serve/rally mechanics).
- ~5% of duals carry an unresolved committee-seed label in the study's
  reconstruction; strength-based figures are used throughout.

## Bugs this study surfaced (fixed separately)

- **Postseason lineups**: AI programs rested starters in NCAA elimination duals
  → `docs/AAR-postseason-best-six-lineups.md`.
- Harness fixes from review (exact Monte-Carlo reliability, engine-favorite
  labeling, doubles-leverage reporting, tail-bucket target key) are in
  `scripts/postseason_validation.py` history.
