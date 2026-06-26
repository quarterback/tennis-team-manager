# Your Program Doesn't Have 8 Scholarships
### Recruiting as a budget you spend, not a headcount you fill

Here is a sentence that quietly runs most college-sports games: every program has the same number of scholarships. It's clean, it's fair, it's how the rulebook reads, and it produces a completely fake world. Because if everyone has eight scholarships and a scholarship is a scholarship, then the only thing separating Texas from a directional state school is which recruits happen to pick them — and in a sim, "happen to" is doing a galaxy of work it can't actually support.

The real world isn't a headcount. It's a budget. The gap between the top of a sport and the middle isn't *how many* players you can fund, it's *what you can put on the table* for the ones you want. So I tore out the flat-count model and replaced it with an economy.

Every program gets a **recruiting budget** — call it scholarship-equivalency, a pool of spending power — and the size of that pool is set by where the program sits: its conference tier, nudged by its own (now dynamic) prestige. Blue-bloods get a wide, deep band. Low-majors get a thin one, barely above the floor. And recruits **cost** out of that pool, by star, on a deliberately steep curve:

| Tier | Cost |
|---|---|
| Blue Chip | 7 |
| 5★ | 3.5 |
| 4★ | 3 |
| 3★ | 2 |
| 2★ | 1 |
| 1★ | free |

That curve is the whole design. A blue-chip costs more than two five-stars. It is a *real* investment, and only a program with a genuinely deep budget can stack them. The first version of this curve was too shallow and I watched a mid-major casually assemble six five-stars, which is insane, which is exactly the flat-count world wearing an economy's clothes. Steepening it fixed it instantly: now the premium talent piles up only where the money actually is, and it piles up *because the cost table makes it pile up*. Talent distribution stopped being something I tuned and became something the economy produces on its own.

There's a second gate on top of cost, and it's the one that makes it feel real: a **floor** you have to clear just to *attract* a tier, separate from whether you can afford it. A blue-chip won't sign with you unless your budget clears a high bar — blue-blood territory. Five-stars need a major-conference budget. Four-stars will go anywhere that's genuinely funded. So a thin program can't just save up and splurge on one blue-chip; the blue-chip won't take the visit. Clustering is *earned*, not bought in a fire sale. Blue-bloods land blue-chips, majors top out at a five-star core, mid- and low-majors build around fours and threes, and that hierarchy falls out of two small tables instead of a single hard-coded "good team" flag.

The detail I'm fondest of is at the bottom of the map, not the top. Most non-scholarship programs get nothing — but the handful of academic-elite ones get a thin "gem" allowance, just enough to outbid their peers for one undervalued player. It means a Swarthmore can win a recruit on something other than money exactly once a cycle, which is precisely how those schools actually compete. They don't outspend anyone. They sop up the one kid who values the classroom more than the offer sheet.

I'll admit the part that took me longest to stop tripping over: there's still an "8" in the code, and it's a trap. It's a totally separate, downstream **display** layer — how the aid gets packaged into full rides and partials for the recruits a program already signed. It has nothing to do with spending power, and twice I "fixed" the budget by confusing it with the display number, and twice I had to back it out. The roster quality comes from the budget. The "8" is just the receipt.

The result is a recruiting board that finally feels like a market. The blue-bloods hoard the blue-chips because they can pay, the middle class builds smart around what it can reach, and once in a while a tiny program with a fat overachievement streak suddenly has the budget to take a swing it couldn't have taken three years ago. Nobody handed it eight scholarships. It earned a bigger checkbook.
