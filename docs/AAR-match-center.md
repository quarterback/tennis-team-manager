# AAR — Match Center (flashscore/sofascore-style dual detail pages)

## Head-to-head rewrite (owner correction, 2026-08)

The Matches tab shipped as a 5-row "recent form" list, capped and silently
truncated — copied from flashscore/sofascore's H2H widget without noticing
*why* those sites cap it: their players mostly haven't met much. This sim
can run a single save for 25+ years, and two programs in the same league
play every year — a real rivalry has dozens of meetings, and capping at 5
with no indicator just reads as broken data.

**The fix reorders the whole tab around the real-world convention (rivalry
pages, Winsipedia-style team-compare pages): the CAREER SERIES RECORD
first, the complete game list second — never a recency snippet standing in
for the record.** `matchcenter.summarize_series(meetings, team_a, team_b)`
takes EVERY known meeting (the three `prior_meetings` functions no longer
cap or `LIMIT` — they return the full history) and computes: who leads and
by how much (W-L, or W-L-T since JV can tie), total meetings and the date
range, current streak, last meeting, last-10 split, a postseason-only split
(when there's been a postseason meeting), and largest margin of victory per
side. `mc_h2h` renders that summary plus a win/tie/loss comparison bar,
then lists every meeting underneath — no cap, no "show more," because
nothing is hidden.

‼️ **`summarize_series` needs the postseason flag threaded through, and
"postseason" means something different per division** — college is
`round in ('CT', 'NCAA')` (the Preseason NIT, `ITAK`/`ITAI`, is a
PRE-season event and does NOT count), GTT is `round == 'PO'`, JHSAA is
`phase in jhsaa.POSTSEASON`. Each `prior_meetings` computes its own division's
flag; `summarize_series` itself is division-agnostic and just reads it off
each meeting dict.

‼️ **A meeting's `home`/`away` name is per-GAME (venue alternates); the
series record is keyed on the two PROGRAMS.** `summarize_series` tallies a
win against `team_a`/`team_b` (the two programs' current display names),
never against "home"/"away," which is why every `mc_h2h(...)` call site
passes the SAME two name strings it used server-side to build `series` —
`series.wins[home]` in the template only resolves correctly because `home`
is that exact string.

Verified by hand-tracing `summarize_series` against several constructed
series (a mixed win/loss/tie/postseason sequence, a single-meeting series,
an all-tie series) and by running it through `tests/test_web_gtt.py`'s real
box-score page end to end.

Owner request 2026-08: model the college/GTT/JHSAA dual-detail pages on
flashscore.com/sofascore.com's live-match UI (score header, grouped
stat-comparison bars, tabs). Read the two sibling docs first if you're
extending this: `app/matchcenter.py`'s module docstring (the stat data-shape
gaps) and `app/web/templates/_matchcenter.html`'s header comment (why the
per-court listing was NOT unified).

## What shipped

A shared macro file, `app/web/templates/_matchcenter.html`
(`mc_scorehdr`/`mc_tabs`/`mc_panel_open`/`mc_panel_close`/`mc_stat_bars`/
`mc_h2h`), that all three dual-detail pages now render from:

- **College** — `season_dual.html` (`/season/dual/<id>`, `sm.dual_detail`)
- **Pro/GTT** — `gtt_dual.html` (`/gtt/dual/<id>`, `gs.dual_detail`)
- **JHSAA** — **new**, `jhsaa_dual.html` (`/jhsaa/dual/<id>`,
  `state.jhsaa_dual_view` + `world.jhsaa_dual_row`/`jhsaa_prior_meetings`).
  This is a real gap that existed before: JHSAA had `world_jhsaa_dual.lines`
  (the same box-score shape college and GTT persist) but no detail page or
  route. Linked in from `jhsaa_school.html`'s existing expandable schedule
  rows (a "Match Center" chip beside the existing line-score toggle, both
  varsity and JV tables).

Each page still owns its own per-court/line listing under the Details tab
(college's `line_row`, GTT's collapsible `statrow` panels, JHSAA's plain
name-list rows) — see `_matchcenter.html`'s header comment for why that
wasn't forced into one macro (the three divisions' per-line data shapes
genuinely differ: pids vs names-only, set-tuple lists vs a scoreline string).
What's shared is the score header, the tab strip, the new Statistics tab
(grouped stat-comparison bars), and a new Matches (head-to-head) tab.

`app/matchcenter.py` is the new pure aggregation layer: `sum_college_lines`/
`sum_gtt_lines` normalize each division's already-persisted per-line stats
into one common `PlayerStats`-field-named shape, and `stat_groups` turns that
into the Service/Return/Points bar-comparison groups the template draws.
**No engine, cache, or persistence changes** — this only reads data that was
already being computed and stored.

## Decisions made with the owner up front (don't re-litigate these)

1. **Replay-only, not live.** The engine simulates an entire week's slate in
   one batch server call (`world.advance_week`) with no incremental match
   state anywhere — there is nothing to poll or stream. Every Match Center
   page is a post-match box-score view. Nothing auto-refreshes. Do not add
   polling/websockets/a "live" badge that implies real-time updates without
   a much bigger architecture change (background sim workers + partial-state
   persistence) that was explicitly deferred, not merely unbuilt.
2. **Unify all three divisions**, not just college. That's why the JHSAA gap
   got filled in the same pass rather than left for later.
3. **Defer true point-by-point** (the 0-15-30-40 game log flashscore/sofascore
   show). The engine's point-level fidelity resolves every point during
   full-fidelity simulation (`engine/rally.py::play_point`) but the sequence
   is never persisted — only the final scoreline and aggregate `PlayerStats`
   counters survive. Adding it means capturing a per-point log during
   simulation and persisting it (a real engine + schema change), which was
   explicitly scoped OUT of this pass. If you build it later: make the field
   optional/additive so old `lines_json` rows without it just hide the tab
   rather than erroring, the same pattern `stat_groups`/`mc_stat_bars`
   already use for "nothing recorded."

## Data-shape gaps — read before touching `app/matchcenter.py`

Two real, already-encountered gaps, both handled by **dropping the row**
rather than fabricating a number:

- **GTT never records a first-serve-attempt denominator.**
  `gtt_seasonmode._stat_summary` tracks `fs_in` (first serves in) but no
  `fs_total`/attempts count, so "1st Serve %" has no denominator on GTT. This
  is not a bug in this feature — it's a pre-existing gap in what
  `_stat_summary` aggregates. `matchcenter._drop_empty` removes any stat row
  that renders "—" on both sides, so the row simply doesn't appear on a GTT
  page rather than showing a permanently blank line. If `_stat_summary` ever
  grows a `fs_total` field, the row will just start showing up — no template
  change needed.
- **JHSAA never records box stats at all.** `jhsaa.FIDELITY` is always
  `"fast"` (CLAUDE.md: a full point-level state bracket would stall the
  request thread), so no `PlayerStats` ever exist for a JHSAA dual.
  `jhsaa_dual_view` sets `stat_groups: None` unconditionally — the
  Statistics tab always shows "No stats recorded for this dual" there. This
  is not a placeholder to fill in later without also solving the fidelity
  cost problem CLAUDE.md documents; don't wire a fake aggregation just to
  make the tab look populated.

Only build a stat row here if it maps 1:1 onto a field the engine already
tracks (`engine.state.PlayerStats`/`STAT_KEYS`). "Games" (total games won
across a dual) was deliberately left OUT of the Statistics tab for this pass
even though college's persisted lines have `home_games`/`away_games` per
line — GTT doesn't persist that at all (only a `scoreline` string), and
parsing it back out of the string to add one more group felt like more risk
than the value justified for a first pass. If you want it: college can sum
`home_games`/`away_games` directly; GTT needs either a schema addition or a
`scoreline` parser, and it should degrade the same way the other rows do
(drop the group entirely for divisions that can't supply it) rather than
showing an asymmetric fourth group only on some pages.

## Four bugs found in review, all in the JHSAA wiring (fixed same day)

- **Year was the raw archive key, not the calendar season.** `world_jhsaa_dual.
  year` is zero-based (`BASE_YEAR + year + 1` is the real season, same
  arithmetic as `jhsaa_season_year`); printing it raw read "Final · 0" on
  every dual. `jhsaa_dual_view` now returns BOTH — `year` stays raw (every
  other cross-link in this section, including the `jhsaa_school` URL, expects
  that same raw key) and `season_year` is the converted value for display
  only. Meeting labels in `jhsaa_prior_meetings` get the same conversion.
- **Exclusion by raw id silently failed from the away side.**
  `jhsaa_prior_meetings` only ever returns `home=1` rows, but a dual opened
  from the away school's schedule hands `jhsaa_dual_view` the `home=0`
  sibling's rowid — which can never match anything in that result set, so
  the dual being viewed showed up in its own head-to-head history.
  `jhsaa_home_row_id` resolves the actual home-side rowid (by the RAW
  archived names, not the canonicalized ones — see next point) when needed,
  and `jhsaa_dual_view` always passes that as `exclude_id`.
- **Only `opp` was canonicalized, not `school`.** A renamed program's OWN
  archived rows kept the historical name for `school` while `opp` got
  aliased — so its old schedule rendered the retired name, and worse,
  `jhsaa_home_row_id`'s companion-row lookup (which must match what's
  literally stored) would have broken if I'd aliased before that lookup.
  Fixed by keeping BOTH: `school_raw`/`opp_raw` (for the companion-row
  query) alongside the now-consistently-aliased `school`/`opp` (for
  display). `jhsaa_prior_meetings` also now searches every name either
  program has ever had (`jhsaa.known_names`), not just today's — the same
  reasoning `world._schedule_rows` already uses.
- **Varsity and JV history were mixed.** `world_jhsaa_dual` stores both
  levels in one table, told apart only by `level` (CLAUDE.md's own
  standing warning about this table). `jhsaa_prior_meetings` didn't filter
  on it, so a varsity Match Center could list a JV result as a prior
  meeting, and since JV rows outnumber varsity ones, a handful of them
  could crowd every real varsity meeting out of the 5-result limit.
  `jhsaa_dual_view` now threads the current dual's own `level` through to
  the lookup.

All four verified directly against a generated JHSAA season (not
screenshots): a genuine district rematch pair, viewed from both its home
and away rows, each correctly excludes only itself and shows the other
meeting; a pair with both a varsity and a JV meeting the same season
resolves the two lookups to disjoint results.

## `world_jhsaa_dual` has no dual-level id — how the JHSAA route works

Every JHSAA dual is TWO rows in `world_jhsaa_dual` (one per school, `home`
flag marking which one) with no surrogate id column. `jhsaa_dual_row` uses
SQLite's implicit `rowid` as the lookup key for **either** side's row — and
either side is enough to render the whole dual, because `lines` is the SAME
shared list object on both rows (`play_dual` appends it to both teams'
schedule entries — see `state._jh_reported_lines`'s docstring, one section
up from `jhsaa_dual_view`), and each line's `home_won`/`home`/`away` keys
already name the TRUE home team regardless of which row you're looking at.
Only `pf`/`pa`/`home` differ by row, and `jhsaa_dual_view` normalizes those
against the row's own `home` flag to get true home/away points. This needed
one additive column added to two existing SELECTs (`rowid AS id` in
`world._schedule_rows` and the new `jhsaa_dual_row`) — no schema migration.

`jhsaa_prior_meetings` reads only `home=1` rows for a pair to avoid double-
counting (the two rows of one dual are duplicates of each other).

## Head-to-head (`Matches` tab)

Each division has its own `prior_meetings` (`sm.prior_meetings`,
`gs.prior_meetings`, `world.jhsaa_prior_meetings`) — deliberately NOT
unified into one query, since the three tables (`duals`/`gtt_duals`/
`world_jhsaa_dual`) have different shapes and identity keys (school name vs
franchise id vs school name+`home` flag). Each returns a common shape
(`{id, label, home, away, home_points, away_points}`) that `mc_h2h` renders;
the ROUTE (not the macro, not the data function) is what attaches `url` to
each meeting, since URL-building is Flask/routing concern and each division's
detail route has a different name/param shape. College's `label` is `"Wk
N"` rather than a year — `duals`/`seasons` carry no year column (a season
row doesn't persist across years the way `world_jhsaa_dual`/`gtt_duals` do),
so inventing one would have meant a deeper dig into season-year continuity
that was out of scope here.

## What to check before extending this further

- `grep -rn "mc_scorehdr\|mc_stat_bars\|mc_h2h" app/web/templates/` to find
  every page currently using the shared macros before changing a signature.
- If you add a fourth "division" dual page: it should call the SAME macros
  from `_matchcenter.html`, not fork new markup — that's the whole point of
  pulling them out. `_bracket.html` is the precedent this follows (shared
  Jinja macros + one CSS file per feature area, not a copy per page).
- New CSS lives under the existing `.bl-*` prefix in `app/web/static/css/
  app.css` (`.bl-mctabs`/`.bl-mctab`/`.bl-mcpanel`/`.bl-statrow`/
  `.bl-statvals`/`.bl-statbar`/`.bl-h2hrow`), reading only semantic color
  tokens (`--stat-good`, `--brand-strong`, `--text-muted`, etc.) — see
  CLAUDE.md's colour section before adding a raw value.
- The tab-switch script is emitted INLINE inside the `mc_tabs` macro (not a
  separate `<script>` block in each including template), because Jinja's
  `{% from import %}` only pulls in macros, never a template's top-level
  markup — a script placed in `_matchcenter.html` outside a macro would
  never reach a page that imports from it.

## Testing

No engine or query-logic changes beyond the two additive `prior_meetings`/
`jhsaa_dual_row` reads and the `rowid AS id` column addition, so the
existing suite should be unaffected. `tests/test_web_gtt.py::
test_gtt_dual_box_score` already exercises the refactored `gtt_dual.html`
end-to-end (it asserts `b"Aces"`/`b"Service Points Won"` are on the page,
which now also appear inside `mc_stat_bars`'s output) and passed unchanged.
The full suite was intentionally NOT run for this change (owner instruction)
— run the targeted files touched here (`test_web_gtt.py`, `test_dual_
formats.py`, `test_jhsaa_routes.py`) rather than the ~10-minute full suite
for a quick follow-up. `test_jhsaa_routes.py::
test_every_classification_has_its_own_class_colour` fails on a clean
checkout of this branch too (a pre-existing `jhsaa.css` gap unrelated to
this change — verified via `git stash`); don't spend time on it here.
