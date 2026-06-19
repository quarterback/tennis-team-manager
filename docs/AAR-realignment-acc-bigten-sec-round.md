# AAR — Realignment round: ACC/Big Ten/SEC reshuffle, UAA & Yankee rebuild, three promotions

**Date:** 2026-06-19
**Scope:** A user-directed realignment round across `data/ncaa/*.json`: 15
within-D1 conference moves plus 3 cross-division promotions. Both genders kept
identical; every step validated to keep each division summing with no school
double-listed.

## Moves

**Within D1 (conference change)**

| School | From → To |
|---|---|
| RPI | Meridian → UAA |
| Rice | CIC → UAA |
| Vanderbilt | SEC → ACC |
| Kentucky | SEC → ACC |
| Louisville | Yankee → ACC |
| Virginia Tech | Yankee → ACC |
| Richmond | CUSA → ACC |
| Maryland | ACC → Big Ten |
| UMass | CIC → Yankee |
| Army | CIC → Yankee |
| Navy | CIC → Yankee |
| Air Force | CIC → Mountain West |
| Grand Canyon | Mountain West → WAC |
| Tennessee State | Summit → SEC |
| Notre Dame | Yankee → SEC |

**Cross-division promotions**

| School | From → To |
|---|---|
| West Chester | D2 PSAC → D1 America East |
| Montclair State | D3 NJAC → D1 NEC |
| UW-Whitewater | D3 WIAC → D1 MAC |

## Net effect

- **Counts:** D1 392 → **395** (+3 promotions); D2 286 → **285** (−West Chester);
  D3 406 → **404** (−Montclair State, −UW-Whitewater).
- **Touched conference sizes (D1):** ACC 16, SEC 16, Big Ten 18, Yankee 12 (−3
  out, +3 in, net flat), **CIC 8** (shed Rice, UMass, Air Force, Army, Navy),
  UAA 10, Meridian 9, CUSA 8, Mountain West 12 (−Grand Canyon, +Air Force),
  WAC 11, Summit 9, America East 10, NEC 10, MAC 14.
- The big mover is the **CIC**, which dropped from 13 to 8 as the service
  academies, UMass, and Rice all left — leaving it a tight mid-tier league.

## Implementation notes

- A single script loaded all six files, applied moves by **exact** team-name match
  (so "Kentucky" never caught "Northern/Western/Eastern Kentucky", "UMass" never
  caught "UMass Lowell", "Maryland" never caught "Loyola Maryland"), removed each
  school from its one current home, and appended it to the target conference. Each
  conference's `teams` list is re-sorted alphabetically to match the file
  convention, keeping the diff minimal.
- **Naming:** the move list said "Wisconsin-Whitewater"; the data carries the
  school as **"UW-Whitewater"**. Kept the existing string so its logo and location
  wiring (keyed by exact name) stay intact rather than orphaning them on a rename.
- **Promotions need no new metadata:** all three schools already had
  `locations.json` entries from their D2/D3 life, so cross-division scheduling
  proximity works immediately; rosters generate via the normal D1 path (D3/D2 had
  no athletic-aid plan, D1 now applies the budget economy).

## Verification

- Per division, both genders: rosters sum (395 / 285 / 404), **no double-listing**,
  men and women memberships identical, all six files load through
  `ncaa.load_division`.
- Built rosters for every moved school and confirmed its new `conf_abbr`; D1
  `ranking_rows` returns 395.
- `tests/test_league.py` (data integrity) and the rest of `test_roster.py` pass.

## Not touched (and why)

- `tests/test_roster.py::test_roster_talent_tracks_program_strength` fails on this
  branch — but it fails **identically on the clean tree** (a pre-existing flake
  from the earlier talent-calibration tuning: a synthetic "Strong U"/"Weak U"
  small-roster assertion that inverts for those specific seeds). It is unrelated to
  conference data and was left for a separate fix.
- No prestige / strength / schedule tuning this round — pure membership edits.

## Files
- `data/ncaa/d1_men.json`, `d1_women.json` — 15 within-D1 moves + 3 promotions in.
- `data/ncaa/d2_men.json`, `d2_women.json` — West Chester out.
- `data/ncaa/d3_men.json`, `d3_women.json` — Montclair State, UW-Whitewater out.
