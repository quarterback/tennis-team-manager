# AAR — league identity as its own dataset

**Date:** 2026-08-16
**Status:** Landed. Owner rules 2027-08.
**Scope:** `scripts/import_jhsaa.py` (`LEAGUE_NAMES`, `league_names`,
`draw_districts`, `build`), `data/jhsaa/schools.json` (all 857 rows re-leagued),
`app/web/templates/jhsaa_district.html`, `jhsaa_districts.html`,
`jhsaa_school.html`.

## What the owner was looking at

A classification's league dropdown:

```
Ashbury Metro District · Bidwell District · Gold Valley District
Halbrook Basin 6 District · Halbrook Basin District · Halbrook District
Harborline District · South Coast District · Vance District
```

> "this is the laziest work i've seen in my life"

Three faults stacked in one list, and the numbered one was the least of them.

## 1. The numbered fallback

`draw_districts` named a block for its dominant AREA, then for each COUNTY it
covered, and then gave up and appended a count. A block sitting entirely inside
one county whose name was already drawn is exactly the case that reaches it —
here, eleven schools wholly in Vance county with "Vance District" already taken.

The cascade now walks further through real places (area → counties → cities →
a compound of the block's two largest towns) and never counts. That block is
Belyakov District, its largest town.

## 2. "Halbrook Basin District" beside "Halbrook District"

The worse one, and the one the owner actually pointed at: **Halbrook Basin is an
area and Halbrook is a county inside it.** Two distinct strings, one league to
any reader. The uniqueness check was `name not in used`, which is a test of
string equality and not of legibility.

A candidate is now rejected when it shares its **leading word** with a district
already drawn in that classification. Four blocks were affected across 5A and
6A, both genders.

⚠️ A review then caught that my fallback re-selected a merely-unused candidate
*without* re-applying the check, and could raise `StopIteration` outright if
every candidate was taken. Correct finding. It became moot when the whole
cascade was deleted below, but the lesson stands: **a constraint that the
fallback path does not enforce is not a constraint.**

## 3. The real problem — one ontology for two things

The owner's diagnosis, which was better than my fix:

> "league identity and JHSAA administrative geography should be separate
> datasets. The repetition is happening because right now they sound like the
> same ontology."

Every league name was generated from the map, so the league names and the
administrative areas were the same eight words in a different order. Real
high-school athletics is not that tidy. A league name is an institutional
**fossil**: it encodes geography, industries, former memberships, counties,
rivers, old political regions, aspirational words, school types, and names that
made sense in 1964 and nobody changed. New Jersey runs a Cape-Atlantic beside a
Skyland and a Super Essex; Vermont has a Marble Valley named for what the ground
produced; Massachusetts has a Dual County League that sounds like administrative
history because it is; Arizona is content with one word (Fiesta, Sonoran,
Premier); New Mexico just numbers them.

So `LEAGUE_NAMES` is now a separate bank of ~100 names across the naming
families — landform, watershed, historical, coined compound, evocative
geography, institutional, metropolitan, paired environment, directional — with
varied suffixes and the plain legacy District kept deliberately, because not
every unit needs to be evocative.

**`affinity` is a soft tug, never a rule.** A name is preferred for a block in
its region and used anywhere once that pool is spent, because — the owner's
rule — *a name need not describe its current members. Real league names persist
through realignment,* and the drift is the realism.

### ‼️ The reserved vocabulary is bigger than "Conference"

The owner flagged Conference and Division as unusable, both being playoff units.
The list is longer: **Area, Section, Ward, Zone, Region, Super Region, Division
and Conference are ALL stage or unit names** in this association
(`_STAGE_NAMES`, `_RECOVERY_UNITS`, `renumber_divisions`,
`reletter_conferences`). A league sharing a word with a bracket round is the
same ambiguity as Halbrook/Halbrook Basin, one level up. Two pages were still
calling a league a "conference" and a schedule band said "district play"; both
are fixed.

## 4. ‼️ Boys and girls were in different leagues

Found only because the names became distinctive. `draw_districts` was called
**once per gender**, so every school held two independently blocked and
independently named leagues — a school could be Chinook League for girls and
Quarry League for boys. Invisible for as long as both draws produced
"<area> District" from the same map; glaring the instant they did not.

A league is a property of the **school**. The map is drawn once per
classification over every sponsor and both gender fields read it. Blocks balance
on the girls-inclusive pool (girls sponsorship is the superset), so a league's
boys half is the ~88% that fields a boys team — eleven girls' teams and nine
boys' in one league is how this works in life, not an imbalance to correct.

Verified on the rebuilt data: **0** schools whose leagues differ by gender, none
without a league, no leading-word clash in any classification, 49 leagues
statewide.

## Lessons

- **Cosmetic sameness hides structural bugs.** The per-gender league split was
  years-old and undetectable while every name came from the same eight words.
  Making the output distinctive is what surfaced it — a reason to prefer varied
  generated data over uniform generated data even when uniformity looks tidier.
- **Uniqueness is not legibility.** `name not in used` passed happily on
  "Halbrook Basin District" and "Halbrook District". When a name is for humans,
  the constraint has to be about how it reads, not whether the strings differ.
- **I fixed the cascade twice before replacing it.** The owner's framing — two
  datasets, not one — was available from their first message and would have
  skipped both patches. When the complaint is "this is repetitive", the answer
  is usually a different source of variety, not a better tiebreaker on the same
  source.

## Related

- `docs/AAR-jhsaa-conference-round-and-atr.md` — the playoff units whose
  vocabulary the leagues must avoid.
- `docs/BRIEF-jhsaa-school-naming.md` — the parallel, still-open pass on school
  names, which has the same shape: invented families replaced with real ones.
