# AAR — Pros are grad transfers ("Gr"): one season, then gone

**Date:** 2027-07-17
**Scope:** `pros.generate_pros` (class assignment), `world.graduate` (Gr retires
with the seniors + legacy migration).

## The bug this fixes

Portal pros were generated with NO class year (`class_year=""`), and
`world.graduate()` only removes class-`Sr` players — so every pro who entered
through a portal cycle **persisted forever**, stacking season over season and
distorting the ecosystem they were designed to only pass through.

## Owner's rule (locked)

Pros are **grad transfers**: class **"Gr"**, listed as Gr on the card next to
their green PRO badge — deliberately NOT fitted into the Fr→Sr 4-year cycle.
One season of eligibility; at the year rollover `graduate()` retires `Gr`
alongside `Sr`. They're an elite, temporary distortion — never a fixture.

- **GTT intake via the PRO ROUND only** (owner design): departing `Gr` pros —
  including migrated legacy pros — ARE saved to `world_graduates`, but in the
  GTT they are draftable ONLY in the draft's opening **Pro Round**: one single
  round, worst record first, each franchise at most ONE pro pick (best
  available of either gender that fits an open slot). Every undrafted pro
  retires immediately — they never sit in the general pool or the waiver wire,
  so a cycle of 15–20 pros can never flood rosters. Intake tags them
  `origin='pro'` (capped at the franchise count per gender) and they never
  consume the normal graduates' pool slots; the hub wire labels the picks
  "PRO ROUND". One pid still threads college → GTT.
- **Medical redshirt edge:** a season-ending injury makes an RS-Gr who repeats
  once, consistent with the injury system. Rare and acceptable.
- **Migration:** pros already living in pre-rule saves carry an empty class;
  `graduate()` treats an empty-class `is_pro` player as `Gr`, so every legacy
  pro leaves at the NEXT rollover. Non-pro players with odd/empty classes are
  untouched.

## Verification

Unit-checked: new cohorts all generate as `Gr`; a mixed roster through
`graduate()` removes the Sr, the new Gr pro, and a legacy empty-class pro,
while a normal Jr advances to Sr and a non-pro empty-class player survives.

## Review fix: recruiting seats (P1)

The first cut taught `graduate()` about `Gr` but left `_openings()` — the
recruiting seat planner — counting only `Sr` as departing. A program hosting a
pro received NO recruiting seat for the pro's imminent departure: after the
rollover the roster ran short, and on D1 the pro was counted as a returning
scholarship player, leaving the core permanently underfilled. Departure is now
ONE predicate — `world._departing(p)` (Sr, Gr, or legacy classless pro) — used
by `_openings`, `graduate`, and `_save_graduates`, so the three can never
diverge again. Verified: a roster with Sr + Gr pro + legacy pro shows 3 D1 core
seats (and 3 D3 openings), and graduation removes exactly those 3.

## Watch-outs

- Anything that buckets players by class (filters, exp maps) should treat `Gr`
  as a senior-equivalent when it matters; unknown-class fallbacks degrade
  gracefully today.
- If a future rule wants two-season pros, give a slice of the cohort `Jr`
  instead — do NOT extend `Gr` itself; "Gr = leaves this rollover" is the
  invariant other layers may rely on.
