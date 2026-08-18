# AAR — building the `/analytics` sidecar

## The ask

Owner wanted a separate tool, in its own directory, that ingests the game's own
`/research/export` zips and gives a real analytics desk to dig into — starting from a
concrete gap: the college app aggregates a player's position/lineup history across a
season on their page; the JHSAA side doesn't. Framed explicitly as "internal analytics
division, but the voice of a statewide sports desk — Fangraphs/Baseball Reference/The
Ringer/The Athletic," not a database browser.

Mid-build the owner expanded scope twice, live: (1) a ~70-metric analytics wishlist —
explicit that this should NOT ship as one long list, but as a first-pass substrate with
components stored, extremes auto-flagged as "storylines," and everything else layered
on later; (2) a same-turn correction that "conference" in the metrics code meant
*league play* (JHSAA district / college conference regular schedule), not a conference
*tournament round* — sent right as `metrics.py` was being written with a `conf_record`
field that would have read exactly backwards on export day.

## What got built, and why it's a sidecar and not a feature

`analytics/` sits beside `app/`, `docs/`, `scripts/` — a separate Python package
(`ptc_analytics/`) with its own `build.py` CLI, own Jinja templates, own copy of the
color/typography **token names and default-palette values** (not the font files, not
the component CSS) ported from `app/web/static/css/tokens/`. It reads zips produced by
`app/research_export.py` and nothing else in the game — no shared imports, no shared
database, no route. That boundary was deliberate from the first clarifying question:
the owner wants to keep doing "out of game agent analysis" on exported data as a
separate discipline from the game itself, not have the game's request thread carry a
second product's load. (`app/research_export.py`'s own read-only discipline —
see `AAR-jhsaa-research-export-resimulation-hang.md` — was the thing that made this
possible at all: the exports are static point-in-time bundles, so a build script can
own its own pace instead of inheriting the app's one-gthread constraints.)

Static HTML, no server: `python3 build.py export.zip` ingests into `analytics/data/`
(cached, gitignored, keyed on `(family, year, gender[, division])` so re-exporting a
season overwrites cleanly) and renders the whole site fresh into `analytics/site/`
(gitignored) every run. That trade was made explicit up front rather than defaulted
into — Flask+Jinja "in the house style" was the other option; static-site won because
the workflow is "drop in an export, look at the result," not a long-running service.

## What it actually contains

- **Team pages** — record, schedule, roster, a templated one-line blurb (deterministic
  string assembly off the numbers, not an LLM call — this is a build script, no API
  access needed and none wanted for something that reruns on every export).
- **Player pages** — full match log **stitched across every season ingested**, keyed on
  `player_id` (stable across a career in the export schema), plus the positions-played
  aggregation table that was the whole reason this got proposed.
- **Leaderboards** — per-scope standings, top individual records, award winners read
  straight from the exported `jhsaa_awards.json`.
- **An analytics library, in its own dropdown menu** (`Analytics ▾` in the masthead,
  `<details>`-based, no JS framework), specifically NOT a flat scrolling list — the
  owner's stated principle was that a big first-pass metric library needs real
  navigation (Overview / Team Shape / Format Lift / Résumé / Storylines) so the data can
  tell them later which numbers earn a permanent spot, rather than burying that decision
  in one page.

## The metrics substrate (`ptc_analytics/metrics.py`)

Shipped from the owner's list, computed off stored components rather than as opaque
finished numbers (their explicit requirement — "an analyst should be able to reproduce
or challenge it without reverse-engineering the calc"):

- **S% / D%** (singles/doubles line win rate) — the foundational split.
- **RCI / SCI / Fmt** — expected court share under the regular 5S/2D card vs the State
  1S/4D card, and the percentage-point gap between them. This is the one the owner
  called out by name as "probably the next genuinely revelatory statistic after Fmt" —
  it answers "what happens when the card changes," which a plain win-loss record can't.
- **Doubles Reliance / Balance**, **State Dual Win Probability** (independent-court
  binomial, needs 3-of-5 courts), **opponent-power quartile splits**, **league-vs-
  non-league record**, **close-match record**, **volatility** (stdev of per-dual line
  share).
- **Storylines** — extremes flagged automatically (`|Fmt| >= 10pp`, `|DR| >= 25pp`,
  lopsided close-match/quartile records, high volatility), sorted by how extreme the
  number is, explicitly framed as a tip sheet rather than a ranking.

Card weights live in one table (`CARD_WEIGHTS`), not hard-coded into the formulas —
because the game itself plays a DIFFERENT dual shape per division (see the per-division
dual-format rule at the top of this file's CLAUDE.md), so a hard-coded 5+2/1+4 would
have been quietly wrong the moment someone fed it a college export. Only JHSAA's shape
is wired precisely right now; `Fmt`/`SCI`/State Win% render `None` (—) for college until
a per-division weight table exists. Said plainly in the README rather than left to be
discovered — a metric that silently degrades to a wrong number on an unmodeled division
is exactly the kind of thing this repo's other AARs keep finding the hard way.

## The near-miss: "conference" almost meant the wrong thing

While `metrics.py` was mid-write, computing a league-vs-non-league split off JHSAA's
`duals.district` boolean and college's `duals.is_conference` boolean, the field was
named `conf_record` with keys `"conference"`/`"nonconference"`. The owner corrected,
live, mid-turn: in this domain "conference" already has a real, different meaning (the
end-of-season conference tournament round, one rung on the JHSAA recovery ladder and a
distinct `round` value in college's `duals.csv`), and using the same word for "in-league
regular-season play" would have collided with it on every page and every future metric
built on top of the field. Fixed before it shipped: renamed to `league_record` with
`"league"`/`"non_league"` keys, and the boolean-source comment spells out explicitly
that both source columns mean the regular league schedule, never a tournament round.
Cheap to fix here because it was caught before the first commit; the lesson is generic
to this codebase, not sidecar-specific — a domain this dense reuses ordinary words
(district, conference, region, division, ward) for named playoff stages, and a variable
name borrowed from "what a normal sports site would call this" needs a second look
against this project's own vocabulary before it ships. (The JHSAA section of this file
has an almost identical rule already, in the other direction: league *names* must never
be Conference/Division/Region/Ward/Zone/Section/Area, because those are all playoff
units here.)

## What's explicitly NOT built

The owner's list ran to ~70 metrics (opponent-adjusted S+/D+, bracket title-equity
Monte Carlo, player WAR, pair chemistry, trend/form ratings, matchup-edge modeling, and
more). None of those are implemented. The README says so directly: this pass is the
substrate everything else in that list gets computed from, not a partial attempt at all
of it. Building toward "comprehensive" without saying which parts are actually done is
exactly the kind of thing that reads as finished when it isn't — stated the gap instead.

Also not built: a real college export was never available to test against (only the
girls/boys 2027 JHSAA zips were supplied), so the college ingestion path is written
strictly to `research_export.py`'s schema but unexercised. Said to the owner directly
rather than silently assumed to work.

## Where the files are

`analytics/README.md` is the primary spec/contract now — read it, not this AAR, before
extending the metrics library or adding a page. This document is the *why*, not the
*how*.
