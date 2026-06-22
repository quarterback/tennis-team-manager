# AAR — D4 academic realignment: lifting stranded elite LACs above D3

**Date:** 2026-06-21
**Scope:** A user-directed, academics-driven reshuffle *within* Division IV
(`data/ncaa/d4_{men,women}.json`). No code changes; no new conferences; the
classification model from the D4 build is untouched. Two rounds of conference
swaps, 18 program moves total, every conference size preserved, both genders
kept identical.

## The problem

In the prestige model the **lift is conference-level** — a D4 program only gets
the academic-elite recruiting lift if *its conference's* academic prior ≥ 0.80
(`ncaa.ACADEMIC_D3_LIFT`). And only flagship schools carry an intrinsic academic
rating (`ACADEMIC_SCHOOLS`); every other school simply **inherits its conference's
prior**.

The consequence: a genuinely elite college sitting in a non-lift D4 league ranked
*below D3*, purely because of the company it kept. The starkest case was
**Carleton** — intrinsic academics 0.94, a top-10 national LAC — stranded in MIAC
(conference prior 0.66, no lift) at prestige ≈ 0.06, beneath every D3 league.

## The approach

Three options were on the table:

1. Lower the lift threshold — rejected; it would sweep in genuinely non-academic
   leagues wholesale.
2. Add more lift conferences — rejected by the user ("rather than adding more
   boosting conferences").
3. **Realign individual programs** — chosen. Move a stranded elite *up* into a
   lift conference, and move that conference's weakest member *down* in exchange.

Swaps are **size-neutral** (1-for-1) and **geography is secondary** (per the
user), so a cross-region move is allowed when the academic fit is right.

A subtle but important effect: because non-flagship academics are conference-
inherited, the move *itself* sets the rating right — e.g. Washington and Lee,
inheriting ODAC's 0.67, jumps to Centennial's 0.92 and clears the lift. The
demoted school inherits its new (lower) league's prior and drops out of the lift.

## Round 1 — five clear elites

| Promote ↑ | From → To | Demote ↓ | From → To |
|---|---|---|---|
| Carleton | MIAC → Midwest | Monmouth (IL) | Midwest → MIAC |
| Macalester | MIAC → Midwest | Illinois College | Midwest → MIAC |
| St. Olaf | MIAC → Midwest | Ripon | Midwest → MIAC |
| Washington and Lee | ODAC → Centennial | McDaniel | Centennial → ODAC |
| Whitman | NWC → SCIAC | La Verne | SCIAC → NWC |

## Round 2 — four borderline-but-credible (user-named)

| Promote ↑ | From → To | Demote ↓ | From → To |
|---|---|---|---|
| Wheaton (IL) | CCIW → Midwest | Lake Forest | Midwest → CCIW |
| Gustavus Adolphus | MIAC → Midwest | Cornell College | Midwest → MIAC |
| Lewis & Clark | NWC → SCIAC | Cal Lutheran | SCIAC → NWC |
| Hampden-Sydney | ODAC → Centennial | Washington College | Centennial → ODAC |

## Net effect

**Nine programs lifted from below D3 to above it.** Receiving conference (a lift
league in each case) and resulting prestige:

| School | Now in | Prestige | (was) |
|---|---|---|---|
| Washington and Lee | Centennial | 0.361 | 0.067 |
| Hampden-Sydney | Centennial | 0.361 | 0.066 |
| Whitman | SCIAC | 0.311 | 0.064 |
| Lewis & Clark | SCIAC | 0.311 | 0.062 |
| Carleton | Midwest | 0.260 | 0.063 |
| Macalester | Midwest | 0.260 | 0.067 |
| St. Olaf | Midwest | 0.260 | 0.068 |
| Wheaton (IL) | Midwest | 0.260 | 0.057 |
| Gustavus Adolphus | Midwest | 0.260 | 0.062 |

For reference, the top of D3 is NJAC at ≈ 0.174, so all nine now clear the
division below them. The nine schools they displaced (Monmouth (IL), Illinois
College, Ripon, McDaniel, La Verne, Lake Forest, Cornell College, Cal Lutheran,
Washington College) fall into the low D4 band (≈ 0.05–0.07), which is where
comparable regional programs already sit.

## Implementation notes

- A single script per round loaded both gender files, moved each team string by
  **exact match** between conferences (asserting the school was found in its
  source league), re-sorted every roster alphabetically (file convention), and
  asserted the per-conference counts were unchanged before writing.
- The eight lift conferences (academic prior ≥ 0.80) are unchanged as a *set* —
  NESCAC, Centennial, SCIAC, NEWMAC, Liberty League, NCAC, SAA, Midwest. Only
  their *membership* shifted.

## What was deliberately left

- **Landmark** contributed no promotions — its strongest programs (Juniata,
  Susquehanna) are solid-regional, not academic-elite, so nothing there clears
  the bar.
- The 11 regional D4 conferences (ODAC, MIAC, NWC, SCAC, CCS, CCIW, Landmark,
  Empire 8, CNE, C2C, PAC) remain below D3 by design — after the swaps they hold
  the genuinely non-elite/regional programs.

## Verification

- D4 men's and women's seasons run to completion and stay **seed-deterministic**
  across both rounds (men's champ DePauw, women's champ Caltech).
- No code touched, so the broader suite is unaffected (still the 10 pre-existing
  `main` failures, zero new).
