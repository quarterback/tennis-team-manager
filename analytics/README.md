# The Clinch Report — analytics sidecar

A separate, static-site analytics tool that ingests Play to Clinch **research
exports** (`/research/export` in the game, zips with `manifest.json` +
`programs.csv`/`players.csv`/`duals.csv`/`lines.csv`/`line_players.csv` plus
JHSAA- or college-only files) and builds team pages, player career pages, and
a first-pass sports-analytics library out of them — styled to look like the
game's own design system, written like a state-desk beat outlet.

This tool never touches the game's database or app code. It only reads zips
you export and drop in.

## Running it

Everything operational lives in this section: setup, the everyday commands, how
to keep the build from filling your disk, and the end-to-end loop from a game
export to a pasted transfer batch.

### First time only — setup

The sidecar has exactly one dependency (Jinja2), and the game already pulls it
in via Flask. **Try running it before installing anything:**

```bash
cd analytics
python3 build.py
```

If that works, skip the rest of this subsection. If it errors on Jinja2, and
`pip install` refuses with *externally-managed-environment*, that is Debian and
Ubuntu's PEP 668 rule — make a venv:

```bash
cd analytics
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Once only. Afterwards it is `source .venv/bin/activate` then `python3 build.py`.
If `python3 -m venv` itself fails, `sudo apt install python3-venv` first.
`.venv/` and `venv/` are gitignored here.

### The three commands

```bash
python3 build.py                      # re-render from everything already ingested
python3 build.py path/to/export.zip   # ingest new/changed seasons, then re-render
cd site && python3 -m http.server 8000
```

**`build.py` with NO arguments rebuilds the whole site from the cache.** You
never need to re-pass a zip to pick up new features or a code change — pass one
only to add a season or replace one you re-exported. Re-ingesting a scope
overwrites it, so a re-export is a one-step fix.

Serving needs no venv (`http.server` is stdlib). Open `http://localhost:8000/`.

### ‼️ Browse over `http://localhost`, never `file://`

Not cosmetics. **My Teams** (the pin/star) and the **scouting shortlist** both
store their data in `localStorage`, and browsers scope that per ORIGIN — a
`file://` page has no real origin, so several browsers (Firefox in particular;
Chromium is inconsistent) give every `file://…/x.html` its OWN storage bucket.
Star a player on the Search tab and the Shortlist tab can come up empty even
though nothing failed: the write happened, it just did not land anywhere the
next page can see. A shared `http://localhost` origin is the actual fix, and
nothing inside a static page can paper over a browser storage policy. Browsing,
filtering and searching work fine either way — only the features that remember
things across pages need the server.

### ‼️ Ingesting and rendering are separate, and past ~10 seasons that matters

The CACHE is the almanac and costs a few MB of CSV a season; every season you
have ever ingested stays in `analytics/data/` whatever you render. The SITE is
what gets big, because it is O(seasons × entities):

| One season-gender, measured | |
|---|---|
| `players/` | **221 MB** · 13,506 pages |
| `teams/` | 25 MB · 778 pages |
| everything else | ~4 MB |
| **total** | **250 MB** |

Fourteen years of both genders is several GB and will run a disk out of space.
Two levers, and they compose:

```bash
python3 build.py --latest 2          # only the newest 2 years, per gender
python3 build.py --years 2038-2039   # or name them (2039 / 2038-2039 / 2031,2038-2039)
python3 build.py --gender boys       # one gender
python3 build.py --no-player-pages   # drop the career pages: 250 MB -> 27 MB
```

`--latest 2 --no-player-pages` is about 54 MB and is the practical default for
market work. The build prints the finished size and names any season it left
out, so a shorter site always explains itself.

**`--latest 2`, not `--latest 1`.** Movement and development are differences
between CONSECUTIVE seasons, so a single rendered season has no prior year to
diff against and every transfer and growth number is legitimately blank.
`--latest` counts years PER GENDER, not bundles.

`--no-player-pages` keeps every other surface — the scouting desk, the Stat
Center, the classification report, team pages, rosters and their ladders all
render. A player's name is simply text instead of a link, and the Players nav
item is dropped rather than left pointing at a 404.

Nothing is lost from the cache either way: re-run without the flags whenever you
want the whole almanac back.

### ‼️ Re-export any season taken before the JV fix

The JHSAA plays a JV season now, and for a while `duals.csv` carried JV duals
with nothing marking them (the 2039 boys export had 18,096 duals against 2038's
10,709). Those zips inflate every record, player total and program court total
if you ingest them, and this side cannot filter them out — they have no `level`
column, and "missing level" has to mean varsity or every pre-JV season would be
silently truncated.

**Re-export those seasons from the game and re-ingest them.** New exports carry
`duals.level`, this side filters to varsity, and the problem is gone:

```bash
python3 build.py ~/Downloads/*2039*.zip     # overwrites the bad cache entry
```

### The market loop, end to end

1. **Export** the season from the game's `/research/export`.
2. **Ingest + build**: `python3 build.py path/to/export.zip --latest 2 --no-player-pages`
3. **Serve**: `cd site && python3 -m http.server 8000`
4. **Scout** → pick the season → search by area/county/town or class/league, or
   click a preset finder (Buried / Reservoir / Stranded), or use the **Cohort
   builder** to pull everyone near one program.
5. **Shortlist** them with the ☆ on any row. The Shortlist tab holds them, with
   a **Destination** box per row and a **Fit** column showing the ladder
   position they would take there.
6. **Export the batch** — *Download batch CSV* or *Copy to clipboard*. The
   format is exactly what the game's bulk transfer field takes:

   ```
   15ea169de75a3fa3,Plainfield
   beeb50343e24e61a,Plainfield
   ```

   `player_id,DestinationSchool`, one per line, no header, LF endings.
   Destinations must match a program name exactly, accents included.
7. **Paste** it into the game's bulk transfer field. Transfers take effect the
   FOLLOWING season, so nothing shows up in analytics until you export that one.

Rows with no destination, an unknown program, or the program the player already
attends are held back from the export and reported rather than silently dropped.
The shortlist is per season and survives a rebuild.

### Where to look for what

| Question | Page |
|---|---|
| Who should move, and where | **Scouting** → Search / the three finders |
| Everyone near one program, to move a group together | **Scouting** → Cohort builder |
| Is 6A really better than 5A · is the talent shape holding · is a class healthy | **Classifications** |
| Did this roster underperform its talent | **Team Stat Center** → Talent view (xShare, Talent luck) |
| Who came and went, and what the arrivals were worth | a **team page** → Movement · or Stat Center → Movement view |
| Best careers on record | **Player Value** (PVAR beside WAE) |
| What the win curve is priced on | **Player Value**, bottom panel (observed bands beside fitted) |

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "No space left on device" | The site, not the cache. Use `--latest 2 --no-player-pages` (above). |
| `pip install` refuses, *externally-managed-environment* | PEP 668. Make a venv (above), or try running without installing — Jinja2 may already be there. |
| Shortlist looks empty after starring players | You are on `file://`. Serve over `http://localhost` (above). |
| In / Out / Net and Dev± are all blank | Only one season rendered. Movement is a diff — render at least two consecutive years. |
| A team's newest season shows `Out —` | Correct. Departures are read from the season players turn up in, and there is no following season yet. That is unknown, not zero. |
| A season's records look inflated | A pre-JV-fix export. Re-export and re-ingest it (above). |
| Cross-class table says "no cross-class duals in this export" | The season was exported for ONE classification. Re-export with classification "all". |
| Nothing renders / "none matched that selection" | Your `--years` / `--latest` / `--gender` filter excluded everything. The message lists what is cached. |
| No Scouting or Classifications page for a season | It is a college export. This is the JHSAA desk — see below. |

## Structure (owner rewrite ×2: 2027-08 nav, 2028-08 data organization)

‼️ **CLASSIFICATION → DISTRICT IS THE ORGANIZING HIERARCHY ON EVERY PAGE,
LIST AND MENU** (owner rule 2028-08) — the exact parallel of the college
game's division → conference. Nothing may ever render a statewide splat: the
first pass listed 861 teams in one standings table ranked on win% and seven
single-metric pages each dumping every (team, season) row statewide, and the
owner's verdict was "impossible to really parse and navigate." (An earlier
intermediate pass, 2027-08, had already moved off the original flat 1,600-
program/19,700-player dump toward cascading Season → Classification → League
pickers — that pass fixed the "no navigation at all" problem; this one fixed
"navigation exists but still dumps a statewide table per page.") The mental
model is **Football Manager / FMRTE**: dashboards with tabbed views, dense
sortable grids scoped by pickers, and entity pages that carry their own
stats in panels. Two corollaries, also owner rules from the same session:
**a player's grade shows in every list a player appears in** (JHSAA "12th" /
college class year, sortable — no clicking through to discover someone's a
senior), and **no tutorial help text** on the pages themselves.

- **Seasons** (`seasons/`) — one dashboard per exported season, four tabbed
  views of it: **Rankings** (class-first — the page opens on the biggest
  classification, statewide is an explicit option — ranked on the ARCHIVED
  TOSS power exactly like the game's own rankings page, win% only as the
  pre-TOSS fallback; every row carries class rank, state rank, district and
  district record/place), **District standings** (one panel per
  (classification, district), ordered on the archived district place — the
  association's own tiebreak ladder decided it, never re-derived),
  **Individual leaders**, **Awards**. Classification/district pickers +
  search filter all tabs.
- **Teams** — cascading Season → Classification → League pickers; the card
  grid renders only once a classification narrows it (or a search does).
- **Team pages** — the FM club screen: KPI tiles (record, district record +
  place, class rank of N, power + statewide rank), the schedule presented
  the way the game presents it (sectioned League play / Invitationals /
  Showcases / Road to State / State / TOC, real dates from the export's
  `duals.date`, vs/at, type chips — never raw phase strings — and
  winner-first scores per the game's scoreline convention), a roster with
  per-player grade + singles/doubles season records, and a Season analytics
  panel so a team's own metrics live on its page instead of seven league
  tables away. **JHSAA roster sizes are no longer flat** (owner rule,
  `ROSTER_SIZE_BY_CLASS`): they now scale by classification, 9A 24 down to
  1A 13, mirroring the college side's `roster_cap` pattern — don't read a
  shallow 1A roster next to a full 9A one as missing data, it's the format.
  Grade distribution is no longer an even ~3-per-grade split either (each
  class's freshman count is now rolled once per school/entry-year and ages
  forward), so a season's grade mix will look naturally uneven rather than
  symmetric.
- **Brackets** — the archived postseason draw per classification, straight
  from `jhsaa_championships.json` (was ingested and completely unused before
  the 2027-08 pass). Round labels use the export's own `round_names` field
  verbatim wherever it's present (`_round_names()` in `render.py`) — an
  expanded 40-team classification prepends "Qualifiers Round"/"First Round"
  ahead of a converged Octofinals-onward bracket, and those two rounds are
  NOT a continuation of the same single-elimination sequence as the rest,
  so they're never relabeled by distance-from-final the way the tail is.
- **Players** — search-only by design (a flat index at this scale is not
  useful); rosters are the real way in.
- **Scouting** (`scout/`) — one page per season; its own section below.
- **Classifications** (`classes/`) — one report per season, three tabs.
- **My Teams** — a star/pin button on any team card or team page, stored in
  the browser's `localStorage` (no server, no account) and surfaced on the
  home page, so you don't re-search your own team/league every visit.

### Schedule ordering: `duals.date` (export schema addition, 2028-08)

The JHSAA export now carries `duals.date` — the game's own display calendar
(`world.jhsaa_match_dates`, one date per dual, identical from both sides).
Without it the sidecar had NO play order for JHSAA (there is no clock inside
a JHSAA season) and fell back to export-file order, which lists a team's
home duals first and its away duals wherever the opponents' cards put them —
that's why every schedule read "Home, Home, Home…" down the page. Old zips
without the column still render (sectioned, card order within a section);
re-export a season to get real dates.

## What's here

- `teams/`, `players/` — entity pages as above; player pages stitch a career
  across every season ingested on the stable player_id, with the full match
  log (dated, type-chipped) and positions-played table.
- `seasons/` — the per-season dashboards.
- `metrics/` — the analytics library: ONE **Team Stat Center** grid
  (season → classification → district scoped, switchable column-group views:
  Shape / Format lift / Résumé / Depth & volatility / Predictive / **Talent** /
  **Movement**, every column sortable) plus **Player Value**. The seven
  separate single-metric pages of the first analytics pass are gone — a new
  metric is a new column (or view) in the grid, never a new page of everything.
- `scout/` — the **Scouting** desk, one page per season: a player search whose
  axes include geography, three preset finders, a shortlist, and a cohort
  builder. Its own section below.
- `classes/` — the **classification report**, one per season.
- **Storylines are GONE** (owner call 2029-08: "useless, can be sunset
  entirely"). The 2028 pass removed the page and left the computation writing
  `analytics/data/storylines.json` on every build; this one removed the
  function too. They were auto-flagged extremes sorted by how extreme the
  number was, which tells you a number is unusual and never why. Do not
  rebuild them — the Scouting desk, the classification report and the Talent
  view replaced them, and each answers a question somebody actually asked.

Design notes and the reasoning behind the sections below:
`docs/AAR-analytics-ability-layer-and-scouting-desk.md`.

## ‼️ This is the JHSAA desk

Owner, 2029-08: "the analytics tool has nothing to do with the college game at
all." College exports still ingest and still render the results-only pages they
always did, but **nothing ability-derived is computed from one** and there is no
Scouting or Classifications page for them. That is not only scope — it is what
the export says about itself. `research_export.build_college`: "Player and
program fields reflect the CURRENT roster/program config … not a per-season
historical snapshot." So a four-year-old college season lists TODAY's roster,
and reading OVR off it would price old flights at later numbers while silently
dropping every flight whose players have since graduated; a movement diff would
see everyone at their current program in every season and conclude nobody has
ever transferred. `aggregate.Bundle.roster_is_snapshot` is the gate and
`aggregate.snapshot_bundles()` the accessor; the Scouting and Classifications
indexes NAME what they left out rather than quietly rendering a shorter list.

The transfer batch is JHSAA-only for the same reason: its only consumer,
`/editor/jhsaa-transfer-batch`, resolves ids through the girls'/boys' rosters,
so a college row would be rejected as an unknown player.

## ‼️ Varsity only — the JV season shares one schedule table

The JHSAA plays a JV season now, and both levels are archived in
`world_jhsaa_dual`, so **`duals.csv` carries both**. Owner rule: JV never needs
to reach analytics. `aggregate.Bundle` filters to `level == "v"` at the one
chokepoint everything downstream reads through.

Left unfiltered a JV dual is not a cosmetic extra row: it inflates every record
derived from the schedule while `jhsaa_standings.csv` stays varsity-only, so a
team page's KPI record and its own schedule disagree — and
`_derive_card_shape`, which finds the varsity shape by counting lines per dual,
averages JV's elastic lineup into it.

**A missing `level` means varsity, not unknown** — seasons exported before the
JV season existed have no such column and every dual in one is a varsity dual.
And "carries no lines" is NOT a usable substitute for the column: that is also
what a varsity dual whose lines failed to record looks like, which is why the
export was given `duals.level` rather than this side being taught to guess.

## The ability layer — the one input the engine reads (`ptc_analytics/ability.py`)

Everything in `metrics.py` measures OUTCOMES, and its win-probability model
runs on TOSS. The match engine reads exactly one number: a player's current
overall. So the library modelled the output and ignored the only input, which
is why it could describe a season and never say whether it should have gone
that way.

`ability.py` joins `lines` → `line_players` → `players.current_grade`, so every
flight on record carries the OVR gap it was contested at. **No export change
was needed** — `current_grade` has always been in `players.csv`, and within a
season it is constant (development lands at the rollover), so a season's value
IS the number every dual that season was played at. That matters: every zip
already downloaded works, with no re-export.

What it produces:

- **A fitted win curve**, one per (family, singles/doubles). ‼️ **Fitted from
  the ingested flights, never hard-coded.** The engine's gap response has been
  retuned before, and a table copied in here would go stale silently — the same
  failure mode the derived `regular_shape`/`state_shape` exists to avoid, and
  the one the game's own flight-weight AAR is about. The curve publishes its
  OBSERVED bands beside the fitted ones on the Player Value page: the bands are
  the receipt, and if the two disagree the bands win the argument.
  Doubles gets its own curve because it is measurably steeper at the same gap.
- **xShare / Talent luck** per team — expected flight share against the share
  actually taken. This is Record Luck computed against the engine's input
  rather than against a rating, and it is the only thing on the site that can
  answer "did this roster underperform its talent".
- **WAE** per player — wins above what their own matches priced. It sits beside
  PVAR on the Player Value page and the two are *meant* to disagree: PVAR asks
  whether the seat was filled better than the next player would have filled it,
  WAE asks whether they beat the matches they were handed.
- **Ladder position** — a program's roster sorted on OVR, which turns the team
  roster panel into a depth chart and makes "where would this player slot in
  over there" a lookup rather than a model.

## Scouting (`scout/`) — the market desk

Modelled on Football Manager's search → shortlist loop, because that is the
loop the roster passes already ran by hand. One page per season, three tabs.

**‼️ GEOGRAPHY IS A TOP-LEVEL AXIS, not a filter under classification.**
Classification → district is the organizing hierarchy on every other page and
is right for a competition, but it is the wrong index for a market: a cohort
build is "the best players within one county", and a class-first tree makes
that query unaskable — you would walk nine class pages and re-filter each one.
The search therefore carries BOTH cascades over one list (area → county → town,
and class → league) and narrows on whichever the question uses. It still never
opens on the whole association: nothing renders until an axis is set, and the
grid draws at most 400 rows and says so.

**Several kinds of candidate, not one list.** A mismatch between ability and
playing time is a FACT, not a problem — a 67 at No. 1 singles for a bad team is
an ordinary thing to be. What makes a move interesting is a pull somewhere
else, so each finder reports the pull:

| Finder | Who | The move |
|---|---|---|
| **Buried** | outside the lineup, above their own class's median starter | across |
| **Reservoir** | returning, barely played, below that line now *and at their ceiling* | down |
| **Stranded** | top-decile in class, top three on their ladder, bottom-third program | out |
| **Cohort builder** | everyone in a destination's county or area, with the ladder slot each would take there | together |

The ceiling test is what separates Buried from Reservoir; drop it and the two
collapse into one list under two names. ‼️ **The finders are not capped** — an
earlier version kept the best 60 per class, which reads on screen as "these are
the candidates" while being "these are 60 of 1,022". Only the grid's display
limit applies, and it announces itself.

**The shortlist is the batch.** Star players, set a destination (with a live
"Fit" column showing the ladder position they would take there), and export
`player_id,DestinationSchool` — exactly what the game's bulk transfer field
takes, no header, LF endings. Rows with no destination, an unknown program, or
the program the player already attends are held back and reported rather than
exported. It lives in `localStorage`, so **browse over `http://localhost`, not
`file://`** (same reason as My Teams — see the top of this file).

**Two derived columns do most of the work.** `starts_in` is the strongest
classification whose median starting line a player clears — that single number
is the whole cascade decision. `lift` is their win rate minus their team's dual
win rate: the good-player-on-a-bad-team detector.

## Classifications (`classes/`)

Three questions about a class, as three tabs.

1. **Is 6A actually better than 5A?** Answerable on court and only on court:
   league play is inside a class by construction, so the classes meet in
   non-district play and nowhere else, and those duals are the entire evidence
   base. Comparing two classes' TOSS instead would compare how each class rates
   *itself*, since the index is opponent-adjusted inside a near-self-contained
   schedule. ‼️ A per-classification export contains one class, so the matrix
   is legitimately empty in one — the page says so rather than rendering a
   blank grid. Export with classification "all".
2. **Is the talent shape holding?** Mean OVR at each ladder position, per
   class. The design's claim is that the top ends sit close together and
   enrollment buys DEPTH, so the classes should fan out going down a lineup.
   Worth measuring in a LIVE world rather than at generation: the generator's
   guarantee says nothing about where talent ends up after nine seasons of
   hand transfers.
3. **Is the class healthy?** Spread across the top 16, how many different
   programs have won it, title concentration, and how often a dual is decided
   by one flight.

## Movement

Transfers were absent from the tool entirely, and every input was already in
the career stitch: diff `program_id` across consecutive seasons on the stable
`player_id`. On a team page that becomes In / Out / Net, who arrived and from
where, who left and for where, the share of the season's flight wins that came
from arrivals (a title built by arrivals and one built at home look identical
on a standings row), and development for arrivals vs stayers against the fitted
headroom curve.

‼️ **Departures are read from the season the player turns up in**, so the
NEWEST ingested season has nothing to read them from and reports unknown, not
zero — a program that lost seven and one that lost none must not print the same
number. Freshmen arriving and seniors leaving are never movement: a player
absent from either side of a year pair is a player the export does not cover.

‼️ **The growth curve is refitted, not copied.** An earlier pass wrote down
0.7 / 3.6 / 5.8 / 6.8 / 7.6 per headroom decade from one year pair. The game's
development model has since been rebuilt and is era-gated by entry year, so a
copied table describes whichever era it was measured in and mis-scores every
other one.

## Two traps that will bite any pass over this data

- **Join on `program_id`, never on a display name.** Roughly 300 of 1,644
  programs have been renamed across the archive, and an id often matches
  neither the old name nor the new one.
- **`classification` is enrollment; `championship_group` is who they play.**
  Six programs differ, two of them by four classes. Every competitive
  comparison here keys on the group (`aggregate.program_class`).

## Vocabulary

A player plays **matches**, at a **flight** / position / line, in a **dual**.
A *court* is the physical surface — "courts played" is wrong, and so is "the D3
court" (it is the No. 3 doubles flight). Aggregates over flights are **flight
share**. The older "court share" wording survives in `metrics.py`'s tier-1
metric names (RCI/SCI are documented as expected court share); it is fixed in
the surfaces this pass touched rather than swept, the same way the game repo
handles its own "card" problem.

## Analytics library

Past "are they good" (record / TOSS power) into "how are they good," "is this
record lying," and "what happens when the postseason card changes." Every
derived number is computed from stored components (S%, D%, per-flight
win rate, opponent power) rather than baked in, specifically so a metric can
be reproduced or challenged rather than trusted blind — see
`ptc_analytics/metrics.py`.

First pass:
- **S% / D%** — singles/doubles line win rate, the foundational split.
- **RCI / SCI / Fmt** — expected court share under the regular-season card vs
  the state/postseason card, and the gap between them in percentage points.
  A team with a big positive Fmt is a different, more dangerous team once the
  postseason format kicks in.
- **Doubles Reliance / Balance** — team shape in one number.
- **State Dual Win Probability** — modeled chance of winning a neutral
  postseason-shaped dual (needs a majority of that card's lines),
  independent-court binomial approximation.
- **Opponent-power quartiles, league vs non-league split, close-match
  record** — résumé questions: who are they beating, is the record padded.

Second pass, added the same session as the first: Format Dependency, Format
Win-Probability Lift, State score profile / three-court / sweep probability,
Expected State Margin, Dominance Margin, split singles/doubles game share and
set share (JHSAA only — college's export has no set-level detail), Line
Conversion, per-flight win-rate curves feeding Top-End/Depth/Star-Dependence,
Singles/Doubles Depth Slope, Floor/Ceiling, Blowout/Resistance rate, and a
crude auto-scaled power-based win-probability model (logistic on TOSS power,
scaled to that season's own spread) driving Expected Record/Record Luck,
Upset Rate/Value, Bad-Loss Value, and Elite Win Share. Plus a first-cut
**Player Value Above Replacement (PVAR)**: for every slot a player logged 3+
matches at, replacement level is the 25th-percentile win rate among other
players at that same slot/season; PVAR sums (actual − replacement) × matches
across every slot and season — deliberately not split by singles/doubles, so
it answers "how much was this player actually worth" rather than restating
S%/D%. All of it now lives in the Team Stat Center grid / PVAR page (see
"What's here" above), not the original separate pages.

‼️ Card shapes (how many singles/doubles lines a "regular" or "state" dual
plays) are **derived from the actual exported duals per scope**
(`aggregate.Bundle.regular_shape`/`state_shape`, the most common line-count
shape seen in each phase/round bucket), never hard-coded — an earlier
version hard-coded JHSAA's regular card as 5S/2D, and the game swapped that
to 3S/4D in the same session this was built, which would have silently
rendered every Fmt/RCI/SCI number backwards. `Fmt`/`SCI`/State Win% return
`None` (rendered "—") when a scope has no duals in that phase/round bucket
yet — currently that's most college scopes (their postseason `NCAA` round
isn't in the sample export), not a family-level restriction anymore.

**A note for JHSAA seasons exported after the format swap**: the game's
regular-season card is now 3 singles/4 doubles (was 5S/2D — the early
non-district window now plays the old 5S/2D shape instead, a straight
swap). Nothing in this sidecar hard-codes either shape (see above), so no
code here needed to change for the swap itself. What it does mean for
reading the numbers: under 3S/4D the S2/S3 lines are a team's *weakest*
two starters (the doubles pool takes the real #2-#9), not its 2nd/3rd
best — the opposite of what they meant under 5S/2D. Keep that in mind
comparing a player's S2/S3 stat line across seasons exported before vs.
after the swap; this sidecar reports raw per-slot performance and doesn't
attempt to normalize across the swap. Award data ingested from
`jhsaa_awards.json` already reflects the game's own post-swap reweighting
(regular-season S2/S3 down-weighted relative to doubles in selection) —
see the game repo's `docs/AAR-jhsaa-awards-3s4d-format-swap.md` if you
need the mechanics.

The full wishlist (opponent-adjusted S+/D+, bracket equity simulation,
player WAR, pair chemistry, trend/form ratings, and the rest) is not built
yet — this first pass is the substrate everything else in that list gets
computed from. Add new metrics as functions against `TeamMetrics`/`Bundle`
rather than a fresh ad-hoc pass over the raw tables.

Tests: `python3 -m pytest analytics/tests -q` (from the repo root) runs
data-bearing coverage — a synthetic multi-class season is pushed through the
GAME's own export builder, ingested, rendered, and the assertions read the
HTML (an empty-state test cannot see a page; that lesson is the game's own).

## Design system

Colors/typography are ported from `app/web/static/css/tokens/{colors,
typography}.css` — same token names and default ("Ensign") palette values,
so a future pass can wire in the other nine schemes without touching
component CSS, same as the game does. Component classes (`.pt-panel`,
`.pt-kpi`, `.pt-table`, `.pt-crest`) mirror the game's `.bl-panel`/`.al-kpi`/
`.bl-protable`/`.bl-crest` patterns rather than reusing them directly, since
this is a standalone static site with no server and no access to the game's
font files.
