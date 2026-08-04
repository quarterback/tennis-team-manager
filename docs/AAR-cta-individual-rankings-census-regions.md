# AAR — CTA individual rankings (national / regional / newcomer) + census-division regions

## Context

The owner asked to replicate the real ITA's individual rankings surface — its
NATIONAL / REGIONAL / NEWCOMER tabs — for our game, branded **CTA (College
Tennis Association)**. Singles and doubles national boards already existed
(`AAR-ita-rankings-and-seeding.md`); team regional cards already existed
(`AAR-polls-regional-rankings-hometown-territory.md` §5). This session added
the missing pieces and re-cut the region map.

## ⚠️ Owner rules (2027-08) — don't "fix" these

1. **Regions are the nine US Census Bureau divisions, NOT the real ITA's cut.**
   The owner explicitly rejected the ITA's ad-hoc regions ("Texas and the
   Carolinas get a region but California doesn't and is lumped with the PNW").
   The authority is `scout_intel.US_REGIONS` / `US_REGION_ORDER` — census
   divisions by name (New England, Mid-Atlantic, East North Central, West North
   Central, South Atlantic, East South Central, West South Central, Mountain,
   Pacific) **plus a tenth "Outlying" bucket** for the non-contiguous /
   non-state places the owner listed: **DC, AK, HI, PR, USVI, Guam** (DC/AK/HI
   are deliberately pulled OUT of their census divisions), plus AS/MP and BC
   (Simon Fraser, the lone Canadian program). This map also drives the Portal
   Search hometown filter and the team regional cards — one authority, so
   player-origin and team regions stay consistent. `ncaa.STATE_REGION` (the
   coarse recruiting-proximity map) is a DIFFERENT system and was not touched.
2. **Newcomer is D1-only, singles-only, freshmen-only.** The real ITA runs
   newcomer rankings only for D1; ours restricts eligibility to freshmen
   ("first-year players, restricted to freshmen to make it easier" — so a
   first-year *transfer* does NOT qualify, only class Fr). The freshman test is
   `world._base_class(class) == "Fr"` so a medical-redshirt **RS-Fr counts**.
   The route quietly falls back to national scope for any other combination.
3. **Branding is CTA**, matching how the UI already avoids the ITA name (the
   preseason events display as "NIT"). Tooltips/copy say "CTA ranking points";
   the algorithm is unchanged (`sm.ita_*_points` internals keep their names).

## What shipped

- `/rankings` grew a **Scope** pill row (National / Regional / Newcomer) beside
  the View pills, which are now Teams / Singles / Doubles. The old
  `view=regional` team cards live on as `view=teams&scope=regional`, and legacy
  `?view=regional` URLs still work (server-side remap).
- **Regional individual boards** (`state.regional_player_rows`): the national
  singles/doubles board split by each **program's** home region (like the ITA —
  a player belongs to their school's region), top 10 per region as cards, with
  the national rank carried in a NATL column. Region comes from
  `Program.state` (`data/ncaa/locations.json`, researched per school, 100%
  coverage — the census map is tested against it so no school can silently
  drop off the boards).
- **Newcomer board** (`state.newcomer_ranking_rows`): the national singles
  board filtered to freshmen, re-ranked among themselves, capped at 50, with
  CLASS and NATL columns. Shares the min-matches gate.
- Rows in `singles_ranking_rows` / `doubles_ranking_rows` now carry
  `region` (school-based) so any future surface can group without re-deriving.

## Drive-by bugfix

`state.player_career_table`'s live-season rows read `info.get("class_year")`
from `sm.player_info`, but `_pid_index` stores the key as **`"class"`** — the
in-progress season row always showed a blank class. Both sites now read
`"class"`.

## Not done (deliberately)

- **No "as of date" dropdown.** The real ITA site archives dated snapshots;
  ours always shows the live board. Weekly ranking snapshots would need new
  persistence (there is none — polls recompute forward, nothing is stored
  per-week) and weren't asked for.
- **No newcomer doubles** (would be near-empty: pairs are top-2 ladder players,
  rarely two freshmen with 3+ matches together).

## Tests

`tests/test_cta_rankings.py`: census-map integrity against `locations.json`
(every school state maps), division spot-checks + Outlying membership, regional
grouping/order invariants, freshman-only newcomer rows, and route smoke tests
including the newcomer fallback outside D1 singles.
