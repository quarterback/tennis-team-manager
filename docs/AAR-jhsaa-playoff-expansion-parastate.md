# AAR — the 2026-09 JHSAA playoff expansion: 6A-1A onto the Parastate

**Owner rule (2026-09).** "JHSAA has approved playoff expansion in 6A, 5A, 4A,
3A, 2A, 1A TO 40 teams using the same parastate format that 7A uses. None of
those classifications will change their dual match format from status quo, it's
just expanding the playoffs to include at-large committee decided seats."

**Scope:** `app/jhsaa.py` (`AT_LARGE_BIDS`, and the assertion beside
`state_field_size`), `app/jhsaa_committee.py` and `app/web/state.py` (prose
only), `tests/test_jhsaa_committee.py`.

‼️ **The approval quoted above says "to 40 teams" and 1A is on a 32** — see the
1A section: the owner refused the sixteen bids a 40 costs off a 24 road. The
quote is left as written because it is what was approved; the section is where
it was amended.

## The whole change is one table

`AT_LARGE_BIDS` is what makes a class a Parastate class — `ATLARGE_GROUPS` is
derived from it, `run_state_parastate` takes its `byes` as `road − bids`, the
committee takes its `seats`, and the bracket page reads the shape off the
ARCHIVE. So six new entries is the feature:

| class | road (`STATE_FIELD`) | bids | field |
|---|---:|---:|---:|
| 9A · 8A · Group 1 | 32 | 16 | 48 |
| 7A · 6A · 5A · 4A · 3A · 2A | 32 | 8 | 40 |
| **1A** | **24** | **8** | **32** |
| **Group 3** | **24** | **4** | **28** |
| Group 2 | 32 | 0 | road only |

‼️ **THE BID COUNT IS THE DECISION; THE FIELD SIZE IS THE CONSEQUENCE.** Eight
bids is a 40 off a 32 road and a 32 off 1A's 24. Read the table that way round —
"every class crowns from 40" is not the rule and never was.

Nothing else moved. The road qualifies exactly what it qualified before, by the
same ladder, with the same Zonal/Epiregional/recovery/Specials arithmetic; the
at-larges are added on top and seeded below every road qualifier, structurally.

## ‼️ 1A IS NOT ON A 40 — the owner refused sixteen bids

The approval said "to 40 teams" in six classes, and for five of them that is
32 + 8. 1A's road is **24**, so a 40 there costs **16** bids — and that would
have made 1A the one class where the committee picks 40% of the field against
everyone else's 20%. Owner, plainly: **"I do not want 16 at-large teams in
1A."**

So 1A takes the SAME EIGHT BIDS as 7A-2A and its structure is **32 = 24 + 8**:

| stage | who plays | alive after |
|---|---|---:|
| Road | qualifies 24 | 24 |
| Epiregional | the 8 Zonal champions, one round among themselves | 24 (placement only) |
| Committee | adds 8, seeded 25-32 | **32** |
| **Parastate** | seeds 17-32 — 17v32 … 24v25; 1-16 bye | **24** |
| R24 first round | seeds 9-24; **the 8 Zonal champions bye** | 16 |
| R16 → QF → SF → Final | ordinary bracket | 1 |

Its State draw is **untouched** — the same 24 with the same eight first-round
byes it has always played. The Parastate is simply a reduction round in front
of it. Seeds: 1-4 Epiregional winners, 5-8 Epiregional losers, 9-24 the rest of
the road by ATR, 25-32 the at-larges by Borda — which is what
`epi_w + epi_l + others + at_large` already produced, with no seeding change.

**The Epiregional needed nothing.** `run_epiregional` has always run
`for group in GROUPS`; 1A's champions were already placed 1-4 / 5-8 by it.

**Two corrections this section records, both of which shipped in a draft:**

1. A draft explained 1A's 24 road by saying `state_field_size(group) == 24`
   "routes a class to the fixed `_recovery_24` wiring". **`_recovery_24` is
   RETIRED AND UNWIRED** (its own docstring says so): every class runs
   `_recovery`, the same rungs with different counts — 1A's Divisionals,
   Semi-Conference and Conference are 8 where a 32-road class runs 16. A
   retired code path with a long explanatory docstring reads exactly like a
   live one; **grep the call site, not the definition.**
2. A draft then pinned "every Parastate class totals 40 or 48" as an
   invariant, and a later one invented "no class lets the committee pick more
   than a quarter of its field" — which is false for the 48s (16 of 48 is a
   third). **Do not promote an observation about today's table into a rule the
   owner never stated.** The test now pins the three totals as consequences of
   the bid counts, which is what they are.

**The general lesson:** when a spec says "same format as X", find the
PARAMETER that produced X's shape rather than copying X's numbers. Here the
parameter is `bids`, and the field size is `road + bids` — `run_state_parastate`
was already written that way and needed no change at any of the three shapes.

## ‼️ GROUP 3 TOOK FOUR BIDS — the one class sized on measurement

Group 3 was not in the approval (which named 6A-1A) and stayed at 24 while
every other class grew, which left it with the association's smallest field
share. Measured across the owner's 2071-2075 exports, both genders — 10
class-seasons — against every other class:

| | best team left home (mean class rank) | top-24 teams left home / season |
|---|---:|---:|
| **Group 3** | **#14.3** | **3.00** |
| 1A | #16.9 | 2.80 |
| Group 2 | #19.3 | 1.50 |
| 2A | #21.6 | 0.90 |

Its road left an 8th-ranked 16-12 team home in 2072. That is the strongest
omission case in the association — but the same data says the FIX IS FOUR, not
eight:

| bids | best left home | top-24 left home | top-16 left home |
|---:|---:|---:|---:|
| 0 | #14.3 | 3.00 | 0.70 |
| **4 (shipped)** | **#26.6** | **0.10** | **0.00** |
| 8 | #31.9 | 0.00 | 0.00 |

Four clears 97% of it and every top-16 omission; eight would take the committee
to #32 of ~68 programs — the "searching for reasons to fill the back half" the
association rejected when it cut 7A from 16 bids to 8. So Group 3 and 1A run 4
and 8 side by side in two otherwise comparable classes, which the owner wants
as a live comparison rather than a settled answer.

‼️ **TWO JUSTIFICATIONS WERE PROPOSED, MEASURED, AND FAILED. Do not restore
either.**

1. *"In a shallow class the middle beats the top as often as not, so the cut
   line is arbitrary anyway."* FALSE: over ~85,000 duals the better-ranked team
   wins **73.9%** in Group 3 against a **73.9-77.9%** band across all twelve
   classes, and 58.5% in close matchups against a 57.0-61.5% band. Group 3 is
   the least predictable class by about two points on a four-point spread —
   noise. A flat TALENT distribution did not produce flat OUTCOMES, because the
   class's spread is still wide (21.5) and the engine converts the gaps that
   exist at the normal rate.
2. *"Group 3 travels furthest, so a smaller field is kinder."* FALSE: mean
   league spread is 47 mi (boys) / 43 (girls), mid-pack — **Group 2 is the
   association's worst at 65/64**, then 2A at 63/64. (Area-centroid resolution,
   coarse but coarse identically for every class.)

The number rests on the omission measurement alone. **A conclusion can be right
while the argument for it is wrong** — both premises here failed and 28 still
survived, on evidence neither of them named.

## ‼️ PLAYOFF SIZE AND DUAL FORMAT ARE SEPARATE AXES — do not tidy them together

The owner said it explicitly, and the code already agreed: `WIDE_GROUPS` (the
4S/5D road) and `ATLARGE_GROUPS` (the Parastate) are different tuples read by
different consumers. Before this pass every Parastate class happened to be in
both, and the constant's own comment said so ("All four are in `WIDE_GROUPS`") —
which is exactly the kind of coincidence a later pass "restores" as an
invariant. It is not one. 6A through 1A now run the Parastate at whatever shape
their road already played (1S/4D, or Group 2's 3S/3D had it been included), and
a test pins that the overlap has not grown.

## The one invariant worth asserting

`bids <= state_field_size(group)`, at import. The Parastate is the `2 × bids`
lowest seeds paired high-low, so every at-large plays a ROAD qualifier for its
seat; `bids > road` would pair at-larges against each other and hand one of
them a berth nobody defended. Two owner tables have to agree and neither knows
about the other, which is precisely when the agreement gets asserted rather
than assumed — the tables are edited independently and by different reasoning
(a class's road moves on sponsor counts and talent, its bids on how big a
committee the association wants), so nothing but this line stops a future edit
to one from silently invalidating the other.

## Surfaces that needed nothing

- `/jhsaa/committee` — its group switcher IS `ATLARGE_GROUPS` and its seat count
  comes off the archived selection's own `seats`, so the seven new classes
  appear with the right numbers and every season archived before them keeps
  reading as the field it was actually selected at.
- The bracket page — `state._jh_split_state` splits on the named Parastate round
  and `_jh_state_view` computes the bye count as `field − 2 × bids` **off the
  archive**, never off today's table. 1A's sixteen Parastate bye lines fall out.
- `recovery_shape` / `sponsor_floor` — projections of the ROAD, which did not move.

## Cost

The Parastate is the only new duals: 8 a class a gender for 7A-2A and 1A alike,
so **60 more duals per gender** (Group 3 adds 4) against a season's ~5,100. The main draws
are the same size they were — a Parastate does not lengthen the bracket behind
it, it fills the same seed lines from a larger pool.

## Tests

`tests/test_jhsaa_committee.py`: the bid table pinned (`bids in (8, 16)`,
`bids <= road`) with the three totals pinned as CONSEQUENCES of it — 1A 32,
7A 40, 9A 48, so a "tidy 1A onto a 40" edit fails here and says why; the
WIDE/Parastate overlap pinned as unchanged; and 1A's 32 walked end to end
through the real `run_state_parastate` (17v32 … 24v25, round sizes, the
surviving 24).
