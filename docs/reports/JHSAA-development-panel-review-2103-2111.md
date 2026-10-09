# JHSAA Development Panel Review, 2103–2111

The new development panel is substantially more useful than the season snapshots for evaluating the player-development model. It contains **325,145 player-season transitions covering 133,683 players** from 2103→2104 through 2110→2111. Instead of inferring development from a few graduating classes, it lets us see the machinery operating year after year: current ability, ceiling, remaining room, exposure, coaching environment, early-development rolls, maturity, transfer, and the resulting annual gain.

The central finding is fairly strong:

> **The development model is producing persistent but highly unequal growth. Current ability matters, latent capacity matters separately, playing time matters only when there is capacity left to realize, coaching modifies the outcome without determining it, and rare early-development events create genuine outlier careers without turning the entire population into stars.**

The Lamont Schultze 29→100 career is not a one-off statistical curiosity. It is the extreme end of a distribution that has a coherent middle.

## The ordinary development curve is restrained

Across the entire panel, the median annual improvement is only **2 OVR**. That remains true at every age.

| Transition | Players | Mean gain | Median gain | 90th percentile |
|---|---:|---:|---:|---:|
| 7th → 8th | 3,372 | 3.11 | 2 | 10 |
| 8th → 9th | 6,126 | 3.23 | 2 | 10 |
| 9th → 10th | 105,951 | 3.77 | 2 | 10 |
| 10th → 11th | 105,402 | 3.25 | 2 | 9 |
| 11th → 12th | 104,294 | 3.07 | 2 | 9 |

That is important because the spectacular careers can make the system look much more explosive than it actually is.

Most players are moving a couple of points a year. Roughly 9–12% of player-seasons produce a gain of 10 or more. Twenty-point annual jumps are rare.

The model therefore does not behave like a universal upward escalator. It has a very ordinary center and a long right tail.

## Development is fundamentally constrained by headroom

The cleanest relationship in the panel is not age. It is the amount of ability a player still has available between current OVR and ceiling.

Exposure matters, but it matters differently depending on that remaining room.

For players with **20–29 OVR of headroom**, average annual gain rises from about:

- **3.2** with only 1–5 exposure units,
- **4.0** around 6–10,
- **4.6** around 11–15,
- **4.9** around 16–20,
- and about **5.3** around 21–30.

For players with only **0–4 points of headroom**, all of that extra playing time has nowhere to go. Their gains stay around 1½–2 points.

That is exactly the behavior the architecture should have.

Playing does not manufacture potential. It helps a player realize capacity that still exists.

This is one reason the model avoids a common simulation-game failure where simply starting 30 matches a year turns almost anybody into a star.

## Exposure is valuable, but raw match volume is not destiny

The unconditional numbers initially look slightly strange because the highest-exposure players are often already near their ceilings.

Across everybody:

| Exposure units | Mean annual gain |
|---|---:|
| 0 | 1.67 |
| 1–5 | 2.30 |
| 6–10 | 3.07 |
| 11–15 | 3.71 |
| 16–20 | 3.86 |
| 21–25 | 3.64 |
| 26–30 | 3.51 |
| 31–40 | 3.28 |

That drop after 20 does **not** mean playing more begins hurting development. It is selection: players receiving 25–35 units of exposure are disproportionately established varsity players who have already consumed much of their developmental headroom.

Once headroom is held roughly constant, the expected pattern returns: more exposure generally produces more realized development.

So the model is distinguishing:

**opportunity to develop** from **capacity to develop**.

Both are necessary.

## Coaching matters, but it does not dominate the player

The coaching development multiplier ranges roughly from **0.86 to 1.27** across the panel.

Among players who still have at least 10 OVR of headroom and receive between 6 and 25 exposure units, moving from the lowest quartile of coaching development environment to the highest changes mean annual gain from about:

**4.23 → 4.54 OVR.**

The median shifts from 2 to 3.

That is a modest effect, and I think that is desirable.

A great development coach helps. A weak development coach costs something. But the coach does not overwrite the player's ceiling, exposure history or stochastic events.

The coach is a multiplier on a career rather than the author of it.

## The complete six-year careers are the strongest validation

The panel contains **1,344 players with an uninterrupted five-transition record from seventh grade through senior year**.

Their median path is:

**25 OVR in seventh grade → 51 OVR as a senior.**

Median total gain: **+22**.

The tails are substantial:

- **27.2%** gain at least 30 OVR.
- **9.7%** gain at least 40.
- **1.8%** gain at least 50.
- The maximum observed gain is **+71**.

At graduation:

- **10.9%** finish at 80+ OVR.
- **4.6%** finish at 90+.

This is a much healthier distribution than either extreme alternative.

The system is not flat enough that seventh-grade ratings predetermine everything, but it is not loose enough that every weak middle-schooler has a plausible route to 95.

## Starting ability still matters enormously

The late-bloomer system does not erase the meaning of current ability.

Among the 1,344 complete six-year careers:

| 7th-grade OVR | Players | Median senior OVR | Median gain | Finish 80+ |
|---|---:|---:|---:|---:|
| 20 | 371 | 33 | +13 | 0.3% |
| 21–25 | 304 | 44 | +22 | 0.3% |
| 26–30 | 174 | 53 | +24 | 1.7% |
| 31–35 | 143 | 59 | +26 | 4.9% |
| 36–40 | 107 | 67 | +29 | 13.1% |
| 41–50 | 135 | 72 | +27 | 25.2% |
| 51–60 | 83 | 85 | +29 | 71.1% |
| 61–70 | 21 | 94 | +29 | 100% |

This makes Lamont Schultze much easier to understand.

A 20 OVR seventh-grader becoming a 90 is essentially absent from the population.

A 29 OVR player becoming elite is still exceedingly unusual, but it can happen if that 29 is sitting on much more latent capacity than the rating suggests and the right development events occur.

That is a very different system from random miracle growth.

## The most extreme six-year trajectories

The panel gives a better list than the earlier snapshot study because these are complete seventh-to-twelfth-grade records.

### Lamont Schultze — Granite Basin

**29 → 100, +71**

- Started with a 74 ceiling.
- Finished with a 100 ceiling.
- Early POT lift: **0.8958**.
- Stayed at Granite Basin.
- Accumulated 92 exposure units across the five transitions.

This remains the cleanest demonstration of the system.

### William Strickler — California Beach → McCrory

**20 → 86, +66**

This one may actually be more startling.

- Starting OVR: 20.
- Starting ceiling: **66**, already dramatically above his current ability.
- Final ceiling: 93.
- Early POT lift: .4676.
- Transferred once.
- 83 exposure units.

Unlike Schultze, this is a truly bottom-rating starting point. What makes the career plausible inside the model is that the 20 never represented a 20-quality future player. He was a badly under-realized 66-ceiling player before subsequent development raised that ceiling further.

### Kaliq Locke — Isla Verde

**31 → 95, +64**

- Starting ceiling: 64.
- Final ceiling: 95.
- Stayed at the same school.
- 118 exposure units.
- Early POT lift: .3253.

This remains one of the best examples because his early development is not dominated by the rare exception mechanism.

### Dustin Nguyen — Purcell Crossing

**29 → 92, +63**

- Starting ceiling: 53.
- Final ceiling: 95.
- Stayed.
- Early POT lift: .8643.

A major ceiling-reveal career.

### Myles Kraus — Sotkamo → Latgaway

**24 → 87, +63**

- Starting ceiling: 60.
- Final ceiling: 87.
- One transfer.
- 95 exposure units.

This is a useful development-plus-mobility case.

### Emma Shupe — Ridgeline

**26 → 84, +58**

- Starting ceiling: 51.
- Final ceiling: 85.
- Stayed.
- 100 exposure units.
- Early POT lift: .7009.

### Kaleb Secor — California Beach → Mesa Dorada

**35 → 92, +57**

- Started with an already substantial 84 ceiling.
- Finished with 99.
- One transfer.
- 103.5 exposure units.

### Emma King — Barley Gap → North Wind

**40 → 97, +57**

- Starting ceiling: 88.
- Final ceiling: 99.
- One transfer.
- 107.5 exposure units.

Her career reinforces the distinction between development and immediate success: moving schools can create the environment in which a high-capacity player keeps developing without guaranteeing instant results.

## The early-development rolls create separation without overwhelming the population

Among complete six-year players, career outcomes split noticeably by early roll history:

| Early-development history | Players | Median senior OVR | Median total gain |
|---|---:|---:|---:|
| Development only | 1,005 | 49 | +20 |
| Accelerator | 286 | 54 | +25.5 |
| Exception only | 39 | 54 | +30 |
| Accelerator + exception | 14 | **76.5** | **+37.5** |

Among the accelerator-plus-exception group, **21.4% finish at 90+**.

But the group contains only 14 of the 1,344 complete careers.

That is exactly why Schultze feels exceptional when he appears rather than routine.

The rare mechanics actually remain rare.

## Total early POT is strongly associated with the eventual career

Dividing the complete six-year cohort into quartiles by accumulated early POT produces a clean gradient.

| Early POT quartile | Median early POT | Median senior OVR | Median total gain |
|---|---:|---:|---:|
| Lowest | .119 | lower 40s | +15 |
| Q2 | .195 | — | +20 |
| Q3 | .281 | — | +25 |
| Highest | .450 | highest | **+30** |

The share finishing at 80+ rises from only **2.4% in the lowest quartile** to **20.5% in the highest**.

This is much stronger evidence for the early-development system than simply observing that early participants outperform other students.

We can see the dose-response relationship inside the population that actually participated early.

## Transfer does not appear to be generating the growth

Of the 1,344 complete six-year careers:

- **644 stayed at one school.**
- **700 transferred at least once.**

So **52.1% moved** at some point.

Yet their median total development is almost identical:

| | Stayed | Transferred |
|---|---:|---:|
| Median 7th OVR | 26 | 25 |
| Median senior OVR | 51.5 | 50 |
| Median gain | +21 | **+23** |
| Median exposure | 86.5 | 86 |
| Finish 80+ | **15.8%** | 6.3% |
| Finish 90+ | **6.8%** | 2.6% |

That reinforces the conclusion from the earlier study:

> **Transfer is mostly reallocating opportunity; it is not the underlying source of development.**

In fact, the elite tail is much more likely to stay.

Players who move gain just as many OVR points at the median, but far fewer become 80–100 OVR stars.

The likely reason is that many movers are exactly the players the portal is intended to help: useful developing players who are blocked rather than extraordinary talents around whom the original program will naturally organize.

## The panel also shows why a transfer can still matter

Across all 325,145 annual transitions, movers gain somewhat more during the transition year:

- same school: mean **3.32**
- changed schools: mean **3.94**

But movers also enter those transitions with much more unused capacity:

- same-school average headroom: **13.9**
- mover average headroom: **19.1**

And they had slightly less prior exposure.

So it would be wrong to conclude that transferring itself creates another half-point of development.

The better interpretation is that the transfer population contains more **unfinished players**.

That is exactly the population the transfer system was built to surface.

## The model is not suffering from runaway inflation

This is probably the most important system-level check.

Across the eight panel seasons, average annual gain remains in a narrow range:

- 2103→2104: **3.20**
- 2104→2105: **3.92**
- 2105→2106: **3.27**
- 2106→2107: **3.30**
- 2107→2108: **3.28**
- 2108→2109: **3.36**
- 2109→2110: **3.26**
- 2110→2111: **3.33**

There is no upward staircase where each subsequent generation develops faster simply because more systems have been layered into the simulation.

The population center is remarkably stable.

The spectacular individual stories are being generated from variance within a stable aggregate system.

That is what you want.

## What I think the model is actually simulating now

At this point the development model has five distinct things operating together:

**Current ability** determines what the kid can do now.

**Ceiling** determines how much player still exists to be realized.

**Exposure** controls how much of that capacity can be converted.

**Development environment** modifies the conversion rate.

**Development events** can reveal additional capacity, occasionally by a lot.

That architecture is why two superficially identical 25 OVR seventh-graders can have completely different careers without either result being arbitrary.

One may actually be a 40-ceiling player and graduate at 38.

Another might already have a 70 ceiling, play enough to realize it, hit an accelerator that pushes the ceiling into the 80s, and graduate as a State-level player.

The starting OVR did not contain that information, because it was never intended to.

## Association judgment

I would not retune the general development engine.

The panel answers several questions that were previously uncertain:

- Ordinary annual development remains modest.
- Exposure has the intended effect when headroom exists.
- Ceiling meaningfully constrains growth.
- Coaching affects development without overpowering player variance.
- The early-development system produces a measurable dose-response.
- Rare rolls remain genuinely rare.
- Very weak players overwhelmingly remain weak-to-average rather than randomly becoming elite.
- Transfers are not manufacturing stars.
- Six-year participation can produce dramatic late bloomers.
- Aggregate development has remained stable across eight seasons.

The model's most convincing result is no longer merely that **Lamont Schultze went from 29 to 100**.

It is that the same system produced **1,343 other six-year careers around him**, most of which were ordinary, some of which were very good, a small number of which were extraordinary, and almost none of which violated the information embedded in the player's starting capacity.

That makes Schultze look less like a bug and more like the intended extreme tail of a working development model.
