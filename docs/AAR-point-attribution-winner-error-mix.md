# AAR — box scores said a player hit zero winners (and another hit 47)

**Date:** 2026-07-31
**Status:** Landed (`engine/rally.py` TUNE — attribution shares recalibrated).
**Scope:** `rally._winner_share` / `_unforced_share` coefficients + clamp band;
no outcome, rating, or determinism change anywhere.

## Symptom

The expanded dual formats (docs/AAR-division-dual-formats.md) put the bottom of
D3/D4 rosters on recorded singles courts for the first time, and their box lines
read **W 0** — whole matches, sometimes whole seasons, without a single winner.
The owner flagged it from a D4 women's national final ("is it realistic to only
hit 3 winners in a match? really?"). The SAME final's D1 sibling had the inverse
absurdity hiding in plain sight: the champion's S1 line read **W 47 / UE 2** —
forty-seven winners and two unforced errors across three sets.

## The mechanism (not the tennis)

The engine decides WHO wins each point first, then labels HOW it ended:

* a server-won rally is a clean **winner** vs the returner's **forced error**,
  split by `_winner_share`;
* a returner-won rally is the server's **unforced error** vs a **returner
  winner**, split by `_unforced_share`.

Both shares swing linearly with attribute baskets anchored at `swing_ref = 0.68`
(a real D1 level). The baskets summed **~0.74** (winner) and — via a hidden `×2`
multiplier on the steadiness term — effectively **~1.36** (unforced). Across a
college talent range (~0.28–0.92) that swings the shares by ±0.30 and more, so:

* a deep-card D4 player went negative on every term and the `[0,1]` clamp pinned
  the winner share at **literal 0%** — every point they won was labeled an
  opponent error;
* an elite player collapsed the unforced share toward 0, so nearly every rally
  they lost on serve was labeled the OPPONENT'S winner — winner counts ballooned
  and UE counts vanished (the W 47 / UE 2 line).

A first patch floored the shares at 6% (`share_floor`). That killed the literal
zero but was symptom-treatment; the owner correctly rejected it and sent
research: the swings themselves were wrong.

## What the data says (owner-supplied sources)

* **Brain Game Tennis / Craig O'Shannessy** (all-Slam data): points end
  **~32% winners / 41% forced / 27% unforced for men; 29/37/34 for women** —
  "MEN = 70% errors / 30% winners" as the building block. The engine's own TUNE
  comment already cited these numbers and then swung right past them.
* **BigTime Stats / LSports (Tennis Abstract, Inpredictable)**: outcomes ride on
  tiny points-won margins (average match 55/45; <5% of matches won with under
  half the points) — the OUTCOME side of the engine already targets this and was
  not touched.

The key property: the winner/error mix is one of the most STABLE numbers in
tennis. It drifts a few points softer as the level drops (more unforced, fewer
winners); it never collapses to 0% or inflates past ~40%. Low-level tennis is an
error festival — but a festival with winners in it.

## The fix

Shrink the swings to hold the whole college spectrum inside the real band, and
keep the clamp band `[share_floor, 1 − share_floor]` (6%) as a backstop:

* winner basket `0.28/0.14/0.10/0.22` (sum ~0.74) → `0.10/0.05/0.03/0.08`
  (sum ~0.26);
* unforced basket `0.50/0.18` with the `×2` → `0.30/0.10`, multiplier removed.

Measured mix after (30 full matches per level, both players' points pooled;
winners include aces, DFs folded into UE — O'Shannessy's triple):

| Level | Winners | Forced | UE+DF |
|---|---|---|---|
| target (pro men) | ~32 | ~41 | ~27 |
| elite D1 | 31.9 | 36.7 | 31.4 |
| mid D2 | 21.3 | 41.3 | 37.4 |
| weak D3/D4 | 13.9 | 44.3 | 41.9 |

Per-match texture: an elite line now reads ~W 22 / UE 15–29; a deep-card line
~W 9–13 against ~25 errors. Error-dominated at the bottom, winner-capable at
every level, no impossible lines at either end.

## Why this was safe to retune (and how it was verified)

The shares only LABEL points already decided — they are drawn AFTER the rally
winner is known and consume the same RNG draw regardless of value. So the retune
is pure box-score texture: same-seed scorelines were verified **bit-identical**
under the old and new coefficients. No result, rating, STR, Power Index, or
determinism moves; the calibrated favorite-win rates are untouched. The
fast-fidelity boxstats overlay reads the same TUNE, so it inherits the fix.
Stored `lines_json` stats from already-played duals keep their old numbers —
only newly simmed matches use the new mix.

## Rule

**A stat layer has a ground truth too.** The outcome model was calibrated
against real win rates and defended by tests; the attribution model cited the
right real-world numbers in a comment and then violated them by 4× at both ends
of the talent range, because nothing ever measured it. When a model exists only
to make displayed numbers realistic, calibrate it against the realism it claims
— a mix table per level is a five-minute harness.

**A clamp hit at scale is a wrong model, not a safety net.** The `[0,1]` clamp
pinning entire cohorts at 0% (and the mirrored cohort at ~100%) was the signal
that the linear swing was mis-sized. Floor it and you get "3 winners instead of
0" — the owner's eye caught it immediately. When a share saturates for a whole
class of inputs, resize the swing; don't floor the output.
