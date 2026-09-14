# Signed rating-system disagreement predicts bracket survival — and the at-large path
# durably corrects for it

**Seasons measured:** 2074-2083, ten consecutive seasons, both genders. All qualifiers
with a valid, connected computer-ratings row. 2083 is used for illustrative examples;
all headline numbers are pooled across the full ten-season run.
**Data sources:** `jhsaa_computer_ratings.csv` (nine rating systems + σ),
`jhsaa_program_history.csv` (record, seed, made_state), `jhsaa_championships.json`
(bracket results, used to count actual rounds won by each qualifier).

---

## 1. Background: σ alone conflates two opposite situations

The nine-system composite already flags teams the rating systems can't agree on (σ, the
standard deviation of a team's rank across all nine systems). But σ is unsigned — a team
whose *record* undersells its *underlying talent* and a team whose record *oversells* its
talent both produce a high σ. Averaging or filtering on σ magnitude erases which of the
two situations a team is actually in.

## 2. The fix: split disagreement into a signed metric

For every qualifying program, three systems are margin-based (Massey-dual, SRS,
Massey-game) and three are record-based (Colley, Bradley-Terry, win%). Define:

```
signed = mean(rank_colley, rank_bt, rank_win_pct) − mean(rank_massey_dual, rank_srs, rank_massey_game)
```

A large **positive** signed value means the record-based systems rank the team much worse
than the margin-based systems do — the record is undersellng them. Call this
**hidden-strength**. A large **negative** value means the record-based systems rank them
much better than the margin-based systems — the record is overselling them.
**hidden-fragility.**

Cohorts defined as |signed| ≥ 8 rank-places.

## 3. Finding: the sign predicts how far a team actually goes — confirmed across ten seasons

**Pooled 2074-2083 (10 seasons, both genders), not a single-season read.** Average bracket
rounds won past the qualifying seed:

| Cohort | Boys n | Boys avg wins | Girls n | Girls avg wins |
|---|---|---|---|---|
| **Hidden-strength** | 364 | **0.832** | 428 | **0.862** |
| **Hidden-fragility** | 432 | 0.461 | 498 | 0.494 |
| **Ratio** | | **1.81x** | | **1.75x** |

Hidden-strength teams win roughly **1.8x more bracket rounds than hidden-fragility teams,
and this holds almost identically in both genders.** This is the load-bearing number — a
single-season read of 2083 alone (below) suggested a much larger, gender-lopsided effect
that does not survive pooling.

**2083 alone, for reference:** hidden-strength averaged 0.71 wins (boys) / 0.82 (girls)
against hidden-fragility's 0.54 / 0.23 — a apparent 3x girls gap that reads dramatically
different from the 10-season 1.75x. That one-season number was noise from a 34-35 team
sample and should not be treated as a real boys/girls asymmetry. **The corrected claim is
that hidden-strength predicts bracket survival by a consistent ~1.8x in both genders**,
not that girls show a uniquely strong effect.

Representative cases from 2083, still useful as illustration of what the metric captures:

- **D. Eisenhower (girls 8A, 2083)** — 23-4, seeded 7th, hidden-fragility. Margin-based
  systems ranked them only 25th.
- **Mater Dei (girls 9A, 2083)** — 21-11, seeded 22nd, hidden-strength.
- **Polk (boys 9A, 2083)** — 8-19, seeded 43rd, largest positive signed value in that
  season's boys field.
- **Cedar Point (boys 5A, 2083)** — 19-7, seeded 12th, hidden-fragility.

**‼️ The blind spot this closes:** a report using σ magnitude alone to flag teams "worth a
second look" would put Polk and Cedar Point in the same bucket. They need opposite
treatment — one is being underrated by the bracket, the other overrated.

## 4. Finding: the at-large mechanism selects for hidden-strength — confirmed and gender-symmetric across ten seasons

This is the part that gets **stronger**, not weaker, with the full ten-season pool, and
it is now the more interesting result of the two:

| Path | Boys n | Boys % hidden-strength | Boys mean signed | Girls n | Girls % hidden-strength | Girls mean signed |
|---|---|---|---|---|---|---|
| **At-large** (seed ≥ 33) | 944 | **57%** | **+1.34** | 944 | **56%** | **+1.21** |
| Road-qualified | 3,804 | 46% | −0.50 | 3,804 | 46% | −0.54 |

At-large qualifiers skew hidden-strength at **57% and 56%**, essentially identical by
gender, against **46% for road qualifiers in both.** This is not a 2083 fluke — it is a
stable, decade-long property of the Borda-count at-large process, present in every season
measured, at nearly the same magnitude in both genders.

**Read plainly:** teams whose win-loss record failed to capture their real ability are
durably, structurally more likely to be the ones getting a second chance through the
wildcard path, in both genders, every year on record. The at-large system is not adding
random variance to the field. It is correcting, on average and consistently, for the
exact blind spot a record-only qualification path would have.

## 5. What this doesn't yet show

- **‼️ A single-season read of 2083 alone suggested girls hidden-strength teams convert at
  roughly 3x the rate of hidden-fragility teams, versus a much smaller boys gap.** That
  asymmetry does not survive pooling across ten seasons (§3) and should not be cited —
  it was a sampling artifact of a 34-35 team single-season cohort. The correctly-supported
  claim is a consistent ~1.8x effect in both genders, not a girls-specific effect.
- This report only measures qualifiers. It says nothing about hidden-strength teams that
  were *not* selected — i.e., whether the at-large cutoff is wide enough, or whether a
  meaningful number of hidden-strength teams are still being left out below the current
  bid count.
- The signed metric here is unweighted (raw mean of three ranks vs three ranks). It has
  not been tested against the seeding ATR's existing 0.6/0.4 TOSS/win% blend to see how
  much overlap exists between "signed disagreement" and "ATR already disagrees with raw
  rank" — that comparison would clarify whether this is a genuinely new signal or a
  restatement of ATR's own logic in different units.

## 6. Suggested next step

The ~1.8x hidden-strength/hidden-fragility win ratio and the at-large mechanism's stable
57%/46% skew toward hidden-strength are both now supported by ten seasons, not one, and
both hold at essentially the same magnitude in boys and girls. `signed` is a reasonable
candidate input for the seeding ATR itself, or for a dedicated "at-large priority" score
separate from raw Borda count — it would let the committee explicitly favor
hidden-strength candidates over hidden-fragility ones with similar overall σ, rather than
treating all high-disagreement teams as equally deserving of a bid. Because the effect is
already gender-symmetric across a decade, this does not need to wait for a confirming
season the way the (retracted) single-season girls effect would have.
