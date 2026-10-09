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

---

## Addendum — Coaching calibration and the staff-dividend proposal (2026-10-09)

**Historical proposal note:** The attribute-level developmental-capacity addendum below supersedes the generic additive-dividend recommendation in this section. Its synthetic figures did not test attribute-specific coaching.


**Status: proposal and synthetic sensitivity tests only; not implemented.**

The 2103–2111 development panel supports the career model but **does not validate coaching calibration**. Among players with at least 10 headroom and 6–25 exposure units, the mean annual gain was **4.23 OVR** in the bottom coaching quartile versus **4.54** in the top, a difference of **0.31 (7.3%)**. This is an association, not a controlled comparison of the same players. The earlier 2094–2104 coaching study likewise found stronger roster-level effects from Program builder and Feeder ties than from Development. Keep intrinsic development unchanged, but specifically test the intended coaching effect.

### What exists, and what is missing

In app/jhsaa_coaches.py, **DEV_K=0.40** and the named-staff multiplier is **1 + DEV_K × (effective Development quantile − 0.5)**. The head supplies the baseline; assistants supply only **40% of the positive gap to the single best assistant**. Other assistants do not independently add value. In app/jhsaa.py, this multiplier scales an archived season's intrinsic growth capacity, subject to exposure and the player's true peak.

A school's **coaching archetype** is separate from its named staff. The coaching-tag mechanism uses COACHING_MATURE and CAREER_COACH_K, and can generate a **1.08–2.20×** multiplier independent of DEV_K. Future Value and Program Interest are other staff effects that influence lineup selection and therefore indirectly influence growth through playing time, rather than granting OVR themselves. Evaluate each layer separately and test whether the archetype and named-staff effects accidentally compound.

The college model's interest_rate is not the JHSAA mechanism. The relevant JHSAA intrinsic characteristic is each player's pre-generated annual development capacity. Here **“irrespective of interest rate” means a coaching opportunity that does not merely multiply that player's intrinsic annual gain**. It must still respect unused true career capacity.

### Three approaches to test

| Approach | Mechanism | Judgment |
|---|---|---|
| **Curved DEV_K** | Make the existing staff multiplier nonlinear, with lower current-OVR and work-ethic eligibility. | Smallest change, but still scales intrinsic growth and still depends heavily on the strongest assistant. |
| **Weighted staff multiplier** | Each coach contributes to a staff-wide nonlinear rate multiplier; head weighted most. | Makes all assistants matter, but does relatively little for intrinsically slow developers. |
| **Conditional additive staff dividend** | Every coach supplies a weighted part of an independent, effort- and fit-gated growth opportunity; head-coach bond scales it. | **Preferred experiment**: selectively improves unfinished low/middle players without universally accelerating a roster. |

Simply changing DEV_K from 0.40 to 0.60 does not create the desired player-by-player differences.

### A trial additive model

A four-coach staff's trial Development weights: **head 52%, assistants 23%, 15%, 10%**. For smaller staffs, redistribute weight without rewarding vacant assistant positions, and keep the head as the largest contributor. Assign a stable, independently seeded work-ethic/coachability trait to each player, unrelated to talent, current OVR, winning or intrinsic development. Assign stable **player × coach fit**, so a particular combination of coaches suits particular players; don't grant every player under a strong staff the same bonus.

Each coach with Development quantile q contributes **d(q) = clamp((q − 0.50) / 0.40, 0, 1)^1.5**. Let **S** be the sum of the weighted individual contributions, adjusted by each player's fit. The *head-coach bond rating* B, a coach's program-development **credit/reliability rating**, multiplies this opportunity by a deliberately modest **0.85–1.15**. The first trial can use these gates:

- **Work ethic:** no dividend below 0.55. Above that, a deterministic seasonal success check, with trial probability rising from 0.25 at 0.55 to 0.90 at 1.00; higher effort also raises the payout size. No success means no dividend, not reduced intrinsic development.
- **Current ability:** full bonus eligibility at **OVR 60 or below**, linear taper to **zero at OVR 80**. Players at 80+ continue normal growth, but don't receive this exceptional coaching boost.
- **Headroom:** payout decreases below 12 unused OVR and can never exceed the player's remaining real career peak after the year's intrinsic gain.
- **Dividend:** in the illustrative version, extra annual realization is **4.0 × S × B × sqrt(clamp((work_ethic − 0.55) / 0.45,0,1)) × seasonal_draw × ability_gate × headroom_gate**, conditional on the check firing. The screening test used a composite player/staff fit factor of 0.65–1.20 and seasonal draw of 0.60–1.40. Production should use separate per-coach fits. **All constants are candidates, not settings or calibrated estimates.**

The essential feature is that the **additive dividend is independent of the amount of ordinary annual growth**. A low-work-ethic player gets normal intrinsic growth but usually no coaching boost; a high-work-ethic, naturally slow developer with genuine headroom can have a good extra-growth year. No dividend raises hidden ceiling, manufactures an early-development roll, or awards ratings for winning.

### Head-coach bond: ordinary success, not championships

Propose a **3–5-season, recency-weighted rating**, beginning neutral for a new head and traveling cautiously with the coach after a move. Trial inputs: **55%** difference between actual and roster-expected regular-season win rate; **30%** actual-versus-expected Road-to-State round units, using the existing jhsaa_coefficient.road_points()/season_points() ledger, normalized by competition group; and **15%** continuity/experience. Shrink estimates with little history toward neutral, avoid double-counting postseason duals, and have past seasons affect *future* dividends only. A coach going 7–17 when 4–20 was expected should be able to gain credibility; a powerhouse merely meeting expectations should not automatically do so. Age is **optional**: if tested, use it modestly for rating confidence or volatility, not an automatic young/old bonus or a second reward for tenure. Bound B to 0.85–1.15 to prevent runaway winner reinforcement.

### Synthetic sensitivity test, not JHSAA export results

The raw 325,145-transition panel is not attached. The following is a **fixed-seed invented 100,000-player-season screening experiment**, not actual JHSAA estimates: OVR sampled uniformly over 20–92, invented positively skewed headroom, truncated intrinsic gain averaging **3.64**, independently beta-distributed work ethic, and the trial probabilities above. A **target** player is under 60 OVR, has at least 12 headroom and work ethic at least 0.65.

| Staff development quantiles: head / three assistants | Bond | Current staff multiplier | Current extra OVR, whole sample | Additive extra OVR, whole sample | Additive extra OVR, **target** |
|---|---:|---:|---:|---:|---:|
| Weak .28 / .30 / .45 / .50 | .90 | .947× | −.192 | .000 | .000 |
| Average .50 / .55 / .45 / .55 | 1.00 | 1.008× | +.027 | +.005 | +.021 |
| Strong .82 / .72 / .74 / .62 | 1.10 | 1.128× | +.424 | **+.196** | **+.880** |
| Average head, excellent assistants .50 / .90 / .78 / .60 | 1.00 | 1.064× | +.213 | **+.107** | **+.479** |

For the strong staff, mean *additive* annual gains are about **+.31 at OVR 20–39**, **+.32 at 40–59**, **+.23 at 60–69**, **+.08 at 70–79**, and **zero at 80+**. Work ethic below 0.55 produces zero bonus, ethic 0.55–0.75 about +.24, and ethic above 0.75 about +.69. Only about **59% of eligible target player-seasons** gain at least a quarter OVR. Low-intrinsic-gain target players (under +1 annually) gained about **+.98** in the additive test versus **+.04** in a whole-staff *rate* alternative. The additive formula accomplishes something a bigger DEV_K alone cannot.

A separate **four-transition stylized career replay** with 30,000 seeded draws per scenario, same strong staff and fixed starting player characteristics:

| Start OVR / true peak | Natural annual gain | Work ethic | Natural four-year finish | Mean with additive dividend |
|---|---:|---:|---:|---:|
| 40 / 75 | +1.5 | .90 | 46 | **52.0** |
| 40 / 75 | +3 | .90 | 52 | **58.0** |
| 40 / 75 | +5 | .90 | 60 | **66.0** |
| 40 / 75 | +3 | .45 | 52 | **52.0** |
| 65 / 90 | +3 | .90 | 77 | **79.7** |
| 80 / 95 | +3 | .90 | 92 | **92.0** |

This shows the **desired behavior**, not a predicted real-world average. Six extra OVR over four seasons for a consistently responsive player is intentionally consequential; the association-wide inflation and elite tail must be evaluated on actual seasons.

### Real-model validation before approval

Use a **fixed-seed same-player replay** with named-staff Development disabled, current DEV_K, curved DEV_K, full-staff rate dividend, and full-staff **additive** dividend. Hold true peaks, annual intrinsic paths, early-POT and maturity rolls, exposure, transfers and program archetypes fixed first. Separately allow coach lineups to change exposure, to measure the indirect effect. Compare results by original OVR, headroom, work ethic, intrinsic capacity, staff and program; independently replace heads and assistants; test 1–3 assistant seats, ages and bond histories; and monitor cohort mean gain and 80+/90+ graduate rates. Check for additive/archetype stacking.

Preserve **seed determinism**, player identities across transfers, archived staff and bond-by-year, future-only era gating, the true-potential cap, a minimum ordinary development path, and no dividend at the trial upper ability gate. Export work ethic, coach/player fit, each coach's dividend, seasonal success roll, bond and realized extra OVR for analysis.

**Decision:** keep the existing career engine and current DEV_K in code. Test the **whole-staff, work-ethic-conditioned, head-bond-scaled additive dividend** as a targeted change to coaching, not a general retuning of players.

---

## Addendum — Attribute-level developmental capacity and coaching portfolios (2026-10-09)

**Status: owner-approved design direction; implementation and real-export calibration are pending.** This section **supersedes the preceding staff-dividend addendum as the proposed design**. The earlier addendum and its synthetic numbers remain as research history, not as evidence for the mechanism below. No JHSAA save, simulation parameter, development code, or archived result was changed in producing this report.

> **Potential becomes a stock of developmental capacity, while coaching determines which capabilities a player can actually acquire.**
>
> A great assistant does not merely make an entire roster progress ten percent faster. That assistant might teach a mediocre baseline player to become a very good doubles player, or help an athlete with excellent movement and weak technique develop into a competitive varsity player.

The objective is **real skill acquisition over a four-to-six-year school career**. Attributes improve, so the player's weighted OVR and on-court ability change through the **existing match engine**. There is **no new win-probability bonus for having a development coach**. The established Changeover advice roll must remain useful in close matches, distinct from the developmental effects. Existing Tactics and Singles match-side coaching rules should also remain separate and intact.

### The rare, consequential career is part of the target

The owner's real coaching observation is that some students arrive in ninth grade having never played tennis, then reach State singles semifinals or State doubles finals by senior year. This is **an experiential design reference, not a measured frequency from the JHSAA exports**. Such transformations are unusual but possible when a newcomer has substantial latent aptitude, absorbs instruction, trains consistently, competes and happens to have highly capable coaches.

The existing 2103–2111 panel had a modest center (median annual gain +2 OVR) and a long tail (the extraordinary seventh-to-twelfth-grade Lamont Schultze career, +71). It validates the value of *latent capacity plus realization*, but **does not measure the desired impact of skill-specific instruction**. Do not force every low-rated freshman to remain weak because of their starting OVR. Equally, do not create a universal beginner-to-elite escalator.

For the new mechanic, specifically stress-test **ninth-grade starters** with rare four-year development paths of +25, +35, +45 or more weighted OVR, when the generated latent capacity and coaching conditions permit. **These are test corridors, not calibrated targets or automatic rating grants.** A semifinal or final is an actual bracket outcome against contemporaneous opponents, not a direct reward for hitting an OVR threshold. Singles and doubles success should be distinguishable: net technique, poaching and doubles chemistry can develop far faster under one staff than baseline skills.

### What exists in the repo

- **51 rich player attributes**, not the stale 49 mentioned in older documentation: app/player_attributes.py defines RICH_ATTRS, separate OVR weights, and the conversion into the engine's skill drivers. Serve accuracy, volley touch, footwork, mental skills, coachability and training_drive already exist. Weighted OVR is computed from the attribute table; it is not itself a stat to increment directly.
- **Per-attribute current and potential dictionaries** already exist in app/development.py. The generator draws individual potential ceilings around talent and shapes them by playing style. For college Prospect.develop, development already moves each attribute toward its own ceiling.
- **JHSAA is different**: app/jhsaa.py:_career_plan / career_ability calculate an overall trajectory; _apply_career generates the prospect at the ceiling, then scales **every current attribute by the same career factor**. It preserves the player's original style proportions but cannot create a new skill-specific career path. The new model must replace this *scalar realization* for new cohorts, not append another generic OVR boost to it.
- **Named staff** in app/jhsaa_coaches.py have stable coach identities, Development/Singles/Doubles/Tactics and other grades, up to three assistants, staff-history snapshots, and Changeover behavior. Today Development is one effective blended rating: the head's grade plus 40% of the gap to the best assistant. Other assistants do not independently contribute to actual player development.
- **Professional proof of feasibility:** app/gtt_seasonmode.py:apply_club_coaching already picks an attribute portfolio by coach playing style and modifies specific current attributes according to coaching strength and player coachability. GTT allows gains beyond preexisting potential and is deliberately simple. Reuse its attribute-targeting idea, **not** its unrestricted growth rule in high school.
- **Actual JHSAA matches run fast fidelity** (jhsaa.FIDELITY). engine/fast.py uses serve, return, rally, mental, stamina and style composites, and doubles has further net-specific channels. Verify every proposed teaching portfolio changes attributes that its intended singles/doubles match mode actually reads. A skill that raises only a display number is not a developmental success.

### The new player contract: stock, targets and trainability

**A player should be generated once with a complete latent developmental profile, but should not be guaranteed to realize it.** Keep four distinct objects, all deterministic from player identity and the relevant era:

| Object | Meaning | Can a school change it? |
|---|---|---|
| **Current attribute vector** | What the player can actually do now, across all 51 attributes. Drives weighted OVR and the match engine. | Yes, by realized development. |
| **Natural targets** | Attribute levels likely under ordinary development, without exceptional coaching. These preserve the default player-specific career shape. | They define the baseline; a specialist may help the player go further. |
| **Trainable ceilings** | Player-specific upper limits for skill acquisition with unusually effective instruction; not simply the old low attribute POTs. Some weak areas are highly trainable; others really are limited. | No: determined from the player's latent aptitude and legitimate early-development events, not from the staff's reputation or team wins. |
| **Developmental stock / budget** | A finite, possibly very large pool of additional attribute development available during the player's school career; can remain unused at graduation. | Coaches change *allocation and realization*, not the initial stock. Rare established maturity/early-POT events may add stock and expand trainable ceilings within the player's maximum scale. |

The user's illustrative “236/600 plus another 300 potential attribute points” describes this **accounting concept**, not a literal sum on the current 51 × 20–100 attribute scale. Raw attribute points, weighted OVR and effective skill strength are **different units**. Implement a clearly named accounting unit and retain **both** a raw-attribute spending constraint and a weighted-OVR realization constraint: otherwise concentrating cheap or heavily weighted attributes can game the budget. Do not choose the budget's numerical distribution until real cohort replays have calibrated it.

A natural target and a trainable ceiling may be far apart in one category: e.g. a ninth-grader's volley touch is 24, ordinary development might reach 38, but that **particular player's** trainable upper limit might be 60. Another player also starting at 24 might have a limit of 42. An elite net/doubles coach can help the first player reach into the upper range, subject to work, time and available developmental stock, but cannot do the same for everyone.

**POT semantics need an explicit migration decision.** Existing p.potential[attr] already means “hidden true attribute ceiling.” For new-era JHSAA cohorts either promote this field to the genuine *trainable ceiling* and store natural targets separately, or add separate trainable limits while updating all POT consumers deliberately. Do not silently rewrite POT to mean both “default senior projection” and “best-ever trainable maximum.” The scouting estimate can remain uncertain; it should not disclose the whole latent budget. This is an implementation-design choice to resolve in the prototype, not a request to regenerate existing player ceilings.

### Natural growth and coached growth draw from the SAME stock

**Do not retain the full scalar JHSAA career gain and then add a second unaccounted pool of coach points.** That would double-count capacity and inflate the association. In the new era, generate the original expected growth curve, convert its *realized* growth into attribute-level baseline expenditures, then allow coached expenditures and reallocations from **remaining** stock.

A year's development proceeds by these concepts:

- **Intrinsic opportunity:** player-specific annual availability and the existing experience/exposure odometer supply ordinary growth, even if no staff is exceptional. No one loses their basic maturation merely for low work ethic.
- **Responsiveness:** a stable work-ethic/disposition seed and category-specific coachability determine how much *additional* coaching the player can absorb; use generated values of the existing training_drive and coachability attributes as relevant evidence, without letting those trainable current ratings repeatedly multiply their own future growth. Keep latent effort traits stable across transfers.
- **Teaching offers:** the head and **each** assistant can offer development in the categories they teach, with player-by-coach fit, year-specific exposure and actual remaining trainability. Coaches may be effective at improving a strength, filling a weakness, or both; no requirement that every staff is additive in every category.
- **Allocation:** distribute the player's available seasonal and career stock among valid offers, subject to category trainable ceilings, season-rate limits, actual headroom, and the weighted-OVR budget. A poor fit or untrained category receives little or no coached growth. Low current skill alone is insufficient; high *trainability minus current skill* identifies a teachable weakness.
- **Outcome:** update individual attributes, recompute derived drivers and OVR from app/player_attributes.py, and let the ordinary match engine decide matches afterward. Archive which coach/category and which kind of growth was realized.

Illustrative interface sketch (NOT implementation):

~~~python
intrinsic = generate_player_yearly_opportunities(pid, grade, exposure)
offers = []
for coach in archived_staff(season):
    for attribute in coach.teaching_portfolio:
        remaining_skill = max(0, trainable_cap[attribute] - current[attribute])
        offers.append(teach_offer(
            player=pid, coach=coach.coach_id, attribute=attribute,
            remaining=remaining_skill, effort=stable_work_ethic,
            receptivity=player_coach_fit(pid, coach.coach_id, attribute),
            exposure=exposure, head_bond=head_bond_at_season))
gains = allocate_and_cap(
    intrinsic, offers,
    remaining_career_stock, year_stock,
    raw_attribute_budget, weighted_ovr_budget,
    personal_trainable_caps)
current_attributes = apply_gains(current_attributes, gains)
# OVR and engine characteristics derive from attributes, never vice versa.
~~~

The stock need not be exhausted, and the developmental offers are **not guaranteed payouts**. A stable, seeded player/coach/category/season check can govern whether instruction took hold. A player with high effort but the wrong teacher might spend an ordinary year without a coaching jump. A different teacher arriving later can open a new avenue of growth. Experience stays valuable, but winning a match **never directly creates attribute points**.

### Every coach contributes something different

The **head coach has the largest influence** over the effectiveness of the development program, the consistency of training, and how well assistants' work reaches the roster. The head also has a teaching portfolio. Assistants each contribute distinct offers to players; a superior assistant is not reduced to 40% of a gap behind the head.

Keep the existing one-head-plus-one-to-three-assistants staff size. Generate each coach a **small stable teaching portfolio**, primarily from existing coach identity and Development, Singles, Doubles and Tactics grades, supplemented by a separately seeded specialization that does not redraw existing ratings. Example portfolios: serve/return mechanics; baseline technique and consistency; footwork/conditioning; net/transition/doubles play; tactical point construction; mental preparation.

**Different mixes should generate different players.** A staff of four elite but identical serve coaches improves fewer *kinds* of skills than four comparably elite, complementary specialists. Overlapping expertise has diminishing returns; complementary instruction opens more attributes. The head should have the largest single influence, but replacing any strong assistant with a weak or mismatched specialist should measurably affect at least some player trajectories. An extraordinary three- or four-person elite staff plus an unusually trainable, hardworking player may support **very large total gains**, not merely a one-point improvement per season.

**Bond remains a program-effectiveness governor, not a new talent generator.** The proposed head-coach bond rating can respond slowly to expected-versus-actual regular-season wins, expected-versus-actual Road-to-State round units (via jhsaa_coefficient), and program continuity. A new head starts near neutral. Make age optional, weak and tested rather than an automatic penalty or reward. Lag results by a completed season and bound the effect: four elite coaches should matter for **what they teach**, not because State titles compound into automatic future superstars.

Keep the distinction between **teaching expertise** and **match-day coaching**. The standing fast-engine Changeover advice effect still rolls at set breaks and should remain a useful situational edge. Existing Singles and Tactics match effects likewise should stay in their own channels. New attribute development changes the *underlying player* before the match; it must not add a second live skill/match multiplier on top.

### Possible player biographies this must make possible

The following are **designed stress cases, not people or outcomes observed in the export**, and their OVR paths are illustrative rather than predicted calibration:

| Career test | Ninth grade | Senior outcome under appropriate conditions | Mechanism that must explain it |
|---|---|---|---|
| **First-time player with extraordinary trainability** | Very low overall ability, major weaknesses, high hidden stock, high effort | Potentially **30–50+ weighted OVR** improvement across the ninth-to-twelfth-grade window, with a genuine chance to reach a State-level singles semifinal in some cohorts | Large latent stock, several complementary coaches, sustained absorption, attribute-specific technical growth and substantial exposure |
| **Previously weak doubles prospect** | Modest baseline skills, weak volleys/poaching and undeveloped doubles play | A State-level doubles finalist is **possible**, even without becoming an equally distinguished singles player | Exceptional net/doubles instruction reallocates stock toward the skills the doubles engine reads |
| **Good player, poor fit for staff** | Strong ninth-grade rating, relatively little headroom in useful categories | Ordinary, bounded improvement despite an elite staff | Coach quality cannot invent missing trainability or require that every player flourish |
| **High-effort project, weak program** | Low-to-middle current level, strong effort, substantial remaining skill room | May improve naturally; a fitting new assistant or transfer creates a distinct opportunity later | Program staff changes allocate capacity; intrinsic trajectory survives |
| **Low-engagement student on elite team** | Any starting level, ordinary or high natural potential | Mostly intrinsic growth, not automatic bonus growth | Low coaching absorption prevents a blanket team-wide escalator |

A 30–50+ OVR transformation is **extreme** relative to the observed median of +2 per year. The prototype must prove that the generator can produce the underlying stock and that 51 actual attributes can move sufficiently, not merely write a desired OVR path onto a graph. The competitive target is **occasional actual State results**, not any guaranteed number of semifinalists or finalists. Check singles and doubles independently and account for championship-group strength, draw and format.

### Prototype plan and calibration gates

**Preserve history first.** Use a distinct development-era gate for newly entering JHSAA cohorts. Keep every pre-era saved/archived roster, POT, match result and identity unchanged. Generation streams for new latent stock/effort/trainability and all coaching rolls must be stable and separate from the old seat RNG. Do not allow coach changes, transfer, renamed schools, or current archetype tags to rewrite prior-year skills. Use archived **staff, bond, exposure and actual school for each year**; the same player_id must retain identity across schools.

**Build a pure attribute-growth prototype**, reusing app/development.py per-attribute structures, app/player_attributes.py weighting, app/playstyles.py attribute emphasis as a reference, and app/jhsaa_coaches.py's real staffing. Replace JHSAA scalar _apply_career only in the new era. The GTT implementation is a starting example for targeting, not a drop-in growth policy.

**Run an attribute-level matched-player experiment**, not an undifferentiated comparison of schools. Start with identical player creation, natural trajectory, work/coachability, early-POT/maturity rolls, and exposure. Replay with ordinary staff; strong head only; excellent assistant only; four overlapping elites; four complementary elites; a staff change in sophomore year; and transfer to a complementary staff. Remove one coach at a time to measure the attributable gain. Then perform a **separate** pass allowing coaching-dependent lineups and exposure to vary. Test both natural and exceptional rookie pools, including ninth-grade beginners who could legitimately develop into State-level competitors.

**Measure what grew.** Export current and natural-target/trainable-cap attribute vectors, starting/remaining stock, spent credits per year, skills added by coach and specialty, player-coach fit and effort, head bond at season, coach moves, and actual on-court singles/doubles outcomes. Output paths by grade, not just terminal senior OVR. Distinguish improved serve placement from improved volley/poaching even when weighted OVR totals match. Verify that fast-fidelity singles and doubles consume the improved skills.

**Protect the center while admitting a genuine upper tail.** Compare the original 2103–2111 panel to the new entry-era cohort: median/mean yearly gain, 90th/99th percentile annual changes, 20+/30+/40+/50+ career gain frequencies, OVR 80+/90+ graduates, attribute-group improvements, headroom remaining at graduation, within-program variation, sensitivity to each assistant, and inflation over repeated generations. The inherited panel supplies a historical benchmark, **not** a completed experiment on this proposal. If the new model produces more extraordinary developers, demand a corresponding audit of their latent stock, work, instruction and exposure rather than suppressing the tail merely because it exists.

**Decision:** Do **not** retune the career model by increasing DEV_K, and do **not** implement the previous generic additive OVR dividend. Advance to a new-era **attribute-level developmental-stock and coaching-allocation model**, with unusually high but rare feasible gains, individually specialized staffs, and no new live match-outcome buff. Preserve Changeover advice as a separate, useful match-day mechanic.
