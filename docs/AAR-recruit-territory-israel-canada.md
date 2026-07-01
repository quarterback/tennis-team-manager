# AAR — D3 trim, Sarah Lawrence academic move, per-school recruiting territories

## Context

Continuation of the Western-fill work (`docs/AAR-western-sky-seas-conference-split.md`).
The owner asked to (a) trim a few genuinely tiny/overrepresented D3 programs, (b) save
Sarah Lawrence from the cut by moving it to an academic conference so it gets the academic
recruiting boost, and (c) give two schools a single-nation "home territory" recruiting
pipeline instead of the generic international band.

## Changes

### 1. D3 trim (5 removals) + United East backfill
Removed the tiniest branch/commuter programs from the two most-overrepresented D3 states
(NY 37, PA 27), **keeping every affected conference at ≥ 8** (the owner dislikes 7-team
leagues):

| Removed | From | Conf after |
|---|---|---|
| Penn State Abington, Penn State Berks, Penn State Brandywine | United East | 10 → 7 → **8** |
| SUNY Delhi, SUNY Cobleskill | North Atlantic (NAC) | 10 → **8** |

Dropping the three Penn State branches would have left United East at 7, so **Gwynedd
Mercy** moved **Atlantic East → United East** (both small PA Catholic schools; Atlantic
East 10 → 9, United East → 8/9). Kept Penn State Harrisburg (the largest branch).

### 2. Sarah Lawrence → D4 Landmark + academic boost
Sarah Lawrence was in the trim shortlist, but it's a genuinely elite LAC. Instead of
cutting it: moved **Skyline (D3) → Landmark Conference (D4)** (Skyline 10 → 9; Landmark
10 → 11) and added it to `ncaa.ACADEMIC_SCHOOLS = 0.90`, so it now carries a top academic
profile (verified academics ≈ 0.89) and draws the academic recruits regardless of league.

### 3. Per-school recruiting territories (`ncaa.SCHOOL_RECRUIT_TERRITORY`)
A new hook in `_base_roster`: a listed school recruits **one foreign nation as essentially
its home pipeline** (heavy, not exclusive), overriding the level-based international band.

| School | Territory | Share | Rationale |
|---|---|---|---|
| **Yeshiva** | Israel (`israel`) | 0.65 | NYC Modern-Orthodox university; Israel is its natural feeder |
| **Simon Fraser** | Canada (`canada`) | 0.70 | the **only** NCAA member in Canada (Burnaby, BC) |

Implementation: when a school is in the map, the name-picker region mix becomes
`{"us": 1-share, <region>: share}` instead of `region_weights_for(...)`. The `israel` and
`canada` region keys already exist in the name/hometown data, so rosters draw real Israeli
/ Canadian names + flags. Verified: Yeshiva → 12 IL / 4 US; Simon Fraser → 7 CA / 3 US.

Note (Simon Fraser): UBC is **not** an NCAA school (U Sports); Simon Fraser is the lone
Canadian NCAA member. In reality SFU is returning to U Sports in 2027-28, but it is kept
in the game per the owner. **Its division placement (stay D2 vs move to D3/D4 for Western
balance) is a pending owner decision** — the Canada territory applies wherever it lands.

## Verify
```python
import app.ncaa as ncaa
from collections import Counter
d3 = ncaa.load_division('D3','men'); d4 = ncaa.load_division('D4','men')
assert d3.by_school('Sarah Lawrence') is None
assert d4.by_school('Sarah Lawrence').academics > 0.85
# no NEW 7-team conferences among the ones we touched
for c in ('United East Conference','North Atlantic Conference','Skyline Conference'):
    assert len(d3.conferences[c]) >= 8
cc = lambda p: Counter(getattr(x,'country','?') for x in ncaa._base_roster(p))
assert cc(d3.by_school('Yeshiva'))['IL'] >= 8
assert cc(ncaa.load_division('D2','men').by_school('Simon Fraser'))['CA'] >= 5
```
