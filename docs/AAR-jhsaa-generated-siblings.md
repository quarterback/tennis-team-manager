# AAR — generated siblings (owner rule 2026-09)

## What changed

Family ties in the JHSAA were owner-authored only. The rule in CLAUDE.md said
"NO generator, NO suggestion pass, NO same-surname candidate scan", and the owner
had rejected all three. On a real save with ~1,700 programs the hand-tagging
became too tedious to keep up, and the owner asked for siblings to happen
mechanically — with one condition stated up front: geography-gated, and
randomised so that two players sharing a surname are not related just because
of the surname.

Siblings now roll at generation (`jhsaa.sibling_link`). Cousins and parents
stay authored.

## The shape

- A freshman seat rolls at `SIBLING_RATE` (0.06) to be the younger sibling of an
  older player who entered 1-3 years earlier (`SIBLING_MAX_GAP`), so they share
  at least one season.
- `SIBLING_HOME_SHARE` (0.70) of hits look at the player's own school, either
  gender. The rest go to another school in the same town — same locality first
  (`School.locality`, the settlement inside a metro), then the `city`. Never
  further.
- The younger takes the older's surname. That is the direction of causation the
  owner asked for: the roll makes the tie and the surname follows. A shared
  surname with no roll behind it is a coincidence, and a test pins that untied
  same-surname pairs exist.
- The tie is derived, never stored. `_gen_seat` writes it to
  `Prospect.jhsaa["sibling"]` off the same roll that set the name;
  `district_teams` unions it with the authored ties (both ends, only when both
  are on the roster — that is what the doubles arrangers read); the player page
  gets `generated_siblings` (older off the seat's link, younger by scanning the
  town's later cohorts); the research export carries `sibling_id` on
  `players.csv`.

## Why it is era-gated

The roll changes a NAME, and every archived season is rebuilt from seed.
`world_jhsaa_dual.lines` archives names and `_jh_line_records` keys on them, so
an ungated roll would rename players inside seasons whose box scores were
written under the old names. `sibling_era` gates on the entry cohort, the
`name_era` idiom, and is registered in `ERA_SETTINGS` so a new save clears it.

## Two costs, both measured

- The decision to roll reads nothing but an rng: `sibling_link` is local to
  (school, entry, seat, salt) and adding a program never changes whether another
  program's seat rolled. Pinned against a bare rng reproduction.
- The pick on a hit reads the town's school list, memoised on the play-up
  fingerprint (`_town_index`). Hits are ~6% of freshman seats, so a season's
  1,600 roster builds pay a few hundred index lookups, not per-seat ones.
  Trade-off accepted: a program added to a town can move which older player an
  existing hit lands on. It is the `_playup_league_cache` trade-off exactly.

Measured on 150 boys' programs at year 0: 758 freshmen, 41 links (5.4%), 11 to
another school in the town, 22 to the other gender's roster. Rosters with the
mechanic off are byte-identical in pids, order and every ability; only the
surnames of rolled seats differ.

## Things that would have gone wrong

- `_seat_name` (the transfer ledger's name-only path) had to take the same
  surname swap or the ledger and the roster would print two names for one seat.
  Both now go through `_seat_full_name`.
- Exchange students are generated through `_gen_seat` at seat 900+ and then
  renamed; without the `EXCHANGE_SEAT_BASE` guard a one-year arrival could be
  rolled as somebody's sibling and vanish the next year.
- The recruit hand-off replaced `p.jhsaa` wholesale; it now merges, so the seat
  and the tie survive to the college board.
- The older cohort's size is taken with `extra=0`. Turnout only raises the
  target the same gauss draw is scaled by, so this under-estimates and every
  chosen seat exists; it also means the roll needs no archetype lookup for a
  school it is not building.
