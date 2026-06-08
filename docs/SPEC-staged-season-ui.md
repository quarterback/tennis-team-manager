# Spec — Staged Season UI (for the season-mode unification agent)

Context for whoever is doing the season-mode unification + staged UI. This is
what the user means by "stages of jobs that the UI can even show and be pushed
to happen," and how it must hook into the awards system that already exists on
the `claude/awards-scheme` branch.

## The idea

The season is not one "Advance" button that silently does everything. It is an
explicit, visible **pipeline of stages**, and the user *pushes* through them one
at a time. The World hub shows the current stage and a single primary action to
run it; running it advances to the next stage.

Stage order (one season-year):

1. **Regular season** — advance week by week (the existing weekly sim).
2. **Conference tournaments** — postseason bracket per conference.
3. **NCAA championship** — the national bracket.
4. **Awards phase** ← *runs before rollover, while the finished rosters are
   still intact.* Pushing it stamps the season's honors.
5. **Offseason / rollover** — graduate → **coach carousel** → transfer portal →
   recruiting intake → walk-ons, then the year advances to the next preseason.

Stages 1–3 already exist inside `app/seasonmode.py` (`phase`:
`regular` → `conf_tournaments` → `ncaa` → `complete`). Stages 4 and 5 are the
new explicit steps to surface. The key change is **splitting today's
all-in-one advance into two distinct, user-pushed steps once the season is
complete**: first *Run Awards*, then *Start Next Season*.

## What already exists on `claude/awards-scheme` (don't rebuild — call these)

- `world.season_complete(seed) -> bool` — every universe has finished its
  postseason; the season is ready for the awards phase + rollover.
- `awards.stamp_world_honors(seed) -> int` — **the awards-phase action.**
  Computes + persists the year's honors (players + coaches) into the `honors`
  table. Idempotent. Already exposed as `POST /world/awards`.
- `honors.has_season(year, division, gender) -> bool` — use this as the "awards
  already run for this year?" flag to drive the stage state.
- `world.advance_week(seed)` — advances a week, OR finalizes the year (rollover)
  when `season_complete`. Rollover now includes the **coach carousel** (coaches
  move before the portal) and returns `coach_moves` / `coach_followers` in its
  summary.

Current wiring (in `world_advance` route): when `season_complete()`, it stamps
honors and then advances in ONE click. **For the staged UI, split that:**

## Required behaviour change

Replace the single advance-when-complete with two pushable stages:

- If `not season_complete()` → primary action = **"Advance week"**
  (`world.advance_week`).
- If `season_complete()` and **not** `honors.has_season(curr_year, …)` for the
  universes → primary action = **"🏅 Run Awards"** (`POST /world/awards` →
  `stamp_world_honors`). Do **not** roll the year yet.
- If `season_complete()` and honors are stamped → primary action =
  **"Begin Season N+1"** (`world.advance_week`, which performs the rollover).
  After rollover, surface the offseason summary (graduated, coach moves +
  followers, portal movers, signings).

So the user sees: … → *Season complete* → **Run Awards** (awards lock in, Awards
page + player/coach cards update) → **Begin Next Season** (rollover happens, new
preseason). The awards genuinely happen *before* and separately from the
rollover, which is the whole point ("the awards phase can come before the true
end of season mode, then the season can be pushed to proceed").

## UI suggestions (World hub)

- A horizontal **stage stepper** showing the five stages with the current one
  highlighted and completed ones checked.
- One prominent primary button whose label/action is whichever stage is next
  (per the logic above).
- After Run Awards: a "Season N awards" recap (POTY, champions, COTY) linking to
  `/awards`. After rollover: an offseason recap.

## Interaction with the season-mode unification

Once the baseline (`run_season`/`get_season`) is retired in favour of season
mode, the awards computation (`app/web/awards.py: honor_records` /
`coach_honor_records`) must read its inputs (player STR + records, conference
champions, national champion, per-team rosters, head coaches) from season mode
instead of `get_season`/`get_bracket`. The *shape* it returns and the honors
schema do not change — only the data source. Keep `stamp_world_honors`,
`honors.*`, `coachreg.*`, and the player/coach career-honors readers intact;
just repoint the computation.

The awards branch and the unification branch will overlap in
`app/web/awards.py` and the World hub template — coordinate the merge there.
Everything else (career honors store, coach registry, coach pages, carousel) is
additive and independent.
