# AAR — Coach-dictated localism in the recruiting sim

**Date:** 2026-06-21
**Scope:** A per-coach **localism** preference, wired into the world recruiting sim
(`world._pick_school`). Programs whose coach recruits the backyard pull in-region
recruits harder — the post-year-0, "coach-dictated" complement to the base-roster
regional bias.

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

## Verification

- A localist program (localism 1.0) beat an **identical** non-localist peer
  (localism 0.0) **200/200** times for an in-region 3-star — coach localism the only
  difference.
- `program_localism` varies across the field (0.00–1.00, mean ≈ 0.49) and is stable
  per school.
- Full suite: pre-existing failures only, zero new; recruiting- and coach-path
  tests pass.

## Notes & future work

- The sim reads the **stable generated** coach (`coach_for_program`) for localism, so
  career coach moves (`coach_carousel`) don't yet carry a coach's localism to the new
  seat. Wiring localism through the seated-coach record (`coachreg`) is the natural
  next step if coach moves should change a program's recruiting geography.
- `localism` is generated and read but not yet surfaced in the coach UI / persisted
  seat summary; that's a small add to `coachgen.ensure` + `coachreg` if wanted.
