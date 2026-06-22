# AAR — Meridian "nerdy major" build + academic-school realignment (round 2)

**Date:** 2026-06-22
**Scope:** Data realignment of academic/tech schools across D1/D3/D4, two brand-new
academic-only schools, and academic tagging. All data + one `ncaa.py` dict; no engine
logic changed.

## The thread

Started from "should MIT move to D1? — it got left behind." MIT sat in D4/NEWMAC while
its UAA-tier peers were in D1. Resolution evolved over several steps:

1. **MIT stays D4? → no, build Meridian instead.** MIT's true twin (Caltech) and the
   NESCAC elites are all in D4, so MIT wasn't really "behind." But NEWMAC was a weak
   home. The chosen fix: turn the existing D1 **Meridian** conference (big publics +
   Clarkson/Union/St. Lawrence/RIT) into a "nerdier major conference" by adding marquee
   academics.

## Changes

### Conference moves
| School | From → To |
|---|---|
| MIT | D4/NEWMAC → **D1/Meridian** |
| WPI | D4/NEWMAC → **D1/Meridian** |
| Illinois Tech | D3/NACC → **D1/Meridian** |
| Merchant Marine | D3/Skyline → **D4/NEWMAC** |

### New schools (academic-only — no real varsity athletics, added for the sim)
| School | Conf | Location |
|---|---|---|
| **Olin** | D4/Liberty League | Needham, MA |
| **Reed** | D4/SCIAC | Portland, OR |

Reed first went to NWC but that's a non-lift conference (prestige ~0.06 despite 0.92
academics); moved to SCIAC — which already holds the Pacific-NW academics Whitman &
Lewis & Clark — so it gets the academic lift (~0.31). Locations added to
`locations.json`; logos are the only thing missing (cosmetic, initials fallback).

### Academic tags (`ncaa.ACADEMIC_SCHOOLS`)
So they read as academics instead of inheriting a conference's mid-major prior:
- **Meridian cluster:** WPI 0.88, Illinois Tech 0.86, Clarkson 0.83, Union (NY) 0.88,
  RIT 0.82, St. Lawrence 0.85 (MIT already 0.99).
- **New schools:** Reed 0.93, Olin 0.93.
- **Service academies:** Coast Guard 0.86, Merchant Marine 0.86 (Army/Navy/Air Force
  were already tagged — the user asked that *all* service academies carry the tag).

## Result

- **Meridian (D1)** academic cluster is now 7 — MIT, WPI, Illinois Tech, Clarkson,
  Union, RIT, St. Lawrence — amid the big publics (Bemidji State, Grand Valley,
  Michigan Tech, Minnesota State, Rowan): the intended tech-flavored power conference.
- **D4** gained Olin (Liberty League) and Reed (SCIAC), both lifted academics, plus
  Merchant Marine (NEWMAC).
- Data integrity verified each step: no school in two divisions, men == women
  memberships, all divisions load, new-school rosters build.

## Note

MIT/WPI/Illinois Tech are now scholarship-tier D1 (they recruit via the budget
economy) — deliberately off real-life (these schools don't give athletic aid) in
service of the "nerdy major conference" concept.
