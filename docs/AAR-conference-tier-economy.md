# AAR — Conference-tier economy: re-leveled tiers, tier-keyed budgets, steep costs, D3/D4 gems

**Date:** 2026-06-24
**Scope:** `ncaa.CONF_PRESTIGE` / `CONF_TIER` / `conf_tier` / `_prestige` ref;
`recruit_economy` (TIERS costs, `_D1_TIER_BANDS`, `_D2_BAND`, `_D3D4_BAND`,
floors, `_prestige_tier`, D3/D4 funding); `ncaa.build_roster` (D3/D4 gem lift);
`seasonmode` AQ-bonus tiers; CLAUDE.md tables; `tests/test_roster.py`.

> Supersedes the budget-band and recruit-cost numbers in
> `AAR-recruiting-prestige-budget-redesign.md` and `AAR-recruiting-budget-economy.md`.
> The *mechanism* (budget economy, cost-by-star, floors, aid-display separation)
> is unchanged; the **numbers and the budget KEY** changed.

## 1. Conferences are now a master 4-tier hierarchy (owner-curated)

`ncaa.CONF_TIER` (D1) is the single source of truth: **Blue Blood / Major /
Mid-Major / Low-Major**, hand-curated, NOT derived from a prestige percentile.
`CONF_PRESTIGE` is **re-leveled to agree** with the tiers so budget, on-court
strength, and tournament seeding all follow one ranking. Re-leveling a league
moves its strength AND budget together (owner decision — "tiers are master, I
don't care about the exact prestige numbers, make them fit").

- **Blue Blood (6):** Pac-16, SEC, ACC, Big 12, Big Ten, **Yankee** (promoted)
- **Major (6):** Ivy, WCC, MW, Big East, **UAA**, **Heritage** (UAA/Heritage lifted)
- **Mid-Major (9):** Big West, **CIC** (demoted from Major), Sun Belt, A-10, ASUN, MAC, WAC, CAA, Patriot
- **Low-Major (13):** **CUSA** (dropped), SoCon, Southland, Meridian, Big Sky, MVC, Summit, Big South, Horizon, America East, OVC, MAAC, NEC

`seasonmode._conf_tier_map` reads `CONF_TIER` for D1 (so the tournament AQ seeding
bonus matches the budget tiers) and falls back to a prestige-percentile split for
D2–D4. `_AQ_BONUS = {top 100, major 65, mid 35, low 12}`.

## 2. Budget is keyed on CONFERENCE TIER, with a decoupling escape hatch

`recruit_economy._D1_TIER_BANDS`: **top 16–26 · major 9–16 · mid 6–9 · low 6–7**.
A program funds *within* its tier's band by its own prestige, plus a per-world
jitter (top tier redraws yearly). Non-top budgets are clamped to ≥ band floor, so
"low = 6" really means ≥6.

**Decoupling (`_prestige_tier`):** a program whose OWN prestige outranks its
conference tier funds UP to its prestige tier — so a school genuinely better than
its league isn't capped by it. Normally a no-op (prestige is re-leveled to match
the conf tier); it bites only when a `PRESTIGE_SCHOOLS` bump or an editor override
pushes a program across a prestige cut. This is the owner's "some schools are truly
better than their conference and shouldn't be penalized" lever. (On-court latent
strength still tracks the *conference* prior, so decoupling lifts RECRUITING, which
makes the roster stronger over time — not the base strength draw.)

`_D2_BAND = (4, 6)` — stabilized tight, brushing D1 low at the top.

## 3. Steep cost curve + re-tuned floors

`TIERS` costs: **Blue Chip 7 · 5★ 3.5 · 4★ 3 · 3★ 2 · 2★ 1 · 1★ free**. A premium
core is now a real investment. `_TIER_FLOOR`: blue-chip **16.5** (Blue Bloods only),
5★ **10.5** (Major+), 4★ **5.0** (any funded D1 / top D2 — low enough that 4★s
always find a home), 3★ anywhere. Running-recruiter mirrors: `recruit_budget_floor`
(0.62→10.5, 0.55→5.0), `_PROGRAM_CEILING` first cut → 16.5.

Net result (D1 men, top program per tier): Blue Bloods land ~3 blue-chips + a 5★;
Majors a 5★/4★ core; Mid-majors a 4★/3★ core; Low-majors a 3★ core + walk-ons. No
mid-major can stack 5★s (the bug that started this).

## 4. D3/D4 "hidden gem" allocation (`_D3D4_BAND`, `build_roster`)

D3/D4 still carry no athletic money EXCEPT the top: **D4 academic-elite leagues**
(academics ≥ 0.85, which ARE tagged) and the **Top-20 D3 programs by prestige**
(academic confs aren't tagged in D3 anymore, so it's a per-save prestige cap, via
`_d3_top_keys`). They get a **1–3** budget. In `build_roster` this LIFTS only the
slots where the budget lands a real recruit tier above the program's conf-strength
baseline (`talent = max(baseline, gem)`), leaving everyone else untouched — so
non-funded D3/D4 rosters are unchanged. Verified: funded Amherst (D4) top-3 ≈ 47
vs an unfunded D4 ≈ 37.

## Gotchas
- **`test_roster.test_roster_talent_tracks_program_strength`** was flipped: it
  differentiated two D1 programs by the raw `strength` field, but **D1 roster
  talent is budget-driven** (`build_roster` line — `talent = tier_grade(plan[i])`;
  `tmean`/strength is only used for D3/D4). It was passing on an RNG coin-flip.
  Rewrote it to differentiate by prestige+conference (the real budget driver).
- Budget-by-conf-tier means a synthetic/edge program with an unknown `conf_abbr`
  defaults to tier "low" — but `_prestige_tier` lifts it back up if its prestige is
  high, which is what keeps the strength/quality intent intact.
- `test_web_recruiting.test_recruiting_board` fails on a **date** issue (class of
  2027 vs 2026 now that the sim clock is mid-2026) — pre-existing, unrelated.
