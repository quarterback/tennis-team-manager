# AAR — Talent compression + the pro tier

> **Status:** Stage 1 (talent compression) is **locked** to owner-approved calibration.
> Stage 2 (the portal-only pro tier) is **fully wired and tested** end to end. The one
> deferred item is the 1,000-dual engine-validation pass and re-baselining the old
> calibration unit tests (see *Open items*). The full suite was intentionally **not** run
> per owner while the calibration is settling.

---

## 1. The vision (owner)

Reject the "video-game pyramid" (a handful of greats, everyone else falls away). Instead:
- **Everything lifted + compressed.** A fat band of genuinely-good players; the floor rises;
  divisions overlap heavily instead of stacking. A great D3 kid can out-talent a mid-D1 kid
  — he's just "ranked lower because he didn't win."
- **Rosters tighter, but organically loose.** An elite roster runs **~2–3 UTR** deep, not the
  old 7-UTR cliff (and not the absurdly-stacked real Texas 0.7). Haves/have-nots still emerge
  — **don't blow up the structure, boost the levels.** "Not everyone across the board should
  have access to this talent — that's the point." More teams than real college tennis → a
  **college-basketball feel with tiny rosters.**
- **Separation from the engine, not the generator.** With talent near-equal, match scores
  (attributes + margins) decide who's actually good — also the best **engine test**: 1,000
  duals of 68v69 / 71v72 / 77v77 should still separate the good from the rest.
- **A pro tier above the college ceiling.** Elite ex-pros, **green-badged, portal-only**,
  real STR, entering every portal cycle.

### Owner acceptance numbers
- **Floor:** absolute bottom (D3/D4, rock-bottom D2) ~grade 36–49; **no hard cap** — "if they
  fall they fall" (a natural low tail is fine).
- **D3/D4:** *average* roster **UTR ~7**; better programs reach 8–9, the occasional 10. No
  engineered D3/D4 spread — it emerges from the sim.
- **Elite roster depth:** ~2–3 UTR #1→#6 (looser than the stacked real Texas).
- **Pros:** **OVR 81–90**, clearly better (not superpowered), real STR/OVR, green badge,
  **recruitable only in the portal**. *(This bullet is the original brief; it evolved — the
  shipped model is free agents at cost **18–30**, signed by hand across the pre-season + fall
  windows. See §3b-iii.)* A **live UI lever** controls the pool size. **Only pros exceed 80;
  every other cap is unchanged** (33.5 is the *elite-only* budget top).

---

## 2. Stage 1 — talent compression (LOCKED)

| Lever | Change | Effect |
|---|---|---|
| `recruit_economy.TIERS` (D1/D2 roster grades) | Blue Chip 70→**74**, 5★ 64.5→**71**, 4★ 58.7→**67**, 3★ 52.9→**62**, 2★ 47→**56**, 1★ 41→**50** | the 29-pt cliff → a ~24-pt ladder a roster only samples a slice of, so 1–6 cluster; budget economy (who *signs* which star) unchanged |
| `_D1_TIER_BANDS["top"]` | blue-blood budget cap 26 → **33.5** (elite tier only) | deeper elite cores; also lets elites afford pros |
| `ncaa._TALENT` (D3/D4 + program levels) | D1 (56,23)→(60,16) · D2 (50,58)→(50,24) · D3 (33,44)→(43,20) · D4 (28,44)→(40,18) (+women) | bases lifted, spreads compressed; heavy division overlap |
| Floor clamp (`_talent_mean`, `_base_roster`) | **kept at 24** (no artificial lift) | per owner "no caps"; the low tail forms naturally |

**Resulting men's shape:** population peak up ~2 UTR; top fattened (75–79: 1→**25**, 70–74:
103→**258**); per-division avg UTR **D1 10.2 · D2 9.3 · D3 7.4 · D4 7.3**; elite roster spread
**5.7 → 3.4** (Texas), low-major D1 (Cornell) **2.1**. Matches the owner's calls (avg-7 D3/D4,
natural floor, structure preserved).

---

## 3. Stage 2 — the pro tier (WIRED + TESTED)

### 3a. Exceeding 80 without touching anyone else
`GRADE_MAX = 80` stays the **normalization reference** (grade 80 == unit 1.0 == college
ceiling) so every normal player is byte-identical. A separate higher **hard clamp**
`player_attributes.GRADE_CEIL = 100` is the only thing lifted:
- `clamp_grade` / `Prospect.current_grade` clamp to `GRADE_CEIL`; normal **generation still
  clamps to `GRADE_MAX`**, so ordinary players never reach the headroom.
- `grade_to_unit` drops its `min(1.0)` cap → grade 80 = 1.0 (unchanged), a pro's 85 = 1.083,
  so pro drivers feed the engine **above 1.0** and win more; the engine already clamps the
  **resulting probability** (`_clamp01`) → "clearly better, not superpowered."
- Verified: pros beat a grade-74 blue-chip **130+/200**; the blue-chip is unchanged (OVR 78);
  `test_engine` green.

### 3b. Generation + cost (`app/pros.py`, `tests/test_pros.py` 6/6)
- **`generate_pros(salt, gender, cycle_key)`** — deterministic cohort of
  `worldconfig.pros_per_cycle()` players; every attribute drawn in **80–90** → **OVR 83–85 /
  STR 58–61**; international-heavy names; green **PRO** badge (`junior_badges`);
  `recruit_stars = 6`. **Regenerable on demand — a pro is never persisted until signed** (so an
  unsigned free agent's profile can still be scouted; see 3b-iii).
- **`pro_cost(pro, cohort)`** — STR-indexed across **18–30** (best pays 30, weakest 18). Pitched
  near the **33.5** elite cap so one pro eats most of a club's ONE budget — a blue-blood affords
  **one**, a major (9–16) **none** → pros **spread** instead of stacking, and still ≤ the cap so a
  pro a club *can* fund stays signable.
- **`assign_pros(cohort, programs)`** — budget-gated auto-placement (only an affording club signs,
  one per club, never overspends). **Retired from the live path** — the shipped model signs pros by
  hand (3b-iii); kept as a tested primitive.

### 3b-i. ONE budget — pros compete with the recruit class (non-obvious; read this)
A program has a **single** recruiting budget (scholarship-equivalency by conference tier).
There is **no separate pro fund** — a pro is paid **out of that same pool**, so signing pros
is a real tradeoff against the freshman class, and that tradeoff is *the reason the tier
exists*. Concretely:
- The `world_pro` ledger records each pro's cost per `(school, gender, year)`.
- `world._pro_spend(conn, world_id, year, gender)` sums a program's pro spend this year.
- **`_recruit_market`** (the annual recruiting budget every program reads) is
  `program_budget − pro_spend`. So a program that spent on a pro has *less* to attract recruits
  and can drop **below a caliber floor** — e.g. a 28-cost pro on a 33.5 budget leaves ~5, under the
  16.5 blue-chip floor → **no blue-chips that year**.
- **`_commit_pro_signings`** writes each signed pro's cost to `world_pro`, so a signing across
  either window (pre-season / fall) draws the one budget down for that year.
- Why it's not obvious: normal recruiting treats the budget as a *standing caliber floor*
  (it isn't "spent down" year to year — it's the program's persistent funding level, re-used
  each year to fill graduation's openings). Pros are the **one thing that actively draws that
  level down** within a year. So the budget is neither per-year-consumed nor lifetime-consumed
  for recruiting — but a **pro signing does consume it for that year**, which is exactly the
  constraint that makes chasing a pro cost you.

### 3b-ii. How the model evolved (two rejected drafts — context so the code reads right)
The pro tier went through two auto-signing drafts the owner rejected, both preserved in `git`
only as history:
1. **Budget auto-assign** (`assign_pros`, funnel-then-spread) → **clustered the whole cohort at
   ~4 blue-bloods** ("you mistakenly send them all to the same place").
2. **All-sign at portal-seed** (auto-inject, deepest-pocket fallback, a read-only "Pros entering
   via the portal" list) → still auto, and at the old **8.5–15** cost a club could **stack
   several** ("too cheap").

The shipped model (3b-iii) throws both out: pros are **free agents the user signs by hand**, and
the cost is **18–30**. `Pros` remains the conceptual **source pool** (nothing flows back into it),
but there is no auto-assignment and no separately browsable Pros roster page.

### 3b-iii. THE MODEL — pros are FREE AGENTS you sign by hand
Pros are **free agents you sign by hand, anywhere.**
- **Cost raised to `PRO_COST_LO/HI = 18–30`** (STR-indexed). Pitched near the **33.5** elite cap so
  one pro eats most of a club's ONE budget — a blue-blood affords **one** without gutting its
  class, a major (9–16) affords **none**. Pros **spread** by economics instead of stacking; still
  ≤ the cap so a pro a club *can* fund stays signable.
- **Pre-season = fully manual free agents.** The cohort is **not** auto-injected. It's a
  deterministic pool (`world.pro_cohort`, regenerated on demand — pros aren't persisted until
  signed) shown in the portal with a **blank, editable destination** per pro. You sign any pro to
  **any program, any division** (`sign_pro` → `overrides.pro_signing` intent; datalist =
  `pro_destinations` = every program). **Unsigned pros don't enter.** Signings persist onto the
  clubs only at **Commit** (`_commit_pro_signings`, idempotent per cycle; belt-and-suspenders on
  the wk-0 `advance_week`), which then feeds the shared-budget deduction (`_pro_spend`) exactly as
  before. Un-sign with the row's ✕ (back to free agent).
- **Both interactive windows are manual.** The **fall portal** gets the same free-agent section
  and `/fall-portal/pro-sign` route (cycle `<year>-fall`), persisted by `_commit_pro_signings` at
  fall commit. The **year-end `-transfer` auto-intake is REMOVED** — a pro is never auto-signed
  anywhere (`inject_pros`/`assign_pros` are now unused by the live path, kept only as a tested
  primitive). Pros enter through the **two gates the user actually reviews — pre-season + fall**;
  the next season's pre-season window is the year-end intake (same moment: rollover → wk-0 portal).
- **Scout a pro BEFORE signing.** An unsigned pro isn't on a roster, but the cohort is
  regenerable, so `world.find_pro` resolves it and the `/player` route renders a **preview** (green
  badge, real STR, full attribute bars, empty career, "Pro free agent" breadcrumb). The portal
  links every pro — signed or not — so you can open the profile to decide. Once committed onto a
  club the link points at its dest universe as usual.
- **Verified end-to-end (Flask client):** pre-season + fall cohorts each 36, all start unsigned and
  are distinct; cost renders 18–30; an **unsigned** pro's `/player` page returns **200** with badge
  + attributes; signing a man→Duke (D1) / woman→Emory (D4) / fall pro→UCLA shows them signed; Commit
  persists exactly those; committed profiles resolve 200; all three templates render.

### 3c. Live wiring (`app/world.py`)
- **`pro_cohort(seed, cycle_key)`** — the free-agent pool for a window: regenerate the
  deterministic cohort, attach STR + 18–30 cost + whichever club (if any) the user has signed each
  to (`overrides.pro_signing`). Blank dest = still a free agent. Feeds the portal `pros` sections.
- **`sign_pro` / `unsign_pro`** — store/clear a pro→club intent (any program, any division;
  `pro_destinations` = every program). **`find_pro`** resolves an unsigned pro from the cohort so
  its `/player` preview renders before it's on any roster.
- **`_commit_pro_signings(seed, cycle_key)`** — at commit, persist each signed pro into
  `world_roster` (displacing the club's weakest if full) + write its cost to the **`world_pro`**
  ledger. Idempotent per cycle; clears the roster caches. **Unsigned pros don't enter.**
- **Two interactive windows:** `<year>-preseason` (persist on pre-season commit + belt-and-
  suspenders on `advance_week` wk 0) and `<year>-fall` (persist on `commit_fall_portal`). The
  year-end `-transfer` auto-intake was **removed**; `inject_pros`/`assign_pros` are unused by the
  live path. **`list_pros`** reads the ledger for the post-commit (already-signed) display.
- **Portal-only:** pros are generated by `app.pros` and enter ONLY through the portal signings —
  never the HS recruit class / board.

### 3d. UI lever + badge
- **`worldconfig.pros_per_cycle()`** — default **18**, always **even** (men == women), **0
  disables the tier**. Sets how many free agents appear in the **pool** each window (you then sign
  whom you want). Set live from the **"Pros / cycle / gender"** input on `/preseason-portal`
  (route `/preseason-portal/pros`).
- **Green PRO badge:** `is_pro` Jinja filter + `.pro-badge` (green) in `app.css`; rendered on
  the roster (`my_program.html`) and the player page (`player.html`, via `info.is_pro`
  resolved from the persisted roster since pros aren't in the base index).

**Verified end-to-end (Flask client, primed world):** the pre-season + fall portals render 200
with the **"Pro free agents"** section; each window's cohort is 36 and **starts unsigned**; an
**unsigned** pro's `/player` preview returns **200** (badge + attribute bars); signing a man→Duke
(D1) / woman→Emory (D4) / fall pro→UCLA shows them signed; **Commit persists exactly the signed
ones** and their profiles resolve **200**; the 404 on cross-division movers is gone.

### 3d-ii. The portal player-profile 404 (both portals)
Clicking a portal mover 404'd: the pre-season + fall portal links called
`url_for('player', pid, school)` **without the universe** (`u=division-gender`), so the
`/player` route — which resolves a pid within ONE division×gender — fell back to the default
D1-men and missed any cross-division mover (a D4-women riser, a pro on a women's club). The
pids were always fine and unique; the link just pointed at the wrong universe. Fixed to pass
the universe where the player currently resolves — **source** roster pre-commit (pre-season
pre-commit / fall-portal hold), **dest** post-commit / for pros — matching every other
cross-division template. **Do not "fix" this by re-keying pids** (history/honors are keyed on
pid); the link is the bug.

### 3e. Pre-season portal first-load perf (shared `_FPPlanner`)
Wiring pros into the portal exposed a pre-existing slowness on first load (a cold
`rescan_preseason_portal` ran **~54s**). Fixed in the shared cascade engine, so it also
speeds the fall portal:
- **`best_in` / `fullest_below`** scanned *every* program in a division per rider tracking a
  max draw-weight → O(programs) per rider, quadratic in the slate. Now `by_div` is sorted once
  by weight (`prestige + 0.3·facilities`, desc, name tie-break) and both early-exit at the
  first program passing the open-slot / line / shed checks — the weight-desc + name order
  returns the *exact* program the old max-weight-first-encountered scan did.
- **`_sv`** re-normalized a player's attributes on every call (empty `player_str`); memoized
  per pid within the planner (a player's intrinsic STR is invariant under relocation).
- **Verified byte-identical** resolved slate vs before (200 moves/gender, both). Cold rescan
  **54s → ~7s**; warm seed **1.7s**, view **1.5s** (were 48s / 5s).

---

## 4. Files touched
- `app/player_attributes.py` — `GRADE_CEIL`, `clamp_grade`, `grade_to_unit`.
- `app/development.py` — import `GRADE_CEIL`, `current_grade` clamp.
- `app/recruit_economy.py` — `TIERS` grades, `_D1_TIER_BANDS["top"]` 33.5.
- `app/ncaa.py` — `_TALENT` bases/spreads (Stage 1).
- `app/pros.py` — **new**: generation, **cost 18–30** (STR-indexed), **budget-gated spread**
  assignment (fall/transfer), `is_pro`.
- `app/overrides.py` — **`pro_signing`** table + `pro_set_sign`/`pro_unsign`/`pro_get_signs`/
  `pro_clear_year` (free-agent signing intents); cleared on reset.
- `app/world.py` — `world_pro` schema + reset, **`pro_cohort`/`sign_pro`/`unsign_pro`/
  `find_pro`/`_commit_pro_signings`/`pro_destinations`** (free-agent pros, both windows),
  `_commit_pro_signings` wired into pre-season commit + wk-0 advance + fall commit; year-end
  `-transfer` inject removed; `list_pros`; portal `_FPPlanner` perf (`best_in`/`fullest_below`
  early-exit, `_sv` memoization). `inject_pros`/`assign_pros` now unused by the live path.
- `app/worldconfig.py` — `pros_per_cycle` / `set_pros_per_cycle` (even).
- `app/web/server.py` — `is_pro` filter, `/preseason-portal/pros` (lever), `/preseason-portal/
  pro-sign` + `/fall-portal/pro-sign` (sign/unsign) routes, **player route renders an unsigned-pro
  preview via `find_pro`**.
- `app/web/state.py` — free-agent `pros` section in `preseason_portal_view` AND `fall_portal_view`
  (`pro_cohort` pre-commit, `list_pros` post-commit).
- `templates/{preseason_portal,fall_portal}.html` — per-pro "Sign with — any program" control +
  scout link; `templates/player.html` — free-agent preview (badge, breadcrumb, empty career).
- `app/web/static/css/app.css`, `templates/{my_program,player}.html` — green PRO badge.
- `templates/recruit_economy.html` — Scholarship Economy page updated to the free-agent pro model.
- `templates/{preseason_portal,fall_portal}.html` — player-profile links now pass the universe
  (`u=`) so cross-division movers resolve instead of 404.
- `tests/test_pros.py` — **new** (6 tests).

## 5. Open items
- **Engine-validation gate (not yet run):** 1,000 near-equal duals (68v69 / 71v72 / 77v77) —
  confirm the compressed band still separates the good from the rest via scores.
- **Re-baseline the old calibration tests:** `test_roster`, `test_development`, and the other
  UTR-band assertions expect the *pre*-compression numbers and will fail until updated to the
  new bands. The full suite was deliberately not run while numbers settle.
- **In-game eyeball:** watch the pro count across the 3 cycles (18/gender × 3 ≈ 54/gender/yr
  entering) and dial the lever if it reads high; confirm the compressed talent feels right.
