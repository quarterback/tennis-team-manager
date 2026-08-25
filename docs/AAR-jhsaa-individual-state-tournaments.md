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

### ‼️ Three display faults the shared card had, all found by LOOKING at it

None would have raised. All three were caught by rendering the page and reading it.

1. **The score displayed as fragments.** `brk_row` splits `m.score` on the hyphen and
   gives each side its half — right for a dual's "5-2", garbage for a tennis scoreline:
   "6-1 6-0" became "6" on one row and "1 6" on the other. A set score is written from
   the *winner's* side by convention — the string describes the match, not one player's
   share of it — so `score_full` prints it once, in full, on the winner's row.
2. **The school wasn't on the card at all.** Owner: *"the logos are there for that
   but…they don't tell me much and it's what most states do with this thing"* — and the
   CHSAA brackets they sent print it inline ("Alec Rodriguez, Regis Jesuit"). Added as
   `t.sub`, which is empty on a team bracket where the name IS the school.
3. **…and then the wrong half truncated.** `.brk-team` is a **CSS grid**
   (`20px 18px minmax(0,1fr) auto auto`), not a flex row, so the flex-shrink ratio a
   first fix reached for did nothing. The sub landed in a trailing `auto` track, `auto`
   sizes to content, and the NAME — the `1fr` track — gave up width instead: "Sydney
   Richardson" truncated while "Southern Jefferson Christian" stayed whole. A row with a
   sub now gets its own template where the name takes content width and the school is
   the flexible track.

Also: **a champion is NAMED.** `Entry.label` is surnames-only for a pair, which is what
a draw sheet prints and what keeps a card readable; a title announcement needs
`full_label` — "Dylan Holloway / Hilary Rimando", not "Holloway / Rimando".

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

## ‼️ Three review findings, and only two were real

A review raised three. The discipline that mattered was **checking each against the
shipped code and the real association rather than against the plan**, because they
did not all survive that.

### 1. REAL, and a bug in the SHARED draw — excess byes doubled up

`seeded_draw` gives byes to the top seeds' first-round opponents, then dropped any
REMAINING byes on random open slots **with no check that the pairing partner was not
also a bye**. A pairing with two empty slots is not a bye, it is a match that does not
exist: whoever is drawn opposite it advances twice without playing, the round after
the first stops being half the one before it, and `state._bracket_canvas` — which
links columns positionally on exactly that halving — then draws the tree wrong.

Invisible until byes outnumber seeds, which needs a field well under the bracket size.
**Measured, 25 draws per size:** fields of **82-92** leaked a bye past round one in
most draws; **93+** (≤35 byes against 32 seeds) never did. Against the real 2041
association that is most of the boys' classifications (82, 83, 84, 86, 87, 88, 89, 92)
and three girls' (85, 90, 92) — a live fault, not a hypothetical.

It is **always** avoidable, so the fix takes no fallback: `n` is the smallest power of
two ≥ `n_real`, so `n_real > n/2`, so the byes needed (`n − n_real`) are fewer than the
`n/2` pairings available to hold them. Verified over **3,564 draws across field sizes
3-299: zero failures.** Pinned by two tests in `test_bracketing.py`.

‼️ The owner offered to trade seeding away to fix it ("I'm fine with 16 byes vs 32 if
it helps"). It was not necessary and the offer was declined: the bug was in how extra
byes were PLACED, not how many seeds exist, so the USTA 32-seed convention survives
untouched. **Check what the defect actually is before spending a design decision on it.**

### 2. REAL in effect, though not for the reason given — the summer pool

The review argued a summer event cannot be preseason input to both genders' ladders.
The owner's calendar answers it: **the league year begins in JULY** — summer mixed →
fall boys → spring girls, one unit — so mixed is the FIRST event of the year, not the
last. June's seniors have already graduated and it is the RISING squads who play it.
The review had assumed the opposite (a last hurrah for departing seniors), which would
have needed the previous year's rosters and a gender-specific credit policy. It needs
neither, and mixed credits nothing anyway.

But it did surface a genuine fault. `run_mixed_season` was handed `run_season`'s
`season["teams"]`, whose `records` are full of a season that on this calendar **has not
been played yet** — and `_ladder` reads `records` through `ladder_score`, so the pool
below #9 was being cut from a finished ladder for the event that opens the year. It now
builds its own `district_teams`, which have no results, so `_order` is ability order —
the same basis the six flights use.

### 3. NOT REAL — the finish labels

The claim was that `run_tournament` emits `Finalist` and `R16` while `_FINISH_SHORT`
expects `Runner-up`, so the labels need translating. Both halves are wrong here:

* this module **never reads an engine finish label or `_FINISH_SHORT`**. It has its own
  `FINISH_BANDS`, keyed on the ALIVE COUNT, precisely because `_finish_short` is wrong
  for a 128 draw (see above);
* and the engine does not emit `R16` — measured, its round labels are
  `Round of 128 · Round of 64 · Round of 32 · Round of 16 · Quarterfinals · Semifinals ·
  Final`. The one rename needed is `Round of 16 → Octofinals`, which `ROUND_LABELS`
  does.

The finding described a plan that was not the implementation. **A review of a design
note is not a review of the code.**

---

## ‼️ The bug the UI work found: a player entered in TWO flights

Building the player page surfaced a correctness fault the tests could not see.
`run_preseason` played the flights in order and called `credit_draw` after each;
`credit_draw` writes `ts.records`, and `_order` sorts on `ladder_score(p,
ts.records.get(p.pid))`. **So crediting S1 moved the ladder that S2 was then selected
from.** A No. 1 who slipped to No. 2 on his own S1 result was entered at No. 2 singles
as well, while somebody else was entered nowhere.

Measured on a real 1A boys field: **23 of 751 players in two flights.** Nothing raised,
and every individual draw was internally consistent.

Two things about how it hid:

* **The existing test could not catch it.** `test_the_nine_entrants_are_all_different_
  people` selects from a FRESH `TeamSeason`, and the fault only exists once a draw has
  been credited. The new test runs the real `run_preseason` path.
* **Counting SEATS does not catch it either.** A program still fills nine
  (1+1+1+2+2+2) when one person holds two of them. It only shows in the count of
  DISTINCT pids — which is how it was found, by checking the archive rather than the
  code.

`entry_sheet` now resolves every program's ladder ONCE before the first draw. That is
also what the event means: every flight's entry is filed at the same moment, off one
order of ability, not re-derived after each draw.

## ‼️ And an engine bug it surfaced: doubles printed a match tiebreak as "1-0"

`engine/doubles.py`'s `_play_set` returned the SET score `(1, 0)` for a final-set match
tiebreak and threw the points away, so a doubles final decided on a 10-point breaker
read **"6-4, 2-6, 1-0"** while the identical singles match read **"6-4, 2-6, 10-8"**.
`_tb_points` was already being recorded three lines below; it was simply never read.
Pre-existing, and the college doubles championship had it too — `app/individuals.py`
uses the same format. A display fix only: nothing in this repo rates a match tiebreak
(the JHSAA's own `MATCH_FORMAT` plays a full third set, and the individual
championships are excluded from TOSS).

## The layout, and what I got wrong in it

The owner supplied licensed Noun Project icons (`data/jhsaa/medals`) and a tiered
layout. Three corrections were needed on my drafts, all of the same kind — **inventing
emphasis, or inventing content, that nobody asked for**:

1. **Every appearance was dressed as an accolade.** My first version was a table, and a
   table row is one visual weight by construction. The event crowns one champion and
   everybody else played in it: *"the section still matters because making Individual
   State is part of their record, but the UI doesn't falsely turn every appearance into
   an accolade."* Now three tiers — gold / podium / plain — where a plain row states the
   round and the seed and carries no honour text at all.
2. **I drew fake monogram badges** ("R16", "QF" discs) for tiers I had not given an icon.
   Owner: *"there's a 1,2,3 and others in there too so you don't have to default to fake
   bad monograms."* Every tier now carries real art; what separates them is colour and
   weight, never whether a row is allowed a picture.
3. **I added a "Most titles" tally** to the history page. Not asked for, and the wrong
   page: counting individual titles by school turns a list of PEOPLE into a school
   leaderboard, and the programme cabinet is the Title Board's job. (The owner then sent
   NCHSAA's champions-by-school PDF explicitly as a counter-example.)

Two more, on presentation:

* **The microcopy went.** Explanatory subtitles on a page whose controls are visible are
  noise.
* **A result is one sentence, and both sides get a school.** `Olivia Miles (9), Foxboro
  def. Johnnia Jackson (11), Eastmont 6-0, 6-0` — the OSAA's convention, and the IHSAA
  writes it identically. A runner-up named without their school is half a result. Grade
  is therefore ARCHIVED with the entry: it is a property of the player in that season,
  and deriving it on read would mean rebuilding a decade-old roster to recover something
  the draw already knew.

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
