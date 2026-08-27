# AAR — JHSAA injuries: the college dice, ported to a one-shot season sim

**Date:** 2026-08-27
**Scope:** `app/jhsaa.py` (`TeamSeason.injuries`/`injury_log`, `_healthy`,
`_injury_tick_and_roll`, expanded `_rest_count`), `app/world.py`
(`world_jhsaa_injury` table + `jhsaa_school_injuries` reader, `run_jhsaa`
insert), `app/web/state.py` (`jhsaa_player_view`), `app/web/templates/
jhsaa_player.html`. JV is explicitly untouched.

## The ask

> "How difficult would it be to integrate a semblance of the injury model from
> the college game into the high school game? … it would be worthwhile for
> getting those benched kids into matches and also for randomness… Resting
> staff as we do it now still works, I think I'd probably expand it past the
> #2 players though and go to maybe 4 or even 6 using the same criteria…
> Fatigue unnecessary if we have injuries. JV ignores injuries or else a team
> could run out of players, the whole point is to get more kids into matches."

Three follow-on asks for visibility: a player-page tab bar (mirroring the team
page's Team trophies / Player honours / Individual State Champions bar) split
into **Player honours**, **Individual State results** (relocated from a
standalone details panel — same data, tidier place), and a new **Injury log**.

## Why this was cheap

`app/injuries.py` was already built as ONE shared implementation split into
dice (pure, reusable) and a SQL-backed store (college/pro specific, per-save
persistence). The JHSAA needed only the dice — `injuries.roll_injury`,
`injuries.durability`, `injuries.is_enabled()` — because a JHSAA season is not
a per-request, resumable save: it runs to completion in ONE in-memory call
(`jhsaa.run_season`, inside `world.run_jhsaa`) and only the OUTPUT is
archived. There is no save/reload boundary mid-season to persist across, so
"the store" collapses to two plain fields on `TeamSeason` (the same pattern
`records`/`matches` already use), not a SQLite table with its own connection
per dual.

This also means injuries roll on real entropy exactly ONCE per world-advance
(inside that single `run_season` call), same as everything else non-
deterministic in a JHSAA season — the archived schedule/records are read back
on every later page view, never re-simulated. No new non-determinism trap.

## Design

### Where the pieces live
- **Dice** — reused verbatim from `injuries.py`: `roll_injury(prospect,
  exposure_scale)`. Respects `injuries.is_enabled()`, so the suite's autouse
  `_injuries_off` fixture (in `tests/conftest.py`) disables JHSAA injuries too,
  for free — no new test fixture needed.
- **State** — `TeamSeason.injuries: dict[pid, int]` (duals remaining out; the
  sentinel `injuries.SEASON_ENDING` (-1) marks a season-ender and never ticks).
  A healthy player has NO key — recovery deletes the row rather than storing 0,
  so `pid in ts.injuries` is the whole availability check.
- **Substitution, not re-rank** — `_healthy(ts, order)` filters a priority list
  (never `_order` itself) at dress time only. Called from `_lineup`'s regular
  and showcase branches, and from `_postseason_nine`, which filters the FROZEN
  Order of Ability after slicing pids from it — an injured player in the
  postseason just steps aside for the next name on the same frozen list, so
  the anti-stacking rule (§ owner rule 2027-08) is untouched.
- **Rolling** — `_injury_tick_and_roll(ts, dressed, dual_index)`, called from
  `play_dual` (varsity only) right before `return res`, after the schedule
  rows are appended so `len(ts.schedule)` is this dual's own ordinal. Ticks
  existing injuries down first, then rolls fresh ones on exactly the players
  who dressed (`la`/`lb`), scaled by `EXPOSURE_BASELINE / len(dressed)` same as
  the college model — a JHSAA 3S/4D dual dresses 11, so each roll scales to
  ~0.55× the college per-player rate, keeping the TEAM's injury volume at the
  original calibration regardless of card size.
- **Archive** — a new table, `world_jhsaa_injury`, one row per injury actually
  rolled: `(world_id, year, gender, school, pid, name, dual_index, duals_out,
  season_ending)`. Modeled directly on `world_jhsaa_individual` (own table,
  same reasoning: per-player event data that has no home on the per-dual
  `world_jhsaa_dual` row and would bloat the `world_jhsaa` summary blob if
  folded in there). `dual_index` is the injured player's own team's dual count
  when it happened — an ordinal within their season, not a calendar week (the
  JHSAA has no clock inside a season — see `world.jhsaa_match_dates`).

### JV stays untouched, by construction
`jv_pool(ts)` reads `_order(ts)` directly and was never routed through
`_healthy` — an injured varsity player is still JV-eligible, and
`_injury_tick_and_roll` is called only from `play_dual` (varsity), never
`play_jv_dual`. Verified: with a team's top two starters marked injured,
`jv_pool` returns the identical set it would with nobody hurt.

### Rest staffing, expanded past 1-2
`_rest_count`'s qualifying gate (`REST_GAP`, `REST_MIN_SAMPLE`, `REST_OPP_PCT`,
`REST_RATE`) is UNCHANGED — same criteria, same trigger. What changed is how
many starters sit once it fires: instead of a hard `k = 2 if … else 1`, `k`
now grows one seat at a time (`REST_TWO` for the 2nd, `REST_FALLOFF` for each
seat beyond), capped at `REST_MAX` (6) and never past the healthy bench
(`_healthy` already ran, so `spare` is healthy-only). Measured over 2,500
qualifying-gate draws: k=0 in ~40% (REST_RATE didn't fire), k=1 ~47%, k=2
~13%, tapering to k=6 in ~1%. Composes with injuries for free — both
mechanisms pull from the top of the SAME already-injury-filtered order, so a
dual can rest starters AND be missing an injured one without double-counting.

One existing test hardcoded the old 1-2 range
(`test_lineup_rests_from_the_top_and_keeps_ladder_order`, `tests/
test_jhsaa_rest.py`) and was updated to `1 <= k <= jhsaa.REST_MAX` — the old
assertion was pinned to a number the owner explicitly asked to change, not an
invariant.

### Fatigue: not built, not missing
There was nothing to port — the college game has no fatigue system either.
Confirmed before writing this up rather than assumed.

## Player-page visibility

Three tabs (`jh_tabs`, the SAME macro `jhsaa_school.html` uses for its own
Team trophies / Player honours / Individual State Champions split), always
rendered rather than gated on any one pane having content — a career can have
honours and no state trip, or a state trip and no injuries:
- **Player honours** — one row per season per honour string, off the same
  `s.honors` list the ledger's Honours column already carries; just given its
  own text-listing pane so the data is legible without hovering a chip (the
  header chips and the ledger's inline column are both untouched).
- **Individual State** — the existing tiered-results markup, moved verbatim
  from a standalone `<details>` panel into a tab pane.
- **Injury log** — new. Season + duration only (`Out N duals` / `Season-ending
  injury`), per the owner's "that's all the detail we'd need." `dual_index`
  is archived but deliberately not surfaced — it's an internal ordinal, not a
  calendar week, and showing it would imply a precision the season doesn't
  have.

## What was deliberately NOT built
- No date/calendar translation for injury duration — shown in duals (the
  engine's native unit here and in the college docs), not real weeks.
- No mid-match retirements (`RETIREMENT_RATE`) — a separate, fidelity-gated
  system college-side; out of scope for this pass.
- No medical-redshirt equivalent — JHSAA eligibility is a fixed four years
  with no redshirt concept, so a season-ending injury just ends the season.

## Verification
No pytest run this session (interactive constraint) — verified with direct
Python calls: a 12-team district season played to completion with injuries
rolling/ticking/logging correctly (9 injuries logged across an 18-dual
season, matching the ~0.15/dual per-team calibration target); the k
distribution for expanded rest matches the intended taper; `_healthy`
preserves relative order and excludes only hurt pids; `jv_pool` is provably
unaffected by injury state. `app.jhsaa`, `app.world`, `app.web.state`, and
`app.web.server` all import clean. The one test file with a hardcoded old
range (`tests/test_jhsaa_rest.py`) was updated in place. Recommend a full
`python3 -m pytest -q` pass before merge — not run here per the user's
direction mid-session.
