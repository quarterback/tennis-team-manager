# Developer Notes — 6.26.26
### A stretch of work that mostly came down to one idea: stop hard-coding who's good

I went into this stretch on the tennis sim with a grab bag of nagging to-do items and came out of it having quietly rewritten the same belief in four different places. The belief is this: in a sim, the worst thing you can do is *tell the engine who the good teams are.* The minute you hard-code the hierarchy, you're playing against a computer that already knows the ending. Every big change below is some version of taking a number I used to type in by hand and making the world earn it instead.

The four meaty ones each got their own write-up, so here I'll keep it to the elevator version and let the deep dives do the talking.

**Prestige stopped being permanent.** Program prestige used to be a static birthright — you were a blue-blood forever, a low-major forever. Now it drifts every offseason based on how a program performs *against its own expectation*, so a small school that keeps overachieving climbs the ladder and a coasting name brand slides down it. It's self-correcting (the bar rises as you rise) and it feeds recruiting, so the climb is real but slow. Full write-up: *Nobody Stays a Blue Blood for Free.*

**The selection committee became four numbers.** I needed the sim to build a national field, so instead of faking a smoke-filled room I wrote down what the room is for. Selection, seeding, and bracketing are three different questions and I refuse to cross them; the seed itself is a transparent blend of strength, résumé, a tiered championship bonus, and recent form. The fun side effect is that a left-out at-large can carry a higher score than a champion seeded inside the field, and that's *correct.* Full write-up: *The Committee Is Just Four Numbers.*

**Recruiting became a budget.** Programs no longer carry a flat scholarship count. They carry a *budget* set by their tier, and recruits *cost* out of it on a steep curve, with floors you have to clear just to attract the top tiers. Talent now clusters at the rich programs because the cost table makes it cluster, not because I flagged anyone as good. Full write-up: *Your Program Doesn't Have 8 Scholarships.*

**The bracket grew regions.** The 96-team top-division field now splits into four S-curve regions that are balanced by strength to the *exact* point total, with byes, a regional play-in, and region champions meeting in the semis. I went basketball-style regions over tennis host-site pods on purpose — pods make your draw about which group you landed in, regions make it about your seed. Full write-up: *Four Regions, No Pods.*

---

The smaller stuff that filled out the rest of the list:

**A lineup lab.** I'd been staring at one UTR chart for weeks — the strip plot that shows every team's singles ladder across a conference, a dot per player per lineup spot. So I stole it. Now you can pick any conference and see all of it at once: where the depth is, where a given rating would slot in on every roster instead of just one, and a side ranking of which leagues are actually strong versus which ones just have a good name. It's the view I always wanted when I was trying to figure out where a player belongs.

**The prestige journey, made visible.** Once prestige started moving, I needed to *see* it move, so the data hub now lists every program with its prestige as a base → current journey and the tier change spelled out. Sim a few years forward and you can watch a mid-major physically climb out of its tier, which is the whole point of having built the thing.

**Regional champions, and a medal ladder.** Winning your region — the Elite Eight, which is really the regional final — now shows up in a program's history as a "Regional Champion" banner, with the division attached. And I cleaned up how deep runs read across the board: R96, R64, R32, Sweet 16, the Elite Eight, then a bronze for the Final Four, silver for the runner-up, and a trophy for the title. Small thing. Reads so much better.

**A bug that was really a lesson.** I found two places where the bracket quietly lied. The "reveal" page was seeding the field by one metric while the *actual draw* used another, so the labels disagreed with the matchups that were scheduled — exactly the kind of thing that erodes trust in a sim without ever throwing an error. And teams with no résumé were getting ranked against each other by, of all things, dictionary insertion order, which handed identical teams wildly different scores for no reason. Both come back to the same rule the committee taught me: if three processes are supposed to agree, *make them agree,* and never let arbitrary order stand in for a real signal.

None of this is flashy on its own. But strung together it's the sim getting a little harder to predict and a little more honest about why things happen — which, for a game whose entire job is to surprise me, is the only direction worth shipping in.
