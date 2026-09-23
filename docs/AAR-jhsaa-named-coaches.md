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

## The contract: identical first season
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
- Eight grades on the 20-80 scale, stored as quantiles: Talent ID, Adaptability,
  Development, Doubles instinct, Program builder, Feeder ties, Clutch, Changeover.
- Two philosophies: pairing and participation temperament.
- **Rolled ONCE at creation and never developed** (owner rule). The only change is
  the owner's editor.
- **Blended:** the first six. **Head only:** Clutch and Changeover.
- **Stage A reads only** Talent ID, Adaptability, Doubles instinct and pairing. The rest
  are imprinted and shown, and become live in Stage B (era-gated).

## Former players
- **The pool:** `jhsaa_alumni` indexes every senior at archive time (JHSAA players
  are otherwise never stored, so there was no list to hire from). College graduates
  come from `world_graduates`.
- **Conversion:** grades are rolled independently of playing ability, seeded on the
  pid.
  - Style tilts ONE grade (+3) and the pairing lean.
- **Displacement:** a displaced coach goes to the free pool with their career intact.
- **Retirement:** stamps `retired`.

## Stage B (not built)
- Development grade and the JV/floor-raiser lean.
- Participation temperament.
- Clutch (postseason arrangement quality within anti-stacking).
- Mentorship pairing.
- Feeder ties (via the feeder head start).
- Program culture and retention.
- Legacy.
- The vetoable carousel page.
- **Changeover** (the one engine effect):
  - Both coaches roll at SET BREAKS only, at most two per best-of-3.
  - The net adjusts the next set's effective gap and is replaced at the next break.
  - It uses its own rng stream.
  - Tune it to move favourite rates under ~1 point.

Each Stage B item needs its own era gate: rosters rebuild from seed, so a staff
effect on development must read the staff OF THAT SEASON from
`jhsaa_coach_history`.
