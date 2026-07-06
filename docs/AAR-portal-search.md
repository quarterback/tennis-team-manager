# AAR — Portal Search (searchable placeable pool by hometown / region / class)

> **Status:** shipped. A new **Analytics Bureau › Portal Search** page (`/intel/portal-search`)
> turns the whole rostered universe into a filterable directory you scan when deciding
> *who to move* in the transfer portal — by **where a player is from** (US state, US region,
> or domestic vs international), plus class and division, sorted by talent / form / origin.

## 1. The problem (owner)
Placing players in the portal ("redirect a riser", "add a player", "sign a pro") means finding
someone in a **massive** dataset with no way to slice it. The owner wanted, for immersion, to
browse by **hometown state (US only)**, **international vs domestic**, and **class / region of
the country** — none of which the portal slate exposes.

## 2. The data was already on the player
`Prospect` already carries `hometown` ("City, ST" for domestic, "City, NAT" for international),
`domestic` (bool), `country` (ISO2), and `class_year`. The god-mode `scout_intel.scan()` builds
an `Intel` per rostered player across all four divisions — the perfect backing set. It just
didn't carry hometown/domestic through.

## 3. The build
- **`scout_intel.Intel`** gained `hometown` + `domestic` (populated in `scan()` from the prospect).
  Added in the *trailing defaulted* field block to avoid a dataclass default-before-required error.
- **US region map** (`US_REGIONS`, `US_REGION_ORDER`): a recruiting-style **6-way** cut —
  Northeast, Mid-Atlantic, Southeast, South Central, Midwest, Mountain, West Coast (finer than the
  4 Census regions where tennis density warrants it; DC files under Mid-Atlantic). Helpers
  `home_state(r)` (parses "…, ST" only for domestic, validated against the map) and `home_region(r)`.
- **`portal_search(gender, …)`**: filters the full scan by `scope` (all / us / intl), `state`,
  `region`, `division`, `class_year`, and `q` (name / school / **hometown**); sorts by `talent`,
  `now` (live STR), `state` (US first, then A–Z), `class` (Fr→Sr), or `name`. Mirrors the existing
  `underplaced_board` server-side filter pattern. `portal_search_states()` returns only the states
  actually present, in region-then-alpha order, so the dropdown never offers an empty state.
- **Route** `/intel/portal-search` + **template** `intel_portal_search.html` (toolbar of dropdowns
  + a FROM column: state chip w/ region tooltip + city for domestic, flag/country for intl; each row
  links to the profile and the Fit Finder). Reuses `_pager` (preserves all filter args).
- **Discoverability**: nav item **Portal Search** (Analytics Bureau), a hub KPI card, and a
  **"🔎 Search players"** button on both the pre-season and fall portal pages next to *Add a player*
  — so you narrow to the profile you want, then type the name into the portal's add box.
- **Gender is a first-class filter** (not just the buried universe key): a **Gender** dropdown —
  **Men / Women / Both** — leads the toolbar. Defaults to the current universe gender; picking one
  gender ~halves the rows loaded (Men+D1 = ~4.6k vs ~28.7k for Both). `Both` merges the two per-gender
  scans and shows an **M/W chip** per row so they stay distinguishable. The portal buttons carry the
  tab's gender straight in (`men`/`women`/`all`→Both; the mixed-gender fall portal opens on Both).

## 4. Why a read-only analytics page (not inline portal actions)
The portal slate is small and curated; the *placement* decision needs the whole ~14k-player pool.
Keeping Search decoupled and read-only (analytics lab) means it works regardless of which portal
window is open, and never entangles the cascade engine. Placement stays on the portal pages; Search
is the scouting lens that feeds them.

## 5. Files touched
- `app/scout_intel.py` — `Intel.hometown/domestic`; `US_REGIONS`/`home_state`/`home_region`;
  `portal_search`, `portal_search_states`.
- `app/web/server.py` — `/intel/portal-search` route + nav item.
- `app/web/templates/intel_portal_search.html` (new); `intel_hub.html`, `preseason_portal.html`,
  `fall_portal.html` — entry points.
