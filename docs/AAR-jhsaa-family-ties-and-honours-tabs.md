# AAR — JHSAA family ties, and the honours panel split (2026-08)

Two owner asks in one pass: the **ability to associate two players as family**
(siblings, twins, cousins, and — in a long save — a former player's child), and a
school page whose honours list had grown past readability.

## What was built

**Family ties** (`overrides.set_jhsaa_family`, `jhsaa.family_add`/`family_for`/
`family_remove`, the Family block on the player page):

- **Metadata, never a naming mechanic — and that is a requirement, not a taste.**
  `world_jhsaa_dual.lines` archives player NAMES, and `state._jh_line_records`
  keys the season-record lookup off them, so rewriting a surname would silently
  zero a player's archived record. A tie links two pids and renames nobody, which
  makes that bug impossible and needs no era gate (nothing about generation
  changes). Verified by capturing a player's season records before and after
  linking: byte-identical.
- **No generator, no suggestion pass, no candidate scan — owner rule, stated
  twice.** The owner associates players personally, from the player page: a
  roster picker (school defaults to this one, season to now), a relation, done.
  Measurement that made this the right call: the frequency-weighted US name draw
  already gives ~1 in 10 programs a natural same-surname pair, so the raw
  material exists without any mechanic. Do not add a scan later; it is the one
  thing the owner explicitly rejected.
- **One row per family** (`roster_overrides` kind `jhsaa_family`, opaque id —
  never a slug with a school name in it; schools get renamed). Members carry a
  denormalised `name`/`school`/`entry` so a tie renders when the other member is
  not enrolled at all (a parent, a graduate). Older/younger/twin is DERIVED from
  entry years, never stored.
- **Cross-gender, cross-school, cross-era all work by construction** — a pid is
  `f(school, gender, entry, seat)` over deterministic rosters, so any two pids
  ever generated can be tied. All four shapes verified through the real routes.
- **Doubles nudge** `FAMILY_CHEMISTRY = 0.025`: ~¼ sd of the measured
  `doubles_rating` spread (0.36–0.75, sd 0.10) added to a family pair's score in
  both arrangers — a tiebreak, never a mandate, and `_order_pairs`' rank-sum
  boundary still runs after it, so anti-stacking cannot be violated. The per-team
  `family_ids` map is resolved ONCE in `district_teams`, never per dual (the
  play-up fingerprint-storm rule).

**Honours panel** (`jhsaa_school.html`): Team trophies and Player honours are now
two tabs of one panel (`jh_tabs`, the district page's macro); the Program card
moved from a starved third column to full width above the ledger it folds; subcopy
renders only where it adds information; the all-time COURTS metric was deleted
(nobody tracks a program's career individual-line record).

## Bugs found on the way — each verified, none guessed

1. **Resolving a pid under the wrong salt returns the WRONG PERSON, not an
   error.** `make_pid` does not fold in the salt but the name draw and
   `_freshman_class_size` do — so `_resolve_member` with a defaulted `salt=""`
   found the right pid and stored a stranger's name on the tie ("Janet Allister"
   for Kanika McNeal). Fix: the salt is never defaulted; unset means "resolve
   from the world". The general lesson repeats this codebase's oldest one: the
   dangerous failure is the one that RETURNS plausible data.
2. **Each member of a tie needs its OWN (gender, year, school) context.** One
   shared context is wrong in exactly the two cases the feature exists for —
   cross-gender and cross-era — where the second member lives on another
   gender's roster or in another season. Sharing didn't misresolve; it failed to
   find the member, which is how it surfaced.
3. **`_jh_scope_args()` reads `request.args` — on a POST there aren't any.** The
   family route took the page gender from scope and got the universe default
   ("boys") for a girls' player, so every association failed. `editor_jhsaa_
   transfer` already read `gender` off the form for this exact reason; the new
   route now does the same. When adding a JHSAA POST route, the scope helper is
   for GETs.
4. **(codex) A TOC finish was filed under Player honours.** `_season_row`
   appended "Tournament of Champions — Semifinal" to the individual `honors`
   list — harmless while the panel was one undifferentiated scroll, wrong the
   moment it split into tabs. Team-level text now lives in its own
   `team_honors` list. A list that mixes two kinds is a latent bug waiting for
   the first reader that distinguishes them.
5. **(codex) The active tab was the empty one.** `jh_tabs` activates the first
   pane, and most programs have player honours but no team trophy — those pages
   opened on "No team trophies yet" with every real honour hidden. The panes are
   now ordered by which has content. When tabbing an existing list, check what
   the COMMON page looks like, not the decorated one.

## Verified

Four tie shapes (same-team / cross-school / cross-gender / cross-era) through the
real routes with stored names checked against the generated rosters; archive
byte-identical before/after linking; 272 honour-bearing programs rendered with
zero empty-first-tab pages and all 8 TOC finishes in the team pane; roster chips
render; `family_remove` collapses a two-member family.
