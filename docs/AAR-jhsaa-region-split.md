# AAR — the Halbrook Basin four-way region split (owner rule 2026-08)

## Why (the owner's own framing — this is the rationale of record)

> "regional teams were essentially our version of 'newspaper all-area teams'
> and so breaking up the massive halbrook one was a win, so many kids got
> screwed out of honors for years."

All-Region is the association's newspaper all-area team. The Halbrook Basin
AREA had grown to **222 girls' / 204 boys' programs** — four times any other
region — so one ~18-selection All-Region team (ten singles + eight doubles
pairs) drawn from ~220 programs was the same honour a 50-program region hands
out, stretched over four times the field. Years of deserving players were
crowded out by geography alone. The split restores the honour's intended
reach: four regions of ~55 programs each, matching every other big region's
density.

It also resolved **Silver Basin**: a 3-program Ruby-County-only area (the 2046
Great Basin expansion's `NET_NEW_AREAS` remnant) sitting BELOW the All-Region
4-program floor (`MIN_REGION_PROGRAMS`), so its three programs could win no
regional honour at all. It absorbs the Vance County Group 1/2 departures and
becomes a full region.

## The owner's table, verbatim

| New region | Territory | Programs (approx, owner's count) |
|---|---|---:|
| Belmonte Metro | Belmonte + Caswell | 58 |
| Halbrook Basin | Rest of Halbrook County | 57 |
| Boise Frontier | Barlowe County + Belyakov + Orellana | 54 |
| Silver Basin | Rest of Vance County + Ruby County | 56 |

## What the data said (resolution)

The pre-split Halbrook Basin area spanned exactly three counties: **Halbrook
(115 rows), Vance (93), Barlowe (14)**. Belmonte (44 schools) and Caswell (14)
are both CITIES in Halbrook County — not counties — so Belmonte Metro is a
city cut, not a county cut. Belyakov (29) and Orellana (11) are the two Vance
County cities that stayed on the 1A–9A ladder; the rest of Vance (53 rows, all
Group 1/Group 2) goes to Silver Basin beside Ruby County's existing 3. Every
school in the old area landed in exactly one bucket — no county or city fell
outside the owner's table.

## Measured counts vs the table

| Region | Owner | Total rows | Girls | Boys |
|---|---:|---:|---:|---:|
| Belmonte Metro | 58 | **58** | 58 | 51 |
| Halbrook Basin | 57 | **57** | 57 | 55 |
| Boise Frontier | 54 | **54** | 54 | 51 |
| Silver Basin | 56 | **56** | 56 | 50 |

The owner's counts are total program rows (girls' sponsorship is the superset,
so they equal the girls' counts). Zero deviation.

## All-Region tier outcomes

`AR_TIER2_MIN_PROGRAMS` is 45: **all four regions clear it in BOTH genders**
(worst case Silver Basin boys at 50), so each crowns a First AND Second Team —
the thresholds are counts, not names, and needed no change. No region now
clears `AR_HM_MIN_PROGRAMS` (100) — that is the rule working, not a dead
constant: the point of the split was that no region should be that outsized;
the threshold stays for whenever one grows back. Silver Basin goes from
below-floor (3 < `MIN_REGION_PROGRAMS` 4, no team at all) to a two-team region.

## Mechanics

- **`import_jhsaa.split_area(area, county, city)`** — the named-table
  convention (RECLASSIFY_TO_2A's pattern), applied at EMIT beside
  `AREA_RENAMES`. District drawing sorts on the SOURCE area, so the split
  cannot move a league; league membership is unchanged, only the area label.
  An unmapped Halbrook Basin county warns loudly rather than defaulting.
- **`LEAGUE_NAMES` affinities keyed "Halbrook Basin" are untouched** —
  affinity matches at draw time on the source area, before the split runs, so
  re-pointing an entry to a post-split name would make it never match.
- **Gazetteer**: `scripts/jefferson_gazetteer.py` applies the same
  `split_area` to prep-network's place rows, so the two-repo area-agreement
  assertion holds WITHOUT extending `NET_NEW_AREAS` — both sides now say
  Belmonte Metro / Boise Frontier / Silver Basin for the split ground.
  Regenerated, along with `docs/JHSAA-school-names.txt`.
- **Committed data** (`data/jhsaa/schools.json`): 165 rows changed area
  (58 → Belmonte Metro, 54 → Boise Frontier, 53 → Silver Basin); a re-import
  reproduces it via `split_area`. The 2046 expansion script needed nothing —
  its Ruby rows already said Silver Basin and it never rewrites a current
  school's area.
- **Non-district pairing** (county → area → anywhere) shifts pools slightly
  with the new labels — expected, no code change. All-Region is group-blind,
  so the Great Basin (Group 1/2) schools legitimately belong to these regions.
- **`app/jhsaa_awards.py`** docstrings updated where they cited pre-split
  Halbrook counts as the live example; both thresholds unchanged.
