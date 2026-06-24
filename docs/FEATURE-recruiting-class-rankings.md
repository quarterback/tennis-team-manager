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
RecruitScore = RankScore × STR
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

- **STR** is the recruit's strength rating (the same number shown on their junior
  profile), so a higher-rated player of the same rank is worth more. Rank and STR
  already track ability, so the score needs no extra star multiplier — the gaps
  stay smooth and a deep class of strong recruits isn't dwarfed by one superstar.

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

Three D1-women classes that the old flat **Star Pts** metric couldn't tell apart
(Arizona State and Ole Miss both had three 5★ → "15"):

| Class | Top-3 commits (rank @ STR) | Per-recruit | ClassScore |
|---|---|---|---|
| Ole Miss | #3 @ 53.1, #21 @ 50.9, #80 @ 49.6 | 969 / 351 / 175 | **499** |
| Arizona State | #8 @ 52.2, #18 @ 51.4, #29 @ 52.7 | 584 / 383 / 309 | 425 |
| Colorado | #22 @ 50.9 (one commit) | 343 | 343 |

Ole Miss edges Arizona State on the strength of its #3-ranked headliner, and a
one-commit class sits below both — distinctions the star count flattened to a tie.

## Where it lives

`app/web/state.py` — `_recruit_score()` (per recruit) and `signing_tracker()` (the
top-3 average + ranking). The rank-curve constant is `_RANK_SCORE_NUMERATOR = 1000`
(inside the square root) if the steepness ever needs tuning. Change history in
`docs/AAR-team-class-ranking-score.md`.
