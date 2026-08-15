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

## Still open

- The generic `african` bucket remains a catch-all for a handful of countries
  (SL, LR, TD) with no dedicated pool.
- ~254 buckets sit under 45 names. All are under 0.3× pressure, so none of them
  repeats in practice — but they are thin if a future preset weights them up.
- There is no user-saveable *named* preset; the five are authored in the data file.
