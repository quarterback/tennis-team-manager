# The press desk — design notes and style corpus

Status: design + research. No generator exists yet.

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
- **Facts first, prose second.** A deterministic extractor builds a fact sheet per
  story from the archive (who, score, flight results, records, streaks). A writer
  turns the sheet into prose under a style policy. Any name or number in the prose
  must be on the sheet. This is the split `quarterback/pbbg-content-schema` already
  makes between game definitions, narrative and interface text.
- **Storyline memory.** A ledger of open threads (an unbeaten run, a sibling pair, a
  new head coach's first year, a transfer facing an old school) that later editions
  pick up and close.
- **A sidecar, not a page of the game.** It reads a game's database or research
  export read-only, the way `analytics/` and the baseball game's `o27audio` do. Each
  game supplies an adapter that emits ordered events; editions, threads, the writer
  and the reader are shared, so viperball and the baseball game can use it. The
  `/jhsaa` front page keeps its rule of no generated prose.

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

## Open questions

- Coach quotes. Real prep stories lean on them and the sim has none. Named coaches
  carry rated attributes and philosophies a quote could be generated from; that is
  an owner decision, not a default.
- Template-only prose or a model as the writer (run as a batch job and stored).
- About 5% of varsity duals carry no display date; they need an edition rule.

## The corpus (`corpus/`)

The generator is only as good as its ear, so the first step is a corpus of real
prep-sports writing from roughly 1980-1999, all sports, tennis weighted, many states,
small-town papers first. `corpus/BRIEF.md` is the collection method and the record
kept per article. The repo holds annotations, short quoted excerpts and source
links. Full article text is not committed: the articles are other people's
copyrighted work.
