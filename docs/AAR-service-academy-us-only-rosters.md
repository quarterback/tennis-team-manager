# AAR — Service academies roster US citizens ONLY

**Date:** 2026-07-27
**Owner rule.** Army, Navy, Air Force, Coast Guard and Merchant Marine can never
have an international player. Reported as an immersion break: the academies were
showing up with foreign rosters like any other program.

## Why

An appointment to a US service academy (USMA/USNA/USAFA/USCGA) — and to the US
Merchant Marine Academy — requires US citizenship. Foreign cadets exist in real
life only as a handful of government-to-government exchange appointments, and never
as recruited athletes. So the correct model is a **hard gate, not a low share**.

Before this, the academies drew nationality from the same level-based international
share as everyone else (`recruiting.intl_share_for`), which put them near 0.10–0.20
because they are high-academic — low, but nonzero, and every downstream pipeline
(recruiting drip, portals, pros) could still hand them a foreign player.

## The gate

One authority, in `app/ncaa.py`:

```python
SERVICE_ACADEMIES = frozenset({"Air Force", "Army", "Coast Guard",
                               "Merchant Marine", "Navy"})
us_only_program(school)        -> bool     # is this a citizens-only program?
is_domestic_player(player)     -> bool     # domestic flag, falling back to country
admits_nationality(school, p)  -> bool     # the one check every pipeline calls
blocked_schools_for(player)    -> frozenset  # exclude/avoid-set form of the same rule
```

`is_domestic_player` reads the `domestic` flag `generate_prospect` wires from the
nation, falling back to the country code so a partial Prospect still classifies.
PR / USVI / Guam kids stay eligible — they're US citizens who merely carry a
dual-territory flag (`ncaa.SCHOOL_LOCAL_TERRITORY`).

**Deliberately NOT included: The Citadel and VMI.** They're state senior military
colleges — ordinary universities that do enroll international students. Only the
five federal academies are gated. Don't add them.

## Every pipeline that could reach an academy roster

The gate is worthless if it covers only generation, so all nine were wired:

| Pipeline | Where | How |
|---|---|---|
| Year-0 base roster | `ncaa._base_roster` | name-picker region mix forced to `{"us": 1.0}` (ahead of the territory/local tilts) |
| Recruiting drip | `world._pick_school` | academies folded into `exclude` for an international — so they're off the board mid-cycle **and** in the signing-day relax pass |
| Recruit board display | `recruiting.build_recruiting` | an international's offers/dreamsheet never list an academy |
| Fall + pre-season portal | `world._FPPlanner.deny` | folded into the `avoid` set every destination search honors, so riders, cascades (`settle`) and `auto_dest` all respect it; an explicit user destination is refused |
| Year-end transfer portal | `world.transfer_portal` | `best_in(..., block)` on all four move kinds (schol/up/lateral/down) |
| Over-cap relocation | `world._normalize` | destination candidates filtered |
| Coach carousel | `world.coach_carousel` | followers filtered — a coach who lands an academy job brings only their Americans |
| Pro free agents | `pros.assign_pros` (`us_only` program flag, set by `world.inject_pros`) + `world.sign_pro` | auto-assignment skips them; a hand signing is refused |
| Walk-on fill | `world.assign_pool_walkons` (leftover sweep) + `refill_walkons` (auto-gen names) | domestic-only leftovers; `{"us": 1.0}` name mix |
| Legacy single-division league | `league._refill`, `league.transfer_portal` | same two treatments |

Hand-picked destinations (portal redirect/add, pro signing) fail loudly with
`world._citizenship_error` — a readable "Navy is a US service academy…" message
rather than a silent no-op.

**The editor is deliberately NOT gated.** `/editor/move` is the owner's god-mode;
if you hand-move a Belgian to West Point there, it sticks.

## Repairing an existing save

The gate fixes generation, but `world.get_or_create` **persists** year-0 rosters into
`world_roster`, so a save built before the fix keeps its foreign cadets.
`scripts/naturalize_academy_rosters.py` repairs one in place (dry run by default,
`--apply` to write):

```
python3 scripts/naturalize_academy_rosters.py            # list what would change
python3 scripts/naturalize_academy_rosters.py --apply    # rewrite the rows
```

It rewrites ONLY the nationality-facing fields (name, country, `domestic`, hometown,
high school, region, secondary flag, homecooking) across `world_roster`,
`world_signing` and the matching `world_graduates` alumni rows — every rating,
grade, class year and **pid** is untouched, so there's no team-strength drift and
nothing keyed on pid (career history, injuries, lineup pins) breaks. That's exactly
what generation would have produced anyway: nationality and talent are independent
draws. Seeded from the pid, so it's idempotent.

## Measured result

- All ten academy base rosters (5 schools × men/women) are 100% `country == "US"`,
  with real US hometowns/high schools. Non-academy programs are untouched (D1 men
  still runs its full level-based international share).
- Over a full men's signing cycle the academies fill **every** opening they have
  (Army 1/1, Navy 1/1, Coast Guard 4/4, Merchant Marine 4/4; Air Force had 0 in
  year 0) — the gate redirects them to domestic recruits, it does not starve them.
  That check is a test, because a starved academy would thin out season over season:
  D1 signs only its scholarship core and has **no auto-generated walk-on depth** to
  paper over a short class (see CLAUDE.md §3b).
- Base rosters stay seed-deterministic. Only the academies' own draws changed
  (their per-program name RNG is seeded per program), so the rest of the world is
  bit-identical.

## Tests

`tests/test_service_academies.py` — the gate helpers, base rosters, the signing
drip (all three windows + a full cycle), the recruit board, the fall-portal planner
(auto + a refused hand pick), the year-end portal, `_normalize`, the coach
carousel, walk-on fill, and pro assignment. Each destructive test empties the
academies first so they are the most attractive open seats in the world — if the
gate ever comes off, the test fails rather than passing by luck.
