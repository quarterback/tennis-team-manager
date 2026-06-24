# How Recruiting Class Rankings Are Scored

*Methodology for the team class rankings on the Signing Tracker.*

Two programs can both sign "a good class," but a flat star count can't tell them
apart — a blue-chip and a borderline 5★ both read as five stars, and a program can
pad its total by signing bodies. The class rankings instead score each commit on
**where they ranked nationally** and **how good they are**, then judge a class by
its **headliners**.

## Per recruit

```
RankScore    = sqrt(1000 / NationalRank)
StarValue    = 7 if Blue Chip, else the star count (5★→5, 4★→4, 3★→3, 2★→2, 1★→1)
RecruitScore = RankScore × STR × StarValue
```

- **RankScore** rewards national pedigree on a *softened* curve. The square root
  keeps the #1 recruit clearly the most valuable without letting one signing
  dominate a whole class:

  | National rank | RankScore |
  |---|---|
  | #1 | 31.6 |
  | #10 | 10.0 |
  | #100 | 3.2 |
  | #1000 | 1.0 |
  | #2500 | 0.6 |

  (A straight `100 / rank` would make #1 worth ~100× a #100; `sqrt(1000 / rank)`
  compresses that to ~10×, so depth and multiple elites matter.)

- **StarValue** gives blue-chips a premium over plain 5★ — the one thing a 1–5 star
  count can't express. Everyone else is worth their star count; unranked signees
  score zero.

- **STR** is the recruit's strength rating (the same number shown on their junior
  profile), so a higher-rated player of the same rank/stars is worth more.

## Per class

```
ClassScore = average RecruitScore of the program's TOP 3 recruits
```

Taking the **average of the top three** judges a class by its best signings, not by
how many names it collected. A program that lands two or three elites outranks one
that lands a single star and pads the rest; a deep class of mid-tier recruits sits
below both.

Classes are then ranked by ClassScore (ties broken by total stars, then name).

## Worked example

| Class | Top-3 commits | ClassScore |
|---|---|---|
| Two blue-chips + a 4★ | #2 BC, #9 BC, #40 4★ | **≈ 4,380** |
| One blue-chip + filler | #1 BC, then 2★ depth | ≈ 3,960 |
| Three 5★/4★ studs | #3 5★, #6 5★, #12 4★ | ≈ 3,310 |
| Eight-deep 3★ class | three mid-pack 3★ | far back |

Landing the literal #1 recruit still grades out near the top — but two or three
elites beat one elite and a pile of filler, which is the point.

## Where it lives

`app/web/state.py` — `_recruit_score()` (per recruit) and `signing_tracker()` (the
top-3 average + ranking). The rank-curve constant is `_RANK_SCORE_NUMERATOR = 1000`
(inside the square root) if the steepness ever needs tuning. Change history in
`docs/AAR-team-class-ranking-score.md`.
