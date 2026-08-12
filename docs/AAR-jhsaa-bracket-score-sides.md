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
names, the `d.`/`l.` marker and the dual score for an away card (`mine = home_points if
is_home else away_points`) — and left the set scores alone. `_jh_side_lines` now flips
them with everything else, copying rather than editing, because `play_dual` appends the
**same** `lines` list to both teams' schedules and an in-place flip would corrupt the
opponent's card.

> When a view flips perspective, flip EVERY field that carries one. Three of the four
> were flipped here, and the fourth was the only one made of numbers rather than names —
> the one where being wrong is hardest to notice.

## 3. Why the tests did not catch either

Both are properties of the join between a value and a side, and every test in this area
asserted the value alone: the archive holds the right winner, the right points and the
right sets, and it always did. Nothing asserted *which team a number is printed beside*.

The regression tests are therefore built on a draw where the away side wins twice and the
home side wins once, so a fix that merely moves the swap to the other half still fails,
and on the pure perspective flip in both directions. Cheap — 0.2s, no simulation, a
hand-written four-team bracket.

One of them pins the contract from the college side (`max-min` must stay in
`state.py`), because the failure mode is not "the JHSAA is wrong" — it is "the two
callers disagree", and either one drifting reintroduces it.

## Measured after the fix

* 198 archived state games across both genders and all five classifications: every card's
  displayed number equals that team's own points. Previously wrong on every game the away
  side won.
* 456 archived lines: the set scores agree with the side shown winning, from both
  perspectives.

## Files

* `app/web/templates/_bracket.html` — the winner-first contract, stated at the macro
* `app/web/state.py` — `_jh_score`, `_jh_side_lines`
* `tests/test_jhsaa_bracket_scores.py`
