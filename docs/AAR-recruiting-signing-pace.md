# AAR — Recruiting signing pace (drip across the season, skewed by rank)

## Symptom

By ~week 15 of an 18-week regular season the entire 1,000-recruit class was
already signed. Commitments cleared the board well before the season ended, and
the tiers signed on the same timeline — a blue-chip was no more likely to hold
out than a back-of-the-class recruit. Neither realistic nor how it should work.

## Root cause

Two independent things front-loaded the class:

1. **Fixed, too-short window + flat quota.** The signing window was a hardcoded
   `SIGNING_WEEKS = 13`, and each week's quota was `openings // 13`. So over 13
   ticks the quota alone cleared every opening — finishing ~5 weeks before the
   regular season did.
2. **Timing decoupled from rank by design.** `_decision_week` drew a triangular
   week with a fixed mid-cycle peak (`SIGNING_PEAK = 0.45`) and a comment that it
   was *deliberately* independent of recruiting rank. Rank decided WHERE a recruit
   signed, never WHEN — so the elite tier didn't hold out.

## Fix

**Window tracks the real regular season.** New `_signing_window(seed, w)` returns
the longest active universe's `total_weeks`, and both the per-week quota and the
decision-week draw use it. Commitments now drip across the whole regular season
and finish near its end; the year-rollover `final` pass still mops up any
stragglers.

**Decision timing is rank-skewed.** `_decision_week(p, salt, rank_frac, window)`
now takes the recruit's position in the national class (`0.0` = the #1 recruit,
`1.0` = the last) and shapes a triangular draw so better recruits commit later:

- `SIGNING_FLOOR_TOP = 0.40` — a rank-dependent *earliest* week. The #1 recruit
  can't commit before ~40% of the season has elapsed; the back of the class can
  commit in week 0.
- `SIGNING_MODE_TOP = 0.82` / `SIGNING_MODE_BOTTOM = 0.12` — the draw's mode
  (peak) slides from late (top) to early (bottom) with rank.

`_sign_batch` enumerates the class (already best-first) to pass each recruit's
`rank_frac`, so the elite tier clusters late while the back of the class — often
locking into a program above what its ranking warrants — signs fast. Tiers still
interleave (a 5★ can occasionally pop early, a 3★ can drag late); the bulk of the
elite simply lands deep in the season.

Determinism is preserved: the week is still a pure function of
`(pid, salt, rank, window)`.

## Verification

- Distribution check (window = 18): mean decision week by tier — blue-chip 12.8
  (earliest 7), top 10% 12.1, median 9.6, bottom 20% 7.5, last recruit 6.2
  (earliest 0). Monotonic, full-window spread.
- Weekly sign-loop simulation on a real 1,000 class: signings spread evenly from
  week 0 (4 signed) through week 17 (board complete), and the **average rank
  signing each week falls from ~960 in week 0 to ~230 in the final week** — lower
  recruits early, blue-chips late.
- New regression test `test_decision_week_skews_late_for_top_recruits`
  (monotonic tier timing, top-recruit floor, in-window bound). World and
  single-gender determinism suites pass.

## Notes / follow-ups

- The "commits faster *especially* to a program better than their ranking
  warrants" nuance is approximated by the back-of-class-signs-early behavior
  rather than modeled at the school level (the destination isn't known until
  `_pick_school` runs). Could be made explicit later by nudging a recruit's
  decision week earlier when their best open fit out-ranks their own tier.
- `SIGNING_WEEKS` remains only as the pre-season fallback before any season's
  `total_weeks` exists.
