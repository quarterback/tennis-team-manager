# AAR — Division radar recruiting: D1 never sees sub-level recruits; D3 signs all season

**Date:** 2026-07-07
**Scope:** `world._pick_school` (radar gate + window floor + D3/D4 gate),
`world._openings` (D1 scholarship-core-only classes),
`recruit_economy.program_level_floor` (new). Owner-directed redesign.

## Symptom (from the owner, week 10 of a live world)

"Every division has had lots of recruits signing including Division 4 but **no D3
schools have signed anyone**." Reproduced exactly with a faithful signing sim
(real `_pick_school`/`_decision_week`, window 18): at week 10 — D1 1137 (capped),
D2 122, D4 194, **D3 0**. D3 signed literally nothing until the year-rollover
mop-up, then absorbed 400+ recruits in one lump.

A second, deeper problem surfaced while diagnosing: **sub-45-STR recruits were
flooding D1**. Only ~680 of the 2,500-recruit class play above 45 STR, but D1 had
1,137 seats — and the fog-of-war projection (scouting the CEILING) rates 74% of
sub-45 kids as D1-worthy, so D1 filled its walk-on depth with players who,
by the owner's design, belong in D2–D4.

## Root causes

1. **No program-side level standard.** `program_caliber_floor` was budget-only, so
   every unfunded program (all of D2–D4) took anyone from week 0 — and recruits
   pick the most prestigious open seat, so D2's seats (prestige 0.20–0.30, inside
   most recruits' aspiration window) absorbed the sub-D1 flow all season while D3
   (prestige 0.10–0.18, below the window) got nothing until seats above it were gone.
2. **The candidate window was aspiration-only.** A recruit's school window keyed
   entirely on `consensus_caliber` — the ceiling-driven projection. A hyped project
   whose *current* game is D3-grade had a window floating above D3/D4 all season,
   so the bottom tier literally never appeared among his candidates.
3. **The D3/D4 division gate keyed on the projection too** (`cal >= FOUR_STAR`
   blocked D3/D4), so half the sub-45 class — inflated to 4★+ perception by their
   ceilings — was barred from the only divisions that matched their current game.
4. **D1 recruited its walk-on seats.** `_openings` = graduating seniors for every
   division, so D1 signed ~3/program/year, refilling depth seats from the class.

## The owner's philosophy (this is the design, spelled out)

- **A program only has recruits near its own level on its radar.** Sub-45-STR
  players are *never in a D1 program's view* during the cycle — D1 can't make the
  mistake of signing them because it never sees them. Those players still **dream
  of D1 like real life** (aspiration is untouched); they're just not on the board.
- **Perception asymmetry by division.** D1 chases stars/hype (the ceiling
  projection — "win-now" plus brand-following, mistakes intended). D2 operates on
  current ability. D3/D4 weigh current ability and potential **evenly** (they'll
  take a project whose game is at their level today).
- **D1 signs scholarship players only — never walk-ons.** A D1 class tops the
  scholarship core back up to `SCHOLARSHIP_SLOTS` (6) **at the most** and stops.
  With the transfer portal there is no reason for a D1 to burn a signing on depth:
  walk-on seats backfill from the portal **or stay open**. This frees D1 seats,
  cascades better players down a level, and keeps the portal dynamic.
- **The asymmetry closes at both ends late.** In the last weeks D1s with open core
  seats sop up the best of whoever is left (best players choose them first); then
  D2–D4 fill the rest — the existing criteria (prestige, academics, geo, coach
  dice) still dictating every decision.
- **D3 and D4 are equal halves of one division**, not tiers. (D4 still out-signs
  D3 mid-season because the tier's brand names — the academic-elite flagships,
  Swarthmore/Emory/W&L-class, prestige to 0.395 + academics to 0.99 — all live in
  D4 and recruit early; that's the criteria working, not a pecking order.)
- **≤45 STR players are ~90% D2–D4 material.** D2 is their goal; low-D1 happens
  only when a program has nothing left to hold for, and not much even then.

## Fixes

### 1. `recruit_economy.program_level_floor(level_caliber, progress)` — the radar
Every program (funded or not) holds for recruits within `_LEVEL_STANDARD_BAND`
(0.06) of its own level — measured against the recruit's **current ability**
(public STR on the caliber scale), *not* the scouting projection, so a raw kid
with a huge hidden ceiling still slots to his level. Holds through
`_STANDARD_HOLD` (0.75) of the window, then ramps down to `_LEVEL_RESIDUAL`
(0.65) of itself — **never to zero** — so on signing day a power sops up only the
best leftovers and the rest slot to their division. Applied in both the scored
loop and the widen-once fallback of `_pick_school` (the fallback keeps the level
floor even at full relax; budget/division/caliber floors still drop).

The budget-side `program_caliber_floor` (elite seat-holding) is unchanged and
still runs on `perceived_caliber` through each coach's stars↔results lens —
that's where D1's hype-chasing (and its intended mistakes) lives.

### 2. Window floor + D3/D4 gate key on current ability (`_pick_school`)
- Candidate window: `lo = min(cal, cur_cal) − 0.30` — however high a kid aspires
  (the `hi` bound is still projection-driven; the D1 dream is intact), programs at
  the level he plays *today* always have him in view and compete for him.
- D3/D4 division gate: keys on `(cal + cur_cal) / 2` — current and potential
  **evenly weighted**, the non-scholarship tier's own philosophy. A currently-elite
  player still never drops to D3/D4; a hyped project can.

### 3. D1 classes are scholarship-core-only (`_openings`)
D1 openings = `min(SCHOLARSHIP_SLOTS − returning core, roster cap − returning)`,
floor 0. D2–D4 unchanged (graduating seniors). D1 never signs into walk-on seats;
depth comes from the portal or runs short. Note the knock-on: D1 rosters thin from
12 toward the ~6–8 range over several seasons unless the portal backfills — that
is the point (portal dynamism), and the lineup engine already plays short-handed
gracefully (`season.coach_lineup` presses the least-hurt back in; clamps under 6).

## Measured (`scripts/sim_signing_drip.py`, window 18, men / women)

| | before | after |
|---|---|---|
| Week-10 by division | D1 1137 · D2 122 · **D3 0** · D4 194 | D1 145 · D2 302 · **D3 48** · D4 389 |
| Final by division | D1 1137 · D2 612 · D3 427 · D4 324 | D1 216 · D2 612 · **D3 912** · D4 739 |
| ≤45-STR recruits landing D2–D4 | **54% / 52%** | **97.9% / 96.6%** (D1 takes 37 / 61 of ~1,800) |
| True elites (cal ≥ 0.70) signing | 100% | 100% |
| Class signed by rollover | 100% | 99.2%+ (leftovers → D3/D4 pool walk-ons, as designed) |

D3 now signs continuously from the early weeks and finishes as the volume half of
the bottom tier; D4's mid-season lead is its academic-elite flagships recruiting
early (intended). Verified on the real `advance_week` path too (fresh world, 6
weeks, both genders): D1 316 · D2 343 · D3 17 · D4 507 — same shape as the sim.

**Year-0 note:** built rosters carry the 8+4 core shape, so most D1 programs open
season 1 with a returning core ≥ 6 and sign only a handful (~0.6/program). That's
the rule working — the core has to graduate down to 6 before D1 classes reach
their ~1.5/program steady state.

## Fog-of-war note (refinement, not a reversal)

`AAR-fog-of-war-recruiting` bars the AI from *evaluating* recruits by true
ability. This change does not re-wire evaluation: preference, hype and the funded
seat-holding all still run on perceived caliber, and D1 still over-drafts flashy
busts *within its level band* — the mistakes the portal exists to correct. What
the owner clarified is that **current ability (public STR — it's on the recruit's
public card) is visible to everyone as a matter of level-placement**: the fog is
on what a player will *become*, never on what he *is today*. Radar/level gates
therefore read current ability; projection gates read perception.

## Dials
- `_LEVEL_STANDARD_BAND` (0.06) — how far below its level a program reaches
  mid-cycle. Raising it lets D1 see further down (0.10 puts the lowest D1's radar
  at ~53 overall ≈ 45 STR — the border; don't go past it).
- `_LEVEL_RESIDUAL` (0.65) — how much standard survives on signing day; lower =
  powers sop up more leftovers, 1.0 = they never reach down at all.
- `SCHOLARSHIP_SLOTS` (6, `ncaa.py`) — the D1 class cap is derived from it.

## Tests
`tests/test_recruit_signing.py` passes unchanged (floor pure-function tests,
elite-signing integration, territory pull). The full-cycle invariants hold: elites
100%, ≥95% of the class signed with everyone else pool-walk-on'd at rollover.
