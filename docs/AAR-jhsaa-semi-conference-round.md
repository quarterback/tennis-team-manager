# AAR — the Semi-Conference, the orphaned recovery loser, and a private-school layer

**Date:** 2026-08-17
**Status:** Landed. Owner rules 2027-08.
**Scope:** `app/jhsaa.py` (`POSTSEASON`, `SEMI_CONFERENCE_NAME`, `_RECOVERY_NAMES`/
`_RECOVERY_UNITS`, `_recovery`, `recovery_shape`, `sponsor_floor`, `champ_group`,
`School.talent_group`/`plays_up`, `_TALENT` keying), `app/world.py`,
`app/web/state.py`, `jhsaa_bracket.html`, `jhsaa_school.html`,
`scripts/import_jhsaa.py`, new `scripts/jhsaa_apply_renames.py` and
`scripts/jhsaa_reclassify.py`, `data/jhsaa/*.json`, `CLAUDE.md`,
`docs/JHSAA-road-to-state.md`.

## What started it

> "Ward teams entering at the conference stage should have to play a qualify match
> rather than giving the teams direct access when other teams will have played
> several matches where they've gotten wins before making it to that round."

The numbers were worse than the complaint. In a 40-field classification the
Conference is 28 teams and awards **14 of the 40 State berths — the largest single
block in recovery**. Its field was:

| Tier | Teams | What they had done |
|---|---|---|
| Divisional losers | 6 | Regional loss → **won** a Super Regional → lost Semi-State → lost Divisionals |
| District champions outside the field | **0** | (all ≤12 champions take protected seats, so they are always already in the ladder) |
| Ward / Sectional / Area losers | **22** | Nothing. Lost, went home, were called back |

Four of every five entrants walked in off a defeat with no recovery dual at all, and
they were competing for the biggest prize on the ladder.

## The round

A byeless `semi_conference` in front of the Conference: everyone except the Divisional
losers qualifies for it on court. 44 teams → 22 winners; the Conference stays 28 (6
Divisional losers + those 22) and still takes 14 berths.

**The thing that makes it not the retired Ward playbacks** — which handed those teams
two or three bites while a Zonal loser got one — is that it grants **zero** extra bites
at a berth. The Conference is still the only berth-bearing round a body team ever sees.
One extra dual to earn the seat, not one extra chance at it. That distinction is the
whole design and it is worth stating in the code, because the obvious next "fix"
(letting them in a round earlier) is precisely what was retired.

Everything below Sectionals is fixed in every class and both genders (Wards 32→16,
Regionals 32→16, Zonals 16→8), so there are only two shapes:

```
40-field (9A 8A 6A 5A 4A 3A 2A-1A)   SR 16   SS 24   DV 12   SC 44   CF 28   State 40
24-field (7A)                        SR 16   SS 22   DV 10   —       —       State 24
```

Measured full size, both genders, after the data work: every class exactly on that
table, byeless everywhere, every non-champion State entrant won its last dual, and no
Conference entrant without a Divisional loss or a Semi-Conference win.

## ‼️ The orphaned recovery loser — the owner found it by reasoning, not by reading

The owner's second message:

> "I presume that all those teams would've already been exhausted but mathematically
> that's probably not true and they should not be skipped over."

They were right, and it was a live bug older than this change. `bodies` walks the
ladder back starting at **Wards**, and `taken` excludes every Regional and Zonal loser.
So a **Semi-State loser the Divisionals could not take**, or a **Super Regional loser
Semi-State could not readmit**, belonged to no tier at all and could be walked straight
past by a Ward loser who had got nowhere near as far.

It is not hypothetical: 7A's Divisionals take `ss_losers[:10]` out of 11, orphaning one
team every season. It goes unseen only because 7A never convenes a Conference for the
orphan to enter — the defect is real, permanent, and invisible because the surface that
would show it does not exist in that class.

The pool now walks back **in round order**: district champions still outside → orphaned
Semi-State losers → orphaned Super Regional losers → Ward → Sectional → Area, with ATR
ordering *within* a tier and never across one. It also restores the ladder's own parity
rule — an orphan has had ONE berth-bearing round where a Divisional loser had two, and a
Ward loser has had none.

**Lesson:** a walk-back that starts in the middle of a ladder is a walk-back with a
hole in it. When a tier list is built by exclusion (`not in taken`), the teams that fall
through are invisible by construction — there is no error, no log line, and no surface
that shows an empty tier.

## ‼️ CORRECTION: the data COULD be regenerated. I checked a stale clone.

Everything in the section below is wrong, and it is left standing because the mistake
is more useful than the conclusion was.

prep-network carries **1,111 schools across nine classifications, enrollment 56-2,597**
— exactly the rebuilt records the committed data came from — in "Nine counties settled,
and one classification ladder for the whole state". The importer reproduces the
association from them cleanly.

I concluded they did not exist. I ran `git log --all` and `git rev-list --all` against
the local prep-network clone, found 840 schools and seven classifications at every
revision, and wrote it down as a rule in `CLAUDE.md`. **The clone was eight commits
behind on main, and `--all` does not see what has not been fetched.** "Not in any ref"
was a statement about my disk, not about the repository — the same category of error as
the suite-hermeticity bug this codebase already has an AAR about, where a test result
was a statement about the developer's disk.

What it cost: two transform scripts and an entire enrollment cascade — 48 promotions,
a league-realignment pass, and the rivalry split that came out of it — built to work
around a source that was one `git fetch` away. The cascade is redundant against the real
records, which already put 9A boys at 84 against a floor of 76.

**Lesson: `git fetch` before concluding anything from history, and be most suspicious of
a conclusion that conveniently explains why you cannot do the obvious thing.** I treated
"the generator's input no longer exists" as a discovery and designed around it, when the
cheap check was to update the clone and run the generator.

## The original (wrong) section, kept for the record

`scripts/import_jhsaa.py --dry-run` emitted **637 sponsors in seven classifications with
no 9A or 8A**, against the committed 857/772 across nine. The instinct was that this
repo had drifted. It had not: **prep-network carries 840 schools and classifications
7A-1A at every revision on every ref in its history**, with a different enrollment scale
(its 7A runs 2,602-4,219; the committed 9A runs 2,213-2,597). The committed data came
from `3c36b16` ("Re-imported against the rebuilt records") and those rebuilt nine-class
records were **never committed to prep-network**. The generator's input does not exist.

So `data/jhsaa/schools.json` *is* the source of record, and data changes are applied as
transforms: `jhsaa_apply_renames.py` and `jhsaa_reclassify.py`. Both hold **no names and
no numbers of their own** — every table is imported from `import_jhsaa`, which stays the
single authority — so they degrade to no-ops the day those records come back. Both are
idempotent, and both were proved so by running twice.

**Lesson:** before planning a change that ends in "regenerate the data", run the
generator. "It is generated from source" can quietly stop being true, and the commit
message that broke it will read like a routine re-import.

A second, blocking find on the same run: the importer **aborted outright** on a
display-name collision, because prep-network now carries a school of its own called
Echevarria while `RENAMES` still mapped Leire Aramburu onto that name. Retargeted to
Echevarria Central, the family its siblings already use. The collision guard did its
job — it refused to write rather than silently merging two schools into one archive slot.

## The reservoir, and a floor worth writing down

A full Semi-Conference needs 44 bodies, and the body reservoir is `programs − 32`
(`PROTECTED` skip to Regionals, `WARD_FIELD` reach Wards, half of those come back). So a
40-field class needs **76 sponsors per gender**. Every class-gender cleared it except
**9A boys at 72** — four short, for no reason but where the enrollment cut lines fell.

Two things came out of that:

- `recovery_shape(group)` projects the entire ladder from the constants with no season,
  which is what lets `sponsor_floor(group)` state the invariant as arithmetic rather
  than a literal. It is a projection, not a second implementation; a full-size run must
  land on it, and it reproduces the previously measured SR/SS/DV/CF table exactly.
- The round **degrades loudly** under the floor rather than shipping a short State
  field: the best bodies by ATR enter the Conference directly and a warning names the
  class, the count and the floor. Verified before the data fix — 9A boys admitted 4 of
  22 directly, warned, and still landed on exactly 40.

The owner's call was to fix the association, not the format: *"there are more than
enough schools to do that so it seems silly to let this be a real constraint when it's
not."* `PROMOTE_ABOVE` moves each class's largest schools up one — 8A→9A, 7A→8A, 6A→7A,
5A backfills 6A — 49 schools in all, taking 9A boys 72 → 83 and leaving every 40-field
class-gender clear with margin. The degradation path stays for drift and should never
fire again.

### Two things the reclassification got wrong first, both about leagues

1. **Capacity is a hard constraint, not a tie-break.** Placing promoted schools in the
   nearest league by geography and using size only to break ties piled every promoted
   school in a county into one league and produced leagues of **13, 15 and 16**. District
   size *is* the schedule here — the league is a double round robin, so a 15-team league
   is a 28-dual season against everyone else's 22. A league at `MAX_DISTRICT` is now
   skipped outright.
2. **A class that runs out of seats is realigned, not overstuffed.** 9A held 80 girls'
   programs in seven leagues — already 11.4 each against a cap of 12 — so twelve arrivals
   cannot fit however cleverly they are placed. When a class needs more leagues than it
   has it gets a full redraw through `import_jhsaa.draw_districts`, the existing authority
   for cutting balanced blocks and naming them. Everyone else keeps their league, because
   league identity is a curated dataset and a redraw would rename ~500 schools' leagues to
   reclassify 49.

And one that was pure sequencing: `promote` moves `group` and leaves the district alone,
so between the two passes a school sits in its **new** class still carrying its **old**
class's league name — and the next school being placed took it as a valid destination.
9A came out with ten leagues where it has seven, three of them 8A names that had walked
up with their schools. Only the *settled* membership of a class is a destination.

## The private-school layer

Jefferson had 297 schools named after invented people and a private tier too thin to
believe. The owner's brief was explicitly **not** a mass rename — *"about 15-25
institutional private-school names, not hundreds"* — so 25 of the most obvious became
institutions, spread evenly across all eight classifications.

- **Varied institutional grammar is the point.** Academy · Cathedral · Prep · College
  Prep · Catholic · Christian · bare. A layer built from one template reads as one.
- **Prelate names come from Jefferson's own surname pool** — Bishop Valera, Archbishop
  Valois, Cardinal Mercier, Cardinal Echevarria. That is what makes them sound native
  rather than imported, and it is why a fresh surname must never be coined for one.
- **Sinkford** — a Unitarian Universalist coed boarding school in the Juniper Highlands,
  founded by UU donors in 1974, named for William G. Sinkford (UUA president 2001-09,
  the first Black leader of a predominantly white American denomination, later of First
  Unitarian Portland). Small, strong arts and outdoor programs, and for no obvious reason
  a very serious tennis program. It exists so the layer is not Catholic prep and
  evangelical academy and nothing else. It went 25-7 and 24-9 in its first season.

### ‼️ The suffix question, and the answer that meant no code

The obvious reading of "Archbishop Gregory High School" and "Sinkford School" was that
the no-suffix rule needed a carve-out, and a plan was written proposing an exemption
list for `_display_name`. Asked directly, the owner said no:

> "You don't need a suffix at all — I was only typing the full name so you knew what I
> was trying to do … you say Archbishop Gregory, I know what you're talking about."

`_SUFFIX_RE` strips only `High School`, `HS` and `School`. **Academy, Prep, Cathedral,
College Prep and Catholic were never suffixes** and survive untouched — so the varied
grammar the brief asked for needed no rule change at all, and the exemption would have
been a mechanism for a problem that did not exist. Also: **Prep, never Preparatory**.

**Lesson:** when a request appears to contradict a hard rule, check whether it actually
does before designing around it. Asking cost one question; the carve-out would have cost
a permanent exemption path through a rule that exists to stop "Baptist HS High School".

## What the reclassification broke downstream, and why it was worth breaking

Moving ~12 schools per class is a small diff and a large change of population, and it
knocked over three things that had been standing on assumptions nobody had written down.

**A fixed district count is not a scaled association.** Both the ladder and lineup
fixtures took "the first TWO districts per classification", which silently assumed every
pair of leagues comes to more than the 16 protected seats. Leagues run 7-12. The
reclassification put two small ones at the head of 8A boys' alphabet, the pool came to
exactly 16, Sectionals got **zero** entrants, and the ladder was handed an empty field.
Both fixtures now add whole districts until the pool clears `PROTECTED + 8` — sized
against the constant that decides whether a ladder can run at all, not against a number
that happened to work.

**`run_rounds` answered an empty field with an `IndexError`.** `size` starts at 1, so a
field of 0 or 1 produced a one-slot draw and the pairing loop read `slots[i + 1]` off the
end: a bare "list index out of range" twenty frames down, naming neither the
classification nor the stage. It now raises with both, and says what an empty field
means. This is the roster-floor rule one level up — degrade or raise loudly, never
crash into an index.

**A flat tolerance asked the same of every pair of classes.**
`test_the_bulk_still_indexes_downward` allowed adjacent classes to sit within 0.5 of each
other, but the top of the ladder is deliberately packed far tighter than that: 9A/8A/7A
boys are **0.7** apart in `_TALENT` while 5A/4A are **5.0** apart. `_TALENT` is a CEILING
band and the test measures CURRENT overall, which maturity compresses further — so the
top pairs were **already measuring inverted before this change**: 8A 41.55 against 7A
41.68 on the old data, passing only because 0.13 fitted under the flat number. Resampling
the classes moved it to 0.65 and the test reported a talent-model regression with
`_TALENT` untouched. Measured on both datasets to establish that, rather than assumed.
The allowance now scales with the gap the model actually promises: demand a real step
where the design provides one, allow the measured order to blur where it does not. This
is the *second* false alarm from that assertion — the `ladder` fixture already carries a
note about a batch of renames doing the same thing.

**Lesson:** a test that a rename or a reclassification can move is measuring the sample,
not the model. Both times the fix was to make the check depend on something the design
states — the whole population, then the designed gap — rather than on a constant tuned
to the data that happened to be there.

## Traps for later

- **`MASCOTS`/`COLORS`/`PRIVATE_SCHOOLS` key on the DISPLAY name.** A rename orphans the
  entry and the school silently reverts to its source record's mascot — `MASCOTS["Oskar
  Bellini"]` did exactly that. Move the key with the name.
- **Never rename a real person's school.** The person-named pool mixes invented names
  with genuine ones — Octavia Butler, James Baldwin, Gwendolyn Brooks, Thurgood Marshall,
  Mae Jemison, Barack Obama, John Lewis, every president. Presidents and justices are in
  `OWNER_EDICTS`; the rest are not, so "looks like a person" is not the test.
- **`_TALENT` is keyed on the school's OWN class, not where it competes**
  (`School.talent_group`). It is a no-op today and stops being one the moment a school
  plays up: keyed on `group`, a 5A blue-blood playing up to 6A would be *generated* with
  6A talent — a free roster upgrade that inverts the point of choosing a harder field.
- **`recovery_shape` and `_recovery` must agree.** The projection exists for the data
  layer; the live computation sizes off real pools because it must degrade rather than
  crash. If they drift, the sponsor floor starts defending a shape nobody plays.

## Still open

- **`tests/test_jhsaa_ladder.py` still cannot reach full size**, and six of its
  assertions fail for that reason alone — before this change and after it (base 20
  passed / 7 failed; now 23 / 6, with both new tests passing and one previously-failing
  test recovered by the resized fixture). The fixture is a scaled association, but the
  ladder is not scalable: `PROTECTED` is a hard 16 and `WARD_FIELD` a hard 32, so
  anything short of ~48 sponsors per class-gender cannot fill a Ward field, and the
  Semi-Conference wants 76. The `ladder_scale` helper four docs still refer to was
  removed when the "THERE IS NO SCALING" rule landed and the fixture was never resized
  to compensate. So the shape assertions are structurally unreachable at fixture scale
  and everything above was verified by **full-size runs** instead — the right check, but
  not a regression test. Either the fixture becomes a real association (slow) or the
  shape assertions move to a full-size run kept out of the default suite. Note the two
  new tests were written to hold at BOTH scales, which is why they pass: they assert the
  invariant (strays are exactly the shortfall, orphans are never skipped) rather than the
  full-size numbers.
*(Play-up was finished in the same session — see below.)*

## Rivalries — the thing the cascade broke that no number could show

Condotti Vanguard Academy (1,666) and Romero-Finniski (1,526) are rivals. Both in
Ashbury, both 7A, both in Metro League for as long as the association has existed.
The enrollment cascade's 7A cut line was 1,638, so it promoted one and not the other,
and every individual number in that decision was correct.

It is unrepairable after the fact, which is why it needs a rule rather than a fix: a
district is `(classification, name)`, so once the two are in different classes there
is no league either could join to be with the other. `import_jhsaa.RIVALRIES` now
outranks the cut line, and `jhsaa_reclassify.check_rivals` **asserts** the invariant
rather than repairing it — a drifted pair means the mechanism that moved them is
broken, and quietly pulling them back together hides that.

Two implementation traps, and the test found the second:

- **The whole class must be decided BEFORE any of it moves.** Checked row by row, the
  guard splits the pair the *other* way when both members qualify: the first is
  promoted, and the second then reads its already-moved rival as no longer being in
  the source class and stays behind. One rule, two opposite failures.
- **Sorting rivals adjacently is not enough for the league draw.** The block boundary
  can still land exactly between them, which is what happened — 7A grew to 97, one
  past its eight leagues, triggering a full redraw that separated two schools nothing
  had moved. `draw_districts` now walks the cut forward past any pair it would split.

**Lesson:** an enrollment cut line is a statement about size, and it was being asked
to decide something that is not about size at all. Where a rule has to survive a
mechanism it knows nothing about, assert it at the end and fail — the check is what
found both bugs.

## Playing up

13 blue-bloods compete a classification above their enrollment class, drawn from the
archetype seed list (`scripts/jhsaa_playup.py`, weighted to the top of each class)
with `overrides.set_jhsaa_playup` layered on top exactly as archetypes are — "yes"
promotes, "no" holds, clearing reverts to the file.

**‼️ SMALL SCHOOLS ONLY**, `PLAY_UP_MAX_GROUP` 4A and below (owner correction): "play
up is for schools at the 4A or under level to play with teams at their competitive
level, not already big schools". The first pass drew from every class and shipped two
8A blue-bloods moving to 9A, which is not playing up — it is a big school in a
slightly bigger class. 9A's exclusion falls out of the same rule instead of needing
its own.

**It moves `group` and never `classification`**, and that is the entire feature.
`group` is the championship you enter; `classification` is how many students you have,
and `_TALENT` reads the latter. Keyed on `group`, a 5A blue-blood playing up to 6A
would be *generated* with 6A talent — a free roster upgrade that inverts the choice,
since playing up is meant to cost you a harder field. `tests/test_jhsaa_playup.py`
pins it by measurement rather than by inspection: hold a played-up school in its own
class through the override and its twelve players come out unchanged, name for name
and to six decimal places. Nothing else would catch a regression there, because the
rosters stay perfectly plausible either way.

**The league moves with the program**, because a district is `(classification, name)`
— a school competing in 6A while carrying its 5A league name lands in a 6A district
holding nobody else, and a one-team league in a double round robin is no league season
at all. It joins the nearest league of the class it plays in, skipping any at
`MAX_DISTRICT`.

‼️ **And they are placed in ONE pass, not one at a time.** Applying that rule per
school independently is not enough: two 8A blue-bloods playing up to 9A both read the
same settled membership, both saw the same nearest league with room, and both joined
it — 11 became 13, four extra duals in a class where district size *is* the schedule.
The running count has to include the play-ups already placed, which makes it one
assignment rather than a rule applied N times. Caught by the test, not by reading.

**Both override tables key the season cache.** An archetype changes how good a program
is; a play-up changes which championship it enters, so it moves the leagues, the
ladder, the State field and All-State. Left out, a cached season built from the old
classification map would be served with no sign anything had changed — and
`reset_schools()` exists because `load_schools` bakes the group and the league into
the School objects, which `reset_all()` alone does not touch.

## Related

- `docs/JHSAA-road-to-state.md` — the player-facing explainer, updated.
- `docs/AAR-jhsaa-conference-round-and-atr.md` — the Conference and ATR this extends.
- `docs/AAR-jhsaa-state-expansion-recovery-rounds.md` — the byeless-recovery design.
