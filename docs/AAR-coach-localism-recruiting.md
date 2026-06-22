# AAR — Coach-dictated recruiting: localism, nationality tilt & home-country pipeline

**Date:** 2026-06-21
**Scope:** Per-coach recruiting preferences wired into the world recruiting sim
(`world._pick_school`): a **localism** lean (recruit the backyard), a **nationality
tilt** (US coaches lean domestic, foreign lean international), and a foreign coach's
**home-country compatriot pipeline**. The post-year-0, "coach-dictated" complement to
the base-roster regional/international model.

## The gap

The coach model (`app/coaches.py`) already carried recruiting preferences —
`source_preference`, `region_pipelines`, `origin_affinity`, `source_fit` — but they
were explicitly "not the final recruit decision model" and **the world recruiting
sim never consulted a coach at all**. `_pick_school` scored a (recruit, school) pair
on prestige, academics, the recruit's own homecooking, facilities and budget only.
So a program's regional pull was entirely recruit-driven; the coach had no say.

## The model

A new coach attribute, **`localism` (0..1)** — 0 = recruits nationally without
regard to geography, 1 = a committed homer who prioritizes in-region kids:

- **`Coach.localism`** (dataclass field, default 0.5, clamped in `__post_init__`).
- **`generate_coach`** sets it from the coach's sourcing instinct: a high-school
  recruiter skews local (+0.16), an international recruiter away (−0.16), blend
  neutral — then a Gaussian spread, so coaches range the full 0–1.
- **`coaches.program_localism(school)`** — the stable per-program value (cached),
  read by the sim.

In `_pick_school` the score gains a coach-side geo term alongside the existing
recruit-side one:

```
prox       = region_proximity(recruit_home, school_region)
geo        = homecooking * prox                       # recruit wants home
coach_geo  = COACH_LOCAL_WEIGHT * localism * prox      # coach wants the backyard
score *= (1 + GEO_WEIGHT*geo + coach_geo) * ...
```

`COACH_LOCAL_WEIGHT = 0.50`. Because the term scales with `prox`, internationals
(proximity 0 to any US region) are untouched — localism only tugs domestic,
in-region recruits. It is **additive to** the recruit's own homecooking, so a homer
program pulls nearby kids even when the recruit isn't especially homesick.

## Nationality tilt & home-country pipeline

The coach model already had `source_fit` (domestic/international lean) and
`origin_affinity` (shared-origin nudge), but the sim never read them — and a latent
bug made it worse: `coach_for_program` drew nationality flat from a 30-country pool
(1 US entry), so **~97% of sim coaches were non-US**. Left unfixed, tilting non-US
coaches international would have shoved the whole world international and undone the
base-roster shares. Fixes:

- **Realistic nationality** — `coaches.program_coach(school)` (new, cached) draws a
  US-weighted home country (`US_COACH_SHARE = 0.68`); measured ≈ 71% US, 29% foreign.
- **Nationality → sourcing** — `generate_coach` now sets `source_preference` by home
  country: non-US lean `international`, US lean `high_school`/`blend` (which also
  feeds the localism bias, so foreign coaches are less local).
- **Sim wiring** — `_pick_school` multiplies a candidate's score by
  `coach.source_fit(recruit)` (±~10% domestic/international tilt) and
  `coach.origin_multiplier(recruit)`.
- **Home-country pipeline** — `Coach.origin_multiplier` converts the grade-point
  `origin_affinity` (4.0 country / 1.5 region, on a 20–80 scale — *not* a multiplier)
  into a gentle `1 + 0.18·(affinity/4.0)`: ≈ **+18%** for a same-country recruit,
  **+7%** same-region. **US-home coaches return 1.0** — their domestic lean is
  `source_fit`, so the generic US↔US case never double-counts.

## Verification

- A localist program (localism 1.0) beat an **identical** non-localist peer
  (localism 0.0) **200/200** times for an in-region 3-star.
- A Spanish-coached program beat an **identical** US-coached peer **200/200** for a
  Spanish international recruit (origin pipeline + international tilt the only diff);
  the Spanish coach's `origin_multiplier` is 1.18 for a Spaniard, 1.00 for an
  American; a US coach is 1.00 for everyone.
- Coach nationality ≈ 71% US / 29% foreign; sourcing splits accordingly.
- Full suite: pre-existing failures only, zero new; 30 recruiting/coach-path tests
  pass.

## Notes & future work

- The sim reads the **stable generated** coach (`program_coach`), so career coach
  moves (`coach_carousel`) don't yet carry a coach's localism/nationality to the new
  seat. Wiring these through the seated-coach record (`coachreg`) is the natural next
  step if coach moves should change a program's recruiting geography.
- `localism` and the nationality tilt are generated and read but not yet surfaced in
  the coach UI / persisted seat summary; a small add to `coachgen.ensure` + `coachreg`
  if wanted.
- The home-region branch of `origin_affinity` only fires for internationals (domestic
  recruits carry a US *state* name, which never matches a coach's coarse home region);
  that's fine here — the domestic compatriot case is the US↔US one we deliberately
  route through `source_fit` instead.
