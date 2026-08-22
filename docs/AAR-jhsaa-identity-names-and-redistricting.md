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

## Still open

- **1A's Rim Country League has 13 members**, one over `MAX_DISTRICT`. Pre-existing,
  outside the classes this run touched.
- **30 schools in 3A/4A/5A have different boys' and girls' leagues**, which the
  association's own rule forbids. The 6A/7A/8A redraw fixed 20 incidentally by deciding
  membership once per school, which is what that rule means. The rest need the same
  treatment — but 2A/3A were being realigned separately, so they were left alone.
- **`COMPETITIVE_MOVES` is empty.** Candidates come from results, and the working copy
  here has no archived season to read them from.

## The generated documents this run added

Each exists because the hand-kept version of it was wrong, and each is regenerated after
any rename batch:

| file | what it answers |
|---|---|
| `docs/JHSAA-school-names.txt` | every school, and which names fail to differentiate |
| `docs/GAZETTEER-jefferson.md` | where a school is — in the association's own names |
| `prep-network/docs/JHSAA-name-map.txt` | why the two repos disagree, and by how much |
| `data/jhsaa/former_names.json` | what a school used to be called |
