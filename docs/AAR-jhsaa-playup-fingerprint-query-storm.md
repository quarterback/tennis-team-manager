# AAR — the JHSAA rung that never finished (65 million database queries)

## The report

Owner, 2026-08, on a first world advance: *"the high school sim just keeps running,
clearly something is wrong."* The screen sat at **277s elapsed and climbing** where the
UI's own copy promises about a minute.

The showcases had landed immediately before, so they were the suspect. They were not
the cause. **The cost was ~65 million SQLite round trips in roster generation**, and it
had been there since the play-up feature (#257) landed one PR earlier.

## The measurement that ended it

One program. Not a season, not a gender — one:

```
ONE build_roster: 6.19s
  load_schools calls        : 2
  playup_version DB queries : 39,776
```

At ~1,630 programs a rung, that is **~65 million queries and ~2.8 hours**. It was never
going to finish, which is exactly what "just keeps running" looks like from outside.

## The chain

```
build_roster
  └─ _program_mod                     (per program)
       └─ upstarts()                  NOT memoised — walks the whole association
            └─ load_schools() × 2     (both genders, rebuilt every call)
                 ├─ _playup_districts(rows)      walks the rows twice more…
                 │    └─ mover loop: all 857 rows PER MOVER
                 └─ per-row: _plays_up_row(r)
                      └─ plays_up(name, seeded)
                           └─ ov.jhsaa_playup_version()
                                └─ SQLite connect + query + close   ← every call
```

## ‼️ The defect worth naming: a cache keyed on something expensive to compute

`_playup_cache` **was** a memo cache. It was correct. It saved nothing:

```python
hit = _playup_map(ov.jhsaa_playup_version()).get(school_name)
```

The map was cached; the **key** cost a database round trip to produce. So every lookup
paid the price the cache existed to avoid, and the cache looked completely reasonable in
review — it has a version, it publishes into a local, it clears per version, it obeys
every rule in CLAUDE.md's threaded-worker section. All of that is true and none of it
helped.

**A memo cache is only as cheap as its key.** If resolving the key touches the database,
the filesystem, or anything else you would not do in a tight loop, the cache is a
decoration. Resolve the key ONCE at the top of the operation and thread the resolved
value down.

## ‼️ Nobody asked for this — it was an agent's own design choice

Worth stating plainly, because it is the part a future agent is most likely to repeat.

**What the owner asked for was a game rule and an editor**: a small school may compete
one classification above its enrollment class, and — in their words — *"I was promised
the ability to edit a handful of play up schools and that was it."* That is the whole
requirement. Nothing in it says anything about where the answer lives or how often it is
fetched.

**Note the size of the thing.** A handful. The seed list is **13 schools**, and the
override table on top of it is normally empty or a row or two. The correct
implementation of "a handful of editable rows" is to read the handful **once** and hold
it. Instead the association's 857 schools were each asked, individually, three times per
`load_schools`, twice per program — and every one of those questions opened a database
connection to re-derive a fingerprint over a table with about a dozen rows in it.
**39,776 queries to answer a question about 13 schools, in order to generate twelve
players.**

**What an agent built** was an override table read through a fingerprint-keyed memo
cache, and then called from inside `load_schools` — the single hottest loop in the
association, walked once per row, three times per call, twice per program. The owner
could not have reviewed that decision: it is invisible from the rule, invisible from the
function signature, and invisible in a diff that reads as "check whether this school
plays up".

The lesson is not "avoid caches" or "avoid override tables" — a handful of editable rows
is exactly what was asked for and it stays. It is:

> **When you add a lookup to satisfy a rule, you own where that lookup happens.** The
> owner specified behaviour and a small editor. The cost class is yours, it is not
> implied by the request, and putting a database read inside a loop over the whole
> association is a decision that has to be made deliberately rather than fallen into.

**Match the machinery to the size of the problem.** Thirteen rows do not need a
fingerprint-keyed invalidation protocol consulted per school per pass; they need to be
read once. The elaborate version is not more correct — it produced the same answers,
just 39,776 times, at 6.2 seconds a program. Owner: *"a handful of play up schools and
that was it… not some crazy SQL wild goose chase."*

## Why nobody saw it

`load_schools` was a **pure JSON-to-objects loop with no database access at all** until
play-up landed. That is why it was never cached: rebuilding a few hundred dataclasses is
genuinely free, and caching it would have been premature. The play-up feature put
`_plays_up_row` into the per-row loop, and in doing so changed the function's *cost
class* — from "pure, free, call it as often as you like" to "one database round trip per
school per pass" — without changing its signature, its return type or any of its call
sites.

**That is the general shape to watch for: a change that alters a function's cost class
while leaving its interface identical.** Every caller keeps calling it the way they
always did, because nothing about it looks different. `upstarts()` calling it twice per
program was a perfectly sensible thing to write against the old cost and catastrophic
against the new one.

## The fix

- Resolve the play-up fingerprint **once** per `load_schools`, and thread the resolved
  map down through `_playup_districts` and `_plays_up_row`.
- Cache the **built `School` objects** per `(gender, version)` — `_schools_cache` only
  ever held the raw JSON, so the objects were rebuilt on every call.
- Memoise `upstarts()` per `(year, salt, archetype_version, playup_version)`. It is a
  pure function of those and was being recomputed per program.
- `_program_mod` asked for the same `archetype()` twice; once.

Caches compute into a local, publish, and return the local, per the gthread rule.

| | before | after |
|---|---|---|
| first `build_roster` | 6.190s / 39,776 queries | 0.036s / 4 queries |
| per program thereafter | 6.19s | 0.0039s / 1 query |
| all ~1,630 programs | ~2.8 hours | **~6.3s** |

**Rosters are unchanged** — identical md5 over both genders' school lists and every
generated player's pid, name and overall, before and after. This was pure plumbing; if
it had moved a single player it would have been the wrong fix.

## What the debugging got wrong, which cost more than the bug

1. **I assumed the newest change was the cause.** The showcases landed last, so I spent
   the first half of this rewriting showcase grouping. That work was worth doing on its
   own merits and was **not** this bug. Recency is a hypothesis, not evidence.
2. **I tried to reproduce before I tried to read.** Two harnesses ran past their
   timeouts in a container that cannot build a full association, and returned nothing.
   The actual diagnosis came from reading the call chain and then writing a **six-line
   probe that counted database calls for one program** — no season, no simulation, a few
   seconds to run. Counting the work is almost always cheaper than reproducing it.
3. **I burned the owner's budget doing it.** Called out, correctly, mid-investigation.

The thing that finally worked: pick the innermost suspicious call, **count how many
times it happens for the smallest possible unit of work**, and multiply. 39,776 for one
program answers the question instantly and costs nothing.

## What to check first if this looks wrong later

- **The rung slow again.** Count queries for one `build_roster` before anything else —
  monkeypatch `ov.jhsaa_playup_version` / `ov.jhsaa_archetype_version` with a counter.
  It should be a handful. Four figures means a fingerprint is back inside a loop.
- **A play-up or archetype edit not taking effect.** `reset_schools()` must clear
  `_schoolobj_cache` and `_upstart_cache` as well as `_schools_cache` and
  `_playup_cache` — the built objects bake `group` and `district` in.
- **A `School` mutating under someone.** `load_schools` now hands out the *same* list to
  every caller. It is read-only by contract; nobody mutated a `School` when this landed.
