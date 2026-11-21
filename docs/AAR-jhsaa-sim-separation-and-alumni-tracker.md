# AAR — separating the JHSAA sim from the college game, and the alumni tracker

## The report

Owner, 2026-11: *"i haven't played the college version of this in a long time, and
when i tried today, the JHSAA sim took so long to get past its first season that i
never got to get back into the college game."* Two asks followed: stop the
high-school season from overtaking the college sim, and find a way to play the
high-school sim with college "in the background with just like players/results/no
backlog bloat."

The decisions, in the owner's words:

- *"Jefferson can stay a state, its high schools real, but the JHSAA sim should just
  be separate from the college game."*
- On following Jefferson kids into college: *"what i actually want then is just the
  alumni tracker … as a finished product rather than real time seasons."*

## What was measured

All on a fresh save in a 4-core container. Absolute numbers will differ by machine;
the proportions are the finding.

**The week-0 JHSAA step: about 18 minutes, on the request thread.**

| Stage (both genders) | Time |
|---|---|
| Varsity regular season | 5.8 min |
| JV season | 5.6 min |
| Roster builds | ~2 min |
| Individual state tournaments + JV individuals | 1.7 min |
| Next season's portal prep (`write_provisional`) | 1.4 min |
| Mixed doubles | 1.0 min |
| Postseason, showcases, awards, archive writes | ~1.5 min |

One season wrote 220 MB: 102 MB of talent pins, 42 MB of preseason state, 33 MB of
duals.

**The hidden second season.** Building one gender's college recruit class in a
fresh process took **460 seconds, 457 of them replaying the high-school season** —
to fill 208 Jefferson slots out of 2,500. `jhsaa.apply_to_class` gets its seniors
from `run_season`, which is memoised per PROCESS. `world.prime_recruit_classes`
builds each gender's board in a SPAWNED worker (`app/parallel.py` uses a spawn
context on purpose), so the memo is always empty there. The same replay ran at
every boot warm. A new college save was about 26 minutes from its first click to
its first dual, and paid the same every year after.

This is rule 6 of the cache section in CLAUDE.md ("a read-only path must READ,
never RESIMULATE") arriving through a process boundary instead of a page: the memo
made the hand-off look free, and it was free only in the one process that had just
played the season.

**College on autopilot: rejected on the numbers.** One hands-off college year on
the fastest settings (fast match model, box stats off) took **10.0 minutes with
only D1 active** — first week 2.9 min, 26 weekly steps 5.3 min, awards 1.3 min,
cups + rollover + pros 0.3 min. With all four divisions it was running about 55
seconds a week (~25 minutes a year) when it was stopped. On top of an 18-minute
high-school season, per year.

## What changed

### 1. The JHSAA sim is separate from the college game

- **`worldconfig.jhsaa_sim()`** — a per-save switch, **off unless a save turns it
  on** (World hub pill, `POST /world/jhsaa-sim`).
- **`world.advance_week`** runs the JHSAA rung and consults the two JHSAA holds
  (reclassification, rising-freshman portal) only with the switch on. The advance
  button's label follows the same condition.
- **`world.recruit_class`**: with the switch off, Jefferson recruits keep the name,
  ability and pid the national class generated and get a real, current JHSAA school
  (`jhsaa.assign_real_schools`) — a program sponsoring that gender today, drawn by
  enrollment, in the recruit's own town when it has one. Both boards build in about
  1.5 seconds with no season simulated. No high-school record, because none was
  played.
- With the switch on, the senior hand-off is reached only for a class whose season
  the save has **archived**, and the rung evicts that year's cached classes.
- The boot warm no longer builds the JHSAA scouting census for a save with no
  archived season.
- The JHSAA lab never reads the switch.

### 2. The alumni tracker (`app/jhsaa_college.py`)

For a world with no college in it. When a class graduates, its best 200 seniors a
gender each get a real college program and a finished four-year line: lineup
position and singles record per season, peak position, career record, honours.

- **Not a simulation.** Placement deals the class into divisions in proportion to
  the seats each turns over (programs × roster cap ÷ 4), best ranks first with a
  blurred border, then into a program near the senior's standing, with a small
  pull toward in-state and western programs. The line comes from the fit between
  player and program plus per-player rolls on the pid's own rng stream.
- **Written once** (`world_jhsaa_college`, keyed on the pid) and only read after. A
  retuned constant reaches classes that have not graduated yet.
- **Older classes fill in from the alumni index.** `jhsaa_alumni` already holds
  every senior of every season since coaches landed, with the rating they left on,
  so a class from before the tracker is built the first time it is opened — one
  class, milliseconds, no roster rebuilt.
- **Where it shows:** `/jhsaa/alumni` on the History sub-rail (the class is the
  season picked in the scope bar), a College panel on the player page, and
  `jhsaa_college.csv` in the research export.
- **Nothing reads it.** No rating, ladder, award or recruit board. It is not written
  for a world with college rosters.

## Lessons

**A memo is per process.** "The hand-off reuses this sim instead of playing a second
one" was true in the comment and false in production, because the consumer ran in a
spawned worker. When a design leans on a memo to make a second call free, ask which
process makes the second call. The durable fix on the switch-on path is still owed:
persist the graduating class at the rung and have the board read it.

**A stale list looks exactly like a working one.** `high_schools.json["JF"]` is the
generic generator's Jefferson school list, and only 122 of its 502 names are current
programs — the rest predate the association's renames. Every one is a plausible
school name, so nothing looked wrong. The college path now reads the live school
list. The file itself was left alone on purpose: `generate_prospect` draws from it
on the caller's rng, so resizing it can shift later rolls on that stream, and JHSAA
players are regenerated from seed.

**Measure the alternative before building it.** Autopilot was the more appealing
design and would have been weeks of work on top of a 10-to-25-minute yearly cost
nobody had measured. One driver script answered it.

**A measurement harness can be the thing that is broken.** The first college-year
timings were contaminated: the driver had no `if __name__ == "__main__"` guard, the
app's pools use a spawn context, and every worker re-ran the whole script against
the same database file. Two orphans kept playing duplicate seasons after the parent
was killed, which showed up as slow weeks, then "database is locked", then a
malformed database. The clean rerun was 10.0 minutes where the contaminated one was
heading for 14. Any script that calls into this app needs the guard.

**The time this took was itself a finding.** It was about 40 minutes before the
owner had a definitive answer, most of it spent waiting on runs that could have
been cut the moment the D1-only number came back. Report the first decisive number
when it lands.

**An eviction is not an invalidation while a build is in flight** (review finding,
fixed the same day). The rung evicted that year's recruit classes after archiving
the season, but a board build that had STARTED before the archive — the boot warm,
a recruiting page, the pool workers in `prime_recruit_classes` — would finish
afterwards and store its pre-archive class, where it stayed for the rest of the
process. Each year now carries a generation (`world._class_gen`): a builder notes
it before it starts and `_publish_class` stores only if it has not moved, check and
store under one lock. The serial build retries once so its caller gets the
post-archive class; pool results that crossed an invalidation are dropped and the
class builds at its next read.

## Not done, and known gaps

- **No full-size season has been played with the tracker on.** The wiring is covered
  with real `TeamSeason` objects and real rosters, not a played season: the scaled
  fixture in `tests/test_jhsaa_toc.py` fails to field a Ward on untouched code.
- **The full suite was not run.** The new tests pass (`tests/test_jhsaa_sim_switch.py`,
  `tests/test_jhsaa_college.py`). Three failures predate this work and fail the same
  way on untouched code: `test_universe_sync.py::test_there_is_exactly_one_advance_route`
  (it counts `/jhsaa-lab/advance`), `test_parallel_gen.py::
  test_enriched_class_reconstruction_is_lossless`, and the `test_jhsaa_toc.py` fixture.
- **The switch-on path still replays the season** in spawned workers and at boot.
- **Base-roster Jefferson players** (already in college at year 0) still draw their
  high school from the stale list.
- **The career-line constants are a first pass**, tuned by eye on synthetic classes:
  roughly a quarter of a class reaches No. 1 singles somewhere, about one in ten
  earns an honour, zero to three All-Americans a class.
- Classes filled in from the alumni index carry no ceiling or nationality, so their
  growth is rolled and the service academies are out of view for them.
