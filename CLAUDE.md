# CLAUDE.md — agent guardrails for tennis-team-manager

College dual-match tennis simulator. Seed-deterministic engine; D1/D2/D3/D4 ×
men/women. Most tests assert invariants/determinism, not golden values.

---

## ⚠️ Recruiting & scholarship economy — DESIGN INVARIANTS (do NOT "fix" without reading)

These values are **intentional game-design decisions**, not bugs, and several
**deliberately diverge from real NCAA rules**. A failing test is NOT proof the code
is wrong — the test may be the stale side. Before changing any number here, read
`docs/AAR-recruiting-prestige-budget-redesign.md`,
`docs/AAR-recruiting-budget-economy.md`, and
`docs/AAR-scholarship-full-funding-rule.md`, and check `git log`.

### ‼️ The big one: a program does NOT have a flat 8 scholarships
Rosters are built by a **scholarship-BUDGET economy**, not a fixed scholarship count.
A program **has a budget** (by prestige tier) and **spends it on recruits**, who
**cost** scholarships by star. The "8" you'll see in `scholarships.py` is a *separate,
downstream aid-DISPLAY layer* — do not mistake it for "the program's scholarships."

### 1. Recruiting budget = what a program actually has to spend (`recruit_economy._D1_BANDS`, `_D2_BAND`)
Per-program budget (scholarship equivalency), with a per-world jitter; only D1 power
redraws season-to-season:

| Tier | Budget band |
|---|---|
| D1 power (prestige ≥ 0.79) | **15–24** (wide, so blue-bloods separate) |
| D1 high-major (≥ 0.62) | 12–14 |
| D1 mid-major (≥ 0.50) | 10–12 |
| D1 low-major | 6–10 |
| D2 | 2–9 (elite D2, prestige ≥ 0.28, fully fund at 9) |
| D3 / D4 | 0 (no athletic money — fit/academics prior) |

### 2. Recruit cost by star — what the budget is spent on (`recruit_economy.TIERS`)
| Tier | Cost (scholarships) |
|---|---|
| Blue Chip | **3** |
| 5★ | **2** |
| 4★ | **1.5** |
| 3★ | **1** |
| 2★ / 1★ | **free (0)** |

### 3. Tier floors gate attainment (`_TIER_FLOOR`)
A program must clear a budget floor to *attract* a tier (not just afford it):
blue-chip ≥ 13.5, 5★ ≥ 10.5, 4★ ≥ 8.5, 3★ and below anywhere. So clustering is
earned: only powers land blue-chips (e.g. budget-24 power can buy eight blue-chips;
a budget-8 program can attract none).

### 4. Aid-DISPLAY caps — a SEPARATE layer (`app/scholarships.py`)
Distinct from the budget above. `economy.allocate_scholarships` spreads a per-division
cap across the recruited core as full-ride/partial *display fractions* — it does NOT
determine roster quality (the budget does). Rule `d885f31` "fully fund men to match
women": caps are D1 **8.0**, D2 **6.0**, D3/D4 0.0, **same for men and women** (NOT
real men's 4.5 equivalency). Do **not** lower men to 4.5 to satisfy an old test — that
reverts the rule. (I did exactly this once; it's the mistake this section prevents.)

---

## ⚠️ Roster capacity & walk-on sourcing (`ncaa.roster_cap`, `autogen_walkons`)
Rosters are NOT a flat 8. Per-division caps = funded core + walk-on depth:
**D1 12** (8+4) · **D2 10** (6+4) · **D3/D4 16** (3+13). Walk-on sourcing:
- **D1/D2**: walk-ons from the recruit pool ONLY — never auto-generated. Carry "up
  to" cap; if a program doesn't sign enough, it runs fewer walk-ons.
- **D3/D4**: fill from leftover pool recruits first (`world.assign_pool_walkons` — no
  junior goes unsigned), then auto-generate only the still-empty seats
  (`refill_walkons`).
`RECRUIT_POOL = 2500`/gender is sized to roster turnover (~2,200); don't drop it back
to the old 1,000 or D1/D2 can't fill from real recruits. See
`docs/AAR-roster-expansion-walkons-recruit-pool.md`.

## ⚠️ Injuries are the ONE non-deterministic system — by design (`app/injuries.py`)
The engine is seed-deterministic everywhere EXCEPT injuries, which roll on **real
entropy** (`random.SystemRandom`). This is a deliberate owner decision ("I never
wanted a deterministic sim… save scumming is fine, I'm the only player") — do NOT
"fix" it back to a seed. Calibration (don't casually retune): `BASE_RATE=0.025`
per-dual, durability-scaled; ~**0.5 starters hurt at any time**; **1-in-100**
season-ending; otherwise **out 1–6 duals**.
- **Wiring:** dice in `injuries.py`; lineup filter in `season.coach_lineup`
  (`unavailable` pids) so depth gets pulled up; per-**save** persistence + rolling
  in `seasonmode` (`injuries` table, keyed by season_id — NEVER store injury state
  on `build_roster` Prospects, they're globally cached and shared across saves).
- **Medical redshirt:** a season-ending injury → `world.graduate(rosters,
  redshirts)` repeats the class with an `RS-` tag that persists to graduation
  (RS-Jr → RS-Sr → grad = 5th year). The tag is cosmetic; strip it with
  `world._base_class` anywhere you key off class year.
- **Tests:** an autouse `conftest` fixture disables injuries (determinism);
  `test_injuries.py` re-enables + seeds. See `docs/AAR-injuries.md`.

## Other notes
- International roster share is by division + gender + academics + a coach dice roll;
  academics damps it (academic schools are US-heavy). See
  `docs/AAR-base-roster-nationality-by-level.md`. Tuned for playability, not 1:1 realism.
- Pre-existing test fragility: `test_roster` `strong > weak` is a borderline
  calibration check that can flip with RNG shifts — investigate, don't blindly edit.
- Run the full suite with `python3 -m pytest -q` (≈10 min).
