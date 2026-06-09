# AAR — Recruiting & Juniors Data Portal

## Segment summary

This segment turned the juniors + recruiting data — which the engine already
produced but barely surfaced — into a navigable **data portal**, in the read-only
presentation pattern of three reference sims the user pointed at (viperball's
Bloomberg-terminal stats site, O27's Fangraphs-style almanac, Super Innings'
management dashboard). The framing the user landed on, after a couple of wrong
turns: *"it's a SaaS dashboard problem — I can't manage things because there's no
data portal."* So the work is a presentation layer, not new simulation.

Shipped on `claude/junior-circuit-spec-i5QGW` (PR #26); rebased clean onto current
`main` (which had gained PR #35's Bubble Watch + Bracket Projection and the
team-logo system). Full suite 166 green throughout.

## The architecture (borrowed from O27, deliberately)

Both reference systems converge on one lesson, and O27 states it most sharply:
a read-only presentation layer over the sim, kept in separated layers —
**loader → compute → render → export** — with metrics calibrated against the
*population*, not real-world constants. Our Flask app already fits the
"same-process, thin adapter over live in-memory state" half of that (viperball's
model), so the mapping was:

| Layer | Where |
| --- | --- |
| compute (pure derived math) | `app/almanac.py` — stat lines, sortable columns, leaders, honor badges |
| loader / adapter (live state → dicts) | `app/web/state.py` |
| render (live Jinja pages) | the templates |
| export (the wiring contract) | `/juniors/feed.json` |

`app/almanac.py` is engine-agnostic and I/O-free; the web layer and the JSON feed
both consume it, so the math lives in exactly one place.

## What was built

- **Junior Rankings** (`/juniors/rankings`) — a dense reference table: clickable
  **column sorting** (rank/points/STR/titles/win%/events/stars/board), **honor-badge
  medals** (gold/silver/bronze from the junior milestones), league-leader cards, and
  the JSON feed.
- **Recruiting HQ** (`/recruiting/hub`) — the portal landing: class KPI stat-cards,
  quick-cards to every sub-page, Top Prospects with badges, League Leaders rail.
- **Signing Tracker** (`/recruiting/signings`) — reads the **live world commitments**
  (`world.signings()` over the `world_signing` table) into Team Class Rankings
  (programs ranked by signed-class strength) + a Top Commitments list, with a
  graceful empty state (signings accrue as the season advances).
- **Per-team recruiting class** (`/recruiting/team/<school>`) — one program's class:
  KPI cards + a commits table, every recruit linked to their card.
- **Game-wide almanac home** — the dashboard gained an O27-style KPI stat-card row
  (Season/Week/phase, Programs, Conferences, Players, Class Signed, Champion/No.1)
  above the existing top-programs / STR-leaders / bracket-seeds panels.
- **Top dropdown nav** (Super-Innings style) — the grouped nav became horizontal
  dropdown menus in the top bar; the sidebar was demoted to a hamburger drawer at
  every width so content runs full-width. (`base.html`, `shell.css`.)
- **Cross-linking** — every player name → their card and every program name → its
  team / recruiting-class page, across the rankings, hub, signing tracker, per-team
  page and the dashboard, using the team-logo crest system from main.
- All portal CSS consolidated into a shared `app/web/static/css/almanac.css`.

## Decisions & tradeoffs (owning the wrong turns)

This segment took several user redirects; recording them so the reasoning is legible:

- **Percentile bars → honor badges.** I first built Statcast-style population
  percentiles (the O27 "index" idea) on the profile. The user didn't want them —
  *"badges for the various honors and an easy way to sort."* Pivoted: the percentile
  machinery was deleted from the compute module and replaced with `honor_chip` +
  sortable columns. The lesson: I over-indexed on O27's *robustness* when the user
  had repeatedly said viperball's *design* was the target.
- **Distinct reference aesthetic vs. current chrome.** Both references run a distinct
  terminal look. I kept our FM `bl-*` chrome (consistency, no theme-engine rewrite)
  but added denser tables + KPI cards + the dropdown nav to get the SaaS feel. A
  dark/theme toggle (both references have one) is left as a follow-up.
- **Signing source: live world vs. web class.** The signed commitments live in the
  world sim (`world_signing`), a different pool from the cached recruiting board.
  I wired the tracker to the *real* commitments (one source of truth) rather than a
  projected board — at the cost that the page is empty until the season advances.
- **The nav rewrite is real chrome surgery.** Sidebar → top dropdowns touches every
  page. It renders clean in markup and all routes return 200, but it's the one change
  in this segment that genuinely wants an eyeball in a browser at a few widths.

## The rebase

`main` had moved on (team logos = ~1100 files, Bubble Watch, Bracket Projection).
Only `server.py` overlapped; `git rebase origin/main` replayed the 5 portal commits
and auto-merged it cleanly — main's Bracket Projection nav + team-logo filters and
the portal's Recruiting HQ / Signing Tracker now coexist. Force-pushed with lease;
the branch is linear, 5 ahead of main, 0 behind.

## Determinism & safety

Pure presentation: nothing here touches the engine or schema. The compute layer is
deterministic given the cached class; `world.signings()` is a read-only query. The
recruiting board (consensus ability) is untouched — only the new views read the
junior/points/signings data. 166 tests pass on the rebased branch.

## Handoff — what's left

- **Dark / theme toggle** (both references have one) and propagating the dense
  almanac styling to the remaining pages (recruiting board, teams, players).
- **A real `compute`/`export` round-trip** — the JSON feed is emit-only today; a
  loader that re-reads its own bundle (O27's portability contract) would make the
  almanac fully source-agnostic.
- **Recruiting *targets*** on the per-team page (top available prospects who fit),
  not just signed commits.
- **A genuine browser pass** on the dropdown-nav layout at desktop/tablet/phone
  widths — the one change that markup-level smoke tests can't fully vouch for.
