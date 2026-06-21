# AAR — elite junior signings, play-in de-confliction, conference strength, schedule colors

A cluster of fixes that followed from adding the ITA opener + ITA-points seeding.

## 1. Same-conference matchups in the >64 play-in (R96)
The bracketing hill-climb that keeps same-conference / rematch / AQ-vs-AQ teams apart
only ran on the ≤64 main draw. The play-in round for larger fields (D1's 96) paired
raw high-vs-low seed, so same-conference first-rounders slipped through (Citadel vs
Western Carolina, Stanford vs Boise). **Fix:** factor the penalty out (`_pair_penalty`)
and de-conflict the play-in (`_deconflict_playin`) by swapping low-seed opponents among
games — every game stays high-vs-low. Verified 0 same-conference play-in matchups.

## 2. Conference strength dropped out of seeding
Switching seeding to ITA team points dropped the power-conference signal the old
`seed_score` preference carried. **Fix:** fold conference prestige into the ITA points'
*opponent quality* (blend of Power-Index percentile and `conf_prestige`, weight
`_ITA_CONF_W = 0.30`, matching the old `CONF_SEED_PREF`). Seeding runs on the points, so
it flows through with no separate layer. Calibrated at 0.30 (21/25 of the top 25 are
power-conference, but a dominant mid-major like Wyoming 23-3 can still rank #1); 0.45
over-corrected.

## 3. Elite juniors never signing
**Symptom:** week 22, 927 signed, but the No. 1 class was a low-major with two 4★ and
zero 5★ — the 40 blue-chips were stuck unsigned.

**Diagnosis (the ITA broke it, as suspected):** the signing window is
`_signing_window = max(total_weeks)`, and the ITA opener shifts the regular slate back
by `lead` weeks (`seasonmode` line ~269), inflating `total_weeks`. Blue-chips were gated
to decide LATE — floor `0.40×window`, peak `0.82×window` — so the stretched window pushed
them to ~week 18. By then mid-tier recruits had "reached up" and filled the funded power
seats, so `_pick_school` returned None for the late-deciding elites and they never signed.

**Not the budget.** Verified the prestige→budget chain is intact (powers fund 15–17) and
**106 programs already clear the 5★ floor (13.5)** for ~40 blue-chips — funded seats were
never the bottleneck.

**Fix (timing, per the user — "varying times in the window"):** drop the hold-out floor
(`SIGNING_FLOOR_TOP` 0.40→0) and center the elite peak (`SIGNING_MODE_TOP` 0.82→0.50) so
blue-chip decision-weeks spread across the whole window (verified weeks 0–20, centered
~11) instead of clustering at the end. Plenty now decide early enough to claim seats;
lower recruits still skew early. Also widened the D1 power budget band 14–16 → 15–24 (user
request) so the blue-bloods separate and late-deciding elites have more funded options.

A first attempt (exempt elites from the gate entirely) was reverted — it made them all
sign in week 0, the opposite of "varying times."

## 4. Schedule tag colors
The team schedule colored only ITA tags (teal). Gave conference tournaments and NCAA
their own bold tags — amber (CT) and crimson (NCAA) — an opener → conference →
championship progression.

## Process notes / loose ends
- The multi-week **world** sim repeatedly hit SQLite `database is locked` (nested
  connections during `world.get_or_create`) and timeouts in the test harness. Worked
  around it by pre-triggering lazy schema (`build_roster` once) before the world txn, but
  never got a clean end-to-end "all 40 blue-chips signed to powers" run. The decision-week
  spread (the mechanism) is deterministic and was verified directly; the signing outcome
  is reasoned, not simulated end-to-end. Worth an in-app confirmation.
- Prestige redesign (the budget distribution was too narrow): the old formula
  `base + (conf - 0.50) * 0.9` compressed every D1 program into 0.52-0.97, so the
  low-major budget band (prestige < 0.50) was NEVER reached — the weakest D1 teams sat in
  the mid-major band at ~10. Replaced the multiplier with explicit, non-overlapping
  per-division bands (D3 0.10-0.20, D2 0.20-0.30, D1 0.40-0.97), mapping each conference
  into its division's band + the blue-blood bump. D1 budget now spans 6.7-24 with 125
  programs in the low-major (6-10) tier (was 0); recalibrated the dependent D2 budget
  frac and `_ELITE_D2_PRESTIGE` to the new D2 band.
- Academic D3 fallout + fix: compressing D3 prestige to 0.10-0.20 collapsed the appeal
  base `(0.15 + prestige)`, flipping smart recruits from academic D3s to low-major D1
  (Swarthmore-type appeal 1.94 -> 1.07 vs low-D1 1.26). Two-part fix: (1) open the
  division gate so 4-stars can choose academic-elite D3s (academics >= 0.85) while
  blue-chips stay blocked; (2) lift academic-elite D3 *conferences* (academic prior
  >= 0.80 — NESCAC/Centennial/SCIAC-tier) out of the band to 0.26-0.42, scaled by how
  academic they are. D3 budgets are always 0, so no funding side effect. This is a
  deliberate, narrow overlap with D2/low-D1 — academic D3s punching above their athletic
  division, which is realistic.
- "Widen the band year over year": the budget bands already existed per conference, but
  the jitter was seeded only by world salt + program key — constant across seasons, so a
  program's budget never moved. Fix: widen the power band (14-16 → 15-24) AND seed the
  jitter with the world `year` FOR THE TOP TIER ONLY (prestige >= 0.79), scaling the
  swing to band width. Only the blue-bloods move season to season (Virginia ~22-24,
  Pepperdine ~18-20); high-/mid-/low-majors hold a fixed value in their prescribed bands
  (Wyoming 13.2, Dayton 12.5, Alcorn State 10.1 every year) — the existing feature, just
  widened for the powers and made year-aware for them.
