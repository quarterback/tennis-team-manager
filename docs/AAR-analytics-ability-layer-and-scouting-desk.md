# AAR — The Clinch Report: the ability layer, the scouting desk, and sunsetting storylines

**When:** 2029-08 · **Scope:** `analytics/` only — the game is untouched
**Owner ask:** "the /analytics tool contains a bunch of stats that are hard to parse,
have limited value at this point… I'd like to be able to understand player value, to
evaluate classifications if it's possible" — and, on the third point, "a tool that
precisely does what I've been doing with the agents and the app already, which is
identifying different kinds of transfers; we don't just find one kind."

---

## 1. The thing that was actually wrong

The sidecar had ~70 metrics and **not one of them touched OVR**.

S%, D%, RCI/SCI/Fmt, Doubles Reliance, the state-card win probability, PVAR, Record
Luck, Upset Value — every one measures an OUTCOME. The win-probability model behind
Record Luck runs on **TOSS**, which is an opponent-strength composite and correlates
with strength at about 0.76. The match engine reads exactly **one** number: a player's
current overall.

So the library modelled the engine's output and ignored its only input. It could
describe what happened in enormous detail and could not answer the one question a
roster pass asks — *did this team do better or worse than its players say it should
have?* That is not a missing metric, it is a missing **layer**, and everything the
owner wanted (player value, classification comparison, transfer candidates) turned out
to sit on top of it.

**The general lesson:** a library can be internally consistent, well-documented,
extensively tested and still be measuring the wrong side of the system. Check what the
simulation READS, not just what it emits.

---

## 2. ‼️ No export change was needed, and checking that first changed the design

The brief that came in proposed adding `home_ovr`/`away_ovr` to `lines.csv` —
"cheapest by far". It would have worked, and it would have been the wrong call:

- `players.csv` has carried `current_grade` since the export existed.
- **Within a season a player's OVR is CONSTANT** — development lands at the rollover —
  so a season's value is not an end-of-year snapshot standing in for the real thing,
  it IS the number every dual that season was played at.
- `lines` → `line_players` → `players` is therefore an exact join, not an approximation.

The difference is not elegance. The owner has **nine seasons of exports already
downloaded**. A schema change means re-exporting all of them; a join at ingest means
every zip on disk gains the whole ability layer with nothing re-run. **Check whether
the data you want is already derivable before asking the producer for a column.**

---

## 3. ‼️ The win curve is FITTED, never copied

The brief supplied a measured table (favourite wins 50% at a 0–1 gap, 61.8% at 3–5,
73.6% at 5–8, …) and it was tempting to hard-code it.

`ability.py` fits a two-parameter logistic on the ingested flights instead, one curve
per (family, singles/doubles), and **publishes its observed bands beside the fitted
ones on the page**. The bands are the receipt: if the fit and the observation disagree,
the observation wins and the model is broken.

Three reasons, all of which have precedent in this repo:

1. The engine's gap response has been retuned before (the hinge/knee work). A copied
   table describes whichever build it was measured on and goes stale **silently** —
   exactly the failure `aggregate.Bundle.regular_shape`/`state_shape` exists to avoid,
   and exactly what `rating.FLIGHT_WEIGHTS`'s `.get(slot, 0.3)` default did in the game
   for a release.
2. Doubles is measurably steeper than singles at the same gap. One shared curve
   under-calls favourites in doubles and over-calls them in singles.
3. Fitting pools every ingested season, because the curve is a property of the ENGINE,
   not of a season — which is also what makes it well-determined off a single export.

Same rule applied to the development curve. An earlier pass wrote down
0.7/3.6/5.8/6.8/7.6 gain per headroom decade from one year pair; the game's development
model has since been rebuilt and is **era-gated by entry year**, so those constants
describe one era and mis-score every other. `market.fit_growth` refits them.

**Rule: if a number describes the simulation's behaviour, derive it from the data. A
constant in the analytics tool is a claim about a version of the game.**

---

## 4. ‼️ A mismatch is a FACT, not a problem — which is why there are four finders

The first instinct is one list: "players whose ability doesn't match their playing
time". That answers nothing. A 67 OVR at No. 1 singles for a terrible team is a
perfectly ordinary thing to be — it is their school, they like being the star. What
makes a move interesting is a **pull somewhere else**, so every finder reports the pull
rather than the mismatch, and the four kinds are genuinely different questions:

| Finder | Who | Where the move goes |
|---|---|---|
| **Buried** | outside the lineup, above their own class's median starter | across |
| **Reservoir** | returning, barely played, below that line now **and at their ceiling** | down |
| **Stranded** | top-decile in class, top three on their ladder, bottom-third program | out |
| **Cohort builder** | everyone in a destination's county/area, with the slot each would take there | together |

Two derived columns carry most of the weight, and both are read off the season rather
than assumed:

- **`starts_in`** — the strongest classification whose median starting line a player
  clears. That single number IS the cascade decision.
- **`vs_starter` / `pot_vs_starter`** — how far above/below a median starter of their
  own class they sit, now and at their ceiling.

‼️ **The ceiling test is what separates Buried from Reservoir.** Drop it and the two
collapse into one list under two names: a good player having a quiet year should move
ACROSS, a player who will never start here is the cascade. Measured on the real 2030
boys season: Buried 22, Reservoir 1,022, Stranded 276 — three different populations.

---

## 5. ‼️ Geography had to be a TOP-LEVEL axis, and that fought a standing rule

The section's organizing rule is **classification → district on every page, list and
menu**, and it is right for a competition. It is the wrong index for a market. The
owner: *"there's nowhere for me to search kids by area."* A cohort build is "the best
players within one county", and a class-first tree makes that query unaskable — you
would walk nine class pages and re-filter each one.

The resolution was not to break the rule but to notice what it protects: **never render
a statewide splat.** The scouting search carries BOTH cascades (area → county → town,
and class → league) over one list and narrows on whichever the question uses, renders
nothing until an axis is set, and draws at most 400 rows with the total stated. You
never see the whole association; you just get to enter it from the other side.

That also forced the page shape. One HTML page per (scope, classification) would have
made a geography query span nine files, so the season's players ship as a **packed JS
array** rendered client-side: 15,113 players and 777 programs is 1.7 MB, parsed in
~255 ms, with filters at ~200–500 ms.

---

## 6. ‼️ No silent caps — the finders shipped capped and it looked completely fine

The first version kept the best 60 candidates per classification, reasoning that the
page is a worklist and the whole population lives on the grid. On real data the
Reservoir list rendered **533** and the true number was **1,022**. Nothing was wrong on
screen; the page simply read as "these are the candidates" while being "these are 60 of
1,022", and there was no way for a reader to tell.

The finders now return everything that qualifies. The only limit is the grid's display
cap, which **announces itself** ("showing the first 400 — narrow the search").

This is the game's own no-silent-caps rule one level up: **if a workflow bounds
coverage, the bound has to be visible, or truncation reads as completeness.**

---

## 7. ‼️ Two faults that only a browser could find

The scouting desk is almost entirely client-side. `pytest` renders the HTML and asserts
on the text, which proves the template ran and proves nothing about whether the page
works. Driving it in Chromium (`playwright-core` against `/opt/pw-browsers`) found two
real defects on the first run:

1. **The JSON payload was HTML-escaped inside `<script>`.** Jinja's autoescape turned
   `"` into `&#34;`, and **script content is raw text — the browser does not decode
   entities there** — so `JSON.parse` would have thrown on a page whose source looked
   perfectly correct. Fixed by escaping only `<`, `>`, `&` as `\uXXXX` in Python (still
   valid JSON, still safe against a `</script>` inside a school name) and marking the
   template expression `|safe`. The comment saying why is load-bearing: the next reader
   will see `|safe` and want to "fix" it.
2. **`.pt-star` is `position: absolute`**, because its first home was the corner of a
   team CARD. In a table row every star stacked into one corner of the nearest
   positioned ancestor; the rest rendered, looked fine, and did nothing. (The team page
   had been carrying an inline `position:static` workaround for exactly this, which is
   the tell nobody read.) Fixed with a `.pt-star-inline` variant.

Both are the template-layer version of the game's own rule: **the wrong type or the
wrong position renders a page instead of raising.** Anything a browser has to execute
must be checked by executing it.

---

## 8. ‼️ The fixture made three finder tests pass while measuring nothing

The original synthetic season gave **every school the same six players** (`40 + i`).
Consequences, none of which produced a failure:

- Every flight was contested at a gap of exactly **zero**, so the win curve was
  undefined and every expected-share number was .500.
- `_lines` wrapped with a modulo, putting the same player on two flights of one dual
  and leaving **no bench at all**.
- Ability and team strength were the same variable, so a strong player on a weak
  program could not exist.

Result: Buried 0, Reservoir 0, Stranded 0 — and `test_scouting_carries_the_four_ways_in`
passed, because it asserted the CONTROLS existed. The fixture now varies OVR per team,
gives two programs a deep roster and two weak programs a star, dresses distinct
players, and plays a second season with a transfer. `test_every_finder_actually_finds_
somebody` exists so this cannot silently return.

**An empty-state test cannot see a page — and a uniform fixture cannot see a
distribution.** If a feature's whole job is to find a shape in the data, the fixture
must contain that shape, and something must assert it still does.

---

## 9. What the classification report actually said

Worth recording, because it is the first time the question has been answerable, and
both answers hold up. From the 2030 boys season:

- **Cross-class, head to head:** the ladder is monotone (9A .634 overall down to 1A
  .270), but **9A vs 8A is 117–108 and 8A vs 7A is 79–77** — the top three classes are
  effectively indistinguishable. The real steps are 7A→6A, 6A→5A, 4A→3A and 2A→1A.
  6A beats 5A **106–77**.
- **The talent shape is holding.** No. 1s span 7.6 points across all nine classes
  (57.8 → 50.2); No. 11s span 16.5 (38.0 → 21.5); and the No. 1→No. 11 drop RISES as
  classes shrink (19.8 in 9A → 28.7 in 2A). That is the design's thesis — the top ends
  converge and enrollment buys depth — measured in a live world after nine seasons of
  hand transfers, not at generation.

‼️ **It has to be measured on court.** League play is inside a class by construction,
so the classes meet in non-district play and nowhere else. Comparing two classes' TOSS
would compare how each class rates *itself*, since the index is opponent-adjusted
inside a nearly self-contained schedule. A per-classification export therefore cannot
answer this at all, and the page says so rather than rendering an empty grid.

---

## 10. Storylines: sunset, function included

Owner: *"useless, can be sunset entirely."* A 2028 pass had already deleted the page and
left `metrics_mod.storylines()` running on every build, writing a JSON file nothing
read. This pass deleted the function.

The reason is structural, not a matter of presentation: **auto-flagged extremes sorted
by how extreme the number is tell you a number is unusual and never why.** The Cortland
case — a 9A title won with the 8th-best top-9 ability in the class — needed
flight-by-flight OVR gaps and a look at how the doubles pairings were arranged. No
threshold detector was going to surface either. The Scouting desk, the classification
report and the Talent view replaced it, and each answers a question somebody asked.

`test_storylines_are_gone_entirely` asserts the page, the JSON and the function are all
absent, because "computed every build, rendered nowhere" is what the previous removal
left behind.

---

## 10b. Review follow-ups — three faults the first pass shipped

**‼️ THE ABILITY JOIN WAS ONLY VALID FOR JHSAA, AND NOTHING SAID SO.** §2 above
is right that the OVR join needs no export change — for JHSAA. It is wrong for
college, and the first pass applied it to every ingested scope. A college
export's `players.csv` is TODAY's roster: `research_export.build_college` says
"Player and program fields reflect the CURRENT roster/program config … not a
per-season historical snapshot." Three silent consequences, only the first of
which was reported:

- the ability join priced old flights at LATER OVRs, and dropped every flight
  whose players had since graduated — so the curve trained on a biased
  subsample with the wrong x-axis;
- `fit_growth` diffed one roster against itself and reported a one-year gain
  of ~0;
- `movement` saw every player at their CURRENT program in every season and
  concluded nobody had ever transferred.

The owner settled the scope question directly — "the analytics tool has nothing
to do with the college game at all" — so the fix is a GATE, not a college code
path: `aggregate.Bundle.roster_is_snapshot`, with `snapshot_bundles()` as the
accessor, and the Scouting and Classifications indexes NAME what they excluded
rather than rendering a quietly shorter list. It also disposes of a fourth
finding for free: no college scope gets a Scouting page, so no college batch is
ever offered to `/editor/jhsaa-transfer-batch`, which resolves ids through the
girls'/boys' rosters alone and would reject every row.

**The lesson generalises past this repo:** "the join is exact" was a property
of ONE producer, and I wrote it in the commit message as though it were a
property of the export format. Before building on a table, read what its
producer says the table MEANS — `build_college`'s docstring stated the problem
in plain English and had done all along.

**‼️ A SYMMETRY TRICK IS NOT EVIDENCE.** The curve is fitted on both sides of
every flight so it is symmetric about a zero gap — correct as a modelling
choice, and a mirrored row is still the SAME flight seen from the other bench.
The mirror was added in `fit_curves` and then again inside `_fit`, so
`MIN_FIT_SAMPLES` was satisfied at half the stated evidence and every count the
page reported — including each observed band's `n` — was double the truth. The
mirror now lives in `_fit` alone and `samples` is the real flight count; on the
2030 boys export the two curves report 41,912 + 30,008 = 71,920, which is
exactly the number of rows in `lines.csv`. **Reconcile a reported total against
something countable from outside the module** — the doubling was invisible for
as long as the only check was that the curve looked plausible.

Fixing it also revealed that the corrected bands land on figures measured
independently before this tool existed (singles .491 at an even gap, .734 at
5-8, .889 at 8-12; doubles steeper at the same gap, .803), which is the
validation the fitted-not-copied decision in §3 was hoping for.

**‼️ TWO HAND-MAINTAINED LISTS OF THE SAME THING DRIFT.** `anyFilter()` decided
whether the grid renders, `resetFilters()` decided what gets cleared, and both
enumerated the control ids by hand. `f-ovrmax` and `f-mmax` were in the second
and missing from the first, so setting only "OVR max" — or only "Matches max",
which is exactly how you ask "who never played" — left the results panel hidden
and the control appeared to do nothing. Both now read ONE list. When a
predicate and a reset walk the same set, derive them from a single declaration;
the bug is not the two missing entries, it is that there were two lists.

## 11. Standing traps carried over (still live)

- **Join on `program_id`, never a display name.** ~300 of 1,644 programs have been
  renamed across the archive, and an id often matches neither the old name nor the new.
- **`classification` is enrollment; `championship_group` is who they play.** Six
  programs differ, two by four classes. Every competitive comparison keys on the group.
- **Departures are read from the season a player turns up in**, so the newest ingested
  season reports **unknown, not zero** — a program that lost seven and one that lost
  none must not print the same number.
- **Freshmen and seniors are not movement.** A player absent from either side of a year
  pair is a player the export does not cover.
- **The shortlist is `localStorage`** — browse over `http://localhost`, not `file://`,
  for the same origin-partitioning reason as My Teams.

## 12. Vocabulary

A player plays **matches**, at a **flight** / position / line, in a **dual**. A *court*
is the physical surface: "courts played" is wrong and so is "the D3 court" (it is the
No. 3 doubles flight). Aggregates are **flight share**. The older "court share" wording
survives in `metrics.py`'s tier-1 metric names; fixed in the surfaces this pass touched
rather than swept, the same way the game repo handles its own "card" problem.
