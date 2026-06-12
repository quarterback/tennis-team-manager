# AAR — ATP/WTA-style Data Portal

## Segment summary

This segment added the first dedicated **tennis data portal** for Play to Clinch:
a standalone `/data` surface meant to feel closer to the ATP/WTA site pattern
than a buried sim-management page. The user called out that other sims such as
Viperball and Superinnings have separate data portals wired to consume sim data
while operating independently; tennis only had dense single-purpose pages
(Rankings, Season, Standings, Juniors, Recruiting) with valuable data scattered
across them.

What landed:

- **New World navigation entry and route.** `Data Portal` now appears in the
  World nav group and maps to `/data`, preserving the selected universe via the
  existing `u` query param. The active-nav resolver treats `/data` as its own
  World section instead of overloading Rankings or Dashboard.
- **Portal aggregation layer.** `data_portal_view()` was added in
  `app/web/state.py` to collect live sim slices into one page: Power Index rows,
  ranking movement, STR player leaders, conference race leaders, latest scores,
  current-week fixtures, and top junior/recruiting watchlist entries.
- **ATP/WTA-inspired page shell.** `app/web/templates/data_portal.html` adds a
  tour-style hero, pill navigation for Rankings / Scores / Race / Juniors / JSON,
  KPI cards, a horizontal latest-results score strip, a rankings table, a player
  leaders panel, race leaders, fixtures, and junior watchlist cards.
- **Shared portal styling.** `app/web/static/css/almanac.css` now includes the
  portal-specific hero, score-strip, grid, movement, player-row, fixture, and
  responsive rules. This deliberately lives in the shared almanac stylesheet
  rather than a page-local `<style>` so future data portal pages can reuse it.
- **Smoke coverage.** `tests/test_web_season.py` now asserts that
  `/data?u=D1-men` renders successfully during the existing season web flow.

## Files changed and where to look

- `app/web/server.py`
  - `NAV_GROUPS`: adds `Data Portal` to the World group.
  - `_active_nav()`: maps `/data` to the `data` nav id.
  - `data_portal()` route: resolves the selected universe and renders
    `data_portal.html` with `data_portal_view()`.
- `app/web/state.py`
  - `data_portal_view()`: the wiring contract for the page. This is the place to
    add or reshape portal data before touching the template.
- `app/web/templates/data_portal.html`
  - Page composition and links into the deeper data surfaces.
  - The template intentionally links out rather than duplicating every dense
    table: Rankings, Season, Standings, Junior Rankings, and JSON feed remain the
    source-of-truth detail pages.
- `app/web/static/css/almanac.css`
  - `.al-hero`, `.al-score-*`, `.al-portal-grid`, `.al-player-row`, `.al-fixture`,
    and mobile rules are the new portal design system pieces.
- `tests/test_web_season.py`
  - Adds the smoke assertion for the new endpoint.

## Data model and wiring notes

The portal is a read-only composition layer. It does not introduce a new database
schema or persist new records.

Key data sources:

- **Season identity:** `sm.get_or_create(division, gender,
  seed=world.current_year_seed(seed))`, matching the rest of the season-mode
  surfaces.
- **Program rankings:** uses `sm.power_index(sid)` when live results exist. Before
  matches are played, it falls back to `ranking_rows()` so the page is useful in
  preseason instead of empty.
- **Movement:** compares the live ranking to the deterministic baseline ranking
  from `ranking_rows()`. This is a rough portal-friendly movement indicator, not a
  persisted week-over-week ATP-style historical ranking delta.
- **Player leaders:** uses `sm.season_player_str(sid)`, `sm._pid_index()`, and
  `sm.player_records(sid)` to build STR leader cards with team, country flags,
  and W-L.
- **Race leaders:** reads `sm.standings(sid)` and takes the current conference
  leader from each table.
- **Scores and fixtures:** latest finals come from `sm.recent_duals(sid)` and
  current-week fixtures from `sm.week_duals(sid, current_week)`.
- **Juniors/recruiting:** reuses `recruiting_hub()` for the configured junior
  class year and projects only the top few prospects onto the portal.
- **Counts:** total/final dual counts are read directly from the seasonmode DB
  using the existing `_db()` connection helper.

## Design decisions

- **A portal, not another management dashboard.** The page leans into public-facing
  data discovery: large hero, pill links, score strip, KPIs, rankings, leaders,
  race, fixtures, and watchlist. Management actions still live in the existing
  World / Season / Recruiting pages.
- **Deep links instead of duplication.** The portal lifts the top story from each
  data domain and links to the full source page. This keeps it independent as a
  landing surface without creating a second copy of every table.
- **Preseason-safe rendering.** Many live data feeds are empty before week one.
  The portal handles that by showing model rankings, a preseason hero state, and
  explicit empty states for scores/player leaders.
- **Shared CSS namespace.** New classes use the existing `al-` almanac/data-portal
  namespace. This keeps them separate from bracket/season-specific classes and
  makes future portal pages easier to build.

## Known gaps / follow-up opportunities

- **True ranking history.** Movement is currently live rank vs preseason baseline,
  not previous week vs current week. A persistent weekly rankings snapshot would
  make this more ATP/WTA-like.
- **Dedicated stats pages.** STR leaders are surfaced, but there is no full player
  stats portal yet. A follow-up could add sortable player tables for STR, W-L,
  flight split, games share, doubles STR, and reliability.
- **Portal-specific JSON endpoint.** Existing JSON exposure is mostly the junior
  feed and database export. A `/data/feed.json` style endpoint could become the
  formal cross-sim portal contract.
- **Search.** ATP/WTA-style sites usually make players/tournaments searchable from
  the portal. This page links to detail pages but does not yet provide search.
- **Performance caution.** The junior watchlist reuses `recruiting_hub()`. That is
  cached after first build, but the first hit can still pay the junior class build
  cost. If the portal becomes the default landing page, consider warming the junior
  cache or using a lighter watchlist helper.

## Verification performed

- `python -m compileall app/web/server.py app/web/state.py`
- `pytest tests/test_web_season.py tests/test_web_recruiting.py -q` — 7 passed
- Manual browser check with Playwright against `/data?u=D1-men`, screenshot saved
  at `/tmp/play-to-clinch-data-portal.png` during the implementation turn.

## Handoff

For the next engineer: start with `data_portal_view()` when adding data, then wire
presentation in `data_portal.html`. If a section grows beyond a teaser, prefer a
new dedicated detail page and link to it from the portal, following the current
Rankings / Scores / Race / Juniors pattern. Keep the portal read-only unless the
user explicitly asks to merge management actions into this surface.
