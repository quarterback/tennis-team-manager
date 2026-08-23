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
  eleven dress varsity, everyone below is JV that day (`jv_pool`). Nothing was added to
  make it porous — a varsity player who loses through the season falls past a JV
  player's seed and they swap, which the ladder already did.
* **An elastic lineup** (`JV_FORMATS` + `jv_format`): 1S/2D at five spare and upward
  with no ceiling, the shape taken from the **thinner** side.
* **`ROSTER_FLOOR` 12 → 16**, so every program can field a JV.
* **Ties**, the association's first: points, then sets, then games, then a draw.
* **`JVTeam`**, a separate type with no `records` and no `matches`.
* **Archive**: `world_jhsaa_dual` gains `level` / `tied` / `shape`; JV rows store
  `lines` empty.
* **Schedule**: district single round robin → invitationals to a 16 cap → one showcase
  pod, outside the cap.
* **Calendar**: JV is dated by `_jh_jv_dates`, entirely outside the varsity allocator,
  opening a month later and allowed to use Sundays.
* **UI**: the school page's schedule is Varsity/JV tabs.

No playoffs, no JV ranking, no per-player JV data, no effect on development.

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
| A | dual + per-court `lines` | schedule · record · player tab | 15.3 MB |
| **B** (chosen) | dual only, `lines=[]` | schedule · record | **2.6 MB** |
| C | a record field only | record only | 0.07 MB |

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
* a JV team is **not a stable entity** — it is a daily slice of one ladder, so the squad
  that qualified in April is not the squad that plays in May;
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
