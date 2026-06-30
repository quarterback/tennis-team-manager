# AAR — Conference / division restructure, single-sex fix, HBCU Legacy League

## Context

A user-directed reshaping of the school universe, on top of the earlier
geographic-diversity work (see `docs/AAR-us-state-allocation-guam.md`). Goals: pull
the academic D3-type leagues back out of D1, give the NAIA HBCU conference a real home,
stop single-sex colleges fielding phantom opposite-gender teams, and make a few
programs recruit above their division level. All edits are to the `data/ncaa/*.json`
school files plus two rating tables in `app/ncaa.py`.

## Changes

### 1. UAA back to D4 (except Rice)
The University Athletic Association was sitting in D1. Moved the whole conference
(both gender files) **D1 → D4**, keeping the name. **Rice** (not a real UAA school)
was pulled out and reassigned to **Conference USA (D1)**.

### 2. Meridian League dissolved
The fictional D1 "Meridian League" was split on academics (clean gap at 0.55 vs 0.82):
- **Academic → new D4 "Liberty League":** MIT, WPI, Illinois Tech, Union (NY),
  St. Lawrence, Clarkson, RIT.
- **Athletic → D1:** Bemidji State, Grand Valley State, Michigan Tech, Minnesota State
  → **Summit League**; Rowan → **Mid-American Conference**.
- The emptied Meridian League entry was removed.

### 3. Legacy League (promoted NAIA HBCU Athletic Conference)
The NAIA HBCU Athletic Conference was added to the game as a **new D3 conference,
"Legacy League"** — 14 schools (Dillard, Fisk, Huston-Tillotson, Oakwood, Paul Quinn,
Philander Smith, Rust, Southern New Orleans, Stillman, Talladega, Tougaloo, Voorhees,
Wilberforce, Wiley). **UVI** is a real HBCUAC member but stays in **C2C (D2)** per the
owner's earlier explicit placement. **Morehouse → Southern Athletic Association (D4)**;
**Spelman** added to SAA (D4).

### 4. Single-sex fix
The men's and women's data files were identical full memberships, so single-sex
colleges incorrectly fielded both. Now:
- **Women's-only (no men's team):** Agnes Scott, Bryn Mawr, Hollins, Mount Holyoke,
  Smith, Sweet Briar, Wellesley, Meredith, Salem (College), Saint Mary's (IN),
  Saint Benedict, Simmons, Cedar Crest, Spelman.
- **Men's-only (no women's team):** Hampden-Sydney, Morehouse, Wabash, Saint John's (MN).
- **Deliberately left co-ed** (gone co-ed in real life): Hood, Mary Baldwin,
  William Peace, Wilson (PA), Russell Sage. (Hobart and William Smith stays in both — it
  is one entry fielding Hobart men + William Smith women.)
- Mechanism: remove from the *opposite* gender's files only; the school keeps its
  conference in the gender it does field.

### 5. Recruiting bump — "recruit above their level" (`app/ncaa.py`)
Two rating tables, hooked into the existing D3/D4 gem economy
(`recruit_economy._d3d4_funded` — see `docs/AAR-recruiting-prestige-budget-redesign.md`):
- **D3 gem pool = Top-20 programs by prestige.** Set
  `CONF_PRESTIGE_D3["Legacy League"] = 0.60` (top of D3), which lands **13/14** Legacy
  members in the Top-20 gem pool — the D3 analogue of the D4 academic-elite bump.
- **D4 gem pool = per-program `academics ≥ 0.85`.** Set
  `ACADEMIC_SCHOOLS["Morehouse"]=ACADEMIC_SCHOOLS["Spelman"]=0.88` so they draw the D4
  gem allocation regardless of conference (SAA's other members, ~0.78, stay unfunded),
  plus `PRESTIGE_SCHOOLS += 0.15` each to seat them atop their D4 band.

## State after (per gender; men's and women's memberships are identical except single-sex)
| Div | Schools | Confs |
|---|---:|---:|
| D1 | 382 | 32 |
| D2 | 307 | 24 |
| D3 | 211 | 24 |
| D4 | 190 | 20 |

Flagship invariant: all 50 states + DC have a D1 program; the territories (PR/VI/GU)
and BC intentionally top out at D2 (UVI stays D2 by owner decision).

## Verify
```python
import app.ncaa as ncaa, app.recruit_economy as re
# UAA in D4, Rice in C-USA, Meridian gone, Legacy in D3
# single-sex: a women's college appears in only the women's division load
w = {p.school for p in ncaa.load_division('D4','women').programs}
m = {p.school for p in ncaa.load_division('D4','men').programs}
assert 'Smith' in w and 'Smith' not in m
assert 'Morehouse' in m and 'Morehouse' not in {p.school for p in ncaa.load_division('D4','women').programs}
# recruiting bump
re.reset_d3_top_cache()
top = re._d3_top_keys('men')
legacy = [p for p in ncaa.load_division('D3','men').programs if p.conf=='Legacy League']
assert sum(p.key in top for p in legacy) >= 12
mh = next(p for p in ncaa.load_division('D4','men').programs if p.school=='Morehouse')
assert re._d3d4_funded(mh)
```
Tests run green: `test_world_model, test_world, test_roster, test_recruit_signing,
test_economy, test_scholarships, test_scholarship_gender` (45 passing).
