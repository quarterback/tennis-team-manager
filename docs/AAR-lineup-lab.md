# AAR — Lineup Lab (Analytics Bureau): every team's singles ladder by conference

**Date:** 2026-06-24
**Scope:** `scout_intel.conference_list` / `conference_lineups` /
`conference_strength`; route `/intel/lineups` + nav/hub wiring in
`web/server.py` / `intel_hub.html`; new `templates/intel_lineups.html`.

## Why

The Bureau already answered "where does *this* player fit?" (one recommendation
per player, via `fit_targets`). The owner wanted the inverse and the breadth: pick
**any conference**, see **every** team's singles lineup at once, judge roster depth
and gaps league-wide, and place a recruit by browsing many landing spots — plus a
read on **relative league strength**. The reference was UTR Sports' "Lineup
Comparison" D3 strip plot (dots = a player's rating at lineup position 1–6).

## What it does

A new Bureau page (`/intel/lineups`, nav "Lineup Lab"):
- **Strip plot.** Pick division + conference; each dot is a starter's **STR** at
  their lineup position (1–6). Hover → that school's full 1–6 ladder (hovered line
  highlighted). An optional "highlight team" turns one school red against the
  conference's teal (the UTR Virginia-vs-ACC view).
- **Team-depth table.** Every team ranked by average starter STR, with top/low
  starter STR and the full ladder.
- **League-strength table.** Every conference in the division ranked by average
  starter STR, with its curated tier (top/major/mid/low) and team count; each row
  links to that conference's plot.

## How it's built (decisions)

- **Data reuses the existing god-mode `scan()`** — it already yields, per player,
  `cur_str` (STR on the sim's 31–57 band), the lineup slot `line` (1–6), school,
  and conference (`team_tier`). The three new functions are thin shapers over that
  one cached scan, so no new rating/roster code and no extra cost.
  - `conference_lineups(division, gender, conf, highlight)` → per-team top-6 ladder
    + avg/top/low, sorted by avg.
  - `conference_strength(division, gender)` → per-conference avg/top starter STR +
    team count + `conf_tier`/`conf_prestige`, ranked.
  - `conference_list(division, gender)` → conf abbrs for the selector.
- **Charting: self-contained inline SVG + vanilla JS, NOT D3/CDN.** The app loads
  no external scripts (checked `base.html`), and outbound CDN is proxied/uncertain
  in headless/cron runs, so a CDN dependency would be fragile. The plot is ~110
  lines of dependency-free JS: it reads `{{ lineups|tojson }}`, builds y-scale from
  the data, lays dots in six position columns with a **deterministic** per-school
  horizontal jitter (hash of the name — stable across redraws), draws highlight
  team on top, and shows an absolutely-positioned tooltip. Redraws on resize.
- **STR, not converted UTR.** Dots are on the sim's native STR band (31–57), the
  same scale every other surface shows. A future toggle could convert to a
  UTR-style number, but mixing scales now would confuse.

## Verified

- Backend: D1 has 34 conferences; ACC returns 16 teams each with a 6-point ladder;
  league strength ranks SEC > Big 12 > ACC > Pac-16 > Big Ten > Ivy (top tier
  first), matching the re-leveled conference hierarchy.
- Route 200s for D1–D4; the embedded `DATA` parses as valid JSON; nav link, hub
  card, and active-tab highlight all wire up.
- No headless browser in the environment, so the plot wasn't screenshotted — the
  structure/data are verified programmatically; visual tuning (jitter, scale) is a
  look-and-adjust follow-up.

## Possible follow-ons (noted, not built)

- A **"recruit STR" input** that draws a horizontal reference line across the plot
  and flags which teams' lineups that STR would crack — directly answers "where
  does a 13.5 fit?" across the whole league.
- Optional UTR-scale relabel of the y-axis.
- Region/round-style polish (beeswarm spacing instead of hash jitter) if dots
  overlap too much in deep conferences.
