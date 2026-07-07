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
A program **has a budget** (by **conference tier**) and **spends it on recruits**, who
**cost** scholarships by star. The "8" you'll see in `scholarships.py` is a *separate,
downstream aid-DISPLAY layer* — do not mistake it for "the program's scholarships."

### 1. Recruiting budget = what a program actually has to spend (`recruit_economy._D1_TIER_BANDS`, `_D2_BAND`, `_D3D4_BAND`)
Per-program budget (scholarship equivalency), with a per-world jitter; only D1 top
tier redraws season-to-season. The D1 band is keyed on the program's **prestige
tier** (`_prestige_tier`). At baseline prestige is re-leveled to the **CONFERENCE
TIER** (`ncaa.CONF_TIER` — the master 4-tier hand-curated hierarchy:
top/major/mid/low), so conference sets the *starting* band; the within-band slot is
set by prestige.

> ⚠️ **Prestige is DYNAMIC (YoY), not static.** A program's prestige drifts each
> world rollover by how it over/under-performs its expectation (`world.
> _update_prestige_momentum`; signed per-(school,gender) momentum persisted as
> `roster_overrides kind='prestige_dyn'`, applied in `load_division`, capped ±0.20).
> So budget moves BOTH ways over seasons: a low-major that keeps overachieving funds
> up a tier; a sliding blue-blood funds down. Tests asserting a fixed prestige must
> clear the momentum store. See `docs/AAR-dynamic-prestige-momentum.md`.

| Tier | Budget band |
|---|---|
| D1 Blue Blood (`CONF_TIER` "top") | **16–26** (wide, redraws yearly, so blue-bloods separate) |
| D1 Major / High-major ("major") | 9–16 |
| D1 Mid-major ("mid") | 6–9 |
| D1 Low-major ("low") | 6–7 (the floor, just above D2) |
| D2 | 4–6 (elite D2, prestige ≥ 0.28, funds at 6) |
| D3 / D4 | **0**, EXCEPT a thin **1–3 "gem" allocation** for the top: D4 academic-elite leagues (academics ≥ 0.85) + the **Top-20 D3 programs by prestige** (academic confs aren't tagged in D3, so it's a per-save prestige cap). Lets them sop up one undervalued recruit. |

### 2. Recruit cost by star — what the budget is spent on (`recruit_economy.TIERS`)
Steep curve (deliberately): a premium core is a real investment, so only the
deepest-funded blue-bloods stack blue-chips.

| Tier | Cost (scholarships) |
|---|---|
| Blue Chip | **7** |
| 5★ | **3.5** |
| 4★ | **3** |
| 3★ | **2** |
| 2★ | **1** |
| 1★ | **free (0)** |

### 3. Tier floors gate attainment (`_TIER_FLOOR`)
A program must clear a budget floor to *attract* a tier (not just afford it):
blue-chip ≥ **16.5** (Blue Bloods only), 5★ ≥ **10.5** (Major+), 4★ ≥ **5.0**
(any funded D1 / top D2 — cascades down so 4★s always find a home), 3★ and below
anywhere. So clustering is earned: only Blue Bloods land blue-chips; Majors top out
at a 5★/4★ core; mid/low majors build 4★/3★; a low-major can attract no 5★.

### 3b. Division radar — signing-time level gates (owner rule, do NOT relax)
The in-season signing drip (`world._pick_school`) is level-gated by CURRENT ability
(`recruit_economy.program_level_floor`): a program only has recruits near its own
level on its radar, so **sub-45-STR recruits are never in a D1 program's view**
mid-cycle (they still *dream* of D1 — aspiration is untouched). The floor ramps to a
**residual (0.65), never zero**, so late-window D1s sop up only the best leftovers.
D1 chases the ceiling projection (hype — its mistakes are intended); D2 reads current
ability; D3/D4 weigh current/potential evenly (their division gate uses the even
blend). **D1 classes top the scholarship core up to `SCHOLARSHIP_SLOTS` (6) and stop**
(`world._openings`): a D1 NEVER signs a recruit into a walk-on seat — depth backfills
from the portal or runs short, and rosters thinning toward ~6–8 over seasons is the
point (portal dynamism), not a bug. Target: ~90%+ of ≤45-STR recruits land D2–D4
(measured 97%+). See `docs/AAR-recruiting-division-radar.md`.

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
- **D1**: NEVER recruits walk-ons at all (owner rule 2026-07 — see §3b above): the
  class tops the 6-seat scholarship core and stops; depth backfills from the portal
  or runs short. Year-0 built rosters still carry the 8+4 shape; live worlds thin.
- **D2**: walk-ons from the recruit pool ONLY — never auto-generated. Carry "up
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

## ⚠️ Fall transfer portal — the ONLY in-season player movement (`world.fall_portal_proposals`)
After the ITA opener every universe HOLDS at a new **`fall_portal`** phase while the
world runs a cross-division reshuffle (sim proposes → user approves on `/fall-portal`
→ commit). It rescues genuinely mis-allocated talent (a D1-caliber player stuck in a
lower division) and is **deliberately curated**, not a migration:
- Risers are picked on **ability**, NOT ITA results (the opener is too few duals to
  trust). A riser must be a top-2 starter AND clear a **higher division's median
  level** (`div_level`); only the most mis-allocated move, capped at
  `FALL_PORTAL_MAX_RISERS` (**30/gender**). ~60 moves on a fresh world, not thousands
  — do NOT "fix" the cap/median bar away. A receiving program takes at most one riser
  (spread, no blue-blood funnel); displaced players cascade DOWN to fill open seats.
- A mover keeps **both stints** of the split season via a `stint` key on history
  entries (ITA at old school = stint 0, frozen at commit; regular+post at new school
  = stint 1, at year-end). `_record_world_history` idempotency is `(year, stint)`;
  the rollover **bakes** the move and clears the override (`_bake_fall_moves`).
- `fall_portal` is a HOLD only under the world driver (`advance_week` skips it);
  standalone `sm.advance` passes it straight through to `regular`. Toggle with
  `seasonmode.FALL_PORTAL_ENABLED`.
- The slate is **user-editable** (intents→resolve): the `fall_portal` table stores only
  rider INTENTS; cascades are derived by `world.resolve_fall_portal` on every view/commit
  (`_FPPlanner` — which MUST shallow-copy roster lists, since `developed_rosters` is a
  shared cache). You can redirect a rider, add one the sim missed, or drop one. An editor
  move made **while holding in `fall_portal`** is routed through the portal (gets the
  two-stint + cascade); outside the window it's a plain move. See
  `docs/AAR-fall-transfer-portal.md`.

## Other notes
- International roster share is by division + gender + academics + a coach dice roll;
  academics damps it (academic schools are US-heavy). See
  `docs/AAR-base-roster-nationality-by-level.md`. Tuned for playability, not 1:1 realism.
- Pre-existing test fragility: `test_roster` `strong > weak` is a borderline
  calibration check that can flip with RNG shifts — investigate, don't blindly edit.
- Run the full suite with `python3 -m pytest -q` (≈10 min).
