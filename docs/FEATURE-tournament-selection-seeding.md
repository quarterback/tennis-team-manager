# How the National Tournament Field Is Built

*A transparency note on selection, seeding, and bracketing in Play to Clinch.*

Every season — for men's and women's tennis, separately, in each of D1, D2, D3,
and D4 — the simulation builds a national championship field "as if the tournament
were held today." We get asked, reasonably, *how*. This note lays out exactly how
a team gets in, how it's ranked once it's in, and how the bracket is drawn. Each
division-and-gender season is its own independent tournament; nothing below mixes
across them.

The single most important idea is this:

> **Selection, seeding, and bracketing are three separate questions. We never use
> the answer to one to settle another.**

- **Selection** answers *"Why is this team in the tournament?"*
- **Seeding** answers *"How good is this team?"*
- **Bracketing** answers *"Who should this team play?"*

Keeping them separate is what makes the field fair. Here is each in turn.

---

## 1. Selection — who gets in

The field is a fixed size (64 teams in D2/D3/D4; 96 in D1, which is a much larger
division). Two kinds of teams fill it:

**Automatic Qualifiers (AQ).** Win your conference and you're in. Full stop. An
automatic bid is a reward for being the best in your league, and it cannot be
taken away by a selection formula. Projected conference leaders hold these bids in
the live projection.

**At-Large (AL).** Every remaining spot goes to the best teams that did *not* win
their conference, ranked by **Power Index** — our results-based strength rating.
No politics, no reputation, no bid-stealing: the strongest available bodies of
work get the at-large seats, in order, until the field is full.

That's the entire selection step. It decides admission and nothing else. A team's
method of entry — AQ or AL — is recorded, then deliberately set aside.

---

## 2. Seeding — how strong each team is

Once the field is chosen, **every team in it is ranked purely by strength.** This
is the part people most often get wrong, so we'll be blunt about it:

> **Automatic-qualifier status is never a seeding input. A conference champion is
> not automatically stronger than an at-large team.**

We seed on competitive merit only — Power Index, schedule strength, and the
quality of a team's league (a team that grinds through a deep conference every
week has earned more than its raw win-loss suggests). We do **not** seed on:

- whether a team is an AQ or an AL,
- whether it won a conference championship,
- how it qualified.

So the seed list interleaves freely. A dominant at-large team can be the #6 overall
seed while a champion from a weak league sits near the bottom of the field. Both
are correct. The question at seeding time is only ever *"how good is this team?"* —
never *"how did it get here?"*

**What this looks like in the projection.** The Bracket Projection page shows the
full **Seed List**, 1 through the field size, with a small **AQ / AL** chip on each
row so you can see at a glance how a team qualified — without that chip ever moving
its seed. The cut line sits at the field size: in a 64-team field, the last team in
is **#64**, and the teams just missing out are **#65, #66, #67, #68** — the "first
four out." This is also why a left-out at-large team can carry a stronger rating
than a champion seeded just inside the cut: the champion was *selected* (it won its
league) and then seeded last; the at-large team was not selected once the at-large
spots filled, so it ranks just outside. Selection happens first; ranking happens to
the teams that were picked.

---

## 3. Bracketing — who plays whom

Only **after** every team is seeded do we build the bracket — and only here may a
team's AQ/AL status matter, purely for match-making. Bracketing never changes a
seed; it only assigns opponents.

**Today**, the bracket uses a standard protected-seed draw: the top seeds are
placed so they can't meet until late rounds (a #1 seed only faces another top seed
in a final, never a first round), and the remaining teams are drawn in around them.
Higher seeds get the easier early paths; every match is then *played out* by the
match engine, so favorites are favored but upsets happen on their own.

**The bracketing principles we are rolling out** sharpen the draw without ever
touching a seed. In priority order:

1. **Conference separation** — teams from the same conference should not meet in
   the first round if any legal alternative exists.
2. **Rematch avoidance** — avoid first-round rematches of regular-season meetings;
   the tournament should create *new* matchups. The more often two teams already
   played, the larger the penalty against pairing them early.
3. **Champion protection** — conference champions should generally open against
   at-large teams rather than each other, preserving each league's representation.
4. **Seed integrity** — none of the above may override a team's earned seed.
5. **Travel** — among otherwise-equal options, prefer the shorter trip.

Each candidate bracket is scored by a penalty total (same-conference and repeat
matchups carry the heaviest penalties), and the lowest-penalty legal bracket wins.
Crucially, these are **bracket-construction** rules: they decide *placement*, never
*strength*. A team is never moved up because it won a conference, nor down because
it was an at-large pick.

---

## In one sentence

We pick the field on merit and bids, rank it on strength alone, and only then draw
the bracket to make the best, freshest matchups — three questions, three answers,
never crossed.
