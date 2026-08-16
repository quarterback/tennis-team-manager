# BRIEF — renaming Jefferson's invented-person high schools

**For:** a future agent, on the owner's instruction ("just put that in a doc for
a future agent and I'll run that another time").
**Status:** NOT STARTED. ~269 schools of 857 still carry invented-person names.
**Files:** `data/jhsaa/schools.json`, `scripts/import_jhsaa.py`
(`RENAMES`, `MASCOTS`), and nothing else.

## The rule

> "the fictional people are kind of boring me… this is how real schools get
> named after all"

Jefferson's generator produced whole FAMILIES of schools named for invented,
unrelated people — eight Crosses, seven Bookers, six Corderos, five Aramburus,
five Tillmans, five Stokeses — which reads as a bug rather than as a state.
Replace them with **real people**.

**A single invented person is fine and always was.** Amelia Freeman stays. It
is the families that break immersion, so a surname with one school can be left
alone; the ones to work through are the repeats. `Preparatory` in the count
below is a false positive (St. X Preparatory) — skip those.

## The pools, in the owner's order of preference

1. **Presidents** — **Port Veles only**, and that city is DONE (Washington
   through Biden). Do not spend presidents elsewhere.
2. Vice presidents
3. Secretaries of State
4. Secretaries of War
5. Postmasters General
6. **Suffragists**
7. **Pioneers of consequence**
8. **The civil rights movement**, named explicitly by the owner: **Malcolm X,
   Marcus Garvey, Fannie Lou Hamer, Emmett Till** — and others of that stature.

Where a real person is not wanted, the town's own idiom serves: "Veles Area"
(the owner's coinage) and harbour/landscape features beside it.

## ‼️ Vet the pool. Use judgement and reject people, do not stop and ask.

The owner's instruction after I stopped to check: *"you should have just done it
like i told you to and used the judgement to reject whoever instead of
stopping."* So exercise judgement inline.

What that means concretely: the 19th-century War and State departments are
thick with Confederates and slaveholders — **Jefferson Davis was Secretary of
War, John C. Calhoun was both** — and the owner has already vetoed a name on
exactly those grounds:

> "Andrew Jackson … NO WAY i WANT THAT war criminal with a high school in my
> state."

Skip secessionists, slaveholders, architects of removal, and the openly
disgraced. Skip **Thomas Jefferson** for a different reason: it is the state's
own name.

## The mechanics — all of it applies

- **One school per name.** No name on any list gets two schools. Check the
  whole file, not just your batch: `John F. Kennedy North` and `Andrew Jackson
  North` both survived earlier passes and had to be cleaned up later.
- **A person's name never takes a directional qualifier.** There is no "Sandra
  Day O'Connor North" and no "<person> North" at all — *"Freeman North is not a
  thing."* A split campus of a renamed school takes a PLACE name off its own
  town instead.
- **Never two directions in one name** — "Port Veles West North" is the shape
  the owner rejected on sight.
- **A town with the same name twice** qualifies the second by its town —
  "Jefferson Heights Polk" — never by a suffix.
- **No institutional suffix**, ever: "John Quincy Adams High School" is emitted
  as `John Quincy Adams`. See the school-names section of `CLAUDE.md`.
- **Stamp `source`** with the pre-rename name on every row. Generation keys pids
  on `source or name`, so a rename without it hands the program twelve strangers
  and points its archived awards at nobody.
- **Display names must stay unique** — the display name IS the archive identity
  (`world_jhsaa_dual.school`, the routes, the pid space). `build` refuses to
  emit a collision; keep it that way.
- **Record every rename in `RENAMES`**, keyed by SOURCE name, or a re-import
  rebuilds the old names. Applied at emit only — the district draw sorts on the
  source name, so renaming earlier reshuffles the leagues.
- **Mascots stay with their school.** If a `MASCOTS` entry is keyed by a name
  you are changing, move the key and keep the value.

## ‼️ The trap that cost me a commit

Do **not** run a regex over the whole import file. `RENAMES` is not the only
dict keyed by school name: a `re.sub('"<source>": "[^"]*",')` sweep rewrote
seven `MASCOTS` entries with school names — `"Anneliese Halvorsen": "George
Washington"` where `Sockeye` belonged — so six schools would have been built
with a person's name as their mascot, and **nothing errored**. Slice the file at
the dict you mean to edit and substitute only inside that slice.

Verify after every pass, against the data rather than by eye:

```python
# names unique; no doubled directions; no "<person> North";
# every MASCOTS value still a mascot; every rename round-trips
assert len(names) == len(set(names))
assert not [n for n in names if sum(w in DIRECTIONS for w in n.split()) >= 2]
assert not [k for k, v in MASCOTS.items() if v in set(names)]
assert all(_display_name(RENAMES.get(src, src)) == name for src, name in renamed)
```

## Scope

~269 schools. Measured with a place-word filter over `schools.json`; re-measure
before starting, since this session renamed 50-odd already. Work by repeated
surname, biggest family first — that is where the immersion damage is, and a
surname down to one school can simply be left.
