# AAR — JHSAA rosters thin enough to force double-booked lines

## The report

Owner, on a multi-year JHSAA Lab advance: Baptist (1A) showed up with **9 players**
on the 2029 roster. The regular-season league card needs 11 distinct players (S1,
an 8-player doubles pool at #2-#9, S2, S3) — nine wasn't enough, so the same player
was appearing on two lines of the same dual at once. Against the actual rules of
tennis, and it corrupts that dual's stats permanently once the season is archived.

The owner's first read was that this was the JHSAA Lab specifically not running the
roster-generation code — "I specifically told the agent that teams should be
generating more players and there's code for this, it just must not be running for
the jhsaa only sim." A reasonable diagnosis from the symptom, and wrong in the
specific way that made it worth writing down: the generation code **was** running,
correctly, every time. It just had no floor under it.

## Two things it was not

**Not the JHSAA Lab.** `jhsaa.build_roster` is a pure function of `(school, year,
salt)` — no database, no world state, nothing that could behave differently in a
lab process versus the real app. Whatever built Baptist's roster in the lab is the
exact same code path a normal `/world/advance` run uses.

**Not play-up.** Baptist plays up (1A enrolled, competing at a higher class), and
the owner flagged play-up as worth checking as a route. It wasn't: `_freshman_class_
size` — the only place roster depth is decided — takes `school.classification`,
never `school.group`. Playing up moves which teams you play, never how many players
your program fields. Confirmed by reading the call site, not by assumption: one
argument, `classification`, threaded through `build_roster`'s per-grade loop to
`roster_size`.

## The actual gap

`ROSTER_SIZE_BY_CLASS` gave each classification one target number (1A: 13). Depth
comes from `_freshman_class_size`, which rolls **each of the four grades
independently**: `target/4` per grade, Gaussian, `std = target * 0.35`. For 1A that's
a mean of 3.25 per grade with a standard deviation over a third of the mean — real,
substantial downside variance, and it compounds across four independent rolls in a
single graded roster rather than averaging out.

Nothing summed the four grades and checked the total against what the season's
biggest card actually needs. Measured directly (no season simulation required —
`build_roster` is pure and cheap to call standalone): **13 of 90** sampled 1A
`(school, year)` combinations landed below 11 without a floor. That's a real ~14%
rate, not a rare edge case, and it explains the report exactly: play a lab world
forward enough seasons and sooner or later a small classification's independent
rolls conspire to break the card.

The double-booking itself was the *engine* correctly avoiding a crash — `_squad`'s
`at(i)` wraps (`r[i % len(r)]`, "degrade, never crash, on a short side"), the same
philosophy the college side uses for genuinely short sides (`dual._court` clamps,
`gtt._slot` wraps). It's a good fallback for injuries or transfers eating into a
roster mid-career. It was never meant to be the thing standing between a normal
roster and a legal dual.

## The fix

Two changes, `app/jhsaa.py`:

1. **`ROSTER_FLOOR = 11`** — the regular-season 3S/4D card's distinct-player count,
   the largest single-dual requirement anywhere in the JHSAA calendar (the early
   5S/2D window and the 1S/4D postseason both need only 9). `build_roster` now tops
   a short roster up to this floor by growing **only the current year's incoming
   freshman class**, continuing its own seat numbering. Never grades 10-12 — their
   sizes are already fixed from a *prior* year's `_freshman_class_size` roll, and
   `_freshman_class_size` is documented as "rolled once per (school, entry_year)";
   touching an already-rolled grade would violate that contract and could desync
   from anything already archived against that class (an award row, a career page,
   a pid another table points to).

2. **Depth is a BAND per classification, not one number** (owner rule: "we can go
   bigger… 9A and 8A can go 20-24, 7A-6A 19-22, 5A-4A 18-20, 3A 17-19, 2A 15-17, 1A
   14-16"). `ROSTER_SIZE_BY_CLASS` became `ROSTER_SIZE_BAND_BY_CLASS`, and
   `roster_size(classification, school_key, salt)` draws **one stable point per
   program** inside its band — seeded on the school alone, never the year, so a
   program's typical depth reads as a durable trait (the same idiom the recruiting
   budget bands already use) rather than something that reshuffles every season.
   Every band sits at or above the old flat target; the bottom of the ladder (1A,
   2A, 3A) moved the most, which is exactly where `ROSTER_FLOOR` was getting hit.

`roster_size` had exactly one caller (`_freshman_class_size`) before this change, so
widening its signature (`classification` → `classification, school_key, salt`) was
safe; a bare `roster_size(classification)` call still works and returns the band's
midpoint.

## Verified

`build_roster` needs no database and no simulation to call — every check here ran in
under a second, not the ~10 minutes a real JHSAA season costs:

- Baptist across 10 simulated years, post-fix: roster size never drops below 11
  (samples ran 14-18).
- 800 `(school, year)` samples spanning all nine classifications: **0 under the
  floor**, band midpoints all landing within a point or two of the configured
  range.
- The band-vs-flat-target comparison above, confirming every classification moved
  up or stayed level, none moved down.

Not addressed, and not asked for: seasons already archived under the old code (a
lab world advanced before this fix) may already contain a double-booked dual. The
owner's call — "not worried about past data, it was a small enough problem" — this
fix is forward-only, same as every other JHSAA generation change; nothing here
rewrites archived duals.

## What to check first if this looks wrong later

- If a roster is *still* short of 11 after this fix, the cause has moved outside
  `build_roster` — most likely a JHSAA transfer (`set_jhsaa_transfer`) pulling a
  player out mid-career, which removes unconditionally in `build_roster`'s
  transfer-out loop and isn't covered by the floor (the floor only tops up the
  *generated* count, before transfers are applied). Transfers are manual/editor-only
  today, not something the sim itself triggers, so this is a low-probability path —
  but it's the next place to look, not `_freshman_class_size` again.
- `ROSTER_FLOOR` is a **structural minimum** tied to the regular-season card shape,
  not a depth preference — don't raise it to mean "more bench," and don't lower it
  without checking `jhsaa.dual_format`'s biggest card first.
- If `roster_size`'s per-program band draw ever needs to change (e.g. a new
  classification), remember it's keyed on `school_key` alone — changing the seed
  string reshuffles every program's stable depth at once, the same footgun a
  recruiting-budget reseed carries.
