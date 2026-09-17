# DESIGN — story forms, taken from real sports desks

Owner ask (2026-09): season journalism from the research export should surface
what the UI cannot show, not restate what it already does. The way to keep a
writer honest about that is to give it FORMS, not a data dump: each form is a
claim shape with a known evidence requirement, and a detector is written to a
form. This document is the taxonomy, drawn from how a handful of real desks
actually structure their pieces.

Rule of the exercise: a form is only worth a detector here if the evidence it
needs crosses a seam the site does not cross — two tables, two seasons, two
programs, two genders, or the two sides of one dual. Anything a single page
already states scores zero on the invisibility factor
(`salience = surprise × consequence × invisibility`).

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
| **Fox Sports Australia** | Reaction and "talking points" after every session; the home-player angle first; the controversy (a box, a question, a default). Not a model for this desk, but useful for what NOT to generate: reaction without new fact. | — |
| **Local US preps** (SI Oregon, KSWO Lawton siblings) | The state final led by the player's exhaustion and the deuce count, seed vs seed, the girls' result in the same breath, the team total to the half point. The sibling piece: four from one school, three won on the day, "three automatic friends", the coach on character. | Seed, score, grade, siblings, the parallel gender result. |

---

## The forms, with what each needs from the export

Each entry: the claim shape · the exemplar · evidence tables · whether a page
already shows it · what is missing to detect it.

### 1. The rule and its winners (ProPublica)
**Claim.** Rule R exists; it was meant to do A; measured over N seasons it does
B, and here are the programs on each side of it.
**Fits here because** the JHSAA rulebook is unusually dense and every rule is
documented with intent: the protected seat, the Parastate bids, the
Semi-Conference, the Specials, the 2S/3D and 4S/5D pilots, the JV cut at 14.
**Evidence.** `duals` (phase, round) × `jhsaa_standings` (seed, place) ×
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
**Evidence.** `jhsaa_computer_ratings` (nine systems + composite) × schedule
strength × format mix per team.
**On a page?** The composite is. The DISAGREEMENT is not, and neither is why.
**Detector.** Teams with the widest spread across the nine systems, joined to
the property of their schedule that explains it (share of duals in the
non-district window, share at a foreign format via showcase host, league
strength). The story is the mechanism, not the rank.

### 3. Why they play that way (Defector, Zarzycki)
**Claim.** A behaviour that looks like a mistake (doubles-forward seating, a
rested starter, a pairing that never changes) is rational given the format and
the roster, and here is the cost of the alternative.
**Evidence.** `lines` × `line_players` × `players` (grades) over a program's
season; needs the coach-evaluated order and the rest decision, which are NOT
exported today.
**On a page?** The lineup is; the reasoning is not.
**Missing.** Per-dual columns for the rest decision and the evaluated order.

### 4. The drought, dated (Irish Examiner)
**Claim.** Program P last won X in year Y against Z; here is what happened in
between and who was on the court both times.
**Evidence.** `jhsaa_program_history` × archive brackets × `line_players`.
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
**Evidence.** Family ties (authored today; generated per the sibling design) ×
`line_players` for shared doubles lines × both genders' results.
**On a page?** The tie is a line on a player page. The joint record is not.
**Detector.** Every sibling pair's D-line record together, and each one's
season alone; the cross-gender pair whose two programs both reached State;
the town with three related players on three rosters.

### 7. The one flight (Athletic, "how X beat Y")
**Claim.** The dual was decided at flight F by players nobody would name, and
that flight decided a title or a seat.
**Evidence.** `lines` × `duals` × standings tiebreak rungs and State seeding.
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
**Evidence.** `programs` (class, play-up) × two seasons of `jhsaa_standings`.
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

---

Sources read for this: The Pudding, "The Winningest Cities in North American
Sports" and its pitch guidelines; Defector, "I Finally Understand Why You Ding
Dongs Won't Come To The Net" and Giri Nathan's tennis index; ProPublica /
Chicago Tribune on Illinois NIL disclosures; Irish Examiner's Cork club
championship desk and the Buttevant 99-year pieces; Yle's tennis index; SI
Oregon's 5A boys tennis state report; KSWO on the Phelps siblings at
Eisenhower. Fox Sports Australia and The Athletic were not fetchable from this
environment; their rows above are from search summaries only.
