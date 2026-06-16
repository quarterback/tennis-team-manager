# AAR — Career record boxes (per-line W-L), singles + doubles

**Date:** 2026-06-15
**Scope:** Add the college-tennis "career record" boxes to the player card — the
format the user shared from Stanford/Michigan/etc.: per lineup-line W-L by
season for singles (lines 1–6) and doubles (1–3), each with **Overall**, **Dual**,
and a **TOTALS** row. No opponent-level logging (the user confirmed match-by-match
detail isn't needed for this sim).

## Why
The player card showed only a current-season match log. The user wanted the
canonical career box: how a player performed *at each lineup position* across
their career — the only college stats that matter here besides team
accomplishments (which already live in the Career Honors section).

## What shipped
Two tables on the player card:
- **Career Singles Record**: `Year · 1 · 2 · 3 · 4 · 5 · 6 · Overall · Dual` + TOTALS.
- **Career Doubles Record**: `Year · 1 · 2 · 3 · Overall · Dual` + TOTALS.

Each cell is the W-L at that line for that season. The "Career — by season"
team/transfer table (team per year, class, STR) sits above the boxes, and the
detailed match-by-match log sits below them in a **collapsed, expandable panel**
(see correction note). All three coexist.

## Correction: the match log was kept, not removed
The first pass *replaced* the opponent-level "Singles — by season" match log with
the record boxes, on the read that "I don't need match-by-match" meant "remove
it." The user actually meant "deprioritize it," and intercepted before deploying.
Resolved by showing it **both ways**: the record boxes (summary) plus the full
match-by-match log restored inside a collapsed `<details>` panel (`.pl-matchlog`,
max-height + scroll) so it expands on demand and doesn't dominate the page.
Lesson recorded: treat "I don't need X" as deprioritize/tuck-away, not delete,
unless stated explicitly.

## The blocker, and the fix
Singles lines already serialized the player's **pid + slot**, so the singles box
was buildable from existing data. **Doubles lines stored only player names, "no
pid"** (`season._line_identity`) — so doubles results couldn't be tied to a
player. The doubles branch already had the player objects in hand (it built the
name string from them), so the fix was a one-line addition: also emit
`home_pids` / `away_pids` on each doubles line.

## Data flow
- `season.py _line_identity` — doubles lines now carry `home_pids`/`away_pids`.
- `seasonmode.player_line_records(sid)` — one pass over completed dual lines →
  `{pid: {'singles': {n:[w,l]}, 'doubles': {n:[w,l]}}}`, cached by completed-dual
  count (mirrors `player_records` / `player_primary_lines`).
- `world._record_world_history` — at year-end (before graduate/portal) stamps
  each player's per-line records (`singles_lines` / `doubles_lines`) onto their
  history alongside the team/transfer line already recorded, so it persists
  through transfers and into the pro league.
- `state.player_career_records(division, gender, pid)` — builds both boxes from
  recorded history (past seasons) + the in-progress current season (live, from
  `player_line_records`), with per-year rows, Overall, Dual, and a TOTALS row.
  Academic-year labels (`2025-26`).
- `player.html` renders the two boxes (`.rc-recbox`, brand-header grid); the
  opponent-level log is gone.

## Overall vs Dual
Every match in the sim is a **team dual** (regular + conference + NCAA), so there
are no individual (fall/ITA) tournament matches feeding non-dual results —
**Dual == Overall**. Both columns are present to match the box and will diverge
automatically if individual events are ever tracked per player.

## Forward-looking caveat
- **Singles** boxes fill immediately (singles always carried pid + slot).
- **Doubles** records accrue only from matches played **after** this change
  (doubles pids weren't serialized before). The current in-progress season's
  doubles start filling on the next advance; full doubles history builds from
  next season onward — consistent with the year-end history-recording model.

## Files
- `app/season.py` — doubles `home_pids`/`away_pids`.
- `app/seasonmode.py` — `player_line_records`.
- `app/world.py` — `_record_world_history` stores `singles_lines`/`doubles_lines`.
- `app/web/state.py` — `player_career_records`, `_acad_year`.
- `app/web/server.py` — player route passes `records`; import.
- `app/web/templates/player.html` — two record boxes + the match-by-match log
  kept below them in a collapsed `<details>` panel.
- `app/web/static/css/recruit.css` — `.rc-recbox`, `.pl-matchlog`.

## Tests
`test_world.py`, `test_world_single_gender.py`, `test_web_recruiting.py` pass
(15/15). The dual-serialization addition and per-line history recording are
deterministic (sim results unchanged — only extra fields serialized).

## Follow-ups
- Per-line records are dual-based; if individual singles/doubles championships
  are ever tracked per player, fold them in to make Overall > Dual and add a
  Tourn. column (as the Michigan box has).
- A career row could also surface the player's primary line as a quick "career
  high" line, and the boxes could collapse to a single combined view on mobile.
