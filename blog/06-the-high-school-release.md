# The High School Release
### Everything merged since the 2.4 notes

The 2.4 notes went up on July 31. This covers everything since: a whole new tier of the
sport, a rebuilt postseason, an awards system, a match-model recalibration, four
scouting surfaces, a design port, and a rewrite of how the world decides where its
people come from.

The headline is that the game now simulates high school tennis. Everything else is
grouped after it.

---

## 1. Jefferson

Before there could be a high school association there had to be a state for it to be in.
**Jefferson** is a fictional West Coast state of about 17.6 million people across 20
counties, standing on real southern-Oregon, northern-California, northern-Nevada and
western-Idaho ground. Its institutions are imported from a companion project; its
*people* are generated here, and no player is ever imported.

It is deliberately an ordinary state in the data. It is the 55th entry in the state list
— which was never 50, since it already carried DC, Puerto Rico, the USVI and Guam as
first-class entries — it sits in region "W", and it gets no special pull table. Out-of-region
signees are normal and expected.

**39 colleges across D1–D4, but only four in D1.** A 17.6M state with a dozen D1 programs
broke immersion. The flagship (University of Jefferson) is in the Pac-16, Jefferson State
is in the WAC, Southern Jefferson in the Big West, Jefferson A&M in Conference USA. The
Jefferson Valley Conference is D2. Colorado State moved to the Mountain West to keep the
Pac-16 at sixteen — a correction rather than a demotion, since that is where CSU plays in
real life.

Several real programs standing on Jefferson ground were absorbed and renamed, so each
keeps its own identity: Oregon Tech became Cascade Polytechnic, Southern Oregon became
Siskiyou, Cal Poly Humboldt became Humboldt Polytechnic, Chico State became Bidwell
State, the College of Idaho became the College of Jefferson. Only three Golden State
campuses relocated, taking D3 California from 20 programs to 17 rather than to 11.

Two things about Jefferson that read as bugs and are not:

**A flagship is never subsumed.** Galena University was first written as a rename of
Nevada — Galena County *is* Washoe County, so absorbing UNR looked tidy. It was wrong and
was reverted. Jefferson may take the ground and the regional publics; a real flagship
keeps existing. Galena is net-new and sits beside Nevada.

**Jefferson develops talent and most of it leaves.** Jefferson produces at a top-tier
rate — measured at 188 recruits in a class against California's 186, Florida's 166 and
Texas's 113, close enough at the top that one class of noise reorders the first two — and
most of them go elsewhere to play, exactly as they do for California, Texas and Florida.
"A good tennis state" has never meant "a state that keeps its own kids," and a big
in-state D1 footprint is not how the state's quality is expressed.

One measured trap worth recording: Jefferson's city pool was **capped at 46 of its 272
cities**, and the cap was load-bearing — against the original hand-curated western pool
of ~150 cities, exporting all 272 made Jefferson 64% of it, so every California, Oregon
and Washington roster filled with Jefferson kids and nothing errored anywhere. When the
hometown pools were later rebuilt from real Census and GeoNames data (below), the west
grew to ~729 real cities and the cap's reason evaporated: Jefferson now exports **all
272 uncapped**, about 27% of the western pool against a 23% population share, with a
tripwire in the import script that warns if the share ever climbs back toward the old
disaster.

---

## 2. The JHSAA

Jefferson's high schools play a full season inside this engine, browsable at `/jhsaa`,
and its graduating seniors are Jefferson's entries on the college recruit board. About
**335 girls' and 292 boys' programs**. This reversed an earlier decision to keep the high
school season invisible.

### Format

Two axes, both explicit. **Shape**: the regular season plays 5 singles + 2 doubles; the
state tournament plays 1 singles + 4 doubles. Both are odd, so a dual can never tie and
there is no tie-breaking logic anywhere in the association. **Scoring**: all high school
tennis is no-ad, and doubles is a full best-of-three rather than the college eight-game
pro set. Every match plays to completion; there is no clinch in high school.

### Schedule

District **double round robin** — you play every league opponent home and away — plus 4–8
non-district duals. District size therefore sets season length: a 12-team district is 22
league duals, about 26 total.

A double round robin turned out to be the subtlest thing in the release. The obvious
implementation (`for a: for b: for leg in (0,1)`) is a correct double round robin and a
schedule no high school has ever played — it puts both meetings with every opponent on
consecutive dates all season. The league is now generated as **rounds** via the circle
method and run as two separated passes: early non-district, district pass 1, a mid-season
window, district pass 2, a late tune-up.

A plain `reversed()` is not the mirror, either. It makes the last opponent of pass 1 the
first of pass 2, recreating the back-to-back pairing for exactly one opponent per team
while the other ten look perfect. The scheduler now scores every rotation of both mirror
families by its worst pair and keeps only those clearing half a pass, drawing one per
season so the rotation varies year to year.

Two related fixes fell out of the same work. Venue is **one bit per pairing**, not per
meeting, so "the return match reverses venue" holds by construction. And a dual's random
seed comes off the **pairing**, never its position in the list — a local index restarts at
zero on the second pass, which gave identical matchups different results depending on how
the caller sliced the rounds.

District place is district win percentage, then a five-rung tiebreak ladder: head-to-head
among the tied teams, the aggregate of those meetings, overall record, Power Index, then
opponents' opponents' win percentage. Ties resolve as a **group**, not pairwise — a
three-way head-to-head is a mini-league, and a pairwise comparator on one is not
transitive.

### The postseason

State is **32 teams in 7A and 24 elsewhere**, and qualification is earned on court. The
rating-based wild cards that existed briefly are gone; a report of a #14 missing State
while #23 got in by winning is what removed them. Three ways in:

- the eight **Zonal champions** (automatic, and the draw's top seeds, so a 24-team field's
  eight byes are theirs by construction);
- the **district guarantee** — a district champion always has access, with no bye, no seed
  help and no extra berth if it also won its Zonal;
- the **recovery rounds**, Super Regionals into Semi-State, for Regional and Zonal losers.

The arithmetic is dynamic rather than hardcoded: berths are field size minus champions
minus unique non-Zonal district champions, and both recovery rounds always cut by the same
fraction. Measured across a full slate, 7A ran Super Regionals 21→17 and Semi-State 24→20,
the same shape as everyone else's 14→10 and 16→12.

The draw itself is seeded, with byes to the top seeds, and then fixed — no reseeding
between rounds, as most states do it. It previously padded the field with empty slots at
the *end*, which meant the byes paired off with each other and went to nobody, and slot
order was finishing order. The result was that **round one paired seed 1 against seed 2 at
every field size**.

A state finish is counted as teams still alive, never as a power of two. A 24-team draw
plays 24 → 16 → 8 → 4 → 2. Saves archived before the seeding fix hold odder shapes — 24 →
12 → 6 → 3 → 2, with a three-team semifinal round — and still render.

Above State sits the **Tournament of Champions**, its own event with its own phase. It
borrows the state event's format but is archived separately, because the phase is the only
thing that distinguishes the two once they are rows in a table; written as "state," its
duals landed on a program's state-tournament record and "did they reach the TOC?" had no
answer to read.

### Seeding: TOSS in a third format

Seeding runs on TOSS — the same composite the college league uses, 0.40 Adjusted
Performance + 0.40 Field Quality + 0.20 opponent game share — not on win-loss. It is
computed over the **whole gender at once**, because non-district play crosses
classifications and rating one class alone cuts those edges out of the graph, and over the
**regular season only**.

The association has its own flight weight table (S1 1.00, S2 0.75, S3 0.25, S4/S5 0.10,
D1 1.00, D2 0.50). The index is archived per school per season at **full precision** and
read back, never recomputed. It was stored rounded to six decimals once, which looks free
because nothing displays more than three — but the seeder sorts on the raw value while the
rankings page re-sorts the stored one and breaks ties by school name, so any two teams
within 1e-6 collapsed and the displayed ranking contradicted its own seeds.

### Talent: smaller classifications are thinner, not capped

The first talent model stepped the mean down by classification with the spread narrowing
as the mean fell. A position-by-position measurement showed it had the sport backwards:

| | #1 | #9 | #1→#9 drop | best #1 seen |
|---|---|---|---|---|
| 7A | 54.4 | 31.1 | 23.2 | 60.0 |
| 3A-1A | 42.0 | 22.8 | 19.2 | 51.0 |

The number ones were **12.4 apart and the number nines only 8.3** — the top fell faster
than the depth — and a 3A-1A program could not produce a 60 at all. Real high school
tennis is the opposite: good players turn up everywhere and enrollment buys *depth*. In
Oregon's 2026 boys table the smallest classification finished No. 9 statewide and four of
the top eight were 5A.

The fix is one mechanism: let the mean fall and the spread **widen**. Twelve ceilings are
drawn and the best nine dress, so a wide draw lifts the number one a long way and drags
the number nine down. After: top-end gap **4.5**, depth gap 8.3, the #1→#9 drop now *rises*
as schools shrink, and every classification reaches a 59–61 number one. Validated on a
played season rather than on the bands — statewide boys TOSS had 6A at No. 1 and 5A at No.
2, with medians still indexing downward.

### Program archetypes

A program is more than its classification. Four archetypes sit on top of the talent model
as durable program conditions — facilities, feeders, participation, coaching tradition —
stored in an editable override table and never branched on a school name:

| | top 9 | grade 9 | grade 12 |
|---|---|---|---|
| untagged | 38.4 | 26.5 | 42.4 |
| blue blood | 46.7 | **31.2** | 53.6 |
| development | 44.9 | 27.4 | **51.9** |
| doubles | 38.0 | 26.3 | 41.9 |

**Blue bloods** generate better and cluster, keeping the better of two draws per seat,
which lifts the middle of a lineup far more than a flat mean shift. It shows on day one:
ninth-graders in the low 30s where an ordinary program's are mid-20s.

**Development programs** have ordinary freshmen and the best seniors in the association —
the mean shift is zero, and the gain is potential plus a maturity bonus that starts at
zero in ninth grade and compounds. A development program can beat a blue blood outright,
but it has to earn it over four years. Arrive good versus leave great.

**Doubles schools** generate completely normally; the edge is a per-match lift applied only
to the doubles lineup. Measured over 25 duals: singles 84-41 either way, doubles 31-19
becoming 36-14.

**Upstarts** are a temporary multi-year run, about ten live statewide at 15–30% over the
program's own baseline, rolled per world and expiring on their own — deliberately not
storable, since a stored tag would make it permanent.

### The lineup ladder

The ladder is seeded on ability and moved by results. It briefly sorted on win count,
which is a ratchet rather than a ladder: a win total measures *opportunity*, so dressing
earns wins, wins earn the next start, and a player who dropped his opening duals could
never climb back past teammates whose only edge was being picked first. It also ranked
5-15 above 4-0, and doubles credits both partners, so a rotation player banked wins faster
than a number one drawing the toughest opponent.

Measured: a top-four player finished outside the nine on **55 of 400 rosters**, 21 of them
under seven matches all year. The reported case was a 51-OVR senior on six matches beside a
28-OVR teammate on twenty-seven.

The ladder is now ability plus a results term worth about ±7 OVR at a perfect record,
weighted by how much evidence there is — so a player who has not played sits at their
**seed**, not at the bottom, and one bad week cannot outrank a season.

The postseason freezes that ladder as an **Order of Ability** before a program's first
postseason dual and binds all postseason to it, which is the NFHS anti-stacking rule; a
live re-rank mid-bracket is the violation the rule exists to prevent. The regular season
stays league policy, and it is varied by design: each program has a durable lineup
philosophy, hashed off the school, so roughly half play the classic singles-first card and
half a doubles-forward permutation.

### Awards

Selections are **résumé-based** and live on their own page. Nothing reads overall rating,
talent, or class year. Scoring comes off the per-match log: record, flight played, opponent
quality in two passes, quality wins, cheap losses, head-to-head among near-ties, and
postseason weight.

Per classification: a State Player of the Year, All-State First/Second/Third teams (plus a
Fourth in 7A) at **10 singles and 8 doubles each**, then Honorable Mention, plus a District
POY and one All-District team per district.

Four things here were rebuilt after they shipped wrong:

**Doubles honours go to pairings, not to individual doubles players.** "8 doubles" is eight
doubles *teams* — sixteen athletes. The candidate entity is the partnership, its résumé is
only the matches those two played together, and it is rated against the *opposing pair*.
Partners rotate in this format, so one player is several candidates.

**Flight weighting is structural, not a small bonus.** Two mechanisms, both load-bearing: an
alpha that sets how far apart the flights sit, and a floor that sets how far down the card
a level reaches at all. State is a #1/#2 honour, Region reaches #3, District has no floor.
Below the floor a player needs a near-perfect record *and* a win over somebody who played
at or above the floor, checked against the match log rather than by re-scoring. A flight
sanity check is archived per season and rendered on the page.

**All-Region is region-wide and class-blind.** There is no 7A All-Region team; there is a
Gold Valley All-Region team, drawn from every program in Gold Valley whatever its
enrollment. Per classification it had been a district by another name: a class-region holds
four or five schools, so ten regions across six classes honoured about **1,080 players out
of ~300 programs** and every school placed somebody. Region-wide it is **180 selections**,
with **47% of schools placing** against All-District's 83%, and teams that mix four or five
classifications.

**Regions are not the same size, so the honour scales with them.** Halbrook Basin has 115
boys' and 128 girls' programs; North Range has 17. A region of 45+ programs crowns a First
*and* Second Team; below that, one unnumbered team, because calling it "First" with no
second promises a tier that does not exist. Halbrook alone clears 100 programs and adds an
Honorable Mention, capped at one entry per school. The thresholds are on the **program
count**, not a list of region names — four regions were named as "big" and the counts said
five.

Honorable Mention is a **threshold, not a team**: no slot count, and its size varies with
how deep the class actually was. Measured: boys 7A 30, boys 5A 7.

Two bugs worth recording because they were invisible on the surface they were on. An
athlete could appear on both the First and Second Team with different partners — ranked
slices keep tiers disjoint by index, but a player with two strong partnerships sits at two
indices, so the "already used" set had to carry across the tiers of a level. And an
athlete's category is now their **better** discipline rather than their more frequent one,
compared by percentile standing within the gender-wide field, because a singles résumé and
a partnership's are different currencies and cannot be compared raw.

Awards are also now selected **after the last dual**. They had been selected inside the
qualification loop — so the postseason weighting weighted a postseason nobody had played,
and, silently, the 1S/4D postseason moves most of a roster into doubles, meaning the
participation split the category rule reads was taken with a third of the season missing.

### Records and history

There is **no separate postseason record**. The NCAA and the NFHS both carry the postseason
inside the season total, and neither publishes a regular-season record beside it as though
the year had two halves. The school page shows one record with a finish beside it.

The record snapshot originally sat inside the loop that ran each classification's state
draw, which is correct for State and silently wrong for the TOC — the TOC needs every
group's champion, so it cannot run until the loop is over. The six programs in it archived
their last duals on their schedule and left them off their record. 131 of 137 balanced, and
the six that did not were exactly the TOC field: the shape a spot check misses. A test now
pins that every archived record covers every dual played.

A program's record persists year to year, not just its trophies. The program history emits
a row for every archived year — it once returned only years with a title or an honour, so a
school looked as though it had never played in between.

### Presentation

A district is `(classification, name)`, never the name alone — the JHSAA reuses its
geographic district names at every level, and "Halbrook Basin District" is five separate
leagues. A lookup keyed on the name alone serves the 3A-1A league under a 7A heading, with
all the right data and all the wrong league.

The state draw uses the same bracket tree as the NCAA tournament and the Preseason NIT
rather than a fourth implementation. Byes are materialised as explicit pass-through cards,
because the shared canvas connects columns positionally and a raw 12→6→3→1 round list is an
invalid input to it.

One rendering bug is worth its own paragraph. A shared bracket card splits the score string
and picks its half by which side *won*, so a home-first string swaps the two numbers on
every card the away team won — and is correct on every card the home team won, which is how
it survived a design pass, a review and a merge. The wrong half reads as an upset. More
generally: a tennis set score is **always written from the winner's side**. That is a domain
convention, not a perspective, so both teams' cards show the identical string and only the
names and the d./l. marker differ.

The high school season runs at fast fidelity — full point-by-point put **103 seconds** on the
request thread against 19.

---

## 3. Upsets fall away past a margin of error

A materially weaker team was ripping consecutive 5-0 and 4-1 postseason upsets. The
diagnosis took four hypotheses and only one of them mattered.

There are no game-day modifiers in the JHSAA at all — no context roll, no form roll. All
variance is the fast model's per-game residual. The 2026 college recalibration had
deliberately flattened the model's slope for a league whose talent is dense, and recorded
the known limitation at the time: one logistic slope cannot keep near-equals a coin flip
*and* make big gaps decisive. High school plays across gaps three to five times the college
band — exactly where that limitation lives.

Measured at a 0.10–0.15 overall gap (6–9 OVR points, a genuinely meaningful mismatch): the
singles favourite won only **69%** of lines and the doubles favourite 74%, composing into
**12.7%** underdog wins in the five-point state dual, with 4-1 and 5-0 underdog scorelines
occurring routinely.

The fix is a hinge rather than a new slope. Below a knee of 0.06 overall units — about 3.6
OVR points, roughly 1 UTR, the margin of error — nothing changed at all, so near-equal
matches keep their 2026 volatility and 3-2 upsets stay common. Above it, every extra unit
of real gap counts **2.8×**. It is shared by singles holds, tiebreaks and the doubles model,
so a dual's curves steepen together.

| eff gap (≈ OVR points) | before | after |
|---|---|---|
| 0.100–0.150 (6–9) | 12.7% | **4.6%** |
| 0.150+ | 5.4% | ≈0, and 3-2 only |

Line-level after the change: singles favourite 83%, doubles 92% at that gap.

Two notes for anyone tempted to touch it. The sub-knee band never changed, so deleting the
hinge does not "restore upsets" — it only removes the fix. And the acceleration already
saturates; the value shipped was the *gentlest* one that reached the target shape.

A separate finding from the same investigation: **TOSS rank is not strength.** The rank
correlation between TOSS and effective strength is about 0.76, so a large rank gap is
frequently a small ability gap. Upset complaints should be diagnosed on effective gaps, not
on seed numbers, and there is a calibration script for exactly that.

---

## 4. The Power Index had no weights for two thirds of a D1 lineup

TOSS weights each flight by how much it should count. When the divisions moved to their own
dual formats in 2.4, the weight table did not follow — it still described a 6+3 card, and
the lookup carried a default for anything it did not recognise.

In a D1 dual that default covered #7–#10 singles and #4–#5 doubles: **1.80 of 6.80 total
flight weight, 26% of every dual**, with #10 singles counting 1.5× as much as #6. The index
ran backwards across the bottom half of every D1 lineup and nothing errored.

There is now one weight table per division and no fallback. An unweighted division or an
unrecognised flight raises, because a missing weight is a missing *decision* and the caller
should stop rather than be served a number nobody chose.

The lesson from validating it is worth more than the fix. Checking who made the NCAA field
would have called this a rounding error — tournament membership changed by exactly one team.
The seeds are where it shows: **313 of 576 seats changed seed and 251 changed region.** A
rating change has to be validated on the seeds, not the cutline.

---

## 5. The NCAA draw is locked

The tournament field was being recomputed on every read, and one of its inputs counted the
very bracket it was seeding. The labels therefore drifted mid-tournament: **67–80 of 96 seed
positions moved**, most duals showed no region at all, and some teams showed no seed.

The bracket itself was always correct. Only the labels lied, which is why it survived so
long.

The field is now selected once and locked, and every reader reads it back from the lock. The
bracket page is a real elimination tree positioned server-side, so the cards and the SVG
elbows share one coordinate system.

The **Preseason NIT** now draws on that same tree. It had been two flat lists — round panels
with nothing connecting a matchup to the one it fed, and a four-team single-elim rendered as
three lines in a box. No seeds, no champion path, no zoom, no print, no season picker, all of
which the NCAA page already had. Its seeds are read back off the persisted draw rather than
re-derived from a live Power Index, which would have relabelled a week-1 bracket all season —
the same drift as above.

---

## 6. Scouting surfaces

Four new read-only surfaces, none of which touches the engine or the economy.

**Team Scanner** (`/intel/teams`) — every program in all four divisions in one sortable
board, with rosters expandable in place. Team strength is shown as **current OVR**, not STR:
STR is results-only, driven by matches played and opposition faced, so freshmen and new
players rate below their real ability. Neither a starters' average nor a whole-roster
average had existed anywhere before this.

**Lineup Architect** (`/intel/architect`) — deals buried talent into up to six
non-overlapping full singles cards for a target division and ranks each against that
division's real teams on the same metric: "Squad 1 · #4 of 214 in D2". Card size comes from
the division's own lineup size, never a literal six. Building this also turned up the Editor
still rendering the old universal 6-singles/3-doubles card.

**The Wire** — every transfer, every season, with the player's career on the row.

**CTA individual rankings** — national, regional and newcomer boards, replicating the real
ITA's individual rankings surface. The regions are the **nine US Census Bureau divisions**
plus a tenth "Outlying" bucket, not the real ITA's cut, which the owner rejected on the
grounds that "Texas and the Carolinas get a region but California doesn't and is lumped in
with the PNW." One region map now drives the individual boards, the portal search hometown
filter and the team regional cards. Final rankings and the recruiting class are archived per
season.

---

## 7. The recruit board reads today, not the ceiling

The recruit profile page was showing five overlapping numbers for one recruit: a hero OVR
(true current ability, on a 20-80 scale), a card OVR (a 0-100 board grade), a Composite
(that same board grade reformatted), a TennisEye star rating (results), and a Scouting panel
repeating two of those a third time under new names. "OVR" meant two different things on one
page.

Underneath the presentation problem was a mechanical one: the board's star and grade were
built from a noisy guess at the recruit's *hidden ceiling*, completely decoupled from
demonstrated performance. A recruit whose results read as clearly average could carry a
board grade that said otherwise, and nothing on the page explained the contradiction.

The board grade now reads current, demonstrated ability and is fogged accordingly; the
ceiling stays hidden where it belongs. The board also re-ranks after the junior circuit
populates results, so early-season grades are not frozen against an empty record.

---

## 8. Coaches are people with careers

A coach id already followed a coach between jobs, but the seat was the only durable record
of where they had worked, and moving a coach rewrote both the source and destination rows.
The coach page could therefore only show the current job, making every coach look as though
they had always worked there. This affected head coaches, associate heads and assistants.

Every coaching job is now visible after a move. A graduate can also be continued into
coaching with a **new coach page linked to the old player page** — the two identities meet
without merging. A converted player-coach is an ordinary coach: they can start at any D1–D4
men's or women's program and move or change role through the same tools as anyone else,
rather than being an alma-mater-only special case.

---

## 9. The Game Guide

There is now a full sectioned game manual, both as a document and as an in-app Guide tab,
covering the rules the sim actually plays rather than the ones a tennis fan would assume. It
includes a **STR / UTR / WTN conversion table**, so a number in this game can be read against
ratings people already know.

---

## 10. Design: colour, type and fonts

The visual design was ported over from the companion project.

**Colour** is now three layers: palette slots, structural slots, then semantic aliases.
Components read aliases only, which is what lets **ten light schemes** exist without touching
a single component rule. Four palettes were replaced or added in this pass. A scheme picker
lives in the top bar.

One measurement worth keeping: every slot has to be checked against its own ground before it
is written down. One supplied palette contains no colour dark enough to be ink — its darkest
value sits at 1.8:1 against its background — so its ink and link colours are derived by
pushing the palette's own hues down. Dropped in as sent, it would have rendered unreadable
body text with no error anywhere.

**Type** was the bigger problem. The app had **768 font-size declarations against a 12-token
scale that was used seven times**: 78% of all type under 14px, 34% under 12px, 31 distinct
sizes including seven half-pixel steps. The scale was raised across the board with a hard
floor of 11px, reserved for uppercase tracked labels.

Two things that fell out of it. Fixed-size boxes are **exempt and must clip** — a crest is an
icon, not prose, and four glyphs of 800-weight display type only fit a 20px square at about
9px, so the sweep pushed team abbreviations out over the school name on every bracket,
standings and portal row. Compact sizes plus `overflow: hidden`, which is a guarantee rather
than an assumption about label length. And seven fixed grid column sets had been sized
against the type they were designed with and needed widening.

The fonts are now self-hosted rather than fetched. A note for the next person: the token
files declare families in one place and sizes in another, and they both declared families
for a while — the one that imported second silently won.

---

## 11. Where the world's people come from

Four asks in sequence, each exposing the next.

### The name pool was a sieve

The 2026 diversity blend was right in intent — real nations field people of many heritages,
and a France squad of nothing but French-first-plus-French-surname reads like a spreadsheet.
The implementation picked the donor culture with a *second, independent draw from the whole
world mix*, so any region could donate a name to any other. A Dominican drew a Russian name
at exactly the rate Russia sat in the mix.

Measured: **11.4% of all players** carried a name from a heritage with no plausible link to
their country. Nothing errored — generated names are real names, so it reads as a slightly
odd squad rather than as a bug.

Diaspora is now **directed**. A region may only receive a name from a heritage it declares,
and a region that declares none is monocultural — that is the default now, not the exception.
23 regions declare sources: France from the Maghreb and West Africa, Britain from South Asia
and the Caribbean, Brazil from Japan, Italy and Lebanon, and so on. Undeclared cross-heritage
draws went from 11.4% to **zero**; the residual 2.6% is entirely declared, which is the
feature.

### Africa is six regions

The old shape filed Kenya with South Africa and Zimbabwe under a "cricket nations" bucket and
dumped Angola and Mozambique into a pan-African one. **West Africa and Central Africa could
not be expressed at all** — there was no key to put a weight on. There are now six regions,
with 1,338 curated names behind them.

### Repetition is pressure, not pool size

"It rolls the same names too often" is not answered by a bucket count. The metric is
**expected draws per 10,000 ÷ bucket size**, measured at each bucket's heaviest preset weight.
A 200-name bucket at 4% is under more strain than a 40-name bucket at 0.1%.

Measured across every bucket: **10 over 1.5×**. 1,813 names went into exactly those, and the
re-measurement found **none**.

The same pass killed a placeholder. When the picker exhausted a bucket's unique combinations
it returned a literal `Player 447` with an empty country code — a person nobody can explain,
shipped into a save and archived alongside everyone else. It now returns the last valid name
it built. A repeated real name is a blemish; a fake one is a bug, and the empty country makes
it a bug in the nationality data too.

### Five presets, and two emergent regions

There are now five authored international-distribution presets — Global College (the
default), Latin World, Afro-Global, Asia-Pacific and Eurasian — each covering 94 regions
summing to exactly 100.0, with the US pinned at 30.0 in all five so they stay comparable.

The Caribbean and the Pacific were then boosted as **emergent warm-weather regions**: warm,
high-sun places that would plausibly be tennis-productive with money in them, and the two
thinnest blocks in the data. Names first — 1,260 across 23 buckets — then weights:

| preset | Caribbean | Pacific |
|---|---|---|
| Global College | 0.92 → **2.60** | 0.90 → **2.00** |
| Latin World | 1.74 → **4.40** | 0.90 → **1.80** |
| Afro-Global | 0.59 → **3.00** | 0.90 → **1.60** |
| Asia-Pacific | 0.69 → **1.80** | 1.20 → **3.40** |
| Eurasian | 0.66 → **1.40** | 0.90 → **1.20** |

Funded from ANZAC down to a floor and then from Europe pro-rata — nothing out of Africa or
Asia, which had just been raised, and nothing out of the US anchor. All five still sum to
100.0 with their Africa, Asia and US totals unchanged, and no bucket exceeds 1.1× reuse
pressure.

### Hometowns from real place data

The follow-up to the name work was the hometowns behind them. The per-state city lists
were hand-typed flavour that nobody had ever sized against draw volume: **33 of 55
states drew more recruits per class than they had cities** — Florida drew 248 recruits a
class from 46 cities — and nothing errored, because a repeated hometown is not an error.

Typing more names in would have added invented data on top of thin data, so the pools
are now **generated from two real datasets**: GeoNames supplies population, and the US
Census Gazetteer supplies legitimacy — each catching what the other misses. GeoNames
alone classes DC neighbourhoods like "NoMa" and "Foggy Bottom" as towns (first attempt
gave the District 28 "cities"); the Census place file alone gave Vermont four, because
New England's municipalities are towns and Hawaii's are CDPs, invisible at that summary
level. The curated lists stay as a union on top — the campus towns matter to this game
and many sit under the population floor.

The floor is graduated per state, because narrative diversity was the point: each state
keeps the highest of 10k / 5k / 2k population that still yields about forty places, so
big states take no hamlets while the states that simply don't have big cities — Vermont,
Wyoming, Montana, Maine — are represented by the towns they actually have. Vermont
fields 40 real towns, Maine 124.

After: **1,218 distinct US cities becomes ~5,100** (Florida 46 → 295, California 81 →
461), Canada's birthplace pool 60 → 659, Mexico's 19 → 610, all population-weighted by
the same one-slot-per-25k rule Jefferson already used. States drawing more than one
recruit per city per class: 33 → **2**, and both survivors are by design.

### A mix is a file you keep

Authoring the international mix is about ninety weights, and it had to be re-entered from
scratch on every new save.

Saving it would not have fixed that, and this is the load-bearing part: the settings table
lives in the same database as everything else, so a "saved preset" dies with the save —
precisely the event it was meant to survive. So the onboarding screen now **downloads** the
whole mix to a small `.json` file, and loads one back into a brand-new save. Saving a named
mix into the current world is still there as a convenience, and the panel says plainly which
of the two lasts.

Two decisions inside the format. Weights are the editor's own integers rather than
fractions: normalising round-trips the *mix* — everything renormalizes downstream — but not
the *display*, and 160 coming back as 561 is useless to someone authoring by eye. And a load
**reports what did not survive**: region ids get added and renamed between builds, so a mix
authored against an older one is quietly a different mix with every value still looking
valid.

That last point turned out to be more than theoretical. A region id this build no longer has
is not an error anywhere — the picker's draw returns nothing and simply retries — so an
existing save whose stored mix still named `africa` or `africa_cricket` silently
redistributed that share, and a mix made *only* of retired ids burned every retry and fell
through to the `Player NNN` placeholder that had just been removed. Retired ids now fold into
their successors on read, split by what each old region actually contained.

---

## 12. The pro league was never short of players

The Global Team Tennis founding draft was seating **112 generated players out of 112** on a
fresh world.

Not a shortage. The graduate table is only written *at a year rollover*, so a league founded
in world year 0 queried an empty table — standing next to a college world with about 2,262
programs and roughly **7,300 seniors** in it. With no archived class, the founding draft now
reads the live about-to-graduate cohort. Measured after: 112 of 112 real college players,
every one of them present in the world.

This is deliberately not a general fallback. Everywhere else an empty graduating class means
the league's world binding is broken, and substituting live players there would convert a
visible fault into plausible-looking data.

A related fix in the same area: the pro league had been generating **99.8% international**
players against a configured 30%, because the world's region map omits the US by contract —
its share is the domestic split, not a region weight — and that map was being handed straight
to the name picker. There is now one place that scales an international mix and restores the
domestic share, which the college side already had and now shares. Measured after: 69.4% US.

---

## 13. Infrastructure

**The test suite no longer shares a database with the app.** The suite resolved the same
database path the app does, and one fixture reset the world and played a season into it — so
test results depended on whatever happened to be on the developer's disk rather than on the
code. This is a hermeticity problem, not a data-loss one.

It is also what broke the All-American selections. A world reset with the played season's
rows left behind meant the season's ~4,600 player ids named people the roster builder no
longer produced. The selector skipped every one and returned an empty board on a fully
played season — no error, no log line, a clean and completely wrong "nobody was honoured."
It was diagnosed by measuring the two id sets (4,596 each, **zero overlap**), not by reading
the selector, which was correct throughout. The selector now logs loudly when nothing
resolves, because an empty honours board on a played season is a fault and not a result.

**Reading configuration inside a transaction deadlocks.** The config layer opens its own
connection and issues a `CREATE TABLE IF NOT EXISTS`, which takes a write lock — and the
world and pro-league tables share one database file. This was latent for as long as the name
picker needed a single config key, because that key was almost always already cached and the
second connection was never opened. Adding a second key made a cold read likely and 20 of 21
pro-league tests failed at once.

**The world-config editor was filing China, Japan, Taiwan, France, Argentina, Colombia,
Chile, Peru, Ecuador, Uruguay, Bulgaria and Romania under "Other"** — the continent grouping
had not been updated when those were promoted out of shared buckets.

---

## A note on how most of this was found

Almost none of the bugs in this release threw an exception. The dual formats had no weight
table and the index ran backwards; the bracket recomputed itself and only the labels lied;
the awards ran before the postseason and the arithmetic still balanced; the name pool put
Russian surnames on Dominicans and every name was real; the pro league drafted 112 people
who did not exist and every one had a plausible name and a nationality.

The common shape is that a wrong distribution is not an error. What caught them was
measuring the thing directly — position by position, id set against id set, seeds rather than
the cutline — usually after someone looked at a page and said the result felt wrong.
