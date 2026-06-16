# Assignment — Wire the pro league (GTT) to college graduates

## Objective
Connect the **college world** to the **pro league (GTT / "Global Team Tennis")**
so that each year's **graduating seniors flow into the pro league** instead of it
running on generated regens, and so a GTT league **persists season-to-season tied
to the active world**. A player's identity, college history, and honors must
carry through college → pro (one continuous career).

## Selection rule (from the product owner)
Each pro off-season, the league signs the **best N graduating players** league-
wide, **with some slack so there's a free-agent pool** (sign a few more than the
open roster spots).
- **~95%** of the intake comes from **D1** graduates.
- **~5%** is reserved for **non-D1 (D2/D3)** graduates whose **OVR/STR** clears a
  "can compete at the pro level" bar (a genuinely good small-school player can
  break in).
Pick `N`, the slack amount, and the non-D1 OVR/STR bar as tunable constants.

## How it works today (read these first)
Single shared SQLite file holds **both** the world tables and the GTT tables;
GTT helpers that read world tables must use the **caller's open connection**
(opening a second connection mid-transaction deadlocks — see the note in
`_world_graduates`).

**College world — `app/world.py`:**
- `world_roster(world_id, year, division, gender, school, pid, data)` — one row
  per rostered player per year; `data` is the Prospect JSON (`class_year`,
  `history`, etc.). A player's division/gender is on the row.
- `graduate(rosters)` — at year rollover, **drops `class_year == "Sr"` players**
  (they currently just vanish) and bumps everyone else up a class.
- `_finalize_year(seed, w)` — the rollover: prime → snapshot history +
  championships → `graduate` → transfer portal → intake recruits → save next
  year. **This is where the graduating cohort exists and is discarded.**
- `world._active_unis()` / `worldconfig.is_active(div, gender)` — the active
  universes (e.g. a women-only save).
- Prospect signals: `p.str_value()` (results STR), `p.current_overall()` (OVR).

**Pro league — `app/gtt_seasonmode.py`:**
- `gtt_leagues(id, name, world_seed, current_year, …)`, `gtt_players(league_id,
  pid, gender, fid, status, age, seasons, joined_year, origin, data)`,
  `gtt_franchises`, `gtt_seasons`, `gtt_duals`, `gtt_hof`.
- `create_league(name, *, seed=2026, n_teams)` — seeds **founder** players
  (generated; correct for the inaugural league since founders "never went to
  college").
- `_world_graduates(conn, world_seed, exclude_pids, limit)` — **already pulls
  this year's college seniors by STR**, but reads `world_roster[MAX(year)]`,
  which are the *currently enrolled* seniors, **not the cohort that just
  graduated** — a timing bug.
- `_intake(conn, league, needed_by_gender)` — fills the off-season free-agent
  pool: real grads first (`_world_graduates`), topped up with generated rookies.
  Called **only at GTT season rollover** (the off-season advance, ~line 719),
  **not** at league creation. No D1/non-D1 split.
- Players persist in `gtt_players` across seasons; honors follow the pid
  (college → pro) per the module docstring and `app/honors.py`.

## The gap
1. **Timing/source:** `graduate()` discards seniors with no durable record, and
   `_world_graduates` reads still-enrolled seniors from the latest roster — so
   the pro intake never reliably gets the *actual* graduating class.
2. **Linkage:** a GTT league's `world_seed` must equal the **active world's
   seed** or `_world_graduates` finds no world → falls back to all rookies
   (regens). Confirm/repair this in `create_league` and the GTT hub.
3. **Selection rule** (95% D1 / 5% non-D1-above-bar, best N + slack) isn't
   implemented — `_world_graduates` just takes the top seniors by STR.

## Recommended implementation
1. **Emit the graduating cohort at finalize.** In `world._finalize_year` (before
   `graduate()` drops them), persist the season's seniors to a new
   `world_graduates(world_id, year, division, gender, pid, str, ovr, data)`
   table. This is the authoritative, correctly-timed source (the class of college
   year Y), and it survives the rollover.
2. **Rewrite the pro selector** (replace/extend `_world_graduates`) to read
   `world_graduates` for the relevant year(s) and apply the rule:
   - Rank D1 grads by STR; take ~95% of the intake target from them.
   - Rank non-D1 grads by OVR/STR; from those above the competitiveness bar,
     take ~5%.
   - Add free-agent slack (a few beyond open roster spots) so a free-agent pool
     exists. Exclude pids already in the league.
3. **Tie the league to the world.** Ensure `create_league` uses the active
   world's seed, and the GTT hub creates/loads the league against the current
   world (so the pipeline always finds it). Founders remain only as the
   inaugural backfill; real grads should dominate intake from year 2 on.
4. **Persistence & continuity.** `gtt_players` already persists; verify intake
   runs every pro off-season, players age/retire, and a graduate keeps their
   **college pid → continuous college+pro career and honors** on the player page.

## Constraints & conventions
- **Determinism:** all generation is seed/salt-keyed (`_h(...)`, `make_pid`,
  `random.Random(seed)`). Keep new selection/intake deterministic per
  (world seed, league id, year). Never use bare `hash()`.
- **Shared DB / no deadlocks:** read world tables through the caller's
  connection inside GTT transactions.
- **Active universes:** only pull graduates from active universes
  (`world._active_unis()`), so a women-only save feeds a women pro league.
- **Tests:** add coverage under `tests/` (mirror `tests/test_world*.py`); the
  suite is heavy, so a focused test that sims a short world + one GTT off-season
  and asserts the 95/5 mix + persistence is ideal. Determinism tests must stay
  green.
- **Write an AAR** in `docs/AAR-*.md` (match the existing format) describing the
  pipeline, the timing fix, the selection rule, and verification.

## Acceptance criteria
- Sim a college world ≥2 years, create/advance a GTT league against that world:
  the pro intake is **~95% ex-D1 / ~5% ex-D2-D3 (above the bar)**, best-first by
  STR/OVR, with a free-agent pool beyond roster need.
- Players **persist season-to-season** in the pro league (age/retire), not
  regenerated.
- A graduate's player page shows **one continuous career** (college seasons +
  pro seasons) and carries college honors.
- World + single-gender determinism tests pass.

## Open decisions for the implementer
- `N` (intake target = league size × roster spots opening), slack size, and the
  non-D1 OVR/STR bar.
- Retirement/aging curve and whether founders phase out as grads fill in.
- Whether to backfill from *multiple* prior graduating classes for an inaugural
  pro league, or only the latest.
