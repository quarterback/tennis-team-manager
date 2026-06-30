# PLAN — Tennis World Cup (international national-team competition)

> Status: **future / not scheduled.** Saved for later revisiting. A feasibility +
> logistics plan, not a build order. Owner's intent: build the minimal single-sex
> cups first to de-risk, then grow into the full "Tennis World Cup" structure.

## Context

A national-team competition where the existing college player universe is regrouped
**by country** into national squads that play **ties** (singles + doubles rubbers) in a
knockout. Two **single-sex** events: a **Davis Cup** (men) and a **Billie Jean King Cup**
(women), run separately — **not** a mixed-gender (Hopman) event for now. The umbrella
goal is a first-class **Tennis World Cup**: a 32-nation finals fed by regional qualifying,
with national teams that exist as persistent entities (records / history / awards), an
**editor to set national rosters**, and results that thread onto the **same players'**
career pages under an **International** tab (beside College and the existing Pro layer).

## Feasibility verdict: HIGH — ~90% glue over existing systems

Every hard part already exists and is reusable:

| Need | Already exists | Where |
|---|---|---|
| Singles rubber | `engine.simulate_match(p0, p1, seed, fmt)` | `engine/match.py` |
| Doubles rubber | `engine.simulate_doubles(t0, t1, seed, fmt)` | `engine/doubles.py` |
| A team **tie** (college 3D+6S, clinch at 4) | `engine.simulate_dual(Team, Team, seed)` | `engine/dual.py` |
| A **mixed** tie (3 MS + 3 WS + 3 XD, first to 5) | `engine.simulate_gtt_dual(GTTTeam, …)` | `engine/gtt.py` — a ready Hopman tie if ever wanted |
| Best-of-5 / match-tiebreak formats | `engine.format.PRESETS["grand_slam"]`, `"best_of_3_mtb"` | `engine/format.py` |
| Seeded single-elim knockout (byes, upsets) | `engine.run_tournament(entrants, seed, play, key, seeds)` | `engine/tournament.py` |
| "Assemble top players → seed → play a draw → Championship" | **`app/individuals.py`** (singles/doubles champs) | the perfect template to copy |
| Prospect → playable engine player | `Prospect.engine_player()` | `app/development.py` |
| Every player in the world, dev-applied | `world.developed_rosters(world)` → `{(div,gender):{school:[Prospect]}}` | `app/world.py` |
| Nationality on a player | `Prospect.country` (ISO2), `.secondary_country` (PR/VI/GU dual) | `app/development.py` |
| Ranking signal within a country | `current_overall()` (20–80), `str_value()` | `app/development.py` |
| Country name / flag | `country_name()`, `flag_emoji()`, `country_abbrev()` | `generators/flavor.py` |
| Derived seed-deterministic event + snapshot-for-history + web caching | `app/individuals.py` + `app/web/state.py` (`get_singles_championship`, `championship_to_dict`) | reuse wholesale |
| Per-player **career page** + timeline | `state.player_career`, `player_career_table`, `player_journey` | add an "International" facet |
| Generic per-player **career/honors store** (keyed by subject id) | `app/honors.py::career(subject_id, "player")` | record caps/titles here |
| A **"pro" career layer** already exists | `app/gtt_seasonmode.py` (`player_detail`, `_career_record`) | the unified College/Pro/International tab assembles three facets |

**Net new code:** (a) group players by country instead of by program; (b) one "play a tie"
callback; (c) key results to the existing **pid** so they land on each player's career page.
All small. The fuller World Cup (persistent national entities + qualifying + roster editor)
is a bigger but well-patterned layer on top.

## Pool-depth reality (the one viability constraint)

At default `intl_share` 0.30: ~750 international players/gender, bottom-heavy. Top ~20
nations (US, ES, FR, IT, DE, GB, CA, AU, CZ, AR, BR, JP, …) have ample depth (15–20/gender);
the long tail has 2–10.

- A **16-nation** field with **4-player squads** is comfortable; **32** is feasible, better
  if `intl_share` is raised (trivial now with the new direct-weights editor).
- **Levers:** keep squads small (a tie needs ~4 players), **auto-size** the field to nations
  clearing a depth floor, and **cap** each nation's squad to its true top-N (US shouldn't be
  lopsided). Regional qualifying naturally lets thinner regions still send a representative.

## Minimal V1 design (single-sex derived cups — build first)

1. **Events:** Davis Cup (men) + BJK Cup (women), separate single-gender knockouts.
2. **Squad assembly:** new `app/national_teams.py` — walk `developed_rosters`, group by
   `country` (territories via `secondary_country` may field their own PR/VI/GU teams), take
   **top 4 by `current_overall`** per nation per gender. Mirrors `individuals.select_singles_field`.
3. **Tie format:** `play_tie()` = **4 singles + 1 doubles, first to 3**, from `simulate_match`
   + `simulate_doubles` (~40 lines, modeled on `engine/dual.py`), `best_of_3_mtb` with a
   best-of-5 `grand_slam` toggle. (Shortcut: reuse `simulate_dual`, but it needs 6 singles.)
4. **Knockout:** `run_world_cup(gender, seed, field=16)` → `engine.run_tournament(nations,
   seed, play=play_tie, key=squad_strength)`. Reuse `individuals.Championship` / `_assemble` /
   `championship_to_dict` for the result + JSON snapshot.
5. **Calendar:** derived offseason "international window," computed after the NCAA championship
   completes (like `individuals.py`); seed-deterministic; **no new season phase for V1**.
6. **Persistence — same players:** every rubber carries the player's existing **`pid`**.
   Snapshot finished cups to a `world_cups` table; write a per-player `world_cup_results`
   index (`pid → [tie/rubber rows]`) + titles/caps to `honors.career`, so a player builds an
   international record across a whole career.
7. **Career-page "International" tab:** extend `state.player_journey` / `player_career_table`
   with an International facet from (6) — caps, ties, singles/doubles W-L, titles, flag —
   beside the **College** results and the `gtt_seasonmode` **Pro** results. One pid threads all.

## Full vision — "Tennis World Cup" (expanded scope)

- **32-nation finals fed by REGIONAL QUALIFYING:** continental/regional qualifying events
  (modeled on the ITA events but bigger); qualifiers advance to the 32-team World Cup. Per
  gender, still single-sex.
- **National teams as persistent ENTITIES** with their own **records / history / awards** that
  persist across seasons — exactly like college programs (all-time W-L, titles, qualifying
  runs, head-to-head, an honors ledger). A stored national identity, not a per-year bracket.
- **Editable national rosters:** an editor to set/override who represents each country — a
  national-team analogue of the roster/ratings editor.

This graduates from a derived computation to a **stored competition structure** (a `nations`
entity + qualifying/finals brackets persisted like seasons, with their own records/honors
tables) — larger than V1 but on the same engine + bracket primitives.

## Phases

1. **Core (1 module, ~200 lines):** `app/national_teams.py` — `national_squads()`, `play_tie()`,
   `run_world_cup()`. Pure engine logic; deterministic. Bulk of the value, small.
2. **Event web page:** `/world-cups` bracket + `state.py` caching (copy `get_singles_championship`);
   flags via `flag_emoji`; reuse championship template/CSS.
3. **Persistence + career integration:** `world_cups` snapshot table; per-player `world_cup_results`
   index + `honors.career` caps/titles; **International tab** on the player career page.
4. **Tennis World Cup structure:** 32-nation finals + regional qualifying; persistent national-team
   entities with records/history/awards (a `nations` table + a national honors ledger); the
   **country-roster editor**.
5. **Polish / optional:** mixed Hopman via `simulate_gtt_dual`; best-of-5 toggle; per-tie box
   scores; host-nation `MatchContext`; promote to a real offseason `seasonmode` phase if it
   should sit on the season clock.

## Effort & risk

- **Effort:** Phase 1 is a few hours (mirrors `individuals.py`); Phases 2–3 are standard
  snapshot/web work. Phase 4 (persistent national entities + qualifying + editor) is the real
  build but reuses the bracket/season/editor patterns.
- **Risks:** long-tail depth (→ 16-team start, small squads, auto-size, raise `intl_share`);
  determinism across rollovers (→ follow the `individuals.py` snapshot pattern); thematic fit
  (college players as national teams — a deliberate what-if); dual-national eligibility
  (PR/VI/GU/Canada) (→ documented rule: primary `country`, territories optional).
- **No engine changes required** — formats, doubles, mixed, and the knockout framework are all
  already in `engine/`.

## Verification (when built)

- Unit: `national_squads()` groups by country, ≤N per nation; `play_tie()` deterministic
  (same seed → same result); `run_world_cup()` yields a champion over a 16/32-nation field.
- Depth probe: a script over `developed_rosters` counting nations with ≥4 players/gender at the
  current `intl_share` (≥16 confirmed; compare 0.30 vs 0.50).
- Determinism: same (seed, year) reproduces the full bracket; snapshot round-trips through
  `championship_to_dict`.
- Identity/career: every rubber's `pid` matches the player's college pid; the per-player index
  aggregates a multi-year record; the **International tab** renders beside College/Pro.
- Web smoke: `/world-cups` and a populated player career page render via the Flask test client.
