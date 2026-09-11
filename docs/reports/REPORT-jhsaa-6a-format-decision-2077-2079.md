# REPORT — should 6A leave 1S/4D? The 2077-2079 State data and a four-format counterfactual

**Question (owner, 2026-09):** an analyst pass on the 2079 exports recommended a 6A 2S/3D
pilot on the strength of 6A's 60.3% one-point State rate. Decide whether to run the 2S/3D
pilot in 6A, some other format, or nothing.

**Answer: the data does not support changing 6A's format to fix anything, because nothing
is broken.** 6A's 2079 rate was one season of one gender's 39 duals. Pooled over three
seasons and both genders 6A sits inside the 1S/4D band with 5A, 4A, 3A and 2A, and its
flight anatomy is indistinguishable from theirs. The engine counterfactual then shows
2S/3D would not move closeness or chalk in 6A at all; what it changes is WHICH team wins
~30% of even duals and which player holds the second singles seat. That is a stylistic
choice, and the report says what it would buy if the owner wants it for its own sake.

## 1. What the three seasons actually say (exports 2077-2079, both genders)

State duals only, read off the archived brackets (seeds = field order, at-larges as the
committee named them), 234 duals per 40-field class.

| class | format | duals | one-point | lower seed wins | at-large wins | champion seeds (6 titles) |
|---|---|---:|---:|---:|---:|---|
| 9A | 4S/5D | 282 | 37.6% | 34.0% | 28.9% | 3 3 5 7 9 9 |
| 8A | 4S/5D | 282 | 35.1% | 30.1% | 36.4% | 1 1 1 1 2 5 |
| 7A | 4S/5D | 234 | 32.1% | 27.8% | 35.1% | 1 1 1 2 2 10 |
| **6A** | **1S/4D** | **234** | **52.1%** | **29.1%** | **36.8%** | **1 1 1 1 7 12** |
| 5A | 1S/4D | 234 | 50.4% | 34.2% | 43.5% | 1 1 2 3 3 12 |
| 4A | 1S/4D | 234 | 47.9% | 32.5% | 33.3% | 1 1 1 2 10 10 |
| 3A | 1S/4D | 234 | 48.7% | 25.6% | 30.4% | 1 2 2 6 6 9 |
| 2A | 1S/4D | 234 | 53.8% | 31.2% | 41.5% | 1 1 1 2 3 3 |
| 1A | 2S/3D | 186 | 46.8% | 36.0% | 31.4% | 1 1 1 3 5 15 |
| Group 1 | 4S/5D | 282 | 41.1% | 35.8% | 37.7% | 1 1 1 2 2 10 |
| Group 2 | 3S/3D | 186 | 18.3%* | 20.4% | 0.0% | 1 1 1 1 1 3 |
| Group 3 | 1S/4D | 162 | 49.4% | 40.1% | 54.7% | 1 2 3 3 4 4 |

\* Group 2's figure is the 3-3 decider rate (an even-point dual has no one-point margin).

**6A by season and gender**, which is the number the 60.3% came from:

| | girls | boys |
|---|---:|---:|
| 2077 | 51% (champion seed 1) | 41% (1) |
| 2078 | 64% (1) | 36% (1) |
| 2079 | 67% (7) | 54% (12) |

At 39 duals a draw, the standard error on a one-point rate near 50% is about eight
points. 6A's six draws run 36% to 67%; 2A, on the same format, pools HIGHER than 6A. The
2079 6A girls' 67% is the top of the band, not a property of the class.

**Flight anatomy of the five-point classes** (every State dual joined to its box score):

| class | n | S1 winner won the dual | D1 aligned with dual | doubles sweep | one-point duals | one-point duals won by the S1 LOSER |
|---|---:|---:|---:|---:|---:|---:|
| 6A | 234 | 65.8% | 77.8% | 24.8% | 122 | 45.9% |
| 5A | 234 | 66.7% | 75.6% | 22.6% | 118 | 45.8% |
| 4A | 234 | 69.2% | 68.4% | 24.4% | 112 | 48.2% |
| 3A | 234 | 70.5% | 76.5% | 18.8% | 114 | 41.2% |
| 1A (2S/3D) | 186 | 73.7% | 76.9% | 36.0% | 87 | 39.1% (S2 aligned 72%) |

6A is not doubles-decided in any way its peers are not. Under 1S/4D the S1 winner takes
the dual about two times in three everywhere, and in a 3-2 dual the team that lost S1 won
it just under half the time everywhere. 1A's 2S/3D shows what a second singles seat
does: S1 alignment rises to 74% and the S1 loser wins fewer nail-biters (39%) — the
singles ladder decides more. That is the real effect of the pilot format, and it is a
change of character, not of closeness.

## 2. What a format change would do in 6A (engine counterfactual)

`scripts/jhsaa_6a_format_study.py`: every 6A program (133), the shipped arrangers and the
shipped fast engine, statewide adjacent-strength pairings and top-half-vs-bottom-half
pairings, 10 matched seeds per pairing, four shapes. Rosters generated on an empty
override table at a fixed salt — a measurement of the FORMATS on 6A-shaped rosters, not a
replay of the owner's save.

| set | format | favourite wins | one-point | mean margin | same winner as 1S/4D |
|---|---|---:|---:|---:|---:|
| girls even (350) | 1S/4D | 51.1% | 69.7% | 1.70 / 5 | — |
| | 2S/3D | 56.0% | 71.4% | 1.65 / 5 | 67.1% |
| | 3S/2D | 55.1% | 66.0% | 1.77 / 5 | 61.7% |
| | 4S/5D | 53.1% | 48.9% | 2.41 / 9 | 64.9% |
| girls mismatched (350) | 1S/4D | 87.1% | 32.0% | 3.18 / 5 | — |
| | 2S/3D | 86.9% | 30.3% | 3.25 / 5 | 90.0% |
| | 3S/2D | 83.7% | 29.1% | 3.31 / 5 | 89.7% |
| | 4S/5D | 90.6% | 21.4% | 5.26 / 9 | 86.9% |
| boys even (310) | 1S/4D | 58.4% | 67.1% | 1.74 / 5 | — |
| | 2S/3D | 54.2% | 65.2% | 1.79 / 5 | 71.3% |
| | 3S/2D | 53.9% | 62.9% | 1.84 / 5 | 61.3% |
| | 4S/5D | 52.9% | 49.4% | 2.52 / 9 | 65.5% |
| boys mismatched (310) | 1S/4D | 89.4% | 28.7% | 3.28 / 5 | — |
| | 2S/3D | 91.3% | 27.4% | 3.23 / 5 | 92.3% |
| | 3S/2D | 89.4% | 27.7% | 3.30 / 5 | 84.5% |
| | 4S/5D | 88.1% | 18.4% | 5.54 / 9 | 89.7% |

Participation: 2S/3D dresses 8 and cuts the #9 player, who sits a mean 1.89 OVR behind
the last player who does dress; 3S/2D dresses 7 and cuts two (gap 4.14); 4S/5D dresses
14, which 6A's 19-22 roster band carries.

Reading it:

- **2S/3D changes neither closeness nor chalk.** One-point rate ±2 points, favourite
  win rate within noise (the 51→56 and 58→54 swings are opposite signs at ~2.7 points
  standard error). This is the 1A study's finding again: closeness comes from court
  count, and 2S/3D holds five courts. Its whole effect is that a different team wins
  about 30% of even duals and the No. 2 player gets a singles seat.
- **3S/2D is 2S/3D with a shorter bench** and slightly fewer nail-biters. No case.
- **4S/5D is the only format that changes the competitive character** — one-point rate
  falls twenty points and the margin widens, exactly what 7A/8A/9A already show in the
  real data. Moving 6A there would make it the fourth wide class and erase the one
  difference between 6A and 7A that the owner has been cultivating.

## 3. Recommendation

1. **Do not change 6A to fix a problem.** There is no problem. The 60.3% was one draw.
2. **If 6A is to pilot 2S/3D, do it for what it actually does** — make the second singles
   position consequential and let the singles ladder decide more nail-biters — and judge
   it on those measures (S1/S2 alignment, who holds S2, which teams win even duals), never
   on one-point rate or upset rate, because the engine says those will not move and a
   season that shows them "not moving" is not a failed pilot. The code path already
   exists (`dual_format(phase, group)` and `_arrange_1a_postseason`); membership is the
   whole change, and the AAR for 1A's pilot lists the traps (`_slot_players` must be told
   the shape; the TOC entry reverts to 1S/4D).
3. **Do not move 6A to 4S/5D** unless the intent is to retire 6A's identity as the largest
   five-point class.
4. **Leave 5A, 4A, 3A and 2A alone**, and note 2A pools the highest one-point rate on the
   format — nobody has proposed changing 2A, which is the right instinct and the same
   instinct should apply to 6A.
5. The analyst's other 2080 items (at-large re-seeding as a replay, Group 3 at four bids,
   Group 2 graduating from pilot, the committee court-share diagnostic) are not
   contradicted by anything here and are outside this report's question.

## Method notes and caveats

- Part 1 reads the archived brackets in `jhsaa_championships.json` (seeds are field
  order, at-larges the committee's list) and joins each State dual to `duals.csv` and
  `lines.csv` by PROGRAM KEY through `programs.csv` — the key is the roster identity
  (`San Cordero East|girls`), the bracket names are display names (`Cordero Junction`),
  and a join on names silently matched 19 of 234 duals on the first attempt.
  `scripts/jhsaa_export_state_anatomy.py`.
- Part 2's rosters are not the owner's: an empty override table (no editable archetypes,
  transfers or families) and a fixed salt, with every era gate at zero. It measures how
  the four shapes behave on rosters generated the way 6A's are, which is the quantity the
  decision needs; it does not reproduce a particular season. Ten trials per pairing gives
  310-350 duals a cell; differences under ~5 points between formats are noise.
- "Favourite" in Part 2 is the side with the higher mean OVR over its top nine, not a
  seed. Seed fidelity in Part 1 is the archived seed.
