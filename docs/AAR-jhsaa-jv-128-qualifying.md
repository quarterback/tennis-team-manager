# AAR — the JV individual state tournaments go to a full 128 draw

**Owner spec, 2026-09.** The association judged the JV Singles / JV Doubles state
tournaments a success and expanded them from a ~95-entry draw padded to 128 with
byes to a **true 128-entry field**, filled the way a Grand Slam fills its main draw:
direct entries, one autobid, and a qualifying tournament for the rest.

This is the record of what was built, what it replaced, what broke on the way, and
what was measured. Module: `app/jhsaa_jv_individuals.py`; engine change:
`engine/tournament.py`; readers in `app/world.py` and `app/web/state.py`.

---

## 1. The shape

Four events — singles and doubles × boys and girls — each built independently
from three sources:

| source | who | how many (95 districts) |
|---|---|---|
| District champions | winner of each district JV tournament | 95 |
| Defending-champion autobid | the program that won last year's JV state title | 1 |
| Regional Qualifying winners | every district **runner-up**, played down | 32 |
| | | **128** |

`STATE_FIELD` is 128 and the arithmetic closes **by construction**:
`qualifying_spots = 128 − champions − autobid`, and the qualifying draw is sized to
produce exactly that many winners. The count is taken **per event and per
season** — a district that fields nobody crowns no champion, one that crowns a
champion unopposed sends no runner-up — so both inputs move year to year and the
qualifying shape is derived from what was actually played rather than assumed.

Measured on the live association (95 districts, girls): both brackets landed on
**exactly 128** — 95 champions, 1 autobid, 32 qualifiers.

## 2. Regional Qualifying — the slam shape, deliberately

The obvious play-down halves the field each round. The owner specified something
different and more specific: the **final qualifying round is exactly `2 × S`
entries**, so every match in it produces one State qualifier ("win your last one
and you're in"), and everything before it is an opening round with a lot of byes.

    opening-round matches = Q − 2S      (2·(Q − 2S) play, the rest bye)
    final-round matches   = S

`qualifying_rounds(q, s)` reproduces the owner's three worked examples verbatim:

| Q | S | rounds | opening round |
|---|---|---|---|
| 95 | 32 | [31, 32] | 62 play, 33 bye → 64 |
| 94 | 33 | [28, 33] | 56 play, 38 bye → 66 |
| 96 | 31 | [34, 31] | 68 play, 28 bye → 62 |

Below `2S` runners-up the opening round is unnecessary and the final round carries
the byes instead; above `4S` a round cannot pair everyone it needs to and another is
added. The loop handles both rather than a special case.

**Byes go to the top of the ranking** and the bottom of the field plays, mirrored
strongest-against-weakest so every match in a round carries the same combined seed
(`_round_pairs` — the same pairing rule every play-down in the module uses).

Each qualifying draw is **archived in its own right** under its own flight key
(`QJVS` / `QJVD`). It is neither a state title nor a district title, and
`world_jhsaa_individual` is keyed on `flight`, so the flight is the distinction —
a reader that does not know the key drops it by construction. It has no champion,
so it never reaches a champions roll.

## 3. The autobid — a district of one

The first cut modelled the autobid as a separate kind of berth with its own label.
The owner corrected it: the entrant *"won a district event by themselves rather
than being granted auto access — the 'TOC' district of one."*

That is a better design than a label, and it removed code. The bid is now a
one-entry district named **`TOC`** that its only entrant wins unopposed — a path
`run_district` already had, because a real district where only one school fields
anybody does exactly this (`run_tournament` returns a lone entrant as champion with
no rounds). The entry therefore enters State as an **ordinary district champion**:
`champions_of` counts its seat, `qualifying_spots` needs no `autobids` argument, no
reader has to know the bid exists, and it archives beside the other 95 districts.

Two rules that took a correction each:

- **It belongs to the program, not the player.** Singles is seniors-only, so a bid
  held by the person who won it always lapses. `defending_program` reads the
  program off the **archive** — the newest archived state draw for that gender and
  bracket, which at the moment the current season is played is last season's. No
  season-year arithmetic against the archive's world-year key.
- **It is the school's best *remaining* entry.** The first cut asked for the best
  entry outright and dropped the bid when that player already held the district
  seat — so it went unused in exactly the year the program earned it. `school_entry`
  gained `exclude=`; the bid skips whoever is already in and takes the next one
  down, which is what makes the owner's "two players from the same school" true.

Measured: **37%** of programs have a second eligible senior and can use a singles
bid; **24%** have a fifth eligible player and can use a doubles one. When a holder
cannot, the seat falls to qualifying and the field is still 128.

## 4. Same-school separation — a swap within the seeding contract

A school can now hold more than one seat, so two of its entries meeting in round
one would waste the bid the association just awarded. Rule: two entries → opposite
halves; three or four → separate quarters; spread as far as the bracket allows.

`engine.tournament.separate_draw` does it **after** `seeded_draw`, by swapping an
entrant with one of the **same placement tier** in the target block. That is the
whole reason it can run after placement rather than inside it: a tier's anchors are
already assigned at random within the tier, so exchanging two of its members is a
draw the same code could have produced. Seeds 1 and 2 stay at the ends; every
unseeded entrant is one tier. When no legal partner exists it skips — the draw
degrades to the un-separated placement for that entrant rather than failing.

Opt-in through `run_tournament(separate=)`. Every varsity flight, both college
championships and the junior circuit pass nothing and draw **byte-identical**
brackets.

Measured over 40 draws in a stress case (60 schools with 2-3 entries each, far
denser than reality): **98%** of pairs in opposite halves, **100%** of triples in
distinct quarters, seeds 1-2 at the ends every time.

## 5. What broke, and why it was invisible

**`Entry.key` was the school name.** Its comment said *"one entry per school per
flight, unique within a draw by construction."* That construction held for every
varsity flight and held for the JV event until the autobid — then two entries from
one school collapsed to one index in `draw_to_dict`'s `ix` map, and the archived
rounds pointed at the wrong entrant. Nothing raised. The key is now
`(school, pids)`; the `finishes` map is keyed by entry index (nothing reads it —
every consumer goes through `finish_for_index`, which walks rounds by index
precisely because a relabelled school name cannot be looked up).

The lesson is the one CLAUDE.md keeps: a comment that says "by construction" is
naming an assumption. When the construction changes, grep for the comment.

**A qualifying draw is not a tree.** `_bracket_canvas` links columns positionally on
the main draw's halving, and 31 matches followed by 32 is not a halving — fed to the
canvas it would draw links between matches that have nothing to do with each other.
The qualifying page renders its rounds as panels, which is how a slam prints
qualifying anyway.

**The test-ordering trap.** `_expo_world_id` caches the world id per database path.
A scratch script that built rosters before creating the world row cached `None` and
the autobid read nothing; it looked like the lookup was broken. In the real path
(`world.run_jhsaa`) the world exists first. Worth knowing before the next person
debugs "the autobid never fires" in a script.

## 6. What was removed

The **pigtail pre-round** — surplus entrants past a 96 cap playing into top seeds'
lines, with layered rounds past 192. Qualifying fills the field exactly, so nothing
is ever surplus and the mechanism has no input. Its tests went with it; the
qualifying arithmetic pins the owner's worked examples instead.

## 7. Open question, answered separately

Whether a JV champion can enter the varsity No. 3 singles / No. 3 doubles draw as a
wild card in the same year. Short version: the draws have the space; the calendar
does not — see the session record.
