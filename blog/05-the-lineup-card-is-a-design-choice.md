# The Lineup Card Is a Design Choice
### Release 2.4: tearing up 6+3, and what a box score owes the player who produced it

Real college tennis plays six singles and three doubles because of things that have nothing to do with tennis. Courts are expensive. Title IX math shapes roster sizes. The 6+3 dual exists inside those constraints, and every college tennis sim I've ever seen inherits it without asking why. I inherited it too — for about two years. Then I was reading about college squash, which plays nine singles and no doubles at all, and the obvious question finally landed: *my game doesn't have courts. My game doesn't have compliance. Why is my lineup card cosplaying someone else's facilities budget?*

Release 2.4 is what happened after that question, plus a deep rebuild of how match statistics get made. It's the biggest version jump this project has had, so this post covers a lot of ground.

## Every division gets its own dual

The headline change: there is no universal format anymore. Each division plays its own shape.

| Division | Format | Doubles scoring | Points | Clinch |
|---|---|---|---|---|
| D1 | 10 singles + 5 doubles | consolidated — win 3 of 5 pairs for ONE point | 11 | 6 |
| D2 / D3 | 8 singles + 3 doubles | every line its own point | 11 | 6 |
| D4 | 10 singles + 3 doubles | every line its own point | 13 | 7 |

D1 keeps the consolidated doubles point on purpose. I mostly *like* what that rule does — it caps how much you can get out of doubles stacking. You can't load two ringers into one pair and buy points; you have to win three of five real matches across ten bodies for a single point. The point kept its leverage (it still decides about one D1 dual in ten) but the cheap route to it is gone. Everywhere else I went the other way: the 9-point construction most real non-D1 divisions actually use — D2, NAIA, JUCO all score doubles per line — scaled up to the bigger cards.

The design goal was depth as a competitive axis. A blue blood's scholarship economy can pay for roughly six pros — I deliberately did *not* resize the recruiting budgets — so under a 10-court card, courts seven through ten belong to walk-ons, portal finds, and player development. The paid core wins you the top of the card. The bottom you have to *build*.

Did it work? I ran the same season under both formats, same seed, and the numbers say yes, precisely where intended: the top five D1 teams dropped from a 93.3% win rate to 88.9% — roughly one extra loss per elite team per season — while the overall spread and upset rates barely moved. The change taxes the very top and leaves the middle alone. Meanwhile scorelines finally have texture. The old 7-point dual maxed out at 4-3. The first converted season produced a D4 women's national final that went 7-6 with the title decided by the last match off the court — and the winning margin was exactly the doubles edge. A 6-0 is now a rout across ten courts; a 6-5 went to the wire. The score finally tells you what kind of dual it was.

One conversion story I want on the record because it's my favorite kind of emergent honesty: existing saves converted mid-season, and a Duke roster that had been portal-stacked down to five elite players reached the national final on a card that needs ten. The engine doesn't crash and doesn't fake anyone — the shorthanded side just plays its last man on every court it can't fill, and the box score honestly listed the poor guy on six singles courts. They made the final anyway, which says something about how good five players can be, and the roster floor tops everyone up with real, persisted walk-ons at the next rollover. (Those walk-ons got an overhaul too — per-division talent bands, so a D1 walk-on is a recognizably different animal from a D3 one.)

## Every level is the pros of its own world

The other half of this release started with a bug report from my own box scores: a player who went 6-3 6-4 and hit *zero* winners. The same week, an S1 in the D1 final posted 47 winners against two unforced errors. Both numbers are impossible, and they were the same bug wearing two costumes.

The engine decides who wins each point, then labels how it ended — winner, forced error, unforced error. Those labels were anchored to an absolute talent reference sitting at "real D1 starter." Players far below the anchor had their winner share arithmetic collapse to literally 0%; elite players had their unforced-error share collapse instead. The stat sheet was applying a level tax.

The fix took me three tries to think about correctly, and the final frame is the one I now consider a design principle: **a winner is relative to the opponent.** A 35-rated shot that a 30-rated opponent can't reach is a winner, full stop. Pull up a Challenger box score and an ATP box score — they're statistically indistinguishable. 51/49 point splits, normal ace counts, ~30% of points ending in winners. The level difference only shows when the levels *meet*. So the attribution model is now level-blind and matchup-anchored: a matched D4 dual reads like a matched D1 dual, because D4 players are the pros of D4's world. Mismatches are where the gap appears — the favorite piles up winners and the underdog's losses tilt unforced.

I validated the whole thing against real data — Craig O'Shannessy's point-ending research (~30% winners / ~70% errors at every level), ATP and WTA match boxes, the works — and wrote the yardsticks into the repo so future me can't quietly drift. There's now a test that enforces *conservation*: every point in every match must be labeled exactly once, a player's points won must equal their winners plus the opponent's errors plus the opponent's double faults, and match totals must land in real ranges (~130 points for a best-of-three). Stat models deserve calibration targets the same as outcome models. Mine now has them in CI.

Two clarifications that came out of stress-testing this with real ATP/WTA tables. First, outcomes were never level-blind and still aren't — win probability rides entirely on attribute gaps, and the curve is properly nonlinear: a 10-point OVR gap wins about 88% of the time, a 20-point gap about 98%, and at 30 points I measured 150 matches without a single upset. A 60 playing a 30 loses only to injury. Second, none of the stats are conjured from level dials: aces read the server's actual first-serve power and variety against the returner's actual return quality, double faults read second-serve quality and composure (and go *up* with serve power — the real ace/double-fault coupling), winners read the weapons. My generated women serve softer in their attributes, and WTA-band serve stats fall out with zero tuning. That's the whole philosophy: the attributes carry the signal; the engine just refuses to override them.

## The rest of the release, briefly

**Match retirements.** Injuries can now end a match mid-play, scored the way tennis actually scores them: the retiring player loses the line *regardless of the score* — Murray d. Djokovic 6-4 3-0 RET is the canonical example — at about a handful per conference per season. And injury volume is calibrated per *team*, so the bigger cards didn't inflate it: expected injuries per dual are identical whether you field six bodies or twelve.

**The pro league grew up.** The co-ed pro league (where your graduates go) picked up the same injury system as college, real development arcs toward a peak instead of frozen ratings, era-rotating playing-style archetypes, coaches drawn from people who actually exist in your save, and a full movement economy — draft, roster locks, alumni tracking. It stopped being a scoreboard and started being a league.

**The offseason became a ladder.** Awards, the international cups, the year rollover, the pro offseason, preseason — each is now its own visible step instead of nine things detonating behind one button. Related: there is exactly one "advance" button in the whole game now, because I learned the hard way that two identical-looking buttons advancing different scopes will silently fork your universes into different weeks. That one cost me a save.

**Small honesty everywhere.** D3/D4 regular-season duals play every match to completion (the real ITA D3 "play-play" format) instead of abandoning dead rubbers, which feeds the portal boards real data on bench players. Box scores show the ITA order of finish. Doubles matches finally appear in player match logs. And the service academies roster US citizens only, through every pipeline — recruiting, portals, walk-ons, all of it — because Army fielding an international recruit was breaking my immersion every time I noticed it.

The throughline of the whole release, if there is one: constraints deserve interrogation, and numbers deserve receipts. 6+3 was someone else's constraint. The zero-winner box score was my own bad assumption with no test guarding it. Both are gone, and both left tests behind so they can't come back quietly.
