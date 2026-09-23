# DESIGN â€” story forms, taken from real sports desks

Owner ask (2026-09): season journalism from the research export should surface
what the UI cannot show, not restate what it already does. The way to keep a
writer honest about that is to give it FORMS, not a data dump: each form is a
claim shape with a known evidence requirement, and a detector is written to a
form. This document is the taxonomy, drawn from how a handful of real desks
actually structure their pieces â€” and, since the 2089 draft, the WRITING
rules at the end ("Writing the piece"), which a story must pass as well as
the evidence rules. Read both before writing a season review.

Rule of the exercise: a form is only worth a detector here if the evidence it
needs crosses a seam the site does not cross â€” two tables, two seasons, two
programs, two genders, or the two sides of one dual. Anything a single page
already states scores zero on the invisibility factor
(`salience = surprise Ã— consequence Ã— invisibility`).

**Consequence is a gate, not merely a multiplier.** Repetition, closeness and
familiarity do not make a regular-season dual consequential in a postseason system
where both teams remain comfortably alive. A repeated matchup may provide the
opening observation or the history for a later rematch, but it does not deserve the
lead unless one of the meetings changed a berth, seed, road, elimination, title,
streak or settled evaluation of a program. A well-written observation cannot rescue
a low-stakes selection.

---

## What each desk is actually doing

| Desk | The repeated move | What it needs |
|---|---|---|
| **Defector** (Zarzycki "why you ding dongs won't come to the net"; Nathan's match essays) | Take a belief everyone holds, admit you held it, then show the MECHANISM that makes the behaviour rational. Or: one match, close-read, and what it changed. Headlines negate or overstate on purpose ("Changed Nothing", "Match Of His Life"). | A conventional reading + the structural cause. Never the number alone. |
| **The Pudding** (Titletowns; the pitch page) | An argument that "invites debate", proven on a DISTRIBUTION, not a ranking; the reader's own definition is addressed head-on ("you define it"); three framings of one question. Rejects topics without a thesis, and rejects AI-flavoured pitches for lack of a specific obsession. | A whole-population dataset and a question with more than one defensible answer. |
| **ProPublica** (Illinois NIL disclosure) | A RULE, a measurement of compliance against records (1,037 deals cross-referenced with what was publicly visible), who the rule protects, named cases both ways, the institution's reply, and what changes next. | A rule, a ledger, and the gap between them. |
| **The Athletic** | "How X beat Y": tactical record, one decision at a time; systems/business pieces; player arcs. | Per-match detail the box score does not carry. |
| **Irish Examiner / Echo** (Cork club GAA; Buttevant) | The DROUGHT (99 years, dated to the day and the opponent), the parish and the family names in the lede, the jersey number retired, the captain's day job; a follow-up months later on "the step up". Ordinary reports lead with the consequence (who they meet next, who is relegated), not the score. | Archive depth, family ties, and the fixture that follows. |
| **Yle** | Small nation, big field: Finnish players framed INSIDE the tournament story, by milestone ("first since", "oldest in 34 years", "99-week streak ends"), never as a separate small-country beat. | Milestone arithmetic over the archive. |
| **Fox Sports Australia** | Reaction and "talking points" after every session; the home-player angle first; the controversy (a box, a question, a default). Not a model for this desk, but useful for what NOT to generate: reaction without new fact. | â€” |
| **Local US preps** (SI Oregon, KSWO Lawton siblings) | The state final led by the player's exhaustion and the deuce count, seed vs seed, the girls' result in the same breath, the team total to the half point. The sibling piece: four from one school, three won on the day, "three automatic friends", the coach on character. | Seed, score, grade, siblings, the parallel gender result. |

---

## The forms, with what each needs from the export

Each entry: the claim shape Â· the exemplar Â· evidence tables Â· whether a page
already shows it Â· what is missing to detect it.

### 1. The rule and its winners (ProPublica)
**Claim.** Rule R exists; it was meant to do A; measured over N seasons it does
B, and here are the programs on each side of it.
**Fits here because** the JHSAA rulebook is unusually dense and every rule is
documented with intent: the protected seat, the Parastate bids, the
Semi-Conference, the Specials, the 2S/3D and 4S/5D pilots, the JV cut at 14.
**Evidence.** `duals` (phase, round) Ã— `jhsaa_standings` (seed, place) Ã—
`jhsaa_program_history`, over many seasons.
**On a page?** No. Every page is one season, one class.
**Detector.** For each rule with a named beneficiary class (district champions,
at-larges, Conference winners), compute the outcome distribution of that class
versus the counterfactual pool it was drawn from, per season, and flag the
seasons where the gap is largest or flips sign.

### 2. The number that lies (Defector / Pudding)
**Claim.** The figure everyone cites for team T (its rank, its record, its
TOSS) is produced by a mechanism that makes it misleading, and here is the
mechanism.
**Evidence.** `jhsaa_computer_ratings` (nine systems + composite) Ã— schedule
strength Ã— format mix per team.
**On a page?** The composite is. The DISAGREEMENT is not, and neither is why.
**Detector.** Teams with the widest spread across the nine systems, joined to
the property of their schedule that explains it (share of duals in the
non-district window, share at a foreign format via showcase host, league
strength). The story is the mechanism, not the rank.

### 3. Why they play that way (Defector, Zarzycki)
**Claim.** A behaviour that looks like a mistake (doubles-forward seating, a
rested starter, a pairing that never changes) is rational given the format and
the roster, and here is the cost of the alternative.
**Evidence.** `lines` Ã— `line_players` Ã— `players` (grades) over a program's
season; needs the coach-evaluated order and the rest decision, which are NOT
exported today.
**On a page?** The lineup is; the reasoning is not.
**Missing.** Per-dual columns for the rest decision and the evaluated order.

### 4. The drought, dated (Irish Examiner)
**Claim.** Program P last won X in year Y against Z; here is what happened in
between and who was on the court both times.
**Evidence.** `jhsaa_program_history` Ã— archive brackets Ã— `line_players`.
**On a page?** The title board shows the count. Not the gap, not the opponent
that day, not the family surname on both rosters.
**Detector.** Longest gaps closed this season, per unit (district, road unit,
State, individual flight); attach the two duals, the two lineups, and any pid
whose surname appears in both.

### 5. The milestone inside the bigger story (Yle)
**Claim.** First X since Y; oldest/youngest/only; a streak ended at N.
**Evidence.** Archive-wide folds on players and programs.
**On a page?** Some (repeat rolls). Most "first since" facts are not.
**Detector.** For every champion, finalist and All-State pick, compute the
class-and-flight-scoped "first since" and "only ever" facts; keep those over a
threshold of years or uniqueness.

### 6. The pairing, the tie, the house (KSWO, Examiner)
**Claim.** Siblings on one roster, or across the boys' and girls' programs, or
across two schools in one town; what they did together and apart.
**Evidence.** Family ties (authored today; generated per the sibling design) Ã—
`line_players` for shared doubles lines Ã— both genders' results.
**On a page?** The tie is a line on a player page. The joint record is not.
**Detector.** Every sibling pair's D-line record together, and each one's
season alone; the cross-gender pair whose two programs both reached State;
the town with three related players on three rosters.

### 7. The one flight (Athletic, "how X beat Y")
**Claim.** The dual was decided at flight F by players nobody would name, and
that flight decided a title or a seat.
**Evidence.** `lines` Ã— `duals` Ã— standings tiebreak rungs and State seeding.
**On a page?** The front-page desk already has `one_flight` and `nailbiter`
detectors on the RESULT. The CONSEQUENCE chain is not on any page.
**Detector.** Re-run the tiebreak ladder and the seed order with each decisive
line flipped; report the lines whose flip moves a district place or a State
line, and the season record of the players on them.

### 8. The distribution (Pudding)
**Claim.** Across the whole association, here is the shape of something: where
the close duals live, how often the better-ranked team wins by class, what a
3S/4D season does to a program built on singles.
**Evidence.** All of `duals` and `lines` for a gender-season, with expected
win probabilities.
**On a page?** `/jhsaa/realism` and `/jhsaa/flights` show two of these. The
by-class, by-format, by-tier cuts are not.
**Detector.** A fixed set of distributions computed every season and DIFFED
against the prior season; the story is the one that moved.

### 9. The step up (Examiner follow-up)
**Claim.** A program promoted, reclassified or playing up: what its first season
in the new class looked like against what its old-class record predicted.
**Evidence.** `programs` (class, play-up) Ã— two seasons of `jhsaa_standings`.
**On a page?** No cross-season program comparison exists.

### 10. The season that never made the page (local preps)
**Claim.** A program or player whose season is remarkable by the numbers and
who finished outside every honour, bracket and desk item.
**Evidence.** `underplayed_candidates`, records, ratings, awards.
**On a page?** By definition not.
**Detector.** Take the complement of every honoured pid and every desk story;
rank what is left by record-over-expected and by flight weight.

---

## What the export does not yet carry

Forms 3, 7 and 8 need per-dual state the engine knows and discards:

- expected win probability per line and per dual, fitted per FORMAT
- the home-court roll for the dual
- the rest decision (which starters sat, and why)
- the coach-evaluated order beside the raw ability order

All four are known inside `play_dual` / `_lineup` at archive time. They are
the prerequisite for anything beyond forms 1, 4, 5, 6, 9 and 10.

## What is deliberately not a form here

Reaction, talking points, power rankings, and "X things we learned". They add
no fact the reader lacks, and they are the register the desk rules
(`jhsaa_desk.py`: lead with a number or a name, no adjectives) already forbid.

## Writing the piece â€” what the 2089 draft got wrong

The forms above say what a story may CLAIM and what evidence it needs. They
say nothing about the sentences, and the first draft written to them (the 2089
"eight stories") showed that a writer can satisfy every evidence rule and still
produce something nobody would read. An independent critique of that draft
found five faults. They are now rules, and one earlier misreading is retired.

### Before rule 0: use memory, not meaning, to choose the material

"What did the season mean?" invites a thesis before the reporting and produces a
piece that spends its length proving its first sentence. A season review starts with
the questions a beat writer can answer after living through it:

- What did people keep bringing up after the schedule ended?
- Which prediction aged badly?
- Which result changed how coaches spoke about a team or player?
- Which postseason match made an earlier result newly relevant?
- What looked obvious afterward but was not obvious beforehand?

The answers do not have to collapse into one idea. If the material contains several
unrelated consequential stories, the correct architecture may be a notebook with
unequal items. Do not turn a notebook into an awards banquet or use one anecdote as
a metaphor for the entire association.

### 0. Invent the fiction. The record is the only thing you may not contradict
**Owner rule (2026-09, restating what was said at the start):** this is a
fictional association and the point of the desk is to invent the fiction and
the texture around the record. The draft refused to â€” it treated the export as
the whole of what may be said, wrote "there is no way to know why" beside a
12-12 record, and read every constraint as "do not generate". That is the
opposite of the brief. `docs/JHSAA_HIGH_SCHOOL_TENNIS_REPORTING_GUIDE.md` is
the authority and already lists what a writer INVENTS FREELY: coach and
assistant names, short player and coach quotes, practice observations, lineup
discussions, local expectations, how a partnership formed, how a player earned
a seat, reasonable context around a turnaround â€” and, for the desk, the
weather on the day, the crowd, the drive, the family in the stands, the
history a town tells about itself. **The one rule is the guide's: do not
invent a fact that contradicts the files.** A 5-0 is never a 3-2 thriller; a
junior is never a senior; a No. 28 seed stays a No. 28 seed; a team that
missed State never qualified. Everything the export holds is the RECORD and is
fixed. Everything it does not hold is the writer's, and leaving it blank is the
failure, not filling it.

Counterfactuals are part of that licence and are wanted: "had the D2 breaker
gone the other way, Silverton is in the Zonals and Oak Knoll's road runs
through the Super Regionals" is a legitimate sentence â€” it is how a desk makes a
decisive flight legible, and it is how the writer rates what a result was
WORTH. Write it as a counterfactual (the reader must not mistake it for what
happened), and derive it from the actual ladder (the tiebreak rungs, the seed
order, the road) rather than from a guess.

### 1. A number is evidence, not a sentence
The draft read: "Bidwell went 12-12. It won a district title. Its No. 1 went
7-8." That is telemetry â€” the box score restated in prose, and the reader
already has the box score. **A number earns its place when it explains
something or is explained by something.** Every figure in the body must attach
to a cause, a consequence or a comparison: a 12-12 record is a story only when
the piece says what the twelve losses have in common (the opponents' class, a
flight that never held, a partner change in March) â€” a `duals` Ã— `lines` Ã—
`line_players` question where the export answers it, and the writer's own
invention where it does not (a coach who rebuilt the doubles after spring
break, a No. 1 playing through a spring of exams). Either way the number is
never left standing alone.

### 2. Vary the architecture of the sentence
Every sentence in the draft was Subject â†’ Verb â†’ Record, and after three of
them the reader hears a drumbeat, not a story. Concretely:
- **Lead with the consequence at least once a paragraph** ("Because the D2
  flight went to a third set, the seed line moved" â€” the Examiner's ordinary
  report leads with who they meet next, not the score).
- **Put the number in a subordinate position** when it is context ("Two months
  after a 12-12 regular season, â€¦") and in the main clause only when it IS the
  point.
- **Use one long sentence and one short one per paragraph.** A run of
  same-length sentences is the tell of a generated draft.
- **Active, physical verbs.** A team does not "record a result"; a No. 3
  singles "held serve from 4-4", a pairing "took the set on the second break".
  Where the set score supports the verb, use it; where it does not, the verb is
  yours to invent within the score.

### 3. Scene over telemetry
The critique asked for sensory and emotional detail, and the draft had none â€”
it said the constraints left it nothing to work with. They did not. Two
sources, used together:

**What the export carries** (the fixed record the scene is built ON):
- `lines.score` â€” every set score of every flight, so "6-4, 3-6, 7-6" is a
  match that swung twice and the writer can say where.
- `duals.decided_on_tiebreak` â€” a FLAG only: a level Group 2 postseason dual
  was settled at three concurrent 10-point breakers. The export does NOT carry
  the three decider scores (`build_jhsaa` writes the boolean and drops them,
  and the championship JSON stores only the overall points and the winner), so
  a writer may say the dual went to the deciders and who won them, and must
  not quote decider points as if they were on file.
- `duals.date`, `home_program_id` â€” the day, and the DESIGNATED HOME SIDE.
  That is row orientation, not necessarily the venue: showcases, State and the
  TOC are neutral (`jhsaa.NEUTRAL_PHASES` â€” no home-court roll, a showcase's
  host is stored separately), so only a league, invitational or road dual may
  be written as played at the home side's campus. A neutral-phase dual is
  written at a neutral site, or the venue is invented consistently with that.
- `jhsaa_program_history.state_seed`, `made_state`, `state_place`,
  `state_finish` â€” the State seed line and finish, and so the upset margin.
  (`jhsaa_standings.csv` carries record, district place, points and TOSS only;
  there is no plain `seed` column anywhere. Road-round seeding is not exported;
  the committee JSON carries the at-large seeding for the Parastate classes.)
- `players.style` / `style_trait` â€” a counterpuncher against a serve-and-
  volleyer is a MATCHUP the engine actually plays
  (`docs/AAR-style-matchup-cross-term.md`); describe it as one.
- `line_players.position` with `players.grade` â€” who was on the flight, how
  old, whether they held it all season or arrived there in the postseason.
- `jhsaa_program_history` â€” the prior meeting, the last time this one got
  this far.

**What the writer supplies** (the texture, per Â§0): the wind off the river at
the away court, the bus that left at six, the assistant who charts every
service game, the senior's parents who have not missed a dual since ninth
grade, what the coach said at 6-6, what the sophomore said afterwards. None of
it is in a table and all of it belongs in the piece â€” consistent with the
record, with the town (the gazetteer is real geography), with the grades and
the school, and with the sport (a quote should sound like a high-school coach,
never a television analyst).

A scene is the record's facts arranged in the order they happened, at the one
dual that mattered, dressed in invented texture that never contradicts them.
Pick the pivotal match, not the season summary, and spend the paragraph there.

### 4. Stakes before the tiebreak, not after
The draft reported the decisive breaker and only then said what it decided.
State the consequence FIRST â€” the seed, the berth, the district title that
hung on the flight â€” so the reader knows why the 10-8 matters while it is
being read. The salience rule (`surprise Ã— consequence Ã— invisibility`) is
already an ordering rule for the sentence: consequence up front.

### 5. The framework never leaks into the body
"Form 7, the one flight." "Source: the 2089 research export, duals.csv joined
to lines.csv." "This story crosses the seam between two seasons." "The data
does not say why." All of that appeared in the draft's BODY. The forms are
scaffolding for the writer; the reader must not see the scaffold. No form
names, no table names, no column names, no evidence-requirement language, no
seam talk, and no confession that the tables ran out â€” where they run out the
writer writes. Sourcing belongs in ONE line at the end of the whole document,
never per story.

### 6. Constraints are not a licence to drop voice
The desk rules (no ratings in the prose, no adjectives in a headline, no fact
against the record) were read by the draft as "write flatly" and then as "do
not write". They forbid CONTRADICTING the record; they do not forbid rhythm,
ordering, emphasis, a quote, a scene, or a sentence that leads with the thing
that matters. Every desk in the table at the top of this document works under
a HARDER constraint than this one â€” a real paper cannot invent at all â€” and
none of them reads like a log file. The question to ask of each paragraph:
would the Examiner's club-GAA desk run it?

### 7. Stay at the scale of the observation

The useful sentence in a draft is often the one that could only have been written
after watching this particular season: by the third meeting the parents knew both
lineups; a coach kept referring to the same lost breaker; the State draw made a
March result look different in June. When the draft reaches such an observation,
stay there long enough to report it.

Do not immediately promote the observation into a thesis about the year, judgment,
resilience, belief, uncertainty or sport itself. Those zoom-outs create the synthetic
cadence the reporting is supposed to avoid.

Ban these constructions from season journalism unless the literal wording is
unavoidable in a quoted source:

- "The season was..." / "The year belonged to..."
- "What made [year] unique..." / "The lesson was..."
- "The story of the season..." / "That was [year]."
- "It was not X. It was Y." / "Not X. Y."
- "In the end..."

Use the counterfactual sentence test: if the line could have been drafted before the
season and completed later by inserting names, it is not reporting. Replace it with
a detail that depends on the recorded sequence or with invented local texture that
could only belong to this scene.

### A worked correction
Draft:
> Silverton Prep finished 14-9. It went 8-4 in district. Its No. 2 doubles
> pairing went 15-6. It lost in the Regional to Oak Knoll 4-3. The D2 flight
> was decided in a tiebreak. Form 7: the one flight. The data does not show
> why the pairing lost.

Rewrite. The record (seed, flight scores, joint record, grades, prior
meetings) is the export's; everything else is invented and contradicts none
of it:
> The Zonal place Silverton Prep had spent a spring earning came down to two
> sophomores at No. 2 doubles, on a Tuesday when the wind off the Klamath
> made every lob a guess. Oak Knoll, seeded above them, had taken the
> singles 2-1 and won D3; Silverton had S1, D1 and D4; the Regional was 3-3
> when the D2 pair â€” 15-6 together since March, never once split, a
> partnership the coach admits she assembled by accident when a senior
> missed a bus â€” lost the first set 4-6, took the second 6-3 and reached 6-6
> in the third. "I told them to stop looking at the other courts," Dana
> Reyes said. "They were the other court." They lost the breaker 8-10, and
> with it the Zonal went to Oak Knoll, which had not beaten them in four
> meetings; Silverton's road to State now runs through the Super Regionals.
> Had the breaker gone the other way, the two schools trade those roads;
> instead the two sophomores are the first Silverton pair since 2081 to
> carry a Regional to a third-set breaker and lose it.

The tally closes: Oak Knoll S2, S3, D3 and Silverton S1, D1, D4 is 3-3 with
D2 the seventh flight, so the dual genuinely turns on it (a worked example
whose flights do not add up teaches the writer to skip the arithmetic). The
Regional loser goes to the Super Regionals and the winner to the Zonals
(`docs/JHSAA-road-to-state.md`), which is the consequence the paragraph
leads with.

It reads as a story because the consequence leads, the sentences vary, the
verbs are the sport's, the paragraph stays on one match, and the texture â€” the
wind, the bus, the quote, the counterfactual â€” is written rather than
withheld.

### Checklist before a story ships
- Did the lead event change a title, elimination, berth, seed, road, streak or the
  evaluation of a player/program? If not, why is it leading?
- Is a repeated regular-season matchup being mistaken for stakes? State the later
  consequence it caused or reduce it to context.
- Does any sentence restate a figure a page already shows, with no cause or
  consequence attached? Cut it or attach one â€” invented if need be.
- Are three consecutive sentences the same shape? Recast one.
- Is there ONE dual, one flight, one set score the paragraph lives on?
- Is the consequence stated before the decisive score?
- Does the body name a form, a table, a column, "the export", or say the
  data cannot tell? Remove it and write the missing part.
- Does any invented detail contradict a row â€” a score, a seed, a grade, a
  finish, a date, a name? Fix the detail, never the record.
- Is there a quote, a scene or a counterfactual? If not, the piece is still
  telemetry.
- Could the closing sentence have been written before the season? If yes, cut the
  conclusion and end on the last concrete fact or observation.

---

Sources read for this: The Pudding, "The Winningest Cities in North American
Sports" and its pitch guidelines; Defector, "I Finally Understand Why You Ding
Dongs Won't Come To The Net" and Giri Nathan's tennis index; ProPublica /
Chicago Tribune on Illinois NIL disclosures; Irish Examiner's Cork club
championship desk and the Buttevant 99-year pieces; Yle's tennis index; SI
Oregon's 5A boys tennis state report; KSWO on the Phelps siblings at
Eisenhower. Fox Sports Australia and The Athletic were not fetchable from this
environment; their rows above are from search summaries only.
