# AAR — porting the Varsity Apex design into Play to Clinch, the type scale, and a test suite that was not hermetic

Three requests in one session — bring the Apex look across, make the text
readable, fix a failing test — and the third turned out to be the biggest thing
in the run by a wide margin. It also turned out to be the cause of the failing
test, which is the part worth reading.

---

## 1. The scoping answer was mostly right, and wrong in the expensive place

The owner asked how hard it would be to port the design. I measured both sides
before answering, which was right, and I answered in three tiers: palette+type
(a day), fonts (a licensing question), components (1–3 weeks).

Two of those numbers held. The thing I got wrong was **which parts are portable**,
and I only found out because I sent a second pass over prep-network:

- **The tables do not port at all.** `.fh-table` / `.fh-row` carry no column
  definition in CSS. Every row and header gets `style='--grid-cols: …'` written
  inline by Python from 20+ call sites. Ship `style.css` alone and every table in
  the system collapses to one column.
- **The hardest component was already solved.** Apex's bracket is
  server-positioned from `app/postseason.py` — which is exactly
  `state._bracket_canvas` + `_bracket.html` here. Both apps independently arrived
  at the same architecture, so the component flagged as un-portable was the one
  that needed no porting.
- **The port is not one-directional.** Apex has NO spacing scale at all, 27
  literal font-sizes against a 6-token scale, and 15 raw radii. This app's token
  layer is the more disciplined one in those dimensions. It is a merge, not a
  transplant.

**Lesson.** "How hard is X to port" is answered by the COUPLING, not by the
size of the files. Line counts and token overlap (32 shared names — both were
built to the same "components read aliases only" rule) made it look like a
palette swap. What actually decides it is what the markup supplies at runtime
that the stylesheet assumes.

---

## 2. The readability complaint was measurable, and much worse than it looked

> "it's extremely hard to read right now because the text sizing isn't
> especially readable where it needs to be"

Measured before touching anything — **768 px font-size declarations against a
12-token scale that was used SEVEN times**:

| band | count | share |
|---|---|---|
| under 10px | 33 | 4.3% |
| 10–11.5px | 232 | 30.2% |
| 12–13.5px | 337 | **43.9%** |
| 14–15.5px | 64 | 8.3% |
| 16–19px | 41 | 5.3% |
| 20px+ | 61 | 7.9% |

**78% of all type was under 14px; 34% under 12px.** 31 distinct sizes, seven of
them half-pixel steps. The body was 14px and almost nothing inherited it.

The fix was mechanical — 733 declarations raised on a documented mapping with a
hard floor of 11px, reserved for uppercase tracked labels — but three things
about it are worth keeping:

- **The token scale had to move with the literals.** Raising only the sweep
  would have left tokened text SMALLER than swept text, inverting the hierarchy
  in exactly the places that used the system correctly.
- **Fixed grid columns are sized against the type they were designed with.**
  Seven column sets were measured against 10–12px and would have clipped.
- **A scale that exists but is not used is not a scale.** Twelve tokens, seven
  usages, 31 real sizes. The document said one thing and the app did another,
  and only counting told the difference.

### 2b. And then it broke the crests — the exception that proves the rule

Reported after the sweep: four-character abbreviations (WAKE, TAMU, MICH, NCST)
spilling out of `.bl-crest.xs` over the school name beside them. The sweep took
that box's text from 9px to 11px; the box is a fixed 20px square and
`.bl-crest` clipped nothing.

**A crest is an ICON, not prose.** Four glyphs of 800-weight display type only
physically fit a 20px box at ~9px, and raising the type would mean widening
every crest box, which widens every dense row in the app to make a decoration
bigger. So crests are the one thing exempt from the raised scale — and the real
fix is `overflow: hidden`, which is a GUARANTEE, where "9px fits four
characters" was only an assumption about label length. Audited every fixed-size
box in the CSS for the same shape; three had it.

**Lesson.** A global type change is safe for prose and unsafe for anything
inside a box the layout has already decided the size of. Sweep the first, list
the second.

---

## 3. The suite shared a database with the app

`test_season_awards_structure` had been failing, and I had correctly established
it was pre-existing (it fails identically at the commit before this work). What
I nearly did was stop there.

> **Correction, from the owner, after I wrote this up as data loss:** *"i never
> keep the same tennis.db so that's not important it never is."* They rebuild the
> sim from scratch on every reload. I had found a real bug and then rated it on a
> cost the owner does not pay — the dramatic framing ("the suite is deleting your
> save") was wrong, and worse, I put it in `CLAUDE.md` where it would have set a
> false priority for every later agent. **The severity of a bug is a fact about
> the user's workflow, not about how alarming the mechanism sounds.** Ask, or say
> plainly what you do and don't know about the cost.

The bug is real and the fix stands; the reason is HERMETICITY, not preservation.

The chain:

1. `app.dbpath.resolve_db_path()` returns `$TENNIS_DB_PATH` or the repo's
   `./tennis.db`.
2. `app.world.WORLD_DB = resolve_db_path()` — **the world shares that file.**
   One database, separate tables.
3. The `played_season` fixture calls `world.reset()`, whose first statement is
   `DELETE FROM world`.
4. `./tennis.db` was a real 218 MB save sitting in the repo root, gitignored.

**So every run of the suite read and wrote whatever was in that file.** Its
results depended on the developer's disk rather than on the code — which is
exactly why the awards test failed: a world reset with the played SEASON rows
left behind means the season's ~4,600 player pids refer to people the roster
generator no longer produces.

Measured to be sure, rather than reasoned about:

```
season pids       4596
current roster    4596
pid overlap          0
name overlap         3  (of 600 — coincidences)
```

`_eligible` resolved none of them, `continue`d past every one, returned `[]`,
and every All-American tier came back empty **on a fully played season**.

Two fixes, because there were two faults:

- **The suite gets its own database**, set in the root `conftest.py` before any
  `app` import — so a run is a statement about the code and not about leftovers.
- **`_eligible` stopped degrading silently.** Every pid failing to resolve is a
  FAULT, not a result. It now says so in the log instead of rendering a clean,
  plausible, completely wrong "nobody was honored".

**Lessons, and they are the durable ones from this session:**

- **"Pre-existing" is a statement about WHEN, not about WHETHER IT MATTERS.** I
  established the failure predated my work and was ready to hand it back
  labelled. The owner said "that's a big problem" and was right: the test was
  the only visible symptom of a suite that wasn't hermetic. Bisecting to "not
  mine" is the start of a diagnosis, not the end of one.
- **When a failure makes no sense, measure the two things that disagree.** The
  awards code was correct. Comparing the two pid sets — same size, zero overlap
  — pointed at the world in one step, where reading `_eligible` more carefully
  would have pointed at nothing, because there was nothing wrong with it.
- **A silent `continue` over unresolved identifiers is a data-loss detector
  wired to no alarm.** This codebase already has a rule about graceful
  fallbacks turning a should-be-crash into plausible-looking wrong data
  (`CLAUDE.md`, world resolution). Same shape, different module.
- **Anything that resolves to a default path can resolve to a shared one.** The
  fallback in `dbpath` exists so the app never fails to boot — a good rule — but
  the same call in a test process silently joins the suite to the app's state.
- **Do not inflate a bug's severity to match how alarming its mechanism is.**
  See the correction above; I wrote a real hermeticity bug up as data loss, and
  put that framing somewhere durable.

---

## 4. The schemes

Ten light schemes now, in both repos. Four palettes came from the owner: three
replaced an existing scheme in place (`meadow→clay`, `banner→ember`,
`evergreen→floodlight`) and one was new (`laurel`).

**Every slot was measured against its own ground before it was written down.**
That is this file's existing discipline and it earned its keep immediately:

- **Clay is the only scheme whose palette contains no ink.** All five colours
  are light or mid tones; the darkest, muted-olive, is 1.8:1 on the ground.
  Dropping them into the slots would have produced a scheme with unreadable body
  text and no error anywhere. The ink (11.7:1) and link (6.8:1) are DERIVED by
  pushing the olive and pink hues down; the five as sent keep the ground, band
  and accents, where their lightness is the point. Neon-pink survives unmodified
  as the mast rule — the one place 3.7:1 is enough, because it sits on the dark
  bar.
- Ember, Floodlight and Laurel needed almost nothing (bordeaux 13.7, iron 7.8;
  shadow 17.5, indigo 11.6; evergreen 13.2, crimson 12.2 — all at the hex given).
- Four rank/grey slots came in at 3.4–4.4:1 on the first pass and were darkened
  until they cleared AA.

Three things about the port into this app:

- **The alias layer did the work.** ~950 existing `var()` references kept working
  because each was re-pointed at a slot. Both codebases had held to "components
  read aliases only, never raw values", and that single rule is what made a
  ten-palette system a same-day change instead of a rewrite.
- **Win/loss stays green/red in every scheme, deliberately.** They are the only
  colours in the app carrying MEANING rather than identity. A reader should not
  have to relearn a result cell because they changed palette.
- **A dozen short aliases were referenced but never defined** — `--surface`,
  `--border`, `--text`, `--pos`, `--neg`, `--stat-bad` — so their hard-coded
  fallbacks won every time. Nothing looked broken and nothing would have: they
  would simply have sat at a fixed light colour while every scheme changed around
  them. That is precisely how a palette ends up looking half-applied, and it is
  invisible until you diff defined-vs-referenced.

### The two ways a picker ships broken, both of which happened

1. **Markup without CSS or a listener.** I committed the picker's `<details>`
   block on its own; it rendered as a bare disclosure triangle whose rows did
   nothing. Every palette was present and none was reachable.
2. **A swatch is keyed on the scheme NAME.** Renaming three schemes emptied
   their chips in prep-network — the row still rendered, the palette still
   applied, and the one element in the menu whose entire job is to show you the
   colours went blank. Caught from a screenshot, not from code.

Both are the same failure: a feature whose parts live in three files, verified
in one of them.

---

## 5. Traps for later

- **`tokens/fonts.css` owns the font families; `tokens/typography.css` owns
  sizes.** They both declared families once, and typography imports second, so
  it silently won.
- **`url()` inside an `@import`ed sheet resolves against THAT file's directory.**
  `../fonts/` from `/static/css/tokens/` is `/static/css/fonts/`, which does not
  exist, reports nothing, and falls back to Helvetica.
- **Crests, rank pips and any other fixed-size box are exempt from the type
  scale** and must clip.
- **Never let a test process resolve to the app's DB path.** The root
  `conftest.py` guard is load-bearing; without it a test result is a statement
  about the developer's disk rather than about the code.
- If a season's awards are empty, check the log for the unresolved-pid error
  before looking at the selection code. It is almost certainly a world/season
  mismatch, not a selector bug.
