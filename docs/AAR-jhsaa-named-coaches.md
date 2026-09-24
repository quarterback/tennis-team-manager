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
  home.
- **The carousel** is `/jhsaa/coaches/carousel`: a button that stores a PENDING
  proposal. The owner vetoes lines, then commits.
  - Each cycle proposes retirements (by age and tenure), rare firings (5+ seasons
    in the current class, 0.20 below the program's own norm, then a 30% chance),
    and a fill for every vacancy.
  - Fill order: the program's own assistant, then an area assistant, then an
    alumnus, then a new local candidate.
  - Vetoing a departure or promotion keeps that seat filled.

## No work after an update
- **Coaches:** `ensure_staff` seats every program, with random rolls, the first time
  the season rung runs. The tables are created by the ordinary schema pass.
- **Former players who graduated before the alumni index existed:** they are indexed
  on demand from their player page. A senior of the newest archived season or earlier
  counts as graduated, so the "Hire as coach" form appears with no migration or
  backfill. From then on, every archived season indexes its own seniors.
