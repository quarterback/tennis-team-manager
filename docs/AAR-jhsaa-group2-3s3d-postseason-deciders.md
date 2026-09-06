# AAR — Group 2's 3S/3D postseason and the deciders; Parastate resized (2026-09)

Two JHSAA decisions landed in one pass. Both are rule changes on top of existing
mechanisms; neither adds a new bracket, phase or table beyond one archive column.

## 1. Parastate for 8A/9A at 48; 7A back to 40 but keeping Parastate

**Rule.** 8A and 9A adopt 7A's structure: a 32-team road (unchanged ladder) plus
16 committee at-larges into a 48-team State field with a 16-dual Parastate. 7A
goes to 40 = 32 road + 8 at-larges, Parastate 25v40 … 32v33, seeds 1-24 bye to
the Round of 32. Group 1 stays at 48 (not mentioned by the owner, untouched).

**Why 8 for 7A.** The owner's own history had 7A missing ~3-4 TOSS top-32 teams a
gender-season; eight bids rescues the obvious omissions plus a few debatable
résumés without a committee "searching for reasons to fill the back half". The
mechanism is what is valuable; sixteen bids was what was oversized.

**Implementation.**
- `jhsaa.AT_LARGE_BIDS = {"7A": 8, "8A": 16, "9A": 16, "Group 1": 16}`;
  `ATLARGE_GROUPS` is derived from it; `at_large_bids(group)` for readers.
- `STATE_FIELD["8A"]` / `["9A"]` 40 → 32: the ROAD is 32 in every Parastate
  class and the at-larges sit on top. 9A's every-season `sc_head` degrade at 40
  (64 sponsors under the 76 floor) goes away — the 32 floor is 44.
- `run_state_48` → `run_state_parastate(seeds, byes=road − bids, seed)`. The
  Parastate is exactly the `2 × bids` lowest seeds paired high-low; winners keep
  their seed; `run_state(survivors, champions=byes)` plays the ordinary 32.
  `run_state_48` stays as the 16-bye alias the original spec named.
- `jhsaa_committee.select(..., seats=)` — every step scales off the seat count;
  a district champion who missed the road consumes a seat. `seats` is archived on
  the selection so an old 7A season keeps reading as sixteen.
- `CHALLENGE_SLOTS` is now empty: the 4-seat valve is a property of the 40 ROAD
  and moved with it every time; no class is on a 40 road any more.
- Rendering reads the ARCHIVE, never today's table: the bracket page's Parastate
  bye count is `field − 2 × Parastate duals`; the committee page's seat count is
  the archived `seats`.

## 2. Group 2 plays 3S/3D on its road to State, decided on three tiebreakers

**Rule.** Group 2 alone plays 3 singles / 3 doubles from Sectionals through
State (TOC excepted, like the 1A and 8A/9A pilots). Six flights is EVEN, so a
postseason dual can finish 3-3; it is then decided by THREE CONCURRENT 10-point
tiebreakers — No. 1 singles, No. 1 doubles, No. 2 doubles, the same players who
played those flights — and the side that wins two of the three advances. A
regular-season tie (unreachable today; every varsity league shape is odd) would
use the JV ladder the association already has: points, sets, games, then a draw.
The owner: "we already use the ties format in the JV world so there's precedent."

**Implementation.**
- `FORMATS["state_3s3d"]`, `THREE_THREE_GROUPS = ("Group 2",)`, a branch in
  `dual_format` scoped exactly like 1A's. `_arrange_postseason` already
  generalises (`_arrange_wide` at three singles pools the top FIVE for S1-S3 +
  D1; D2/D3 pair #6-#9 under the rank-sum boundary). `FLIGHT_WEIGHTS` already
  prices S1-S3/D1-D3. Nine dress, same as 1S/4D.
- `_deciding_tiebreaks(home, away, la, lb, phase, shape, seed)`: uses the
  engine's own fast tiebreak dice (`fast._tb_prob` for S1, the doubles fast
  model's tiebreak logit for the pairs, both under `HS_PROFILE`) and
  `_mtb_score` for a real `10-7`. Its own rng stream off the dual seed, so no
  later match in the association moves.
- `play_dual`: a level dual in a POSTSEASON phase runs the deciders and
  overrides `res.winner` (the engine's `0 if a > b else 1` reports an AWAY win
  on a draw — the `jv_outcome` trap); a level REGULAR-SEASON dual runs
  `jv_outcome` and, if still level, is recorded as a tie (`TeamSeason.ties`,
  W-L-T record only when a T exists, a T is half a win in `win_pct`).
- **The deciders are NOT lines.** Their box score rides a `tiebreak` key on the
  schedule row and a new `tiebreak` column on `world_jhsaa_dual` (ALTER-added,
  default `'[]'`). Every reader of `lines` counts a match — player records,
  flight boxes, court totals, the research export's shape inference — and a
  10-point decider is not one. Nothing is credited to `records`/`matches`.
- Surfaces: the school schedule's line expand shows `TB S1/D1/D2` rows under the
  flights and a `TB` chip beside the 3–3; the Match Center shows a Tiebreaker
  block; its winner is read off the row's `won` when points are level. The
  research export gains `duals.decided_on_tiebreak` and the manifest says so.

## 3. Showcases play the HOST class's state format; the early window is 5S/2D for all

**Rule (owner, 2026-09).** "Showcases move to match the format of the classification
hosting" — so a 9A-hosted showcase is 4S/5D, a 1A-hosted one 2S/3D, a Group
2-hosted one 3S/3D, and a 1S/4D-class host 1S/4D. A small school drawn into a
big host's pod plays the big format: "everyone generates enough players to play
every format so there's no issue." And "I don't want 5/2 tennis to go away
completely", so the early non-district window went BACK to 5S/2D for every class —
the wide classes' 4S/5D early window (owner rule 2070) is retired; the showcases
are their rehearsal now.

**Implementation.**
- `showcase_schedule` stamps a `host` on every event — the first team of the
  dealt group, which is shuffled, so no program is systematically the host.
  Hosting decides the FORMAT only; a showcase stays a neutral site for home court.
- `play_dual(group=)` overrides `shape_group`'s resolution; `play_showcases`
  passes the host's group. The row archives `shape_group` (the group the dual was
  played at) so `rating_duals` prices the flights on the right table — the two
  sides cannot reproduce a host's format.
- `dual_format`: `wide and (road or showcase)` → 4S/5D; `PILOT_GROUPS` /
  `THREE_THREE_GROUPS` and `(road or showcase)` → their shapes; the early window
  falls through to `FORMATS["early"]` for everyone.
- `_lineup`'s showcase branch arranges onto the dual's shape (`_arrange_postseason`
  at the host's format), not `_arrange_state` unconditionally.

**Consequence.** A Group 2-hosted showcase can finish 3-3. It is regular season,
so it takes the JV ladder — sets, games, then a TIE — and `TeamSeason.ties`, the
W-L-T record, the `T` cell and the half-win arms in the rating systems are live
code, not the dead path §2 first described. The deciders remain postseason-only.

## What I got wrong on the way

- Wrote the tie path as "unreachable" and said so in three places. The owner
  asked how a varsity draw could ever happen; the answer was that the showcases
  should have been shaped like the state formats all along, which makes it
  reachable. Rule stated as unreachable → check whether a sibling mechanism was
  meant to reach it.
- Moved the wide classes' showcases only after being asked "is this true of
  7A-9A too?". The rule was "showcases rehearse the state format"; I applied it
  to the two classes named instead of to the rule.

## Assumptions made (not confirmed by the owner)

- Group 1 stays at 48/16.
- 8A/9A's Special Challengers drop to the standard two seats with the 40 road.
- The deciders are 10-point match tiebreaks by the flight's own players, and
  count for nothing on any player record.
- A showcase's host is the first team of the dealt group (a random draw); the
  owner said "hosting" without naming a rule for who hosts.

## Tests

`tests/test_jhsaa_committee.py` (40-shape pairings and byes, bid table vs. seat
count, automatic bid consuming a seat at 8), `tests/test_jhsaa_special_challengers.py`
(empty valve table; the 4-seat path via monkeypatch), `tests/test_jhsaa_lineup.py`
(3S/3D scoping, the arranged lineup, a real level Group 2 dual decided on the
three tiebreakers with no credit leaking, the best-two-of-three fold). Only the
touched files were smoke-run, per the owner; the full suite was not.
