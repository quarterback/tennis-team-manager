# AAR — a school's name, a school's identity, and what a rename costs

**Scope.** One long run over the JHSAA: ~180 school renames across three owner passes,
a locality layer for the five big metros, a sponsorship change, a geographic
redistricting of 6A/7A/8A, and — the part worth reading — four separate faults that all
turned out to be the same mistake wearing different clothes.

---

## The one lesson

> **A school has THREE identities, and every fault in this run came from treating one
> of them as if it were another.**
>
> | identity | what it is | what breaks if it moves |
> |---|---|---|
> | **`source or name`** | the ROSTER identity — seeds the RNG that builds the twelve players and their pids | the program gets twelve strangers; its archived awards point at nobody |
> | **display name** | the ARCHIVE identity — keys `world_jhsaa`, `world_jhsaa_dual.school`, the routes | its record, titles and history detach from it |
> | **prep-network name** | the SOURCE identity — what the other repo calls the record | `RENAMES` stops firing; a re-import emits the wrong name |
>
> They are three different strings and nothing in the type system tells them apart.
> All three are `str`.

---

## Fault 1 — two schools shared one roster identity

A school kept `source: "Wheatley"` from a rename whose source prep-network had since
renamed away. A **different** school was simply *called* Wheatley. `RENAMES` is matched
against `source or name`, so one entry reached both.

It surfaced only because the two then collided on a display name and the uniqueness
guard refused to write. **Had the targets differed it would have been silent** — two
schools generating the same twelve people, every page looking correct.

**Fixed:** `check_identities` asserts `source or name` is unique *before* renaming.

## Fault 2 — sixteen dead rename keys, waiting

Each keyed a prep-network name that repo had since renamed away, so none could fire.
That made them look harmless. They were not: a dead key is **loaded**, and fires the
day some school happens to be named that string — which is exactly what Wheatley did.

> ⚠️ `RENAMES` is a permanent record of renames that are still REACHABLE. An entry
> matching neither prep-network nor any school here is debris, not history. Prune it.

## Fault 3 — a rename cost a school its history

The archive keys on the display name at the moment a season was written. Rename the
program and every row it had already earned orphans: its page finds nothing under the
new name, and the old name is nobody's school, so that page 404s too. **Cherry Hill
North won 8A in 2031 and vanished from its own program page.**

The data was never lost. Only the link.

**Fixed** by relabelling archived seasons into today's names **on read** rather than
migrating rows — the archive stays the record of what was written, and the next rename
needs no migration at all.

> ⚠️ The relabel is **key-driven, not a blanket string swap.** Ten former school names
> are also live TOWN names — Port Veles, Ashbury, Telfair, Orellana. Replacing every
> string that matched a former name would have rewritten addresses. Everything is a
> school name EXCEPT the places and units, which is the safer way round: a shape the
> rule misses keeps an old name — a visible broken link — where a blanket swap would
> quietly move a school to another town.

**And the alias table cannot be typed.** Renaming a school twice REWRITES the target in
place (the rule: never chain A → B → C), so intermediate names survive only in git.
`scripts/jhsaa_former_names.py` walks every revision of `import_jhsaa.py` and reads what
`RENAMES[source]` held at each — 698 aliases, into a readable block beside `RENAMES` and
into `data/jhsaa/former_names.json`, because **the app reads data files, not `scripts/`**.

> ⚠️ **A LIVE NAME ALWAYS WINS.** `jhsaa.current_name` checks live schools before the
> alias map. A retired name reissued to another program must never make a lookup serve
> the wrong school's record.

## Fault 4 — the same shape, in a table nobody swept

`AREA_RENAMES` is keyed on prep-network's CURRENT name. That repo renamed **Mother Lode
→ Siskiyou Valley**, so the entry stopped firing and a full import would have emitted
"Siskiyou Valley" for an area the association has always called **Southern Jefferson**.

Nothing could have shown it: the committed data already holds the right string, so every
page reads correctly until someone re-imports. It was caught by a consistency check
added to the gazetteer generator on its **first run** — not by reading the table.

> ⚠️ When a rename table is keyed on ANOTHER repo's names, that key is a foreign
> reference with no constraint behind it. Something must compare the two sets, or the
> table dies quietly.

---

## What I got wrong, and it is worth being specific

**A guard I added was wrong in the opposite direction.** After Wheatley I wrote a check
refusing any `RENAMES` key that was a live school's own name. That is the ORDINARY path
— a school never renamed IS its own identity, so every first rename looks like that. It
blocked four legitimate town-school renames before I noticed. The real fault is
*ambiguity*: a key matching one school's own name AND another's `source`.

> ⚠️ A guard written from one incident tends to forbid the incident rather than the
> fault. Ask what the SHAPE was, not what the instance was.

**I reported a problem instead of fixing it.** The owner: *"you could just rename those
same-named schools to avoid it from being an issue at all rather than badger me about
it since I cannot really understand what you're saying."* Correct. A structural fix I
can make myself does not need explaining first.

**I applied a spec's own list without flagging a consequence.** The 111-family pass
included three Cherry Hill schools; renaming them was in the spec and the owner had not
meant it. They were reverted. Worth noting only because the *reason* it mattered was
Fault 3 — a rename of a school with a title is not the same act as a rename of one
without.

**I got the direction of a two-column list backwards**, treating the owner's own name
bank as the thing to be replaced. Thirteen renames had to be retargeted. When a list is
`A -> B`, which side is the input is not always obvious; ask before applying 15 of them.

---

## Redistricting — what the measurement showed

A league is cut from a geographic ORDER into blocks of `MAX_DISTRICT`. That keeps most
leagues tight and dumps the REMAINDER — whatever is left once the metros have filled
their own blocks — into leagues that are geographic leftovers rather than regions.

| class | worst span | mean span | leagues over 250mi |
|---|---|---|---|
| 8A | 362 → 112 mi | 155 → 68 | 2 → 0 |
| 7A | 397 → 213 mi | 181 → 79 | 3 → 0 |
| 6A | 397 → 191 mi | 206 → 92 | 5 → 0 |

> ⚠️ **THE NAMES STAY.** League identity is a curated dataset — real league names
> persist through realignment and the drift IS the realism — so the redraw creates no
> new leagues. It keeps the ones each class has and moves SCHOOLS between them, each
> block inheriting the name it most overlaps. A realignment must read as a realignment,
> not a rebrand.

Three details that are load-bearing:

- **Assignment order is REGRET**, not nearest-centroid: how much worse a school's
  second-best league is than its best. Plain nearest-centroid hands one metro every seat
  while its neighbour starves.
- **League size IS the schedule.** The capacitated pass leaves a rump; a floor pass pulls
  it back to strength by taking the geographically NEAREST available member — nearest, so
  fixing the size does not undo the geography the redraw was for.
- **Rivalries are repaired last** and outrank geography, exactly as they outrank
  reclassification.

`COMPETITIVE_MOVES` is the mirror of `PLAY_UP`: a program may be placed BELOW its
enrollment class when it cannot compete where enrollment puts it, with the enrollment
scaled to match rather than the other way round — the numbers are fictional and nothing
about them is permanent, so **the number follows the decision instead of blocking it**.

> ⚠️ It moves `group`, NEVER `classification` — the same invariant play-up rests on.
> Keyed on `group`, a demoted school would also be GENERATED with the weaker class's
> talent, turning a fairer field into a self-fulfilling collapse.

---

---

# Round two — the 2033 realignment, and three corrections that were all one correction

Everything above was written before the owner read it. Three of its conclusions were
wrong, and they were wrong the same way: **each had taken an implementation detail and
promoted it to a rule.**

## Correction 1 — "THE NAMES STAY" was half a rule

I wrote that in capitals. The owner: *"in real life leagues realign and rebrand all of
the time, do a search on OSAA."*

That search settles it. The OSAA runs a **four-year classification-and-districting
period**, and the current one — [approved for 2026-30 and effective 2026-27
](https://www.osaa.org/news/4704) after a four-month review, 300+ written submissions
and testimony from 171 groups — did not merely reshuffle membership. It created a
brand-new **seven-team 6A/5A Southwest Hybrid**: Ashland, Crater and Eagle Point
alongside Grants Pass, Roseburg and both Medfords, the state's [second hybrid
conference](https://www.osaa.org/news/4601) after the Midwestern. A league that did not
exist before now does, and the schools in it did not previously share one.

So the rule is the half I had: **a block INHERITS the name it most overlaps**, because
a league keeps its historical core. What I had wrongly made absolute is the rest — a
class that GAINS leagues draws new names from `LEAGUE_NAMES`, a class that loses them
retires names, and a block with no free overlap **rebrands** rather than reaching for
some unrelated leftover name and putting it on schools that never carried it.

> ⚠️ I had turned "names persist through realignment" — which is true of *a* league —
> into "a class has the leagues it has forever", which is true of no association
> anywhere. **A property of an object is not a property of the set.**

## Correction 2 — a cap I had been treating as a target

`draw_districts` took `k = ceil(n / MAX_DISTRICT)`: the FEWEST blocks that fit under the
cap. So every class packed its leagues to 11-12 and **the ceiling silently became the
design.** The owner had said this before: *"no conference should be over 12 teams like
I said before, with 40 teams there's no reason for some weird cap on districts when
smaller ones (around 10 teams) would be fine."*

`import_jhsaa.district_count(n)` is now the one authority — aim at `DISTRICT_TARGET`
(10), never exceed `MAX_DISTRICT` (12) — and both the importer and the redistricter read
it. Every class in the association now runs 9-12, none over.

**And the redraw trigger was the same mistake.** The condition for "this class needs a
redraw" was *does it still fit under the cap*, which can only ever fire on GROWTH. So
the class a realignment takes schools OUT of kept whatever leagues it had at whatever
sizes were left over — 3A would have come out of this at eleven leagues averaging 8.5,
one of them at six. It is `district_count` in **either direction** now.

That same fix swept up something four rounds old: 1A's **Rim Country League had 13
members** since the 1A/2A split, listed as "still open" above precisely because no
reclassification was ever going to touch a class where nothing had changed. A cap is
enforced wherever it is broken, not only where a pass happens to be looking.

## Correction 3 — strict geography was never the constraint

The redraw minimised span. The owner: *"strict geography isn't a major constraint here,
no different than real life (see what the OSAA does to the Bend schools or others due
to distance)."* Correct — and the Southwest Hybrid above exists **because** the
geography left no tidy answer.

Distance is a cost, not a rule. **Size wins:** a league near the target with one distant
member is a better league than a tight one with six, because district size IS the
schedule. The floor is now the target rather than an even split of whatever the class
happens to hold. 2A comes out with two leagues over 250 miles and that is the right
answer, not a defect to iterate on.

---

## The realignment itself

32 named 3A schools move to 2A. 2A: 63 → **95 programs, 10 leagues, a 40-team field**.
3A: 125 → **93 in 9**. 1A untouched. Every class clears `sponsor_floor` (2A at 95
girls'/87 boys' against 76), no league is over 12, and 305 schools changed league across
the nine-class redraw.

| class | worst span | mean span | over 250mi |
|---|---|---|---|
| 9A | 429 → 122 mi | 158 → 62 | 2 → 0 |
| 5A | 389 → 243 mi | 147 → 83 | 2 → 0 |
| 4A | 387 → 227 mi | 197 → 90 | 4 → 0 |
| 3A | 419 → 256 mi | 225 → 112 | 5 → 1 |
| 2A | 373 → 303 mi | 229 → 149 | 5 → 2 |
| 1A | 369 → 218 mi | 205 → 129 | 3 → 0 |

> ⚠️ **It is a RECLASSIFICATION, and that is why it moves `classification` as well as
> `group`.** The distinction from `COMPETITIVE_MOVES` is not bookkeeping: `_TALENT`
> generates from `classification`, so a school moved on `group` alone keeps its old
> class's players and would walk its new class. That is *correct* for a program
> petitioning down on RESULTS — it is supposed to keep the roster it has — and wrong
> here, where the association is saying these schools are 2A-SIZED. They are: every one
> already sat inside 2A's committed enrollment band (306-375 against 86-431), so the
> owner's "scale the enrollment to justify it" lever was available and not needed.

It is a NAMED TABLE rather than a moved cut line because the owner named the schools. A
line at ~380 takes a different 32 — 3A's smallest program is 303 and stays 3A — and the
association's judgement about which programs belong where is the input, not a threshold
reverse-engineered to approximate it.

## The one that was already fixed

*"the boys & girls separate leagues thing needs to be fixed, i've only said it a million
times."* This AAR said 30 schools in 3A/4A/5A still had it. **They did not.** All 30
were schools that sponsor GIRLS tennis and not boys, so `boys_district` is empty — which
is not a mismatch, it is the correct representation of not having a boys' programme.
Measured both ways: zero rows where both fields are populated and differ, and zero
runtime mismatches across 862 girls' and 777 boys' schools.

> ⚠️ I generated that finding with a `girls_district != boys_district` filter and wrote
> it into an AAR as an open defect without ever looking at a row. **An empty field is
> not a different value**, and a count is not a finding until you have read one of the
> things it counted.

## Still open

- **`COMPETITIVE_MOVES` is empty.** Candidates come from results, and the working copy
  here has no archived season to read them from. Unchanged from round one — and note
  that the 2033 realignment is NOT it: that was a reclassification, and the two are
  deliberately different mechanisms.

---

# Round three — the 2039 cross-class realignment, and one thing that did NOT happen

30 schools moved to new classifications for the 2039 season, from an owner list of exact
`school -> class` pairs pulled from that season's actual research export (the live save
had already drifted from what was committed — see below). **No tennis was added
anywhere.**

## The move itself

`import_jhsaa.RECLASSIFY_2039` is a second named table, the same shape as
`RECLASSIFY_TO_2A` and applied the same way — display-name keyed in the full-import
path (`reclassify()`), name-keyed directly in the transform (`scripts/
jhsaa_reclassify.py`'s new `reclassify_named()`) — with one difference from the 2033
pass: **every single one of these 30 needed its enrollment rescaled.** The 2033 moves
all already sat inside 2A's band; none of these do — the spread runs from a
216-enrollment 2A program reclassifying to 8A to a 2,550-enrollment 9A program
reclassifying to 8A, in both directions and across as many as seven classes at once.
`_reclass_enrollment(name, group)` gives each a stable, hash-seeded number inside its
new class's committed band (`_CLASS_ENROLLMENT_BAND`, the nine contiguous ranges
already measured off the committed data) — the same one-point-per-band idiom
`jhsaa.roster_size` uses for depth, applied here to the OTHER number a classification
determines.

> ⚠️ This is the case `RECLASSIFY_TO_2A`'s own docstring named as the exception —
> "only needed when the number would otherwise contradict the move" — except here it
> is not the exception, it is universal. Checked before writing any code: of the 30,
> **zero** already fit their target band.

Two schools (Valley Christian, Baptist) carried a seeded `play_up: true` flag from
being small blue-bloods playing up out of 3A/1A. Both are now genuinely 6A-classified,
so the flag is cleared on the move — harmless either way (`can_play_up` gates on
`classification` and 6A fails it outright), but a stale flag is still a lying field.

Leagues: most of these 30 simply **joined an existing league in their new class**
(`rehome()`, unchanged from the 2033 pass) — 6A, for instance, gained and lost enough
members in different directions that its league COUNT never moved (114→111, still
wants 11). Two classes crossed a `district_count` boundary and got a full geographic
redraw: **1A** (81→91, 8 leagues→9) and **2A** (95→94, 10 leagues→9). Nothing else was
touched.

## The thing that did NOT happen: no tennis was added

The owner's instruction authorized adding boys tennis sponsorship where needed "to
ensure the classifications stay with enough teams... to run the playoff format at 40
teams." **It was not needed.** Measured before making any change and again after:

| class | boys, before | boys, after | floor |
|---|---|---|---|
| 1A | 74 | 84 | 48 |
| 2A | 88 | 88 | 76 |
| 3A | 84 | 84 | 76 |
| 4A | 98 | 94 | 76 |
| 5A | 90 | 89 | 76 |
| 6A | 99 | 96 | 76 |
| 7A | 84 | 82 | 76 |
| 8A | 80 | 80 | 76 |
| 9A | 83 | 83 | 76 |

Every class clears `sponsor_floor` in BOTH states, with 8A the tightest at 80 against a
76 floor. `EXTRA_SPONSORS`/`NEVER_SPONSOR` (`scripts/import_jhsaa.py`'s sponsorship
tables) are untouched by this round — nothing was forced in or out.

> ⚠️ The permission was conditional ("as needed"), not a standing instruction to add
> sponsorship regardless. Check the floor before reaching for the mechanism it
> authorizes — the owner asked for a specific outcome (a runnable 40-team field), not
> for the lever itself to be pulled.

## A branch reset, not a rebase — because the PR had already merged

Before this round started, `PR #308` — everything in rounds one and two — had already
merged into `main` (plus unrelated work landed by other sessions: the JV season,
analytics). The owner's "rebase main before starting" is not literally what happened:
a rebase replays commits already on the branch onto a new base, and every commit on
this branch was already IN that base. The correct move, per this repo's own standing
rule for a merged PR, was to restart the branch from `origin/main` — `git checkout -B
<branch> origin/main` — rather than attempt a rebase with nothing left to replay.

## Where the move list came from

The owner supplied two things: a plain list of `school -> class` pairs, and — separately,
mid-session — a pair of research-export zips for the actual 2039 season, "for context...
which might not be reflected in the repo, but should be." Cross-checking the two showed
the committed `data/jhsaa/schools.json` had drifted from the live save it was meant to
describe (e.g. `Baptist` was archived at `class=1A, group=4A` — already playing up —
while the committed file had it at a bare 1A with no override). The move list matches
the export's TARGET classes, not its stale committed state, which is what "the enrollment
is just scaled to meet the new class" (owner, this round) actually resolves: the fictional
number follows wherever the owner's decision says the school now plays, not wherever a
stale JSON row still says it does.

## The generated documents this run added

Each exists because the hand-kept version of it was wrong, and each is regenerated after
any rename batch:

| file | what it answers |
|---|---|
| `docs/JHSAA-school-names.txt` | every school, and which names fail to differentiate |
| `docs/GAZETTEER-jefferson.md` | where a school is — in the association's own names |
| `prep-network/docs/JHSAA-name-map.txt` | why the two repos disagree, and by how much |
| `data/jhsaa/former_names.json` | what a school used to be called |
