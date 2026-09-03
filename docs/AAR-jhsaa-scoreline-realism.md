# AAR — JHSAA scoreline realism: calibrating the fast model against real Oregon high-school results

**Owner report (2026-08):** "the tennis scores generated feel not diversified
enough — far too many 7-6 7-6 matches." Correct, and the fix was calibrated
against five seasons of REAL data rather than intuition.

**‼️ WHEN THIS LANDED IN THE OWNER'S LIVE SAVE: the 2053 season.** Every JHSAA
season from 2027 through 2052 was simulated on the OLD college-calibrated
dials; 2053 is the first on `HS_PROFILE`. That boundary is deliberate
benchmark material, not an inconsistency to migrate away: the archive is never
re-simulated, so the in-game realism page (/jhsaa/realism, season switcher)
shows the 2027-2052 seasons scoring tiebreak-heavy against the Oregon target
and 2053+ scoring like real tennis — the before/after is readable directly
from the owner's own history. Do not "fix" old seasons to match.

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

## In-game view — `/jhsaa/realism` (the Juniors "Realism" tab)

The owner wants the tracking visible without running Python (2026-08), so the
benchmark has an in-game face beside Mismatches / Lineup Lab. ‼️ It is a FOLD
over `world_jhsaa_dual`, never a simulation on the request thread (the
section's read-only rule): it parses the archived score strings (the
`jhsaa._games` precedent — the archive already holds the score), varsity only
(`COALESCE(level,'v')='v'`), one side per dual (`home=1`), standard sets only
(showcase-pod pro sets fall out, exactly the target's own filter), split by
phase family because the formats differ by design. The Oregon target lives
ONCE — `jhsaa.OREGON_SET_TARGET` / `OREGON_THREE_SET` — read by both the view
and the script; hold% appears only in the script (the archive stores no game
flow). Class-blind like the Title Board; the SEASON switcher is honoured,
which is what makes the 2053 boundary above browsable. Pinned by
`test_realism_fold_reads_the_archive_varsity_only`.

## 2026-09 — "it reports the same numbers every season": the page was right, the framing was wrong

**Owner report:** the Realism tab "is reporting the same numbers each year
regardless of what data is inside my sim". Diagnosis, in order:

1. **The fold WAS reading the selected season.** The archive writes each year's
   duals under its own `year`, the season switcher carries `year=` through
   `jh_scope_url`, and the view folds exactly that year. Pinned now by
   `test_realism_fold_is_per_season` (two seasons archived with opposite
   shapes fold to opposite histograms).
2. **The percentages are identical across seasons because they SHOULD be.** A
   gender-season is ~200k standard sets, so the sampling error on any bucket is
   ~0.1 point, and the set-score shape is a property of the engine dials plus the
   talent distribution — both stable year to year. The counts move; the shares
   do not. The owner's own paste (6-0 3.3%, 7-6 12.4%, three-set 45.5%) is
   exactly the banded curve's shape documented in `engine/fast.py`.
3. **The page was asking a superseded question.** It presented Oregon as the
   TARGET and printed "distance from Oregon 35" in the failure colour — but the
   banded matchup curve (owner ruling 2026-08) deliberately does not reproduce
   the Oregon fit, so a page framed as a fit to it reads as broken while
   reporting the archive faithfully.

**Owner rule (2026-09):** "compare the previous season to the current one and
then leave the Oregon comps there not because they're targets, but rather as
baselines." So `/jhsaa/realism` is now **this season vs last season**, bucket by
bucket, with the shift in points and a total-variation "shift from last season"
per table; the Oregon column stays at the far edge as a BASELINE (a tick on the
bar scale, muted text, no pass/fail colour). "Previous" is the next-older
ARCHIVED season relative to the one on screen, so the season switcher walks the
comparison back through the save; on the oldest season the page says there is
nothing earlier and shows dashes, never zeros.

- `world.jhsaa_scoreline_realism` is unchanged as the per-season fold, now
  memoised on `(world_id, year, gender)` (`_scoreline_cache`, cleared by
  `reset()`) — an archived season is immutable, and the page folds two of them
  per request on the one gthread.
- `world.scoreline_compare(cur, prev)` is the pure composition; the view
  (`state.jhsaa_realism_view`) only picks the two years.
- **A shift near zero is the expected reading while nothing in the engine or
  the talent scale changes.** The page now exists to show WHEN it moves — the
  §24 talent-scale change, a `HS_PROFILE` retune, a `_TALENT` reshape — as a
  jump between two consecutive seasons, with the real-world figures beside it
  for orientation.

### By OVR gap band — the check a curve change actually shows up in

Owner (2026-09): "The next useful check is not the statewide set distribution.
It is 2068 versus 2067 by OVR-gap band. That is where the new curve should show
itself clearly: 0–9 should look almost unchanged, while 15–24 should show more
favorite wins and more decisive scorelines." The statewide histogram averages
over every matchup, so a curve that only steepens above the peer band is
diluted into a point or two; by band it is the whole signal.

`world.jhsaa_gap_bands` buckets every varsity best-of-3 match of a season by
the OVR gap between the two sides on the owner's five competitive bands
(`world.OVR_GAP_BANDS`: 0-6 peers · 7-14 modest · 15-21 clear · 22-28 strong ·
29+ major) and reports, per band and per discipline (all / singles / doubles):
matches, favourite win %, three-set %, and the share of sets at 6-0/6-1.
`world.gap_bands_compare` sets this season beside last with the shift per cell.

- **The archive holds NAMES, not ratings**, so the fold rebuilds each program's
  roster for that season (`jhsaa.build_roster(school, season_year, salt)`, the
  Underplaced board's own idiom) and resolves names against it; `former_names`
  maps a renamed program. A name the rebuilt roster does not carry is counted
  in `unresolved` and skipped, never guessed.
- **Home court is not in the gap.** The 1-4 point host lift is rolled off the
  dual's seed, which the archive does not store. Symmetric across a season and
  identical between the two seasons compared, so it cannot manufacture a shift.
- **‼️ ~20 s cold, so it is ON DEMAND.** Two full-gender rebuilds (~12 ms a
  school, ~900 schools) cannot run on the one gthread's request; the route runs
  it through `_jh_deferred` (the Transfers page's pattern) behind a "Compare by
  gap band" button, `world._gapband_cache` is the publish side (keyed on the
  transfer stamp too, since a recorded move changes who a roster names), and
  the set histograms above it never wait on it. The view takes `bands=True`
  only after the route has done that.

## Traps for the next agent

- **Oregon is a BASELINE on the realism page, not a target** (owner, 2026-09).
  Do not put the pass/fail colouring or the "distance from target" framing
  back; the season-over-season shift is the page's question.
- **Identical percentages season after season are not a bug.** Check the set
  COUNTS on the footer line before suspecting the fold — they move; the shape
  does not until the engine does.

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
