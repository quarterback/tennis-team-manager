# AGENTS.md — `engine/`

Match simulation. Points, games, sets, tiebreaks, duals, doubles, formats, box stats.
No web, no database, no league logic. Everything above this layer calls into it.

## Files

| File | Responsibility |
|---|---|
| `match.py` | A single match: point → game → set → match resolution. |
| `rally.py` | Point-level resolution. |
| `dual.py` | A dual: assembles flights into a team result. |
| `doubles.py` | Pair construction and doubles-specific behaviour. |
| `format.py` | Format definitions — set counts, tiebreaks, dual shapes. |
| `state.py` | Scoreline state machine. |
| `boxstats.py` | Per-match statistical output. |
| `render.py` | Play-by-play and scoreline rendering. |
| `tournament.py` | Generic bracket resolution. |
| `fast.py` | Fast path for bulk simulation. |
| `gtt.py` | Pro-league engine hooks. |

## Rules

**Determinism is the contract.** Same seed, same inputs, same transcript and same scoreline.
`manage.py` exists partly to prove this from the CLI. Anything introducing entropy here is a
bug — injuries are the one intentional exception and they live in `app/`, not here.

**Never hard-code a format.** Set counts, tiebreak rules and dual shapes are configuration,
read through `format.py`. The regular-season dual format has already swapped from 5S/2D to
3S/4D, and every hard-coded copy of a shape went stale silently when it did.

**Never hard-code the gap-response curve.** The mapping from rating difference to win
probability has been rebuilt twice. It is a per-point slope array applied cumulatively, and
it belongs in exactly one place. A table copied to a second location is a future silent
failure.

**Doubles is not singles with two players.** It converts rating separation into results
faster than singles does — measurably steeper at the same gap, with lower three-set rates.
Anything modelling expected wins must treat the two separately rather than sharing one curve.

**Margins are bounded.** A set is at most 6-0, a dual at most 9-0. Least-squares and
margin-based reasoning imported from unbounded-score sports will misbehave here; dampen or
cap rather than porting an implementation unchanged.

**The engine has no concept of a rating as a display value.** It reads a number. Nothing here
formats one for a user.

## Vocabulary

A player plays **matches**, at a **flight** (position, line), inside a **dual**. A **court**
is the physical surface. Aggregates over flights are **flight share**. A lineup or format is
never a "card".
