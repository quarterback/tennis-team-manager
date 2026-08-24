# AAR — the JHSAA individual state tournaments

**Owner rule 2026-08.** Jefferson now crowns individual state champions: six flighted
draws per classification per gender — **No. 1-3 singles and No. 1-3 doubles** — plus a
separate **mixed doubles** event in the summer. Played **preseason**, credited to the
season in full.

Design: `docs/DESIGN-jhsaa-individual-tournament.md`. Code: `app/jhsaa_individuals.py`,
`world.run_jhsaa`, `state.jhsaa_individual_view`, `/jhsaa/individuals`.

---

## What it is

| | |
|---|---|
| **Flights** | S1 · S2 · S3 · D1 · D2 · D3, each its own draw and its own champion |
| **Classes** | every one, **1A included** — "even in 1A, it's still a 3/3 event" |
| **Field** | OPEN. Every program enters its holder of each flight; no district quota |
| **Draw** | 82-107 entries into a flat **128**, byes to the top seeds (the NJSIAA model) |
| **Rounds** | R128 · R64 · R32 · Octofinals · QF · SF · Final |
| **Seeds** | a quarter of the draw (32), placed in TIERS — the engine's existing rule |
| **Scoring** | the college individual championships' own format, imported |
| **Credit** | FULL, to `records` and `matches`, for the six flights |
| **Mixed** | one flight, one bracket, one entry per school from below #9, SUMMER, credits **nothing** |
| **Where** | Championship sub-rail → **Individual State**, flights switched inside it |

---

## The things worth writing down

### ‼️ The port was mostly a matter of NOT writing things

The college side already had every piece: `engine.run_tournament` sizes a bracket to
the next power of two and byes the top seeds; `engine.tournament.seed_count` is already
the tennis convention (a quarter of the draw); `seeded_draw` already places seeds in
tiers ([1], [2], [3-4], [5-8], [9-16]) rather than as a flat ranking. `app/individuals.py`
already had the selection → draw → flatten shape.

Two moments in the build were an agent about to write a thing that existed:

* **Seeds.** The owner sent an NJSIAA seeding release — "TOP SEEDS 1-, 2-, SEEDS 3-4
  (Alphabetical), SEEDS 5-8 (Alphabetical), SEEDS 9-16 (Alphabetical)". That is exactly
  what `seeded_draw` already does, and the reason it does it: the tiers are *how seeds
  are placed*, so a "No. 6 seed" is not ranked under No. 5, it is a member of the 5-8
  tier. Nothing needed changing; the page just had to *publish* them that way instead of
  printing 1..32 flat, which would claim a precision the draw does not have.
* **Match format.** A draft added a `best_of_3_ad` preset to `engine/format.py` on the
  theory that a championship should be played with ads and that this would be a
  documented exception to "all high-school tennis is no-ad". The owner asked the obvious
  question — *does the college sim run 2 out of 3 with a 10-point tiebreaker? if so we
  can just use that* — and it does: `individuals.INDIV_FMT`. The preset was deleted and
  the constant is now imported, so the two events cannot drift. **There was no departure
  to justify, only a constant not looked up.**

### ‼️ Entries come off the ABILITY LADDER, not the league lineup

The obvious implementation — "the program's No. 2 singles player enters No. 2 singles" —
is wrong here, and quietly so. The league season plays 3S/4D doubles-forward: S1 = rank
#1, the doubles pool = #2-#9, and **S2/S3 = ranks #10-#11**. So a program's "No. 2
singles" in a league dual is its *tenth-best* player. Right for a league dual, absurd as
a championship entry.

Entries are therefore `S1=#1 S2=#2 S3=#3 D1=#4+#5 D2=#6+#7 D3=#8+#9` off `_order` — nine
players, the same nine in every classification.

### ‼️ The event reads NO dual format, and that had to be said out loud

A draft docstring described the nine as "the same nine the postseason dresses". That is
false for 1A (whose road now dresses eight under the 2S/3D pilot) and — worse — it
re-couples an individual tournament to a dual shape it has nothing to do with. The
owner's correction was flat: *"so the 1/4, 2/3, 3/4 discussion is irrelevant"*, *"even in
1A, it's still a 3/3 event"*. No branch in the module reads a group's dual shape.

### ‼️ An open field is CHEAPER than district qualifying

The instinct is that "everyone enters" is the expensive option. It is not: a single-
elimination draw plays `entries − 1` matches whatever its shape, so qualifying rounds
*add* matches rather than saving them. Measured: an open field is 10,569 matches against
12,204 for a district-quota design. The owner's reason for the open field was
correctness, not cost — *"talent isn't evenly distributed geographically… a strong
league's third-best beats a weak league's champion"* — and it happens to be free.

### ‼️ Full credit cost ZERO new code, because three earlier decisions lined up

The owner asked for the easy option: *"treat them like the regular season + playoffs,
easiest idea no fuss."* It turned out to need no weighting table, no flag and no special
case, because:

* the six flights are named **S1-S3/D1-D3 — the same slots a dual uses**, so
  `jhsaa.FLIGHT_WEIGHTS` already prices S1 above S3 with no new entry;
* the phase is deliberately **outside `jhsaa.POSTSEASON`**, so
  `jhsaa_awards._phase_weight` gives it 1.0 — an ordinary match, which is what "treat
  them like the regular season" means;
* a pair is credited to **both** members with `partner` set, which is exactly what
  `jhsaa_awards._pairs` keys a partnership on.

It is still its **own phase** (`"individual"`), because a phase is the archive's identity
for an event — that is what tags it on a card and keeps it out of `rating_duals`.

### ‼️ …and the own-phase decision turned out to be load-bearing in a way nobody planned

`jhsaa_awards.FLIGHT_S2S3_REGULAR` deflates S2 and S3 to roughly **D4's weight** — but
only when `phase == "regular"`, because the league's 3S/4D format seats ranks #10-#11
there. This event's S2 and S3 are the program's genuine #2 and #3.

So had the event been archived as `phase="regular"` — the obvious way to get "ordinary
weight, no fuss" — **every individual No. 2 singles champion in Jefferson would have been
scored as though they were a tenth-best player.** Nothing would have errored and the
résumés would have looked entirely normal. It is only correct because the phase is its
own, which was decided for an unrelated reason (an event's archive identity).

Pinned by `test_individual_s2_s3_escape_the_LEAGUE_s2_s3_deflation`. **The generic lesson:
"reuse an existing phase to inherit its behaviour" inherits ALL of it, including the
corrections that were written for that phase's particular lineup shape.**

An earlier draft asserted a records-only split without presenting the alternatives; the
owner had to ask for the options. **When a decision has cheap variants, show them before
picking one.**

### ‼️ Preseason placement is what makes ability-selection honest

The association's own rule is that berths are earned on court. Selecting entries on
ability would violate it at any other point in the year. Preseason there are no results
yet, so ability is the only input that exists — and the event becomes an **input to** the
season rather than a summary of it: `credit_draw` writes into the same `records` that
`ladder_score` reads, so a deep run moves a player up the ladder before the first league
dual.

### ‼️ `state._finish_short` is WRONG for a 128 draw, and says so itself

Its own docstring explains why it needs no field-size parameter: *"every field converges
on the same 24-team main draw at the Octofinals, so a team still alive above 24 went out
in the QUALIFIERS."* True for the team event. False here — a 128 individual draw has no
qualifying and no 24-team convergence, so it would render **R128, R64 and R32 all as
QUAL**: a round nobody played, three distinct rounds collapsed into one label.

So the individual event has its own `FINISH_BANDS`, and the team path is untouched. **A
function that documents itself as needing no parameter is telling you what it assumes;
adding the parameter is the wrong repair.**

### ‼️ THE ARCHIVE: two size mistakes, one after the other

1. **Matches stored full copies of their entrants.** Each match carried the whole entry
   dict — school, label, seed, both players' pid and name — on *both* sides, so a 128
   draw repeated each entrant up to eight times over. A gender's slate came to **3.5 MB**.
   Matches now store **indices into `entries`**, which is what the engine's own
   `TourneyMatch` does: **1.7 MB**, and the seed lives on the entry because it is a
   property of the entrant, not of a match it appears in.
2. **1.7 MB is still far too much for the summary row.** `world_jhsaa` is a JSON blob
   read *in full* by every JHSAA page — carried there, rendering the hub's champion list
   would deserialise every bracket in the association. The duals table exists for exactly
   this reason ("~10k duals a year per gender would make every summary read heavy"), and
   the same answer applies: **`world_jhsaa_individual`, one row per draw**, so a page
   loads the flight it is showing and nothing else.

   ‼️ And **not** a row in `world_jhsaa_dual`. That table's row is a dual between two
   *schools*, with pf/pa and a `lines` box score, and six readers fold it into records,
   court totals and the research export. An individual match is one court between two
   *players*; dropped in there it would land on programs' records exactly as JV duals did
   before `level` — the same fault, one table over.

### ‼️ Mixed doubles cannot live in `run_season`, for a structural reason

`run_season` takes ONE gender. A mixed pair is one player from each, so the event cannot
be assembled until both genders' seasons exist. It runs at the world rung after both —
the same place `renumber_divisions` and `reletter_conferences` run, and for the same
reason. That also happens to be where it belongs on the calendar: the owner put it in the
summer, *"when there are no matches"*.

It is archived under gender **`'mixed'`**: it belongs to neither field, so storing it on
one gender's rows would make "which one?" a question and on both would duplicate it.

Its pool is **below #9** by design — a consolation event for the players the six-flight
slate has no seat for. `ROSTER_FLOOR` is 16 and the main draw consumes nine, so every
roster carries at least seven below the line; measured median 8, never fewer than 7. It
credits **nothing to anybody** (owner: *"mixed doubles gets no credit for anything for
awards"*), which is also why it can run outside any season at all.

### ‼️ The shared bracket stretched by two attributes rather than forking

`_bracket.html` assumes an entrant IS a school and links it as `ep(school=…)`. An
individual draw breaks both: the card must show a *person* and link to
`/jhsaa/player/<school>/<pid>`, whose pid varies card by card and so cannot ride in
`epq`, which is constant for the whole canvas. Two optional attributes — `t.name` and
`t.pid` — cover it; both existing callers pass neither, so the college tree is untouched.

The pid is passed as **data** and the URL built in the template, because `state.py` is a
view-model layer with no request context; calling `url_for` there would couple it to
Flask for the sake of one link. (A draft did exactly that and it had to come back out.)

### ‼️ The mobile round-tabs fallback was NOT shipped, deliberately

The team draw hides its canvas below the mobile breakpoint and hands over to
`jh_round_tabs`, whose cards (`jh_mgame`) render a *dual* — two school names, a points
score, a district. An individual card is a person against a person, so those tabs would
render empty rows and **raise nothing**. Until an individual card shape exists the canvas
stays visible at every width and scrolls inside `.brk-scroll`, which it already does.
This is noted in the template so the gap is a decision rather than an oversight.

### ‼️ `hash()` is not a seed for anything archived

`_draw_seed` uses `blake2s`. Python salts `hash()` of a str per *process*, so a seed built
that way reproduces a draw only inside the interpreter that wrote it — and these draws are
archived, which means "the same season" has to mean the same thing across restarts.

`run_season`'s own `hash(group) % 9973` is an older wart with exactly this shape. It was
**not** copied here, and it should not be copied anywhere else. (Fixing it in place would
change every archived season, so it is left alone and flagged.)

---

## Measurements

| | |
|---|---|
| Draws per gender | 54 (9 classes × 6 flights) |
| Matches per gender | girls 5,130 · boys 4,662 |
| Cost per gender | **18s girls / 17s boys** — ~35s on a rung documented at ~7 min (**~8%**) |
| Archive per gender | **1.7 MB** (3.5 MB before indexing) |
| Entries per flight | 82-107 into a 128 draw; 32 seeds |
| Mixed eligibility | every roster carries ≥7 players below #9 (floor 16 − 9); median 8 |

‼️ The cost figure had been **estimated** at "+15%, ~8-9 min" in an earlier note. It is
now measured, and the estimate was pessimistic. A cost that decides something has to be
measured, not guessed — this section exists because that lesson has been learned here
twice already (the JV box-score MB figure was quoted at 15.3 before the uncapped format
table changed its shape).

---

## Pre-existing, and not caused by this work

`tests/test_jhsaa_toc.py::test_a_toc_title_is_listed_in_the_honours_exactly_once` fails
**on a clean worktree at the parent commit** as well as with this change. It was
baselined rather than assumed, because crediting individual results preseason genuinely
moves every ladder in the association and so genuinely changes the TOC field — which is
exactly the shape of change that would make an unrelated failure look like yours.
