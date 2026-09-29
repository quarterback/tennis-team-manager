# AAR — JHSAA early participation, maturity, and the rising-freshman portal (rule 2100)

Owner spec 2026-09. Code: `app/jhsaa.py` (the `EARLY PARTICIPATION` block before
`_career_plan`, `career_ability`, `_gen_seat`, `build_roster`), `app/jhsaa_portal.py`,
`app/world.py` (both advance holds), `app/web/state.py` / `server.py` /
`templates/jhsaa_portal.html`, `app/research_export.py`. Tests:
`tests/test_jhsaa_early_participation.py` (a REAL archived season with the era pulled
back to the fixture's year — the `test_jhsaa_toc` shape).

---

## 1. What was asked, and what was decided

The question was whether 7th- and 8th-graders could join JHSAA tennis without
building a middle-school sport. Three shapes were considered and two were rejected:

| Considered | Decision | Why |
|---|---|---|
| A middle-school system (teams, districts, a postseason, ratings, a hand-off) | **Rejected** | Everything it would produce — a player who exists before ninth grade — the roster builder already produces for free (§2). |
| An intake / placement board (a youth recruiting game) | **Rejected** | The feeder is the school itself. Assignment is automatic; the one interactive moment is the portal (§5), *after* the two early years, when there is a real question to answer. |
| Cloning the college redshirt so a career "lasts six years" | **Rejected** | A redshirt repeats a class year and delays graduation. An early participant does not repeat anything — they are the same seat of the same future freshman class, seen two seasons sooner. Six seasons on one pid, no redshirt tag, no fifth year (§2). |

What shipped, in the owner's rules:

1. **Gate: 1A, 2A and Group 3** (`EARLY_CLASSES`), read against `classification`
   (what the school *is*), never `group` (where it plays). Group 1 and Group 2 were
   in the first draft and taken out: Group 1 is 1,066–2,556 enrollment (6A–9A
   sized), Group 2 is 407–1,059 (3A–5A). Small-school roster access is the rule;
   the three classes in the gate are enrollment 57–396.
2. **7th AND 8th** — "if 8th graders why not 7th". A 7th-grader is rostered six
   seasons.
3. **No JV-only rule.** Every squad level is open; the coach's ladder decides V1 /
   V2 / V3 / JV / does not dress. Nothing restricts them anywhere, and nothing had
   to be added to make that true.
4. **They count toward the roster floor.** A program that fields 7th- and
   8th-graders tops up fewer freshmen — it is not short of players.
5. **Development runs like everyone else's**, plus the one new thing bolted onto
   *every* player: **maturity** (§4).
6. **The interactive piece is a HELD portal** (§5): a rising freshman with no
   projected V1 seat at the school they played for is proposed a move.

---

## 2. Early participation — an 8th-grader is next year's freshman, rostered early

A JHSAA player is a recipe on `(school, gender, entry year, seat)`. Next year's
freshman class already exists deterministically — `_freshman_class_size` rolls it
once per `(school, entry)` — so an early participant is simply seat *k* of
`entry = season + 1` (8th) or `season + 2` (7th), appended to this season's roster.
Same pid, same name, same ceiling as the freshman they become; no new identity, no
hand-off, no feeder mapping. `build_roster` appends them **after transfers and the
exchange student and before the floor top-up** (they count toward it, owner rule).

**Eligibility is a projection of the class history, not today's map.**
`early_seasons(school, entry)` returns `()`, `(entry-1,)` or `(entry-2, entry-1)`.
A 7th-grade season needs the school in the gate *that season*; an 8th-grade season
needs it that season OR a 7th-grade season already played there — **grandfathered**:
a reclassification out of the gate never cuts a player the program already has,
and a new 7th-grader cannot enter a school that has left it.
`classification_in(school, season)` rewinds today's `classification` through every
committed `world_jhsaa_reclass_move` (one query per save, memoised, cleared by
`reset_schools()` — which a reclass commit already calls). ‼️ Archived rosters are
REBUILT, so an eligibility rule read off today's map would add or delete an old
season's 7th-graders the day a cycle moves the school — players the archived box
scores name. The cycle history is the record of what the class *was*.

**Era-gated on the season** (`early_era()` = `max(EARLY_PARTICIPATION_FROM,
_resolve_era("jhsaa_early_era"))`, the `exchange_era` idiom). In this section a new
roster ingredient is retroactive by default.

**The grade 7/8 recipe is the freshman recipe.** `_gen_seat` reads its maturity
tables at `mgrade = max(9, grade)` — a career-era player's ability is set outright
by `_apply_career`, and the tables are consumed for their rng draw only, so this
keeps the seat rng stream identical and never indexes `_MATURITY[7]`. Legacy-era
cohorts (`entry < career_era()`) never get early seasons at all; the legacy model has
no grade below nine.

**What else had to move for a grade below nine** (from a sweep of every 9–12
assumption in `app/`, `scripts/` and the templates):

- `career_ability` grew pre-high-school years (§3).
- The odometer asks for the early seasons too (`expo_ask` in `build_roster`) — only
  for a program that has any, so every other build asks exactly the three seasons
  it always did.
- `cohort_size` sizes an early cohort at its **first early season** (`cohort_horizon`),
  because `retention_extra` folds every archived season before its horizon: read at
  `entry`, the 7th-grade build and the freshman build would see different histories
  and a player on the 8th-grade roster could vanish at ninth grade under box scores
  that name them. `sibling_link`'s under-estimate uses the same horizon.
- `PROOF_GRADE` reads experience as seasons *in the program*: a freshman who played
  here as an 8th-grader reads as a sophomore.
- `_stamp_pot_estimate`'s "knowledge" counts the early seasons the staff watched.
- `jhsaa.career()` leads with the early years; the player page needed nothing (it
  walks every archived season and looks the pid up on that season's roster);
  `_JH_CLASS_YEAR` gained `7: "7th", 8: "8th"`; the players directory, the Talent
  Mismatch filter and the Lineup Lab pool admit 7/8; `world.jhsaa_career_wins`
  claims a mover's early seasons; `scripts/dev_model_access_experiment.py` filters
  to grade ≥ 9 (its access models raise a negative offset to a fractional power).
- Transfers: an inbound mover's `_gen_seat` is handed `early_s` and `fire_expo` —
  the seasons they actually played, at whichever school `transfer_school` puts
  them in each — so the head start and any maturity event follow the player.

**Deliberately unchanged:** `GRADES` stays `(9, 10, 11, 12)`. It divides the
roster-size target and the retention term and bounds every enrollment window;
adding 7 and 8 to it would resize every cohort in the association. Early grades are
`EARLY_GRADES`, looped separately. The JV individual events stay grades 10–12.
`jhsaa_recruit_class` takes grade 12 and is unaffected. `world.jhsaa_underplayed`
(the transfer board) stays at grades 9–10.

---

## 3. Development before ninth grade

`career_ability` is a start, a peak and four yearly capacities, each capacity
realised at the odometer's rate. The career plan's freshman **start** is now read as
"a kid who went through 7th and 8th grade at `EXPO_FLOOR`" — adolescence happens
anyway, which is exactly what every program *without* early participation shows.
So, for an early participant:

- two pre-HS capacities are drawn on their own stream (`_early_caps`, the
  `jhsaa-career` idiom, `CAREER_BIG_RATE`/`_BAND`/`_STEP_BAND`);
- a 7th-grader sits their floor-realised total *below* the start (scaled, never
  clipped, to keep them above `EARLY_FLOOR` × peak — the path stays continuous);
- each early season realises at its own odometer rate, times that season's staff
  development multiplier;
- at ninth grade they arrive `Σ cap × (x − EXPO_FLOOR)` ahead of the start — the
  same formula every high-school year uses. **Never behind it**: a rostered kid who
  never dressed realised the floor, which *is* the baseline.

A season with no archive reads FULL (the odometer's own convention) — what a
transfer built without `expo_years` must see so it never loses a head start.

---

## 4. MATURITY — what it is for, and how it works

### What the owner asked for (this is the contract)

> "an additional thing bolted onto every player called maturity, a new attribute
> that ONLY FIRES on 7th, 8th and 9th graders … if the kid plays a lot of matches
> that year it essentially can roll for them a boost to their POT/OVR up to a limit
> … players sometimes develop later and not everyone shows up a 80 OVR player …
> sometimes a kid who slotted as a 30 turns into a 60+ … the odometer mileage
> happens at a faster rate for varsity appearances than JV ones"

Then three corrections, each of which changed the mechanism:

1. **"Playing time affects the probability of a maturity event."** Only the odds.
   Nothing about the *size* of an event reads playing time.
2. **"A maturity event primarily reveals additional POT; it may also produce a
   smaller immediate OVR growth-spurt effect, but POT and OVR increases should not
   be mechanically coupled. Results do not affect maturity."**
3. **"The gains should be modest for most, but can increase a lot YoY; 7th grade
   year to 8th grade it should be capped at 6% up to hundredths, then 8th to 9th it
   can be more and same for 9th to 10th. DOESN'T preclude them from starting out
   elite as well."**

The first draft was wrong on (2): it scaled the *generated ceiling* by a boost and
let `_apply_career` scale current ability with it — POT and OVR moved together by
construction. It was rebuilt.

### The mechanism (`player_maturity`, `maturity_events`, `career_ability(bloom=)`)

- **Every player** carries a hidden `maturity` in 0–1, the square of a uniform on
  its own rng stream (`jhsaa-maturity`): most are low, a few are high. It never
  moves. It is exported (`players.csv: maturity`) and never shown on a page.
- In each **archived** 7th-, 8th- and 9th-grade season the player was rostered for
  — for every program in the association the freshman year, for an early
  participant all three — a **maturity event** rolls on its own stream
  (`jhsaa-bloom|…|grade`):
  `P(fire) = MATURITY_RATE (0.35) × maturity × played`
  where `played` is that season's exposure-odometer share, 0–1 (`EXPO_FLOOR`
  rescaled away; a varsity appearance counts double a JV one — the odometer's own
  `EXPO_JV_UNIT`). Results, opponents, wins: none of it is an input; there is
  nowhere in the signature to put one.
- An event does **two independent things**, each its own draw off that stream:
  - **POT reveal**: `MATURITY_POT_CAP[grade] × u²`, rounded to the hundredth of a
    percent, as a share of the BASE ceiling — caps **7th → 6.00%**, 8th 15%, 9th 15%.
    `u²` is what "modest for most, a lot for a few" means in one line. It never
    reads talent: an elite freshman blooms as readily as a 30.
  - **Growth spurt**: `MATURITY_POT_CAP[grade] × U(0.10, 0.50)`, as a share of the
    base career peak, added to ability at once. Tied to the grade's cap so it stays
    the smaller effect *without* being derived from the reveal.
- **How the reveal becomes ability** (`career_ability`): the career peak rises by
  `pot × base peak`, and `MATURITY_REALISE` (0.50) of the new headroom joins the
  player's yearly capacity, spread evenly over the growth years left through grade
  12 — so it is realised the way every capacity is, at the odometer's rate. A
  revealed ceiling with no playing time behind it is realised slowly; that is the
  point of routing it through the capacity rather than adding it to OVR.
- **History only.** An event is read off the archived season, so it moves builds of
  the seasons AFTER it and never the season it happened in. Nothing is stored: the
  event is a deterministic function of `(pid, grade, played)`, and `played` is in
  the archive.
- **From `early_era()`**, and `MATURITY_ENABLED` is the kill switch.

### What the numbers imply (compute before you retune)

- With `E[maturity] = 1/3`, a **full season fires ~11.7%** of the time
  (0.35 × 1/3), a bench season (`played ≈ 0.1`) ~1.2%. A freshman who plays a full
  varsity season has roughly a 1-in-9 chance of a bloom; an early participant who
  plays three full seasons has ~30%. Across ~5,900 freshmen a gender-season, expect
  a few hundred 9th-grade events a year.
- **Mean reveal on a fire** is cap/3: **2% at 7th, 5% at 8th and 9th**; the
  ceiling-most case is 6% + 15% + 15% = 36% over three seasons. The measured
  fixture path for a maximal bloomer on a 60 ceiling: senior ability 57 vs 44 with
  no events (`test_a_reveal_lifts_pot_and_a_spurt_lifts_ovr_independently` pins the
  independence; the arithmetic is in the module docstring).
- The **spurt** on a 9th-grade fire is 1.5–7.5% of the base peak (cap 15% × 0.10–0.50)
  — about 1–5 OVR on a 60.
- Maturity cannot lower anyone and cannot fire twice for one grade.

### How to evaluate the 2100 cohort (owner rule: instrument, don't guess)

`players.csv` carries `maturity`, `bloom_grades` (`"7;9"`), `bloom_pot` (summed
reveal, share of base ceiling), `bloom_spurt` (summed, share of base peak),
`early_participant`, `early_seasons`. Join two seasons' exports on `player_id`:

- `ceiling_grade` YoY moves ONLY for players with a new entry in `bloom_grades` —
  a whole-roster, same-name shift is still REGENERATION, never development
  (`docs/AAR-jhsaa-talent-pin.md`); bloom is per-player and sparse.
- Fire rate by `early_participant` and by played share (the sidecar's exposure
  fold), against the 11.7%/1.2% above.
- The "30 → 60" story is a **multi-season** path (reveal realised over the years
  left), so read it on the 2100 cohort at grade 11–12, not the season after.

---

## 5. The rising-freshman portal (`app/jhsaa_portal.py`, `/jhsaa/portal`)

The first interactive system in the high-school game; the college portal's shape.

- **Trigger**: an early participant (played 8th grade for a gated program), going
  into ninth grade, with **no projected V1 seat at that program**. V1 is the game's
  own projection — `jhsaa._order` on the team `district_teams` builds with last
  season's `prior` evidence and the named staff (the rung's own inputs), cut at
  `lineup_need("regular", group)` — never a top-N by OVR. ‼️ The trigger reads the
  origin's ladder with NO portal move applied: the first draft let a mover sent
  *into* a program push a home kid off V1 and into the portal, and the slate
  churned.
- **Destinations** must project the player ONTO their V1 (`_with` adds them with
  their own evidence and that coach's read, then `v1_rank`). Any classification.
- **Geography is a cascade, not a score**: same **county**, then same **area**,
  then **neighbouring areas** (`area_neighbors`: two areas neighbour when a pair of
  their towns is within 30 miles, read off `coords.json`; an area with none takes
  its two nearest). No league preference (owner). The first tier with any V1 seat is
  the tier; within it the **best seat wins** (lowest projected rank), and the
  owner may redirect to any other option in that tier.
- **Sequential and sees its own moves**: strongest first; each destination's ladder
  includes the movers already sent there; only MOVERS are re-checked
  (`MAX_PASSES` 4) — an earlier mover a later one pushed off is placed again.
- **Held** in BOTH advance paths (`advance_week` after the reclass hold, before
  the rung; `advance_jhsaa_lab` raises `PortalHold`), the fall-portal pattern; an
  empty slate is recorded resolved and never holds. Page: redirect / drop / undo
  per row, commit, dismiss, run now, rebuild (edits kept). The shell's advance
  button becomes "Review rising-freshman portal".
- **A commit writes ordinary transfer records** (`overrides.set_jhsaa_transfer`,
  effective the freshman season) — rosters, the ledger and the player card already
  know what to do with them. `world_jhsaa_portal` is the record of what the PORTAL
  did (`applied()`), which is what the export reads.

### The review pass (2026-09) — four faults in the first build, and what they taught

1. **A displaced mover was still proposed to a seat he no longer had.** Placement is
   sequential and a later, stronger mover can push an earlier one off the seat he was
   placed on; the re-check re-placed him only while passes remained, and the emit
   step read the stale row. Now `build` emits a mover ONLY if `v1_rank` on the FINAL
   ladder of his final destination is not None; anyone else is pulled back off that
   roster and listed as a stay flagged `displaced`. The row's `rank` is the FINAL
   projected seat, not the one at placement (pinned:
   `test_every_emitted_mover_holds_a_v1_seat_with_the_whole_slate_applied`).
2. **A redirect was a cached option pasted onto the row.** `final_moves` swapped the
   destination from the option list the proposal was built with — but the options
   were computed against a ladder that has since taken other movers, and two
   redirects onto one school were never checked against each other. Now every edit
   REBUILDS the proposal (`build(edits=)`): redirects are placed FIRST, strongest
   first, each reprojected with `_with`/`v1_rank` on a ladder already carrying the
   earlier redirects; a redirect that fails falls to the automatic pass and the row
   says so (`redirect_failed`); the automatic pass never takes a seat that would
   push a redirected player off V1 (`held` — the owner's decision outranks the
   cascade). `commit` rebuilds once more before writing, so what lands in the ledger
   is what the ladders say at that moment, never a proposal that went stale while
   the page sat open. A dropped player never enters placement and is reported as a
   stay flagged `dropped`, with an undo. **Reproject, never trust a cached row.**
3. **The page printed ratings.** OVR and the staff's potential estimate were columns
   on a page the owner reads to make decisions — exactly the god-mode data the
   section keeps behind a toggle everywhere else. A candidate is now described by
   what the game already shows: the origin's projected LADDER position against its
   V1 (`ladder` of `roster_n`, V1 `from_v1`), the 8th-grade record and ladder
   finish off `PriorSeason`, the early-season count, and the destination's
   projected seat. `_describe` builds those fields; `ovr`/`pot`/`maturity` stay on
   the stored row for `jhsaa_portal.csv` only.
4. **The page was a statewide splat.** Both genders, every class, one list sorted
   by OVR — nothing else in the section reads that way, and at ~270 movers a season
   it would have been unusable. The view now shows ONE sport and ONE classification
   (the class rail carries the three gated classes only, defaulting to the first
   with anything to show), rows grouped by ORIGIN DISTRICT with the district linked,
   and the meta line says how much of the slate is in view. The slate is still one
   event: Commit commits everything, and the class counts sit beside the buttons.
   `_jp_back` carries `g` and `group` so an edit lands back in the same view.

**And one roster fault beside them (P2):** a 7th/8th-grader's transfer record did
nothing. `is_enrolled` sliced the ledger to grades 9-12, so an early participant's
record never reached `build_roster`'s `tmap`, the early loop had no outbound check,
and the inbound path refused any grade outside 9-12. Now `is_enrolled` spans
`entry - 2 .. entry + 3`, the early loop asks `early_transfer_effective`, and the
inbound path admits grade 7/8 when the seat exists (`year in early_seasons(origin,
entry)`) through the SAME helper. That helper carries the one extra rule: **a 7th/
8th-grader can only go where the destination is in `EARLY_CLASSES` that season**;
a move to a program that cannot take them is ignored for that season and the
player stays put — never nowhere. One authority for both sides of the build, the
`transfer_school` idiom, so the origin's skip and the destination's pull cannot
disagree (pinned: `test_an_early_graders_transfer_record_moves_them_only_where_
they_may_go`).

**Two things measured on the fixture that the owner should look at** (not changed
unasked):

1. "Best seat in the tier" is, in practice, often **"the weakest program in the
   county"**: a 68-OVR rising freshman, 16th on an *elite* 2A whose V1 floor was
   73, was sent to a *poor* 6A whose No. 1 was a 41 — seat 1 of 11, correctly. If
   that is not the intended reading of "best genuine V1 opportunity", the knob is
   the option sort in `build` (e.g. prefer the strongest program that still seats
   them, or the seat nearest the middle of V1).
2. On the scaled fixture **~190 of ~270 rising early participants moved** (girls).
   Elite gated programs carry 40-deep rosters whose V1 floor is above most
   8th-graders. The full-size share is the number to read off `jhsaa_portal.csv`
   after the first real 2100 season.

---

## 6. Instrumentation (research export)

- `players.csv`: `maturity`, `bloom_grades`, `bloom_pot`, `bloom_spurt`,
  `early_participant`, `early_seasons`, `portal_move`, `portal_from`, `portal_to`,
  `portal_season`. Grade 7/8 rows are this season's early participants.
- `jhsaa_portal.csv`: one row per committed move, every season the save has held a
  portal, this gender — season, player, from/to program ids and classes, tier,
  projected seat and V1 size, OVR/POT at the move, maturity, `owner_redirected`,
  option count. Archive path only, the realignment ledger's rule. Manifest
  `rating_semantics` and a `domain_rules` sentence describe both; the caps in the
  text are DERIVED from `MATURITY_POT_CAP`, never retyped.

---

## 6b. The edit path — overlay, never rebuild (owner, 2026-09)

**Report:** "the middle schoolers transfer page is very long with too many items and
if i remove a kid it repolls for each single kid."

Both halves were true. `edit()` called `build(edits=)` on every drop, redirect and
undo — the reprojection rule (§ review pass) read "every edit reprojects", so one
struck row cost a full slate: every origin built, every destination consulted, ~14s
on the fixture and minutes on the real save, for a decision that removes one row. And
the page stacked every league of the class as its own panel, so a class with a dozen
origin districts was a dozen tables long.

**Now.** `edit()` stores the decision and nothing else; `jhsaa_portal.effective(cur)`
lays the edits over the stored proposal on read:

- a **drop** moves the row to the stays ("dropped by you"), 0.02s;
- a **redirect** is checked against the ONE destination it names —
  `_check_redirect` builds the origin, that school and the origins of the other movers
  the slate already sends there (one `district_teams` call, a handful of programs),
  applies those movers with `_with`, and asks the real `v1_rank`. Held, the edit stores
  its validated row (`{"to", "row"}`); not held, it stores `failed` and the automatic
  row stands with the "redirect not held" chip — exactly what `build(edits=)` would
  have said. 0.16s on the fixture;
- an **undo** pops the edit. The one rebuild left is undoing a drop the LAST FULL
  BUILD baked in (a "Rebuild proposal" or commit after the drop): that player is in no
  move row to restore, so nothing but a rebuild can bring him back.

"Rebuild proposal" and the commit still reproject the whole slate with the edits, so
what is committed is what the ladders say — the overlay is the page's answer, the
rebuild the commit's. `final_moves` reads the overlay, and the commit's count agreed
with it on the fixture (396 of 397 after one drop and one held redirect).

The page renders ONE district — the class's leagues are a `<select>` switcher with each
league's counts, the sibling-page idiom the section already uses — and every edit form
carries `district` so a decision returns you to the league you were reading.

Measured on the fixture copy: open 14.2s (unchanged, a full build) · drop 0.02s ·
redirect 0.16s · out-of-reach redirect 0.05s (fails, no build) · undo 0.01s · page
0.15s · commit 26.9s (the reprojection plus the transfer writes).

## 7. Traps hit (each cost a run)

- **A local shadowed the module function.** `_gen_seat` has a legacy local
  `maturity = (lo, hi)`; the new `maturity()` function raised `'tuple' object is
  not callable` at the stamp line. Renamed `player_maturity`. Grep a new module-level
  name against the function it is called from.
- **‼️ `_expo_world_id` MEMOISED A "NO WORLD" ANSWER — a real product bug.** The
  odometer, the talent pin and (now) the class-move history all scope their reads
  through it. Probed once before the world row existed, it cached `None` for the
  life of the process and every archive read answered "no archive": early seasons
  realised as unplayed, nothing raised. Now a `None` is never memoised (one indexed
  probe per call while there is no world — the cold path). `run_jhsaa` also clears
  `_expo_cache` after archiving, beside `invalidate_staff_history`.
- **The fixture must be ONE file.** `wd.WORLD_DB` (the archive) and
  `dbpath.resolve_db_path()` (the odometer, the transfer ledger, the era settings)
  were two files in the first draft; the test now sets `TENNIS_DB_PATH`, clears
  `dbpath._resolved`, and ASSERTS the two resolve to the same path — split-brained,
  every read silently answers "no world".
- **`career()` takes the save's salt.** Called without it, it looks for names drawn
  under a different salt and returns `[]`.
- **The school page's roster snippet is the top SIX by OVR**, so "7th" is not on it;
  the full roster model (`jhsaa_school_view(...)["roster"]`) is where to assert.
- **Diagnose the seat-1 rows before "fixing" them** (§5): both ladders were printed
  and the projection was right; the surprise was the design, not the code.
- **A sequential placement's LAST state is the only one that counts.** The first
  build stored each row when the player was placed and never re-read it; the emit
  step is where the slate must be re-validated (§5, review pass 1). Same shape as a
  redirect applied from a cached option (review pass 2): a projection made earlier
  in the pass is not a projection of the slate.
- A full season on the scaled fixture is **~8 minutes**, so the test file was made
  self-diagnosing (the odometer assertion prints memo state, both resolved paths and
  a direct row count) — one run tells the story.

---

## 9. Coach investment — Future Value and Program Interest (owner spec 2026-09)

### The problem this actually solves

The portal's trigger was "no projected V1 seat", and the ladder it read had no way
to represent a coach saying *I know he's outside my lineup today, but I'm invested
in this kid and I'll find him a role so the family doesn't leave*. So every young
player outside V1 read as somebody the program was willing to lose — ~70% of rising
early participants moved on the fixture. A forced "hold" seat was designed and
rejected (a seat mechanic, a freeze special case at every postseason width, and a
guarantee no coach actually gives). What shipped instead makes `coach_eval` able to
represent two real biases in lineup judgment, and lets the projected ladder — which
the portal already reads — carry the coach's answer.

### The two terms (`future_value`, `program_interest`, `investment_terms`)

Both are in the ladder's own units (OVR points, beside form ±7 and proof +8),
additive, capped, and resolved once per team in `district_teams`. Neither changes
how anybody plays.

- **Future Value — return on further development.**
  `FUTURE_K (0.20) × future_w × FUTURE_HORIZON[grade] × max(0, pot_est − ovr)`,
  capped at `FUTURE_MAX` 8. It reads the **staff's estimate** of the ceiling
  (`pot_est`), never the true one. The horizon is the owner's shape —
  `7: 1.00 · 8: 1.00 · 9: 0.90 · 10: 0.80 · 11: 0.35 · 12: 0.00` — high through
  sophomore year on purpose ("I do not want freshman future value falling rapidly
  just because they're already in high school"), then a substantial decline. A
  senior's future is worth nothing to a lineup; his *development* is untouched.
- **Program Interest — the "senior interest rate", return on investment already
  made.** `INTEREST_K (5.0) × loyalty_w × INTEREST_CLASS[grade] × tenure / 6`,
  capped at `INTEREST_MAX` 8. Class `7: 0 · 8: 0 · 9: 0.2 · 10: 0.3 · 11: 0.6 ·
  12: 1.0` — it accumulates (a three-year junior beats a brand-new freshman in a
  close call) and senior year is where it is most valuable. **Tenure is derived,
  never stored** (`program_tenure`): the early seasons, the entry year and the
  transfer record, so a senior who entered in seventh grade (six years), one who
  walked in as a freshman (four) and one who transferred in this year (one) do not
  read alike. A move resets it; the new coach can still value the player highly
  through the other terms.
- **Why additive and capped is the whole design.** The owner's boundary was a
  10–20% competitive gap, in evaluation units. With a six-year senior: at 52 vs 55
  he wins; at 52 vs 59 it is coach-dependent (a loyalty weight of 1.6 bridges 7
  points, 0.4 does not); at 52 vs 65 the interest rate collapses — nobody benches a
  dramatically better player as a sentimental gesture. That is a property of an
  8-point cap, not a separate "competitiveness" formula.

### Where the weights come from

Off the **named staff**, so they vary by coach: `StaffEffect.future` is the
staff's Development quantile, `StaffEffect.loyalty` is `0.6 × Program builder +
0.4 × temperament` (Senior-first 1.0 · Steady 0.5 · Broad rotation 0.25), each
mapped through a `(0.4, 1.6)` band. **Both default to `None`** on a history row
written before they existed and on a program with no staff — and `None` means
both terms are OFF, so an archived season keeps reading exactly as it was played
and a standalone season or test is byte-identical. That is the era gate, with no
setting (the Stage B idiom). The fingerprint carries them, so a season played under
them is a different memo key.

### The lifecycle this gives the coach model

- **Early career (7th–10th):** future value dominates; maturity may fire through
  9th; tenure is accumulating.
- **Middle (10th–11th):** ability and proof dominate.
- **Late (12th):** ability + proof + accumulated program interest; future ≈ 0;
  ordinary development still active.

Age itself is never a bonus; what changes is *what the coach is paying for*.

### Retention, and the owner's lever

The portal reads `jhsaa._order` on the team `district_teams` builds, so the terms
are in the projected V1 automatically: a young player the coach's future value
puts inside the lineup is **not proposed** — the coach is saying "I want to keep
this kid, so I'm going to play them". One the coach does not value enough stays
outside V1 and the family may look elsewhere. A destination projects the
newcomer's future at *its* coach's weight and zero program interest (`_with`).

**The owner's coach read** (`overrides.set_jhsaa_read`, `/editor/jhsaa-read`,
the form on the player page): a per-player offset, in OVR points, on ONE
program's coach evaluation. It is added to `TeamSeason.read` after the captain
scaling (it is a decision, not a misread), it modifies the judgment and never
pins a position, and its table version keys the season memo. Captains remain
separate; captaincy is not this mechanism.

### Instrumentation

`players.csv`: `tenure_years`, `future_value`, `program_interest`,
`coach_read_override`, computed on the archive path from the staff that season
was played with (`jhsaa_staff_for_season`). Read the 2100 cohort's move rate
against `future_value` before retuning any constant.

`tests/test_jhsaa_coach_investment.py` pins the caps, the horizon shape, the
derived tenure (natural / early / transfer), the 55-59-65 collapse, the neutral
no-staff path and the override round trip.

## 8. Open items

- **Owner decisions**: the option sort in the portal (§5.1); `MATURITY_RATE`,
  `MATURITY_POT_CAP[8]`/`[9]`, `MATURITY_REALISE`, `MATURITY_SPURT` after the 2100
  export; whether the 9th-grade roll should stay association-wide (it is — "only
  fires on 7th, 8th and 9th graders" was read as every 9th-grader).
- The **feeder head start** (`staff_years.get(entry - 1)`) is resolved at a cohort's
  FIRST build; for an early cohort that is two seasons before ninth grade, so the
  pin freezes it without the staff lift a freshman-first cohort would have got.
  Small, consistent, and worth a horizon fix like `cohort_size`'s.
- `_next_cohort_year` / `_resolve_era` still mean "first cohort not yet in the
  building" as `newest archive + 2`; with 7th/8th-graders rostered, cohorts `S+1`
  and `S+2` are already in it. Band/archetype edits reach archived 7th/8th-graders
  (the talent pin mitigates); a FUTURE entry-keyed era gate resolved for the first
  time after 2100 would rewrite archived early players. Note it before adding one.
- `jhsaa_desk`'s freshman-champion story ignores a 7th/8th-grade champion (arguably
  the bigger story).
- The player page shows a 7th-grader's early seasons only once they are archived
  (it walks the archive) — correct, and it means a live-season 7th-grader's card
  shows nothing yet.
