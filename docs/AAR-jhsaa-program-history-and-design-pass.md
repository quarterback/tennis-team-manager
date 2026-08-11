# AAR — the JHSAA becomes a world surface: program history, and the design pass

The JHSAA simulated a full high-school season from its first commit, and archived it.
What it did not have was a way to **live in it**. `/jhsaa` was a stack of white cards
and long text lists; a school page was a schedule table over a roster table with a
"Program History" card that listed badges. You could read what happened. You could not
follow a program across a decade, or a player across four years, the way you can follow
a college program across the college side.

This pass did two things: gave the reading layer a real **season ledger** on top of the
archive that already existed, and rebuilt the section as another layer of the same
sports world rather than an admin page bolted to the side of it.

## What shipped

| | |
|---|---|
| Reading layer | `world.jhsaa_school_history` → `{totals, seasons}`; `jhsaa_state_result` / `jhsaa_state_rounds` / `jhsaa_group_ranking` |
| Surfaces | `/jhsaa` hub · `/jhsaa/bracket` · `/jhsaa/districts` · `/jhsaa/district/<class>/<name>` · `/jhsaa/school/<name>[/<year>]` · `/jhsaa/player/<school>/<pid>` · `/jhsaa/champions` |
| Design | `static/css/jhsaa.css` (`.jh-*`), `templates/_jhsaa.html` (header, scope bar, school/player links, mobile round tabs) |

## 1. Honours are annotations. The SEASONS are the history.

The old program-history card answered "what did they win". The questions an owner
actually asks of a program are all about seasons:

> Was this historically a strong program? Are they improving? When was the last
> title? How many consecutive state appearances? What was their best season? Their
> worst? Have they moved classifications?

None of those is answerable from a list of All-State names, and all of them fall out of
a row per season. So `jhsaa_school_history` now returns **two distinct things**:

* `totals` — the career: seasons played, all-time W-L, district titles, state
  appearances / quarters / semis / finals / championships, POY and All-State counts,
  the last title, the current and longest state streak, the best and worst season, and
  every classification the program has played in.
* `seasons` — the ledger: one row per archived season, newest first, carrying the
  overall / district / postseason records, courts won and lost, district place, state
  seed, state finish, the classification ranking, and the honours won that year.

Every number in `totals` is a **fold over `seasons`** — all-time W-L is literally their
sum — so the two halves of a program page cannot disagree, and a new season moves the
totals only by being appended. 

## 2. No new table. The archive already held it.

The instinct was a `world_jhsaa_school_season` table. It was the wrong instinct, and
the reason is worth keeping: **`world_jhsaa` already archives per-school
`record`/`drecord`/`place`, the state brackets with their fields and rounds, and the
award lists; `world_jhsaa_dual` already holds every dual with its line scores.** The
postseason record, the courts won and lost, the state seed and the state finish are all
*derivable from those two*, at a cost of one indexed read of ~26 rows per season.

A second table would have been a second source of truth for numbers the archive already
determines — the class of bug this codebase keeps relearning (see the cache-invalidation
and bracket-drift AARs). The rule that came out of it:

> Before adding a persistence layer, check whether the thing you want is a **projection**
> of a layer you already have. A ledger read is cheap; a ledger that can disagree with
> its own source is not.

## 3. A JHSAA draw is not a power of two, so a "round" cannot be assumed to halve

The first cut computed a program's finish as `2 ** (rounds - eliminated_in)`. It looked
right on 7A (a 32-team field) and was wrong everywhere else. `run_state` pads a field to
the next power of two and the byes collapse **unevenly**: a 24-team field plays rounds of
**24 → 12 → 6 → 3 → 2**, and a semifinal round genuinely has three teams in it.

So a finish is now counted **down from the field** — every game eliminates exactly one
team, so `alive(n+1) = alive(n) - games(n)` — and `state_place` is *the number of teams
still alive when the program went out*: 1 champion, 2 runner-up, 3-4 semifinalist.
"Reached the semis" is `place <= 4`, a number, never a string compared against a label.
The champion is read off `bracket["champion"]`, not inferred from "won its last game",
because a bye lets a program sit out a round without being out of the tournament.

### The draw itself was never seeded — and I looked straight at the evidence

The round math above is right, but it was describing a broken tournament. `run_state`
built its slots as `list(field) + [None] * (size - len(field))` — the field in finishing
order, padded at the end — which is not a draw:

* the `None`s **paired off with each other** and vanished, so the byes a
  non-power-of-two field is supposed to hand its top seeds went to nobody, and
* because slot order was just finishing order, **the first round paired seed 1 against
  seed 2**, seed 3 against seed 4, and so on, at every field size. Every state
  tournament in the association was decided by a ladder that put its two best teams
  against each other first.

The function's own docstring claimed the opposite ("the top seeds take first-round
byes"), and the first 7A bracket screenshot in this pass has `1 Ruby Stokes` against
`2 Petra Weiss` in the round of 32, in the middle of the frame. I reviewed that
screenshot for layout and never read the tree. **Rendering something faithfully is not
the same as checking it is right** — a chart of wrong numbers looks exactly like a chart.

The fix is `engine.tournament.seeded_draw`, the helper the college championship already
uses: entrants go to standard bracket anchors, and the byes go to the top seeds. A
12-team field is now a 16 draw where seeds 1-4 sit out and 5-12 play into an eight-team
quarterfinal; a 24-team field is a 32 draw where the top eight sit out. The bracket is
FIXED after that — no reseeding between rounds (owner rule: most states don't reseed).

### How JHSAA seeding actually works, end to end

Four stages, and each one sorts on a *different* thing — which is the part that reads as
inconsistent until you see why.

**1. District place** (`play_district`). After the double round-robin, a district's teams
sort on **district win % → point differential → name**. District duals only: the
non-district card doesn't count here, because a league table should be decided by the
league. That ordering is `district_place`.

**2. Who qualifies** (`qualifiers`). Automatic bids first — `AUTO_PER_DISTRICT`, which is
the top **two** per district in 7A and the champion everywhere else — then the rest of
the association pooled and taken by **TOSS Power Index** until `FIELD` is full. (This
sorted on overall win % in the first cut; TOSS replaced it a few commits later —
`docs/BLOG-toss-in-a-third-format.md`. Win % survives only as the fallback for a caller
that runs a district in isolation, and for archives written before TOSS.)

| | Field | Auto | Districts (girls / boys) | Draw | Byes |
|---|---|---|---|---|---|
| 7A | 32 | top 2 | 9 / 8 → 18 / 16 auto | 32 | 0 |
| 6A | 24 | champion | 7 / 6 | 32 | 8 |
| 5A | 24 | champion | 6 / 6 | 32 | 8 |
| 4A | 16 | champion | 5 / 4 | 16 | 0 |
| 3A-1A | 8 | champion | 3 / 3 | 8 | 0 |

**3. Seed number** (`qualifiers`, final sort). The whole field — autos and at-larges
together — is re-sorted on the **Power Index**, and a program's index in that list *is*
its seed. Three consequences worth stating out loud because they look like bugs and
aren't:

* an automatic bid buys entry, **not** a seed. A district champion with a thin index is
  seeded below at-larges from stronger districts.
* the seed key is an **association-wide** rating while district place is
  **district-only**, so a program can win its district and still be seeded under a team
  that finished second in another one.
* a **better record can seed lower**. That is the whole point of a strength model: 22-4
  out of a weak district rates under 19-7 out of a brutal one. It is the single most
  likely thing to be reported as a bug.

The index is computed **once**, over the whole gender, on the regular season only, and
then **archived on the standings rows** — never recomputed on read. And it is archived
at **full precision**: `round(pi, 6)` looks free because nothing on screen shows more
than three decimals, but the seeding sorts the raw value while the ranking page re-sorts
the stored one and breaks ties by school name, so any two teams inside 1e-6 collapse and
the ranking starts contradicting its own seeds. Rounding is a property of a view. It
does not belong in a store whose job is to reproduce a decision.

**4. The draw** (`run_state` → `engine.tournament.seeded_draw(n_real, n, n_seeds, rng)`).
`n_real` is the field, **`n` is the bracket size — the field padded up to the next power
of two** (24 → 32), and `n_seeds` is how many entrants get a protected anchor. The
college championship passes `seed_count(...)` there and draws everyone else in at
random; the JHSAA passes `n_seeds = len(field)`, because `qualifiers` has already ranked
the *whole* field, so every entrant is placed rather than drawn.

Placement is **tiered, not strictly canonical**. Tiers are `[1] [2] [3-4] [5-8] [9-16]
[17-32]`; each tier's canonical anchors are shuffled among that tier's own members. So
the *structure* is guaranteed — 1 and 2 at opposite ends and unable to meet before the
final, 3-4 in opposite halves, 5-8 in separate quarters, 9-16 in separate eighths, and
every 1-16 seed drawn against a 17-32 seed in round one — while the *exact* opponent
inside a tier is random (deterministic from the season seed). That is why a real draw
reads `1 v 22, 15 v 27, 8 v 30, 4 v 31, 2 v 26` rather than the textbook
`1 v 32, 16 v 17, 8 v 25`. It is the same behaviour the college bracket has, and it is
how actual tennis draws are made.

Byes are `n - n_real`, handed to the **top seeds' first-round slots in seed order**, and
the bracket is **fixed** after that — no reseeding between rounds.

**The same assumption was hiding in the drawing code, and it bit twice.**
`_bracket_canvas` connects a column to the one before it *positionally*: equal widths
mean one feeder each, anything else means the standard halving (`2k`, `2k+1`). Handing
it the raw round sizes — 12 → 6 → 3 → 1 → 1 — is therefore invalid at the 3 → 1 step:
it links the first two quarterfinal winners into the final and draws nothing at all for
the third, who byed straight through. The card showed the right teams, so the tree
looked plausible while one program's whole route to the final was missing.

The fix is not a smarter canvas. It is to stop lying to it, in two steps:

1. A bye is materialised as an explicit **pass-through card** in the column it happens
   in, so the column counts describe a real tree. The empty side reads **BYE**, not TBD:
   the slot is not undecided, there is genuinely no opponent.
2. The cards are **ordered by their real feeders** — walking right to left, each card
   claims the previous column's cards whose winners are standing in it. That makes the
   positional rule true by construction whatever the draw does.

Step 2 matters more than it first looked. With the draw properly seeded, byes land on
the *top seeds' anchors* and are therefore **interleaved through the opening round**,
not conveniently at its end — so "append the byes after the games" (which happened to
be right while the field was padded at the end) would have been wrong again. Deriving
the order from the winners is the version that does not depend on how the draw is built.

Which teams byed is derived from the archive too (a team alive going into a round that
appears in none of its games), so all of this holds for any field size, including the
archives written before the seeding fix.

> When a helper assumes a shape, the bug is usually the input, not the helper. Feed it
> the real shape rather than teaching it a special case.

## 4. A district is (CLASSIFICATION, name) — never the name alone

`/jhsaa/district/<district>` shipped in the first draft and served the wrong league.
The JHSAA reuses its geographic district names at every level: **"Halbrook Basin
District" is five different leagues**, one per class, and the archive has always been
keyed `standings[group][district]` for exactly that reason. Keying a page on the name
alone quietly served the 3A-1A league under a 7A heading — 23 members, all the right
data, all the wrong league. The route is now `/jhsaa/district/<group>/<district>`.

## 5. The bracket is the shared tree, not a third bracket

CLAUDE.md's rule ("ONE bracket surface — don't fork the markup for a third bracket")
held here, but the shared macros hard-wired two college assumptions: team names linked
to `url_for('teams')`, and a card linked to `season_dual`. Rather than fork,
`_bracket.html` gained `ep`/`epq` (the endpoint a team name links to) and honours a
`mark` on a team (inline SVG, where college renders a crest); a card without an `id`
simply isn't clickable, which is the right behaviour for a league with no per-dual page.
The JHSAA draw therefore renders through the same `state._bracket_canvas` — same
coordinates, same elbows, same toolbar — as the NCAA bracket and the Preseason NIT.

Small screens get round TABS instead (`jh_round_tabs`), swapped in by CSS at 880px. That
is a second *presentation* of the same rounds, not a second bracket.

## 6. Dates are a DISPLAY calendar, and they are labelled as one

The owner asked for dates on the schedule; the simulation has no clock inside a JHSAA
season (the whole association runs in one rung at world week 0). What is real and
persisted is the **order** the duals were played in — non-district, then the district
double round-robin, then the state tournament. `state._jh_dates` lays that order on a
spring high-school calendar at three duals a week, so a ~26-dual card runs March to
mid-May and the state tournament follows it.

This is presentation only: nothing reads it back and no simulation decision depends on
one. It is called out here, in the docstring, and in CLAUDE.md, because a plausible date
is exactly the sort of thing that gets mistaken for sim state later.

## 7. Density is a bug class, and it has a shape

Several surfaces were rebuilt because the first version was *correct and unusable*:

* **A 12-team district plays 132 duals.** As a flat list it was the longest thing on the
  page and told you nothing. It is now a **head-to-head grid** — every team against every
  other, the season series in the cell, columns numbered by standings position so the
  header stays narrow however long the school names are.
* **A "line scores" row under every dual** doubled a 35-match schedule. The dual row is
  now its own toggle.

The pattern: a list whose length is a *product* (teams × teams, districts × players,
duals × lines) needs a shape, not a scroll.

## 7b. Parallel views are TABS; sibling pages get a SWITCHER

The first fix shortened the lists and still left both the hub and the district page a
long scroll, because the real problem was structural rather than per-list:

**Stacking parallel views of the same set.** A district page showed standings, then a
head-to-head grid, then results, then a member list — four views of the same twelve
schools, laid end to end, so comparing two numbers meant scrolling between them. They
are now one panel with **tabs**, and the member list is gone: it was the standings table
with the numbers taken off. 1,730px → 1,208px.

**Putting a child page's whole contents on its parent.** The hub carried full standings
for all nine districts — ~110 schools of tables that a hub is not for. It now carries a
district **index** (one row per league: champion, its records, how many it sent to
state), and the standings live one click away on the district's own page. The rail then
became the longest column on its own — Player of the Year, All-State, District Champions
and All-District as four stacked panels — so the honours are one tabbed panel, and
District Champions was deleted outright: it was the district index's champion column
rearranged. 3,709px → 1,371px, with the two columns finally the same height.

**Navigating siblings should not mean going back up.** Switching districts meant walking
to the index and back. The district page now has a **`<select>` switcher** for district
and class, which is what `season_standings.html` has done for conferences all along —
the pattern already existed in the app and high school just wasn't using it.

Three rules worth keeping:

> Parallel views of one set are tabs, not a stack.
> A parent page gets an index of its children, not their contents.
> If two panels answer the same question, one of them is decoration — delete it.

## 8. Two CSS bugs worth naming

* **`display: block` on spans inside a flex child.** `.jh-modrow .n` / `.s` are spans
  inside a `<span class="bd">`; without `display: block` they flow inline and every rail
  module read `Ruby StokesCascade Divide District`. Every side panel in the section was
  wrong at once, which is what made it obvious.
* **`table-layout: fixed` clips `<td>` but not `<th>`.** Setting it fixed the columns
  being pushed apart by long school names, and left the *headers* overrunning each other
  (`POSTSEASOMEED`). Both need `overflow: hidden`.

## 9. Continuity is the point, so every name is a link

A roster name, an All-State name, a Player of the Year, a bracket participant and an
All-District pick all link to the same place: `/jhsaa/player/<school>/<pid>`. **PID, not
name** — a pid keys on (school, gender, entry year, seat) and is therefore stable across
all four of a player's years, survives two players sharing a name, and matches the award
rows straight off.

That page rebuilds the career rather than storing it (deterministic; a roster build per
year, no duals) and reads each season's individual record off the archived duals — so a
senior shown at 27-4 and their school's season are **the one simulated season**, not two
computations that agree by luck. 

The chain the section exists for now has no gaps:
**freshman → four high-school seasons → graduating class → recruit board → college.**
