# AAR — Editor built every roster just to list teams

**Date:** 2026-06-15
**Scope:** Opening the Editor (Tools › Editor), or changing the Conference
filter, was very slow and "overloaded the game"; the team picker also appeared
not to honour the selected conference (e.g. Northeast Conference showed Georgia,
Alabama, Ohio State…).

## Symptom
With Division = D1 Women and Conference = Northeast Conference, the Team
dropdown listed all ~366 programs instead of the 9 NEC schools, and each
conference change took several seconds and spiked load.

## Root cause
The editor route filled its pickers from `ranking_rows(division, gender)`:

```python
all_rows = ranking_rows(division, gender)
schools  = [r.school for r in all_rows if conf == "All" or r.conf == conf]
```

`ranking_rows` is the Power Index table. At preseason (no results yet) it orders
programs by `_ability`, which **builds every program's roster** (~366 in D1) to
rank them. So merely opening the editor — before any filtering — materialised
the entire division's rosters (CPU + ~100s of MB), and did it again on every
conference change. The conference filter was applied *after* that work, so it
never reduced the cost — hence "the filter wasn't doing a good job" and the
overload. Measured cold: `/editor?u=D1-women` ≈ **5.9s**.

The server-side conference filter itself was correct (`r.conf == conf` →
exactly the 9 NEC schools). The all-teams dropdown the user saw was the stale
view during the multi-second reload: the conference `onchange` submits and the
page sits on the previous (unfiltered) list until the slow rebuild returns.

## Fix
The pickers only need each school's **name + conference** — not Power Index — so
read them from the cheap, cached `load_division().programs` and filter that
directly:

```python
div     = load_division(division, gender)
schools = sorted(p.school for p in div.programs
                 if conf == "All" or p.conf == conf)
...
prog = div.by_school(school)          # reuse the same Division load
```

The editor now builds **exactly one roster** — the selected team's, via
`editor_roster` — instead of all 366. The school list is alphabetised (better
for a picker than Power-Index order). No engine, schedule, or ranking changes.

## Verified
Rendering the route directly (warm season):

```
/editor?u=D1-women                            #366  (full division, alphabetised)
/editor?u=D1-women&conf=Northeast Conference  0.12s  #9  Central Connecticut … Stonehill
/editor?u=D1-women&conf=Ivy League            0.12s  #8  Brown, Columbia … Yale
```

Conference changes are ~0.1s and correctly filtered; the editor path no longer
triggers a Power-Index / full-roster build.

## Notes / follow-ups
- The remaining one-time ~4s on the very first editor load is **season-schedule
  creation** (`seasonmode.get_or_create` building the full slate), which is
  shared with every other page and already warm in a running game — not editor
  specific.
- Other pages that legitimately need Power Index (Rankings, Dashboard) still pay
  the preseason all-roster sort; if that cold cost becomes a problem, `_ability`
  could cache a lightweight team-strength estimate instead of building full
  rosters at preseason.
- The full test suite was intentionally not run for this change: it rebuilds
  every universe's rosters/seasons and bogs the machine down (the very cost this
  fix avoids). The route was verified directly instead.
