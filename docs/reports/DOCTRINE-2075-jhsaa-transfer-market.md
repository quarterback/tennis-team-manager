# 2075 JHSAA Transfer Doctrine

Status: governing design doctrine for future JHSAA transfer-market work.

This document exists so future agents do not infer the purpose of the JHSAA transfer system from aggregate mover counts, parity outcomes, or one-off repair passes. The transfer market is not primarily a generic talent-allocation mechanism. Its purpose is to keep varsity-caliber players from being stranded in JV/reserve roles when real varsity seats exist elsewhere, while separately allowing a narrow class of elite players to escape chronically bad competitive environments.

The two markets are distinct and should remain distinct in code, evaluation, and reporting.

## 1. Ordinary transfer market: clear roster congestion

The ordinary transfer market exists to solve one specific problem:

**A player is good enough to be a varsity player, but their current program has more varsity-caliber players than varsity seats.**

That player should be able to move to a program where they can occupy a real varsity role.

The objective is not to maximize transfer volume. It is not to redistribute talent for parity. It is not to move strong players simply because another team could use them. It is to clear excess varsity talent out of JV/reserve roles.

The primary system-level success metric is therefore:

**Does the transfer market lower the amount of varsity-caliber talent trapped on JV/reserve rosters?**

That should be measured directly.

### Ordinary-transfer eligibility

A player should enter the ordinary transfer pool only when all of the following are materially true:

- the player is projected outside meaningful varsity use at the current program;
- the player is clearly stronger than the normal JV/reserve population;
- the player would plausibly hold a varsity seat somewhere else;
- the move does not simply displace an equivalent or better varsity player at the destination and recreate the same congestion problem.

The trigger is **role mismatch**, not abstract talent.

A No. 14 player at an exceptionally deep 9A program may be an obvious transfer candidate if their OVR would make them a varsity regular almost anywhere else. A weaker reserve who is correctly placed on JV is not.

## 2. Destination logic: varsity access before classification descent

The destination search should answer:

**What is the highest appropriate competitive level where this player can hold a real varsity seat?**

It should not default to moving players down the classification ladder.

With larger varsity rosters now available in 9A and 8A, those classifications should absorb more congested varsity-caliber players. A blocked player at one 9A school may have a perfectly legitimate lateral destination at another 9A school, or at 8A, rather than being pushed automatically into 6A/5A merely because those programs historically had more open seats.

Preferred destination order should therefore broadly favor:

1. same classification, when a real varsity seat exists;
2. adjacent classification, when the player fits naturally there;
3. farther downward movement only when necessary to secure meaningful varsity use.

The model should not treat classification descent as the definition of opportunity.

## 3. The JV talent distribution is the key diagnostic

The transfer market should be evaluated by what happens to the top end of JV/reserve talent.

Future season reviews should report at minimum:

- count of JV/reserve players above a defined varsity-caliber threshold before transfers;
- count after transfers;
- 90th and 95th percentile JV OVR before and after;
- maximum JV OVR before and after;
- number/share of transfer candidates who become real varsity players at their destination;
- destination rank for movers;
- varsity appearances for movers;
- same-class / one-class-down / two-plus-classes-down movement shares;
- number of destination varsity players displaced into JV by incoming transfers;
- net change in association-wide varsity-caliber players stuck outside varsity.

Aggregate mover counts are secondary. A smaller market that removes nearly all obviously misplaced JV talent is better than a large market that merely circulates players.

## 4. Transfers reallocate opportunity; they do not create varsity capacity

The ordinary transfer market should not be mistaken for a general participation policy.

Moving a blocked player to an open varsity seat can dramatically improve that player's career without materially changing the total number of varsity appearances available across the association.

JV, roster-size rules, schedule size, lineup formats, and other participation mechanisms address total opportunity. Transfers address **misallocation of existing opportunity**.

That distinction should remain explicit in future analysis.

## 5. Separate market: elite-player rescue

There is a second, narrower transfer doctrine for elite players on chronically bad programs.

This is not congestion clearing. These players are usually already playing No. 1 or No. 2 and receiving substantial varsity use.

The problem is different:

**The player is elite, but the program cannot provide a competitive environment commensurate with the player's level.**

An elite freshman or sophomore on a persistently poor team may reasonably seek a stronger competitive setting.

This market should be rare and selective. It should not turn every elite player on a losing program into a transfer candidate.

### Elite-rescue candidates

A player becomes a plausible elite-rescue candidate when several conditions align:

- genuinely elite individual level, not merely best-on-a-bad-team;
- source program is persistently poor rather than temporarily down;
- source program is unlikely to become meaningfully competitive during the player's remaining career;
- player has limited accumulated institutional legacy at the source school;
- player is early enough in their career that moving changes the competitive arc rather than merely relocating a senior season.

Freshmen and sophomores are the cleanest candidates.

## 6. Junior retention

Juniors should generally have a strong presumption toward staying.

By junior year, the player has only one season remaining after the current one and has already accumulated substantial program history. The model should not routinely turn elite juniors on bad teams into senior-year mercenaries.

A junior may still move in exceptional circumstances, but the threshold should be materially higher than for a freshman or sophomore.

## 7. Historic-career retention

Historic individual careers should create an even stronger retention force.

A player's accumulated legacy at a school has independent value. The simulation should recognize that identity rather than treating every season as a fresh optimization problem.

Examples of strong legacy anchors include:

- multiple Player of the Year awards;
- three-time Player of the Year status;
- multiple State No. 1 Singles championships;
- an ongoing attempt at an unprecedented third/fourth S1 title;
- repeated All-State / classification honors at the same school;
- major team-title history tied directly to the player's career;
- other historically unusual records or milestones.

A player chasing a fourth State S1 championship at their original school is qualitatively different from an equally strong sophomore with no established legacy.

The stronger the accumulated career, the stronger the retention effect should become.

This allows bad or mediocre programs to still produce legendary four-year players instead of having every exceptional player migrate toward contenders.

## 8. Do not collapse the two markets into one transfer score

Future agents should not implement one generic formula that blends congestion, team quality, individual strength, and destination prestige into a single mover ranking.

The two markets answer different questions:

### Congestion transfer

> I am good enough to play varsity, but there is no varsity seat for me here.

### Elite rescue

> I am already a star, but this program cannot provide an appropriate competitive environment.

### Legacy retention

> I could find a stronger team, but my career at this school has become historically meaningful enough that staying has independent value.

These should be separate pathways with separate eligibility rules and separate reporting.

## 9. Source-program integrity still matters

Even when individual moves are justified, the market should not strip a source program mechanically.

For congestion clearing, recalculating the source ladder after each departure is essential. Once one blocked player leaves, another player's role may become viable and they should no longer be treated as congested.

For elite rescue, multiple top players should not be removed from the same weak program simply because each independently clears an elite threshold. The source team remains part of the simulation ecosystem.

The system should therefore enforce source integrity during slate construction, not repair catastrophic depletion afterward.

## 10. The intended association-level outcome

A healthy JHSAA transfer system should produce all of the following at once:

- fewer varsity-caliber players marooned on JV;
- lower upper-tail JV OVR;
- more blocked players occupying meaningful varsity seats;
- more lateral movement within 9A/8A now that those classifications have larger varsity rosters;
- less automatic downward cascading through classifications;
- occasional elite-player escapes from genuinely hopeless competitive situations;
- strong retention for juniors and historically significant careers;
- continued possibility of legendary players remaining loyal to weak or mediocre programs;
- no requirement that overall competitive parity improve.

Parity is not the goal. Correct placement of players is.

## 11. What future agents should optimize

When changing transfer logic, optimize in this order:

1. reduce obviously varsity-caliber talent sitting in JV/reserve roles;
2. place movers into real varsity seats;
3. prefer lateral or near-level destinations when those seats exist;
4. avoid simply displacing equivalent players at the destination;
5. protect source-program integrity;
6. run elite rescue as a separate, narrow market;
7. apply junior and historic-career retention strongly;
8. only then examine secondary effects such as parity, championship concentration, or aggregate movement.

The transfer market is a placement mechanism first and a competitive-market mechanism second.

## 12. 2075 as the reference point

The duplicated 2075 season created an accidental comparison that clarified the philosophy but did not itself test this exact doctrine.

The original 2075 included a large opportunity-transfer class and a separate stranded-talent repair class. The rerun effectively did not reproduce that transfer intervention. That comparison showed that targeted transfers can dramatically change individual playing opportunity and competitive outcomes, but the future doctrine is more specific than either historical pass.

Going forward, the ordinary market should be explicitly designed around **flushing varsity-caliber players out of JV/reserve roles into available varsity seats**, especially taking advantage of the larger 9A/8A varsity rosters. Elite-player rescue should remain a distinct exception market constrained by class year and career legacy.

That is the governing transfer philosophy unless the owner explicitly changes it.