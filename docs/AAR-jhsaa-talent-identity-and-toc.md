# AAR — what a program IS, and the tournament that proved it wasn't working

Three passes over the JHSAA talent model, in the order they happened, because each one
only became visible once the previous one was measurable.

---

## 1. The Tournament of Champions was a measuring instrument before it was a feature

Asked: *"would it be worth it to replicate the old New Jersey Tournament of Champions in
JHSAA tennis or not?"*

Answered by playing it. Five classification champions from three archived seasons, 60
runs each through a real `seeded_draw`:

| | titles | reached final |
|---|---|---|
| 7A | 55.3% | 88.3% |
| 6A | 39.2% | 78.1% |
| 5A | 2.5% | 15.6% |
| 4A | 2.5% | 16.1% |
| 3A-1A | **0.6%** | 1.9% |

Recommendation: don't build it. Three of five entrants were ceremonial.

That was the right read of the numbers and the wrong read of the problem. The owner's
response reframed it: *"the talent distribution is unfairly distributed right now
disproportionately to the big schools when in reality that's not how tennis works."*

> A feature that measures badly is sometimes telling you about the model, not about
> itself. The TOC was a fair test that the world failed.

## 2. The talent ladder was backwards, and only a position-by-position measurement showed it

`_TALENT` was an even −5/−4 step per classification with the spread NARROWING as the mean
fell. Measured (boys, mean current OVR):

| | #1 | #9 | #1→#9 drop | best #1 seen |
|---|---|---|---|---|
| 7A | 54.4 | 31.1 | 23.2 | 60.0 |
| 3A-1A | 42.0 | 22.8 | **19.2** | **51.0** |

The number ones were **12.4** apart and the number nines only **8.3** — the TOP fell
faster than the DEPTH — and the drop from #1 to #9 was *flatter* at a small school. A
3A-1A program could not produce a 60 at all.

Real high-school tennis is the opposite. Good players turn up everywhere; enrollment buys
**depth**. In Oregon's 2026 boys table the smallest classification finished No. 9
statewide and four of the top eight were 5A.

The fix is one mechanism, not two: let the mean fall and the spread **widen**. Twelve
ceilings are drawn and the best nine dress, so a wide draw lifts the number one a long way
and drags the number nine down. After: top-end gap **4.5**, depth gap 8.3, the drop now
*rises* as schools shrink, and every classification reaches a 59-61 number one.

Validated on a played season, not on the bands: statewide TOSS boys had **6A No. 1, 5A
No. 2**, 4A's best at No. 5 and 3A-1A's at No. 11, with the medians still indexing
downward (131/126/146/180/183). Thinner, not equal.

> One knob, two effects, because the selection step (best 9 of 12) does the work.
> Reaching for a second parameter to model "depth" separately would have been the
> obvious move and the wrong one.

## 3. A program is more than its classification

Archetypes, stored in an editable table and never branched on a school name:

| | top9 | gr9 | gr12 |
|---|---|---|---|
| untagged | 38.4 | 26.5 | 42.4 |
| blue_blood | 46.7 | **31.2** | 53.6 |
| development | 44.9 | 27.4 | 51.9 |
| doubles | 38.0 | 26.3 | 41.9 |

* **blue_blood** generates better and CLUSTERS — 70% of seats keep the better of two
  draws, which lifts the middle of a lineup far more than a flat mean shift. It shows on
  day one, and it beats a development programme on balance. That is what makes it one.
* **development** has ordinary freshmen and the best seniors: `mean` is 0, the gain is
  potential plus a maturity bonus starting at ZERO for ninth-graders and compounding by
  grade. It can beat a blue blood outright — the owner's point, *"that's the point,
  leveling the playing field"* — but it earns that over four years.
* **doubles** generates identically and wins doubles. Measured over 25 duals: singles
  **84-41 either way**, doubles 31-19 → 36-14.
* **upstart** is a temporary run, not a promotion — ~10 live statewide, expiring by
  itself, deliberately not storable.

Two corrections the measurements forced:

**Locality.** The upstart draw originally filtered tagged schools out of the POOL, so
tagging one school changed which OTHERS drew an upstart — `rng.sample` was sampling from
a different list. Tagged schools are now skipped at application. *A tag must only ever
affect the school it is on.*

**A wrong invariant of my own.** I wrote a test asserting a blue-blood 3A-1A must stay
under an ordinary 7A, "so the modifier doesn't flatten the classification model". That is
exactly the thing the talent model exists to allow. What actually needs pinning is that
the class ladder survives INSIDE each tag.

> When you write the test for a rule you just implemented, check whether you are pinning
> the rule or pinning your first guess at it.

## 4. Some freshmen arrive finished

~1 in 100 shows up with most of their ceiling already accessible. Deliberately NOT a
potential bonus — an ordinary 28-ceiling player arriving at 25 is as valid as a 75 arriving
at 67, and both occur. It is a maturity FLOOR that persists all four years, so they start
near their ceiling and barely grow: the early bloomer their classmates catch.

Rolled on its own rng stream, not the roster one. Drawing it from the main sequence would
shift every subsequent draw and regenerate every player in the association; keyed
separately, the only rosters that change are the ones that gain a prodigy.

## 5. And then the TOC was worth building

Same instrument, rerun after the rebalance — boys titles 22 / 30 / 18 / 22 / 8% by class.
A real tournament. So it shipped: `/jhsaa/toc`, its own bracket per gender, the five
champions **seeded on the TOSS Power Index rather than on classification**, the two
lowest-rated playing into a four-team semifinal.

The first archived running has the boys' 4A champion seeded No. 2 and winning it, and the
girls' 4A champion seeded No. 2 behind a 7A. Which is the entire point of the event, and
would have been impossible three commits earlier.

## 6. A dice roll had already voted on the owner's list

The archetype list arrived — 78 programs. Thirty-eight resolved against
`data/jhsaa/schools.json`; I reported the other forty back as near-misses and "nothing
close", with a tidy table of suggested alternatives.

Every one of the forty existed. `scripts/import_jhsaa.py` decides which of Jefferson's
840 schools sponsor tennis with a **seeded coin flip per school** against a
per-classification rate, and the owner's nominations had lost that flip. The file I was
checking against was not a list of Jefferson's schools; it was a list of the ones a
random number generator had let in. prep-network was cloned in the same working tree the
whole time.

> When a human's data disagrees with your file, establish which one is authoritative
> BEFORE reporting theirs as wrong. I had a filtered artifact and treated it as the
> territory — and the filter was one I had written.

The fix is a rule, not a list: **a school the owner names sponsors tennis.**
`always_sponsor()` forces named schools in for both genders, sourced from the archetype
seed file plus an explicit extras list, matched accent- and punctuation-insensitively
(Bahía Leal and San Borondón differed from the owner's spelling by accents alone). The
roll is still drawn for every school either way, so unforced sponsorship is byte-identical
and reproducible.

The archetypes themselves are two layers, as specified: `data/jhsaa/archetypes.json` ships
the seed list as school data, and the override table layers on top. That distinguishes
three intentions a single "clear" cannot — promote, demote a seeded program ("none"), or
drop the override and revert to the file.

## 7. Splitting 3A-1A, and getting the cutline backwards

The old 3A-1A group held the widest enrollment spread in the association — medians of
1,043 / 385 / 199 — so a 1,370-student school and a 108-student one played for the same
trophy. Six championships now.

The split alone left 2A-1A with 18 programs and an 8-team field: 44% of the class making
state. The owner's fix was more programs rather than a smaller field, and then more again
— 2A and 1A sponsor at 0.78 and 0.62, rates no real state would post, because a huge
ragged small-school classification is the point of having one. 18 → 151 girls / 136 boys.

Then I sized its bracket at 24 and called it the least selective class in the
association. It was the **most**: 13 districts × 1 automatic bid left eleven at-large
places for 138 programs — a 21% cutline against 24-32% everywhere else, and I had the
comparison inverted in the direction that made my own number look fine.

> A field size is not a number, it is a ratio, and the ratio has two terms. I had checked
> the field against the other fields and never against the pool it selects from.

Six groups, and the depth ladder survives the split intact (#9 mean current OVR: 31.9 →
22.1 boys, 29.7 → 21.4 girls, monotonic). Girls 3A needed one nudge — at 39.5 its middle
of the lineup edged 4A's — which `test_the_bulk_still_indexes_downward` caught rather
than a person. The Tournament of Champions is six champions now: two play-ins into a
four-team semifinal, a cleaner bracket than five.

## 7. Then it shipped without a bracket, and the tests said everything was fine

The owner opened it: *"why didn't you make a real bracket for TOC like every other state
tournament? Why can't I see round by round results like everything else? why aren't team
pages populating their TOC matches or placement — it's a big honor to make it."*

Four faults, and they are four instances of one habit.

**The page handed `brk_canvas` the wrong object.** `brk_canvas(cv, …)` reads `cv.width`,
`cv.columns`, `cv.cards`, `cv.links` — it wants a `_bracket_canvas` RESULT. I passed the
column list that goes INTO `_bracket_canvas`. Jinja resolves every missing attribute on a
list to Undefined and prints the empty string, so the page rendered a `<div>` of width
`px`, no cards, no elbows, no error and no log line. The columns themselves were correct
the whole time; `_jh_bracket_cols` handled the 6→4→2→1 shape and materialised both byes.
I had built the data and never connected it.

> Jinja's Undefined is silent by design, so a template is the one place in this codebase
> where passing the wrong type produces a page instead of a traceback. Anything a
> template dereferences by attribute has to be checked by RENDERING it, not by reading
> the view function and agreeing with yourself.

**`jh_round_tabs(rounds, u, gender, pin)`** — the signature is `(rounds, u, gender,
id='jhrd', pin=none)`. The year went into the DOM `id` slot. Positional arguments past
the third on a five-parameter macro; the state bracket page passes both and I copied the
call without its `id`.

**The duals were played `phase="state"`.** Shape and lineup rules are the state event's,
so borrowing the phase looked like reuse. But phase is also the only thing that
distinguishes the two events once they are rows in `world_jhsaa_dual` — so a TOC dual
counted toward a program's *state tournament* record, and "did this program reach the
Tournament of Champions?" had no answer to read. A phase is not a format selector; it is
the archive's identity for the event.

**And the honour appeared nowhere.** Six programs of ~335 reach the field. Nothing on the
program page said so, because the ledger row is derived from `world_jhsaa` +
`world_jhsaa_dual` and I had added the TOC to neither derivation.

The through-line: I verified each piece against the layer I had just written and never
end to end. `test_jhsaa_routes` renders every JHSAA page with **nothing archived** — it
was written after the last route bug and it proves the empty state works, which is why it
was green through all four of these. `tests/test_jhsaa_toc.py` now runs a real season
(two districts per classification, ~10s a gender), archives it through `run_jhsaa`, and
asserts on the HTML: a card per game plus the byes, every round named, the TOC chip on
the champion's page.

> An empty-state test proves the wiring. Only a test with data in it can see the page.

## 8. The lineup ladder was a ratchet

Reported in the same breath: *"this team has a kid that's a 50 OVR and they didn't use
him all year."* `_order` sorted on `(-wins, -pct, -ovr, -str)` — cumulative wins first.

A win total measures OPPORTUNITY. Dressing earns wins, wins earn the next start, and a
player who lost his opening two duals — or who was tenth in week one — can never climb,
because every team-mate who kept playing is above him on a number he is not being allowed
to add to. Ability was in the key, third, where it was unreachable. It also ranked 5-15
above 4-0, and doubles credits both partners, so a rotation player banked wins faster
than a number one drawing the toughest opponent on the card.

Measured over a boys' season: a top-four player finished outside the nine on **55 of 400
rosters**, 21 of them under seven matches all year. The report was a 51-OVR senior with
six matches beside a 28-OVR team-mate with twenty-seven.

The ladder now seeds on ability and lets results move it — `ovr + LADDER_SWING ×
(pct − ½) × n/(n + LADDER_PRIOR)`. A perfect record is worth +7 OVR and a winless one −7,
weighted by how much evidence there is, so **a player who has not played sits at his
seed** rather than at the bottom. After: 0 of 400 rosters bench a top-four player, the
top three play a median 27 matches to the bottom three's 5, and 28% of players still
finish somewhere other than their ability seed. The bench rotation — the variation the
owner asked for — was never the problem and is untouched.

> The bug was not in the rotation I added. It was in the ORDER the rotation sorted, and I
> had described that order in its own docstring as "results, then ability, then STR"
> without noticing that a raw count makes the second and third terms dead code.

## 9. A record is a record

Owner, on the same program page: *"sports don't track a separate post-season record, you
simply add it to the overall record for a final record at the end of the year — the NCAA
and NFHS both do it this way."* With a worked example: *"Baptist was 33-5 not 27-4, with
a 6-1 dual record in the post-season."*

The arithmetic in the example doesn't hold — 27-4 already contained the state tournament,
so adding the 6-1 counts those duals twice — but that is the point being made, not a
mistake in it. **I put a number on the page that a reader has to be told not to add.** The
fix is not to explain the tile; it is to delete it. A postseason leaves a FINISH behind,
not a second record.

And underneath it there *was* a real leak, in the direction the owner suspected. The
standings snapshot sat inside the loop that ran each classification's state draw:

```python
for group in GROUPS:
    state = run_state(...)                       # this group's postseason: done
    out["groups"][group] = {"standings": [... t.record ...]}
champs = [...]                                   # every group's champion
out["toc"] = run_toc(champs, ...)                # ← played AFTER every record was written
```

Correct for state and silently wrong for the TOC, which by definition cannot run until
the loop is over. So the six programs whose seasons matter most archived their final one
or two duals on their SCHEDULE and left them off their RECORD. **131 of 137 programs
balanced.** The six that didn't were exactly the TOC field — which is why nothing looked
wrong: any sample that isn't the whole association is overwhelmingly likely to miss them,
and the six that are broken are the six with a champion's page nobody reads sceptically.

> A per-item loop that also produces a cross-item event has to be split. The snapshot
> belongs after the last thing that can change what it records, and "the last thing" is
> not always inside the same iteration.

Now: all state draws → the TOC → then the records. Pinned over the whole association
rather than on a champion, because the failure was a six-row minority inside a
green-looking majority.

## Files

* `app/jhsaa.py` — `_TALENT`, `ARCHETYPES`, `_program_mod`, `upstarts`, `_doubles_lift`,
  `PRODIGY_RATE`, `run_toc`, `POSTSEASON`, `ladder_score`/`_order`
* `app/overrides.py` — the editable archetype table
* `app/world.py` — `jhsaa_toc_result`, `_toc_finish_label`, the TOC columns on
  `_season_row` / `jhsaa_program_totals`
* `app/web/state.py`, `app/web/server.py`, `templates/jhsaa_toc.html`,
  `templates/jhsaa_rankings.html`, `templates/jhsaa_school.html`
* `tests/test_jhsaa_talent_shape.py`, `tests/test_jhsaa_archetypes.py`,
  `tests/test_jhsaa_toc.py`, `tests/test_jhsaa_lineup.py`
