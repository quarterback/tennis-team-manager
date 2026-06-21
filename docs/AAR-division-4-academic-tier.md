# AAR — NCAA Division IV: an academic-first tier carved out of D3

**Date:** 2026-06-21
**Scope:** A user-directed expansion from three NCAA divisions to four. D3 had
grown past 400 full members, so a new **Division IV** — the regional,
academic-first liberal-arts tier — was carved out of it, then the engine was
wired to simulate four concurrent divisions instead of three. Data spans
`data/ncaa/d3_{men,women}.json` (trimmed) and new `data/ncaa/d4_{men,women}.json`;
code spans the world/recruiting/season/web layers.

## What D4 is

D3 = competitive, athletics-oriented non-scholarship schools. **D4 = regional,
academic-first liberal-arts colleges** with a student-first, de-emphasized-athletics
model. It sits **below D3** in the classification order (rank 4), runs an 8-team
ITA Team Indoor (no Kickoff), and a standard 64-team NCAA championship.

## Membership

**19 founding conferences, 188 schools** (both genders identical), moved intact
from D3 with autobids preserved:

NESCAC, Liberty League, Centennial, NCAC, ODAC, SCIAC, SAA, PAC, Landmark,
NEWMAC, MIAC, Midwest, Northwest, SCAC, CCS, CCIW, Empire 8, Conference of New
England, Coast to Coast.

The size was a user decision (offered ~140 / ~188 / ~205; chose **~188, "broad
academic"**). Selection principle: academic-first / liberal-arts identity first,
then size — so the more athletics-oriented regional and public-school leagues
stayed in D3.

**NESCAC split.** The dataset's 16-team NESCAC had folded in the schools that are
really Liberty League members, so it was divided into two eight-team conferences:
NESCAC (Amherst, Bates, Bowdoin, Colby, Middlebury, Tufts, Wesleyan, Williams)
and a revived Liberty League (Bard, Hobart and William Smith, Ithaca, Skidmore,
Vassar, Connecticut College, Hamilton, Trinity (CT)). User chose an even 8/8
split over the historically exact 5/11.

## Net effect

| Division | Schools | Conferences | Prestige band (men) |
|---|---|---|---|
| D1 | 395 | 34 | 0.40–0.94 |
| D2 | 285 | 23 | 0.20–0.30 |
| D3 | 216 | 23 | 0.10–0.18 |
| **D4** | **188** | **19** | **0.044–0.395** |

D3 dropped from 404 → 216. No school is double-listed; both genders sum identically.

## Engine wiring (D4 = rank 4, below D3)

Every place that enumerated or keyed on division was extended:

- **`world.py`** — `UNIVERSES`, `DIV_RANK` (D4:4), transfer up/down chain
  (`_UP_DIV`/`_DOWN_DIV`: D3↔D4), `_flat_programs` scan, `INTL_TIER_PULL` (D4 the
  lowest, 0.05), `_intl_tier`, and the recruit division gate `_div_ok`.
- **`ncaa.py`** — `UNIVERSE_PAIRS`, `DIVISION_PRESTIGE_RANGE`/`_CONF_PRESTIGE_REF`
  (new D4 band below D3), `_academic_prior`, and the (base, spread) talent band
  `_TALENT` (just below D3).
- **`scout_intel.py`** (`DIVISIONS`, `_DIVRANK`), **`worldconfig.py`** (`_ALL_DIV`),
  **`gtt_seasonmode.py`** (active-division default).
- **Economy** — `scholarships.DEFAULT_LIMITS`, `economy.SCHOLARSHIP_CAPS`,
  `recruit_economy.program_budget`: D4 is non-scholarship with zero recruiting
  budget, the same model as D3.
- **`ita.py`** — D4 runs an 8-team Team Indoor, no Kickoff.
- **`bracket.py`** — D4 uses the standard 64-team championship field.
- **Web** — `state.UNIVERSES` + `all_gender_programs`, three `server.py` dropdown
  loops, and the onboarding division checklist.

`load_division()` was already generic (reads `d{div}_{gender}.json`), so no loader
change was needed.

## Prestige model — the one subtle interaction

Mid-effort, `main` landed a redesign of prestige into **non-overlapping
per-division bands** plus an **academic-elite lift**: the NESCAC-tier academic
conferences punch *out* of their division's band because brand + classroom pull
recruits like a small D1. Those are exactly the conferences D4 took.

On rebase this was reconciled deliberately rather than mechanically:

- Added a D4 band **(0.04–0.10), cleanly below D3's (0.10–0.20)** — so the
  regional, non-academic D4 leagues (PAC, Landmark, Empire 8, CNE, C2C, CCIW)
  sit below D3 as the classification order implies.
- **Extended the academic-elite lift to D4.** NESCAC/Liberty League/SCIAC-tier
  schools keep their recruiting draw (Williams ≈ 0.395, same as it had in D3) —
  moving them to a lower athletic division does not erase their pull. This is why
  D4's prestige *range* (0.044–0.395) is wide and overlaps D3's: by design, the
  academic flagships punch above, the regional members sit at the bottom.
- The recruit gate `_div_ok(div, acad)` (also reworked on `main`) was extended so
  a 4★ can still choose an academic-elite D4 (an Ivy-calibre classroom is worth
  the athletic step down) while blue-chips never drop that far.

## Academic realignment within D4

The lift is conference-level (it keys on a conference's academic prior ≥ 0.80),
and only flagship schools carry an *intrinsic* academic rating — everyone else
inherits their conference's prior. So a genuinely elite college sitting in a
non-lift D4 league (e.g. **Carleton**, intrinsic 0.94, stranded in MIAC) ranked
*below* D3. Rather than lower the lift threshold or invent more lift conferences,
the fix was a set of academics-driven, size-neutral conference swaps (geography
deprioritized per the user): the standout academic program moves up into a
lift conference, the lift conference's weakest member moves down in exchange.

| School | From → To |
|---|---|
| Carleton | MIAC → Midwest |
| Macalester | MIAC → Midwest |
| St. Olaf | MIAC → Midwest |
| Monmouth (IL) | Midwest → MIAC |
| Illinois College | Midwest → MIAC |
| Ripon | Midwest → MIAC |
| Washington and Lee | ODAC → Centennial |
| McDaniel | Centennial → ODAC |
| Whitman | NWC → SCIAC |
| La Verne | SCIAC → NWC |

A second round promoted four more borderline-but-credible programs the same way:

| School | From → To |
|---|---|
| Wheaton (IL) | CCIW → Midwest |
| Gustavus Adolphus | MIAC → Midwest |
| Lewis & Clark | NWC → SCIAC |
| Hampden-Sydney | ODAC → Centennial |
| Lake Forest | Midwest → CCIW |
| Cornell College | Midwest → MIAC |
| Cal Lutheran | SCIAC → NWC |
| Washington College | Centennial → ODAC |

Every conference size is unchanged. All nine promoted programs now clear D3
(≈ 0.26–0.36); the demoted ones drop into the low D4 band as intended.

## Verification

- D4 men's and women's seasons run to completion and are **seed-deterministic**
  (men's champ DePauw, women's Wilkes — both fittingly academic), before and
  after the NESCAC split.
- Full suite: **233 passed, 10 failed**; all 10 failures are **pre-existing on
  `main`** (scholarship-cap tests out of sync with the repo) and were confirmed
  to fail identically on a clean checkout. Zero new failures.

## Remaining shape

After the realignment, the 8 academic-elite D4 conferences (NESCAC, Centennial,
SCIAC, NEWMAC, Liberty League, NCAC, SAA, Midwest) sit **above D3** as recruiting
draws; the 11 regional D4 conferences (ODAC, MIAC, NWC, SCAC, CCS, CCIW, Landmark,
Empire 8, CNE, C2C, PAC) stay in the low band **below D3**. That two-group split
is intentional — those leagues are not academically distinctive enough to clear
the lift — but it can be revisited with more swaps if specific programs look
mis-sorted.
