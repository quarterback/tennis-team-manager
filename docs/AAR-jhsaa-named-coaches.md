# AAR — Named JHSAA coaching staffs (Stage A)

**Owner spec 2026-09.** The JHSAA already simulated coaching. It just had no people
behind it. Three mechanics were random draws seeded on the SCHOOL:

| Mechanic | Old source | What it does |
|---|---|---|
| Coach lens | `jhsaa.coach_lens(school.name, salt)`, one draw `q` | misread size, trust in proven players, reaction to form |
| Doubles culture | `jhsaa.doubles_culture` (tag draw, 1.0 untagged) | partnership ramp and lock threshold |
| Pairing philosophy | `jhsaa._coach_strategy(school.key)` | maximize / balanced / traditional doubles pairing |

Stage A gives every program a named staff and routes those three through it.
The code is `app/jhsaa_coaches.py`.

## (Superseded) The Stage A contract: identical first season

> **Withdrawn (owner rule 2026-09): every coach now rolls at random, inaugural
> staffs included.** The solve made every inaugural head read Adaptability 50 and
> Doubles instinct 50, which is not a random roll. The staff replaces the old school
> draws; a `doubles_culture` tag stays a floor. The history below is kept as a record.

- **The inaugural staff reproduces the old draws EXACTLY.**
  - The head's Talent ID quantile is the lens `q`.
  - Adaptability is 0.5, which means zero tilt.
  - Doubles instinct maps to 1.0, or to the tagged draw.
  - Pairing is `_coach_strategy`.
- **Verified:** exact on all 3,582 program×salt samples, and a scaled real season
  is byte-identical with and without staffs (`tests/test_jhsaa_coaches.py`).
- **Assistants keep full grades; the HEAD is solved.** When the best assistant is
  above the target, the head sits at `(T − 0.4·b)/0.6`, so the "cover weak spots"
  blend lands on `T`.
  - Float arithmetic lands ~1e-16 off, so the head carries `pins` and a blended
    value within 1e-9 of a pin snaps to it.
  - A tagged program's exact culture rides on `culture_pin`.
  - The first draft CAPPED assistants at the head's grade instead. That was exact
    too, but it masked every specialty: a "Doubles guru" showing 50.
- **One entity.** The program page, the coach page and `district_teams` read the
  same rows. That is the college game's two-model split (`coaches.program_coach`
  vs `coachreg`), not repeated.

## Where the season reads the staff
- **The converter:** `world.jhsaa_staff_for_season(season_year, gender, world_id)`
  is the twin of `jhsaa_prior_for_season`.
  - The rung and the recruit hand-off (`apply_to_class`) both resolve through it,
    or the memoised season forks.
  - An ARCHIVED season reads the effects stored on its history rows (the head's
    `eff`), so a coach moved afterwards cannot change the season the college board
    replays.
- **The memo key:** `run_season` keys its memo on `_staff_fingerprint(staff)`.
- **Mixed doubles** gets the same staff map (its pool is cut off the coach's ladder).
- **No staffs** (standalone, tests): falls back to the school draws.

## Seats
- A staff is a head plus 1-3 assistants by ROSTER SIZE: under 20 → 1, 20-27 → 2,
  28+ → 3. One assistant carries the JV-head LABEL, a designation only.
- Seats follow the roster with hysteresis. Growth opens a vacant seat at archive time;
  shrinkage never removes anyone.
- Keyed on `School.ident`, never the name or classification, so a rename or a
  realignment keeps its staff.

## Ratings
> **Superseded by the band roll below (owner spec 2026-09).** Ten grades now —
> Tactics and Singles were added — on a 20-90 roll.

- Originally eight grades on the 20-80 scale, stored as quantiles: Talent ID,
  Adaptability, Development, Doubles instinct, Program builder, Feeder ties,
  Clutch, Changeover.
- Two philosophies: pairing and participation temperament.
- **Rolled ONCE at creation and never developed** (owner rule). The only change is
  the owner's editor.
- **Blended:** the first six. **Head only:** Clutch and Changeover.
- **Stage A reads only** Talent ID, Adaptability, Doubles instinct and pairing. The rest
  are imprinted and shown, and become live in Stage B (era-gated).

## How a coach rolls (owner spec 2026-09)
Everyone came out ~50 under the old N(50,10)-per-grade roll: the averaged
coach overall spanned 43-60 and staffs 48-63. The replacement is ONE upstream
quality roll, then the permanent attribute rolls, then nothing (`roll_coach`):
1. **Band** (`BANDS`, overlapping): Bad 20-32 · Poor 25-36 · Below average
   33-46 · Average 44-56 · Good 51-68 · Excellent 68-79 · Elite 78-90. The mix
   (6/9/18/32/22/9/4%) is this module's call; the owner set the bands.
2. **Overall**: any integer inside the band — the anchor, never a round tier value.
3. **Identity** (`IDENTITIES`) with FLOORS, not values: a primary floor of 50
   (so every coach, a Bad one included, is good at something) plus related floors.
4. **Wide windows** around the overall: primary −5/+30, related −15/+20, other
   −20/+15, clamped 20-90; a floor above the window's top raises the top to leave
   a real roll (`MIN_ROLL`). No budget; nothing averages back to the overall.
Measured: overall p1 22 / p50 50 / p99 87; single grades 20-90.
**Elite breaks 80 and the page shows the real number** (quantile up to 70/60;
every consumer clamps or stays sane past 1.0).

**Tactics and Singles** are new, both BLENDED so an assistant can supply them:
- **Tactics** (`TACTICS_K` 0.5) scales the existing style-matchup edge
  (`engine.fast.tactics_scale`): the favoured side's better tactician amplifies
  it, the other blunts it; a flat matchup stays zero; exactly antisymmetric.
  Singles and doubles.
- **Singles** (`SINGLES_K` 1.2) is a small per-side offset at the singles
  flights only (doubles never reads it).
- Measured on real rosters, best vs worst staff: Tactics +0.9 pts overall /
  +3.8 in close matches; Singles +2.3 / +3.3. At grade 60 vs 40: +0.4/+1.6
  and +0.7/+1.2.
- **Fast engine only**, like Changeover: the HS profile is read by the fast
  model alone. The JHSAA always plays fast (`jhsaa.FIDELITY`); on the point
  engine the three match effects would simply not apply.

## Former players
- **The pool:** `jhsaa_alumni` indexes every senior at archive time (JHSAA players
  are otherwise never stored, so there was no list to hire from). College graduates
  come from `world_graduates`.
- **Conversion:** grades are rolled independently of playing ability, seeded on the
  pid.
  - Style tilts ONE grade (+3) and the pairing lean.
- **Displacement:** a displaced coach goes to the free pool with their career intact.
- **Retirement:** stamps `retired`.

## Stage B (built)
Every effect has one dial in `app/jhsaa_coaches.py`; 0 switches it off. Every
grade is centred on 50, so an average staff changes nothing.

**Acting on ROSTERS: read archived history only.** `jhsaa.staff_history` is one
read per program, memoised and cleared by `record_season`.
- **Why history only:** rosters rebuild from seed for every archived season, so a
  past year must use the staff that coached THAT year.
- **This is the era gate:** a Stage A history row carries no Stage B keys, so it
  reads NEUTRAL (`_eff_from_json`). No setting is needed.
- **Development (`DEV_K`):**
  - Multiplies each year's capacity by the staff's blended grade, ×0.80..×1.20.
  - A JV whisperer on staff tilts the multiplier toward players who rarely dressed
    that year (`LEAN_K`, read off the exposure odometer).
- **Feeder ties (`FEEDER_K`):**
  - Adds to the freshman head start. The value comes from the staff of the season
    BEFORE entry (who ran the summer clinics).
  - The talent pin freezes it once the player is rostered.
- **Retention (`RETENTION_MAX`):**
  - Up to ± players per class.
  - It reads the program culture the cohort walked into: a fold of Program builder
    (`CULTURE_KEEP` carry), rising over a long tenure and fading after.
  - The sibling generator's cohort-size estimate includes negative retention, so
    it never picks a seat that does not exist.

**Acting in SEASON (the current staff):**
- **Clutch (`CLUTCH_MISS`):**
  - A weak big-match head sometimes runs the frozen ladder instead of the best
    legal postseason arrangement. The ladder in slot order is itself legal under
    the Order of Ability.
  - It uses its own stream, and it is skipped when siblings would be split.
- **Temperament:** scales bench rotation and resting. "steady" is ×1.0 exactly.
- **Mentorship:** a fourth pairing philosophy that pairs oldest with youngest inside
  the fixed doubles pool. Its off-night flip is "balanced".
  - **The younger partner's development boost (`MENTOR_K`):** under a mentorship
    head, a freshman or sophomore banks up to +8% of that year's growth, scaled by
    how much they dressed (the exposure odometer). It reads history only, like
    development, so archived seasons rebuild unchanged. Nobody loses growth.
- **Changeover (`CHANGEOVER_K`):**
  - Both heads roll at set breaks only.
  - The net of the two rolls (capped at 2 OVR) shifts the next set's gap and is
    replaced at the next break.
  - It uses its own rng stream, so set 1 never changes, and `co_k`=0 is
    byte-identical.
  - **Measured:** random coach pairings move favourite rates ≤0.1 pt; best vs
    worst coach ≈ +1-2 pts in a close match.
  - Comebacks do not rise on average: both coaches roll, so the effect is
    symmetric.

**Legacy and the carousel:**
- **Legacy** (seasons by 10+-year heads) raises how often a program's alumni come
  home, and is a fifth of a job's prestige.
- **The carousel** is `/jhsaa/coaches/carousel`: a button that stores a PENDING
  proposal. The owner vetoes lines, then commits.
  - Each cycle proposes retirements (by age and tenure), rare firings (5+ seasons
    in the current class, 0.20 below the program's own norm, then a 30% chance),
    and a fill for every vacancy.
  - **A statewide market, not a regional one (owner rule 2026-09).** The first
    build filled a head vacancy from its own assistant, then an assistant in
    the same AREA, then an alumnus, then a new local — which the owner called
    overwrought: coaches move for jobs. Now every vacancy, best jobs first
    (head seats, then by prestige = coefficient standing + enrollment +
    legacy), interviews applicants from ANY program: its own assistants,
    assistants anywhere chasing a head job, sitting heads at less prestigious
    programs (hired away — a dedicated shortlist of five), free-pool coaches
    and one alumnus. Each hire opens the seat it left, so moves CASCADE down
    the ladder. A better job draws a longer shortlist (4-20 for a head seat).
  - **Heads first, then assistants (owner rule).** The pick is the best
    interview: talent (the overall) + a noisy read (`HIRE_NOISE` 5) + small
    edges (own assistant 6, alumnus 4, same area 2 — a tiebreak, never a gate).
    Anyone who has RUN a program carries `head_record`'s edge: 18 points at an
    average record, ±30 per unit of record quality, scaled by seasons
    (n/(n+1)). The record blends a shrunk win % (60%) with the program's
    coefficient standing (40%) — wins are not all equal, and postseason
    results are what separate them. So a head of any consequence beats an
    assistant who never ran a program; a clearly better assistant can still
    beat a poor head. Measured on a synthetic full association: when a head
    applied they took 33 of 67 jobs, and every assistant who beat one was
    9-35 points more talented.
  - **A new coach is the LAST RESORT** — rolled only for a seat nobody applied
    to. Entrants still equal departures (the pool is conserved), but they
    enter at the BOTTOM of the ladder (measured: destination prestige 0.28
    against 0.45 for moves) after the chain has moved everyone up.
  - **‼️ No tenure gate on who applies (owner report 2026-09).** The first
    market required two seasons in a seat before a coach would apply anywhere.
    On a save whose staffs were seated one season earlier that closed the
    market entirely: no assistant moved, no head was hired away, and every
    opening fell through to a promotion or a new coach ("the idea that it's
    only program assistant, alumni or no one else applied seems silly").
    Ambition alone now decides who is looking. On one-season staffs a cycle
    proposes about 200 assistant moves, ~65 assistants moving up to head jobs
    elsewhere and ~50 heads hired away. The lateral step-up is now 0.05
    prestige.
  - A coach may sit on several shortlists; the best job is filled first, so
    their first offer is the best one they applied for.
  - Vetoing a departure or promotion keeps that seat filled.

## No work after an update
- **Coaches:** `ensure_staff` seats every program, with random rolls, the first time
  the season rung runs. The tables are created by the ordinary schema pass.
- **Former players who graduated before the alumni index existed:** they are indexed
  on demand from their player page. A senior of the newest archived season or earlier
  counts as graduated, so the "Hire as coach" form appears with no migration or
  backfill. From then on, every archived season indexes its own seniors.

## Transactions, program head-coach history, coach records (owner, 2026-09)
- **The coach page's "Moves" panel is "Transactions"**, and it says only
  **Hired · Left staff · Retired**, with the year and the school
  (`jhsaa_coaches.transactions`). The raw event log said "existing — on staff
  when coaches were introduced" and "replaced — moved to the free pool": that is
  plumbing, not a coaching history. Head or assistant does not change the line.
  Going to the free pool is what leaving a staff means, so it is never stated. An
  assistant-to-head move inside one staff in one season reads as "Promoted to head
  coach". A carousel firing is written as a retirement and then an un-retirement,
  so it reads as leaving staff.
- **Off a staff a coach is a FREE AGENT, or RETIRED**, never "not on a staff".
  Nothing deletes a coach row, so a retired coach's page stays.
- **Every varsity head coach in a program's history** is a collapsible panel on
  the program's **History** tab, under Seasons (`program_head_coaches`). One row
  per consecutive run: "Janes Jacobs 2056-present · Dave Williams 2054-56". Every
  panel on that tab (and on the Staff tab) is now a `jh-fold`.
- **Coach Records** (`/jhsaa/coach-records`, History sub-rail) has two boards:
  - *Most wins*: head coach, varsity dual wins.
  - *Multiple state titles*: head coach of the champion, 2+ titles.
  - Each board reads this sport or **Overall**. A coach who moves between the
    girls' and boys' programs is one career, which is why the overall list exists.
  - The titles board reads each season's `champions` through `json_extract`,
    only for seasons with a coach history. It never parses the whole archived
    blob.

## Coach of the Year (owner spec 2026-09, `app/jhsaa_coy.py`)

### What it is
- **Two awards, both for HEAD coaches, both by gender**:
  - **District Coach of the Year**: one per league, where league and district are
    the same thing (`(classification, league)`). Ranked against the other heads in
    that league.
  - **State Coach of the Year**: one per classification, ranked against the other
    heads in that class.
- Both are RÉSUMÉ selections off the archived season. Nothing reads a coach's
  ratings: a Bad-band coach whose team overperformed can win.
- A program with no head coach that season has no candidate.
- **A State run never decides the District award.** Its inputs are district duals,
  district place and district record only. The two schedule-level components
  (improvement, quality) read end-of-season TOSS, which excludes the postseason by
  construction (`rating_duals`).

### The formulas (owner's weights, exactly)
Every component is a 0-100 score and the award score is the weighted sum.

**District** (`DISTRICT_WEIGHTS`)

| Component | Weight | Measurement |
|---|---:|---|
| District overperformance | 45% | `z_to_score(z)` over district duals only |
| District achievement | 40% | `100 × (0.65 × place percentile + 0.35 × district win %)` |
| Program improvement | 10% | `improve()` (below) |
| Overall team quality | 5% | `100 × TOSS percentile within the class` |

- Place percentile is `1 − (place − 1) / (n − 1)` in a league of `n` teams, and
  1.0 in a league of one.
- District win % counts a tie as half.
- **Dual margin is deliberately left out** (owner). It would reward a coach for
  leaving the strongest lineup in against poor opposition, and district finish
  already captures dominance.

**State** (`STATE_WEIGHTS`)

| Component | Weight | Measurement |
|---|---:|---|
| Season quality | 30% | `100 × TOSS percentile within the class` |
| Postseason achievement | 30% | `100 × (State value) / 56` |
| Overperformance | 30% | `(20 × z_to_score(z_full) + 10 × surprise_score) / 30` |
| Program improvement | 10% | `improve()` |

- **State value** is the coefficient's State prices, read through
  `jhsaa_coefficient.season_points`, plus the TOC bonus:
  - Parastate 3.
  - First round 5.
  - Octofinals 9.
  - Quarterfinals 14.
  - Semifinals 22.
  - Final 42.
  - Champion 52.
  - TOC field +4.
  - Divided by the maximum, 52 + 4 = 56.
  - **There is NO separate title bonus.** The 22 → 42 → 52 steps already pay for
    reaching and winning the final, and a second bonus would pay for the same
    thing twice.
- **The 20 : 10 split** (`STATE_OVER_SPLIT`) is the owner's internal split of the
  30% between the full-season expected-win residual and the postseason surprise.

### The expectation: preseason strength and the fitted curve
- **Preseason strength** is the mean `current_overall()` of the nine best players
  on the roster the season was played with (`strength_of`, the same rule as
  `jhsaa._strength`).
  - The rung stores it per program per season in `jhsaa_preseason`
    (`record_preseason`, inside the rung's transaction beside `record_season`).
  - It is PRESEASON: ratings do not change within a season, because development
    happens between seasons.
- **Win probability for one dual:** `p = σ(k · gap + h · hosted)`.
  - `gap` is the team's strength minus the opponent's.
  - `hosted` is +1 at home, −1 away, and 0 in a neutral phase (`jhsaa.NEUTRAL_PHASES`
    — the showcases, State and the TOC).
- **`k` and `h` are FITTED on the season's own varsity duals** (`fit_curve`: a
  two-parameter logistic maximum likelihood by Newton's method, a small ridge on
  the diagonal only).
  - Fitting on outcomes sets only the curve's STEEPNESS. The ratings feeding it are
    preseason, so an overperforming team is still judged against what its roster
    said it should do.
  - It falls back to k = 0.2, h = 0 on a degenerate season (under 20 duals), and
    clamps k to 0.01-3 and h to ±2.
  - ‼️ The first build regularised the cross term too (`a01 = 1e-6`). With no home
    variation that leaked the slope's step into `h`. A test caught it
    (`test_the_fitted_curve_recovers_a_real_slope`).
- **Overperformance z** (`z_score`):

  z = (W − Σ pᵢ) / √(Σ pᵢ(1 − pᵢ))

  - `W` is actual wins, where a tie counts half.
  - **The denominator is the point.** Two wins above expectation over coin flips
    (p = 0.5, variance 0.25 per dual) is ordinary. Two wins where the model gave
    p = 0.1 (variance 0.09) is not.
  - Capped at ±2.5 (`Z_CAP`), then `z_to_score(z) = (z + 2.5) / 5 × 100`.
  - A team with no duals scores 50.
  - District z uses district duals only (the dual row's `district` flag). The
    State z uses every varsity dual of the season, postseason included.

### The postseason surprise
- `surprise = actual State value − expected State value`, scored as
  `50 + 50 × clamp(surprise / 40, −1, 1)` (`SURPRISE_FULL` 40).
- **Expected State value** (`expected_state_values`) simulates qualification and
  the bracket from preseason strengths, as the owner asked:
  - **Qualification:** each class's teams are ranked by `strength + N(0, 1.2/k)`,
    which is a season's worth of noise in rating units, and the top `F` qualify.
    `F` is the size of the archived State field for that class and season.
  - **Bracket:** the qualifiers are seeded by that noisy order into a
    power-of-two bracket in standard seed order (1 v 16, 8 v 9 …), and the top
    seeds get the byes. Every game is played on `σ(k · strength gap)` with no home
    court, since State is neutral.
  - **Pricing:** a loser is priced by teams still alive when it went out, through
    `state_points` (the same arithmetic as the archive). The champion gets
    `state_points(1) + TOC_BONUS`.
  - The postseason component's 100 is that same `state_points(1) + TOC_BONUS`,
    DERIVED from the coefficient module and never typed as a literal (it was 56
    once), so a re-priced schedule cannot leave the ceiling stale.
  - **400 draws per class** (`SIMS`), seeded on blake2s of (world SALT, year,
    gender, class), so re-selecting a season is byte-identical. It is the salt and
    NOT the world row id: the id is a database row number and says nothing about
    which world this is, while the salt is the world's own seed material.
  - A preseason No. 20 reaching a semifinal scores far more surprise than a
    preseason No. 2 doing it, which is the reason for simulating rather than
    treating every semifinal alike.
  - **Accepted simplification:** the simulation does not model the Parastate or
    Metastate separately. It qualifies straight into a seeded bracket, so a real
    Parastate exit (3) is compared against expectations built on first-round
    pricing.

### Improvement and the rating choice (TOSS, not ATR)
- `improve()` compares this season's **TOSS percentile within the class** with a
  weighted baseline of the previous three seasons: 0.5 / 0.3 / 0.2
  (`BASELINE_WEIGHTS`), renormalised over the seasons that exist.
  - Score: `50 + 50 × clamp((now − baseline) / 0.5, −1, 1)` (`IMPROVE_FULL` 0.5, so a
    half-field percentile move earns full marks).
  - **No history is a neutral 50, never a penalty.**
  - Percentiles rather than records keep it resilient to realignment and changing
    schedules.
- **Why TOSS and not ATR** (owner question 2026-09, "isn't ATR better?"):
  - ATR is the association's POSTSEASON SEEDING key (the 2070 rule). TOSS folds
    three dual formats into one opponent-strength graph, which distorts cross-format
    comparisons.
  - But ATR is **half raw win percentage**. The season-quality component exists so
    that a 24-4 team against an excellent schedule does not lose to a 28-1 team that
    played nobody, and the win-% half of ATR leans exactly back toward the 28-1.
  - The record is already rewarded elsewhere in the State formula (the postseason
    and overperformance components).
  - Every comparison here is WITHIN a class, where every team plays the same
    postseason format, and that is where the format distortion bites least.
  - The owner accepted TOSS. Switching is one line if it is ever wanted, because
    `atr` is archived on every standings row beside `pi`.

### Selection, storage, backfill
- **Selected ONCE, after the rung commits** (`world.run_jhsaa` →
  `jhsaa_coy.select_season`, both genders), off the season exactly as stored.
- Stored in `jhsaa_coach_award`: the top five per pool (`FINALISTS`), each row
  with its component scores in `detail`. It is **never recomputed on read**, the
  same rule as `pi`, because an award is a decision the season already made.
- A failure is logged loudly and leaves the season intact.
- **A season archived before this module** has coach history but no awards
  (`needs_awards`). The Honors page selects it once in the background
  (`_jh_deferred`).
  - `_preseason` rebuilds that season's rosters with `build_roster(school,
    season_year, salt)`, which is deterministic, and stores the strengths it
    derived.
  - The page says the selection is running and lands on the result after a refresh.
- **Name handling:** duals are read in archived names and mapped through
  `jhsaa.former_names`. The archive is already relabelled on read, but
  `_relabel` deliberately leaves a retired name that ANOTHER program now uses as
  its live name. So the coach is found by (world-year, ident) where the ident
  comes from `jhsaa_coefficient.identity_map(season's names, jhsaa._rows())` —
  the season-aware resolution the coefficient uses — never by inverting today's
  names, which would credit the current holder of the string's coach with the
  older program's season. `coach_state_titles` resolves champions the same way,
  per season, off that season's standings names.
- **Repeat winners, District only** (owner rule 2026-09): the award favours a
  first-time winner. Each District COY the coach already won IN THE SAME DISTRICT
  (same classification and league name, same gender, an earlier season) takes
  `DISTRICT_REPEAT_PENALTY` (4) points off the ranking score, capped at
  `DISTRICT_REPEAT_CAP` (10). A repeat can still win; it needs a clearly better
  season. A win in another league does not count. The discount is stored in
  `detail["repeat"]`. **State COY has no such term.**
  - A backfill counts only awards already selected for earlier seasons, so
    seasons selected out of order can read a shorter history. That is accepted.
- **Where it shows:**
  - The Honors page's **Coach of the Year** tab: the State winner and its five
    finalists by RANK, then one row per league with the District winner.
    **‼️ Names and rank ONLY (owner rule 2026-09).** No score, component, weight
    or record appears in the visible UI anywhere in the award. Those numbers are
    stored for the record and stay behind the scenes.
  - The coach page: a career tile with the state and district counts, and the
    award on its season's ledger row (`coach_awards`).
  - The program History tab's Seasons column puts a **COY / STATE COY** chip beside
    that season's head coach (`program_awards`).
- **Tests:** `tests/test_jhsaa_coy.py` covers the binomial z and its cap, the curve
  fit recovering a known slope, expected State value rising with strength, and a
  hand-archived season selected end to end. In that season, a league's preseason
  last place wins the league and takes District Coach of the Year.
