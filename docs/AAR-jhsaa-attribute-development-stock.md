# AAR — The JHSAA attribute-level development model (developmental stock + coaching portfolios)

**Owner spec:** the second addendum ("Attribute-level developmental capacity and
coaching portfolios", 2026-10-09) of
`docs/reports/JHSAA-development-panel-review-2103-2111.md`. The first addendum
(the generic additive staff dividend, with its OVR-80 gate and synthetic tables)
was **superseded by the owner and is not built**; nothing from it is in code.

**Shipped:** 2026-10, on PR quarterback/tennis-team-manager#493, in
`app/jhsaa_develop.py` with wiring in `app/jhsaa.py`, `app/jhsaa_coaches.py`,
`app/world.py` and `app/research_export.py`.

**In game terms:** the model is gated on the ENTRY COHORT by `jhsaa.stock_era()`
(`worldconfig` key `jhsaa_stock_era`, listed in `ERA_SETTINGS`). On an existing
save it self-configures to the first cohort not yet in the building — the newest
archived JHSAA season's year plus two — so on the owner's save at world year 2037
(JHSAA season 2111 just archived) the first stock-era freshmen are the class
entering for the **2113** season; a fresh save is era 0 and every cohort is
stock-era. Every player who entered before the era keeps the old model byte for
byte for the rest of their career: their archived seasons, ladders, box scores and
honours do not move. The association converges over one four-year graduating
cycle (six with 7th/8th-grade early participants).

---

## 1. What it replaced

### The scalar realisation (`jhsaa._apply_career`)
A career-era player was generated once AT their ceiling (`p.potential`, 51
attributes shaped by play style), and each season their CURRENT ability was set
by **one factor** over every attribute:

    target  = career_ability(grade, …)            # one OVR number for this grade
    factor  = target / ceiling_OVR
    current[a] = potential[a] × factor   for every attribute a

`career_ability` is the career plan — start, peak and four yearly capacities drawn
once per seat — realised by the exposure odometer, program archetype
(`coach_factor`), maturity and early-POT events, and the named staff's `dev`
multiplier. It preserves the player's shape exactly and can only slide the whole
player up or down their own curve. A coach could not teach a specific skill.

**Still runs, for every cohort.** For a stock-era cohort it now produces the
INTRINSIC path (the natural shape, exposure-aware), on top of which the stock model
adds what the staff taught. For pre-era cohorts it is the whole answer, unchanged.

### The blended staff `dev` multiplier (`jhsaa_coaches.staff_effect`)
One number per program per season: `1 + DEV_K × (effective Development − 0.5)`
where effective Development is the head's grade plus `COVER` (40%) of the gap to
the single best assistant; `DEV_K` 0.40 → ×0.80 to ×1.20 on the whole roster's
yearly capacity. Every player and every attribute got the same factor; other
assistants added nothing.

**Retired for stock-era cohorts (owner decision 2026-10).** `_gen_seat` passes
`staff=None` to `_apply_career` for them, so coaching reaches a stock-era player
only through what each coach teaches — never as a second blanket speed-up on top.
Pre-era cohorts keep the multiplier; `DEV_K` is untouched in code. The JV-lean and
mentorship adjustments rode on that multiplier and are therefore also inert for
stock-era cohorts.

### Unchanged on purpose
Changeover (the set-break advice roll), Tactics (the style-matchup scale) and
Singles (the flight-side points) are match-day effects in `engine.fast` and are
not touched. The coach lens / `coach_eval` ladder judgment, Future Value and
Program Interest are selection effects and are not touched. Feeder ties,
retention and culture are roster effects and are not touched. Maturity and the
early-POT rolls still fire and still lift the natural ceiling; the stock model
reads the ceiling they produce.

---

## 2. The player contract (`jhsaa_develop.latent_profile`)

Drawn ONCE per seat on its own rng stream `"{salt}|jhsaa-stock|{school_key}|{entry}|{seat}"`
(the main seat rng is never touched, so no other roll in the roster moves).
Inputs: the NATURAL attribute vector (the pre-era `p.potential`, i.e. the scalar
model's ceilings, including any maturity/early-POT peg), and the career plan's
`start_frac` and `peak_frac` (start and peak as shares of the natural ceiling,
from `_career_plan`).

Nine categories cover all 51 attributes; eight are COACHED, the ninth
(`intangibles`: coachability, training_drive, academic_fit, team_culture,
leadership, the four comfort/tolerance attributes, and flexibility) grows only on
the natural path. Flexibility is there because nothing in the engine reads it.

| Draw | Formula | Meaning |
|---|---|---|
| work ethic `E` | `0.55 × Beta(2.2, 2.0) + 0.45 × evidence`, where evidence = mean of the generated training_drive and coachability CEILINGS mapped to 0–1 | stable disposition; never reads a current grade, so effort cannot multiply its own growth |
| trainability `t_k` per coached category | `U(0,1) ^ 1.6` | how far instruction can take that skill group for THIS player (mean ≈ 0.38, a few near 1) |
| coachability `c_k` per category | `0.5 × E + 0.5 × Beta(2, 2)` | how much extra instruction the player absorbs in that group |
| realisation share `ρ` | `U(0.60, 1.00)` | how much of the trainable headroom the stock can fund |
| trainable ceiling `cap[a]` | `natural[a] + t_k × 40 × sqrt(1 − (natural[a] − 20)/(100 − 20)) + N(0, 1.5)`, floored at `natural[a]`, clamped to 100 | the hidden maximum for that attribute; intangibles: `cap = natural` |
| natural spend | `Σ_a natural[a] × (peak_frac − start_frac)` | what the natural path spends over a full career |
| extra stock (raw) | `ρ × Σ_a max(0, cap[a] − natural[a])` | what coaching can add, in raw attribute points |
| extra budget (OVR) | `ρ × (weighted(cap) − weighted(natural))` | the same thing in weighted-OVR units — the second budget |
| `stock_total` | natural spend + extra stock | the ONE pool both kinds of growth spend from |

`weighted(x)` is the game's OVR mean, `Σ OVERALL_WEIGHTS[a] × x[a] / Σ weights`
(`player_attributes`). Two budgets exist because concentrating cheap or heavily
weighted attributes could otherwise game a single pool.

**`p.potential` for a stock-era player IS the trainable ceiling.** The natural
target is kept on `p.jhsaa["stock"]["natural"]` (its OVR) and in the pinned
caps/natural relationship.

### POT on a card (owner decision 2026-10)
`_stamp_pot_estimate` estimates a BLEND, `0.5 × natural_OVR + 0.5 × trainable_OVR`,
with the existing per-player misread (`POT_MISREAD_SD` 6, shrunk by seasons of
knowledge) on top. The scout sees "he's got a ceiling" without the exact maximum;
the research export carries both numbers (`natural_grade`, `trainable_grade`) and
`ceiling_grade` stays the hidden trainable maximum.

### The pin (`world_jhsaa_talent.stock`)
`record_talents` writes the whole profile (ethic, ρ, `train`, `coach`, the 51
caps, `stock_total`, `extra_raw`, `extra_ovr`) as JSON beside the talent pin at a
player's first archive; `pinned_talents` reads it back and `_apply_stock_era` uses
the pinned profile instead of redrawing. So a retune of any constant in
`jhsaa_develop` reaches **new entrants only**; an enrolled player's capacity never
regenerates. Column added by the existing `ALTER TABLE` migration list in
`world.init_schema`.

---

## 3. What each coach teaches (`jhsaa_coaches.teaching_portfolio`)

`{category: intensity}` per coach, deterministic on the coach_id, memoised. The
identity's categories at intensities `(1.0, 0.7, 0.45)`, plus ONE specialisation
drawn from `random.Random(f"jhsaa-portfolio|{coach_id}")` at 0.6 (a generalist
draws two at 1.0). It reads no rating, so a grade edit changes how WELL a coach
teaches, never what.

| Identity | Teaches (in order) |
|---|---|
| singles | baseline, serve, return |
| doubles | net, touch, return |
| practice (and legacy teacher / jv_whisperer) | movement, physical, baseline |
| tactician | touch, return, mental |
| motivator | mental, physical |
| builder | mental, movement |
| evaluator | baseline, serve |
| generalist | two random categories |

How WELL: the coach's governing quantile per category (`GOVERNING`), a blend of
the imprinted grades, through `d(q) = clamp((q − 0.30)/0.60, 0, 1)^1.5`. A coach
under the 30th percentile in a category's governing grades teaches nothing in it;
an elite coach (q ≈ 0.95) teaches at ≈ 1.0.

| Category | Governing grades |
|---|---|
| serve | singles 0.6, development 0.4 |
| return | singles 0.5, tactics 0.2, development 0.3 |
| baseline | singles 0.5, development 0.5 |
| net | doubles 0.6, development 0.4 |
| movement | development 0.7, builder 0.3 |
| touch | tactics 0.5, singles 0.3, development 0.2 |
| physical | development 0.5, builder 0.5 |
| mental | clutch 0.5, changeover 0.3, talent_id 0.2 |

### The head-coach bond (`jhsaa_coaches.head_bond`)
Computed at `record_season` for the head of every program and stored on the head
row's effect JSON (`bond`), from PRIOR archived seasons only (so a season can never
rate itself), up to five, recency weights `(1.0, 0.8, 0.6, 0.45, 0.3)`:

    s_year = 0.55 × (actual win% − expected) × 2
           + 0.30 × ((made State ? 1 : 0) − expected)
           + 0.15 × (min(tenure, 5)/5 − 0.5) × 2
    expected = the program's preseason-strength PERCENTILE in its gender-year
               (`jhsaa_preseason`; 0.5 when no strengths are stored)
    s = recency-weighted mean of s_year × n / (n + 2)        # shrink toward neutral
    bond = clamp(1 + 0.15 × s, 0.85, 1.15)

A new head is 1.0. It travels with the coach_id. No age term. It scales the whole
staff's offers for the NEXT season and nothing a match reads.

---

## 4. The season spend (`jhsaa_develop.season_offers` / `allocate` / `apply_stock`)

Run inside `_gen_seat` for a stock-era player, over every ARCHIVED prior season
(7th/8th grade for an early participant, then 9th up to the grade before the
current one), in order. The staff for each season is the people archived in
`jhsaa_coach_history` for that program and season (`jhsaa.staff_coaches_history`,
head and every assistant); for a transfer, the staff of the school the player was
AT that season (`build_roster`'s mover branch resolves it per year, the odometer's
own rule).

**Intrinsic first.** The scalar baseline at the current grade (what `_apply_career`
just set) is the natural path. Its spend so far,
`Σ_a max(0, baseline[a] − natural[a] × start_frac)`, is charged to the stock before
any coaching.

**Offers.** For each coach and each category in their portfolio:

    took?  seeded on "{salt}|jhsaa-teach|{pid}|{coach_id}|{category}|{season}"
           P(took) = 0.35 + 0.55 × c_k × ethic_term
    offer  = 45 × slot_w × d(q) × intensity × fit × c_k × ethic_term × reps × bond
      slot_w     = 1.0 head, 0.8 assistant
      fit        = U(0.6, 1.3) seeded on "{salt}|jhsaa-fit|{pid}|{coach_id}|{category}" (stable for the pair)
      ethic_term = 0.3 + 0.7 × E
      reps       = 0.25 + 0.75 × min(1, (played − EXPO_FLOOR)/(1 − EXPO_FLOOR))   # practice counts; a full varsity season converts fully

Two coaches on the SAME category: offers sorted, the second adds 25%, the third
10%, the fourth 5% (`OVERLAP`). Complementary staffs open more than overlapping
ones; overlapping expertise has diminishing returns.

**Allocation.** Categories in order of total offer. Within a category the offer is
split across its attributes in proportion to HEADROOM (`cap − current`), capped at
12 raw points per attribute per season, 120 raw points per player per season,
7.0 weighted OVR per player per season, the remaining stock and the remaining OVR
budget. Gains are credited per coach in proportion to their (decayed) share, which
is what the ledger records.

**Landing.** `current[a] = baseline[a] + min(coached[a], max(0, cap[a] − baseline[a]))`
— coaching can never carry an attribute past its cap; the natural path is never
clipped (a career peak may sit above the natural target, and that overflow is the
player's own). `p.potential[a] = max(cap[a], current[a])`. OVR and every engine
driver derive from the attributes afterwards; nothing sets OVR beside them, and
there is no match buff anywhere. Winning adds nothing.

Headroom for a season is read against the player as they stood then: the intrinsic
share by that season plus coaching already banked. The stock may end unspent.

---

## 5. Archive and export

**Owner rule 2026-10: EVERY quantity the coach layer and the development model
produce reaches the end-of-season research export, whether or not a page shows
it** — the owner evaluates the model from the bundle, not the UI. The first
export pass (same day) carried six player columns and a thin ledger; the second
pass carries the whole contract. Nothing here is recomputed on read: every value
is what the roster build / the season rung actually used.

Archive:
- `world_jhsaa_talent.stock` (new column): the pinned profile
  (`{ethic, rho, train, coach, caps, stock_total, extra_raw, extra_ovr}`).
- `jhsaa_coach_history.eff` (head rows): gains `bond`.

In memory (`Prospect.jhsaa`, derived every build, never stored):
- `stock`: `{ethic, total, left, coached_ovr, natural, trainable, rho, extra_raw,
  extra_ovr, ovr_left, intrinsic, seasons_staffed, seasons_coached}`.
- `stock_pin`: the profile. `stock_attrs`: `{natural, baseline, coached}` — three
  51-attribute vectors (natural target · intrinsic path at this grade · coached
  points before the cap clip; the caps are on the pin).
- `coached`: the per-season ledger `[{season, raw, ovr, played, bond, offered,
  stock_left, ovr_left, by_coach: {coach_id: {category: raw}}, detail: {coach_id:
  {category: {slot, d, intensity, fit, p_took, offer, overlap_w, raw}}}}]`.
  `jhsaa_develop.allocate_detail` is `allocate` plus that detail; `allocate` is
  unchanged for every other caller.

The bundle (every JHSAA export, archive path and injected season alike):
- `players.csv` (blank for pre-era cohorts): `work_ethic`, `natural_grade`,
  `trainable_grade` (weighted OVR of the two vectors), `stock_total`, `stock_left`,
  `stock_intrinsic_spent`, `stock_extra_raw` (raw points), `stock_realise_rho`,
  `coached_ovr_budget`, `coached_ovr_left`, `coached_ovr` (weighted OVR),
  `seasons_staffed` (prior seasons with an archived staff), `seasons_coached`
  (prior seasons in which something landed), and `train_<category>` /
  `coach_<category>` for each of the eight coached categories (the per-category
  trainability and coachability draws, 0-1). `potential_grade` is the blended
  estimate; `ceiling_grade` the trainable maximum.
- `jhsaa_development_ledger.csv`: one row per player per archived season per
  coach per category of coached growth — `raw_points`, and every term of the
  offer behind it: `slot`, `offer` (pre-overlap), `overlap_w`, `teach_d`,
  `intensity`, `fit`, `p_took`, the season's `played`, `bond`, `season_offered`,
  `season_raw`, `season_ovr`, `stock_left_after`, `ovr_left_after`. So "why did
  this assistant move this kid and that one didn't" is answerable from the file.
- `jhsaa_development_profiles.csv` (new): one row per stock-era player per
  attribute (51): `category`, `natural`, `trainable_cap`, `baseline`, `coached`,
  `current`, `ovr_weight`. This is the file to measure the model on — the two
  ceilings and the realised path, attribute by attribute.
- `jhsaa_coaches.csv`: `teach_<category>` (portfolio intensity, 0 = not taught),
  `portfolio` (the same as one string) and `d_<category>` (the coach's teaching
  quality per category, `d_of(governing_q)` — 0 under the floor, 1 elite).
- `jhsaa_coach_seasons.csv`: `bond` on head rows (blank on assistants and on
  seasons archived before the bond).

The manifest describes all of it. Pinned by
`test_the_research_export_carries_the_whole_development_contract` (a real
roster built against a synthetic archived staff, through `build_jhsaa`) and
`test_the_coach_tables_carry_portfolio_quality_and_bond` (through
`research_tables` on the test database).

Every rng stream added: `jhsaa-stock` (the profile), `jhsaa-fit` (player × coach ×
category), `jhsaa-teach` (the success check), `jhsaa-portfolio` (the coach's
specialisation, salt-free because it is a property of the coach record).

---

## 6. What was measured (`scripts/jhsaa_stock_replay.py`)

Matched-player replay on a scratch world (12 girls' programs, 67 seniors, salt
`replay`): the same players, natural targets and scalar baselines from a pre-era
build, pinned profiles from an era-on build, replayed over three seasons under
synthetic staffs with exposure 1.0 and bond 1.0, so the only difference between
rows is the staff. Career coached-OVR budget across the sample: mean 8.4, p90
13.8, max 16.4; work ethic mean 0.46.

| Staff (three seasons) | mean coached OVR | median | p90 | max | share at zero |
|---|---:|---:|---:|---:|---:|
| weak (q 0.25, two coaches) | 0.00 | 0.00 | 0.00 | 0.00 | 100% |
| average (q 0.50, three) | 0.40 | 0.36 | 0.69 | 0.92 | 0% |
| strong head only (practice 0.95 + two average) | 1.58 | 1.40 | 2.71 | 3.54 | 0% |
| elite assistant only (doubles 0.95 under an average head) | 0.99 | 0.89 | 1.68 | 2.65 | 0% |
| four overlapping elite (all singles 0.95) | 3.40 | 3.21 | 4.91 | 6.49 | 0% |
| four complementary elite (practice / singles / doubles / tactician 0.95) | 3.46 | 3.21 | 5.65 | 6.75 | 0% |

Remove-one-coach ablation on the complementary staff (mean coached OVR lost over
three seasons): head 0.70, singles assistant 0.64, doubles assistant 0.37,
tactician 0.45 — every seat is attributable and the head is the largest single
voice. The top-quartile-ethic × top-quartile-budget player in the sample under the
complementary staff over five seasons went from a natural-path 59 to 66 (+8.7
coached of a 12.1 budget).

Against the 2103–2111 panel's center (median +2 OVR a season, mean ≈ 3.3): an
average staff adds about 0.13 OVR a season on top of the natural path, an elite
complementary staff about 1.15, with a hard per-season ceiling of 7.0 and a
per-career ceiling of the player's own budget. The center is preserved; the
separation is in the staff and the player's latent profile.

Checks pinned by `tests/test_jhsaa_stock.py`: pre-era cohorts carry no stock; an
era-on roster with no archived staff is attribute-identical to the scalar path;
coaching never passes a cap, never goes below the natural path, never overspends
the stock or the OVR budget; OVR is derived from attributes; a pinned profile
freezes the player against a constant change; elite > average > weak = 0; every
coached attribute is read by the engine or the driver mapping; portfolios are
deterministic; the bond is neutral without history and bounded.

---

## 7. What was deliberately not done

- No additive OVR dividend, no OVR-80 ability gate, no work-ethic gate at 0.55 —
  the superseded first addendum.
- No live match buff of any kind; Changeover, Tactics and Singles untouched.
- No change to `DEV_K`, the career plan bands, exposure, maturity or early-POT.
- No migration of existing rows: the era gate and the pin do the protecting.
- No reduction of the stock when a transfer happens; the player carries it.

## 8. Open calibration — re-measure on the real save after the first stock-era season

Every constant in `jhsaa_develop.py` is a first-pass candidate: `TRAIN_SPAN` 40,
`TRAIN_SKEW` 1.6, `STOCK_REALISE` (0.60, 1.00), `TEACH_RATE` 45, `OVERLAP`,
`D_FLOOR`/`D_SPAN`/`D_CURVE`, `FIT_BAND`, `SUCCESS`, `ATTR_RATE` 12,
`SEASON_RAW_CAP` 120, `SEASON_OVR_CAP` 7, and the bond's weights. Things to read
off the first real export: the coached-OVR distribution by staff quality and by
player ethic/budget; whether the +30–50 careers the owner described appear at the
intended rarity (they need a high-budget, high-ethic player under a strong
complementary staff for five or six seasons, on top of the natural path's own
+25); the 80+/90+ graduate rates against the panel; and whether the per-season
7.0 OVR cap ever binds. The replay script is the harness; its scratch-world
numbers above are the baseline to compare against.

Known simplification: a season's staff for a player who transferred is resolved
per season at the school they were at, but the pre-era `dev` multiplier path
never did this; for stock-era players the per-season resolution is the one used.
