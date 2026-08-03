# Release 2.4
### Per-division dual formats, full-fidelity outcomes, and a rebuilt stat model

Release 2.4 covers everything merged between tags 2.1 and 2.4. The changes group into seven areas.

## Per-division dual formats

The universal 6 singles + 3 doubles dual is gone. Real college tennis plays 6+3 because of court counts and Title IX roster constraints, neither of which applies to this game. College squash, which fields nine singles and no doubles, prompted the reconsideration. Each division now plays its own format:

| Division | Format | Doubles scoring | Points | Clinch |
|---|---|---|---|---|
| D1 | 10 singles + 5 doubles | consolidated: win 3 of 5 pairs for one point | 11 | 6 |
| D2 / D3 | 8 singles + 3 doubles | each line is one point | 11 | 6 |
| D4 | 10 singles + 3 doubles | each line is one point | 13 | 7 |

D1 keeps the consolidated doubles point because it limits doubles stacking: one point requires winning three of five pairs across ten players. The per-line scoring in the other divisions is the system most real non-D1 divisions (D2, NAIA, JUCO) use.

The recruiting and scholarship economy was not resized. A D1 scholarship core covers about six players, so courts seven through ten come from walk-ons, the portal, and development. Roster floors now equal each division's card size, enforced at the year rollover with generated walk-ons drawn from per-division talent bands.

Measured effects, same season simulated under both formats with the same seed: the top five D1 teams' win rate moved from 93.3% to 88.9%; overall win-percentage spread and upset rates were unchanged within noise; the consolidated doubles point decides 10% of D1 duals (12.2% under the old format); doubles decides 18.5% of D2 duals (14.6% under the old format).

Existing saves convert without migration. Stored duals keep their recorded box scores; new duals play the new formats. A converted roster below its card size plays its last player on the courts it cannot fill until the next rollover fills the roster to the floor. In the first converted season this occurred in a national final: a five-player roster reached it with one player recorded on six singles courts.

## Outcomes decided by the full point engine

Match outcomes are now decided by the per-point engine at full fidelity by default. Previously the fast game-level model decided outcomes and the point engine only reconstructed statistics afterward. The fast model remains available as a speed option on the world hub.

Engine players now carry all 49 graded attributes instead of nine averaged drivers. Each probability in the point engine reads specific attributes: aces read first-serve power and serve variety against the returner's return quality and depth; first-serve percentage reads first-serve accuracy; double faults read second-serve quality and composure, and increase with the server's first-serve power; rally outcomes read groundstrokes, movement, and consistency; conditions read each player's wind, heat, indoor, and crowd tolerances.

Box scores gained a forced-error category, calibrated against charted NCAA data. Player generation gained playing-style profiles: attributes shift in coherent groups with overall rating held constant, which produces genuine doubles specialists. About a third of programs field a doubles player outside their singles top six. The box-stat and attribute work is described in detail in the 2026-07-24 developer notes; 2.4 is the release where that engine became the default decider.

## Point-ending attribution

How points are labeled (winner, forced error, unforced error) was rebuilt three times in this release. The starting problem: deep-lineup players posted completed matches with zero winners, and an elite player posted 47 winners against 2 unforced errors. Both came from anchoring the label shares to an absolute talent reference; players far from the anchor saturated the clamps in opposite directions.

The final model is symmetric and matchup-anchored. Every rally end is a three-way split — the point-winner's winner, or the loser's forced or unforced error, on either side — driven by the gap between the hitter's attacking attributes and the misser's defensive attributes. There is no absolute-level term. Matched pairings produce the same statistical mix at every level: measured 31.7% / 30.0% / 28.5% winners for matched elite, mid, and weak pairings. This matches the reference data: winner/error mixes are approximately 32/41/27 for pro men and 29/37/34 for pro women, and Challenger box scores are statistically indistinguishable from ATP box scores.

Outcome probabilities were not changed by any of this and remain attribute-difference-driven. Measured win rates by overall-rating gap on rostered players: 10 points, 87–89%; 20 points, 98–100%; 30 or more points, 100% across 150 matches per cell.

Three invariants are now enforced by tests: every point is labeled exactly once (a player's points won equals their winners plus the opponent's errors and double faults); matched mixes stay level-blind; mismatches show the gap. The real-world reference data used for calibration is logged in the repo.

## Injuries and retirements

The pro league now uses the same injury system as college: shared dice and store, per-league tables, durability-scaled rates. Previously it had no injuries.

Matches can end in retirement. A retirement follows an injury, occurs at 0.2% per completed singles match, and costs the retiring player the line regardless of the score, with dual points corrected when that flips a line. Injury state is wiped when a new save is created.

Injury volume is calibrated per team rather than per player on court: rolls scale by the number of competitors in the dual, so the expanded cards produce the same expected injuries per team per dual as the six-court game did. Retirement rolls scale the same way.

## Pro league

The pro league gained: player development toward a peak (ratings previously did not change after graduation), playing-style archetypes drawn from real tennis eras and weighted for the league's format, club coaches who shape their players' styles, coaches drawn from people who exist in the save, and a movement economy with a draft surplus, roster locks, and alumni tracking. A 500 error on the player page for free agents without a club was fixed.

## World structure

Every active division and gender universe advances together on one world clock. The Season Hub's separate advance button was removed; `POST /world/advance` is the only advance route, enforced by a test. Separate advance paths had allowed universes in one save to reach different weeks.

The offseason is a sequence of visible steps — awards, the international cups, the year rollover, the pro-league offseason, preseason — each advanced by one click. The cups and the pro offseason were previously interior steps of the rollover and could not be observed or run separately. Three regressions from this change were found and fixed in the same release.

## Rules and data integrity

- Service academies (Army, Navy, Air Force, Coast Guard, Merchant Marine) roster US citizens only, enforced through every player-placement path: base rosters, recruiting, all portals, walk-on fill, coach moves, and pro free agents. The Citadel and VMI are state institutions and are not gated.
- D3/D4 regular-season and ITA duals play every singles match to completion (the ITA D3 format). The clinch still decides the winner; the remaining matches fill in the margin and give players completed matches on record. Postseason duals in all divisions keep clinch play.
- Box scores show the ITA order of finish.
- Player match logs include doubles matches, with the partner and opposing pair listed. Previously the logs covered singles only.
- The fall-portal slate enforces one move per player at the write layer, and a bug producing duplicate portal move rows was fixed.
- New saves restart the international cups and pro leagues instead of carrying them over from a previous world.
- The top navigation bar renders correctly at laptop widths.
