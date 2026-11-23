# The press desk — design notes and style corpus

Status: researched house voice, annotated corpus and reusable editorial rules.
A first JHSAA-specific writing adapter is implemented in `app/jhsaa_paper.py`
and can be used from the game or the CLI. There is not yet a generic
multisport publishing runtime.

## The problem (owner, 2026-11)

A JHSAA season is simulated whole at week 0 and the college season is advanced by a
button, so the owner meets a season as an engine report after the fact. The ask is to
experience it as a reader: a 1990s local paper that still staffed high-school sports,
with running coverage of programs, players and storylines.

## Shape

- **Reading order, not a calendar.** A paper is a sequence of editions. Each edition
  sees only what has happened so far in the season's order of play. Dates inside a
  story can be invented, as long as they fall inside the season (owner: "the
  newspaper could just make up a date").
- **The record is fixed; colour is invented and remembered (owner rule, 2026-11).**
  "This is all invented, writing counterfactuals is perfectly reasonable ... if we
  say x kid has a brother he always does." Two stores feed a story:
  - the RECORD, read from the game: scores, flights, standings, streaks, honours,
    rosters, coaches, family ties the sim already has. Never contradicted.
  - the CANON, written by the press itself: every invented detail a story prints
    about a person, a program or a place (a quote's gist, a nickname, a pre-match
    habit, a parent who is an alum, the state of the home courts). Keyed on the
    game's stable ids, dated by edition, and read back before anything else is
    written about that subject.
  A writer may add to the canon and may leave a detail unused. A writer may not
  print something that disagrees with either store. Where the game later produces a
  real fact (a sibling tie, a transfer), the record wins and the canon entry is
  retired.
- **Storyline memory.** A ledger of open threads (an unbeaten run, a sibling pair, a
  new head coach's first year, a transfer facing an old school) that later editions
  pick up and close.
- **Shared editorial logic, flexible delivery.** The JHSAA proof of concept
  reads the archive without changing the simulation, writes editions through an
  optional agent/API step, and shows the paper in the existing game UI. It also
  supports a CLI and research-export workflow. A later cross-game adapter can
  consume ordered events from tennis, Viperball and baseball without requiring
  a second interface or a manual ZIP export. The ordinary `/jhsaa` data front
  page keeps its no-generated-prose rule.

## Five voices

Several generators over one event pool, so nothing has to cover the whole state.

| Voice | Covers | Typical output |
|---|---|---|
| Local | one town's programs | every dual, every name, JV, senior night |
| Beat | one program, followed closely | lineup moves, role changes, the coach's season |
| Area | one area or league | roundups, the league race, athlete of the week, all-area |
| Statewide | the association | rankings, the title picture, state previews, all-state |
| Columnist | whatever the columnist chooses | opinion, notes, picks, tributes, a persona that recurs |

The same event appears at different sizes: a freshman's first varsity win is a local
story, a line in the area roundup, and absent statewide unless it becomes a streak.
Threads are shared, so the statewide desk can pick up what a beat writer has followed.
The columnist is the one voice allowed an opinion and a first person.

## Writers

A paper is several people, and the corpus shows them writing differently inside the
same old voice. So style has three layers, and a story is written from all three:

1. **The house voice** (`VOICE.md`): shared by everyone at every paper.
2. **The desk and story type**: sets length, order, whether there are quotes and
   whether it is signed. An unstaffed roundup has no author at all.
3. **The writer**: a small standing profile attached to a byline, which only changes
   choices the first two layers leave open.

A writer profile holds a handful of habits, each one seen in the corpus:

- lead habit: score-first, a conceit or pun, a one-line teaser, or a contrast
- sentence length and how long the nut sentence runs
- attribution: "said" only, or the rotating verbs
- quote appetite: one coach quote, or six to fifteen
- favourite verbs and nouns, and whether they pun in headlines
- what they notice: the deciding flight, seniors, families, the program's history,
  the numbers
- for a columnist only: the persona, first person, running devices and targets

Profiles are data, a few lines each, and a masthead has a small staff of them: a
sports editor who also writes the column, one or two staff writers, a stringer, and
"staff reports" for everything phoned in. A writer keeps the same habits all season,
which is what makes a byline recognisable.

## Open questions

- Quotes are invented (decided: yes). Open: how much of a coach's or player's way of
  talking is fixed in the canon after the first quote.
- Template-only prose or a model as the writer (run as a batch job and stored).
- About 5% of varsity duals carry no display date; they need an edition rule.

## The voice guide (`VOICE.md`)

The file another agent loads: story types, paragraph order, agate formats, the
desks, the decades, the columnist and how teenagers are written about. It states its
own gaps.

## The corpus (`corpus/`)

The generator is only as good as its ear, so the first step is a corpus of real
prep-sports writing from roughly 1980-1999, all sports, tennis weighted, many states,
small-town papers first. `corpus/BRIEF.md` is the collection method and the record
kept per article. The repo holds annotations, short quoted excerpts and source
links. Full article text is not committed: the articles are other people's
copyrighted work.
