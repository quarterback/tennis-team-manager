# AAR — the JHSAA JV season (2026-08)

A concurrent sub-varsity season for the whole association. Feasibility work and the
owner decisions are in `docs/BRIEF-jhsaa-jv-and-varsity-2-feasibility.md`; this is what
the build actually taught.

## What it fixes

Measured on the real 2038 save: **40.8% of girls' and 42.3% of boys' JHSAA players
finished a season with five matches or fewer**, 8-10% with none, and **18-19% of
seniors reached the college hand-off having played ≤5 in their final year** — about 750
a gender arriving on the recruit board at 0-0. The regular season dresses eleven of a
median-19 roster, so ranks #12 and below were effectively invisible.

## What shipped

* **One roster, one ladder, best eleven play.** `_order` ranks the roster, the top
  eleven dress varsity, everyone below is JV (`jv_pool`). Nothing was added to make it
  porous — a varsity player who lost through the season has fallen past a JV player's
  seed and they swap, which the ladder already did. **The swap is not date-by-date
  though — see §13.**
* **An elastic lineup** (`JV_FORMATS` + `jv_format`): 1S/2D at five spare and upward
  with no ceiling, the shape taken from the **thinner** side.
* **`ROSTER_FLOOR` 12 → 16**, so every program can field a JV.
* **Ties**, the association's first: points, then sets, then games, then a draw.
* **`JVTeam`**, a separate type with no `records` and no `matches`.
* **Archive**: `world_jhsaa_dual` gains `level` / `tied` / `shape` / `played`; JV rows
  carry a full per-court `lines` box score AND `played` (§11, §12).
* **Schedule**: district single round robin → invitationals to a 16 cap → one showcase
  pod, outside the cap.
* **Calendar**: JV is dated by `_jh_jv_dates`, entirely outside the varsity allocator,
  opening a month later and allowed to use Sundays.
* **UI**: the school page's schedule is Varsity/JV tabs, both with expandable box
  scores; a player's career ledger carries a **JV** column — the team's result in the
  duals they dressed for.

No playoffs, no JV ranking, no effect on development, and JV touches no record,
résumé or rating that the varsity season owns.

---

## 1. ‼️ The elastic table is the whole feature, and the reason is arithmetic

A **fixed** JV format has to be fielded by BOTH schools, so its reach is the *product*
of two roster constraints. Measured as a share of real league dates where both sides
could field: 3S/4D **7-9%**, 2S/3D 32-36%, 2S/2D 61-64%, 1S/2D 78-79%. Every one of
those is worse than either school's individual capacity, and the good formats are far
worse.

The elastic table has no product — the shape simply drops to what the thinner side can
dress — so the condition collapses to "both sides have five spare". With the floor at
16 that is always true: **864/864 girls' and 780/780 boys' programs field a JV.**

The projected payoff (≤5-match players 41% → ~5%) is nearly **flat** from 1S/2D to
2S/3D, because a bigger format reaches fewer programs but gives each reached player more
lines and the two effects cancel. That is worth knowing before anyone "improves" the
table: the format is a presentation choice, not a data one.

## 1a. ‼️ The table was eight literals; it is one rule

It shipped clamped at twelve — a deep program dressed 4S/4D and the rest watched.
Owner: *"if two teams have bigger than 4/4 can we add those formats to go bigger? 5/5,
4/5, 5/6, whatever to fit their jv roster avail."*

The eight authored entries are not eight arbitrary shapes. They are:

    D = (spare + 1) // 3        S = spare - 2D

which reproduces all eight exactly and then keeps going — 13 → 5S/4D, 14 → **4S/5D**,
15 → **5S/5D**, 16 → 6S/5D, 17 → **5S/6D**, 18 → 6S/6D — i.e. the three examples asked
for, in order. Read another way: doubles steps up, and singles runs D−1, D, D+1
beneath it, which is what keeps the card doubles-forward at every size, matching the
varsity 3S/4D league format's character.

The literals stay (they are what was decided) and an import-time assertion checks the
rule against them, so the two cannot drift. **A table that a rule reproduces is a rule
with a cache in front of it** — worth checking for before extending any authored table
by hand.

No ceiling was needed as a safety rail either. The shape is always the *smaller* side's
capacity, so a big card needs BOTH programs that deep, and the association's own roster
distribution bounds it: measured over the real 2038 league pairings, **only 2.0% of
girls' and 3.3% of boys' pairings go past 4S/4D at all**, and the largest single
pairing in the state is 5S/6D (girls) / 7S/7D (boys). A constant would have been
picking a number the data already picks.

## 2. ‼️ A floor of 15 would have changed nothing

The first proposal was 15. Measured: it lifts the 12-14 rosters to 15 and leaves them —
plus the 61 girls'/42 boys' programs already sitting at exactly 15 — **still one short**,
because a JV needs 11 + 5. It would have looked like a fix and moved zero programs into
JV eligibility. 16 moves 105 girls'/89 boys' programs and takes participation to 100%.

`ROSTER_FLOOR` is now asserted as `lineup_need("regular") + JV_MIN_SPARE` rather than as
a literal, so raising the smallest format without the floor fails loudly.

## 3. ‼️ `res.winner` is wrong for any even-court dual

`engine.dual` computes `winner = 0 if points[0] > points[1] else 1`, so a **level dual
reports an AWAY win**. Every varsity format in this association has an odd court count
and can never draw, which is exactly why that has always been safe — and why it would
have been silent here. Three of the eight JV formats are even, and 2S/2D is one of the
most common shapes on the slate.

`jv_outcome` therefore decides from the points itself and never reads `res.winner`.

Calibration, measured over a slice: **21% of even-court duals are level on points**,
about 40% of those are still level on sets, and only ~8% of *those* survive games — so a
true draw is about **0.24% of all JV duals**. The tie machinery is genuinely needed and
genuinely rare. (The brief's earlier "ties are a quarter to a third of the JV season"
was about even-court FORMATS, not about draws; it is corrected there.)

## 4. ‼️ Adding `level` to `jh_match_key` shifted a tuple four other places read
positionally

`jh_match_key` had to gain `level` — the same two programs meet at varsity and at JV, in
the same phase, in the same league, so without it both duals hash to ONE key,
`_jh_global_order` gets a self-edge whose in-degree never reaches zero, and the whole
gender's topological sort falls into its cycle fallback. Nothing raises; every card just
stops reading in play order.

But the key went from 4-tuple to 5-tuple, and **four consumers indexed it positionally**:

| site | read | consequence if missed |
|---|---|---|
| the stage sort | `k[0]` → `k[1]` | sorts every dual by the string `"v"`, so postseason stages stop separating from the regular season |
| the main loop | 4-way unpack → 5-way | raises (the only loud one) |
| the monotonic pass | `key[2], key[3]` → `key[3], key[4]` | compares phase strings and district ints as school names |
| `_jh_showcase_days` | `key[0]` → `key[1]` (twice) | every showcase silently reverts to the ordinary weekday pattern |

Three of the four are silent. **A positional read of a shared key is a latent
dependency on that key's arity** — `grep` for every index of it before changing its
shape, which is what caught these.

## 5. ‼️ JV must never enter the varsity date allocator

`jhsaa_match_dates` packs duals into rounds by advancing a per-school cursor on **every
distinct key**. So a JV dual sharing a school with a varsity one takes a *later* round,
and the two seasons serialise: the calendar overruns its window, `_jh_pattern` degrades
to a six-day week, and **every individual card still reads correctly** — only the SPAN
is wrong. That is precisely how `AAR-jhsaa-postseason-calendar-lanes.md` hid.

Two ways out, and it matters which:

* **Coalesce** — give a JV dual its varsity dual's date. This is what a *mirrored* JV
  schedule would need, and adding `level` to the key does the OPPOSITE of it: it makes
  the keys distinct. Necessary, but not sufficient, and easy to think you are done.
* **Separate** (chosen) — JV rows never enter the varsity pool at all, and get their own
  pass with their own pattern. Strictly less work, and the varsity calendar is
  *provably* untouched rather than carefully preserved.

JV opens a month after varsity (girls April, boys September), which also steps past the
5S/2D early window where `lineup_need` is **nine** rather than eleven — a JV dual
overlapping it would find two more players available and size itself off a different
varsity lineup. Measured: every early-phase dual in 2038 falls in March (girls) or
August (boys), so the April/September opening clears the whole window.

## 6. ‼️ Archiving the dual but not the courts retired a hazard instead of guarding it

The choice was three-way, not yes/no, and the costs are measured per season across both
genders against varsity's 40.0 MB:

| | persists | pages can show | cost |
|---|---|---|---|
| **A** (shipped) | dual + per-court `lines` + `played` | schedule · record · **BOX SCORE** · participation | **23.4 MB** |
| B+ | dual + `played` names | schedule · record · participation | ~9 MB |
| B | dual only, `lines=[]` | schedule · record | 2.6 MB |
| C | a record field only | record only | 0.07 MB |

A was taken in the end (owner: *"the jv box score is worth the small annual MB add
it's trivial"*) — B+ shipped first and is kept underneath it, because the career
ledger's JV column folds `played` and should not have to parse court detail it does
not show.

> ⚠️ **A was quoted at 15.3 MB when the decision was taken and it is ~22.** The estimate
> predated the uncapped format table, which took courts/dual from 4.8 to **5.22** (max 9
> in the measured slice). A cost figure that decided something has to be re-measured when
> the thing it was measuring changes shape; nothing prompts you to.

C was the literal reading of "don't archive JV match data" and would have retired the JV
schedule tab, because **the JHSAA has no live season**: the rung runs once at world week
0 and every surface reads the archive, so an unarchived dual cannot be shown *at all* —
not next season, not the day it is played, short of re-simulating on a request, which is
`AAR-jhsaa-research-export-resimulation-hang.md`.

What B bought beyond the bytes:

* **`_jh_line_records` cannot merge a JV appearance into a varsity player card.** It
  matches by NAME inside `lines`; a JV row has none. That is a fact about the data, not
  a guard someone maintains. `_season_row`'s court counts are immune for the same
  reason, and `jhsaa_underplayed` keeps counting varsity-only for free.
* **The JV record stays a FOLD, not a store** — the dual rows persist, so it derives
  exactly as the varsity record does and `jhsaa_school_history`'s "no second source of
  truth" rule holds. C would have forced the exception.

The hazard **returns the moment anyone archives per-court JV detail**, which is why it
is written at both ends.

## 7. Precision was spent on a decision that does not matter — again

The invitational matcher was first a windowed scorer: bucket the talent gap, break ties
on geography, scan the next N candidates. Owner: *"Rather than run forever scheduling
for precision it should just pick someone… especially in JV it's literally whoever has
someone."*

It is now a talent sort and a walk — pair each team with the next one still free. This
is the **same lesson `_showcase_groups` already learned** (it was a placement solver
before it was a one-pass deal, and it was quadratic per tier per window). The pattern to
notice: *when the quality of a matchup comes from the ORDERING, searching inside the
ordering buys nothing.* A talent sort already puts comparable teams next to each other.

The one rule that survives is the same one that survived there: no league-mate.

Note that talent-first is itself the **inverse** of varsity's `_nondistrict_pairs`
(geography, then nearest strength). That is deliberate — travel is not a real cost in a
simulation, and a JV player facing their own level is the entire point. Measured:
talent-first pairs at a median gap of 0.0 OVR, geography-first at 4.2-5.2.
Classification is deliberately **not** a gate; talent proximity already lands 78-79% of
pairs within two classes, and gating would force a worse match to satisfy a rule about
enrollment.

## 8. The showcase needed a phase, and a test found it

The JV showcase initially played at `phase="regular"`, which made it indistinguishable
from an invitational — on the card, in the archive, and in the cap arithmetic (the
"outside the 16" rule could not be checked because nothing could tell them apart). It
now plays `showcase_pod`, which is the association's existing rule restated: **a phase
is the archive's identity for an EVENT**. It also picks up `match_format`'s 8-game pro
set, which is what a pod plays.

## 9. Cost, measured

A full girls season: **146.6s → 204.7s** (+40%), so the week-0 rung is roughly **5 → 7
minutes** for both genders. 8,198 JV duals a gender — ~6,900 league and invitational
plus ~1,300 showcase. The JV slate averages 4.8 courts against varsity's ~6.7.

The `DESIGN-jhsaa-high-school-season.md:280` figure of 19s for both genders is long
stale and was already wrong before this.

## 10. Why there are no JV playoffs

Asked directly, and the answer is that there is no good shape for one:

* a playoff needs a **ranking to seed it**, and JV has none by design — building one
  re-introduces exactly what was excluded;
* a JV team is **not a stable entity** — it is a slice of one ladder rather than a
  standing squad, so the squad that qualified need not be the squad that plays;
* the format is **elastic and opponent-dependent**, so a semifinal could be 4S/4D and
  the final 1S/2D;
* real associations agree — the MIAA sanctions no sub-varsity tournament at all.

If a season-ending event is ever wanted, more **showcase weekends** are the shape that
works: pods, no bracket, no advancement, no seeding, and the machinery already exists.

## A near miss worth recording

Swapping the table for the rule left the OLD `jv_dual_format` and `jv_lineup_need`
definitions further down the module. Python keeps the last one, so the clamped version
would have won and the whole change would have been inert — `jv_format` uncapped,
`jv_dual_format` still clamping it back to twelve. Exactly the shape of `flavor.py`'s
double `roll_us_hometown`, which CLAUDE.md already warns about. `grep -n "^def "` after
any block replacement.

## Pre-existing failures, not touched

Three tests failed at the parent commit and still do, verified in a worktree at
`HEAD~1`: `test_jhsaa_lineup.py::test_maximize_never_scores_worse_than_traditional`
(fails by ~0.0007 — `maximize` optimises `doubles_rating + FAMILY_CHEMISTRY` while the
test sums bare `doubles_rating`, so a sibling pair legitimately picks a split that is
fractionally worse on the bare metric) and two in `test_jhsaa_schedule.py` about the
non-district allowance. None is related to this work.

Two `test_jhsaa_toc.py` tests DID break and were mine: both count rows in
`world_jhsaa_dual` per school and compare to the varsity record, which JV rows now join.
Both take an `AND level='v'` filter — the invariant they protect is unchanged.

---

## 11. ‼️ "It can't be shown" was a data decision reported as a limitation

Asked whether a player page could show a JV season, the answer given was effectively
*no, per-court JV detail is not archived* — with the retired `_jh_line_records` hazard
offered as a benefit. The owner read that as a claim the UI was **hard**, and pushed
back. They were right to: the tab machinery was already built (it is the same
`jh_tabs` call the schedule split uses), and B was **their own choice** from an A/B/C
menu. Nothing was blocked; a previous decision was being restated as a constraint.

Two things came out of re-opening it, and the second is the useful one.

### The middle option was never on the menu

A/B/C was framed as *how much detail*, so the only way to get a player-level answer
looked like paying for A in full. But "did this kid play JV, and how did it go" and
"what did they go at No. 2 doubles" are **different questions with an order of
magnitude between them**. `played` — the names that dressed, crediting the DUAL's
result off the row's own `won`/`tied` — answers the first for ~9 MB against A's ~22.

‼️ **And putting it in its OWN field rather than in `lines` is what keeps the hazard
retired.** `state`'s player view hands the WHOLE schedule, both levels, to
`_jh_line_records` — it always has, and `state.py:4914` still does. That is safe
*because* a JV row has no `lines`, which is a property of the data. Had `played` gone
into `lines` as slot-less entries, every JV appearance would have joined the varsity
singles/doubles record and the flight box on that line, and the fix would have been a
level filter on every present and future reader. The cheaper option is also the safer
one, which is not the trade-off the original menu implied existed.

### The "dynamic columns" objection was wrong, and the code already said so

Raised against A: the JHSAA flight box is fixed at S1-S5/D1-D4 while uncapped JV
reaches S6+/D6+, so JV would need dynamic columns. The owner's answer — *"the varsity
flight box is only fixed because you didn't copy it from the college game which
already has one that flexes"* — is correct, and `player_career_records` had been
carrying the general solution the whole time:

```python
n_s = max([f.n_singles] + [max(s["singles"], default=0) for s in seasons])
n_d = max([f.n_doubles] + [max(s["doubles"], default=0) for s in seasons])
```

*"Card width = the player's division's dual shape, widened to any line they actually
played (career history can span formats)."* That is the JV problem exactly — a career
spanning formats — solved, with a comment explaining why. `_jh_flight_box`'s docstring
says it "mirrors `player_career_records`'s `_box`", and it is a **degraded copy**: it
hardcodes `range(1, 6)` / `range(1, 5)` where the original derives them.

**The lesson is the owner's, stated plainly: the college game already has everything
being asked for, and that is why it is in the same repo.** When a JHSAA surface needs
something the college side has, the question is which helper to widen — not what to
build. A capability that exists twenty modules away, in a helper the local one already
claims to mirror, is easy to describe as a design obstacle if you only read the copy.

*(Left as-is deliberately: `_jh_flight_box` is not widened here, because option B+
archives no flights to widen it for. It becomes real work the day A is chosen, and
then it is a port, not a design.)*

## 12. The box score, and the six readers that were only safe by accident

Owner: *"yes, the jv box score is worth the small annual MB add it's trivial."*
Measured at **23.4 MB** a season for both genders (590 B of lines + 125 B of `played`
per row), against varsity's 40.0.

The recording is a near-copy of `play_dual`'s loop with one deliberate omission and one
trap:

* **No `_credit`.** `play_dual` credits each line to its players as it builds them —
  that is what feeds the ladder, the awards résumé and TOSS. The JV loop builds the same
  rows and credits nothing, which is the entire difference between a box score and a
  competition.
* **‼️ `_slot_players` had to take the elastic `fmt`.** It resolved doubles as
  `f.n_singles + 2*(i-1)` off `dual_format(phase)` — the varsity shape — so a JV D2
  would have named the players sitting at the varsity singles offset. Wrong names, right
  count, no error: exactly the `_squad` override that already existed, needed a second
  time in the function that answers *who was on that court*.

### What actually made this a change worth doing carefully

Until now, "JV cannot contaminate varsity" was a property of the DATA — JV rows had no
`lines`, and every varsity reader iterates `lines`. Adding the box score turns that into
a rule six readers have to follow, and **five of them were reached by callers that pass
both levels**:

| reader | what it feeds | now |
|---|---|---|
| `state._jh_line_records` | a player's season singles/doubles record | filters `level` **inside** |
| `state._jh_slot_records` | the per-flight box on a player card | filters `level` inside |
| `world._season_row` | a program's `courts_won`/`courts_lost` | filters `level` |
| `world.jhsaa_underplayed` | the transfer-portal board | `AND COALESCE(level,'v')='v'` in SQL |
| `world.jhsaa_history_rows` | the research export's program ledger | **had dropped `level` from its SELECT** |
| `jhsaa.rating_duals` / `_weighted_lines` | TOSS | safe by TYPE — they take `TeamSeason`, and JV teams are `JVTeam` |

Two things worth keeping:

**The filters went INSIDE the readers, not at the call sites.** `_jh_line_records` is
called from three places and `_season_row` from two; a filter per caller is five chances
to forget, and the sixth caller written next year has no way to know. A reader that
means "varsity" should say so itself.

**`jhsaa_history_rows` is the one that would have shipped broken.** It re-reads the dual
table in bulk for the research export and built its row dicts with only `home` and
`lines` — so `_season_row`'s new `level` filter saw no key, read every row as varsity,
and would have added JV courts to every program's court totals in the export. The same
omission already had `jhsaa_jv_record` returning 0-0 there. **A filter is only as good as
the field reaching it**, and a bulk re-reader that hand-builds row dicts is exactly where
a column goes missing — it does not share `_schedule_rows`, which is what made this
invisible.

`jhsaa.rating_duals` is worth naming for the opposite reason: it needs no filter, because
`JVTeam` is a different type and never enters the list. That is the separation earning
its keep — the strongest guard here is still the one that is structural.

### The analytics sidecar is untouched

Checked directly, because it is the obvious downstream: `analytics/` reads
research-export zips, and `research_export.build_jhsaa` iterates
`season["teams"]` — varsity `TeamSeason` objects only. `season["jv"]` is never read,
so **no JV dual, line or line-player row has ever reached a zip**, box score or not.

The one place JV did reach it is the program-history table, via `jhsaa_history_rows` —
the bug above. Fixed before it shipped.

**And it should stay that way** — owner, asked directly: *"it can ignore JV generally
i do not need JV analytics."* So the export deliberately remains varsity-only; this is
a decision now, not just an accident of which collection the exporter iterates.

‼️ If that is ever revisited, **the exporter needs a `level` column first.**
`duals.csv` has none, and `aggregate.py` DERIVES each phase's card shape by counting
the singles and doubles lines it sees (*"Card shapes … are DERIVED from the actual
exported lines"*). JV duals are `phase="regular"` with an elastic shape, so dropping
them in unlabelled would not add a JV section — it would corrupt the derived shape of
the varsity regular season. (Owner, same message: the analytics app *"needs a
refurbish at some point"* — that is the moment to do it, not by widening the export
underneath it.)

## 13. ‼️ The porousness is real but NOT temporal — and the docs said otherwise

Flagged on the PR, and correct:

> *"the implementation says JV is a 'daily slice' of the ladder, but it actually runs
> the entire JV season only after the varsity regular season has finished. That means
> every JV lineup is selected from the end-of-regular-season ladder, not from the ladder
> as it existed on that date. So the code currently models a porous JV in name, but not
> temporally."*

The mechanism is exactly that. `run_season` calls `play_regular_season` to completion,
then `play_jv_season`; `jv_pool` reads `_order`, which reads `ts.records`, which by then
hold the whole varsity season; and `play_jv_dual` deliberately never calls `_credit`, so
nothing moves the ladder *during* the JV season either. **Every JV dual of the year
therefore resolves `jv_pool` to one identical ordering.** A JV dual dated 12 April is
staffed off the ladder as it finished in June. "Daily slice" is right that it is derived
rather than a standing squad, and wrong that it is re-cut per date — it is cut once, at
the end, and applied to every date.

### How big it is, measured

Reconstructing each player's ladder position from their own appearance log
(`ts.matches` is ordered), over 42 programs:

| ladder read at | JV pool differing from the end-of-season pool |
|---|---|
| 10% into the season | **4.1%** (13 of 408 players) |
| 25% | 3.8% |
| 50% | 3.1% |
| 75% | 2.8% |

Median rank change for a player across an entire season: **0 places** (mean 0.5, max 4).

### Why it is small, and the condition under which it stops being

Not because the shortcut is sound — because of a decision made somewhere else.
`ladder_score` is `ovr + LADDER_SWING × (pct − ½) × n/(n + LADDER_PRIOR)`: results are
worth at most ±7 OVR and are damped by how much evidence there is, deliberately, so that
"a 1-2 opening week cannot outrank a season" (§AAR-jhsaa-order-of-ability). **A ladder
built not to move is a ladder whose read TIME barely matters.** The critique assumes a
swingier ladder than this association has.

‼️ **So the error scales with `LADDER_SWING`.** At 7 it is 3-4% of JV slots. Raise it —
or add anything else that moves players faster (injuries, fatigue, a challenge-match
system) — and this shortcut degrades proportionally, silently, with every JV lineup
still looking perfectly plausible.

### What the fix would be, when it is worth doing

The reason the JV season sits after the varsity one is real: `jv_pool` reads a
results-moved ladder, so running it *first* would staff every JV dual off opening seeds.
But that is a false dichotomy — **the alternative to "all at the start" is not "all at
the end", it is interleaved.** `play_regular_season` already has clean block seams
(early non-district → district pass 1 → mid-season window → district pass 2 → late
tune-up), and the JV district slate is already generated as rounds, so JV could be
played one block at a time at those seams and read the ladder as it stood.

Not done here (owner decision): it is real surgery on both functions' control flow —
`play_jv_season` carries cumulative state across its windows (the `JV_DUAL_CAP`
accounting, the `played` set, the showcase) — for a measured 4.1%. Documented instead,
at `jv_pool`, at the `run_season` call site, and in CLAUDE.md, each carrying the number
and the `LADDER_SWING` trigger.

**The transferable bit:** the docstring described the *design intent* and the code
implemented a cheaper approximation of it, and nothing in between flagged the gap —
no test could, because both behaviours produce a complete, plausible JV season. When a
comment claims a property (*porous*, *daily*, *live*), the thing to check is whether
the call ORDER actually delivers it, not whether the function it points at is correct.
