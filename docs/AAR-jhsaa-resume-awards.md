# AAR — JHSAA postseason awards: résumé selections and a Honors page

## The report

Two things, from the owner:

> "The All-State Teams need to grow and you need to have a page/tab for honors
> that shows that so it can be archived YoY along with team pages and such."

and, on finding the awards scattered across the hub and program pages:

> "there needs to be a page for this stuff so i can actually see them, right now
> it's kind of scattershot where POY is and such."

Plus a full SOP: the awards must be **résumé selections**, not an ability
leaderboard.

## What was wrong

`season_awards` sorted every player by `(-wins, -pct, -ovr, name)` and took the
top **six** for All-State and six per district. Three separate problems:

1. **Too small.** ~500 programs, ~10-12 schools per district, six honours.
2. **The wrong question.** OVR was the tiebreak, so the awards partly measured
   ABILITY. Worse, `-wins` led — a win TOTAL measures opportunity, so doubles
   players (who are credited on both sides of a pair) and rotation regulars
   banked wins faster than a number one playing the hardest opponent every week.
3. **No home.** POY and a six-name All-State list lived in a rail panel on the
   hub; All-District only ever surfaced one school at a time on program pages.
   There was nowhere to see who the association had honoured, and no way to page
   back through past seasons.

## The evidence layer (the actual precondition)

None of the SOP's criteria could be computed from what was stored. `TeamSeason`
held `records[pid] = [w, l]` and nothing else — no opponent, no flight, no
phase. "Who did you beat, from which court, and when" had no answer.

`_credit` now logs every appearance as a tuple —
`(slot, won, phase, opp_pids, partner_pid, opp_school)` — on
`TeamSeason.matches`. Tuples rather than dicts because a gender's season
produces ~100k of them. **This is the load-bearing change**; the scoring model
is replaceable, the evidence is not.

## The model (`app/jhsaa_awards.py`, its own module)

Two passes, because opponent quality is circular:

1. **Base** — a Laplace-shrunk win rate per player per discipline. Crude on
   purpose; it exists only to give pass two something to weigh opponents by.
2. **Résumé** — signed credit accumulated per match:
   `weight(flight) × phase_weight × (WIN_BASE + WIN_SLOPE × opponent_quality)`
   for a win, minus `max(0.05, LOSS_BASE − GOOD_LOSS × opponent_quality)` for a
   loss. That single expression carries five of the SOP's criteria at once:
   record and volume (it accumulates), position (`FLIGHT_WEIGHTS` — the
   association's own table, so #1 singles and #1 doubles carry the most),
   opposition and quality wins (the `q` term), good losses (a loss to an elite
   player costs almost nothing), and postseason (`PHASE_WEIGHT`).

Head-to-head is applied afterward, and only inside `H2H_BAND`: it reorders
candidates already level on everything else, so one match never erases a season.
Doubles is scored in its own pass over doubles lines only, and a player who
partnered around is judged on the body of the work rather than an invented
permanent partnership (the most frequent partner rides along for display).

Nothing in the module reads OVR, talent, potential, class year, or last season.

## Shape (all owner-specified, several by correction mid-build)

- All-State **First / Second / Third**, plus a **Fourth in 7A**.
- Every All-State team is **10 singles + 8 doubles** — *the same size as an
  All-District team.* (First built as a 5+4 "lineup card"; corrected.)
- One **All-District team per district**, same size, plus a **District POY**.
- **State POY** per classification — best résumé in either discipline.
- All of it in **one pass** off the same completed season; there is no district
  vote feeding a later state vote.

## ‼️ Honorable Mention is a THRESHOLD, not a team

The SOP is explicit: no fixed number, size varies with how deep the
classification actually was, and a good season can miss it entirely. The cutoff
is measured against the numbered teams' **own spread** (`HM_DROP` below the
weakest numbered selection), because résumé credit scales with how much tennis a
classification played — an absolute number would mean something different in 7A
than in 2A-1A.

**The bug this section exists for:** the first attempt paired a loose threshold
with a tight runaway guard, and the guard bound in every classification. HM came
out **a flat 27 everywhere** — a fixed-size team wearing a threshold's clothes,
which is exactly the thing the rule removes. It looked fine (27 is a plausible
number) and only a per-classification comparison exposed it.
`test_honorable_mention_is_a_threshold_not_a_fixed_size` now fails if every
classification reports the same count, and separately asserts the guard is not
binding.

Measured through the shipped path after tuning — boys 7A 30 · 6A 11 · 5A 7 ·
4A 9 · 3A 18 · 2A-1A 7; girls 7A 19 · 6A 9 · 5A 11 · 4A 11 · 3A 14 · 2A-1A 15.
Different by class, by gender, and by season, which is the point.

**Max two per school, and that cap is HM-ONLY.** The numbered teams stack a
school as high as its résumés earn — four from one school measured in 7A, 6A and
4A. Nothing backfills a place vacated by a school's third HM candidate, because
HM has no quota to fill. Two tests hold the two halves apart.

## The page

`/jhsaa/honors`, a tab beside State / Bracket / TOC / Rankings / Districts. POY
hero, then each numbered All-State team, then Honorable Mention, then the
districts as folds (a classification has ten-plus of them and each team is 18
players — an unrolled page is enormous). Rows show the résumé — name, school,
discipline, record — and deliberately carry **no ability column**, which is the
page making the same argument the model does.

It reads from the archive, so an old season shows exactly what it awarded at the
time. `world.py` archives the tiers, HM and district POYs; the flat `all_state`
list stays for seasons archived before the tiers existed, and the readers fall
back to it.

## Traps for later

- **The size of an HM group is an OUTPUT.** If a change makes every
  classification honour the same number, a slot count has crept back in.
- **Never add ability to the ranking.** Not as a tiebreak either — that is how
  the old model justified itself. Ties break on match volume, then name.
- The school cap belongs to HM alone. Applying it to the numbered teams would
  quietly cap a genuinely dominant program.
- `FLIGHT_WEIGHTS` is shared with TOSS. Changing it to tune awards would move
  team seeding too; add a table rather than retune that one.

---

# Addendum, 2027-08 — pairings, structural flight, and a page that could be read

Three owner corrections landed on top of the SOP above, plus one bug the first of
them uncovered. All four are in `app/jhsaa_awards.py`,
`app/web/templates/jhsaa_honors.html` and `app/jhsaa.py::run_season`.

## 1. Doubles honours go to PAIRINGS, not to individual doubles players

> "oh i realize you crewed up doubles has to be DOUBLES PAIRINGS / not INDIVIDUALS
> WHO PLAYED DOUBLES"

The first implementation ranked every player's *doubles record* and put the top
eight individuals into the doubles half of a team. That is a real thing some
selectors do and it is not what the JHSAA does: **"eight doubles" means eight
doubles TEAMS — sixteen athletes.** A doubles honour describes a partnership, so
the partnership has to be the candidate.

What changed:

- **Two candidate entities, not one.** `_collect` builds PLAYERS (singles);
  `_pairs` builds PARTNERSHIPS keyed on the sorted pids. A pair's résumé is only
  the matches those two played **side by side** — never a doubles record
  accumulated across a season of different partners.
- **Pairs are rated against PAIRS.** `_base_pairs` / `_q_pairs` look the
  opposition up by the *opposing pair's* key, taken from the two opponent pids
  the match log already carried. Head-to-head is pair-vs-pair (`_h2h_pairs`).
- **Both halves of a match are logged once.** `_credit` appends the same match to
  both players, so `_pairs` takes each one from the higher pid's side only. The
  key is the sorted pids, so the two members can never disagree about the
  partnership's identity.
- **Partners rotate in this format, so one player is several candidates.** The
  regular-season card puts a program's #5–#9 into different pairs week to week;
  `MIN_PAIR_MATCHES` (6) is what separates a partnership from two people who
  happened to be put together. Measured: ~120–180 partnerships per classification,
  of which ~50 clear the threshold.
- **No athlete twice on one team, in either direction.** `_take` carries a `used`
  set across both halves of a team. The owner's earlier "if for some reason this
  happens, it's okay" about a player holding a singles *and* a doubles slot was
  explicitly reversed here, so it is now impossible — see §1b.
- **The HM cap counts ENTRIES, not athletes.** A pairing is one selection against
  the two-per-school cap even though it honours two people.
- **A row names two people.** `pids` / `names` are parallel lists of length 1 or
  2; `pid` / `name` stay populated (`name` is `"A / B"`) so older readers keep
  working. Every "was this person honoured?" lookup goes through `row_pids` —
  `honors_for`, the school page's badge map, the tests. **Matching on `row["pid"]`
  credits half of every pairing**, which looks completely correct on the page it
  is on and simply loses the partner everywhere else.

### 1b. Which category an athlete is considered in is a FACT, not a comparison

The owner's rule was "singles vs doubles category choice by actual participation".
So `_primary_discipline` decides it from the match log — mostly-singles seasons are
singles candidates, mostly-doubles seasons are doubles candidates, ties to singles
— and NOT by taking whichever of two résumés scored higher. Two things fall out of
that for free: no athlete can be in both halves of one team, and the doubles pool
stops containing singles players. That second one matters more than it looks: the
1S/4D postseason format puts nearly every singles player into a pairing for a
handful of duals, and those are not doubles teams — they are singles players
covering a card.

### 1c. A team can only be as large as the candidates who cleared the bar

> **Superseded in scale by Addendum 2** — the region teams that were coming up
> short were the symptom of a deeper error, not a pool problem. Kept because the
> RULE still holds; the measurement no longer does.

A four-school region (the `MIN_REGION_PROGRAMS` floor) has ~20 doubles-primary
players and ~9 partnerships over the threshold; eight DISJOINT pairs is not always
available. Such a region crowns seven pairs rather than promoting a ninth-best pair
to fill a slot — the same no-backfill rule Honorable Mention runs on. The singles
half is always full.

That a region was ever that thin was the actual bug: All-Region was being selected
per classification, so a "region" held four or five schools. Taken whole (Addendum
2) a region holds ~40 programs and every team fills. The no-backfill principle
stands and still governs Honorable Mention — a team is only as large as the
candidates who cleared the bar — but if a region team is coming up short again,
look first at whether something has re-narrowed its pool.

## 2. Flight weighting is STRUCTURAL, not a small bonus

> "FLIGHT WEIGHTING IS STRUCTURAL, NOT A SMALL BONUS … A 19–7 #1 singles season may
> be substantially more impressive than 25–1 at #5."

The first implementation applied flight as an exponent on `FLIGHT_WEIGHTS`
(`FLIGHT_ALPHA`), softened at region (0.72) and district (0.45) so the lower levels
could reach past their #1s. That softening was doing two jobs at once and only one
of them was wanted: it opened the district up, and it also let #4s with fat records
against nobody onto the state and region lists.

The weighting alone could not fix it, because the two failure modes pull opposite
ways. So flight is now carried by **two** mechanisms, both load-bearing:

1. **`FLIGHT_ALPHA` — how far apart the flights sit.** Tightened to
   state 1.00 / region 0.90 / district 0.70. It never inverts the order of the
   flights, only the distance between them.
2. **`FLIGHT_FLOOR` — how far down the card an honour reaches at all.** State is a
   **#1/#2** honour, Region reaches **#3**, District has **no floor** (it is a
   smaller pond, and "broadens downward without erasing the hierarchy" is the
   owner's phrasing). A below-floor candidate is admitted only by
   `_extraordinary`, which is checked **against the match log, not against a
   score**: a near-perfect record (`EXTRAORDINARY_PCT` 0.88) **AND** at least one
   win over an opponent who themselves played at or above the floor.

Re-scoring a lower flight would just re-ask the question the weights already
answered. "Did you beat people who were higher up the card?" is a different
question, and it is the one that distinguishes a genuinely misplaced player from a
#5 with twenty-five wins against other #5s.

Measured composition (boys, two districts per class):

| Level | #1 | #2 | #3 | below the band |
|---|---|---|---|---|
| All-State (incl. HM) | 17–24 | 13–18 | 0–2 | **0–2 per classification** |
| All-Region | 11–20 | 5–11 | 2–6 | 0–1 |
| All-District | 11–16 | 4–8 | 0–1 | — (no floor) |

### The mandatory flight sanity check

The owner asked for an inspection of every lower-flight selection before a singles
team is finalised. `_rank_singles` already refuses to offer one that has not
cleared `_extraordinary`, so it cannot fail silently — but the check has to be
**visible**, because "the weighting looks about right" is exactly how flight
stopped being structural the first time. `_flight_report` therefore produces, per
level: the floor, the count by flight, and every below-floor selection **by name,
flight and record**. It is **archived with the season** (`awards[group]
["flight_check"]`) and rendered on the page, so a season can be audited years later
without re-running a selector that has since moved on.

## 3. THE BUG: awards were selected before the postseason was played

The pairing tests failed on a player whose row said 18–5 while their log said 19–8,
and on another selected as a singles honour with 16 singles and 17 doubles matches.
Both were the same cause: **`season_awards` was called inside the qualification
loop, before Sectionals.**

Nothing errored. What it meant:

- SOP criterion 7 — "Sectionals through State count for more" — weighted a
  postseason **nobody had played yet**. `PHASE_WEIGHT` never applied to a single
  match, and a state title run added nothing to anyone's résumé.
- Worse, because it is silent: the postseason is **1S/4D**, so it moves most of a
  roster into doubles. The singles/doubles participation split that decides an
  athlete's category was therefore taken with a third of the season missing.

This is the **same fault, in the same function, as the record-snapshot bug**
documented in `CLAUDE.md` — a thing that reads a completed season being run before
the season completes. That one was caught because six programs' records did not add
up; this one had no arithmetic to fail, and survived until an unrelated test
compared a row against its own log. The awards call now sits after `run_toc`,
beside the record snapshot, with a comment tying the two together.

**The lesson generalises:** anything that summarises a season — records, awards,
ratings, honours — belongs after the last dual, not next to the code that happens
to have the data in scope. "It has the teams in hand here" is not the same as "the
teams are finished here".

## 4. The page: four views of one slate, not one scroll

> "the honors page needs better design per usual you just did a whole pgae with no
> differentiation all scroll by class instead of separate dropdowns for class,
> region, district"

A classification's honours are a POY, up to four All-State teams, Honorable
Mention, ten All-Region teams and a dozen All-District teams — around **four
hundred selections**. The first version stacked all of it, which is a page nobody
reads and nobody can cite. Rebuilt on the association's own layout rules:

- **Parallel views of one set of people are TABS** — All-State / All-Region /
  All-District / How these are selected.
- **A view that is itself a set of teams gets a SWITCHER** — one region or district
  on screen at a time, chosen the same way the classification is chosen. Three
  dropdowns, three questions: which class, which region, which district. The
  switchers are client-side, so browsing never reloads and the archived-season pin
  in the URL cannot be lost on the way.
- **Each team announces its two halves** — "Singles 10" and "Doubles teams 8 pairs
  · 16 athletes". Without the split, eight pairing rows read as eight individuals,
  which is the whole thing this release exists to fix.
- **The hub's rail stopped duplicating the page.** It reproduced All-State and
  All-District in full beside the bracket; it is now an INDEX — POY, the size of
  the slate, a way in. ("If two panels answer the same question, delete one.")
- **The rank cell is always emitted**, empty or not. It is a CSS grid with fixed
  columns, so the previous `{% if rank %}` shifted the crest, name, school and
  record one column left on every unnumbered team.

## 5. A knock-on: the honours got wider, and a test was measuring that

> **Half of this was wrong, and Addendum 2 is the correction.** "Every program
> places somebody" was read here as the spec working as written. It was not — it
> was the tell that All-Region had been built per classification. The owner's
> reply: *"unless you're telling me every school places someone as a good thing —
> and in which case, yeah, that's the whole point."* It was not a good thing.

A doubles selection being a pairing doubles the athletes in the doubles half, so
an All-District team went from 18 people to **26** — 10 singles plus 8 pairs —
spread over a district of about a dozen schools. That part IS the spec working as
written (the owner set the team sizes and then made doubles a pairing): a district
is a small pond and All-District is meant to be the wide honour, at 83% of schools
placing. What was not the spec was ~1,080 region honours stacked on top of it,
which is what pushed coverage to everybody.

It broke `test_a_season_with_nothing_to_show_is_not_listed_as_an_honour`, which
looked for a bare season in the live archive to prove `honoured` was computed
rather than hardcoded true. Those are two different claims and only one of them
was ever the point. The test now **strips a classification's slate** and checks a
program in it goes dark — the same mutate/restore pattern its neighbour uses —
which tests the computation instead of the breadth of the awards.

**The lesson is about how the failure was read, not what it was.** A test that had
held for releases started failing, and the first instinct was to reclassify it as
measuring the wrong thing. That instinct was half right — the assertion genuinely
was over-specified — and it was also a way of not asking why coverage had gone to
100%. A guard that suddenly goes green-by-saturation is evidence about the DATA.
Loosen it only after answering what changed underneath, and say the number out
loud to the owner: "every school now places somebody" was the whole diagnosis, one
sentence long, and it took the owner saying it back to land.

## 6. A test that could not see the bug it was named after

`test_award_rows_name_the_PLAYER_not_the_school` was written for the "All-State
rendered as a list of schools" regression. It asserts on `season["awards"]` — and
those records named people correctly the whole time. The fault was one line in
`jhsaa_honors_view.deco()`, splatting a SCHOOL deco (keyed `name`) over a row that
is a PERSON. **Reverting the production fix left the test green.**

The replacement (`test_jhsaa_toc.py::
test_the_honors_view_never_overwrites_a_player_with_their_school`) builds the VIEW
off the archived season and compares every decorated row against the archived row
it came from, on every surface — POY, each All-State tier, HM, each region, each
district and its POY — asserting the crest arrived and that `name`, `names`,
`pid`, `pids`, `school`, `kind`, `flight` and the record all survived the merge.
Verified by reverting the fix: it fails with `'San Cordero' != 'Sonoma Swanson /
Natasha Baynes'`, which is the symptom.

**The general rule:** a regression test belongs at the layer where the defect
lived. If the data was always right and the presentation was wrong, asserting on
the data proves nothing — and it is worse than no test, because it reads like
coverage.

---

# Addendum 2, 2027-08 — All-Region is region-wide, not per classification

> "i realize the problem is that classifications ame the regions and districts
> blur, it would be better to make all-region not class dependent, all region is
> just across the whole region (which is how it works in real life too)"
> … "so there's no 7A all-region, it's just EXAMPLE VALLEY ALL-REGION TEAM"

The addendum above shipped All-Region selected **per classification**, which put
three geographies on one page that were really only two. It was wrong, and the
symptom was §5: every program placed somebody.

**A region taken per classification is a district by another name.** The
association has ten regions and six classifications, so a class-region holds four
or five schools — the same order as a district, which is why the doubles halves
kept coming up short (§1c) and why nine class-regions per gender fell under
`MIN_REGION_PROGRAMS` entirely. Ten regions × six classes × 18 selections is
**~1,080 region honours a gender**, on an association of ~300 programs.

Region-wide and class-blind it is **one team per region for the whole gender**,
drawn from ~40 programs. Measured on the same season: **180 selections**, 47% of
schools placing (All-District: 83%), every team full at 10 + 8, and teams mixing
four or five classifications each. That is where the honour belongs — harder to
make than All-District, and open to a 2A school that produced a regional #1.

## What moved

- **`region_awards(pool)`** is its own selection, run once per gender, not part of
  `season_awards`. `season_awards` is now State + District only, and its docstring
  says why: All-State is the classification, and a **district IS
  `(classification, name)`** — that hierarchy is real. Class → region is not.
- **`build_pool(teams)`** rates the WHOLE GENDER once, and the per-class slates are
  selected from it. All-Region needs a ranking that spans the association, and this
  also fixes something that was quietly wrong before: non-district play crosses
  classifications, so rating a class in isolation cut those edges out of the
  opponent graph and defaulted every cross-class opponent to 0.5. It is the same
  reason `jhsaa.power_index` is computed gender-wide.
- **The archive** carries `all_region` and `all_region_flight_check` at the SEASON
  level, beside `all_district`, not inside `awards[group]`. Every reader merges it
  in — `honors_for` takes `{**aw, "all_region": arc["all_region"]}`. Readers keep an
  `aw.get("all_region")` fallback for seasons archived under the old shape.
- **Breadth at region scope is school + CLASSIFICATION.** Still a near-tie reorder,
  never a quota: a region whose best ten singles seasons are all 7A gets all ten.

## The page has to say so

The honors page is per classification, and the Region tab now **ignores the
classification dropdown** — the same ten teams whichever class is on screen. An
unlabelled tab under a class heading would reproduce exactly the blur this change
removes, so the pane carries a note in plain words ("There is no 7A All-Region
team…") and each team is headed **"Gold Valley All-Region Team · all
classifications"**, never "All-Region · Gold Valley" under a 7A page.

---

# Addendum 3, 2027-08 — regions are not the same size, and an athlete is one thing

Three owner corrections on top of Addendum 2, and one real bug that the first of
them exposed.

## 1. A big region crowns two teams; the biggest also crowns an HM

> "some regions are bigger than others so like the Ashbury Metro, Halbrook Basin,
> Gold Valley, and maybe the Harborline regions should all have bigger All-Region
> Teams because there are so many schools. So I'd say First and Second Team"

Making All-Region region-wide (Addendum 2) fixed the honour's SCOPE and left its
SIZE flat, which is its own unfairness: ten singles places is a very different
honour in a region of 115 programs than in one of 17.

Measured, boys / girls:

| region | boys | girls | | region | boys | girls |
|---|---|---|---|---|---|---|
| Halbrook Basin | 115 | 128 | | Sage Plains | 36 | 38 |
| Gold Valley | 65 | 77 | | Juniper Highlands | 31 | 32 |
| Harborline | 51 | 56 | | Cascade Divide | 28 | 29 |
| South Coast | **49** | **50** | | Timber Valley | 22 | 24 |
| Ashbury Metro | 45 | 54 | | North Range | 17 | 18 |

**The measurement corrected the request.** The owner named four regions; the
counts say five, because South Coast (49) is BIGGER than Ashbury Metro (45) on the
boys' side. Excluding it would have contradicted the owner's own stated reason —
"because there are so many schools" — so the threshold is on the PROGRAM COUNT
(`AR_TIER2_MIN_PROGRAMS = 45`), never a list of region names. There is a clean
break there: the next region down is 36. A name list would also have gone stale
the first time a school was added.

Halbrook is then its own case (`AR_HM_MIN_PROGRAMS = 100`): 115/128 against a
next-largest 65/77, so even two full teams reach only 36 athletes in a region the
size of a small classification. Its HM mirrors All-State's exactly — a merit
THRESHOLD, not a fixed-size third team, same résumé criteria and same flight
weighting, no requirement to fill anything — with one difference the owner set:
**one entry per school, not two** (`AR_HM_PER_SCHOOL = 1`), an entry being one
singles player OR one pairing. All-Region HM exists in exactly one region, and
that region is a fifth of the association; without the tighter cap its deepest
programs would take the tail of it two at a time.

Shape: `all_region[region]` is now `{tiers, honorable_mention, programs}`, and
**`region_rows()` is the one place that knows it.** Half a dozen readers walk this
structure; walking it by hand in each is how one of them ends up showing a big
region's First Team only.

## 2. THE BUG: an athlete on both the First and the Second Team

The tier test failed immediately — one Gold Valley athlete on both teams. Cause:
`used` was created fresh per team. The ranked slices keep tiers disjoint by INDEX,
but **a player with two strong partnerships appears at two different indices**, so
they landed on the First Team with one partner and the Second with another.

Owner: *"that should not happen."* Correct — that reads as a selector that could
not make up its mind. `used` now carries across the tiers of a level, so an
athlete is taken at their best tier and skipped thereafter.

**It was not only a region bug.** All-State's tier loop had the identical shape,
so the same duplication was possible on the First/Second/Third/Fourth teams and
nobody had looked. Adding a feature surfaced a fault in the thing it was copied
from — worth remembering: when a new caller of an old pattern fails, check the
old callers before assuming the new one is wrong.

## 3. The category is the athlete's BETTER discipline, not their more frequent one

> "kids can't play singles and doubles in the same match so just take their better
> thing and give them that"

Addendum 1 assigned an athlete's category by PARTICIPATION — whichever discipline
they played more of. Defensible, and not what was asked for: a player who filled
in at doubles through a rotation while producing the region's best singles season
was being judged as a doubles player.

Now it is STANDING (`_assign_primary`). "Better" cannot be a raw score comparison
— a singles résumé and a partnership's carry different flight weights over
different volumes, so the numbers are not the same currency. It compares where the
athlete sits in the gender-wide singles field against where their strongest
partnership sits in the gender-wide field of partnerships, both as percentiles of
the same shape. Ties go to singles.

This inverted a dependency: `_pairs` used to skip non-doubles-primary players, but
the primary is now DECIDED from the pair ratings, so every partnership is built
first and the cross-category ones are dropped afterwards. Circular otherwise.

One category per athlete is still what makes "nobody in both halves of one team"
true by construction rather than by a filter.

## Traps for later

- **A threshold that separates a named list today will separate a different list
  tomorrow.** Derive from the property the owner is actually reasoning about
  (size), then CHECK it against the names they gave — and say so when it disagrees.
- **`region_rows()` or nothing.** Any new reader of `all_region` that walks the
  dict itself will miss a tier or the HM.
- `used` carries across tiers, at every level. Resetting it per team silently
  re-admits the duplicate.
- **Never put All-Region back inside `awards[group]`.** If a region team is being
  selected per classification, it is a district with a different heading.
- Class → district is a hierarchy; class → region is not. Any UI that nests them
  the same way is wrong.
- A stripped-classification test must clear `arc["all_region"]` separately now —
  emptying a class's slate no longer removes its players' region honours. Two tests
  caught exactly this.
- **`row_pids`, never `row["pid"]`.** A doubles row honours two athletes. Every
  membership test in the codebase goes through it; a new one that does not will
  credit exactly half of every pairing and look right on the surface it is on.
- **A pairing's record is the PARTNERSHIP's**, not either player's doubles season.
  If a row's record ever matches a player's doubles total, the pair log has been
  rebuilt from the wrong side.
- **Do not "restore" the softened `FLIGHT_ALPHA`** to open a level up. That was
  tried; it opens the state list at the same time. The floor is the control for
  reach, the alpha is the control for spacing.
- **Do not make the flight check advisory.** It is an archived artefact of a
  decision, in the same family as the archived TOSS index: recomputing it later
  would produce a report about a selector the season never ran.
- **Selection runs after the last dual.** If a summary of a season is moved earlier
  "because the data is here", check what phase of the season it can actually see.
- Region teams may be short by a pairing. That is the pool being honest; do not add
  a backfill.
