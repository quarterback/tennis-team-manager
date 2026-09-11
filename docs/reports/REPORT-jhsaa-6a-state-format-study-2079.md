# JHSAA 6A State Format Study (2077–2079 data, six formats, two scoring variants)

**Question.** An analyst pass on the 2079 exports recommended a 6A 2S/3D pilot on the
strength of 6A's 60.3% one-point State rate. Should 6A move to 2S/3D, to some other
format, or stay on 1S/4D?

**Answer.** Nothing is broken in 6A, so nothing should be changed to fix it. If the
owner wants a 6A pilot for its own sake, the most interesting candidate is not 2S/3D but
the **consolidated doubles point** (4 singles + 3 doubles folded into one team point):
it is the only five-point format tested that changes who wins without changing how close
the duals are. Scoring length (pro sets, match tiebreaks) is not a lever at all.

Scripts: `scripts/jhsaa_export_state_anatomy.py` (section 1, reads the exports),
`scripts/jhsaa_6a_format_study.py` (section 2), `scripts/jhsaa_6a_format_study2.py`
(section 3).

---

## 1. The three seasons as played (exports 2077–2079, both genders)

State duals only, read off the archived brackets: seeds are field order, at-larges are
the committee's list, every dual joined to its box score by program key.

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

\* Group 2's figure is the 3-3 decider rate; an even-point dual has no one-point margin.

**6A by season and gender** — the 60.3% came from one of these six draws:

| | girls | boys |
|---|---:|---:|
| 2077 | 51% (champion seed 1) | 41% (1) |
| 2078 | 64% (1) | 36% (1) |
| 2079 | 67% (7) | 54% (12) |

At 39 duals a draw the standard error on a rate near 50% is about eight points. 6A runs
36% to 67% across its six draws, and 2A pools HIGHER on the same format. The 2079 girls'
67% is the top of a band, not a property of the class.

**Flight anatomy of the five-point classes** (every State dual, 2077–2079):

| class | n | S1 winner won the dual | D1 aligned | doubles sweep | one-point duals | one-point duals won by the S1 LOSER |
|---|---:|---:|---:|---:|---:|---:|
| 6A | 234 | 65.8% | 77.8% | 24.8% | 122 | 45.9% |
| 5A | 234 | 66.7% | 75.6% | 22.6% | 118 | 45.8% |
| 4A | 234 | 69.2% | 68.4% | 24.4% | 112 | 48.2% |
| 3A | 234 | 70.5% | 76.5% | 18.8% | 114 | 41.2% |
| 1A (2S/3D) | 186 | 73.7% | 76.9% | 36.0% | 87 | 39.1% (S2 aligned 72%) |

6A is not doubles-decided in any way its peers are not. Under 1S/4D the S1 winner takes
the dual about two times in three in every class, and in a 3-2 dual the S1 loser wins
just under half the time in every class. 1A shows what a second singles seat does: S1
alignment rises to 74% and the S1 loser wins fewer nail-biters. That is a change of
character, not of closeness.

---

## 2. Six shapes on 6A rosters (engine counterfactual)

Every 6A program (133), the shipped arrangers and fast engine, statewide
adjacent-strength pairings ("even") and top-half-vs-bottom-half pairings
("mismatched"), 10 matched seeds per pairing, 310–350 duals a cell. "Favourite" is the
side with the higher mean OVR over its top nine.

| set | format | on court | favourite wins | one-point | mean margin | same winner as 1S/4D |
|---|---|---:|---:|---:|---:|---:|
| girls even | 1S/4D | 9 | 51.1% | 69.7% | 1.70 / 5 | — |
| | 2S/3D | 8 | 56.0% | 71.4% | 1.65 / 5 | 67.1% |
| | 3S/2D | 7 | 55.1% | 66.0% | 1.77 / 5 | 61.7% |
| | 4S+3D→1pt | 10 | 59.7% | 64.0% | 1.78 / 5 | 59.4% |
| | 3S/4D | 11 | 54.9% | 62.9% | 1.93 / 7 | 70.0% |
| | 4S/5D | 14 | 53.1% | 48.9% | 2.41 / 9 | 64.9% |
| girls mismatched | 1S/4D | 9 | 87.1% | 32.0% | 3.18 / 5 | — |
| | 2S/3D | 8 | 86.9% | 30.3% | 3.25 / 5 | 90.0% |
| | 3S/2D | 7 | 83.7% | 29.1% | 3.31 / 5 | 89.7% |
| | 4S+3D→1pt | 10 | 88.3% | 29.7% | 3.28 / 5 | 87.4% |
| | 3S/4D | 11 | 86.9% | 21.4% | 4.45 / 7 | 88.9% |
| | 4S/5D | 14 | 90.6% | 21.4% | 5.26 / 9 | 86.9% |
| boys even | 1S/4D | 9 | 58.4% | 67.1% | 1.74 / 5 | — |
| | 2S/3D | 8 | 54.2% | 65.2% | 1.79 / 5 | 71.3% |
| | 3S/2D | 7 | 53.9% | 62.9% | 1.84 / 5 | 61.3% |
| | 4S+3D→1pt | 10 | 54.2% | 64.2% | 1.81 / 5 | 57.7% |
| | 3S/4D | 11 | 59.7% | 60.3% | 2.01 / 7 | 72.3% |
| | 4S/5D | 14 | 52.9% | 49.4% | 2.52 / 9 | 65.5% |
| boys mismatched | 1S/4D | 9 | 89.4% | 28.7% | 3.28 / 5 | — |
| | 2S/3D | 8 | 91.3% | 27.4% | 3.23 / 5 | 92.3% |
| | 3S/2D | 7 | 89.4% | 27.7% | 3.30 / 5 | 84.5% |
| | 4S+3D→1pt | 10 | 87.7% | 27.7% | 3.26 / 5 | 86.1% |
| | 3S/4D | 11 | 90.3% | 22.9% | 4.37 / 7 | 89.4% |
| | 4S/5D | 14 | 88.1% | 18.4% | 5.54 / 9 | 89.7% |

Participation: 2S/3D cuts the #9 player, who sits a mean 1.89 OVR behind the last player
who dresses; 3S/2D cuts two (gap 4.14); the consolidated format dresses ten; 3S/4D eleven;
4S/5D fourteen, which 6A's 19–22 roster band carries.

What it says:

- **2S/3D changes neither closeness nor chalk.** One-point rate within two points of
  1S/4D, favourite win rate within noise (the girls' +5 and boys' −4 are opposite signs
  at ~2.7 points standard error). Its whole effect is that a different team wins about
  30% of even duals and the No. 2 player gets a singles seat. That is the 1A finding
  again: closeness comes from court count, and 2S/3D keeps five courts.
- **3S/2D is 2S/3D with a shorter bench.** No case.
- **The consolidated doubles point is the odd one out, in the useful direction.** It
  keeps five-point closeness (64% one-point in even duals) but agrees with 1S/4D on the
  winner of an even dual only 58–59% of the time, the lowest of any five-point shape.
  It re-decides four even duals in ten because the doubles point is an aggregate of
  three matches rather than four independent lotteries. Favourite win rate unchanged
  within noise. It dresses ten and has real-world pedigree (the college D1 rule).
- **3S/4D through State behaves like every seven-court shape**: one-point rate down to
  60–63% even and 21–23% mismatched. The league format really is a different sport from
  the postseason one, so the mid-season showcases are not redundant.
- **4S/5D is what 7A already plays.** Moving 6A there erases the one difference between
  6A and 7A the association has been cultivating.

---

## 3. Scoring length, lineup held fixed (1S/4D)

High-school best-of-3 (today) against 8-game pro sets (the pod showcase's scoring) and
best-of-3 with a 10-point match tiebreak for the third set.

| set | scoring | favourite wins | one-point | mean margin | same winner as best-of-3 |
|---|---|---:|---:|---:|---:|
| girls even | best-of-3 | 51.1% | 69.7% | 1.70 / 5 | — |
| | pro set 8 | 53.1% | 67.4% | 1.72 / 5 | 69.4% |
| | 10-pt MTB | 51.4% | 63.7% | 1.81 / 5 | 67.7% |
| girls mismatched | best-of-3 | 87.1% | 32.0% | 3.18 / 5 | — |
| | pro set 8 | 84.9% | 29.7% | 3.17 / 5 | 86.9% |
| | 10-pt MTB | 82.9% | 31.1% | 3.13 / 5 | 88.9% |
| boys even | best-of-3 | 58.4% | 67.1% | 1.74 / 5 | — |
| | pro set 8 | 54.2% | 61.9% | 1.88 / 5 | 66.1% |
| | 10-pt MTB | 54.5% | 66.1% | 1.75 / 5 | 71.6% |
| boys mismatched | best-of-3 | 89.4% | 28.7% | 3.28 / 5 | — |
| | pro set 8 | 86.8% | 32.9% | 3.12 / 5 | 89.7% |
| | 10-pt MTB | 88.4% | 29.4% | 3.12 / 5 | 88.7% |

Shorter matches move the favourite's win rate down 2–4 points and the one-point rate by
1–6 points. The 1S/4D nail-biter rate is a lineup property, not a scoring property. There
is no format lever in the scoring axis, which also means pro sets are a safe way to
shorten a State weekend if that is ever wanted.

---

## 4. Recommendation

1. **Do not change 6A to fix a problem.** The 60.3% was one draw; three seasons say 6A
   is an ordinary 1S/4D class.
2. **If 6A pilots something, prefer the consolidated doubles point over 2S/3D.** It is
   the only five-point format that changes the competition without changing the
   closeness, it dresses ten, and it is a real format. Judge it on which teams win and
   on how the doubles point is contested, never on one-point rate or upset rate — those
   will not move, and a season confirming that is not a failed pilot.
3. **If 2S/3D is chosen anyway,** judge it on S1/S2 alignment and who holds the S2 seat,
   for the same reason.
4. **Do not move 6A to 4S/5D** unless the intent is to retire it as the largest
   five-point class.
5. **Leave 5A, 4A, 3A and 2A alone.** 2A pools the highest one-point rate on the format
   and nobody has proposed changing it; the same instinct applies to 6A.

**What the consolidated point would need.** The engine already scores it
(`DualFormat(doubles_team_point=True)`). The JHSAA side does not: the arrangers must
pool six for four singles seats, `_slot_players` and `_credit` must be told the shape,
TOSS needs a rule for a consolidated point (the flight score normalises by weight
contested, but a team point is not a flight), and the awards résumé must decide how one
team doubles point credits three pairs. A design job, not a membership change like 1A's.

## Caveats

- Section 1 is the owner's own data. Sections 2–3 use rosters generated on an empty
  override table at a fixed salt: 6A-shaped rosters, not the save's. They measure the
  formats, not a season.
- Differences under ~5 points between formats in sections 2–3 are noise at these
  sample sizes.
- The first attempt at the section-1 join matched 19 of 234 duals because the bracket
  uses display names and the duals table uses program keys; the shipped script joins
  through `programs.csv` and matches all 234.
