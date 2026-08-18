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

Open `analytics/site/index.html` in a browser. Re-run `python3 build.py` with
no arguments to re-render from everything already ingested, or pass more zips
to add/refresh seasons — ingested raw data is cached under `analytics/data/`
(gitignored) so a season only needs re-passing if you re-exported it.

## What's here

- `teams/` — one page per program per exported season: record, schedule,
  roster, a one-line sports-desk summary.
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

## Analytics library (first pass)

Past "are they good" (record / TOSS power) into "how are they good," "is this
record lying," and "what happens when the postseason card changes." Every
derived number is computed from stored components (S%, D%, per-flight
win rate, opponent power) rather than baked in, specifically so a metric can
be reproduced or challenged rather than trusted blind — see
`ptc_analytics/metrics.py`.

Shipped in this pass:
- **S% / D%** — singles/doubles line win rate, the foundational split.
- **RCI / SCI / Fmt** — expected court share under the regular-season card
  (5S/2D) vs the State postseason card (1S/4D), and the gap between them in
  percentage points. A team with a big positive Fmt is a different, more
  dangerous team once the postseason format kicks in.
- **Doubles Reliance / Balance** — team shape in one number.
- **State Dual Win Probability** — modeled chance of winning a neutral 1S/4D
  dual (needs 3 of 5 courts), independent-court binomial approximation.
- **Opponent-power quartiles, league vs non-league split, close-match
  record** — résumé questions: who are they beating, is the record padded.
- **Storylines** — auto-flagged extremes (big Fmt, lopsided team shape,
  volatile results, suspiciously good/bad quality-win splits) with plain-
  English explanations, sorted by how extreme the number is. This is meant
  to work like a tip sheet, not a ranking.

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

Card weights (`ptc_analytics/metrics.CARD_WEIGHTS`) are configurable per
family rather than hard-coded, since divisions/classifications play
different dual shapes. Only JHSAA's 5S/2D-vs-1S/4D shape is modeled
precisely right now (that's the data on hand); college's D1/D2/D3/D4 dual
formats differ per division and aren't wired up to per-division weights yet
— `Fmt`/`SCI`/State Win% only render for JHSAA until that's added.

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
