# AAR — a program with fewer than six players crashed the engine

**Date:** 2026-07-30
**Status:** Roster floor + walk-on personas landed. Mid-season injury walk-ons and
match retirements are specified but NOT built (see "What's left").
**Scope:** `engine.dual._pair` (guard), `ncaa.LINEUP_SIZE` / `WALKON_BAND` /
`walkon_talent` (new), `ncaa.squad_and_ladder`, `world.refill_walkons`,
`tests/test_dual.py`, `tests/test_world.py`.

## Symptom

Live save, dashboard 500:

```
File "engine/dual.py", line 81, in _pair
    return DoublesTeam(players=(pool[pair[0]], pool[pair[1]]))
IndexError: list index out of range
```

## Root cause

`Team.doubles` defaults to `[(0, 1), (2, 3), (4, 5)]` and indexes into the singles
list. Any side with fewer than six available players hit `pool[5]` and took the whole
page down mid-bracket.

Two ways to get there, **both intended behaviour elsewhere**:

* Rosters thin toward ~6–8 over seasons — D1 never signs walk-on depth, so it "runs
  short" (owner rule 2026-07, CLAUDE.md §3b).
* Injuries can cut a six-man roster below six at lineup time.

Measured: **a freshly generated world has zero programs under six.** That is why this
never appeared in testing and only surfaces in a played save.

## The wrong fix, and why review caught it

The first attempt synthesised filler inside `ncaa.squad_and_ladder`. Two review
findings, both right in mechanism even though the severity did not reproduce:

1. `generate_prospect` still ran the nation elite roll, so a floor filler *could*
   spike into the 68–80 bands regardless of the low talent passed. Measured on 240
   generated fillers the roll fired **0 times** and filler topped out at **OVR 55**
   against a real top six of **61–73** — so no phantom blue-chip in practice, but the
   path was open.
2. Worse and not probabilistic at all: the filler's pid existed in **no roster, no pid
   index and no persisted world**. If one reached an individual championship,
   `championship_to_dict` would persist that pid, the UI would link to it, and the
   page would 404 — with any stamped honor pointing at a player who does not exist.

Owner's call, which dissolves both: *"the trick is just not to let teams ever get
below 6 players."*

## The fix

**The floor lives where rosters actually change.** Moved out of `squad_and_ladder`
and into `world.refill_walkons`, which runs at the rollover on the real roster that
gets persisted and indexed. Every division now gets a hard floor of six; only D3/D4
still get walk-on **depth** beyond it, so the D1 rule is intact — "runs short" means
8 → 7, not a program that cannot put six on court.

**Walk-ons are explicit personas.** `ncaa.WALKON_BAND` gives a talent range per
division × gender, replacing the old implicit "division mean minus 8":

| | men | women |
|---|---|---|
| D1 | 40–50 | 34–44 |
| D2 | 34–44 | 29–38 |
| D4 | 32–42 | 28–37 |
| D3 | 26–36 | 23–31 |

Tier-ordered and gender-ordered, both asserted in tests. A walk-on is a known
quantity: clearly below its tier's recruited core, and a D1 walk-on is a different
animal from a D3 one.

**`engine.dual._pair` keeps a guard** — indices wrap and a player is never paired with
themselves — as a backstop for saves that are *already* below six, since the floor
only applies from the next rollover. A crash here takes out a whole page, so it
degrades instead.

## Rule

**A default that encodes a size is a constraint.** `Team.doubles = [(0,1),(2,3),(4,5)]`
silently requires six players, and nothing in the roster layer knew that. When one
module hard-codes positions into another module's list, state the floor where the list
is built, not where it is read.

**Generated filler must be a real, persisted, indexed entity or not exist at all.**
A synthetic player that never enters `build_roster`, the pid index or `world_roster`
will look fine everywhere except the one surface that follows its id — and that
surface will 404 long after the code that created it is forgotten.

**"Runs short" needs a floor.** Any design that deliberately lets a resource shrink
must say where shrinking stops. Thinning to 7 was intended; thinning to 5 was never
considered, and only the engine noticed.

## What's left (specified, not built)

Both are owner-specified and the design is settled; neither is implemented.

1. **Mid-season injury walk-ons.** The rollover floor guarantees six at season start,
   but injuries can drop a team below six *during* a season — the owner's actual case.
   Needs a mid-season write path (rosters are only persisted at rollover) plus the
   `[WO]` tag rendered next to the name in box scores and roster views. Owner's
   preference is explicit: these SHOULD persist, so the data and team history are
   trackable, and they carry everything a real player has — name, class Fr–Gr, a
   persona — differing only in the tag.
2. **Match retirements.** A rare mid-match injury ends the match as a *retirement*:
   the scoreline reads "retired" rather than abandoned, and ONLY following an injury.
   Sizing needs one decision first — the owner gave "a rare 5th of 1%" and "~5 per
   conference per year / 100–200 total", which disagree by ~8x: D1 alone plays ~9,700
   singles matches per gender per season, so 0.2% is ~19 and 5-per-conference is ~160.
   Build it as a tunable rate and calibrate to whichever is meant.
