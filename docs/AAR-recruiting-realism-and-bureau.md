# AAR — Recruiting realism (prestige tiers, star gates) + Bureau usability

## What it was before
Talent scattered to the wrong places. The prestige model banded divisions only
loosely and the conference weight was shallow, so:

- A high-prestige **D3** (UAA/NESCAC) or a high-academic Ivy could out-pull a
  low-major D1, and the **academic pull reached elite recruits** — so 5★/blue-chip
  kids could drift to academic or small-division programs.
- Within D1 the **Power conferences didn't clearly separate** from the mid- and
  low-majors, so the blue-chips weren't concentrating at the dominant programs.
- Because placement leaned on dice rolls within fuzzy bands, **weaker schools got
  more than their fair share** of talent. The resulting parity was fun to look at
  but made it genuinely hard to assess what was really going on — and it meant
  perfectly good lower-tier players (the 1★ who isn't *bad*, just not elite) were
  buried everywhere because talent wasn't leveling into the right opportunities.

The Analytics Bureau measured talent-vs-level but you couldn't sort/search by who
was good **right now**, and Scholarship Watch was redundant (talent-only).

## What changed
**Prestige is now tiered (`app/ncaa.py`).** `DIVISION_PRESTIGE` (0.66 / 0.40 /
0.26) makes every D1 outrank every D2 outrank every D3, and the conference weight
is steeper (×0.9) so within D1 the Power band sits clear of the mid-majors, clear
of the low-majors. Dominant programs now sit where they should.

**Star → division gate (`app/world.py` `_pick_school`).** A 5★/blue-chip never
signs D3; a 4★ only rarely (~5%); a 3★ and below can go anywhere. Combined with
the prestige window, the blue-chips concentrate at the top programs and talent
tiers downward instead of scattering.

**Academic gate tightened (`app/recruiting.py` `academic_gate`).** The academic
pull (Ivy/NESCAC/UAA advantage) is full for 3★, a thin sliver for 4★, and exactly
0 for 5★/blue-chips — academics land good-not-elite kids, never drag an elite down
(a blue-chip at Stanford/an Ivy is there on athletic prestige).

**Bureau — sort + search (`Underplaced Talent`).** Added a Sort lens — Most
underplaced / **Best right now** (current ability) / Highest ceiling — plus a
player/school search, so finding who's good today and worth moving isn't a scroll.

**Bureau — Playing-Time finder (was Scholarship Watch).** Reframed to D1/D2
**walk-ons who aren't in their own lineup**, each paired with the best program —
in or out of their division — where their **current** ability would make them a
starter. This is the piece that finally values the not-bad-not-elite player: it
surfaces the 1★ who'd start somewhere instead of sitting.

## Why this is better
- Blue-chips concentrate at dominant programs; talent tiers down the bands; the
  league reads like the real ITA/NCAA landscape (verified: 40 5★ + 80 4★ all D1,
  zero D3; lower tiers fill D2/D3).
- Opportunity levels honestly — a solid lower-tier player can be identified and
  moved to a lineup spot rather than being lost to noise.
- It's *assessable*: prestige tiers and star gates remove the dice-roll parity
  that made it hard to see what was actually happening.

## Verification
Full signing pass on a fresh world: 5★/4★ never D3, academic pull zero for elites,
P5 gets the lion's share. Underplaced sort/search and the Playing-Time finder
render and return sensible results (589 stuck D1/D2 walk-ons each with a real
landing spot). World + single-gender determinism suites pass.

## Files
- `app/ncaa.py` — `DIVISION_PRESTIGE`, steeper conference weight.
- `app/recruiting.py` — `FOUR_STAR` + rewritten `academic_gate`.
- `app/world.py` — `_pick_school` star→division gate (+ fallback).
- `app/scout_intel.py` — `playing_time_watch`; `underplaced_board(sort=, q=)`.
- `app/web/server.py`, `intel_underplaced.html`, `intel_scholarships.html` — sort/
  search controls, Playing-Time board, nav relabel.

## Still open
"Alphabetize the schools" — the common dropdowns are already sorted; need a
pointer to the specific list that isn't.
