# AAR — a correct double round robin that no high school has ever played

**Reported** with a screenshot of a program's card, which is the only place it was
visible:

```
Mar 10  at Alder Landing            Mar 15  at Altamonte School of Commerce
Mar 12  vs Alder Landing            Mar 17  vs Altamonte School of Commerce
```

> "That is too mechanical and does not resemble how a high-school season should read."

Every card in the association read like that, for every opponent, all season.

---

## 1. The bug was three lines and none of them were wrong

```python
for i, a in enumerate(teams):
    for b in teams[i + 1:]:
        for leg in (0, 1):                      # home and away
```

That **is** a double round robin. Every opponent twice, once home and once away, every
pairing exactly once per leg. A test asserting "every league opponent exactly twice, one
home one away" passes. The league table is right. The point differentials are right.

What is wrong is a property nobody had written down: **when** the two meetings happen.
The loop plays them consecutively, so a season is eleven two-game series rather than two
passes through a league. No invariant caught it because no invariant described it, and
the sim has no calendar of its own to violate — a dual's POSITION in `schedule` is the
entire clock, and the display calendar (`state._jh_dates`) faithfully rendered a bad
order as bad dates.

> A schedule bug is a bug in an ORDER, and orders are the thing test suites are worst at
> describing. "Correct set of matches" and "correct sequence of matches" are different
> properties, and only the first one is obvious enough to assert by accident.

## 2. The fix: rounds, two passes, and a window between them

The league is now generated as **rounds** (`_rr_rounds`, the circle method — every team
plays exactly once per round), run forward as pass 1 and mirrored as pass 2 with the
venue flipped. `play_regular_season` plays each phase across the WHOLE gender before the
next begins, so every program's card stays in step:

```
early non-district → district pass 1 → mid-season window → district pass 2 → late tune-up
```

Because the order of play IS the schedule, this reordering is the entire fix. Nothing
about who plays whom changed, no dual was added or removed, and the season lengths are
identical (girls 14/28/35 duals min/median/max, boys 15/27/34).

## 3. ‼️ A plain `reversed()` is not the mirror, and it fails invisibly

The obvious second pass is the rounds backwards — the serpentine the report asked for,
A → B → … → G then G → … → B → A. I wrote it, and it was wrong at the fold: **reverse the
rounds and the last opponent of pass 1 becomes the first of pass 2.** Those two meetings
land on consecutive league dates. The bug being removed, reintroduced, for exactly one
opponent per team.

It is invisible on a rendered card. Eleven opponents beautifully spread across two
halves of a season, and one played twice in a row — which looks like an ordinary quirk
of a schedule unless you are measuring gaps. Measured on a 12-team district:

| | before | plain `reversed()` | shipped |
|---|---|---|---|
| closest two meetings | 1 round | **1 round** | **10 rounds** |
| same opponent back-to-back | 12 | **12** | **0** |

The fix is to stop guessing at the rotation and score it. `_mirror_orders` enumerates
every rotation of both families — serpentine (`rev`) and straight mirror (`fwd`) — scores
each by its **worst** pair, and keeps everything clearing half a pass:

| rounds per pass | best `fwd` | best `rev` | floor | variants kept |
|---|---|---|---|---|
| 5 | 5 | 3 | 3 | 5 |
| 7 | 7 | 4 | 4 | 6 |
| 11 | 11 | 6 | 6 | 8 |

`district_rounds` draws one on the season seed, so a program's opponent order genuinely
differs year to year — the report explicitly allowed that ("does not need to be a perfect
reverse every season") — while the separation floor never moves.

> When the obvious structure has one bad case, do not special-case it. Enumerate the
> structures, measure the property you actually want, and keep the ones that clear it.
> That also gets the year-to-year variety for free, because there is now a *band* of
> acceptable answers instead of one.

## 4. Venue is one bit per PAIRING, not per meeting

Two constraints wanted the same knob: "the second meeting reverses venue" and "no long
runs of home or road dates". Held as a per-meeting home flag they fight — any run repair
can flip a meeting and silently break the reversal.

Held as **one orientation bit per pairing**, where pass 2 is defined as its inverse, they
cannot. The reversal is true by construction; `_orient` flips bits to shorten runs and
has no way to express the broken state. Result: longest home/away run 3, perfect
home/away balance, and a reversal property that needs no defending.

> If two invariants contend for the same variable, look for a representation in which one
> of them is unstateable rather than a checker that catches the violation afterwards.

## 5. The mid-season challenge is a LABEL, not a phase

The one pairing in the association that reads results. It is drawn AFTER pass 1 on
district record, so a #3 meets another district's #3 — which is the whole idea, and the
reason it cannot live in the early window. Everything else about non-district pairing
still seeds on roster strength precisely so it can run before any results exist.

The implementation temptation was `phase="challenge"`. That would have been quietly
destructive: `dual_format(phase)` would have handed it the regular shape by luck, but
`rating_duals` filters on `phase`, and the whole point of playing a strong cross-district
opponent is that it counts toward TOSS. So it is a `challenge` boolean beside
`district=False` — a label on an ordinary non-district dual, structurally unable to reach
a district table.

> Before adding a value to an enum, grep who branches on that enum. A phase is not a tag.

## 6. The existing test asserted the bug

`tests/test_jhsaa_schedule.py` already had:

```python
def test_non_district_duals_are_played_before_league_play(played):
    flags = [x["district"] for x in _regular(t)]
    assert flags == sorted(flags)        # all False, then all True
```

Correct when written, and exactly what the new season shape must violate — a mid-season
window is a `False` between two `True`s. It was the stale side, as CLAUDE.md's own rule
warns ("a failing test is NOT proof the code is wrong"), and it is now the inverse
assertion: every card opens non-district AND has a non-district group between league
dates.

The fixture also called `jhsaa._crossover`, which no longer exists. Rather than
re-implement the ordering in the test — which would have tested the re-implementation —
the orchestration was extracted to `play_regular_season(by_group, ...)`, which takes a
subset of districts. The tests run the shipped path on four districts in 4.3s.

Covering, per the report: opponent counts, venue reversal on the later date, no
consecutive dates, separation as a share of the card, venue balance and run length, the
windows surviving, the challenge never reaching district records, and seed
reproducibility.

## 7. Two follow-ups the review caught, and they are the same shape as §3

**The seed carried a position.** `play_rounds` hashed the local round and seat index into
the dual seed. Harmless while the list was played straight through — and the whole point
of this change is that it no longer is. `play_regular_season` plays `rounds[:half]`, runs
the window, then `rounds[half:]`, and the second call's `enumerate` restarts at zero, so
every second-pass dual seeded differently from the same district played through by
`play_district`. Identical inputs, different results, in a sim whose contract is that a
save seed reproduces a season. The ordered `(home, away)` pair is already unique in a
double round robin — each unordered pair meets twice with the venue reversed — so the
index was never carrying information, only coupling.

**The margin carried the wrong duals.** `points_for`/`points_against` accumulate over
EVERY dual, non-district included. Both the old district tiebreak and the challenge's
provisional rank used that difference while being documented as league-only, so a
February blowout against another district could decide a district title. Fixed at the
source: every league figure is now read off the district schedule entries.

> Both are the §3 failure again — a value that is correct in one context silently reused
> in another where it means something else. A round index means nothing once the list is
> sliced; a season margin means nothing once it is labelled "district".

## 8. The tiebreak ladder

Place is district win %, then (owner rule 2027-08): head-to-head among the tied teams →
the aggregate of those meetings → overall season record → Power Index → OOWP.

Two implementation notes worth keeping. A tie is resolved as a **group**, not pairwise:
head-to-head among three level teams is a mini-league, and a pairwise comparator on a
rock-paper-scissors tie is not transitive, so the answer would depend on the input order.
And settling had to move **after** the Power Index is computed, because rung 4 reads it —
`play_regular_season` now computes TOSS over the whole gender as its last act and hands
it back, so `run_season` does not recompute a ~5,000-dual rating it already has.

On a real season, 88 teams across 30 districts needed the ladder — it is not a
theoretical rung.

## What did NOT change

Season length, district sizes, the non-district allowance, opponent selection (geography
→ talent → availability, gated to one classification), TOSS, seeding, the state draw, and
the display layer. The card renders through the same three segment kinds it always had.

## Files

* `app/jhsaa.py` — `_rr_rounds`, `_mirror_orders`, `_venue_cost`, `_orient`,
  `district_rounds`, `play_rounds`, `settle_district`, `play_regular_season`,
  `_nondistrict_pairs`, `_challenge_pairs`
* `tests/test_jhsaa_schedule.py`
