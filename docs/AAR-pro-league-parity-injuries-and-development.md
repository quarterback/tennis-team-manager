# AAR — building out the pro league: injuries, development, and club playing styles

**Date:** 2026-07-29
**Status:** COMPLETE. Injuries, development, club styles, the coach pool and
carousel, the player-movement economy and the alumni view all landed.
**Scope:** `injuries.table_schema` / `unavailable` / `recover` / `roll_new` (new — the
shared store), `seasonmode._unavailable` / `_recover_team` / `_roll_new_injuries` (now
delegations), `gtt_seasonmode` (`gtt_injuries` table, `_inj_scope`, `_lineup` filter,
`_play_and_store` roll, `PRO_GROWTH` + the develop branch, `franchise_coach` /
`club_style` / `club_identity` / `apply_club_coaching`), `app/playstyles.py` (new),
`coaches.coaching_strength`, `tests/test_injuries.py`, `tests/test_gtt.py`,
`tests/test_playstyles.py`.

## Symptom

Owner: *"THE PRO GAME NEEDS TO WORK LIKE THE COLLEGE GAMES' DURABILITY WHY IS IT
SEPARATE IT'LL ALWAYS BE BROKEN"*, then the part that matters most:

> *"the pro league lacks everything because past agents have told me it wasn't
> necessary and i've asked for this before and gotten not very far"*

## What was actually true

Measured, not assumed — grep across `seasonmode`/`world`/`season` vs `gtt_seasonmode`:

| System | College | Pro |
|---|---|---|
| Injuries / durability | yes | **zero references** |
| Player development | yes | **zero calls to `develop()`** |
| Aging / decline / retirement | — | yes (pro-only) |
| Results-based STR convergence | yes | yes |
| Doubles | yes | yes |
| Honors / MVP / Hall of Fame | yes | yes |
| Transactions / waiver wire | — | yes (pro-only) |
| Per-dual chaos form | — | yes (pro-only) |
| Coaches | 77 refs | **zero** |
| Franchise prestige | 69 refs | **zero** |

So "lacks everything" was close but not exact: the pro league has real systems college
doesn't (waiver wire, chaos form, aging). What it lacked were the two that make players
**change over time** — and without those, nothing else you add to it can feel alive.

## Root cause 1 — injuries: the rules lived in the wrong module

The dice were already shared in `app/injuries.py`. The **store and the rules** —
availability, the recover/grace clock, rolling on whoever actually competed — were
private helpers (`_unavailable`, `_recover_team`, `_roll_new_injuries`) inside
`seasonmode`. There was nothing for the pro league to call, so it called nothing.

This is not a design split anyone chose; it's a module boundary drawn in the wrong
place. It stayed invisible because **nothing errors when injuries simply never
happen** — durability quietly stopped meaning anything the moment a player graduated.

## Root cause 2 — development: a calibration trap that makes the fix look pointless

`gtt_seasonmode` never called `develop()`. Its only per-year change was age+1, retire,
and `decline()` once past `PEAK_AGE` (28). A pro drafted at `ENTRY_AGE` (22) was
**frozen at their college exit level until 29, then only got worse.** Every graduate
carries a ceiling out of college that was never approached again.

The important part is why this is easy to wave off. Measuring the obvious growth curve
on a **raw generated prospect** looks fine — big remaining gap, visible movement. But
the actual pro population is **graduates**, who have already spent four years of growth
and have a much smaller gap. On graduates, the same curve is worth:

```
scale 1.0/yr, ages 22→28, measured on 5 real graduates:
  55→56   52→58   41→42   45→49   39→41      (+1..+4 OVR across a WHOLE prime)
```

+1 OVR over six years is indistinguishable from nothing. **Anyone who calibrated on raw
prospects and then sanity-checked against the real league would conclude that pro
development "isn't necessary" — the measurement agrees with them.** That is the most
likely shape of the answers the owner got before, and it is a measurement error, not a
judgement call.

With `PRO_GROWTH = 2.0` on the same graduates: `+2..+10`, the spread coming from each
player's own remaining gap and interest rate — some break out, some plateau.

## The fix

1. **One injury implementation.** The store moved into `app.injuries` as
   `unavailable` / `recover` / `roll_new`, taking the caller's table and key columns.
   College passes `injuries` keyed `(season_id, school)` — behaviour unchanged, its
   helpers are now three-line delegations. The pros pass `gtt_injuries` keyed
   `(_inj_scope(league, year), franchise id)`. Separate rows, identical rules.
   `gtt._lineup` filters the injured so a reserve is pulled up exactly as college depth
   works; a club too thin to field a healthy lineup plays its hurt players rather than
   forfeiting, because the sim needs a full card.
2. **The new table is cleared with its league.** `gtt_injuries` is keyed by an
   opaque `_inj_scope` int rather than `league_id`, so it needs explicit cleanup:
   `delete_league` drops that league's whole scope range and `reset()` wipes the
   table. Missing this is the same id-reuse trap this repo already hit with
   `world_cups` — SQLite hands the rowid back to the next league, and a new save
   reuses the default seed, so pids AND scopes repeat exactly; stale season-ending
   rows would have benched players in a league that never injured them.
3. **Pros develop**, tapering linearly to zero at `PEAK_AGE` — the mirror of decline's
   scale growing past it — scaled by the tunable `PRO_GROWTH`.

## Verification

- A full simulated pro season now produces injuries with the same shape as college
  (out 1–6 duals, or season-ending); an injured pro is dropped from the lineup and a
  reserve promoted.
- College injury behaviour unchanged: all 21 pre-existing injury tests pass against the
  shared store.
- Pro growth is visible in OVR, never exceeds the ceiling, and is fully spent at the
  peak.
- Deleting a league and resetting the tour both leave `gtt_injuries` empty.

## Rule

**Absence is the hardest bug to see.** Nothing errors, no test fails, and every number
on screen looks reasonable — a league where nobody is ever hurt and nobody ever improves
renders perfectly. When a subsystem is reported as "lacking", diff it against its
sibling by grep before forming an opinion; the answer is a table, not a judgement.

**A new persistent table is not done until its teardown is.** Every id this repo
keys on is recycled by SQLite after a reset, and a new save reuses the default seed —
so "the ids will differ" is never true here. Add the DELETE to both the per-entity
delete and the whole-tour reset in the same change that adds the CREATE.

**Weight by what the FORMAT actually uses.** The same attribute is not worth the same
in two leagues. Doubles is 1/3 of a pro tie and 1/7 of a college dual, so net skills
carry ~2.3x more there; a boost table copied between them is silently mis-tuned. Check
the line composition before calibrating anything that targets specific attributes.

**And calibrate on the real population.** A growth/decay curve tuned on freshly
generated prospects will be silently near-zero on graduates, who have already spent most
of their headroom. If a change measures as "no effect", check what population you
measured on before concluding it isn't needed.

## Round 2 — club playing styles (owner: *"can't you look at IRL player styles and
develop revolving archetypes?"*)

Adding coaches raised three complaints worth recording, because two were
calibration errors of the same family as the development one above.

**1. Net play was under-weighted for THIS format.** Owner: *"the net thing is so much
more crucial in this version than in the college game."* Correct, and measurable: the
pro tie is **3 men's singles + 3 women's singles + 3 mixed doubles = 9 lines, first to
5** (`engine/gtt.py`). Doubles is **a third of every tie**, against one point of seven
in a college dual — and `engine/doubles.py` reads `net_play` (0.34), `poaching` (0.38),
`volley_touch`, `overhead` and `doubles_chemistry` directly. Treating net as one bucket
among five was wrong by roughly 2.3x. `playstyles.FORMAT_WEIGHTS` now states the
format's demands explicitly instead of pretending every attribute is worth the same
everywhere.

**2. The style vocabulary was too coarse.** The `Coach` model's existing
`offensive_style` — balanced / serve-first / baseline / counterpunch / all-court — puts
most of the professional game in "baseline" and a handful of specialists in
"serve-first", so nearly every club landed in the same two buckets. Replaced by ten
real-tennis archetypes in `app/playstyles.py`, each a WEIGHTED attribute map rather
than a flat set (a serve-and-volley staff builds the volley harder than the overhead;
flat sets move every emphasised attribute identically, which reads as a bulk buff, not
a style).

**3. Styles are now REVOLVING.** `era_for(year)` cycles a prevailing meta every
`ERA_LENGTH` (6) seasons — serve-and-volley, then power baseline, then athletic
defence, then heavy topspin, then junk/big-serve — and new staffs are pulled toward it
at `ERA_PULL` (0.65), never locked to it. Counter-trend clubs are what seed the next
era. A club keeps the identity it was hired with for the era's duration.

### Measured

Six seasons of one graduate at two different clubs:

```
net-poacher club   poaching +11.1  net_play +11.1  doubles_chemistry +11.1  shot_tolerance +0.0
topspin-grinder    shot_tolerance +7.4  consistency +7.4  stamina +6.6  net_play +0.0
```

And the shaping is a SPECIALISM, not a buff — the net-shaped player's pair beat the
unshaped pair **57% over 300 doubles matches**, while the same player in **singles was
47%** (noise around even). A doubles club makes doubles players. In a format where a
third of the lines are doubles, that is a legitimate way to build a whole roster.

## Round 3 — the movement economy (owner: *"people get released and it's unclear
what happens to them"*)

Measured first, 8 teams over 16 seasons with real rollovers:

```
yr   total  rostered  free agents  retired
 0      92        80           12        0
 8     168        80            0       88
15     215        80            0      135
```

**The free-agent pool drained to zero by year 8 and never recovered**, so the waiver
wire had nothing to sign and the whole add/drop economy silently stopped existing —
which is exactly why released players felt like they vanished. Owner diagnosed the
cause better than the measurement did: *"that's a vestige of you not bringing over
more players from college... most drafts have a surplus of players."*

Two constants caused it. `GRAD_D1_SHARE = 0.95` excluded the lower divisions from the
pipeline by design, and `WAIVER_POOL_* = 6` sized the surplus as a fixed +6 on top of
open roster HOLES. The generated top-up then filled only to `needed`, never to the
pool target — so year 0 had a surplus and every year after had exactly enough bodies
for the rosters and nothing spare.

### What landed

- **The draft leaves a surplus, sized per club** (`DRAFT_SURPLUS_PER_CLUB`), and the
  top-up fills to the POOL target rather than the roster holes.
- **Two draws, different division mixes.** The roster-filling slice stays D1-dominant;
  the surplus that becomes the wire is mostly D2-D4 (`GRAD_D1_SHARE_SURPLUS = 0.25`) —
  they graduate far more players than the pros can ever use.
- **Rosters lock for the season** (`ROSTER_LOCK`). The only in-season signing covers a
  player out for the YEAR. No week-to-week churn on form.
- **Unsigned free agents retire** after `FA_SEASONS_BEFORE_RETIRE` seasons — counted in
  seasons, not weeks, because a player cut in week 3 stays signable to the off-season.
- **Coaches come from finished careers**, in a pool deliberately larger than the number
  of clubs, with a carousel (vacancies, upgrades, and staffs nobody hires leaving). The
  year-zero synthetic staffs retire after one season, so from year one every job belongs
  to someone you watched play. `best_fit()` infers a coaching archetype from how they
  played, which makes the eras causal rather than a fixed cycle.
- **Retired players are pruned** after `RETIRED_KEEP_YEARS`, except Hall of Famers and
  coaches, who are permanent.
- **Alumni view** (`/gtt/alumni`) — everyone past college in one place, filtered by
  playing / free agent / coaching / Hall of Fame / retired. Deliberately a QUERY over
  the live tables and not an archive table: a second copy of the truth is what made the
  cup preview disagree with the cup archive earlier in this same PR.

### Measured after (12 teams, 14 seasons)

```
yr   total  rostered  free agents  retired  in-season moves
 0     216       120           96        0                0
 7     649       120           99      430                7
13     943       120          100      723                7
```

The wire holds ~100 instead of collapsing to 0, and in-season movement is a trickle of
7 across a decade instead of weekly churn.

### A calibration miss of the same family, caught in testing

Deepening the free-agent drain meant ~100 players retiring per year, and
`COACH_INTAKE_SHARE = 0.35` of that turned the coaching pool into a second landfill
(58 coaches for 6 clubs). Capped per club. Same lesson as the others here: a share
that is sane against one population is absurd against another.
