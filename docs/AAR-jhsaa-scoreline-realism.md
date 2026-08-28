# AAR — JHSAA scoreline realism: calibrating the fast model against real Oregon high-school results

**Owner report (2026-08):** "the tennis scores generated feel not diversified
enough — far too many 7-6 7-6 matches." Correct, and the fix was calibrated
against five seasons of REAL data rather than intuition.

## The benchmark that decided everything

The owner aggregated five seasons of actual Oregon high-school tennis (boys +
girls, 2021-25, TennisReporting meet records:
`github.com/quarterback/or-tennis-data`). Extracted: **41,932 varsity matches,
84,238 completed standard sets.** The real distribution:

| set | real OR | sim (before) | sim (after) |
|-----|--------:|-------------:|------------:|
| 6-0 | **26.4%** | 2.5% | 27.4% |
| 6-1 | 21.5% | 9.0% | 19.0% |
| 6-2 | 17.4% | 15.5% | 16.5% |
| 6-3 | 13.4% | 23.4% | 14.1% |
| 6-4 | 12.3% | 24.8% | 12.2% |
| 7-5 | 5.1% | 10.0% | 5.4% |
| 7-6 | **3.9%** | **14.9%** | 5.3% |
| three-set matches | 13.8% | 42.8% | 16.9% |

Real HS tennis is **blowout-shaped**: 6-0 is the single most common set and
frequency falls monotonically toward 7-6 — every game longer is less likely
than the one before. The sim produced the near-inverse. And the real shape is
**near-uniform across the association**: boys/girls, flights D1-D3 and S2/S3
all sit within ~2 points of each other (only No. 1 singles is more lopsided
still — 33% 6-0 — talent concentrates at the top flight). Measured before
assuming per-flight profiles were needed; one profile serves every line.

## Diagnosis — three compounding causes, none a bug in isolation

Matches are simulated forward at GAME granularity (`engine/fast.py`): each
game is one Bernoulli draw on a hold probability. Nothing is "reconstructed";
the texture was wrong because every dial was college-calibrated:

1. **`hold_base_logit 0.9` is a PRO hold rate** (~71% at parity). Real HS hold
   rates run **30-45%** (vs ~80% ATP, ~65% WTA — serve dominance collapses down
   the ladder). Two HS players both "holding" at 71% random-walk to 6-6
   constantly: that IS the 7-6 glut, mechanically.
2. **The anti-blowout knee sat ON the median gap.** The hinge
   (`gap_knee 0.06`) was designed so near-equal matches stay volatile — but
   the measured median matched-line gap across JHSAA district play is
   **0.059**, so HALF of all real mismatches were being played as "even
   matches". This is also the root of the owner-reported unreal upset volume:
   the anti-blowout band was designed too narrow (too wide, in gap terms) for
   a level where talent disparities are massive.
3. **`skill_slope 1.5` under-converts skill into games.** Measured: at a gap
   where the favorite wins ~100% of matches, the modal set was still 6-2/6-3
   and 6-0 only 11%. A real HS mismatch is a near-automatic 6-0/6-1.

**‼️ THE DIAGNOSTIC THAT MATTERED: sweeping the dials FIRST proved the fault
was structural.** A 20-point sweep of hold_base × skill_slope barely moved the
distribution (err 104 → 84 of a ~14 target) because most lines sat under the
knee where neither dial reaches. Measure where the inputs actually live before
tuning the curve that maps them.

## The fix — `engine.fast.HS_PROFILE`, threaded as an explicit overlay

A per-league tuning overlay (`profile=` on `simulate_dual` → `simulate_match`
/ `simulate_doubles` → the fast models), passed by `jhsaa.play_dual` and
`play_jv_dual`. **`profile=None` — every college/cup/pro call — is
byte-identical to the pre-profile model** (no extra rng draw, no dial moved);
pinned by `tests/test_jhsaa_scorelines.py`.

- `hold_base_logit -0.4`: a BREAK is the expected outcome of an HS game
  (measured hold ~42%, inside the real 30-45 band). ‼️ **Serve still matters —
  as a SKILL.** `hold_serve` (0.44) is untouched: a big server still steals
  matches past his overall. What went away is the *structural free hold*.
  "Serve doesn't matter in HS" is the wrong takeaway and a draft nearly wrote
  it down.
- `skill_slope 6.0, gap_knee 0.02` (`tb_slope 4.5`, accel 1.8): skill converts
  to games much harder, and the even-match band shrinks below the real gap
  distribution. **This deliberately steepens the match-win curve** (favorite at
  a ~1-UTR gap ~76%, saturating by 0.08 — vs the college curve's 52%/67%),
  superseding the flatter JHSAA upset table in
  `AAR-jhsaa-upset-variance-recalibration.md` for HS play. That is the point,
  not a cost: the owner's own report was that the sim's upsets defy reality.
- `d_*` keys: the doubles fast model's equivalents, scaled by the ratios its
  college dials already carry over the singles ones.

## ‼️ A "form" variable was built, measured, and REJECTED (owner, 2026-08)

The first fit added a per-match hot/cold day (σ ≈ 0.10 overall) to each
player. It reproduced the distribution beautifully AND preserved the old
match-win curve — which is exactly why it was wrong: **the noise term existed
to protect a mis-calibrated deterministic core.** The ratings already abstract
coaching, fatigue, confidence, week-to-week improvement; a latent variable
introduced to reproduce a score distribution is the rating model and the match
model compensating for each other. Owner: the sim "already has a lot of
stochastic variation as-is." The machinery was stripped back out — do not
reintroduce it to fix a marginal the deterministic dials can carry. If a
residual someday genuinely needs it, it must solve a problem the fixed core
demonstrably cannot.

## Tracking — `scripts/jhsaa_scoreline_benchmark.py`

The permanent regression instrument, run after any change to `engine.fast`,
the doubles fast model, `HS_PROFILE`, or the JHSAA talent tables. Real district
round-robins through the SHIPPED path (`_lineup`/`_squad`/`simulate_dual` with
the profile), reporting: set-score histogram vs the Oregon target with
total-variation distance (currently **3.3**), three-set rate, hold rate (read
off `game_flow`), and favorite dual-win% binned at the **empirical
percentiles** (p10/p25/p50/p75/p90/p95) of the sampled gap distribution
(owner rule — never typed bin edges). Judge the whole report, not one row:
several wrong mechanisms can reproduce any single marginal.

## Traps for the next agent

- **Calibrate hold% to hold%, then VERIFY scorelines** — fitting scorelines
  alone lets multiple wrong mechanisms reproduce them. The benchmark reports
  both for this reason.
- **The Oregon data has no serving records**, so hold rate is judged against
  the published HS band (30-45%), not an Oregon number.
- **`_tb_prob` reads `overall` off the edge dicts**, not the players — keep it
  that way; a profile-era overlay flows through `_edges`.
- The real data's "other" buckets (8-x pro sets, 10-point MTBs, 2-0 retirement
  shells) are EXCLUDED from the target — only completed standard sets count.
- Do not "restore" the old JHSAA upset table by flattening this profile — the
  two AARs now disagree on purpose, and this one is later and owner-driven.
- College (`profile=None`) is byte-identical by contract. Any change to the
  fast models must keep that test green.
