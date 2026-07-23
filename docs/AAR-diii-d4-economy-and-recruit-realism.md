# AAR — DIII/D4 economy overhaul + recruiting realism

**Date:** 2026-07-23
**Scope:** An owner-directed pass, sparked by real DIII coverage (r/10s + The 3rd
Set Blog on NESCAC/UAA), to (1) fix the D4 tier inversion, (2) put playing time and
academics into the recruiting decision, (3) diversify the fall portal, and (4) make
the Power Index forgive losses to strong teams. Every value below is an
**intentional owner decision** — do not "fix" a number to satisfy a stale test.

Files: `rating.py`, `recruit_economy.py`, `ncaa.py`, `scholarships.py`, `world.py`,
`recruiting.py`, `web/state.py`, `web/server.py`, templates `player.html` /
`recruit.html`.

---

## 1. The D4 inversion — the headline fix

**Problem.** D4 was carved out of D3 as the *academic-first* tier and holds the real
best-in-class academic programs — **NESCAC, UAA, SCIAC (CMS), NCAC (Denison),
Centennial, Liberty League**. But the engine modeled D4 as the **weakest** tier:
`DIVISION_PRESTIGE_RANGE["D4"] = (0.04, 0.10)` clamped the Williams/Amherst/CMS
prestige bumps (0.17–0.18) down to ~0.10, D4 carried **no** scholarship budget, and
`_TALENT["D4"]` sat below D3. So the strongest non-D1 programs in the country were
simulated as the worst.

**Fix — D4 joins the scholarship economy, gated on academics.**
- **Budget band `_D4_BAND = (3.0, 8.0)`** (`recruit_economy`): every D4 program funds a
  floor of 3, the top-academic programs 6–8, positioned by prestige across
  `_D4_PRES_LO/HI = 0.09..0.40` (the elite academic confs are lifted above the base
  band by the academic-conference recruiting draw, so they spread across 6–8).
- **D4 builds via the star-plan** like D1/D2 (`ncaa.build_roster` `use_budget` now
  includes D4). D4 talent band lifted to `(46, 22)` men / `(40, 20)` women — its top
  reads near a **D1 walk-on**, which is the point (see the blog's "kid that'd walk on
  at a D1").
- **Prestige range widened** to `(0.08, 0.20)` so the academic bumps register.
- **Aid display** (`scholarships.py`): D4 = `count 6, rate 0.70, cap 6.0` (mirrors D2)
  so the budget has slots to spend and D4 shows funded aid like D2.

**Why D2 still beats D4 on average.** The **academic gate**. D4 can *afford* top
talent but can't *admit* all of it, so most D4 sit at budget 3–4 (median 4) while D2
runs 4–6 and takes anybody — D2 > D4 on average, even though a top D4 out-funds a mid
D2 and is genuinely elite. That gap is the whole design: talent D4 must pass on flows
to the open divisions.

### The academic gate (`recruit_economy.d4_academic_min`)
A recruit needs a minimum test score (`academic_rating`, 59–99) to sign at a D4
program. It is **per-program**, scaled by the program's academics normalized across
the D4 span (`_D4_ACAD_LO/HI = 0.60..0.99`):
- `D4_MIN_FLOOR = 67` (~SAT 960) — absolute floor, no D4 admits below it.
- `D4_MIN_CEIL = 90` (~SAT 1400) — a Caltech/MIT-tier strict-year minimum. **MIT never
  admits 900s.**
- `D4_MIN_SWING = 5` — a lenient class admits a touch lower year to year, never below
  the floor.

Enforced in `world._pick_school` for signings (a **HARD** bar — it never relaxes, even
on signing day) and in `ncaa.build_roster`, which lifts a below-gate generated D4
player into `[gate, gate+7]` so a D4 roster is academically self-consistent (and its
visible SAT scores read right). Test scores are on the real **800–1600 scale** on
player pages (`recruiting.academic_sat`; new TEST stat block).

### Test scores track the program (`ncaa.ACADEMIC_TILT`)
The old draw was a flat `N(79, 9)` for everyone, so a blue-blood tennis factory and an
academic power looked identical. Now every roster's admissions center scales with the
program's academics: `center = 79 + (academics − 0.5) × 22` (internationals a touch
lower). Measured roster-mean SATs: **Harvard ~1410, Northwestern ~1425, Chicago ~1355,
Stanford ~1380, Duke ~1330** vs athletic-first **Texas ~1190, Tennessee ~1170, Georgia
~1150**. Division means: D1 ~1224, D2 ~1165, D3 ~1230, **D4 ~1349** (highest — the
academic tier); population ~1252. Any high-academic program is covered automatically
(no per-school wiring); the D4 gate floor layers on top.

---

## 2. D3 = widest-variety, lowest-floor tier
`_TALENT["D3"]` → `(39, 27)` men / `(33, 23)` women: base dropped and spread widened
so D3 holds the **broadest** range AND the **weakest** pool players — the leftovers
after D2 absorbs and D4 admits its academics. Measured roster-mean spread: D3 ≈ 17 OVR
(floor 36) vs D2/D4 ≈ 5. D3 stays non-scholarship (its top programs keep the thin 1–3
gem allocation; `_d3d4_funded` is now D3-only).

## 3. Aggressive D2 absorption
`recruit_economy.program_level_floor` is now division-aware: D2 uses a wide
`_D2_REACH_BAND = 0.22` (vs the standard 0.06), so it pursues recruits well below its
own level from the start of the cycle and **absorbs** mid-tier talent that would
otherwise sink to D3/D4. Owner-authorized relaxation of the strict per-level radar
(§3b of the recruiting rules) for D2 only.

## 4. Playing time as a recruit factor
Recruits now weigh whether their OVR would crack a program's **current top 6**
(`world._pick_school`): `PLAY_TIME_WEIGHT = 0.35`, saturating over
`PLAY_TIME_SCALE = 8` OVR points of top-6 margin. A would-starter gets up to +35%, a
buried recruit −35%. It's a **key** factor but sits **below prestige** — the
`(0.15 + pres)` term spans ~4× and still dominates, so recruits still aspire up; they
just stop blindly signing where they'll never play. Surfaced on the recruit board: a
new **ROSTER FIT (TOP 6 OVR)** column shows each offering program's current top-6 and
whether the recruit projects Starter / Rotation / Depth.

## 5. Warm-weather + big-city tiebreakers
Marginal only. Per-recruit `prefers_warm` / `prefers_big_city`
(`recruiting.recruit_geo_prefs`, deterministic from pid — no schema change; ~50% /
~40%) nudge toward programs in warm states (`ncaa.WARM_STATES`) or big metros
(`ncaa.BIG_METRO_CITIES`) by `WARM_APPEAL_WEIGHT` / `CITY_APPEAL_WEIGHT = 0.06`. It
advantages bigger/warmer places only when programs are otherwise a wash — and can pull
a recruit **against** the home-state tug (a warm-preferring kid from a cold state leans
south).

## 6. Fall portal diversification
`_FPPlanner.best_placement` replaces the top-prestige-first `best_in` in the auto
discovery path: among open-seat programs in the fitting division where a riser would
make the lineup, send them where they'd **slot highest** (biggest lineup upgrade / most
playing time), prestige breaking ties. Underutilized talent now spreads to the programs
that need it instead of funneling to the same blue-bloods every resolve. One-riser-per-
program (`received`) and the median fit bar are unchanged.

## 7. Asymmetric loss weighting (Power Index)
`rating.compute_ratings`: a loss now counts as `1 − LOSS_FORGIVE·S[opp]` of a game in
the win% denominator (`LOSS_FORGIVE = 0.55`), recomputed each SOS iteration as opponent
ratings firm up. A loss to a top team barely dents the rating; a loss to a weak one
still stings. Wins are never discounted; the road-win +10% bonus is unchanged.

---

## Tuning knobs (all named constants)
`rating.LOSS_FORGIVE` · `recruit_economy._D4_BAND` / `_D4_PRES_*` / `D4_MIN_*` /
`_D2_REACH_BAND` · `ncaa._TALENT` / `DIVISION_PRESTIGE_RANGE` / `WARM_STATES` /
`BIG_METRO_CITIES` · `world.PLAY_TIME_WEIGHT` / `PLAY_TIME_SCALE` /
`WARM_APPEAL_WEIGHT` / `CITY_APPEAL_WEIGHT`.

## Watch-outs for the next agent
- D4 is **not** the weakest tier anymore and is **in** the scholarship economy. Do not
  restore `_D4_BAND`-less budget=0 or the tiny D4 prestige clamp.
- The D4 academic gate is a **hard** admissions bar; it intentionally does not relax on
  signing day. D4 leaving talent on the table is the design, not a fill bug.
- D2 > D4 on average is intended; top individual D4 programs beating a mid D2 is also
  intended.
