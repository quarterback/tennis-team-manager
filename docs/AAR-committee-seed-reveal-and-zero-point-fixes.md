# AAR — Committee seed score: reveal/sim seeding drift + zero-point résumé spread

**Date:** 2026-06-24
**Scope:** `seasonmode.ncaa_field`, `bracket_field`, `committee_seed_score`.
**Found by:** an external (codex) review pass; both confirmed real before fixing.

## Context

The NCAA field is built by the **Committee Seed Score** (`committee_seed_score`):
a blend of Power Index rank (45%), ITA team-points rank (30%), a tiered AQ
championship bonus (15%), and recent form (10%). See
`AAR-committee-seed-score-and-conference-tiers.md`. Two bugs survived that change.

## Bug 1 — the reveal/sim seeded by a DIFFERENT metric than the draw

**Symptom.** The "actual" bracket reveal could show seeds / top-seed labels that
disagreed with the matchups actually scheduled.

**Cause.** Three code paths build the field, and they had drifted apart:
- `_ncaa_seeds` (the **real draw**, via `_advance_ncaa_round`) → `select_field(...,
  score=committee_seed_score(...))`. ✅
- `ncaa_field` (the **reveal / lock**, used by `ncaa_bracket_view`) → still
  `score=ita_team_points(...)`. ❌
- `bracket_field` (the **as-it-stands sim**) → still `score=ita_team_points(...)`. ❌

Power Index and ITA points diverge, and the AQ bonus only exists in the committee
score, so the selection AND the seed order could differ between what was drawn and
what was shown — the labels would lie about the bracket.

**Fix.** Seed `ncaa_field` and `bracket_field` by `committee_seed_score` with the
same champions set the draw uses, and order `ncaa_field`'s snub board by the
committee score too. All three field paths now agree. Verified `ncaa_field` still
returns a clean 96 / 34 AQ / 8-snub D1 field.

**Guardrail.** *Every* seeding path must use `committee_seed_score`, never
`ita_team_points`. The only remaining `ita_team_points` callers are (a) the
committee score itself (the 30% component) and (b) the standalone ITA-rankings
view — both correct.

## Bug 2 — point-less teams ranked by dict insertion order

**Symptom.** In projections / early season (when many teams have no ITA points
yet), otherwise-tied no-point teams got wildly different résumé scores.

**Cause.** `ita_team_points` **deliberately omits** teams with no quality wins. But
`pts_rank` sorted *every* Power-Index team with a default `0.0`:

```python
pts_rank = {sc: i + 1 for i, sc in enumerate(
    sorted(schools, key=lambda x: pts.get(x, 0.0), reverse=True))}
```

So a block of tied 0.0 teams received **unique sequential ranks by dict order**
(3, 4, 5, …), and the 30% résumé component became an arbitrary spread — up to a
~12-point swing in the committee score (40 rank-score points × 0.30) decided by
nothing but iteration order.

**Fix.** Build `pts_rank` only from teams that actually have points; every
point-less team then falls through to the floor rank `n` via the *existing*
`.get(sc, n)` default, so they all share one identical (low) résumé score:

```python
pts_rank = {sc: i + 1 for i, sc in enumerate(
    sorted((sc for sc in schools if pts.get(sc, 0.0) > 0.0),
           key=lambda x: pts[x], reverse=True))}
```

Unit-checked: three no-point teams all land at rank `n` → identical score (20.0)
instead of 60 / 40 / 20.

**Why it hid.** In a fully-played save every team has points, so `pts_rank` covered
everyone and the `.get(sc, n)` default never fired — the bug only bites projections
and early-season fields, exactly where the committee score is most consulted.

## Tests
`test_bracketing` / `test_ita` / `test_season` (17) green. Both guardrails are also
recorded in `AAR-committee-seed-score-and-conference-tiers.md`.
