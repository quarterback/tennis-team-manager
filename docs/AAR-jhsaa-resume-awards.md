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
