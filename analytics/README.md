# The Clinch Report — analytics sidecar

A separate, static-site analytics tool that ingests Play to Clinch **research
exports** (`/research/export` in the game, zips with `manifest.json` +
`programs.csv`/`players.csv`/`duals.csv`/`lines.csv`/`line_players.csv` plus
JHSAA- or college-only files) and builds team pages, player career pages, and
a first-pass sports-analytics library out of them — styled to look like the
game's own design system, written like a state-desk beat outlet.

This tool never touches the game's database or app code. It only reads zips
you export and drop in.

## Use

```
cd analytics
pip install -r requirements.txt   # just Jinja2
python3 build.py path/to/export.zip [more.zip ...]
```

**Browse it over a local server, not by double-clicking the file.** `cd site &&
python3 -m http.server 8000`, then open `http://localhost:8000/`. This isn't
optional cosmetics: "My Teams" (the pin/star feature) stores its data in
`localStorage`, and browsers scope `localStorage` per ORIGIN — a `file://`
page has no real origin, so several browsers (Firefox in particular; Chromium
is inconsistent about it) silently give every `file://…/teams/x.html` and
`file://…/index.html` its OWN separate storage bucket. Pin a team from a team
page and it can look empty on the home page's My Teams panel even though
nothing failed — the star toggled, the write happened, it just didn't land
anywhere the next page can see. A shared `http://localhost` origin is the
actual fix; nothing in this app can paper over a browser storage-partitioning
policy from inside a static page. Everything else on the site (browsing pages,
filters, search) works fine either way — only the cross-page favorites feature
needs the server.

Re-run `python3 build.py` with no arguments to re-render from everything already ingested, or pass more zips
to add/refresh seasons — ingested raw data is cached under `analytics/data/`
(gitignored) so a season only needs re-passing if you re-exported it.

## Navigation (owner rewrite, 2027-08)

The first pass flatly listed every program (~1,600) and every player (~19,700
statewide) — closer to a raw database dump than an analytics tool, and it made
the site nearly unusable at real scale. Rebuilt to look like the actual pro-
team scouting tools this is modeled on (StatsBomb IQ / Wyscout-style: a
persistent season → competition → team scope picker, not a flat list, plus
pinned favorites) rather than a Football Manager save browser:

- **Teams** — cascading Season → Classification → League `<select>`s, plus an
  independent global search box that ignores the pickers. Nothing renders
  until you pick a season or start typing — never a silent 1,600-card dump.
- **Brackets** — new section, reading `jhsaa_championships.json` (was
  ingested and completely unused before this pass) straight from the export:
  the real archived postseason draw, round by round, per classification —
  the same "look at the playoff bracket" the game itself offers. Round
  labels use the export's own `round_names` field verbatim wherever it's
  present (`_round_names()` in `render.py`) — an expanded 40-team
  classification prepends "Qualifiers Round"/"First Round" ahead of a
  converged Octofinals-onward bracket, and those two rounds are NOT a
  continuation of the same single-elimination sequence as the rest, so
  they're never relabeled by distance-from-final the way the tail is.
- **My Teams** — a star/pin button on any team card or team page, stored in
  the browser's `localStorage` (no server, no account) and surfaced on the
  home page, so you don't re-search your own team/league every visit.
- **Players** — search-only by design (a flat index at this scale is not
  useful); the real way in is a team's roster page, where every name already
  links out.

## What's here

- `teams/` — one page per program per exported season: record, schedule,
  roster, a one-line sports-desk summary. **JHSAA roster sizes are no longer
  flat** (owner rule, `ROSTER_SIZE_BY_CLASS`): they now scale by
  classification, 9A 24 down to 1A 13, mirroring the college side's
  `roster_cap` pattern — don't read a shallow 1A roster next to a full 9A one
  as missing data, it's the format. Grade distribution is no longer an even
  ~3-per-grade split either (each class's freshman count is now rolled once
  per school/entry-year and ages forward), so a season's grade mix will look
  naturally uneven rather than symmetric.
- `players/` — one page per player, stitched across every season ingested
  (player_id is stable across a career), with a full match log **and** an
  aggregated positions-played table — the JHSAA gap that started this: the
  in-game college app shows a player's position history across a season, the
  JHSAA side didn't.
- `leaderboards/` — per-season team standings, top individual records, award
  winners pulled straight from the exported award JSON.
- `metrics/` — the analytics library (see below), split into its own
  dropdown menu rather than one long page, since the metric list is meant to
  grow.
## Structure (owner rewrite ×2: 2027-08 nav, 2028-08 data organization)

‼️ **CLASSIFICATION → DISTRICT IS THE ORGANIZING HIERARCHY ON EVERY PAGE,
LIST AND MENU** (owner rule 2028-08) — the exact parallel of the college
game's division → conference. Nothing may ever render a statewide splat: the
first pass listed 861 teams in one standings table ranked on win% and seven
single-metric pages each dumping every (team, season) row statewide, and the
owner's verdict was "impossible to really parse and navigate." The mental
model is **Football Manager / FMRTE**: dashboards with tabbed views, dense
sortable grids scoped by pickers, and entity pages that carry their own
stats in panels. Two corollaries, also owner rules from the same session:
**a player's grade shows in every list a player appears in** (JHSAA "12th" /
college class year, sortable — no clicking through to discover someone's a
senior), and **no tutorial help text** on the pages themselves.

- **Seasons** (`seasons/`) — one dashboard per exported season, four tabbed
  views of it: **Rankings** (class-first — the page opens on the biggest
  classification, statewide is an explicit option — ranked on the ARCHIVED
  TOSS power exactly like the game's own rankings page, win%% only as the
  pre-TOSS fallback; every row carries class rank, state rank, district and
  district record/place), **District standings** (one panel per
  (classification, district), ordered on the archived district place — the
  association's own tiebreak ladder decided it, never re-derived),
  **Individual leaders**, **Awards**. Classification/district pickers +
  search filter all tabs.
- **Teams** — cascading Season → Classification → League pickers; the card
  grid renders only once a classification narrows it (or a search does).
- **Team pages** — the FM club screen: KPI tiles (record, district record +
  place, class rank of N, power + statewide rank), the schedule presented
  the way the game presents it (sectioned League play / Invitationals /
  Showcases / Road to State / State / TOC, real dates from the export's
  `duals.date`, vs/at, type chips — never raw phase strings — and
  winner-first scores per the game's scoreline convention), a roster with
  per-player grade + singles/doubles season records, and a Season analytics
  panel so a team's own metrics live on its page instead of seven league
  tables away.
- **Brackets** — the archived postseason draw per classification, straight
  from `jhsaa_championships.json`.
- **Players** — search-only by design; rosters are the real way in.
- **My Teams** — localStorage pin/star, unchanged.

### Schedule ordering: `duals.date` (export schema addition, 2028-08)

The JHSAA export now carries `duals.date` — the game's own display calendar
(`world.jhsaa_match_dates`, one date per dual, identical from both sides).
Without it the sidecar had NO play order for JHSAA (there is no clock inside
a JHSAA season) and fell back to export-file order, which lists a team's
home duals first and its away duals wherever the opponents' cards put them —
that's why every schedule read "Home, Home, Home…" down the page. Old zips
without the column still render (sectioned, card order within a section);
re-export a season to get real dates.

## What's here

- `teams/`, `players/` — entity pages as above; player pages stitch a career
  across every season ingested on the stable player_id, with the full match
  log (dated, type-chipped) and positions-played table.
- `seasons/` — the per-season dashboards.
- `metrics/` — the analytics library: ONE **Team Stat Center** grid
  (season → classification → district scoped, switchable column-group views:
  Shape / Format lift / Résumé / Depth & volatility / Predictive, every
  column sortable) plus **Player Value (PVAR)**. The seven separate
  single-metric pages are gone — a new metric is a new column (or view) in
  the grid, never a new page of everything.
- **Storylines are ARCHIVED, not rendered** (owner call 2028-08: "not useful
  as rendered at all") — `metrics_mod.storylines()` still runs on every
  build and writes `analytics/data/storylines.json`; there is no page.

## Analytics library (first pass)

Past "are they good" (record / TOSS power) into "how are they good," "is this
record lying," and "what happens when the postseason card changes." Every
derived number is computed from stored components (S%, D%, per-flight
win rate, opponent power) rather than baked in, specifically so a metric can
be reproduced or challenged rather than trusted blind — see
`ptc_analytics/metrics.py`.

Shipped in this pass:
- **S% / D%** — singles/doubles line win rate, the foundational split.
- **RCI / SCI / Fmt** — expected court share under the regular-season card vs
  the state/postseason card, and the gap between them in percentage points.
  A team with a big positive Fmt is a different, more dangerous team once the
  postseason format kicks in.
- **Doubles Reliance / Balance** — team shape in one number.
- **State Dual Win Probability** — modeled chance of winning a neutral
  postseason-shaped dual (needs a majority of that card's lines),
  independent-court binomial approximation.
- **Opponent-power quartiles, league vs non-league split, close-match
  record** — résumé questions: who are they beating, is the record padded.
- **Storylines** — auto-flagged extremes (big Fmt, lopsided team shape,
  volatile results, suspiciously good/bad quality-win splits) with plain-
  English explanations, sorted by how extreme the number is. This is meant
  to work like a tip sheet, not a ranking.

Tests: `python3 -m pytest analytics/tests -q` (from the repo root) runs
data-bearing coverage — a synthetic multi-class season is pushed through the
GAME's own export builder, ingested, rendered, and the assertions read the
HTML (an empty-state test cannot see a page; that lesson is the game's own).

Second pass, added the same session: Format Dependency, Format Win-Probability
Lift, State score profile / three-court / sweep probability, Expected State
Margin, Dominance Margin, split singles/doubles game share and set share
(JHSAA only — college's export has no set-level detail), Line Conversion,
per-flight win-rate curves feeding Top-End/Depth/Star-Dependence, Singles/
Doubles Depth Slope, Floor/Ceiling, Blowout/Resistance rate, and a crude
auto-scaled power-based win-probability model (logistic on TOSS power,
scaled to that season's own spread) driving Expected Record/Record Luck,
Upset Rate/Value, Bad-Loss Value, and Elite Win Share. Plus a first-cut
**Player Value Above Replacement (PVAR)**: for every slot a player logged 3+
matches at, replacement level is the 25th-percentile win rate among other
players at that same slot/season; PVAR sums (actual − replacement) × matches
across every slot and season — deliberately not split by singles/doubles, so
it answers "how much was this player actually worth" rather than restating
S%/D%. All of it lives in three new Analytics pages (Depth & Volatility,
Predictive, Player Value) rather than piling onto the existing ones.

‼️ Card shapes (how many singles/doubles lines a "regular" or "state" dual
plays) are **derived from the actual exported duals per scope**
(`aggregate.Bundle.regular_shape`/`state_shape`, the most common line-count
shape seen in each phase/round bucket), never hard-coded — an earlier
version hard-coded JHSAA's regular card as 5S/2D, and the game swapped that
to 3S/4D in the same session this was built, which would have silently
rendered every Fmt/RCI/SCI number backwards. `Fmt`/`SCI`/State Win% return
`None` (rendered "—") when a scope has no duals in that phase/round bucket
yet — currently that's most college scopes (their postseason `NCAA` round
isn't in the sample export), not a family-level restriction anymore.

**A note for JHSAA seasons exported after the format swap**: the game's
regular-season card is now 3 singles/4 doubles (was 5S/2D — the early
non-district window now plays the old 5S/2D shape instead, a straight
swap). Nothing in this sidecar hard-codes either shape (see above), so no
code here needed to change for the swap itself. What it does mean for
reading the numbers: under 3S/4D the S2/S3 lines are a team's *weakest*
two starters (the doubles pool takes the real #2-#9), not its 2nd/3rd
best — the opposite of what they meant under 5S/2D. Keep that in mind
comparing a player's S2/S3 stat line across seasons exported before vs.
after the swap; this sidecar reports raw per-slot performance and doesn't
attempt to normalize across the swap. Award data ingested from
`jhsaa_awards.json` already reflects the game's own post-swap reweighting
(regular-season S2/S3 down-weighted relative to doubles in selection) —
see the game repo's `docs/AAR-jhsaa-awards-3s4d-format-swap.md` if you
need the mechanics.

The full wishlist (opponent-adjusted S+/D+, bracket equity simulation,
player WAR, pair chemistry, trend/form ratings, and the rest) is not built
yet — this first pass is the substrate everything else in that list gets
computed from. Add new metrics as functions against `TeamMetrics`/`Bundle`
rather than a fresh ad-hoc pass over the raw tables.

## Design system

Colors/typography are ported from `app/web/static/css/tokens/{colors,
typography}.css` — same token names and default ("Ensign") palette values,
so a future pass can wire in the other nine schemes without touching
component CSS, same as the game does. Component classes (`.pt-panel`,
`.pt-kpi`, `.pt-table`, `.pt-crest`) mirror the game's `.bl-panel`/`.al-kpi`/
`.bl-protable`/`.bl-crest` patterns rather than reusing them directly, since
this is a standalone static site with no server and no access to the game's
font files.
