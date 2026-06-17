# AAR — Postseason record, bracket-seed persistence, performance-based awards

Three fixes from one play session, all around "the season's results should be
reflected honestly."

## 1. Postseason counts toward the season record

**Before:** `team_schedule` queried `round='REG'` only, and `team_results`
(the displayed season record) was computed from that schedule. So conference
tournament and NCAA matches appeared *nowhere* on a team's schedule and counted
toward *nothing* — unlike real college tennis, where all postseason games are
part of the season record.

**After:** `team_schedule` returns the full slate (REG + CT + NCAA), week-ordered.
`team_results` therefore counts all of it. The schedule page labels postseason
rows ("Conf Tourney" / the NCAA round name), the team-page header shows the full
W-L, and the results list tags CT/NCAA games. Verified: a champion's schedule
reads 21 REG + 2 CT + 6 NCAA and the record includes them (e.g. 22-7).

## 2. Bracket lost its seeds once the season ended

**Before:** `ncaa_field` derived the conference champions by parsing
`season.champion` as JSON. That field holds the conf-champion map only during the
selection window — at NCAA completion it's **overwritten with the national
champion's name** (a plain string). So once the season finished, `json.loads`
threw; the bracket view's `try/except` swallowed it and the per-team **seeds and
the Top-seeds panel silently disappeared**. (Mid-tournament it rendered fine,
which is what made the bug look intermittent.)

**After:** `ncaa_field` derives conference champions from the **CT results**
(`conf_champions(sid)` — the reliable source) instead of the repurposed field, so
seeds persist on the completed bracket. Verified: a finished bracket shows the
champion's seed, a #1-vs-#64 opening round, and the full Top-seeds sheet.

## 3. Awards were talent-based, not performance-based

**Before:** `_eligible` ranked players by `(STR, wins)` — STR (the rating) first.
A higher-rated player with a worse record outranked a big winner, so
All-American / All-Conference / Player of the Year (national + conference) read as
a talent ranking, not who actually performed.

**After:** `_eligible` ranks by an on-court score:

    singles wins  ×  win%  ×  lineup-position weight  ×  team factor

- **Position weight** (`_POS_W`, 1.00 at line 1 → 0.75 at line 6): a
  top-of-lineup win is worth more than a sixth-singles one. Position ≈ each
  player's STR rank on their own team (how lineups are actually set).
- **Team factor** (`0.85 + 0.30 × team win%`, a ±15% nudge): team success is *a
  factor, not a gate* — a standout on a weak team still earns recognition
  (an 18-0 player on a .500 team still ranked 4th nationally), while a winning
  team's player gets a small bump.
- **STR** is only a deep tiebreaker.

POTY and Conference POTY come off the top of this same list, so they're fixed by
the same change. Coach awards were already results-based (Coach of the Year =
top-PI team's head coach; National Assistant COTY = most bottom-lineup wins), so
they were left as-is. Awards-page copy updated from "by Power Index STR" to the
record-based description.

National POTY went from the top-STR 12-3 player to Henry Hutson (20-2) — the
top performer — confirming the shift.

## Files
- `app/seasonmode.py` — `team_schedule` (full slate); `ncaa_field` (champions
  from CT results, not the `champion` field).
- `app/web/state.py` — `team_results` carries `round`/`postseason` per result.
- `app/web/awards.py` — `_eligible` performance score (`_POS_W`, team factor).
- Templates — `season_schedule.html` (postseason labels), `teams.html` (full
  record + CT/NCAA tags), `awards.html` (copy).
- Tests — `test_web_awards.py` updated to assert performance ordering.
