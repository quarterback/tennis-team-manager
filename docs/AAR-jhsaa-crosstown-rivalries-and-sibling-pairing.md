# AAR — crosstown rivalries, and siblings partnering automatically

Owner rules, 2026-09. Two reports, one session:

> 1) i want more rivalries between cross-town programs to be codified into the game so
> they play each other annual right now none of the cherry hill schools or port meridian
> schools play each other much/enough and that's not realistic
>
> 2) the sibling thing on the same team should be paired automatically because i can't
> track them all the time and it's easier to see it that way.

Both are the same shape of mistake on our side: a thing the owner expects to be a RULE
was implemented as a WEIGHTING, so it happened sometimes, and "sometimes" is invisible
until you go looking for it across the whole association.

---

## 1. Crosstown rivalries

### The report, measured

`_nondistrict_pairs` draws a program's out-of-league card on geography (`GEO_WEIGHT`),
then talent, then availability, and it draws at RANDOM from a `SHORTLIST` of six. That
is the right shape for the average card and the wrong one for a rivalry: it is a
weighted lottery, and a rivalry is a fixture.

The scale of it, over a full shipped girls' season (912 programs):

| | rivalry fixtures played |
|---|---|
| before | **36 of 263 (14%)** |
| after | **263 of 263 (100%)** |

Port Meridian is the case that makes it obvious. Nine tennis programs in one city,
spread across **six leagues** and 9A down to 3A — so the league season can never pair
them, and the non-district draw pairs them only when the lottery lands there. Cherry
Hill is the same story one level down: three campuses of one name (East / North /
South), split between Three Rivers League and Ambassador League.

### The rule

A rivalry is DERIVED from the school list once, then scheduled unconditionally.

* **The town is the CITY.** A metro's core-city programs and its locality (CDP)
  programs are one pool; sharing a locality is a PRIORITY, not a gate. Splitting the
  pool by locality would have left most of Port Meridian's nine unpaired, since none of
  them carries one.
* **Priority**, best claim first: a shared campus stem (`Cherry Hill` East/North/South —
  it is one school district naming its campuses, the strongest crosstown signal there
  is), then the same locality, then the nearest classification, then the names so the
  derivation is stable.
* **`RIVALS_PER_PROGRAM` = 2**, accepted greedily best-claim-first. This is what stops
  Port Veles's 41 programs from becoming an 820-dual round robin, and it happens to give
  a three-campus town (Cherry Hill) exactly its round robin.
* **`RIVAL_MAX_GAP` = 3.** The general matcher refuses a pairing more than ONE class
  apart. A rivalry reaches three, because a town looks like that (Port Meridian's two 3A
  privates take the 5A private across town). It does not reach further — see the
  measurement below.
* **`RIVAL_OVERRIDES`** is the owner's hand-authored list, placed FIRST and taking a
  seat like any other rivalry.

### ‼️ THE CAP ALONE PRODUCED THE OPPOSITE OF A RIVALRY

The first cut had no `RIVAL_MAX_GAP`, on the doctrine that a rivalry outranks the
classification gate exactly as `import_jhsaa.RIVALRIES` outranks reclassification. That
doctrine is right and the conclusion was wrong, because of what a greedy cap does to a
BIG town: everyone pairs off nearest-class-first and the **stragglers are left to each
other**. Valderra's 9A drew the 1A across an 18-school city — the two programs nothing
closer had room for. Six such pairs a gender, at eight classes apart.

The tell is that they were the LAST pairs formed, not the first. A rivalry between two
programs that nothing else in town would take is not a rivalry; it is a remainder. A
program with nothing in range now simply has no town rival, which is a real answer.

### It is a fixture, not an allowance

They are ordinary 3S/4D non-district duals in every respect but their certainty: they
count to the record, to TOSS, and to the `spent` fold at the late tune-up, so **a
rivalry does not lengthen anybody's card**.

An unexpected second result: programs finishing OUTSIDE the non-district allowance
(`NONDISTRICT_MIN` 4) went from **44 to 15** of 912. A guaranteed pairing is one the
matcher cannot fail to make, and the ones it was failing on were exactly the programs
whose eligible pool was thinnest.

### ‼️ RESERVED BEFORE THE FIRST DRAW, PLAYED AFTER LEAGUE PASS 1

Reserving and playing are two steps, and the first cut collapsed them into one — it
derived the pairs in the mid-season window and skipped any that had already met, on the
reasoning that a rivalry played is a rivalry played.

It is not, and a reviewer caught it. The early matcher is *allowed* to pair two town
rivals — one inside its ±1 class gate is an ordinary candidate to it — so on the seasons
where it did, that random draw silently became the annual fixture and lost both of the
things the fixture exists to guarantee:

* it was played at the **early window's 5S/2D shape** rather than the league's 3S/4D one;
* its **host was whichever side the matcher happened to put first**, defeating the
  year-parity alternation, so the venue could stay with one school two seasons running.

`_rivalry_pairs` now runs at the TOP of `play_regular_season`, where marking `played`
takes each pair off the ordinary matcher's board, and hands the pairs back to be played
after league pass 1. **A fixture the draw can pre-empt is a fixture only when the draw
does not.** Reserving them also turned out to help the matcher: the allowance shortfall
above went 22 → 15 on the same measurement.

### The rivalry is not archived, and must not be

`jh.are_rivals(a, b, rival_map(schools))` is a pure question about the school list, so no
column was added to `world_jhsaa_dual`. A card therefore reads the same for a season
played before the fixtures existed and one played after. This is the section's own rule —
*before persisting, check whether the thing is a PROJECTION of a layer you already have*
(`jhsaa_school_history`, the title board).

The RIVALRY chip is the one exception to *"only a bracket round earns the second chip"*:
which invitational is the rivalry game is the one thing on that row a reader cannot infer
from the row, unlike the showcase kind and the early window's shape that rule retired.

### ‼️ TWO TABLES, ONE FACT, AND THE AGREEMENT IS ASSERTED

`import_jhsaa.RIVALRIES` (a classification-integrity constraint applied once at import)
and `jhsaa.RIVAL_OVERRIDES` (a season fixture) state the same fact for two different
mechanisms, and the app cannot read `scripts/`. They are separate lists, and
`test_the_two_rivalry_tables_agree` fails loudly on drift.

Without the override entry the derivation quietly **breaks the named pair**: Alameda and
Condotti Vanguard Academy are both Ashbury 7A and Alameda sorts first, so on class alone
Alameda takes the seat and the association's oldest rivalry — the one the whole
`RIVALRIES` doctrine exists to protect — stops being played. Nothing errors; the card
just stops carrying that one dual.

---

## 2. Siblings partner automatically

`FAMILY_CHEMISTRY` (0.025, ~¼ sd of the pair-rating spread) is a TIEBREAK, which means
two brothers partnered when the ratings were already close and not otherwise. The owner's
objection is not that the number is wrong — it is that whether they are together is a
question at all, answerable only by opening every dual of every program.

So the bonus stays, and it still decides which COURT the pair takes. What changed is that
**whether they are a pair is no longer a rating question**.

* `_sibling_units` cuts the disjoint sibling pairs out of a lineup in ladder order.
  Three siblings on one roster cannot all partner, so the higher two pair and the third
  plays on.
* The SEARCHING arrangers (`_arrange_state`, `_arrange_1a_postseason`) take it as a
  CONSTRAINT: `_legal_partitions` drops the partitions that split a sibling pair and the
  search picks the best of what remains. That keeps the best LEGAL arrangement rather
  than repairing an illegal one — and it is why the anti-stacking rank-sum boundary
  still binds afterwards without a second thought.
* `_arrange_regular` pairs by DIRECT DECISION rather than search (owner rule 2027-08 —
  do not put the 105-partition search back), so it takes a partner SWAP afterwards
  (`_force_pairs`): the two displaced players take each other's seats and nothing else
  in the lineup moves. All three strategies, `traditional` included.
* Two siblings inside the 1S/4D top three ARE D1 and the third plays S1 — there is
  nothing left to choose, since S1 + D1 consume ranks #1-#3 by the anti-stacking rule.

### ‼️ THE WINDOW WITH NO ARRANGER IS THE ONE THAT GETS MISSED

The first cut wired the rule into the three arrangers and stopped, which looked complete
because every varsity lineup goes through an arranger — except the early 5S/2D window,
which never had one. Its allocation is fixed by the shape (top five at singles, #6-#9 the
doubles pool), so `_lineup` handed back the plain ladder and the pool paired adjacently.
Siblings at #6 and #8 therefore drew different partners in **every early dual** while
partnering everywhere else in varsity play — the exact "sometimes" the rule was written
to remove, reintroduced in the one block nobody looked at.

`_arrange_early` exists only for this. With no sibling pair to force it returns the
ladder unchanged, so the pre-rule lineup is preserved byte for byte. And the coverage
goes through `_lineup`, not just the helper: a fix that only adds the function changes
nothing.

### ‼️ A PAIR STRADDLING A FIXED BOUNDARY IS NOT HONOURED

S1 and the doubles pool in the 3S/4D lineup; the top-three pool and #4-#9 in the 1S/4D
one. Those boundaries are the anti-stacking rule and the format's fixed allocation, and
both outrank this. **A lineup is never rearranged to put two siblings together** — the
sibling rule decides pairing INSIDE a pool, never who is in which pool. Pinned by
`test_siblings_are_never_forced_across_a_boundary_the_format_fixes`.

---

## Known-stale, not touched

`tests/test_jhsaa_lineup.py::test_maximize_never_scores_worse_than_traditional` fails on
`main` and still fails. Its docstring describes the exhaustive 105-partition search that
the owner **explicitly removed** in 2027-08 ("real-life coaches do not run a permutation
search before every match"), so a direct-decision `maximize` can legitimately score below
the ladder pairing on a given roster. It is the test that is stale, not the code, and
rewriting an unrelated stale test inside this change would have hidden that. Flagged
rather than fixed.

Two `tests/test_jhsaa_schedule.py` allowance assertions also fail on `main` — this change
halves the population they are failing on (44 → 22 programs) without closing the gap.
