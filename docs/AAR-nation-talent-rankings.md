# AAR — National talent rankings (investment / grassroots)

**Purpose:** a single visible reference for *which countries are the top talent
producers* in the sim, so the per-nation ratings don't have to be re-derived from
`generators/data/names/nation_talent.json` each time. Snapshot generated from the
current `nation_talent.json`. Re-run the script at the bottom after any edit to refresh.

## What the two ratings mean

Each nation carries two 0–100 ratings (keyed by ISO 3166-1 alpha-2; **absent code =
neutral 50/50**, so any small nation still generates at tour-average with full
variance and the occasional gem). See `generators/nation_talent.py` for the math.

- **investment** — top-end funding (national academies, junior ITF / college
  pathways, private-coaching depth). Drives the **elite spike** — the chance a
  generated player from that nation is a blue-chip.
  - `elite_index = 0.7·investment + 0.3·grassroots` → blue-chip probability
    `0.001 + (elite_index/100)·0.009` (≈ 1-in-1000 up to 1-in-100).
- **grassroots** — breadth of development (clubs, courts, participation). Drives the
  **average-quality lift** applied to *every* player from that nation.
  - `lift_index = 0.4·investment + 0.6·grassroots`; talent shift
    `round((lift_index − 50)·0.16)`, **capped at ±8** grade points.

## The top tier (the names to remember)

- **Elite producers (investment ≥ 84):** Spain, France, USA, Italy — the four that
  reliably stack blue-chips.
- **Strong (investment 76–80):** Canada, Russia, Germany, Australia, Great Britain,
  Czechia.
- **Solid tour nations (investment 70–74):** Serbia, Argentina, Japan, China,
  Switzerland.
- Everyone below ~66 trends toward tour-neutral; everyone absent from the table *is*
  neutral (50/50).

## Full ranking — by investment (ties broken by grassroots)

| # | Nation | Investment | Grassroots | Elite index | Lift index |
|---|--------|-----------:|-----------:|------------:|-----------:|
| 1 | Spain (ES) | 92 | 86 | 90.2 | 88.4 |
| 2 | France (FR) | 88 | 86 | 87.4 | 86.8 |
| 3 | United States (US) | 88 | 82 | 86.2 | 84.4 |
| 4 | Italy (IT) | 84 | 78 | 82.2 | 80.4 |
| 5 | Canada (CA) | 80 | 72 | 77.6 | 75.2 |
| 6 | Russia (RU) | 80 | 70 | 77.0 | 74.0 |
| 7 | Germany (DE) | 78 | 74 | 76.8 | 75.6 |
| 8 | Australia (AU) | 78 | 72 | 76.2 | 74.4 |
| 9 | Great Britain (GB) | 78 | 64 | 73.8 | 69.6 |
| 10 | Czechia (CZ) | 76 | 74 | 75.4 | 74.8 |
| 11 | Serbia (RS) | 74 | 54 | 68.0 | 62.0 |
| 12 | Argentina (AR) | 72 | 72 | 72.0 | 72.0 |
| 13 | Japan (JP) | 72 | 66 | 70.2 | 68.4 |
| 14 | China (CN) | 70 | 58 | 66.4 | 62.8 |
| 15 | Switzerland (CH) | 70 | 54 | 65.2 | 60.4 |
| 16 | Belgium (BE) | 66 | 58 | 63.6 | 61.2 |
| 17 | Croatia (HR) | 66 | 56 | 63.0 | 60.0 |
| 18 | Netherlands (NL) | 64 | 58 | 62.2 | 60.4 |
| 19 | Austria (AT) | 64 | 56 | 61.6 | 59.2 |
| 20 | Poland (PL) | 64 | 56 | 61.6 | 59.2 |
| 21 | Sweden (SE) | 62 | 56 | 60.2 | 58.4 |
| 22 | Kazakhstan (KZ) | 62 | 44 | 56.6 | 51.2 |
| 23 | Brazil (BR) | 60 | 62 | 60.6 | 61.2 |
| 24 | Greece (GR) | 60 | 48 | 56.4 | 52.8 |
| 25 | Bulgaria (BG) | 58 | 48 | 55.0 | 52.0 |
| 26 | Denmark (DK) | 58 | 48 | 55.0 | 52.0 |
| 27 | Norway (NO) | 58 | 44 | 53.8 | 49.6 |
| 28 | Hungary (HU) | 56 | 52 | 54.8 | 53.6 |
| 29 | Slovakia (SK) | 56 | 52 | 54.8 | 53.6 |
| 30 | Ukraine (UA) | 56 | 50 | 54.2 | 52.4 |
| 31 | Slovenia (SI) | 56 | 50 | 54.2 | 52.4 |
| 32 | Romania (RO) | 56 | 50 | 54.2 | 52.4 |
| 33 | Chinese Taipei (TW) | 56 | 50 | 54.2 | 52.4 |
| 34 | Chile (CL) | 54 | 52 | 53.4 | 52.8 |
| 35 | Finland (FI) | 54 | 50 | 52.8 | 51.6 |
| 36 | Portugal (PT) | 54 | 50 | 52.8 | 51.6 |
| 37 | Korea (KR) | 54 | 48 | 52.2 | 50.4 |
| 38 | Colombia (CO) | 52 | 52 | 52.0 | 52.0 |
| 39 | Mexico (MX) | 50 | 50 | 50.0 | 50.0 |
| 40 | India (IN) | 50 | 48 | 49.4 | 48.8 |
| 41 | Turkey (TR) | 50 | 48 | 49.4 | 48.8 |
| 42 | South Africa (ZA) | 48 | 46 | 47.4 | 46.8 |

> Every ISO code **not** in this table generates at the neutral 50/50 baseline by
> design (the non-major-market floor) — see `nation_talent.json` `_doc`.

## Change log

- **2026-06:** Canada bumped **investment 74→80, grassroots 66→72** (moves it from
  mid-pack to #5 overall), alongside a ~2.5–3× boost to Canada's *population* weight
  across the nationality presets (`regions.json`: `tennis_global` 0.03→0.08, etc.).
  Canadians are now both more numerous and slightly stronger.

## Regenerate this table

```python
import json
from generators.flavor import country_name
r = json.load(open('generators/data/names/nation_talent.json'))['ratings']
rows = []
for code, v in r.items():
    inv, gr = v['investment'], v['grassroots']
    rows.append((code, country_name(code) or code, inv, gr,
                 0.7*inv + 0.3*gr, 0.4*inv + 0.6*gr))
rows.sort(key=lambda x: (-x[2], -x[3]))
print("| # | Nation | Investment | Grassroots | Elite index | Lift index |")
print("|---|--------|-----------:|-----------:|------------:|-----------:|")
for i, (c, n, inv, gr, e, l) in enumerate(rows, 1):
    print(f"| {i} | {n} ({c}) | {inv} | {gr} | {e:.1f} | {l:.1f} |")
```
