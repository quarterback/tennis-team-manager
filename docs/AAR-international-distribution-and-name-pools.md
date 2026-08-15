# AAR — International distribution presets, and the name pool behind them

**Date:** 2027-08
**Scope:** `generators/names.py`, `generators/data/names/*.json`,
`scripts/scrub_name_pools.py`, `app/worldconfig.py`, `app/coaches.py`,
`app/gtt_seasonmode.py`
**Supersedes in part:** `docs/AAR-name-pool-diversity.md` (2026-06-27)

Five owner asks, worked in order, each one exposing the next:

1. *"the ones you have right now aren't really suited or what i want so i'm gonna
   give you replacements"* — five authored international-distribution presets.
2. *"we need to break out West Africa and Central Africa"* — Africa was two
   buckets and could not express either.
3. *"the pool is a sieve and we're getting russian names on dominicans or chinese
   names on africans and it's breaking my immersion."*
4. *"i noticed the repetitions recently and forgot about it."*
5. *"close the gaps in the Caribbean and in the Pacific … they're warm weather
   places with good sun they should logically be places where tennis is more
   popular if there were more money there."*

---

## 1. The sieve — diaspora was a second roll on the whole world mix

The 2026 diversity blend (`DIASPORA_SHARE = 0.12`) was right in intent: real
nations field people of many heritages, and a France squad of nothing but
French-first-plus-French-surname reads like a spreadsheet. The **implementation**
picked the donor culture with a *second, independent draw from the world mix*, so
**any region could donate to any other**. A Dominican drew a Russian name at
exactly the rate Russia sat in the mix. Measured: **11.4%** of all players carried
a name from a heritage with no plausible link to their country.

Nothing errored. Generated names are real names, so it reads as a slightly odd
squad rather than as a bug — which is why it survived a release.

**Fix: diaspora is DIRECTED.** A region may only receive a name from a heritage it
*declares*, via a `diaspora` map in `regions.json`:

```python
name_region = region_id
reg = regions_meta.get(region_id) or {}
sources = reg.get("diaspora") or {}
if sources:
    share = reg.get("diversity")
    share = DIASPORA_SHARE if share is None else float(share)
    if share > 0.0 and rng.random() < share:
        pick = _pick_weighted_key(rng, sources)
        if pick in regions_meta and pick != "zaryanovia":
            name_region = pick
```

A region that declares nothing is **monocultural** — that is now the default, not
the exception. 23 regions declare sources (France ← Maghreb/West Africa; the US ←
most of the world; Britain ← South Asia/Caribbean; Brazil ← Japan/Italy/Lebanon;
and so on). Undeclared cross-heritage draws went **11.4% → 0**; the residual 2.6%
is entirely *declared* diaspora, which is the feature.

> ⚠️ `DIASPORA_SHARE` is now only the **default rate for a region that has declared
> sources**. It is not a licence to restore the undirected draw.

## 2. Africa is six regions, not two

The old shape filed Kenya with South Africa and Zimbabwe under `africa_cricket`
and dumped Angola and Mozambique into a pan-African `africa` bucket. **West Africa
and Central Africa could not be expressed at all** — there was no key to put a
weight on. Now: `north_africa`, `west_africa`, `central_africa`,
`southern_africa`, `east_africa`, `indian_ocean_africa`, with **1,338 curated
names** behind them and 30 African ISO codes added to `coaches.COUNTRY_REGIONS`.

The taxonomy is duplicated in three places and all three must move together:
`regions.json` (the pools), `worldconfig._CONTINENTS` (the editor grouping) and
`coaches.COUNTRY_REGIONS` (nationality → region for coach generation). An unmapped
ISO code in the last one **silently becomes `"global"`** — no error.

## 3. Repetition — measure PRESSURE, not pool size

"It rolls the same names too often" is not answered by a bucket count. The metric
that matters is **repetition pressure = expected draws per 10k ÷ bucket size**, at
each bucket's *heaviest* preset weight. A 200-name bucket at 4% is under more
strain than a 40-name bucket at 0.1%.

Measured across every bucket: **10 over 1.5×**. Added 1,813 names into exactly
those, and re-measured: **0 over 1.5×**, 4,000/4,000 distinct full names in a
sampled world.

Same pass killed the `Player 447` placeholder. When the picker exhausted a
bucket's unique combinations it returned a literal `f"Player {rng.randint(100,999)}"`
with an **empty country code** — a graceful fallback that produces a player nobody
can explain. It now returns the last valid (name, country) it built:

```python
fallback = fallback or (full, country)
...
if fallback:
    return fallback
```

A repeated real name is a cosmetic flaw; `Player 447` is a visible defect.

## 4. The five presets

`global_college` (the default), `latin_world`, `afro_global`, `asia_pacific`,
`eurasian`. Each is 94 regions summing to **exactly 100.0**, with `us` pinned at
**30.0** in all five — that anchor is what makes the five comparable, so fund a
change from somewhere else.

`worldconfig._DEFAULTS["name_preset"] = "global_college"`. All five
`make_name_picker` call sites in `gtt_seasonmode` now pass `region_weights` via a
new `_world_weights()` helper — they used to fall through to the `americas_pro`
default, so the pro league ignored the world's own mix.

## 5. The Caribbean and the Pacific (owner rule 2027-08)

Both are warm, high-sun, and tennis-productive in the way the owner wants the
world to express: *"across the diaspora of both that might be plausible."* They
were the two thinnest blocks in the data and the two lowest-weighted in every
preset.

**Names first.** 1,260 names across 23 buckets — Cuban, Dominican, Haitian,
Afro-Caribbean, Guyanese (Afro + Indo), Indo-Trinidadian, Papiamento (Curaçao +
Aruba), Puerto Rican, the four Surinamese buckets, Samoan, Tongan, Fijian,
Indo-Fijian, Papuan, Hawaiian, Chamorro, Māori, and the shared `pacific_islander`
surname pool. A further top-up went into the three buckets left nearest the
ceiling (Dominican, Cuban, Indo-Fijian).

> Three Trinidad buckets (`afro_trinidadian`, `chinese_trinidadian`,
> `lebanese_trinidadian`) are **surname-only by design** — those subregions draw
> their first names from `afro_caribbean` / `arabic`. `0/0/51` is not a dead
> subregion; check `first_keys` before "fixing" one.

**Weights second.** Caribbean block (12 regions) and `pacific_islands`, per preset:

| preset | Caribbean before → after | Pacific before → after |
|---|---|---|
| `global_college` | 0.92 → **2.60** | 0.90 → **2.00** |
| `latin_world` | 1.74 → **4.40** | 0.90 → **1.80** |
| `afro_global` | 0.59 → **3.00** | 0.90 → **1.60** |
| `asia_pacific` | 0.69 → **1.80** | 1.20 → **3.40** |
| `eurasian` | 0.66 → **1.40** | 0.90 → **1.20** |

Funded from `anzac` (down to a per-preset floor — the Pacific rising at ANZAC's
expense keeps Oceania's own shape honest) and then **Europe pro-rata**. Nothing
came out of Africa or Asia, which the owner had just boosted, and nothing out of
the `us` anchor. Within the block the share vector is tilted per preset: neutral
in three, toward the Spanish-speaking Caribbean in `latin_world`, toward Haiti and
the anglophone islands in `afro_global`.

Verified after: all five still sum to 100.0, Africa/Asia/`us` totals byte-identical,
realized output share within 0.2pt of the weights, 20,000/20,000 distinct names and
zero placeholders in every preset, and **no bucket over 1.1× reuse pressure**.

## Traps this phase left behind

- **‼️ THE SCRUBBER IS AUTHORITATIVE — a name added only to the JSON is deleted on
  the next run.** `scripts/scrub_name_pools.py` treats several buckets as curated
  allowlists (`KOREAN_SURNAMES`, `CHINESE_SURNAMES`, `KOREAN_FEMALE_GIVEN`,
  `TAIWAN_SURNAME_ADD`) and rewrites them wholesale, and it strips any token that
  is also a city or a scraped club name. Grandison, Ramsay, Jerez and Rosario —
  four ordinary Caribbean family names — were removed silently the first time.
  Additions to a scrubbed bucket go **in the scrubber**; place-name collisions go
  in `SURNAME_CITY_KEEP`. **Always finish with `scripts/scrub_name_pools.py
  --check` and re-read the diff.**
- **Write the JSON the way the scrubber writes it** (`indent=2`, `ensure_ascii=False`,
  trailing newline, **insertion key order — no `sort_keys`**). A `json.dump` with
  different options reformats all 16,800 lines and buries the four names you
  actually changed.
- **`worldconfig._CONTINENTS` silently files anything unlisted under "Other".**
  It had drifted: China, Japan, Taiwan, France, Argentina, Colombia, Chile, Peru,
  Ecuador, Uruguay, Bulgaria and Romania were all in "Other" on the world-config
  editor because they were promoted to their own regions after the grouping was
  written. Fixed here. Any new region needs a row in both files.

---

## 6. A mix is a file (owner rule 2027-08)

> *"I often will create a new save once I've updated the file … but then I have to
> re-create my entire geographic parameters and it can be very tedious because I can
> often be very precise about what I wanna do on them … just being able to download
> the preset would be better because then I don't have to worry about it anymore."*

The five presets above are a *starting point*; the thing the owner actually authors
is the ~90-weight grid on `/start`, and it was the most-retyped input in the app.

**Saving it was not enough, and this is the load-bearing part.** `world_setting` —
where every other config value lives — is a table in the same `tennis.db` as
everything else. A "saved preset" would therefore die with the save, which is
*precisely* the event the owner is trying to survive. So:

- **Download** writes a `*.ptc-mix.json` holding every weight, the band it started
  from, and the US/world split. Built **client-side from the live grid**, because the
  owner tunes the boxes and keeps the result before any world exists — an endpoint
  reading the persisted config would export the wrong thing.
- **Load file…** reads one back into the grid on a brand-new save.
- **Save to this world** stores a named mix in `world_setting` — a convenience
  *within* a save. The panel says out loud that the file is the copy that lasts;
  an affordance that silently promises durability it doesn't have is worse than
  not having it.

### Two decisions worth keeping

**Weights in the document are the editor's own integers, not fractions.**
Normalising on save round-trips the *mix* — every consumer renormalizes, so 160/40
and 0.30/0.075 are the same world — but not the *display*: 160 comes back as 561.
The owner authors by eye, so the numbers have to return as typed. One apply path,
`applyWeights(map, fractions)`: bands pass fractions, files and saved mixes pass raw.

**A load reports what did NOT survive.** Region ids get added and renamed between
builds — *this build alone* split Africa into six and promoted a dozen countries out
of shared buckets. A mix authored against an older build is quietly a **different
mix**, and every value in it still looks perfectly valid. `parse_region_mix` returns
`unknown` (regions in the file this build lacks) and `missing` (regions this build
has that the file omits, which load at zero) and the panel names them:

> *Loaded "Euro core" from euro-core.ptc-mix.json — 3 regions. Ignored 1 region this
> build does not have: africa_cricket. 89 regions are not in the file and loaded at
> zero.*

### Testing a feature that has no server

The download is a Blob and the load is a `FileReader`; a Flask test client cannot
see either. `tests/test_region_mix_presets.py` covers the document, the drift report
and the two routes (25 tests), and the browser half runs under `node` +
`playwright-core` against the preinstalled Chromium — author a mix, download it,
open a **fresh page**, load the file, and compare the grid. That check caught
nothing on the first run, which is only meaningful because it also exercises the
stale-file, junk-file and band-still-works paths.

---

## 7. Three faults the region work left behind (found in review)

All three share a shape: **a wrong distribution is not an error.** Every name is
real, every page renders, and the only tell is a number nobody was looking at.

### `region_weights()` is not a picker map

Its docstring says so — `us` is omitted because its share is the domestic split,
not a region weight — but §4's fix wired it straight into `make_name_picker` at all
five pro-league call sites. The picker renormalizes whatever it is given, so the
pros generated **99.8% international** players against a configured 30%. The
previous bug (falling through to the `americas_pro` default, which carries
`us: 0.55`) had at least been *approximately* right.

`worldconfig.with_domestic(weights, share)` is now the one place that scales an
international mix and restores `us`. `ncaa.region_weights_for` — which already had
this arithmetic, wrapped in college-specific share derivation — delegates to it, and
`full_region_weights()` applies it to the world's own `intl_share()` for generators
with no per-program share. Measured after: **69.4% US**, matching the 30% setting.

### A retired region id loses share silently

`_draw_from_region` returns `(None, None, "")` for an id the table lacks and the
draw loop just `continue`s. So an existing save whose persisted `region_w` still
named `africa` or `africa_cricket` (§2 removed six ids) **quietly redistributed
that share** to the rest of the mix — and a mix made *only* of retired ids burned
all 500 retries and fell out to the `Player NNN` placeholder that §3 was rewritten
to make impossible. It was reachable again through a door nobody had shut.

`region_w` is persisted, so it outlives the build that wrote it. Retired ids are
folded into their successors (`worldconfig._LEGACY_REGIONS`, split by what each old
region actually *contained*: `africa_cricket` was 68% South Africa, 20% Zimbabwe,
12% Kenya → southern 0.88 / east 0.12), applied **on read** rather than by a
one-shot migration — the rows are already out in saves nobody will run a script
against, and the read point is where all of them pass through. Anything still
unresolvable is dropped *and logged*, because a weight the picker cannot draw is a
hole in the mix, not a weight.

### Reading config inside a transaction deadlocks

`worldconfig.get()` opens its own connection and issues `CREATE TABLE IF NOT
EXISTS`, which takes a write lock — and world and GTT tables **share one SQLite
file**. Reading config while `create_league` holds pending INSERTs is a
`database is locked`.

This was latent for as long as the picker needed one config key: that key was
almost always already cached, so the second connection was never opened. Restoring
the US share added a second key (`intl_share`), a cold read became likely, and
**20 of 21 GTT tests failed at once**. `_prime_world_config()` loads the whole
settings snapshot at the entry point, before any transaction opens.

## 8. The pro league was never short of players

> *"the GTT should always have enough players there are tens of thousands of them
> … so idk why the GTT wouldn't have players."*

Correct, and the founding draft was seating **112 generated players out of 112**
on a fresh world anyway. Not a shortage: `world_graduates` is written **at a year
rollover**, so a league founded in world year 0 queried an empty table, and
`create_league`'s own docstring blessed the outcome — *"a fresh save with no
graduates yet gets the classic all-founder inaugural league."* The archive was
missing; the players were not. A year-0 world holds ~2,262 programs and roughly
**7,300 seniors** about to graduate.

With no archived class the founding draft now reads the live about-to-graduate
cohort (`world.departing_now`) — same `_departing` predicate and same row shape as
the archive, resolved through `load_world` so a stale seed can never
`get_or_create` a parallel universe. Measured after: **112 of 112 real college
players**, every pid present in the world.

Deliberately **not** a fallback inside `_world_graduates`. Everywhere else an empty
class means the world binding is broken (the very thing `_active_world_seed`
self-heals), and substituting live players there would convert a visible fault into
plausible-looking data — the failure this codebase keeps relearning. A test pins
that `_intake` never calls it.

The ranking rules are shared rather than copied: `_select_graduates` was split out
of `_world_graduates` so the archived class and the live one go through one set of
D1/non-D1 rules, instead of a league's founding draft and its first off-season
draft ranking players differently.

## Still open

- The generic `african` bucket remains a catch-all for a handful of countries
  (SL, LR, TD) with no dedicated pool.
- ~254 buckets sit under 45 names. All are under 0.3× pressure, so none of them
  repeats in practice — but they are thin if a future preset weights them up.
- A downloaded mix carries the geography only — not the active divisions/genders or
  the coached program. Those are a handful of clicks; the grid was ninety.
