# AAR — Elite recruits weren't signing + signing tracker showed every division

**Date:** 2026-06-23
**Scope:** `recruit_economy.program_caliber_floor` (new), `world._pick_school`
(program-side standard threaded through the drip + decommit pass), and a
division filter + universe selector on the signing tracker.

## Symptoms (from the owner, with screenshots)

1. "Elite players aren't signing." The recruiting board showed Blue-Chip 5★
   recruits (0.999x) still **available** deep into the cycle (week 17).
2. The signing tracker showed the **same top teams for D1 and D4** — 768 programs,
   2085 signed — i.e. it wasn't scoped to the chosen classification.
3. On mobile you **couldn't switch m→f** (or division) on the signing tracker.

## Root causes

### Elite crowding-out (the big one)
Signing is recruit-driven: each recruit picks the best program with an open seat
it can *afford* (`recruit_budget_floor`). But there was **no program-side
standard** — a 3★ (budget floor 0) aspiring up would happily take a budget-24
power's seat. Powers have ~3 senior openings; 3★s decide early and fill them, so
blue-chips (deciding mid-cycle) found the premium seats gone.

Measured with a faithful signing sim (real `_pick_school`/`_decision_week`, no
match sim) over the full 2500-recruit men's class:

| tier | recruits | signed (before) | signed (after) |
|---|---|---|---|
| Blue Chip | 181 | **22** | **180** |
| 5★ | 177 | 67 | 177 |
| 4★ | 354 | 182 | 354 |
| 3★ and below | 1788 | 1788 | 1788 |

There were always *enough* premium seats (246 blue-chip-capable seats for 181
blue-chips) — they were just being spent on lesser recruits.

### Signing tracker not division-scoped
`state.signing_tracker(gender)` iterated `world.signings(gender)` — every program
in every division — and the template had no universe selector (only a label).

## Fixes

### Budget-aware program standard
New `recruit_economy.program_caliber_floor(budget, progress)`: the minimum recruit
caliber a program will accept **right now**. A funded program courts talent worthy
of its budget (`_PROGRAM_CEILING`: ≥13.5 → 0.70, ≥10.5 → 0.62, ≥8.5 → 0.55) and
**holds that standard for the first `_STANDARD_HOLD` (0.75) of the window**, then
ramps it to 0 by signing day so seats still fill. Unfunded programs (ceiling 0)
take anyone, always — so 3★ volume is untouched.

`world._pick_school` gained a `progress` arg (0→1 across the signing window) and
skips a program when `caliber < program_caliber_floor(budget, progress)`, in both
the scored loop and the widen-once mop-up. Threaded from `_sign_batch`
(`progress = week/(window-1)`, `1.0` on the final mop-up) and `_decommit_pass`.

This is the program-side mirror of the existing recruit-side `recruit_budget_floor`
— together they tier the class: powers hold for blue-chips/5★, everyone else fills
in, and nobody is crowded out.

### Division-scoped signing tracker + selector
`signing_tracker(gender, division=None)` filters `by_school` to the division's
programs. The route passes the selected division, and `signing_tracker.html` now
has the standard **Division (universe) dropdown** — so m↔f and D1–D4 switch on the
page, and the class rankings/commitments are scoped to one classification.

## Tests

`tests/test_recruit_signing.py`: pure tests for `program_caliber_floor` (holds then
relaxes, monotonic, unfunded=0) and a full-cycle integration test asserting
blue-chip / 5★ / 4★ sign rates ≥ 0.90 with 3★ ≥ 0.99.

## Not done (deliberate follow-up)

The owner also wants programs to **over-sign and push the worst to the portal** (so
a power with no senior opening can still take a blue-chip). The over-cap → portal
relocation already exists in `world._normalize`; wiring recruiting to over-sign
beyond `_openings` is a larger, separate change and wasn't needed to fix elite
signing (existing premium seats sufficed once they stopped being wasted). Flagged
for a follow-up.
