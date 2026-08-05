# AAR — the NCAA bracket's regions drifted, and the page was never a bracket

**Reported:** "why can't I track the brackets well, some of the regions don't even show
up in the NCAA tournament pages" — then, after a first look: "I need to be able to see
an actual bracket, not how it is now where it's tough to scroll and see everything…
who they'd play if they won."

Two separate problems, one data and one presentation. Both are fixed; this is the
record so neither gets reintroduced.

---

## 1. The field was re-derived on every read, so the seeds and regions drifted

`ncaa_field()` and `_ncaa_seeds()` both **re-selected and re-seeded the whole national
field from live data every time anything asked for it.** Nothing stored the field the
bracket was actually drawn from.

That is only safe if the selection inputs are frozen once the tournament starts. One
of them was not: `committee_seed_score` spends 10% of its weight on "recent form", and
`team_form()` read **every final dual in the season — including the CT and the NCAA
rounds being seeded.** So each NCAA round that was played changed the committee score,
which changed the seed order, which changed the S-curve split into regions.

Measured on a full simulated D1 men's season (`seed=2026`), comparing the field at
selection (which is what the bracket was drawn from) with the field as the page
recomputed it later:

| | selection-time field | as the page re-derived it |
|---|---|---|
| positions changed | — | **67–80 of 96** |
| field membership | — | changed too (Stanford out, Michigan in) |
| region label shown (round 1) | 32/32 | **1/32** |
| teams shown with a wrong seed | 0 | **38/64 in round 1, 46/64 in the R64** |
| teams shown with NO seed | 0 | 2 (they'd dropped out of the recomputed field) |

This is exactly what the owner saw: `Round of 64 · Centennial` on a handful of duals
and nothing on the rest (the template only printed a region when both sides agreed on
one), a 5-seed in a play-in that only contains lines 9–24, and teams like `Brown` and
`Georgia Tech` with no seed and no conference at all.

The bracket itself was never corrupted — byes, pairings and advancement were all
structurally correct. **Only the labels lied**, which is why it survived so long.

### The fix, in three parts

1. **`committee_seed_score` reads only `SEED_ROUNDS`** — regular season, ITA opener
   and the conference tournaments, every one of which is finished before selection.
   Conference-tournament form still counts (it should); the NCAA bracket being seeded
   does not. `team_form()` keeps its all-rounds default for the season page's form
   column — the narrowing is a parameter, passed on the seeding path only. Because
   nothing but the NCAA rounds was removed, **the field a save selects at reveal is
   unchanged** — only its refusal to move afterwards is new.

2. **The draw is LOCKED when it is made** — a new `ncaa_draw` row (season → seeded
   school order + autobids), written once by `_ncaa_seeds` and read back by everything
   after: the bye rebuild that feeds the main draw, `ncaa_field`, the bracket page,
   and any later season's view of it. Re-derivation is no longer trusted to be
   reproducible; the answer is stored.

3. **A save drawn before the lock existed checks itself against its own bracket**
   (`_drawn_positions` / `_honour_drawn_field`). Bracket position is stored (`bpos`)
   and encodes the draw, so an in-flight tournament can say where its teams were
   seeded:
   - opening round, 96 field: `bpos = region*8 + g`, home = region line `9 + g`
     (exact); the away side is one of lines 17–24 and the deconflictor permutes
     which, so only its **region** is recoverable;
   - Round of 64: `bpos = slot*8 + k` over `MAIN_DRAW_ORDER`, home = the bye of
     region line `BYE_SEQ[k]` (exact);
   - 64 field: `bpos = slot*8 + k` on the canonical seed positions.

   It **validates first and only rebuilds on a contradiction.** That order is the
   whole trick, and the first cut got it wrong: rebuilding unconditionally *lost*
   accuracy, because a correct field knows the eight lines per region the bracket
   cannot name, and the rebuild replaced them with placeholders (32 of 64 opening-
   round teams then showed a wrong seed — a fix making its own smaller version of
   the bug). Validate, and a field that already agrees is returned untouched.

   Re-measured on the same played season — drawn entirely under the old code, no
   locked draw anywhere in it:

   | | before | after |
   |---|---|---|
   | duals showing their region | 1/32, 7/32, 7/16, 1/8, 1/4 by round | **100% of every regional round** |
   | teams with a wrong seed | 38/64, 46/64, 27/32, … | **0** |
   | teams with no seed at all | 2 | **0** |

> ⚠️ Do not add an input to `committee_seed_score` that reads the NCAA rounds, and do
> not "simplify" `_ncaa_seeds` back into a plain re-selection. The seed order and the
> S-curve region split are the same computation — anything that moves the score moves
> teams between regions, under a bracket that has already been played.

Verified on the 64-team shape too (a full D2 women's season): the draw locks, all four
region trees build with every link live, and no dual is missing a region or a seed.

## 2. The page was round columns, not a bracket

The old page rendered each round as an independent column of stacked result cards. A
bracket's whole job is to show **which two matchups feed the next one**, and stacked
columns can't: to find out who a winner plays next you had to search the next column
by name.

The page is now a real elimination tree, built server-side (`_bracket_canvas`) so the
cards and the connector lines share one coordinate system and cannot drift apart:

- the widest full round is the leaf row, evenly spaced; **every later matchup is
  centred on the average of the two feeders it receives**;
- a play-in column (same width as the round it feeds — one source per destination)
  is laid out **level with its destination slot**, and labelled *Opening Round*, not
  as a peer of the main draw;
- connectors are **SVG elbows** (source right edge → mid-gutter → target y → target
  left edge) drawn behind the cards, green once the feeder's winner is standing in
  the destination card;
- the field is split into **four region trees plus a Final Four**, with region tabs,
  full-bracket / previous / next, zoom + fit, seed and score toggles, team
  highlighting (hover a team to light its whole route), and print;
- a card is a compact two rows — seed, crest, name, a subdued AQ badge, score, winner
  in bold with a green score. Conference moved to the tooltip; nothing is repeated.
- **scheduled duals are on the board too** (`sm.ncaa_duals`, not `all_results`, which
  is finals-only): the round currently being played renders as a neutral dashed card
  with both participants and no score. That is the literal answer to "who would they
  play if they won".

The committee sheet (region seed lists + how the field was drawn) moved into a
collapsible drawer under the bracket instead of taking the left column.

Kept as-is: a **non-regional field** (anything that isn't 64 or 96, so no S-curve
regions) still renders the old flat round columns — there is no tree to draw when
there are no regions.

### Not built
Clicking a card opens the existing **box-score page** (`/season/dual/<id>`) rather than
an in-page drawer, and there is no "run dual" action from the bracket — the tournament
advances through the one world clock (`POST /world/advance`), and a second surface that
plays a dual would be exactly the second advance button `test_universe_sync` exists to
prevent.

## Tests
`tests/test_ncaa_bracket.py` pins both halves: the seed score must not move when
postseason duals land, `team_form` keeps its all-rounds default, a shuffled field is
pinned back onto the bracket it was drawn from, and every canvas matchup is centred
between its two feeders with a live link per feeder.
