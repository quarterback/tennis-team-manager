# AAR — power-conference preference in NCAA seeding

## Problem
The NCAA field was selected and seeded purely by the **Power Index** (`select_field`
sorted on `ratings[p.school].pi`). The Power Index is results-based — a gentle
strength-of-schedule nudge (`rating.K_SOS = 0.45`) but otherwise rewards winning — so
a mid-/low-major that piles up wins against a weak conference schedule can land a top
seed it hasn't earned on the court. Observed live: a Big West team as the overall #1
seed; SoCon / ASUN / Mountain West teams seeded #1–#4 and then **losing in the first
round** to the power-conference teams seeded beneath them. Classic SOS failure.

## Change
NCAA selection/seeding now runs on a **seed score**, not the Power Index alone:

```
seed_score(p) = pi + CONF_SEED_PREF * (conf_prestige(p.conf) - CONF_SEED_PIVOT)
```

(`app/bracket.py`). `conf_prestige` is the existing per-conference prior — power
leagues sit at ~0.79–0.82 (ACC/SEC/Pac-16/Big 12/Big Ten), mid-/low-majors ~0.40–0.58.
`CONF_SEED_PREF = 0.30` (the one tunable knob; 0 = pure Power Index). The pivot only
centers the number; ordering depends solely on the weight.

It's a **balance, not a takeover**:
- A genuinely dominant mid-major still earns a high seed (in validation a 0.950-PI
  Mountain West team held the #2 overall seed; a 0.934-PI A-10 team stayed in the top 16).
- Automatic-qualifier status is **not** required to be seeded high — at-large teams
  out-seed AQs purely on seed score, as before.
- The **Power Index rankings themselves are untouched** — the tilt lives only at
  bracket time. The rankings page, `national_top`, and `power_index` stay pure PI.

Applied consistently everywhere the field is built by index: `select_field`
(at-large fill + seed order), the field-reveal snub board (`ncaa_field`), and the
live projection / bubble (`_project`).

## Validation
On a played D1-men season, top-16 seeds flipped from mid/low-major-heavy
(Wyoming/MW, Dayton/A-10, UMass Lowell/America East, Chattanooga/SoCon, Pepperdine/WCC)
to power-conference-dominated (ACC/SEC/Big 12/Big Ten/Pac-16) while the two genuinely
elite mid-majors stayed near the top. Existing bracket tests still hold — field size,
all conference champions in the field, and "talent is predictive" — and seeds now align
*better* with strength, so favorites win at least as often.

## Notes / follow-ups
- `CONF_SEED_PREF` is the single dial. Raise it for a firmer power-conference tilt,
  lower it toward a pure-results bracket. ~0.28 is roughly the point where the single
  most dominant mid-major reclaims the overall #1 seed.
- No user-facing copy was changed; the selection-model microcopy still says "Power
  Index," which is now a slight simplification of "seed score."
