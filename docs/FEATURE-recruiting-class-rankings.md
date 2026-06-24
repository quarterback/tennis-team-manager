# How Recruiting Class Rankings Are Scored

*Methodology for the team class rankings on the Signing Tracker.*

Two programs can both sign "a good class," but a flat star count can't tell them
apart — a blue-chip and a borderline 5★ both read as five stars, and a program can
pad its total by signing bodies. The class score instead judges a program by its
**top three recruits**, on two axes at once: **how good they are** (combined STR)
and **how highly regarded they are** (average national rank).

## The formula

```
Take the program's TOP 3 recruits by national rank.
ClassScore = 0.1 × Σ STR(top3) × sqrt(1000 / average rank(top3))
```

- **Σ STR** — the combined strength of the three headliners. Summing (not
  averaging) rewards landing *three* strong players over one strong player and
  filler; a class with fewer than three signees just sums what it has.
- **sqrt(1000 / average rank)** — how highly the trio is regarded, on a softened
  curve (#1 → 31.6, #10 → 10, #100 → 3.2). Using the *average* rank means a single
  superstar can't carry a class on his own — a low-ranked third commit pulls the
  whole class down.
- **× 0.1** — purely cosmetic, to land scores on a ~100 scale. A strong class
  clears 100; weak ones sit in the tens. Nothing caps it — an elite class can run
  well over 100.

Classes rank by ClassScore (ties broken by total stars, then name).

Why both axes: STR alone barely separates recruits (they all sit in a tight ~49–53
band), and rank alone ignores that a deeper class is genuinely better. Combining
combined-STR with average-rank lets a deep, high-STR class out-point a one-star
class — which a flat star count or a single-headliner metric can't.

## Worked example

Three D1-women classes the old flat **Star Pts** metric couldn't tell apart
(Arizona State and Ole Miss both had three 5★ → "15"):

| Class | Top-3 (rank @ STR) | Σ STR | avg rank | ClassScore |
|---|---|---|---|---|
| **Arizona State** | #8 @ 52.2, #18 @ 51.4, #29 @ 52.7 | 156.3 | 18.3 | **115.4** |
| Ole Miss | #3 @ 53.1, #21 @ 50.9, #80 @ 49.6 | 153.6 | 34.7 | 82.5 |
| Colorado | #22 @ 50.9 (one commit) | 50.9 | 22.0 | 34.3 |

Arizona State's three Top-30 signees outscore Ole Miss even though Ole Miss landed
the higher individual recruit (#3) — the #80 third commit drags Ole's average rank
down, and ASU's depth + slightly better STR wins. A one-commit class sits well
below both. (Earlier "edges ahead" framing from a per-recruit-average draft no
longer applies; this is the chosen depth-first scoring.)

## Where it lives

`app/web/state.py` — `_class_score()` (the formula) and `_top3()`, used by both
`signing_tracker()` (league rankings) and `team_recruiting_class()` (the per-team
page). Tunables: `_CLASS_SCORE_SCALE = 0.1` (the ~100-scale factor) and
`_RANK_SCORE_NUMERATOR = 1000` (inside the square root). Change history in
`docs/AAR-team-class-ranking-score.md`.
