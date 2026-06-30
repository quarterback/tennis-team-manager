# AAR — Organized US-state recruit allocation + Guam as a US territory

## Context / problem

Domestic recruit origins were drawn from a coarse integer weight map
(`_STATE_WEIGHT`, e.g. `CA:8, FL:7, …`, everything else `1`) with a plain weighted
draw and **no floor**, so low-weight states (VT, ND, SD, the territories) could
produce **zero** recruits in a given year — the allocation felt random and
uncoordinated. Separately, Guam existed only as a foreign nationality.

## Decisions (do NOT "fix" back)

### 1. Calibrated origin weights + guaranteed per-state floor (`app/juniors.py`)
- `_STATE_WEIGHT` is replaced by **`US_JUNIOR_TENNIS_ORIGIN_WEIGHTS`** — a calibrated
  (USTA-ish) per-state share for all 54 entries (50 states + DC + PR + VI + GU). These
  are **relative** weights (need not sum to 1; `rng.choices` renormalizes).
- `generate_class` now decides domestic/intl up front, then fills domestic slots
  **floor-first**: one recruit of **every** state (guarantees no empty state in a
  year), then the remainder by the calibrated weights, then `rng.shuffle`. So **every
  state generates every year** while hotbeds (CA/FL/TX/NY) still supply far more on
  average. (Floor only applies when `n_domestic ≥ 54`; tiny test classes fall back to
  a pure weighted draw.)
- Talent is unchanged — still an independent `N(talent_mean, talent_sd)` per recruit,
  so every state, including the one-per-year floor states, gets the full talent range.
- Still fully seed-deterministic.

### 2. Guam is a US TERRITORY, not a nationality
- `("Guam", "GU")` added to `US_STATES`; `GU` added to `_US_TERRITORIES` → generated as
  a **US dual-citizen** origin with a US+Guam dual flag (exactly like Puerto Rico / US
  Virgin Islands).
- Guam recruits get **Chamorro** names (as PR gets Hispanic names), via a name picker
  on the existing `guam` region pool. Real Guam **villages** (`hometowns.json`
  `us_states.GU`) and **high schools** (`high_schools.json` `GU`) were added so they
  read authentically instead of falling back to generic placeholders.
- Guam was **removed** as a standalone country in the nationality selector:
  dropped from `worldconfig._CONTINENTS` (Oceania) and from the `oceania` preset in
  `regions.json` (its 0.1 folded into `pacific_islands`). The `guam` **region
  definition is kept** — it now only backs the Chamorro name picker. **Do not re-add
  `guam` to any nationality preset or to `_CONTINENTS`.**
- Two follow-up leaks were closed (Codex review):
  - **Editor "Other" group:** `region_groups()` appends every unplaced region to
    "Other", which re-surfaced `guam`. Added **`worldconfig._HIDDEN_REGIONS = {"guam"}`**,
    filtered out of both `region_groups()` (so it's not selectable) and
    `region_weights()` (so a stale stored multiplier can't reintroduce it).
  - **`pacific_islands` GU subregion:** that region carried a `country:"GU"` (Chamorro)
    subregion, so an international Pacific-Islands draw produced a GU player that
    `generate_class` then converted to a domestic recruit — undercutting the chosen
    international share. The **GU subregion was removed** from `pacific_islands`. Verified:
    an all-international Pacific-Islands class now yields **0** Guam recruits.

### 3. Canada boost (count + quality)
- Region weight raised ~2.5–3× across presets (`regions.json`): `tennis_global`
  0.03→0.08, `americas_pro` 0.04→0.10, `o27_year_1` 0.04→0.10, `o27_year_5` 0.02→0.05,
  `o27_year_10` 0.015→0.04.
- Talent raised in `nation_talent.json`: Canada investment 74→80, grassroots 66→72
  (now #5 overall — see `docs/AAR-nation-talent-rankings.md`).

### 4. HS coverage
- Wyoming `WY` 33→86 and Colorado `CO` 195→294 high schools, merged & deduped from
  authoritative public lists (to match Oregon/New Jersey-level completeness).
  `generators/origins.py` is legacy/unused (superseded) and was left untouched.

## Verify
```python
import random
from app.juniors import generate_class, US_STATES
k = generate_class(random.Random(7), n=2500, gender='male')
abbr = dict((s, a) for s, a in US_STATES)
seen = {abbr.get(p.region, p.region) for p in k.recruits if p.domestic}
assert {a for _, a in US_STATES} <= seen           # every state generated
gu = [p for p in k.recruits if getattr(p, 'secondary_country', '') == 'GU']
assert gu and gu[0].country == 'US'                # Guam = US dual-citizen
```
