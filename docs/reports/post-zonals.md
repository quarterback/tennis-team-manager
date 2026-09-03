# The State byes stop being a Zonal prize

**What changed:** the eight State byes are no longer handed to the eight Zonal champions.
Four are now played for by those champions in a pre-bracket round, and four go to the best
remaining teams on a rating that includes their record. Field sizes, round counts and the
bracket tree are untouched.

**Why:** the Zonal title was doing two jobs — qualifying a team for State and assigning it
a top-eight seed. Only the first was earned, and the second broke the 2068 postseason.

---

## 1. The observation that started it

Sunset Hills won the 2068 8A girls state title as the **31 seed**, out of a 40-team field,
at 25-10 and ranked 34th in the class. Nothing in the archive comes close.

The path was not a soft draw. Six rounds, **four of them decided 3-2**:

| round | beat | opp seed | opp rank | opp record | score |
|---|---|---|---|---|---|
| R1 | Apalachicola | 17 | 13 | 18-9 | 3-2 |
| R2 | North Coast Packing | 37 | 48 | 19-16 | 4-1 |
| R3 | Ironwood Flats | **3** | 7 | 21-7 | 3-2 |
| R4 | Vespertine | 12 | **1** | 27-10 | 4-1 |
| R5 | Larchmont Ridge | **2** | 11 | 19-8 | 3-2 |
| R6 | Leonard Coleman | 21 | 15 | 22-9 | 3-2 |

They beat the 2 seed, the 3 seed, and the class's rank-1 team. And the program had no
business being there: 9-18, 6-19, 15-18 and 8-21 in the four seasons from 2061 to 2064,
missing the field entirely in four of the eight prior years.

The detail that turned this from a great story into a bug report is in the fourth row.
**Vespertine was ranked 1st in 8A girls and seeded 12th.**

## 2. The measurement

Seed against rank-order within each State field, 2068, every classification and gender.
`mean |seed − rank-order|`:

| class | boys | girls |
|---|---:|---:|
| 4A | 1.8 | **4.9** |
| 5A | 3.3 | 1.9 |
| 6A | 3.8 | 1.9 |
| 7A | 1.5 | **4.1** |
| 8A | 2.9 | **5.1** |
| 9A | 2.2 | 2.3 |
| Group 1 | **4.0** | 3.9 |

The aggregate divergence is bad enough on its own, but the diagnostic is in *which* seed
is wrong. Listing the single worst-placed team in each of the 24 class-genders:

**Seed 8 appears in 20 of 24.**

Not 7, not 9. Seed 8, over and over, going to teams ranked 19th, 20th, 22nd, 23rd, 24th,
25th, 27th in their own field:

- boys 6A — Bolinas, seed 8, rank-order 24 (21-11)
- boys 8A — Lago Vista, seed 8, rank-order 27 (19-11)
- girls 4A — Montelago West, seed 8, rank-order 27 (16-14)
- girls 7A — Cherry Hill East, seed 8, rank-order 27 (16-14)
- girls Group 2 — Burdensome, seed 8, rank-order 27 (14-14)

That is the eighth and last Zonal berth. A mediocre team that wins a thin Zonal takes a
top-eight seed and, in a 40-team class, the double bye straight into the Round of 16 —
while the best team in the class enters at 12 because its Zonal was harder.

**‼️ This was invisible in every aggregate view.** Champion-seed distribution for 2068
looked *healthier* than 2067 (boys median champion seed 3, ten of twelve seeded 4th or
better) because the diffusion-curve change was tightening outcomes at the same time. The
seeding fault only surfaces when seed is compared against rank **within** a field, which
is the same conditional-versus-aggregate lesson the gap-response work produced.

## 3. What was considered, and why the shape landed where it did

**Decouple entirely — seed purely on strength, Zonal is qualification only.** Rejected.
It fixes the bug and removes the reason to care about the road to State. The Zonal title
should still be worth something; the gauntlet after it is brutal.

**Zonal champions play down for the byes.** Kept, as the first half. Eight champions, four
matches, four winners take byes, four losers enter the draw. The reward now has to be
earned against peers rather than granted by which zone a team happened to be in, and a
weak Zonal winner is exposed immediately instead of skipping two rounds.

**The arithmetic problem that created.** Four byes instead of eight means four more teams
in the opening round, so a 40-team class went from 8 byes + 32 playing (16 matches, 24 into
the next round) to 4 byes + 36 playing (18 matches, **22** into the next round). 22 is not
a power of two and the old shape's 24 was. Rather than restate every round size, the second
half of the change restores the missing four byes on merit — **the bracket is then
byte-identical to today's**.

**Single byes, not double, for the merit four.** Winning a Zonal and then winning the
play-in skips two rounds; rating into the next four skips one. The Zonal stays the biggest
prize.

**Play-in losers remain eligible for a merit bye.** In a year where the Zonal champions
genuinely are the eight best teams, they take the four play-in byes and then the four
merit byes as well — eight byes to the same eight teams, exactly as today. The mechanism
only bites in a year like 2068 when it needs to.

## 4. TOSS or ATR — the byes are decided on a measure that includes winning

Both measures were run over the four most recent seasons (2065–2068), 8A and 9A, both
genders, picking the top four by each.

```
atr = 0.6 * z(toss_power_raw) + 0.4 * z(win_pct)     # z within class-gender, State field
```

**In 9A they agree.** Overlap 4/4 in five of eight cases, 3/4 in the rest. The class is
deep enough that schedule strength and record point at the same teams. Both give Rockridge
(40-0) and Cliffside (29-0) their 2068 byes.

**In 8A they disagree every year, and TOSS makes the odd pick every time:**

| season | TOSS takes | ATR takes instead |
|---|---|---|
| 2068 girls | Tuscaloosa 23-11, Vespertine 27-10 | Hollywood 21-3, Altamonte 24-6 |
| 2067 boys | Vespertine 27-10 | Sherwood Bench 24-5 |
| 2065 boys | Tidegate 21-9, Plainfield 22-11 | Marshfield Prep 24-3, Xavier College Prep 24-5 |
| 2066 girls 9A | Talladega 24-7, Jesuit 22-6 | Westfield Friends 29-5, Morgan Park 25-4 |

The pattern is consistent: 8A carries enough schedule variance that TOSS will rate a 22-11
team above a 24-3 team, and a bye is exactly the wrong prize to hand that team. ATR keeps
TOSS dominant at 0.6 — strength of schedule still decides most of it — while making a
double-digit-loss record disqualifying in practice.

**The weighting is a tuning choice, not a derived one.** At 0.5/0.5 the 8A disagreements
sharpen; at 0.75/0.25 it converges back toward TOSS. It ships as a named constant.

## 5. The shape, stated once

Three field sizes behave differently, because 32 is a power of two and carries no byes at
all:

| field | byes | play-in winners get | ATR four get |
|---|---|---|---|
| 40 | 8 | double bye (skips Qualifiers + First Round) | single bye (skips Qualifiers) |
| 24 | 8 | double bye | single bye |
| 32 | 0 | the top four seed lines | nothing to award |

- Bracket tree, field sizes and round counts, unchanged.
- Eight Zonal champions play a **pre-bracket round** in every field size, paired
  1v8 / 2v7 / 3v6 / 4v5 by class rank among those eight. All eight remain in the field.
- In 40s and 24s the four winners take **double byes**, and four **single byes** go to the
  highest ATR among everyone else, play-in losers included.
- In 32s the play-in decides the top four seed lines and the reform is seeding-only.
- The field is seeded on strength, independent of berth type.

**‼️ The play-in is not a bracket column.** Four matches feeding four byes is not a
halving, and the bracket canvas links columns positionally — rendered as a column it would
draw links between unrelated matches. It archives and displays as its own panel, the same
way the JV qualifying round already does.

## 6. What to check in the next export

- **`mean |seed − rank-order|` per class-gender.** The 2068 numbers (girls 8A 5.1, girls
  4A 4.9, Group 1 boys 4.0) are the benchmark; these should fall toward the classes that
  already behave (boys 7A 1.5, boys 4A 1.8).
- **Whether seed 8 is still the outlier.** If a single seed number keeps appearing as the
  worst-placed team, some other berth type is assigning position.
- **Champion seed distribution**, but read alongside the gap-response change landing in the
  same window — both push toward chalk, and the two effects will need separating.
- **Whether the play-in ran at all.** It only executes when eight Zonal champions exist,
  which the real association produces every season and a small fixture does not. A silent
  skip is the specific failure this design is most exposed to.
