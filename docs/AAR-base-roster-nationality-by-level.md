# AAR — Base-roster nationality by program level (international share + regional bias)

**Date:** 2026-06-21
**Scope:** Base-roster generation only (`app/ncaa.py:_base_roster`). Year-0 rosters
now set their international share by **division × prestige** and draw their domestic
recruits from the program's **own region**. Past year 0, the existing recruiting
sim dictates the mix (unchanged here).

## The problem

Every base roster — D1 blue-blood to small D3 — drew nationality from one global
band mix (`worldconfig.region_weights()`), so a tiny regional D3 program started as
international as a national power. Unrealistic: real college tennis is heavily
international at the top and almost entirely domestic at the bottom, and lower-tier
programs recruit their own backyard.

## The model

Two levers, both keyed off the program (not a global constant):

1. **International share by level** — `recruiting.intl_share_for(division, prestige)`.
   Prestige sets the spot within a division's band (it pulls better players *and*
   more internationals). Targets:

   | Division | intl share |
   |---|---|
   | D1 | 0.40 (low-major) → 0.50 (blue-blood) |
   | D2 | 0.30 → 0.40 |
   | D4 | 0.09 (regional) → 0.42 (high-prestige academic) |
   | D3 | 0.07 → 0.10 (lowest) |

   `ncaa.region_weights_for()` rewrites the name-picker mix so the `us` weight is
   `1 − share`; the non-US regions keep their relative proportions (scaled to the
   share), so *which* nations the internationals come from still follows the world
   band mix / onboarding preset.

2. **Regional bias for every program** — `recruiting.LOCAL_REGION_TARGET = 0.70`.
   A program's domestic recruits are drawn ~70% from its own region's real
   (city, state) pool (`ncaa.towns_in_region`), passed to `generate_prospect` via a
   new optional `town_pool`. Applies to all programs — prestige drives quality and
   the international share, not how local the domestic pool is.

## Measured result (men, base rosters)

| Group | intl % | domestic in-region % |
|---|---|---|
| D1 power (SEC/ACC/B1G) | 49.0 | 81.9 |
| D1 low-major | 42.7 | 80.9 |
| D2 | 35.5 | 74.2 |
| D4 academic (NESCAC/Centennial) | 40.3 | 74.4 |
| D4 regional (PAC/Landmark/Empire 8) | 8.5 | 73.5 |
| D3 | 7.6 | 74.0 |

Range 49% → 7.6%, exactly the requested "50% down to 7%", with D1 highest, D3
lowest, regional D4 very low, and the high-prestige academic D4 programs the
intended exception.

## Implementation notes

- `generate_prospect(... town_pool=None)`: the domestic branch draws its birthplace
  from `town_pool` when given, else nationwide. The international branch is
  unchanged. Same number of RNG draws either way, so talent/attributes are
  undisturbed by the regional bias itself.
- The region-bias coin flip uses a **dedicated RNG** (`seed ^ 0xC17`) so it doesn't
  perturb the talent stream; the name picker keeps its own RNG (`seed ^ 0x5EED`).
- Talent is still generated purely by level (budget star plan for D1/D2, the
  conf-strength talent prior for D3/D4) — only nationality and hometown changed.

## Verification

- Base rosters remain seed-deterministic.
- Full suite: **234 passed, 9 failed** — all 9 failures pre-exist on `main`
  (scholarship-cap / roster-calibration tests out of sync with the repo). Net
  **−1 failure**: the borderline `test_roster_talent_tracks_program_strength`
  calibration check now passes under the reshuffled draw. Zero new failures.
- The juniors circuit has its own international pipeline (`generate_class`,
  `intl_share=…`) and is untouched.

## Left for later (optional, noted by the user)

Recruiting *preferences* — e.g. a coach who favors local kids — could bias the
post-year-0 sim too. Not built; the recruiting sim still dictates the mix after the
base year as before.
