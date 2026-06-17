# AAR — Postseason visibility, clarity & season archives

A batch of read-it-at-a-glance fixes plus making past seasons durable.

## Conference-tournament rounds (results browser)
Each CT group read "Conference Tournament · 1 dual" — a meaningless count. It
now names the round (Final, Semifinals, Quarterfinals, Round of 16, …), derived
from the END of the bracket so it's right for any field size (one round plays
per week). The bare "N duals" microcopy was dropped from every results group.

## Real NCAA bracket — seeds + committee sheet
The played `/ncaa` bracket rendered every team with a blank seed slot. It now
labels each team with its seed, conference and bid (AQ/AL) — drawn from the
locked postseason field (`ncaa_field`, computed from that season's own stored
results, so it's historically accurate) — bolds the advancing winner, and adds a
"Top seeds" committee sheet beside the round columns. Same "N duals" clutter
removed here and on the simulator.

## Season archives (awards / bracket / championships)
All three already persisted per world-year but only the current season was
viewable. Added Season pickers that read the stored data:
- **Awards** — `/awards/archive` reconstructs a past season's winners (POTY,
  COTY incl. National Assistant, champions, All-Americans, All-Conference) from
  the stamped `honors`. Archived player names are plain text (a graduated winner
  no longer resolves on the live `/player` route — a frozen record shouldn't
  link to a 404); schools/coaches still link.
- **NCAA bracket** — `ncaa_bracket_view(year=…)` resolves a past season via its
  seed (`find_season`, no creation) and reconstructs it (seeds included).
- **Singles/doubles championships** — served from the `world_championship`
  snapshot for the chosen year.

## New-save isolation
`world.reset()` wiped world/season/honors/coaches but left editor overrides
behind, so a prior save's player moves and prestige tweaks lingered in Active
Overrides. It now also clears overrides + scholarship overrides and drops stored
championships, so each new league starts clean.

## Transfer portal — pagination + year filter
The portal dumped every transfer in one list. Added an Off-season (year)
dropdown and 40-per-page pagination (the pager preserves the division + year
filters across pages).

## Analytics Bureau — plain labels
Underplaced Talent / Scholarship Watch used cryptic headers (TRUE, NOW, TALENT
vs LEVEL, DESERVES A PROGRAM LIKE, MERITS). Renamed to short, plain labels
(TALENT, NOW, vs TEAM, FITS / BEATS, WEAKEST FUNDED, DESERVES) with a one-line
hover tooltip each, and removed the verbose footer paragraphs.

## Verification
Round labels walk Quarterfinals → Semifinals → Final; real bracket shows
#1 vs #64 with the Top-seeds panel; awards/bracket/championship archives render a
past year and a graduated winner shows as plain text (no `/player` link); a new
save reports zero overrides; all touched web suites pass.
