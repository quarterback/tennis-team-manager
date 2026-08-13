# AAR — JHSAA upset variance: hinged gap response in the fast match model

## The report

Owner report (2027-08): repeated extreme overperformance by materially weaker
JHSAA teams. Diagnostic case — a 2027 boys 7A program, regular season 8-20
(5-15 district, TOSS #98), then **three consecutive postseason upsets**: 3-2
over TOSS #18, **5-0** over #11, **4-1** over #4, before losing 0-5. A single
3-2 upset is fine; consecutive major upsets with blowout scorelines are not.
Constraints set by the owner: don't remove upsets, don't touch roster
generation / TOSS / the postseason architecture / the 1S-4D format, and never
let seeds or TOSS affect match outcomes — the fix has to live in the match
model's response to the *actual underlying* strength gap.

## Diagnosis — on the engine inputs, not OVR

Everything below was measured on what the fast model actually plays on: the
singles player's `Player.overall` (mean of the nine [0,1] drivers) and each
doubles pair's `engine.doubles.doubles_rating`, averaged per line —
"effective strength" (eff). Harness: `scripts/jhsaa_upset_calibration.py`
(real `build_roster` rosters, every classification, real `_lineup`/`_squad`
lineup rules, high-school match format, both dual shapes).

The five suspects, and what the measurements said:

1. **Game-day variance too large relative to STR/attribute gaps — CONFIRMED,
   and it is the whole story.** There are no game-day modifiers in the JHSAA
   at all (no context, no form roll); all variance is the fast model's
   per-game Bernoulli residual. The 2026 college recalibration
   (`AAR-engine-upset-recalibration-and-rating-scale-map.md`) deliberately
   flattened `skill_slope` 2.2 → 1.5 for a league whose talent is dense, and
   recorded the known limitation: one logistic slope cannot keep near-equals
   a coin flip AND make big gaps decisive. High school plays across gaps 3-5×
   the college band, exactly where that limitation lives. Measured (line-level
   favorite win %, high-school best-of-3): at a 0.10-0.15 overall gap —
   6-9 OVR points, a genuinely meaningful mismatch — singles favorite only
   **69%**, doubles **74%**. Composed into the 5-point state dual: **12.7%**
   underdog wins at that gap, and still 5.4% at 0.15-0.20, with 4-1 and 5-0
   underdog scorelines occurring routinely (see tables below).
2. **Low/mid-strength compression — minor, not the driver.** The only real
   compression is the `GRADE_MIN` clamp (a weak program's youngest players
   floor at grade 20 → unit 0.0), which flattens gaps among the *weakest*
   rosters. Those matchups are the "genuinely similar low-STR players" whose
   variance the owner wants kept; postseason 7A teams sit well above the
   floor. No change (roster generation was out of scope anyway).
3. **Doubles variance / pairing bonuses overwhelming base ability — NO for
   variance** (the doubles fast slope, 2.4 on pair rating, is *steeper* than
   singles; pair ratings average two players so per-line noise is smaller).
   One real interaction documented: a `doubles`-archetype school's +5..11
   per-player lift covers 2 of 7 points in the regular format but **4 of 5**
   in the postseason's 1S/4D, so a doubles school is legitimately much
   stronger in the postseason than its TOSS (built on 5S/2D results)
   suggests. That is effective strength, not variance — the designed sleeper
   team — and it was not the diagnostic case (not a seeded doubles school).
   Left alone.
4. **Fast fidelity producing too many reversals — CONFIRMED as a factor.**
   Same matchups, fast vs full: underdog dual-win 6.0% vs 2.0% (gap 0.14),
   3.2% vs 0.0% (0.19), 41.5% vs 31.2% (0.02). Fast was ~2-3× looser at
   meaningful gaps. Full fidelity stays out of reach for the JHSAA (~5,100
   duals/gender on the request thread, measured ~103s — the outage class), so
   fast had to be fixed, not swapped.
5. **Postseason lineup selection creating strength swings — NO.** The
   postseason strict best-nine vs regular-season bench rotation moves both
   sides symmetrically, and the results-based ladder adjustment is capped at
   ±7 OVR (`LADDER_SWING`), which barely reorders a nine.

**Why the case *felt* even worse than 12.7%:** TOSS rank is a results index
over a ~26-dual season played under this same variance, so it decouples from
underlying strength — measured rank correlation (TOSS rank vs eff rank, whole
gender) was only **0.74**, and a "TOSS #98 vs TOSS #11" pairing can be a
near-coin-flip 0.03-eff-gap match wearing an 87-rank costume. The flat slope
thus compounded itself: it scrambled the rankings AND let genuine gaps upset
too often. One dial drives both.

## The fix — a hinged effective gap (`engine/fast.py`)

`effective_gap(gap)`: below `gap_knee` (0.06 overall units ≈ 3.6 OVR points ≈
1 UTR — a margin of error) the gap passes through **unchanged**; beyond it,
every extra unit of real gap counts `1 + gap_accel` (1.8 → 2.8×). Continuous,
sign-symmetric, applied to the *gap* rather than the slopes, so hold, tiebreak
and the doubles fast model (`_fast_hold`/`_fast_tb` import the same function)
steepen together. No seed, rank, or TOSS term anywhere near a match — the
inputs are still only the two sides' abilities. Consecutive huge upsets decay
exponentially for free (independent duals at ~0.3% each ≈ 1-in-10⁵ for two in
a row).

`gap_accel: 1.8` was the *gentlest* value that reached the target shape — the
1.6/1.8/2.2 sweep moved the big-gap rows by under half a point (the hinge
saturates once lines approach certainty), so there is no reason to creep it up.

## Before → after (state 1S/4D dual, underdog win % by per-line-avg eff gap)

Real-roster matchup grid, 700 duals/bin (`scripts/jhsaa_upset_calibration.py`):

| eff gap (units ≈ OVR pts) | before | after | underdog-win scores after |
|---|---|---|---|
| 0.000-0.025 (≤1.5) | 42.9% | 39.7% | 5-0:13 · 4-1:82 · 3-2:183 |
| 0.025-0.050 (1.5-3) | 35.3% | 29.6% | 5-0:2 · 4-1:45 · 3-2:160 |
| 0.050-0.075 (3-4.5) | 28.3% | 18.0% | 5-0:2 · 4-1:13 · 3-2:111 |
| 0.075-0.100 (4.5-6) | 19.6% | 8.4% | 4-1:6 · 3-2:53 |
| 0.100-0.150 (6-9) | 12.7% | 4.6% | 4-1:1 · 3-2:31 |
| 0.150-0.200 (9-12) | 5.4% | 0.3% | 3-2:2 |
| 0.200-0.350 (12+) | 1.0% | 0.0% | — |

Which is the owner's requested shape: near-equals keep substantial variance
and common 3-2s (the knee guarantees the *line-level* model is bit-identical
below 0.06); a modest underdog stays believable (18% / 8%); a large underdog
is occasional and almost always 3-2; a huge underdog is rare, 3-2 when it
happens, and 4-1/5-0 huge upsets did not occur in 1,400 trials. The regular
5S/2D format moves in proportion (12.7% → 6.1% at 0.10-0.15; 0.15+ ≈ 0), so
records — and therefore TOSS — track strength better too (rank correlation
0.739 → 0.759 on the same world; most residual rank noise is schedule-graph,
which a 26-dual season cannot rate away, but a #98-ranked team can no longer
convert that noise into blowout bracket runs).

Line-level after: singles favorite 83% / doubles 92% at a 0.10-0.15 gap
(69/74 before); both unchanged below the knee.

## Blast radius

`engine.fast` is shared by every fast-fidelity consumer: the JHSAA, the
juniors circuit, the Davis/BJK cups, GTT bulk sims, and the *legacy* college
mode (`TTM_FIDELITY=fast` — the college default is full fidelity, untouched).
By construction nothing changes below the knee; above it juniors and cup
blowout pairings get chalkier, which is the same directive applied there. The
2026 college fast-curve table in
`AAR-engine-upset-recalibration-and-rating-scale-map.md` still holds for its
1-1.5 UTR bucket (≈ 0.065-0.097 units, barely over the knee) but its 3+ UTR
bucket now lands ~93% rather than 87% — superseded deliberately by this rule.
The full-fidelity rally model is untouched.

## Validation

- `scripts/jhsaa_upset_calibration.py` grids + `--seasons` end-to-end runs
  (tables above; in-season big-gap upsets 12% → 5% at 0.10-0.15, 4% → 0% at
  0.15+, every surviving big-gap upset 3-2).
- Full suite green (engine, JHSAA, juniors, GTT, web).

## Traps for later

- **Do not "restore the college feel" by deleting the hinge** — near-equal
  matches never changed; the hinge only exists past a margin-of-error gap.
  Equally, do not crank `gap_accel` to chase determinism: 1.8 already
  saturates the big-gap rows, and the flat sub-knee band is the owner's
  competitiveness rule from the 2026 recalibration, still in force.
- The dual-level upset rate at a given *team* gap is NOT the line-level rate
  at that gap: a 0.03-avg-gap dual usually contains individual lines well past
  the knee (lineups are uneven), which is why small-gap *dual* rows moved a
  few points while the sub-knee *line* model is provably unchanged.
- Season-path upset tables run hotter than matchup-grid tables at the same
  nominal gap — bracket survivors are self-selected for "better than their
  eff estimate", so grid tables are the calibration ground truth and season
  tables the sanity check, not the other way round.
- TOSS rank ≠ strength. Correlation ~0.76 after the fix; a rank-gap "upset"
  can be a coin-flip in eff terms. Diagnose future reports on eff gaps
  (`scripts/jhsaa_upset_calibration.py::eff_state`) before blaming the match
  model.
