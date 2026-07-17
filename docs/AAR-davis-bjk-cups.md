# AAR — Davis Cup / Billie Jean King Cup (national-team cups, V1)

**Date:** 2027-07-17
**Scope:** `app/national_teams.py` (new), `world._store_world_cups` /
`latest_world_cup` / `world_cup_years` / `player_world_cups` + `world_cups`
table + `_finalize_year` hook, `honors.stamp(conn=)`, `state.get_world_cup`,
`/world-cups` route + `world_cups.html`, International panel on `player.html`.
Implements V1 of `docs/PLAN-tennis-world-cup.md` (owner scope: core + web +
career tab; auto-sized field).

## What it is

The college player universe regrouped BY COUNTRY into national squads playing
knockout ties — the **Davis Cup** (men) and **BJK Cup** (women), run separately
each off-season. A derived, seed-deterministic computation over the live
rosters, snapshotted at the year rollover exactly like the individual
championships. ~90% glue: `run_tournament` for the draw, `simulate_match` /
`simulate_doubles` for every rubber.

## Owner's choices (locked)

- **Field is AUTO-SIZED by depth:** every nation with ≥ `DEPTH_FLOOR` (4)
  players enters; trimmed to the largest power of two ≤ `FIELD_CAP` (32) by
  squad strength. Measured on the real world: 82 nations (men) / 75 (women)
  clear the floor → 32-nation finals, 8 seeded.
- **Squads pool ALL divisions** — top 4 by current ability; a D2/D3 star makes
  a thin nation's team (verified: the US women's squad drew D2 + D3 players).
- **Tie format:** 4 singles in rank order, then the doubles (each side's top-2
  pair), first to 3 rubbers; dead rubbers are not played. Rubbers score like
  the NCAA individual events (best-of-3, no-ad, 10-pt match TB decider).
- **Territories don't field separate teams in V1** — players group under their
  primary `country` only.
- **Timing:** an off-season event. Live-computed (memoized) once the world's
  active seasons are complete; stored to `world_cups` at `_finalize_year` over
  the fully-developed rosters BEFORE graduation, so seniors play their cup.

## Career integration — one pid threads all

- **Honors:** champion squad → "`{event}` Champion" (sort 95), runner-up →
  Finalist (70), stamped via `app.honors` under division `INTL` to the players'
  REAL pids — so titles surface automatically on the college card, the GTT pro
  card, and the Hall of Fame, beside their college/pro honors.
- **International panel** (college player card): per-edition caps, singles/
  doubles rubber W-L, and the squad's finish, from the snapshot's per-player
  index (`world.player_world_cups`).

## Hard-won detail: stamp through the caller's connection

`_store_world_cups` runs inside the rollover's open write transaction on the
shared SQLite file. `honors.stamp` used to open a SECOND connection → "database
is locked" → the per-gender `try/except` swallowed it → cups stored fine but
NO honors stamped (exactly the failure the GTT graduate-pipeline AAR warns
about). `honors.stamp` now accepts `conn=` and the rollover passes its own.
When adding any new rollover-time writer, route it through the caller's
connection — never open a sibling connection mid-transaction.

## Verification

- Determinism: same (gender, seed, rosters) → byte-identical snapshot.
- Depth floor excludes thin nations; `auto_field`: 40→32, 20→16, 9→8.
- Ties clinch at 3 (S1–S4 then D1 only if needed); caps/rubber records
  accumulate per pid; degenerate one-nation fields return safely.
- Full pipeline on real rosters: store → `latest_world_cup` round-trip →
  `player_world_cups` row → "Davis Cup Champion" in `honors.career(pid)`.

## Future (per the plan, not in V1)

Regional qualifying feeding a fixed 32; persistent national-team entities with
records/history; the national-roster editor; mixed (Hopman) via
`simulate_gtt_dual`; host-nation `MatchContext`.
