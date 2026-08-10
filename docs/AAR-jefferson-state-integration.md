# AAR — Jefferson: a fictional US state, its juniors and its colleges

## Context

`prep-network` (github.com/quarterback/prep-network) contains a fully built
alternate-history West Coast state, **Jefferson** — ~17.6M people across 20 fictional
counties, each standing on the real ground of southern Oregon, northern California,
northern Nevada and western Idaho. It has 272 cities, 840 high schools under its own
sanctioning body (the JHSAA), and a simulated boys'/girls' tennis season. This sim knew
nothing about it.

This pass makes Jefferson an ordinary US state here — the **55th** entry in
`juniors.US_STATES`, which is not a list of 50: it already carries DC and Puerto Rico /
USVI / Guam as first-class entries, and `scout_intel.US_REGIONS` maps 58 codes in all
(adding American Samoa, the Northern Marianas and BC for Simon Fraser). Its juniors
appear on the recruit board with Jefferson hometowns and Jefferson high schools, and it has a college
footprint sized like a state of that population.

### Owner decisions that set the scope (2027-08)

| Question | Decision |
|---|---|
| Should the JHSAA season be visible in the sim? | **No.** Jefferson is a state like Texas — no HS season UI, no archive, no HS simulation. |
| Where do Jefferson recruits come from? | **Generated**, by this sim's own engine, drawing hometowns and high schools from Jefferson pools. No import of prep-network's simulated players. |
| How big a tennis state? | **Biggest** — Jefferson edges California as a talent source, AND its own league funds at major tier, so it DRAWS as well as develops (like TX/CA/FL). |
| College footprint | Absorb the real programs standing on Jefferson's ground, relocate part of the extra California cadre, add the owner's named flagships. |
| Division coverage | At least one Jefferson program in **every** division D1–D4; at least two in D1. |

Because the season stays invisible and recruits are generated, **there is no runtime
coupling between the repos.** Jefferson crosses over as two committed name pools and a
set of data-file edits. `prep-network` is read once, at authoring time, by a committed
script.

---

## What shipped

### Phase 1 — Jefferson as a recruiting state

`scripts/import_jefferson.py` reads `prep-network/records/orgs/{schools,cities}.json`
and rewrites two committed pools. The script is the provenance record; the JSON is what
the game reads.

- `generators/data/names/high_schools.json` → `"JF"`: the **526** Jefferson schools that
  sponsor tennis, name-normalized so each reads as a school (below).
- `generators/data/names/hometowns.json` → `us_states["JF"]`: Jefferson's **46** largest
  cities, repeat-weighted by population (below).

Wiring, all of it ordinary-state plumbing:

- `app/juniors.py` — `("Jefferson", "JF")` in `US_STATES`; `"JF": 0.0700` in
  `US_JUNIOR_TENNIS_ORIGIN_WEIGHTS`.
- `app/ncaa.py` — `STATE_REGION["JF"] = "W"`; five Jefferson metros in `BIG_METRO_CITIES`.
- `app/scout_intel.py` — `US_REGIONS["JF"] = "Pacific"`.
- `generators/cities.py` — `"JF"` added to `_US_CODES`.

### Phase 2 — the college footprint

`scripts/build_jefferson_colleges.py` applies a declarative table of **39 programs** to
the eight division files plus `locations.json` and `logos.json`. It is idempotent and
has a `--dry-run`. It deliberately does **not** write the curated Python rating tables
in `app/ncaa.py` — it prints the lines to paste, because those tables carry comments a
machine rewrite would destroy.

| Division | Jefferson | Conference |
|---|---:|---|
| D1 | 12 | **Jefferson Valley Conference (`JVC`)** 10, plus the flagship in the Pac-16 and Galena in the MW |
| D2 | 14 | **Jefferson Collegiate Conference (`JCC`)** |
| D3 | 9 | **Jefferson Athletic Association (`JAA`)** |
| D4 | 4 | joined the existing NWC |

39 programs is **2.2 per million**, matching California's 2.0 — the right comparator for
a large West Coast state.

---

## Decisions that look like bugs and are not

### 1. The origin-weight table no longer sums to 1.0

It sums to ~1.134. The file already says these are *relative* weights and `rng.choices`
renormalizes. Jefferson enters at 0.1400 and the four states whose real counties it
stands on are shaved by the population share it actually takes from them — OR ~17% (nine
counties), NV ~16% (Washoe, Humboldt), ID ~12% (Canyon, Owyhee), CA ~1.8% (seven
far-northern counties). The rest of Jefferson's weight is its invented population.
**Do not "fix" this by rescaling all 55 numbers** — the diff would be unreviewable and
the behavior identical.

Measured over three 2,500-recruit classes (~1,627 domestic each, the rest international):

```
JF 188 · CA 186 · FL 166 · TX 113 · NY 82 · WA 59
```

A single class is noisy enough to reorder the top two. **Average several classes before
concluding the weight is wrong.**

Producing talent and attracting it are separate levers here. The weight above is only
the first; the second is `CONF_TIER["JVC"] = "major"`, which funds Jefferson's ten
JVC programs at 12–13 scholarships (the major band is 9–16) — past the 10.5 floor
needed to attract a 5★, so they can outbid for out-of-state recruits the way a real
destination does. Owner rule 2027-08: Jefferson develops AND draws, like TX/CA/FL.

### 2. The Jefferson city pool is capped at 46, not all 272

This is the number that bites, and it caused a real bug during this work before being
caught. The pool feeds **two** consumers, and only one of them sees the repeat-weighting:

1. `flavor.roll_us_hometown("JF")` — a Jefferson recruit's own hometown. Flat
   `rng.choice`, so repeats are the weighting.
2. `ncaa.towns_in_region("W")` — the pool **every western program** draws its local
   year-0 base-roster players from, at `LOCAL_REGION_TARGET = 0.70`. It dedupes by
   `(city, state)`, so only the **distinct** count matters there.

Exporting all 272 made Jefferson **64%** of that Western pool — every California, Oregon
and Washington roster would have filled with Jefferson kids, and **nothing would have
errored**. Capping at 46 puts Jefferson at 23.1% of the pool, matching its ~23% share of
the region's population, and at ~2.6 cities per million against California's 2.4.

`scripts/import_jefferson.py` now prints this share on every run and warns above 30%.
If Jefferson's population or the western state pools change, **re-derive the cap; do not
just raise it.**

### 3. Jefferson is NOT in `SCHOOL_LOCAL_TERRITORY`

`SCHOOL_LOCAL_TERRITORY` exists because PR/VI/GU/AK have no `STATE_REGION` entry, so
`region_proximity()` returns 0 for them and a local kid has nothing binding them to the
local school. Jefferson **is** in `STATE_REGION` as `"W"`, so it already gets the full
`homecooking × proximity × GEO_WEIGHT` (0.55) tug plus `COACH_LOCAL_WEIGHT` (0.50).
Adding it here would stack a `LOCAL_TERRITORY_PULL = 6.0` multiplier on top and make
Jefferson programs hoard their own state. Leave it out.

### 4. Jefferson is NOT in `WARM_STATES`

It is Pacific Northwest and Great Basin. Neither Oregon nor Washington is in that set
either.

### 5. Jefferson is deliberately absent from `_STATE_HEAT`

It draws at the default weight 1 in `generators/cities.py`. Its city list is *already*
population-repeated at export, so weight 1 alone puts it at **8.7%** of the nationwide
birthplace pool. Giving it a hotbed heat would multiply an existing weighting and blow it
past California.

### 6. Absorbed programs keep their own logos

Real programs standing on Jefferson's ground were **renamed, not replaced** — so each
keeps its own mark, which is how they carry their real lineage honestly rather than
borrowing someone's art:

| Was | Campus | Real county | Is now |
|---|---|---|---|
| Oregon Tech | Klamath Falls, OR | Klamath → Tamarack | **Cascade Polytechnic University** (Redfork) |
| Southern Oregon | Ashland, OR | Jackson → Marlow | **Siskiyou University** (Boyerstown) |
| Cal Poly Humboldt | Arcata, CA | Humboldt CA → San Marcos | **Humboldt Polytechnic University** |
| Chico State | Chico, CA | *outside the footprint* — owner-optional | **Bidwell State University** |
| Fontbonne | Jackson, WY | — owner decision | **Santa Laura College** (D3) |
| College of Idaho | Caldwell, ID | Canyon → Halbrook | **College of Jefferson** (D4) |
| Carroll (MT) | Helena, MT | — owner decision | **Aurelia College** (D4) |

`logo_source` records the origin as `rename:<Old>`, and the old `espn_id` is dropped —
that id belongs to the old identity.

> ### ‼️ A FLAGSHIP IS NEVER SUBSUMED (owner rule 2027-08)
> Galena University was first written as a rename of **Nevada** — Galena County *is*
> Washoe County, so absorbing UNR looked geographically tidy. That was wrong and has
> been reverted. Jefferson may take the ground and it may take the regional publics,
> but a real flagship keeps existing: **UNR cannot be eliminated.** Galena is now
> net-new, wears its own badge, and sits beside Nevada in the Mountain West. Galena
> and Reno are two towns on the same ground in different fictions, and that is fine.
>
> The cost of the two owner-directed takes is real and should not be discovered later:
> **Montana now has no D4 program at all** (Carroll was its only one), and Wyoming
> keeps a D3 presence only because Dean (Cheyenne) still stands alongside the departed
> Fontbonne.

### 6b. The flagship is in the Pac-16, and Colorado State moved to make room

A 17.6M state's flagship should fund like a blue blood, and `CONF_TIER["Pac-16"]` is
`top` (a 16–33.5 budget) against the JVC's `mid` (6–9). Rather than rename the
conference — its abbr is a key in `CONF_PRESTIGE`, `CONF_TIER`, `web/state.py::_P5`
and `polls.py::_POWER_CONFS` — **University of Jefferson joins the Pac-16 and Colorado
State steps out to the Mountain West**, which is where it plays in real life, so the
swap reads as a correction rather than a demotion. The Pac stays at exactly 16, nobody
is deleted, and Gonzaga is untouched. The mechanism is the `MOVES` table in
`scripts/build_jefferson_colleges.py`: a conference move for an existing program, with
no rename and no relocation. MW goes to 14 (Colorado State + Nevada + Galena).

### 7. Only THREE Golden State campuses moved, not ten

The GSAA was built to fill a D3 California hole (CA went 5 → 20 in
`docs/AAR-western-sky-seas-conference-split.md`). Emptying it would undo that. Three
moved — the ones with generic western names; the seven that stayed carry unmistakably
Southern-California place names. **D3 California went 20 → 17**, not 20 → 11.

The other relocations from that pass (Dean WY, Elms NV, Lasell AK, Talladega VI, Judson
NV, Voorhees GU) were left alone simply because they are what keeps those states on the
D3 map — worth checking before moving one, not a rule. Fontbonne (WY) was taken by owner
decision and Wyoming still has Dean.

### 8. Borrowed marks are COPIED to a new slug, never shared

The owner picked three donors whose monograms already match: Jacksonville's **JU**,
Jacksonville State's **JSU**, University of St. Joseph's **USJ**. All three are live
programs, so their art is **copied** to a new slug and the donor entry left untouched.
**Never copy the donor's `espn_id`** — the logo collision pass groups by `espn_id` and
would flag the real owner as the loser and drop it from its own match.

The one shared slug in the repo remains the pre-existing, documented
`University of Oregon-Portland` → `oregon` reuse. Nothing new joined it.

### 9. The JVC is `mid`, not `major`

It is Jefferson's Big West — a geographically tight league of big-state publics — and the
Big West is `mid`. A brand-new conference should not be gifted a Major budget band on day
one; dynamic prestige momentum is the intended path up. `SCHOOL_META` pins **JU / JSU /
USJ** because the crest fallback would render "University of Southern Jefferson" as
`UOSJ`.

### 10. The high-school suffix rule is word-aware, not a trailing match

prep-network stores bare institution names because its own site supplies the context;
here the string stands alone in a "High school" bio row. The rule appends `" High School"`
unless any of `School / Academy / Institute / Prep / Preparatory / Collegiate / High`
appears **anywhere** in the name. Matching only the tail breaks the magnet schools:
`San Cordero School of Commerce` and `Lake Esperanza School of Science and Industry` end
in a topic word and must not become `... High School`.

```
Alder Landing                        -> Alder Landing High School
Halbrook Technical                   -> Halbrook Technical High School
San Cordero School of Commerce       -> San Cordero School of Commerce   (unchanged)
Aldecoa Depot High                   -> Aldecoa Depot High               (unchanged)
```

---

## Blast radius

- **Existing saves get a different unsigned recruit tail.** Adding a 55th state changes
  `len(state_abbrs)`, so the floor pass, the `rng.choices(k=…)` count and the
  `rng.shuffle()` in `juniors.generate_class()` all consume differently — every generated
  class for a given seed shifts. Persisted players are safe (`world_roster` /
  `world_signing` store the serialized prospect by `pid`), so signed recruits, rostered
  players and graduates do not change; the *unsigned* remainder of an in-flight class
  does. Nothing corrupts. Same class of shift as `docs/AAR-us-state-allocation-guam.md`,
  which shipped it unconditionally. **Advance to signing day before taking this change,
  or start a new league.**
- **Phase 2 is best taken on a new save.** School name is the join key in `world_roster`,
  `roster_overrides`, honors and championship links. The nine renames orphan those rows
  in an existing save. Phase 1 alone is save-safe.
- Division sizes moved: D1 379 → 390, D2 306 → 316, D3 228 → 233, D4 189 → 191, and two
  new autobids (JVC, JCC, JAA replace nothing). D3's field is 64 against 28 conferences.
- No new caches and no new invalidation edges — these are load-time data changes.
  `towns_in_region("W")` grows 153 → 199 and is cached per region as before.

---

## Verify

```python
import json, os, glob, random, sys
from collections import Counter
import app.ncaa as ncaa, app.scout_intel as si
from app.juniors import generate_class, US_STATES, US_JUNIOR_TENNIS_ORIGIN_WEIGHTS as W
from generators.flavor import _load_us_states, _load_high_schools

# --- Phase 1 ---------------------------------------------------------------
assert ("Jefferson", "JF") in US_STATES and W["JF"] == 0.0700
assert ncaa.STATE_REGION["JF"] == "W" and si.US_REGIONS["JF"] == "Pacific"
assert "JF" not in ncaa.WARM_STATES and "JF" not in ncaa.SCHOOL_LOCAL_TERRITORY

cities, schools = _load_us_states()["JF"], _load_high_schools()["JF"]
assert 40 <= len(set(cities)) <= 55, len(set(cities))      # the cap that matters
assert len(schools) > 500
SCHOOLY = ("High", "Prep", "Academy", "School", "Institute", "Collegiate")
assert all(any(t in s for t in SCHOOLY) for s in schools)

w = Counter(st for _, st in ncaa.towns_in_region("W"))
assert w["JF"] < w["CA"], w                                # never swamp the West

k = generate_class(random.Random(1), n=2500, grad_year=2030, gender="men")
jf = [p for p in k.recruits if p.region == "Jefferson"]
assert jf and all(p.hometown.endswith(", JF") for p in jf)
assert all(p.high_school in schools and p.domestic for p in jf)

# --- Phase 2 ---------------------------------------------------------------
logos = json.load(open("data/ncaa/logos.json"))
loc = json.load(open("data/ncaa/locations.json"))["schools"]

for div in ("D1", "D2", "D3", "D4"):                        # every division represented
    for g in ("men", "women"):
        d = ncaa.load_division(div, g)
        ps = [p for cs in d.conferences.values() for p in cs if p.state == "JF"]
        assert ps, f"no Jefferson program in {div} {g}"
        assert all(p.city and p.region == "W" for p in ps)
        assert not [p.school for p in ps if p.school not in logos or not
                    os.path.exists(f"app/web/static/logos/{logos[p.school]['slug']}.png")]

names = {p.school for cs in ncaa.load_division("D1", "men").conferences.values() for p in cs}
assert {"University of Jefferson", "Jefferson State University",
        "University of Southern Jefferson", "Galena University"} <= names
assert "Nevada" not in names                                # absorbed
assert ncaa.crest("University of Southern Jefferson")[0] == "USJ"
assert ncaa.conf_tier("JVC") == "mid"
for a, exp in (("JVC", 0.565), ("JCC", 0.48), ("JAA", 0.44)):
    assert ncaa.conf_prestige(a) == exp, (a, ncaa.conf_prestige(a))

# borrowed marks copied, not shared; the only shared slug is the documented one
dupes = {s: [k for k, v in logos.items() if v["slug"] == s]
         for s, n in Counter(v["slug"] for v in logos.values()).items() if n > 1}
assert dupes == {"oregon": ["Oregon", "University of Oregon-Portland"]}, dupes
for s in ("University of Jefferson", "Jefferson State University",
          "University of Southern Jefferson"):
    assert "espn_id" not in logos[s] and logos[s]["logo_source"].startswith("reuse:")

# the small-state seeds are sacred
for s, st in [("Dean", "WY"), ("Elms", "NV"), ("Lasell", "AK"), ("Talladega", "VI"),
              ("Voorhees", "GU"), ("Judson (NV)", "NV"), ("Fontbonne", "WY")]:
    assert loc[s]["state"] == st, (s, loc[s])

abbrs = [c["abbr"] for f in glob.glob("data/ncaa/d*_men.json")
         for c in json.load(open(f))["conferences"]]
assert len(abbrs) == len(set(abbrs)), "duplicate conference abbr across divisions"
assert not ({v["state"] for v in loc.values()} - set(si.US_REGIONS))
```

Then `python3 -m pytest -q` (~10 min), and `python3 scripts/sim_signing_drip.py` /
`python3 scripts/eval_realism.py` if the signing economy needs re-checking after the
+28 net-new program seats.

## Regenerating

```sh
python3 scripts/import_jefferson.py --dry-run        # name pools
python3 scripts/import_jefferson.py
python3 scripts/build_jefferson_colleges.py --dry-run # college footprint
python3 scripts/build_jefferson_colleges.py
python3 scripts/make_badges.py                        # marks for the net-new programs
```

Both scripts are idempotent. `build_jefferson_colleges.py` prints the `app/ncaa.py`
rating-table lines to paste; it never writes them.

## Not done, deliberately

- No JHSAA season, standings, brackets or archive in the sim (owner decision).
- No import of named JHSAA players. Worth knowing it is available if the appetite
  changes: the 2026-27 season carries 606 boys and 1,309 girls seniors with real names,
  schools, flight records and state-tournament finishes. It would need a top-~150/gender
  filter — 606 into a 2,500 national pool would make Jefferson a quarter of the boys'
  board — and it would partly bypass the fog-of-war design, since `_recruiting_score` is
  deliberately a noisy projection rather than truth.
- No per-year re-import. Jefferson in `prep-network` is one frozen 2026-27 season at a
  fixed clock (`SEED = 5`, `TODAY = 2027-05-13`), so it could not feed a live pipeline
  without re-running its generator anyway.
- `prep-network/jefferson_data/` is an orphaned earlier draft (256 schools, different
  geography, capital "Ashford"). Nothing reads it. Ignore it.
- Promoting Jefferson's flagship into the Pac-16 was considered and not done — it would
  have meant renaming the conference (its abbr is a key in `CONF_PRESTIGE`, `CONF_TIER`,
  `state.py::_P5` and `polls.py::_POWER_CONFS`) or displacing an existing member. It is a
  one-line follow-up if wanted.
