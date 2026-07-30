# AAR — a program with fewer than six players crashed the engine

**Date:** 2026-07-30
**Status:** Roster floor, walk-on personas and match RETIREMENTS landed. Mid-season
injury walk-ons stood down by the owner ("you solved the walk-on problem").
**Scope:** `engine.dual._pair` (guard), `ncaa.LINEUP_SIZE` / `WALKON_BAND` /
`walkon_talent` (new), `ncaa.squad_and_ladder`, `world.refill_walkons`,
`injuries.RETIREMENT_RATE` / `roll_retirement`, `seasonmode._mark_retirements`,
`tests/test_dual.py`, `tests/test_world.py`, `tests/test_injuries.py`.

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

* Rosters thin toward ~6–8 over seasons — D1 never signs walk-on depth (owner rule
  2026-07, CLAUDE.md §3b). That rule exists to keep D1 rosters SMALLER than
  D2/D3/D4, so the portals can oversign and rebuild quickly without mass cuts. It was
  never a licence to drop below a playable lineup — but nothing enforced a floor.
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
still get walk-on **depth** beyond it, so the D1 rule is intact: D1 rosters stay the
smallest, which is the whole point of it — cheap portal rebuilds without mass cuts.

The floor fills with **generated** walk-ons, never with pool or portal players — the
point of the D1 rule is that a low-major must not absorb a body who would start
somewhere lower down. A program that simply never gets portal help and sits at 7 is
left alone; the floor is 6, and only a roster that literally cannot field a lineup is
topped up.

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

**A rule about RELATIVE size is not a licence to hit zero.** "D1 carries no walk-on
depth" was written to keep D1 rosters smaller than the other divisions so portal
rebuilds stay cheap. Read literally it also permits a roster of four, which nobody
intended and only the engine noticed. When a rule constrains one end of a range,
state the other end too.

## Match retirements

A rare mid-match injury ends the match as a **retirement** — in tennis the scoreline
reads "retired" rather than abandoned, and it happens ONLY after an injury, never as
a way to concede.

* `injuries.RETIREMENT_RATE = 0.002` per **completed singles match**, so it scales
  with how much tennis is actually played. Owner picked 0.2% from two candidate
  sizings; on D1's ~9,700 singles matches per gender per season that is roughly 19 a
  year, a handful per conference.
* Rolled on the same real entropy as every other injury (CLAUDE.md: injuries are the
  one deliberately non-deterministic system) — a retirement IS an injury outcome.
* **A retirement does not care what the score is.** The retiring player is drawn
  independently of who the sim said won, and retiring LOSES them the line even if they
  were ahead — that is the whole difference between a retirement and a normal loss
  (real ATP examples: *Murray d. Djokovic 6-4 3-0 RET*, *Guccione d. Nadal 6-5 RET*).
  When that flips a line, the dual's points and winner are corrected too.
* `seasonmode._mark_retirements` relabels the line (`retired`, `retired_pid`) and
  GUARANTEES that player an injury rather than merely rolling for one — the retirement
  IS the injury becoming visible. A player retires because they have to.
* **No walkovers, anywhere** (owner rule). A walkover is a no-show before play starts;
  in college you just put another rostered player on court, so it does not arise —
  and there is no reason to simulate one in the individual championships, the cups or
  the pro league either.

## What's left

**Mid-season injury walk-ons** — stood down by the owner. The rollover floor covers
season start; a team injured below six mid-season would still need a mid-season write
path and the `[WO]` tag through the box score. Design captured here if it is ever
wanted.
