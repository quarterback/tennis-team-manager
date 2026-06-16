# AAR — Player career history, player search, Bureau profile links

**Date:** 2026-06-15
**Scope:** Three player-facing additions requested in one pass, modelled on
sports-reference / ESPN / college-tennis pages: (1) a year-by-year college
career on the player card showing the team played for each season (transfers
visible) plus position and record; (2) a global player search (the biggest
missing surface); (3) Analytics Bureau players linking to their player profile.

## 1 — Year-by-year career history

### Why
Player cards only showed the current season. There was no way to see where a
player played year over year — crucial for the college game (transfers) and for
the pro league later (players change teams). The reference examples show a
season row per year with the team, class, position (1–6 singles / 1–3 doubles)
and record.

### What it does
The world's year-end rollover now **stamps each player's finished season onto
their career history** before graduation/portal move them, so the record
persists with the player (and will follow them into the pro league):

- `world._record_world_history(seed, world, rosters)` — called in
  `_finalize_year` right after `developed_rosters`, before `finalize_rollover`.
  Appends `{year, season_no, division, gender, school, class, line, w, l, str}`
  per rostered player. `class`/`school` are the season actually played; a school
  change between entries is a transfer. Idempotent per year.
- `seasonmode.player_primary_lines(sid)` — one-pass modal singles slot per pid
  (the lineup position they played most), cached by completed-dual count.
- `state.player_career_table(division, gender, pid)` — recorded history (past
  seasons) + the in-progress current season added **live** (from the live
  season) so the card is current before the year closes. Newest first, with the
  team crest.

The player card renders a **"Career — by season"** table: Season · Team · Class
· Position · Record · STR. Awards stay in the existing **Career Honors** section
(the user's "separate awards section"). Position shows the raw slot (`S2`/`D1`).

### Forward-looking, by design
Existing saves accrue history from the next finalized year onward (the world
never recorded it before — only the standalone `league.py` did). The live
current-season row means the card is useful immediately regardless.

## 2 — Player search

`state.search_players(query)` matches a case-insensitive name substring across
the **active** universes: rostered players (→ their profile, with the player's
own division+gender) and the current recruiting class (→ the recruit page). It
reuses the cached `seasonmode._pid_index`, so it's cheap once rosters are primed
(and only touches active universes, never dormant ones). Surfaced as:

- a `/search` results page (Players + Recruits sections), and
- a **topbar search box** in `base.html` (hidden under 900px).

## 3 — Bureau → player profile

The Analytics Bureau (HQ previews, Underplaced Talent, Scholarship Watch)
previously linked player names only to the Fit Finder. Names now link to the
**player profile** (`/player`) carrying the player's own division+gender; a
compact `fit ↗` link keeps the Fit Finder one click away, and the Fit Finder
page links back to the profile.

## Files
- `app/seasonmode.py` — `player_primary_lines`.
- `app/world.py` — `_record_world_history` + call in `_finalize_year`.
- `app/web/state.py` — `player_career_table`, `_pos_label`, `search_players`.
- `app/web/server.py` — `/search` route; player route passes `career_table` +
  `gender`; imports.
- `app/web/templates/` — `player.html` (career table), `search.html` (new),
  `base.html` (search box), `intel_hub/underplaced/scholarships/fit.html`
  (profile links + fit link).
- CSS — `shell.css` (`.fm-search`), `recruit.css` (`.ib-fit`).

## Verified
- Career table renders with a live current-season row (e.g. `2026 · Michigan ·
  S2 · 4-3 · STR 48.7`); world + single-gender tests pass 9/9, history recording
  is deterministic.
- Search returns players across divisions (e.g. "Mattord" → a D3 and a D1
  player), `/search` 200, topbar box present.
- Bureau pages link names to `/player/...` with the Fit link retained.

## Follow-ups
- Doubles line/record per season isn't tracked yet (only the modal singles
  slot); the reference pages show 1–3 doubles too — add when doubles results are
  surfaced per player.
- Search covers active universes only (consistent with the world model); a
  dormant-universe toggle could be added if single-gender saves want to browse
  the inactive side.
- Once the pro league activates, the same `history` list should keep appending
  pro seasons so a career spans college → pro on one timeline.
