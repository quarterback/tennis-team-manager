# AAR — Coach career lineage and player-to-coach conversion

## Why

College coaches were already persistent people: a `coach_id` followed a coach when
the editor or offseason carousel moved them, and honors were keyed to that id. The
seat, however, was the only durable description of where they worked. Moving a
coach rewrote the source and destination `coach_seat` rows. The coach page could
therefore show only the new job and made the person look as though they had always
worked there. This affected head coaches, associate head coaches, and assistants.

Players had the opposite strength. A player's stable `pid`, season history, transfer
stints, and archived player page preserve their trajectory after graduation. There
was no supported way to continue one of those people into college coaching without
either losing the player page or inventing an unrelated coach with the same name.

The owner wanted the two systems to meet without merging their identities:

1. every coaching job must remain visible after a move;
2. a graduate may receive a **new coach page** linked to the old player page; and
3. a converted player-coach must be a normal coach, not an alma-mater-only special
   case. They may start at any D1–D4 men's or women's program and later move or
   change roles through the same tools as every other coach.

## Model: identity, seat, season record, assignment

These are deliberately separate concepts:

| Concept | Store | Meaning |
|---|---|---|
| Coach identity | `coach` | The person, ratings, nationality, stable `coach_id`, and optional source `player_pid`. |
| Current job | `coach_seat` | The one live division/gender/program/role occupied by that person. This remains authoritative for development, recruiting, tactics, and staff pages. |
| Season record | `coach_history` | A concluded season's team W/L context. Only head-coach rows bank career wins. |
| Career path | `coach_assignment` | An append-only sequence of jobs held, written at hire or movement time rather than waiting for season end. |

`coach_history` could not solve the lineage problem by itself. An editor can move a
coach before a season concludes, assistants need a visible path even though their
team wins do not count as personal wins, and two jobs can occur in the same season.
Assignment history therefore records `(coach_id, year, division, gender, school,
role, event)` with an auto-increment sequence as its chronology.

## Movement wiring

All college movement primitives write assignment rows in the same transaction as
their seat changes:

- `ensure_seat` records a newly generated coach's initial hire;
- `move_to` records the mover's destination and, for an occupied destination, the
  displaced coach's swapped destination;
- `swap_seats` does the same for promotion/demotion and arbitrary staff swaps; and
- `swap_head_coaches` covers the offseason world carousel.

The web editor and carousel pass the current calendar year into these operations.
`assignments(coach_id)` orders by `assignment_id` and collapses consecutive duplicate
jobs, making repeated idempotent observations harmless to the displayed path.

### Existing-save backfill

The feature must work on saves whose staffs predate `coach_assignment`. Schema
initialization inserts the current non-vacant seat as an `existing` assignment for
each coach who has no path rows. This must happen **before that coach's first move**;
without the backfill, an upgraded save would record only the destination and repeat
the original bug for every pre-existing coach.

This backfill can recover only the job visible at upgrade time. Jobs overwritten by
old versions were never persisted anywhere and cannot be reconstructed honestly.
The rule is therefore: preserve the current job at migration, then preserve every
future job exactly.

## Same-season moves

The coaching-record table and assignment timeline answer different questions. The
timeline always shows both programs. The season table shows concluded
`coach_history` rows plus the current live seat.

Previously the live-row check was merely "does any row exist for this year?" If a
coach already had a row at the old school, it suppressed the new school's live row.
It now compares the complete `(year, division, gender, school, role)` key, so an old
stint cannot hide a distinct current stint. Head-coach career totals continue to
count only head rows; assistant team W/L remains context.

## Player-to-coach conversion

Conversion does **not** mutate a player into a coach and does not reuse the `pid` as
the coach id. It creates a normal coach row with a new `coach_id` and stores the
player's pid in `coach.player_pid`:

```text
archived player page (/player/<pid>)
              ⇅ player_pid link
new coach page (/coach/<coach_id>)
```

The archived player page continues to age and remains reachable from career honors,
championship archives, and historical rosters. The coach page accumulates its own
jobs, coaching records, and coaching honors. Each page links to the other.

The conversion action appears only when the pid is present in the authoritative
`world_graduates` archive, not merely when a player page falls back to persisted
history. (`world_roster` contains both active and historical players and is not
proof of graduation.) The POST repeats this check so a forged request cannot turn
an active player into a coach. The user chooses gender, conference, program, and seat
(head, associate, or assistant). The POST route validates the submitted division,
gender, and school against the actual NCAA universe rather than trusting the form.
An existing link is idempotent: `coach_for_player` returns the already-created coach
instead of producing a second coaching identity.

### They are normal coaches

There is no `former_player` movement branch. After creation the linked coach occupies
a regular `coach_seat`; `move_to`, staff-role swaps, retirement, season recording,
honors, and the career-path display all operate on the same `coach_id` as for a
generated coach. A graduate may begin anywhere—not only at their alma mater—and may
later cross divisions, switch between men's and women's programs, or become a head
coach. The `player_pid` link remains intrinsic to the coach through every move.

### Occupied-seat semantics

Creating the coach in an occupied seat is an appointment/firing, not a two-seat
swap: the new coach has no source seat to give the incumbent. The incumbent coach
entity, honors, season history, and assignment history are preserved, but they no
longer hold a college seat (a free agent). Subsequent moves between two seated
coaches retain the existing swap behavior. UI copy must not claim that conversion
leaves the incumbent in place.

## UI

- Alumni player page: **Begin coaching career** panel with cascading
  gender → conference → program selectors and a seat selector.
- Linked player page: **View coach page** link replaces the creation form.
- Linked coach page: **View playing career** link.
- Coach page: **Career path** panel showing program, role, universe, movement year,
  and a current marker.

The conversion panel explicitly says the coach may choose any program and uses the
normal movement tools afterward. This copy exists because the first implementation
silently appointed every graduate at their alma mater, which made the data model
more restrictive than the intended feature.

## Gotchas burned in during the build

1. **A stable id is not a career history.** Keeping honors on `coach_id` preserved
   the person but not their prior seat; assignments need their own append-only store.
2. **Do not infer jobs only from concluded seasons.** In-season moves and assistant
   jobs would disappear or lag until rollover.
3. **Backfill upgraded saves.** Tests that reset the registry and create fresh seats
   can pass while real saves still lose every origin job.
4. **Compare a complete live-stint key.** A year-only check hides the destination
   when two programs occur in one year.
5. **Keep player and coach ids separate.** Sharing an id or page would couple two
   record systems with different aging, honors, current-team, and archive rules.
6. **Validate destination tuples server-side.** The cascading selector is a UI aid,
   not authority for division/gender/program membership.
7. **Conversion is not alma-mater placement.** The alma mater is part of the playing
   biography, not a restriction on coaching employment.
8. **An initial appointment has no source seat.** Replacing an incumbent cannot use
   the ordinary two-seat swap without inventing a phantom job for the new coach.
9. **A persisted player is not necessarily a graduate.** Cross-universe page lookup
   can fall back to `world_roster` for someone who is still active elsewhere. Gate
   both UI and POST on `world_graduates`.
10. **Rollover owns its year.** `coach_carousel` must use the `year` passed through
    `finalize_rollover`; loading the default global world crashes standalone
    rollovers and stamps the wrong calendar year for non-default seeds.

## Invariants and regression coverage

- A moved coach's assignment list contains source then destination.
- Both people in a normal occupied-seat move retain paths through both programs.
- A linked player-coach retains `player_pid` after moving.
- A converted assistant can move to another division and become a head coach using
  the ordinary movement primitive.
- Player and coach pages remain separate and mutually linkable.
- Resetting the registry clears identities, seats, season history, and assignments.

The focused tests live in `tests/test_web_coaches.py`. Any future carousel, hiring,
promotion, or editor pathway that changes `coach_seat` must either call one of the
instrumented movement primitives or append the equivalent assignment rows in the
same transaction.

## Future work

- A first-class free-agent staff search and hire flow would make fired incumbents
  appointable without an editor workaround.
- Assignment rows have an `event` field (`hired`, `existing`, `moved`) that is not
  yet displayed; it can later distinguish hires, promotions, firings, and carousel
  moves without changing the core chronology.
- If partial-season coaching statistics become important, add explicit coaching
  stints with start/end boundaries. Do not overload `coach_assignment` with match
  totals or make assistant wins count as head-coach career wins.
