You're right. The prior response mostly translated the other agent’s ideas instead of mining the 2086 save.

I went back into the actual Season 60 export and joined `duals → lines → line_players → players`, then cross-referenced `program_history`, `coefficient`, and the full 2086 individual brackets. 

The result is much more useful.

## 1. There are 319 actual “nemesis” pairings in 2086

Definition used: the lower-rated player is at least 5 rating points below the opponent and beats that same opponent in at least two consecutive meetings.

Four pairings became full 3–0 curses:

| Lower-rated player | Program    |         Class | Rating | Higher-rated opponent | Program            |         Class | Rating |     H2H |
| ------------------ | ---------- | ------------: | -----: | --------------------- | ------------------ | ------------: | -----: | ------: |
| Samantha McPherson | Burdensome | Group 2 girls |     67 | Lauryn Tosch          | Hampton            | Group 2 girls |     76 | **3–0** |
| Johan Zanutto      | Pendleton  |       5A boys |     81 | Declan Brewster       | Providence Academy |       5A boys |     86 | **3–0** |
| Thérèse Paquette   | Coleman    |      8A girls |     77 | Chloe Hilliker        | Dogpatch           |      8A girls |     82 | **3–0** |
| Jamie Lefevre      | Madrigal   |       8A boys |     66 | Gabriel Hutchinson    | Okefenokee         |       8A boys |     71 | **3–0** |

The most extreme rating-gap curse is Collins Terrell of Latgaway (Group 3 girls): rating **67**, but **2–0** against Cassidy Pace-Wilson of Riverview (Group 3 girls), rating **89**.

That is a 22-point rating disadvantage repeated twice against the same player.

Other extreme repeat upsets:

* Zahra Ait Ali, Singleton (Group 3 girls), 54: **2–0** over Brooke Elie, Raft County Catholic (Group 3 girls), 75.
* Alexa Olden, Salmon Bay (1A girls), 51: **2–0** over Bristol Jurado, Redwood Glen (1A girls), 70.
* Payton Guerrero, Anse Doree (8A girls), 64: **2–0** over Kaela Wood, East Moscow (8A girls), 82.
* Tucker Gatti, Romare Bearden (Group 1 boys), 57: **2–0** over Timothy Grantham, Boyle Heights (Group 1 boys), 75.

That is actual universe lore, not a hypothetical metric.

## 2. The real giant-killers are not necessarily good players

I fitted expected singles win probability from rating differential and home advantage, then measured wins above expectation.

The strongest season-long overperformers with at least 20 singles matches:

| Player           | Program              | Class        | Rating |   Record | Expected wins |      WAE |
| ---------------- | -------------------- | ------------ | -----: | -------: | ------------: | -------: |
| Morgan Corey     | Santa Cruz del Norte | 7A girls     |     58 | **24–5** |          15.7 | **+8.3** |
| Antonio Cohen    | Four Rivers Charter  | 2A boys      |     57 |     20–9 |          12.3 | **+7.7** |
| Willa Ford       | Emerson              | 6A girls     |     63 |     18–8 |          11.5 | **+6.5** |
| Ethan Allister   | Hidden Draw          | Group 1 boys |     52 | **15–6** |           8.5 | **+6.5** |
| Royal Desantiago | Temescal             | 8A boys      |     64 | **24–3** |          17.8 | **+6.2** |
| Ana Félix        | Cedar Point          | 5A girls     |     45 |    11–15 |           5.1 | **+5.9** |

Ana Félix is especially interesting. She is only 11–15, but a rating-45 player was expected to win about five matches. She nearly doubled that.

Ethan Allister of Hidden Draw (Group 1 boys) won four matches while at least 10 rating points behind and had one matchup where the gap reached **37**.

Morgan Corey of Santa Cruz del Norte (7A girls), a sophomore, won three matches as a 10+ point underdog and encountered a maximum deficit of **39**.

That is the kind of player I would actually tag as a giant-killer.

## 3. Some players live almost entirely on punch-ups

If I require at least three wins while trailing by 10+ rating points:

* Xochitl Testerman, Central West End (5A girls): **5–2** in those matches.
* Omar Martinez, Carter (9A boys): **5–6**.
* Francisco Nichols, Ransom Pass (1A boys): **5–6**.
* Joshua Staudt, Mabry Township (Group 3 boys): **5–7**.
* Sophia Dahl, Mar Vista (9A girls): **5–7**.
* Ileana Moldovan, Aldecoa (Group 1 girls): **5–11** despite a rating of only 52.

That last one matters. Moldovan went only 8–13 overall at S1, but the model expected about **2.7 wins**. Her apparent losing record masks a huge amount of schedule difficulty and upset production.

## 4. There are real “bracket merchants”

I compared regular-season singles performance against the full individual championship bracket.

The largest elevations:

| Player          | Program        | Class / flight   | Regular season |   Individual run |    Elevation |
| --------------- | -------------- | ---------------- | -------------: | ---------------: | -----------: |
| Estefania Erazo | Starfield      | 6A girls S1      |      **11–13** |              4–1 | **+34.2 pp** |
| Leila Rock      | Rilland        | Group 3 girls S1 |      **10–14** |              3–1 |    **+33.3** |
| Asher Rhee      | Pelican Town   | 6A boys S2       |           10–9 |              4–1 |        +27.4 |
| Jase Wang       | Spring Harvest | Group 2 boys S3  |            9–8 |              4–1 |        +27.1 |
| Tristan Bonds   | Brown          | Group 2 boys S3  |            7–7 |              3–1 |        +25.0 |
| Madeleine Kim   | Fellows Mill   | 4A girls S1      |          11–11 |              3–1 |        +25.0 |
| Prince Spain    | Sandhill Marsh | 5A boys S1       |          12–11 | 3–1 from seed 22 |        +22.8 |

Erazo is exactly the archetype the earlier prompt was trying to describe: mediocre regular season, then suddenly an 80% win rate in the S1 championship.

There were no individual champions with a regular-season singles win rate below 70%. So the “bracket merchant” phenomenon exists primarily among deep non-championship runs, not among the actual title winners.

## 5. There are legitimate “great senior, no title” cases

I isolated current seniors with:

* at least 15 S1 matches;
* at least 70% season singles win rate;
* no individual championship in the historical ledger;
* no team State championship during their 2083–2086 high-school window.

The strongest cases without even an individual finals appearance:

* Maggie McPherson, San Dámaso (6A girls): **22–1**, rating 92. San Dámaso (6A girls) finished 18–10, class rank 18. McPherson reached the 2086 individual octofinal.
* Alyssa Andrade, Marigny (6A girls): **20–1**, rating 87. Marigny (6A girls) was class rank 3, but only reached the team octofinal. Andrade reached the individual quarterfinal.
* Finn Brockway, Tidegate (8A boys): **23–2**, rating 91. Tidegate (8A boys) went 36–4 and reached the team semifinal; Brockway reached the individual quarterfinal.
* Maura Clardy, Odellville (1A girls): **17–2**, rating 65, while Odellville (1A girls) went **4–21, class rank 71** and never made State. This is the cleanest “trapped star” profile.
* Madilyn Bangura, Homeland (Group 2 girls): **23–3**, rating 84. Homeland (Group 2 girls) went 32–1, yet exited the team octofinal; Bangura also exited the individual octofinal.

Clardy is much more interesting to me than a 99-rated player on a powerhouse. A 65-rated senior winning 89.5% at S1 on a 4–21 team is exactly the kind of hidden universe story that disappears in normal standings.

## 6. Lineup stacking is actually happening

I used a stricter definition than “top player isn't at S1.”

A stacking event requires:

* regular-season varsity dual;
* the strongest player actually used in the lineup;
* that player is at least **5 rating points stronger** than the S1 player;
* the stronger player is placed below S1 or in doubles.

There were **240 such events across 88 programs**.

Across those events:

* the stronger displaced player won **72.1%** of the time;
* the sacrificial S1 player won **48.3%**;
* the team won the dual **62.9%**.

That strongly suggests the mechanic is often functioning as an actual point-allocation strategy, although it is not a counterfactual proof that the alternative lineup would lose.

The cleanest example is Minnesota City (8A girls), the eventual 8A champion.

In nine regular-season duals, Sophia Gideon, rating **93**, was placed at S2 or S3 while an 87–88 rated teammate played S1.

Gideon went **9–0** in those lower positions.

The S1 player went **7–2**.

Minnesota City (8A girls) went **9–0 in those duals**.

That is a real strategy pattern.

Fort Tabor (2A boys) looks more like classic sacrifice-and-bank-the-next-point:

* Richard Saffold, rating 71, was repeatedly placed at S2.
* S1 was occupied by players rated 61–64.
* five such duals;
* Saffold went **4–1**;
* S1 went **2–3**;
* Fort Tabor (2A boys) went **3–2**.

At the other extreme, Burnt River (1A girls) did this 12 times and got nothing from it:

* stronger displaced line: 3–9;
* S1: 1–11;
* team: **0–12**.

Stacking cannot rescue a roster that is simply overwhelmed.

## 7. Flight efficiency exposes hidden program strengths and failures

I calculated actual win rate versus rating-based expected win rate for each program/flight.

Strongest positive residuals with at least 20 matches:

* Hidden Draw (Group 1 boys), S1: **71.4% actual vs 40.5% expected**, +30.9 points.
* Fort Tabor (2A girls), D3: 83.9% vs 55.8%, +28.1.
* Bahía Leal (7A boys), S1: 75.0% vs 47.1%, +27.9.
* Santa Cruz del Norte (7A girls), S3: **87.5% vs 61.7%**, +25.8.
* Chaparral (8A girls), D2: 52.0% vs 27.5%, +24.5.
* Harriman (Group 1 boys), D3: 74.1% vs 50.4%, +23.7.

Worst:

* Xavier College Prep (8A girls), S3: **29.6% actual vs 60.9% expected**, −31.2.
* Pacersburg (4A girls), S3: 29.2% vs 60.1%, −30.9.
* Rilland (Group 3 girls), S3: 37.5% vs 67.7%, −30.2.
* Pennsauke (9A girls), D4: **4.5% vs 32.3%**, −27.8.
* Dusty Spur (6A boys), D4: 16.0% vs 43.4%, −27.4.
* Springfield (6A girls), S2: 31.4% vs 58.1%, −26.6.

That gives you actual places to investigate lineup construction rather than merely bad team records.

## 8. The coefficient now reveals true fallen powers

This is one of the strongest uses of the new metric.

Programs with elite recent coefficient standing but awful 2086 current rank:

| Program         | Class    | Coefficient rank | 2086 class rank | Record |
| --------------- | -------- | ---------------: | --------------: | -----: |
| La Grande       | 5A girls |            **5** |          **80** |   2–19 |
| Mt Jacqueline   | 1A girls |                6 |              74 |   4–23 |
| Chaparral       | 8A boys  |            **4** |          **66** |   7–19 |
| Chaparral       | 8A girls |                8 |              65 |   7–18 |
| Vale            | 2A girls |                5 |              61 |   5–19 |
| Elk Run         | 2A boys  |                9 |              61 |   4–19 |
| Larchmont Ridge | 8A girls |            **2** |          **57** |   7–15 |
| Canyonlands     | 7A girls |            **3** |          **57** |   4–20 |
| Dusty Spur      | 6A boys  |            **4** |          **55** |   5–23 |

Those are exactly the programs where “new coach + targeted transfer injection” has a compelling universe rationale.

They are not random bad programs. Their recent championship history says the institution has been one of the stronger programs in its class, while the current roster has collapsed.

## 9. And the inverse identifies genuinely new powers

Current top programs with weak recent coefficient pedigree:

* De La Salle (9A girls): current class rank **10**, coefficient rank **58**, 25–5.
* Friendship City (9A girls): rank **8**, coefficient rank **56**, 26–5.
* Springfield (6A boys): rank **4**, coefficient rank **34**, 25–2.
* Driftwood (4A boys): rank **4**, coefficient rank **34**, 26–6.
* Deaconsburg (7A boys): rank **9**, coefficient rank **36**, 24–4 and State quarterfinal.
* Boyle Heights (Group 1 boys): rank **6**, coefficient rank **36**, 26–5.

Those are not established dynasties having another good year. They are current teams outrunning the program's recent institutional record.

## 10. The three-year rise/collapse map is violent

From 2083 to 2086:

Largest rises:

* Wells (9A girls): class rank **78 → 15**
* Springfield (6A boys): **65 → 4**
* Metropolitan Country Day (5A girls): **61 → 1**
* Portola-Caverly (1A boys): **69 → 10**
* De La Salle (9A girls): **69 → 10**
* Crater View (8A girls): **60 → 4**
* Wallowa (1A boys): **78 → 22**
* Deaconsburg (7A boys): **62 → 9**

Largest collapses:

* Burnt River (1A girls): **3 → 85**
* La Grande (5A girls): **1 → 80**
* Burnt River (1A boys): **9 → 80**
* Kilbride Switch (5A boys): **7 → 77**
* Mt Jacqueline (1A girls): **5 → 74**
* Chaparral (8A boys): **1 → 66**
* Sotkamo Union (Group 3 girls): **3 → 69**
* Canyonlands-type programs also show major drops depending on gender.

That is the program-cycle dashboard I would want: not simply current rank, but **trajectory plus coefficient pedigree**.

## 11. There really are “systems”

Using 2080–2086 program history, some programs are so consistently strong across cohorts that calling them player-dependent is hard to sustain.

* Westfield Friends (5A boys): top five **7/7 seasons**, five State titles.
* Gagarin (4A boys): top five **7/7**, five titles.
* Baptist (7A boys): top five **7/7**, four titles.
* Mirage Crossing (Group 3 girls): top five **7/7**, four titles.
* Baptist (7A girls): top ten 7/7, four titles.
* Banfield Day (1A girls): top ten 7/7, four titles.
* Porterfield (2A boys): six State titles in seven seasons and top ten in six.

Those are genuine program factories in the data.

Springfield (6A boys) is the opposite kind of story: its 2080–2086 median class rank is **45**, with only one top-five season — this one, when it reached rank 4. That is a breakout, not yet a system.

De La Salle (9A girls) is even more extreme: seven-year median rank **69**, current rank 10.

## 12. Close-dual records still produce absurd mini-stories

Among programs with at least eight one-point duals:

* Valera (1A girls): **9–0**
* Emerson (6A girls): **8–0**
* Paddock Tech (2A girls): **8–0**
* Naylors Landing (Group 3 girls): 9–1
* Michaela East (4A boys): 8–1
* Hackensack (5A girls): 11–2

At the other extreme:

* Laurel Park (9A girls): **0–9**
* Silver Junction (Group 3 girls): 1–10
* Fontainebleau (4A girls): 1–9
* Indigo Rim (7A boys): 1–8
* Odellville (1A girls): **2–11**

I would not call this “clutch ability” from one season. But as universe lore, Valera (1A girls) never losing a one-point dual and Laurel Park (9A girls) never winning one are absolutely worth surfacing.

The major limitation is also clear now: the export contains full line-level data for **2086 only**, while the historical ledger contains season summaries. So true multi-year player-vs-player curses and career WAE cannot be reconstructed from this one ZIP. Program history can go longitudinal; player H2H cannot unless the prior season exports are also available.

I also packaged the actual derived tables rather than just describing them:

[Download the 2086 god-mode analysis tables](sandbox:/mnt/data/jhsaa-2086-godmode-analysis.zip)

That includes the nemesis pairs, player WAE, rating-gap upsets, program/flight residuals, coefficient anomalies, three-year rank swings, senior no-title candidates, tournament elevation, and one-point dual records.
