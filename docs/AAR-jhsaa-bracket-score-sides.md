# AAR — the bracket showed the winner losing, and half of it was right

**Reported** from a first real run, with a screenshot of the 2027 7A draw:

```
 1  Marcus Langston   3          16  Canal View     5
19  Mila Chernov      2  ← advances        24  Katya Moroz    0  ← advances
```

> "the team that won actually shows like a loss"

The advancing team was correct everywhere. The numbers beside it were not.

---

## 1. The shared bracket's score string is WINNER-FIRST, and nothing said so

`templates/_bracket.html` renders a card's score by splitting one string and picking a
half **by who won**:

```jinja
{{ m.score.split('-')[0] if t.won else m.score.split('-')[1] }}
```

The college callers build that string winner-first:

```python
"score": f"{max(hp, ap)}-{min(hp, ap)}"
```

The JHSAA, added later on the same shared tree, built it **positionally**:

```python
"score": f"{int(gm['home_points'])}-{int(gm['away_points'])}"
```

Those agree exactly when the home side wins, and swap the two numbers when the away side
does. So every card the home team won was right, and every card the away team won showed
each side the other's score.

That is why it survived being built, screenshotted during a design pass, reviewed and
merged: a bracket half-full of correct cards, where the wrong ones read as *upsets*. A
19-seed beating a 1-seed 3-2 is a story. It takes a second source — the school page,
which renders the same dual `at Marcus Langston · W 3-2` — to see that the number is
simply on the wrong side.

> An implicit contract between a shared component and its callers is fine until there is
> a second caller. `score` looked like "the score"; it was "the score, winner first", and
> the only place that fact existed was in the expression that consumed it.

The fix is one line in the JHSAA (emit `max-min`) plus the contract written down **at the
macro**, where the next caller will read it.

## 2. The same bug, one page over: line scores are home-first

The screenshot that identified the bracket bug also contained a second one, in the
expanded line detail of an away dual:

```
D1  Chauncey Batt / Beals Oluwaseyi   d.   Rafael Blanco / MaliVai Slater   3-6, 3-6
```

A pair marked as having won, with a score saying they lost both sets.

`jhsaa._score_str` writes set scores home-first. The school page correctly flips the
names, the `d.`/`l.` marker and the dual score for an away card — and left the set scores
alone.

**And my first fix for this was also wrong.** I flipped the numbers *for the away card*,
which makes the away card read correctly and the home card read the loser's games first
on every line the away side won. It passed its test because the test encoded the same
misunderstanding.

A tennis score is not a perspective. **It is always written from the winner's side** —
"6-4, 3-6, 7-5" belongs to whoever won, and the loser is named beside it, not counted in
it. Both teams' cards show the identical string; only the name order and the `d.`/`l.`
marker differ. `_jh_reported_lines` normalises on `home_won`, not on who is looking.

The engine had this right the whole time. `MatchResult.scoreline` is documented *"from
the winner's perspective"*, and the college league stores that and un-flips it with
`home_won` where it needs directional games. The JHSAA reimplemented the string rather
than using it, and reimplemented it wrong.

The stored JHSAA string stays home-first, and that divergence is now deliberate: seasons
are already archived that way, and re-reading them under a new convention would silently
misreport every away-won line — the same bug, moved into the past where nobody can see
it. Storage keeps the record; the report is normalised at the render.

> A domain convention is not a display preference. "Which side is this written from" had
> an answer in the sport before it had one in the code, and the engine already encoded it
> — the bug was reimplementing a value that existed rather than looking for it.

## 3. Why the tests did not catch either

Both are properties of the join between a value and a side, and every test in this area
asserted the value alone: the archive holds the right winner, the right points and the
right sets, and it always did. Nothing asserted *which team a number is printed beside*.

The regression tests are therefore built on a draw where the away side wins twice and the
home side wins once, so a fix that merely moves the swap to the other half still fails,
and — after the second mistake — on the line score being IDENTICAL from both cards rather
than merely correct from one. Cheap: 0.4s, no simulation, a hand-written four-team
bracket.

One of them pins the contract from the college side (`max-min` must stay in
`state.py`), because the failure mode is not "the JHSAA is wrong" — it is "the two
callers disagree", and either one drifting reintroduces it.

## Measured after the fix

* 198 archived state games across both genders and all five classifications: every card's
  displayed number equals that team's own points. Previously wrong on every game the away
  side won.
* 4,111 archived lines across both genders and all five classifications: every reported
  set score leads with the winner's games, and the two teams' cards agree exactly.

## Files

* `app/web/templates/_bracket.html` — the winner-first contract, stated at the macro
* `app/web/state.py` — `_jh_score`, `_jh_reported_lines`
* `tests/test_jhsaa_bracket_scores.py`
