# AAR — Late conference swap: Western Sky / Western Seas splits + SLIAC / USA South moves

## Context

A user-directed "late conference swap," on top of the earlier restructure
(`docs/AAR-conference-division-restructure.md`) and geographic-diversity work
(`docs/AAR-us-state-allocation-guam.md`). Two goals:

1. A few one-off membership fixes (Monmouth (IL) + Illinois College back to D3/SLIAC;
   Mississippi University for Women into USA South).
2. Spread D3 geography **without adding any new schools** — CA had been left with **zero**
   D3 programs, and WY/NV/AK/HI/VI/GU were empty. Rather than invent schools, the owner
   chose to **split two existing D3 conferences in half and relocate one half** to those
   underrepresented states.

All edits are to `data/ncaa/d3_{men,women}.json`, `data/ncaa/d4_{men,women}.json`,
`data/ncaa/locations.json`, and one prestige table in `app/ncaa.py`. No new schools, no
logo changes (every relocated/moved school keeps its existing mark).

## Changes

### 1. Monmouth (IL) + Illinois College → D3 / SLIAC
Both were in D4; moved back to **D3** into the **St. Louis Intercollegiate Athletic
Conference** (both gender files). SLIAC is now **10** teams.

### 2. Mississippi University for Women → USA South
Added to the **USA South Athletic Conference** (D3). USA South is now **9** (men) /
**11** (women) — MUW is women-only, and USA South already carries the women-only
Meredith and Salem, hence the men/women asymmetry.

### 3. Legacy League split → new "Western Sky Conference"
The 14-school NAIA HBCU **Legacy League** (D3) was split in half. Seven programs stay in
the Legacy League; seven were moved into a **new D3 conference, the Western Sky
Conference**, and **relocated** (per the owner's rule: send to CA / VI / GU *unless the
school is already in a talent-rich state* — none of these were):

| School | New city / state |
|---|---|
| Dillard | Los Angeles, **CA** |
| Fisk | Oakland, **CA** |
| Oakwood | Riverside, **CA** |
| Philander Smith | Fresno, **CA** |
| Rust | Sacramento, **CA** |
| Talladega | Charlotte Amalie, **VI** |
| Voorhees | Mangilao, **GU** |

**Legacy League (remaining 7):** Huston-Tillotson, Paul Quinn, Southern New Orleans,
Stillman, Tougaloo, Wilberforce, Wiley. Both conferences are 7 teams.

> This is the fix for the owner's main concern — **D3 now has 5 California programs**
> where it had none.

### 4. Great Northeast (GNAC-D3) split → new "Western Seas Athletic Conference"
The D3 **Great Northeast Athletic Conference (GNAC-D3)** was split in half. The half that
sat in overrepresented states (all MA/CT) was moved into a **new D3 conference, the
Western Seas Athletic Conference**, with **Linfield** added to bring it to **8** teams:

| School | New city / state | Note |
|---|---|---|
| Dean | Cheyenne, **WY** | relocated (name is not state-tied) |
| Elms | Reno, **NV** | relocated |
| Lasell | Anchorage, **AK** | relocated |
| Colby-Sawyer | — | joined; not relocated |
| Mitchell | — | joined; not relocated |
| Rivier | — | joined; not relocated |
| Albertus Magnus | — | joined; not relocated |
| Linfield | — | added (was already in OR); gives the league its 8th team |

**GNAC-D3 (remaining):** Emmanuel (MA), New England College, Norwich, Regis (MA),
Saint Joseph (CT), Saint Joseph's (ME) — plus **Simmons** (women-only). So GNAC-D3 is
**6** (men) / **7** (women).

## Design decisions / things to know

- **Only name-neutral schools were relocated.** Of the moved GNAC schools, the three whose
  names aren't tied to a place (**Dean, Elms, Lasell**) were physically relocated to
  WY/NV/AK. The state-named MA schools (**Emmanuel (MA), Regis (MA)**) were *kept in place*
  in GNAC-D3 rather than relocated, to avoid an "Emmanuel (MA) in Hawaii" name/location
  mismatch. As a result **HI was not seeded** by this pass, and **VI/GU were seeded from
  the Legacy/Western Sky split** (Talladega, Voorhees) instead. CA got 5, WY/NV/AK got 1
  each, VI/GU 1 each.
- **GNAC-D3 dropped to 6 (men).** Western Seas took 4 GNAC schools + 3 relocations +
  Linfield = 8, which pulls GNAC-D3 below the owner's usual "7 is okay" floor on the men's
  side (women's stays at 7 via women-only Simmons). Flagged for the owner in case a school
  should be shuffled back.

## Recruiting economy: Western Sky prestige = 0.60 + gem pool expanded

The Legacy League was deliberately set to **0.60** prestige so its HBCU members land in the
D3 **"gem" pool** (`recruit_economy._d3_top_keys`) and out-recruit their level — the D3
analogue of the D4 academic-elite bump (see `CONF_PRESTIGE_D3` in `app/ncaa.py`). Because the
**Western Sky Conference is literally half of the Legacy League — the same HBCU programs** —
it **keeps the 0.60** so those schools don't lose the bump merely from a geographic reorg.

The gem pool used to be a fixed **Top-20**. Adding a second 0.60 conference would have
over-squeezed it (Legacy 7 + NJAC 8 + Western Sky 7 = 22 > 20), pushing out the next-tier
(0.58) programs. So the pool now **scales with the division: `max(50, 15% of D3 programs)`**
(`_D3_TOP_MIN=50`, `_D3_TOP_FRAC=0.15` in `recruit_economy.py`). At ~215–220 D3 programs
that resolves to **50** — the floor is what binds at the current division size. This holds
all three 0.60 conferences (22) plus a healthy slice of the 0.58/0.56 tier, spreading the
hidden-gem hunt across the country rather than a tiny elite (the owner's call), and the
pool auto-grows if more D3 conferences are added later. The economy explainer
(`state.recruit_economy_view` → `recruit_economy.html`) reads the live pool size, so its
"Top-N D3" label tracks this automatically.

**Western Seas Athletic Conference = 0.40**, inheriting GNAC-D3's level (no economy change).

## Resulting sizes

| Conference | Div | Men | Women |
|---|---|---:|---:|
| SLIAC | D3 | 10 | 10 |
| USA South | D3 | 9 | 11 |
| Legacy League | D3 | 7 | 7 |
| Western Sky Conference | D3 | 7 | 7 |
| Western Seas Athletic Conference | D3 | 8 | 8 |
| GNAC-D3 | D3 | 6 | 7 |

## Verify

```python
import json, os
import app.ncaa as ncaa
logos = json.load(open('data/ncaa/logos.json'))
d = ncaa.load_division('D3', 'men')
loc = {p.school: (p.city, p.state) for ps in d.conferences.values() for p in ps}
assert loc['Dillard'] == ('Los Angeles', 'CA') and loc['Voorhees'] == ('Mangilao', 'GU')
assert {p.school for ps in d.conferences.values() for p in ps if p.state == 'CA'} >= {
    'Dillard', 'Fisk', 'Oakwood', 'Philander Smith', 'Rust'}
assert ncaa.conf_prestige('Western Sky Conference') == 0.60
assert ncaa.conf_prestige('Western Seas Athletic Conference') == 0.40
# every school still resolves to an on-disk logo
missing = [p.school for ps in d.conferences.values() for p in ps
           if p.school not in logos or not os.path.exists(f"app/web/static/logos/{logos[p.school]['slug']}.png")]
assert not missing, missing
```
