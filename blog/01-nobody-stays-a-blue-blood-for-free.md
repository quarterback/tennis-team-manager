# Nobody Stays a Blue Blood for Free
### Making program prestige something you re-earn every season

For most of this sim's life, prestige was a birthright. A program got a number — part conference, part a hand-tuned bump for the blue-bloods — and it carried that number forever. Texas was Texas in year one and Texas in year forty, no matter what happened on the court. Which is fine, until you actually sit down and play a few seasons and watch a tiny program go 28-2, make a deep run, and get *nothing* for it. The world remembered them exactly as well as it did before they were good.

That's the bug that isn't a bug. It's the thing a static rating *can't* model: the lag between being good and being known for it. Gonzaga didn't get to recruit like Gonzaga until Gonzaga had spent a decade making everyone uncomfortable in March. Reputation trails results, and then — once it catches up — it becomes self-fulfilling, because the recruits follow it.

So I made prestige drift.

The rule I landed on is "overperformance versus expectation," and the word that's doing the work there is *expectation*. Every offseason, each program gets scored two ways. First, where it actually finished — its Power Index percentile in the division, plus a small bump for the postseason stuff that a raw rating undersells (making the field, reaching the Final Four, winning it all). Second, where its **current prestige** said it should finish. The gap between those two is the whole engine:

```
momentum ← clamp( 0.85·momentum + 0.10·(result − expectation),  ±0.20 )
```

Beat your own bar, you climb. Fall short of it, you slide. The momentum is a signed delta that gets added on top of the base prestige and persists season to season, so it compounds.

The reason I keyed it on *expectation* instead of raw results is that raw results snowball. If the strong just get stronger for being strong, you end up with the same eight programs forever and a sim that's decided before it starts — the exact failure mode I'd just spent a month fixing on the baseball side, where an engine that can't forget who's good is an engine you can't lose to. Tying the gain to expectation makes it self-correcting: the moment a low-major climbs, its *bar climbs with it*, so it only keeps rising if it keeps overachieving the new, higher standard. A blue-blood coasting on reputation but finishing 9th is, by definition, underperforming its expectation, and it bleeds prestige until the number matches the results.

The decay term (`0.85`) is the part I like most. It quietly pulls everyone back toward their baseline a little every year, which means a single Cinderella run doesn't permanently rewrite a program. You overachieve once, you get a bump; you go back to being mediocre, the bump melts. You have to *sustain* it to bank it. That felt true to how this actually works — one magic season makes you a story, five make you a brand.

The payoff is that prestige now feeds the thing that matters, which is recruiting budget. (More on that economy in another post.) A program that climbs a prestige tier starts recruiting a tier up, lands better players, and gets genuinely better — but slowly, through the recruiting pipeline, not as an instant rating bump. I deliberately left a program's *on-court* baseline tracking its conference, so prestige can't teleport a roster from bad to good. It just changes who's willing to come play for you. The wins still have to be earned with the players you can now attract.

I let it run aggressive — the cap is wide enough that a program can move a couple of tiers over a long enough arc. A dynasty can build, a blue-blood can genuinely fall out of the penthouse. When I first watched a save roll forward, the biggest climber was a Southland school that finished first in the division while sitting in the 29th percentile of prestige — a +0.78 gap, the engine screaming *these people are way better than you have them.* And the biggest faller was a name-brand academic program that finished near the bottom and got quietly demoted by the math. Both of those felt like the right outcome, and neither was something I typed in by hand. The system did it because the results told it to.

It's also, finally, *legible*. The data hub shows each program's prestige as a journey now — base → current, with the tier move spelled out, so you can scrub a few years in and watch the hierarchy actually breathe. The blue-bloods are mostly still on top, because mostly they keep winning. But the door's open now. You just have to keep kicking it.
