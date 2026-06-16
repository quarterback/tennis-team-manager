# AAR — Postseason visibility: results browser, real bracket, reveal phase

**Date:** 2026-06-16
**Scope:** The postseason was opaque — no way to see conference-tournament or
NCAA matchups, who won, or what round the season was on; the only "bracket" was
a projection sim; and the field jumped from conference tournaments into the
NCAAs with no moment to see who got in. This batch makes the postseason legible
end to end, plus two correctness fixes flagged in review.

## What shipped

### 1. Week-by-week Results browser (`/results`, World nav)
Pick a division + week and see every dual played that week — regular slate,
conference-tournament rounds, and NCAA rounds — grouped and labelled
("Big Ten Tournament", "Round of 16"), each with its score and the winner in
bold. The week selector tags each week with its phase, so the current round is
obvious. (`seasonmode.all_results` + `state.results_by_week`.)

### 2. Real (played) NCAA bracket (`/ncaa`, World → NCAA Bracket)
Reconstructs the actual tournament from results — rounds of real matchups
(winner bold, loser dimmed, dual score) and the champion. The `/bracket` page
stays the projection sim and now points to the real one in the nav instead of
burying a link on the sim page. (`state.ncaa_bracket_view`.)

### 3. Bracket Reveal (`selection`) phase
New phase between conference tournaments and the NCAAs. When the conference
tournaments crown champions, the season **pauses at the reveal**: the 64-team
field is locked (champions as AQ, the rest at-large by Power Index) and shown on
the NCAA Bracket page; advancing once starts the NCAAs (plays round 1).
- `seasonmode`: `_finish_conf_phase` parks at `selection`; `advance()`
  `selection` branch flips to `ncaa` and plays round 1; new `ncaa_field()`
  returns the locked field; `bracket_field` honours champions from `selection`
  on.
- `world_hub` stepper + topbar gained a **"Bracket Reveal"** stage; `world_hub`
  primary action becomes "Reveal complete — start NCAAs →".
- `ncaa_bracket_view` shows the locked field (seed · conf · AQ/AL) during the
  reveal, then the played rounds once they begin.
- **Who's in AND who's out:** `ncaa_field` also returns a snub board — the
  highest-Power-Index teams just outside the locked field — rendered as a
  "First Out" section (conf + record) beneath the field.

### 4. Bracket-page clarity + topbar
- Winner of each matchup now reads at a glance (loser dimmed, winner bold).
- Removed the distracting **upset** badge/styling and the Upsets metric — a
  lower seed winning isn't necessarily an upset — and later the **Top Seed**
  metric too (no editorialising, just results). Labelled the page a projection.
- Topbar now reflects the live stage across active universes (Conf tournaments /
  Bracket reveal / NCAA championship) instead of always "Regular season".

## Review fixes (codex, both P2)
- **Moved-player stats read from the wrong season.** `_record_world_history`
  recorded a moved player's destination school but read record/line/STR from the
  *source* season being iterated — wrong for cross-division editor moves, where
  the player actually plays in the destination season (0-0 / missing line). Now
  it precomputes each active universe's season data and reads a moved player's
  stats from their **destination** universe.
- **New caches not reset.** `_pline_cache` / `_plrec_cache` are keyed only by
  `(season_id, completed-dual count)`, so a New League reusing a season id could
  serve stale per-line records. Added both to the clears in `state.reset_all()`
  and `world.reset()`.

## Files
- `app/seasonmode.py` — `all_results`, `ncaa_field`, `player_line_records`
  caches; `selection` phase in `advance` / `_finish_conf_phase`; `bracket_field`
  champion window.
- `app/web/state.py` — `results_by_week`, `ncaa_bracket_view`, `_round_phase`;
  `world_hub` selection stage; cache clears.
- `app/web/server.py` — `/results`, `/ncaa` routes; World nav (Results, NCAA
  Bracket); `_active_nav`; topbar phase label.
- `app/world.py` — `_record_world_history` destination-season fix; reset clears.
- `app/web/templates/results.html` (new), `ncaa_bracket.html` (new),
  `bracket.html` (winner clarity, upset/metric removal, projection note).
- `app/web/static/css/bracket.css` — loser dimmed.
- `tests/test_world_single_gender.py` — allow `selection` stage.

## Tests
`test_world.py`, `test_world_single_gender.py`, `test_web_recruiting.py` pass
(15/15). The phase change is deterministic; finalize still triggers only on all
active seasons `complete`, and `selection` sits cleanly before `ncaa`.

## Follow-ups
- The projection `/bracket` page still shows no dual score per matchup (the
  Results browser and real `/ncaa` bracket do); thread the score through the sim
  `Matchup` if wanted.
