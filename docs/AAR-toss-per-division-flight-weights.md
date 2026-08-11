# AAR — the Power Index had no weights for two thirds of a D1 lineup

**Asked:** "never realized we hadn't adjusted TOSS to work for the other formats of
tennis in the game, is that worth doing?" — after TOSS went into the JHSAA, which is
what surfaced it.

It was worth doing. The rating had been scoring courts it had no opinion about for a
release, silently, and getting the bottom half of a D1 dual **backwards**.

---

## 1. The bug: one fallback, 26% of a dual

`app/rating.py` carried a single flight-weight table:

```python
FLIGHT_WEIGHTS = {
    "S1": 1.00, "S2": 0.85, "S3": 0.60, "S4": 0.45, "S5": 0.30, "S6": 0.20,
    "D1": 0.80, "D2": 0.50, "D3": 0.30,
}
```

That is the engine's **CLASSIC 6+3** — what a bare `simulate_dual` plays, what the cups
and the tests use. It is not what any division plays. Per-division dual formats landed a
release earlier (`ncaa.DUAL_FORMATS`, owner rule 2027-07):

| | Singles | Doubles | Doubles points |
|---|---|---|---|
| D1 | 10 | 5 | all five consolidate into **one** team point |
| D2 / D3 | 8 | 3 | each doubles line is its own point |
| D4 | 10 | 3 | each doubles line is its own point |

The rating never followed. Every court the table didn't name fell through this:

```python
w = w_table.get(ln["slot"], 0.3)
```

In a D1 dual that is #7–#10 singles and #4–#5 doubles — **1.80 of 6.80 total flight
weight, 26%**, set by a number nobody chose. And because #6 singles was *deliberately*
weighted 0.20 while #7 through #10 each defaulted to 0.30, the index ran **backwards
across the bottom half of every D1 lineup**: a #10 singles court counted **1.5× a #6**.

Nothing failed. FQI stayed in range, the rankings table looked plausible, the bracket
seeded, the season played out. That is the whole hazard: **a rating model cannot tell
you it is measuring the wrong thing.** There is no assertion to trip and no output that
looks obviously wrong, because the output is a number between 0 and 1 either way.

## 2. Two kinds of default, and only one of them is fine

The fallback got there honestly. When TOSS was ported into the JHSAA, `_flight_score`
grew a `weights` parameter so a 5S/2D dual could be scored by a 5S/2D table:

```python
def _flight_score(lines, side, weights=None):
    w_table = FLIGHT_WEIGHTS if weights is None else weights
```

That default is **compatibility**: it preserves the behaviour of the caller that already
existed, it is checkable against the old code, and it is correct.

`.get(slot, 0.3)` is a **judgement** default. It answers "what is a #9 singles court
worth?" on behalf of someone who never considered the question, and it answers it the
same way for every format forever. It predates the port — it was there when the table
covered every court that existed — and it survived the format redesign precisely because
it made the redesign not break anything.

> A default that keeps an existing caller working is a compatibility decision.
> A default that supplies a value nobody chose is a judgement, and it should be a
> `raise`. The two look identical in a diff.

So there is no fallback now. An unrecognised flight raises, naming the table it wasn't
in. Threading `weights_for(division)` through the nine rating call sites was the mechanical
half; `weights_for` also raises on a division nobody has weighted, so adding a fifth
division cannot quietly inherit a fourth's judgement about a #7 singles court.

## 3. The tables

Owner-supplied, one per format, and the shape of each is an argument about the sport:

* **D1** suppresses doubles hard (D1 0.40 down to D5 0.05). Winning all five doubles is
  worth one point of eleven, so it cannot carry the weight five singles courts do.
* **D2/D3** and **D4** keep full doubles weight (D1 0.80, D2 0.50, D3 0.25) because every
  doubles line is its own point.
* Singles decay monotonically in all four, steeply through the depth courts — which is
  the actual fix for depth-farming.

Verified mechanically rather than by eye: for each division, the table's keys are exactly
the format's slots (no missing, no extra) and singles weights are monotonically
non-increasing.

## 4. What it did — measure the seeds, not just the cutline

One season simulated per division × gender (seed 9100), advanced to the selection window,
then the **real** selection path run twice over the same results — old table with the
fallback, new per-division tables. Everything downstream is shipped code:
`compute_ratings`, `committee_seed_score`, `select_field`, `regions.scurve_regions`.

| | rated | field | PI rank changed | mean Δ | max Δ | seed changed | ≥ 4 lines | region changed |
|---|---|---|---|---|---|---|---|---|
| D1 men | 383 | 96 | 353 (92%) | 5.2 | 24 | 59 (61%) | 19 | 51 (53%) |
| D1 women | 383 | 96 | 347 (91%) | 5.0 | 23 | 62 (65%) | 25 | 50 (52%) |
| D2 men | 324 | 64 | 265 (82%) | 2.5 | 10 | 30 (47%) | 1 | 21 (33%) |
| D2 women | 324 | 64 | 257 (79%) | 2.5 | 15 | 26 (41%) | 3 | 18 (28%) |
| D3 men | 233 | 64 | 150 (64%) | 1.1 | 5 | 32 (50%) | 5 | 27 (42%) |
| D3 women | 238 | 64 | 173 (73%) | 1.3 | 7 | 29 (45%) | 2 | 23 (36%) |
| D4 men | 191 | 64 | 161 (84%) | 2.0 | 10 | 36 (56%) | 5 | 29 (45%) |
| D4 women | 196 | 64 | 153 (78%) | 2.4 | 13 | 39 (61%) | 5 | 32 (50%) |

**The magnitude tracks how much of each format the fallback was guessing at** — which is
the confirmation that matters, because it is a prediction the diagnosis makes and a
generic "we changed some numbers and things moved" would not. D1 had four unweighted
singles courts *and* two unweighted doubles, and moved most. D2/D3, with only #7 and #8
falling through, moved least. D4 sits between: ten singles like D1, but its doubles were
already weighted.

Across 576 field slots, **seven** teams changed places — one per tournament, all at the
last seed line, none at all in D3 women:

| | in | out |
|---|---|---|
| D1 men | Johns Hopkins (73) | Arizona State (was 78) |
| D1 women | Kentucky (73) | Johns Hopkins (was 78) |
| D2 men | Albany State (55) | Colorado Mesa (was 54) |
| D2 women | Maryville (55) | Rockhurst (was 55) |
| D3 men | TCNJ (53) | SUNY New Paltz (was 51) |
| D3 women | — | — |
| D4 men | Colorado College (58) | Emerson (was 59) |
| D4 women | Babson (53) | Bates (was 53) |

## 5. ‼️ The lesson: the cutline is the wrong instrument

Seven cutline swaps. **313 of 576 seats changed seed** and **251 changed region.**

That gap is a property of the selection design, not of the rating.
`committee_seed_score` is 45% Power Index **rank** + 30% ITA résumé points + 15%
automatic-bid pedigree + 10% recent form. A five-place move inside a 383-team table
barely nudges a 0–100 rank score, and conference champions are in regardless of it. So
the rating was wrong almost entirely in **where teams were placed**, not in **who was
placed**.

> **A model can be badly wrong and still pick nearly the right field**, because the field
> is mostly decided by inputs it doesn't touch. Validating a rating change against
> "did the tournament field change" is measuring through the component that dilutes it.

Had I only checked membership, a bug that inverted the bottom half of every D1 lineup
would have reported as one team in and one team out — a rounding error. The seeds and the
S-curve are the sensitive instrument here; the cutline is the insensitive one. When
validating a change to an input, look at the surface **closest** to it, not the one the
user happens to care most about.

Corollary, and the reason this AAR has a table at all: **the pre-change behaviour has to
be runnable.** The measurement worked because the old code path could be reconstructed
exactly — restore `FLIGHT_WEIGHTS` as the default and put the `0.30` back inside
`_flight_score` — and then the *shipped* selection path run over *identical* simulated
results. A re-implementation of selection would have measured my re-implementation.

## 6. Related, from the same pass — archive at full precision

The JHSAA seeds on this same index, and archived it `round(pi, 6)`. Harmless-looking:
nothing displays more than three decimals. But `qualifiers()` seeds on the raw value
while `world.jhsaa_group_ranking` re-sorts the **stored** one and breaks ties by school
name, so any two teams inside 1e-6 collapse and the published ranking starts
contradicting the seeds it exists to explain. Measured closest gap in a three-season
fixture: **1.77e-06** — inside a factor of two of the threshold.

> Rounding is a property of a **view**. It does not belong in a store whose job is to
> reproduce a decision. Same family as the NCAA region drift
> (`docs/AAR-ncaa-bracket-region-drift.md`): if a number is going to be read back to
> justify a choice, persist the number the choice was actually made on.

## Files

* `app/rating.py` — `DIVISION_WEIGHTS`, `weights_for`, `_flight_score` raises
* `app/seasonmode.py`, `app/season.py` — `weights_for(division)` at the rating call sites
* `app/jhsaa.py` — full-precision `pi` on the archived standings rows
* `scripts/toss_weight_impact.py` — the harness that produced §4, kept runnable
* `docs/BLOG-toss-in-a-third-format.md` — the same material written for publication
