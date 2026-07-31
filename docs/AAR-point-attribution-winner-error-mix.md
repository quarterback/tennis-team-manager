# AAR — box scores said a player hit zero winners (and another hit 47)

**Date:** 2026-07-31
**Status:** Landed in four passes; final model = symmetric, matchup-anchored,
level-blind (owner rule 2027-07).
**Scope:** `engine/rally.py` (`_end_shares`, `play_point`, TUNE), a stale
`test_box_stats` assertion, `tests/test_point_attribution.py` (new invariants);
no outcome, rating, or determinism change at any pass.

## Symptom

The expanded dual formats put the bottom of D3/D4 rosters on recorded singles
courts for the first time, and their box lines read **W 0** — whole matches
without a single winner. The owner flagged it from a D4 national final. The D1
final had the inverse absurdity: **W 47 / UE 2** across three sets — nearly
every rally labeled a winner, almost no unforced errors.

## The wrong models, in order (this took FOUR passes — read the rules below)

The engine decides WHO wins each point, then labels HOW it ended. The labeling
was wrong three different ways before it was right:

1. **Floor patch.** Clamp the shares at 6% so nobody posts a literal zero.
   Symptom treatment; the owner rejected it on sight ("3 winners instead of 0").
2. **Gentler absolute swings.** Shrink the coefficients so the shares stop
   saturating. Mix landed 32% winners at elite, **14% at the bottom** — still a
   ladder from "pro" down to "bad." The owner rejected the premise, not the
   magnitude: *a winner is relative to the opponent.* A 35-STR shot a 30-STR
   opponent can't reach is a winner. Matched weak players produce near-normal
   winner counts; their tennis is uglier, not winner-less.
3. **Relative + small level drift.** Rebuilt symmetric and matchup-anchored,
   but kept a small absolute-level term ("collegiate slightly lower"). The
   owner's final correction: that residual term is still pro-anchoring.
   **Every division's players are the pros of their own world.** A Challenger
   box score is statistically indistinguishable from an ATP one (owner supplied
   three: 51/49 and 54/46 point splits, normal ace/DF counts, 149–234 points a
   three-setter) — the difference only shows when the levels MEET.
4. **Final model.** Level term deleted. The matchup gap is the whole dial.

## The final model (`rally._end_shares`)

Every rally end is ONE three-way draw — the point-winner's clean WINNER, or the
loser's FORCED or UNFORCED error — **on both sides symmetrically**. (The old
code could never charge a returner an unforced error while losing a service
point, nor a server a forced error; both are common in real tennis.) The split
reads the hitter's attacking basket vs the misser's defensive basket:

* outgun your opponent → your winners and their forced errors rise;
* get outgunned → your losses tilt unforced;
* matched → the real-world baseline mix, at EVERY level.

Wind tilts the misser's errors unforced. The 6% clamp band survives as a
backstop only. The label draw consumes the same single `rng.random()` the old
two-way split did, so the RNG stream — and every outcome — is bit-identical
(verified 40/40 mixed-level same-seed scorelines).

## Measured (30 matches/cell; winners incl. aces, DFs folded into UE)

| Pairing | Winners | Forced | UE+DF | pts/match |
|---|---|---|---|---|
| real target (O'Shannessy, pro men) | ~32 | ~41 | ~27 | ~132 (ATP avg) |
| elite matched | 31.7 | 37.2 | 31.1 | 137 |
| mid matched | 30.0 | 36.7 | 33.3 | 139 |
| weak matched | 28.5 | 36.2 | 35.3 | 135 |
| big mismatch | 33.1 | 34.5 | 32.4 | 104 |

Matched play is level-blind (the small drift is ace rates — genuine serve
talent, attribute-indexed). Mismatches run shorter and the favorite out-hits
the underdog on winners. A weak player posts ~27 winners in a matched
two-setter — the owner's "a 35 playing a 30 might get 30 winners."

## Validation against the owner's real-world reference boxes

The owner supplied real box scores and season tables during this arc; they are
the calibration record, logged here so future retunes have the same yardsticks.

**Men (ATP / Challenger)** — three Challenger three-setters: 234, 149 and 170
total points; total-points-won splits 51/49, 51/49, 54/46; serve points won
62–70% a side; aces 3–17; DFs 2–5. Statistically indistinguishable from
tour-level boxes — the fact that anchored the level-blind rule. Season scale:
ATP average ≈ 131.8 points/match; tour ace leaders ~8–16/match (Fritz 580 in
36); serve points won 62–70%, service games held ~72–93%.

**Women (WTA / WTA 125 / doubles)** — a 125 two-setter at 119 points
(serve pts won 49–60%, aces 0–5), a tour two-setter at 118 (Pegula 73.3% serve
pts won on a dominant day), a 125 three-set semifinal at **247 points**
(aces 10/2, DFs 8/7), a pro doubles two-setter at 91. Season tables: serve
points won ~55–65% (Sabalenka 64.9%, Swiatek 60.6%, mid-tier upper-50s), aces
~2–6/match a side (Rybakina 6.4), DFs ~1.5–5.6, return points won 47–52% for
the best returners. Same lesson as the men: a 125 box reads like a tour box.

**The game's women, measured against those tables** (real rosters, full
fidelity, per side):

| Metric | WTA real | Game D1 women | Game D4 women |
|---|---|---|---|
| Serve points won | ~55–65% | 57.8% | 53.1% |
| Aces / match | ~2–6 | ~4.6 | ~2.8 |
| Double faults / match | ~1.5–5.6 | ~3.7 | ~5.0 |
| Points / match | ~118 (2 sets) – 247 (long 3) | 142 | 135 |
| Winners incl. aces | ~29% (women's mix) | 31.8% | 29.1% |

No further tuning was needed on the women's side: the softer serve attributes
of generated women already put serve dominance in the WTA band (not the ATP
one), D4 women differ from D1 women the way a 125 differs from tour, and the
mix lands on the women's ~29% winners with the error tilt. Marginal watch
item: D1 women's aces (~4.6/side for top-of-lineup players) sit at the
Rybakina end of the real range — defensible, but if women's aces ever feel
plentiful, that's an ACE-MODEL (outcome-relevant) knob requiring an explicit
owner call and a recalibration pass, not an attribution tweak.

## Guardrails (tests/test_point_attribution.py)

1. **Conservation** — the owner's gut check: every point is labeled exactly
   once; a player's points won == their winners + opponent's errors +
   opponent's DFs, asserted per match per side, and totals sit in real ranges.
2. **Level-blind** — matched elite and matched weak mixes within 5 points.
3. **Gap-driven** — a big favorite out-winners the underdog and the beaten
   side's losses tilt unforced.

Also fixed: a `test_box_stats` assertion that summed a player's log aces across
all matches — the match log now (correctly) includes doubles, so the
singles-aggregate cross-check filters to S slots.

## No magic: the attribute → stat mapping (owner audit, logged)

The owner asked for confirmation that serving and the rest draw from the
player's actual talent attributes rather than level dials. The full-fidelity
path reads the 49 rich attributes (engine.state.Player role baskets, fed by
`Prospect.engine_player`); the mapping, for the record:

| Stat | Attributes read |
|---|---|
| Aces | server `first_serve_power` + `serve_variety` (2nd: `second_serve_quality`), offset by returner `return_quality` + `return_depth` |
| 1st serve % | `first_serve_accuracy` |
| Double faults | `second_serve_quality` + `serve_variety`, steadied by `composure`/`focus`, raised by the server's own `first_serve_power` (the real ace↔DF coupling, pro r≈0.93) |
| Rally/point wins | `forehand`/`backhand`/`movement`/`consistency` composite vs the opponent's, plus serve advantage |
| Winner label | `forehand_power`, `backhand_power`, `passing_precision`, `approach_shot`, `court_vision` + `footwork`/`speed`/`agility`/`balance` + `competitiveness`/`clutch` vs the misser's `groundstroke_consistency`, `shot_tolerance`, `discipline`, `rally_patience` |
| Conditions | per-player `wind_tolerance`, `heat_tolerance`, indoor/outdoor comfort, `crowd_pressure` |

**Talent gates the RESULT nonlinearly (owner rule, measured and confirmed).**
Level-blindness is about the labels, never the outcomes: every serve and rally
probability is a DIFFERENCE against the opponent (ace chance = server power
minus a weight on returner quality — the owner's "net against OVR"), so a
modest serve is lethal against a much weaker returner, and the win curve
steepens hard with the gap. Measured on real rostered players (150 full
matches per cell): OVR gap 10 → favorite ~87-89%; gap 20 → ~98-100%; gap 30+
→ 100%, zero upsets observed. "A 60 OVR playing a 30 OVR is simply never
gonna be an upset save for injury" — and injuries are the one system outside
this model. No change was needed; logged so the calibration isn't re-litigated.

This is why the women's numbers validated with no tuning: generated women
carry softer serve grades, so WTA-band serve stats fall out of the attributes.
TUNE baselines are the shared physics of tennis (e.g. the first-serve
advantage); every deviation from them is earned by attributes. Two deliberate
exceptions, both owner-sanctioned: FAST fidelity (legacy speed mode, off by
default) collapses outcomes to `overall`, and GTT's per-night chaos form is
the pro league's intentional randomness.

## Rules

**A stat layer has a ground truth too.** The outcome model was calibrated and
test-pinned; the attribution model cited the right real-world numbers in a
comment and violated them by 4× at both ends, because nothing measured it. If a
model exists to make displayed numbers realistic, calibrate it against that
realism — the mix harness is five minutes of code and now lives in the tests.

**Fix the frame of reference before the coefficients.** Passes 1 and 2 tuned
magnitudes inside a wrong frame (absolute level). The owner's correction was
conceptual: winners are defined BY THE MATCHUP, so the model had to be relative
before any constant could be right. When a calibration keeps missing in the
same direction at both extremes, suspect the anchor, not the gains.

**"Worse level" is not a stat modifier.** Every tier plays its own game at its
own top. Level differences express through attributes meeting attributes when
sides actually differ — never through a global discount knob. (This is the same
owner philosophy as the division radar and talent bands: levels are worlds,
not multipliers.)
