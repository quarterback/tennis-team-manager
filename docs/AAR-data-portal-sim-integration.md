# AAR — Data portal export feed read a phantom preseason season

**Date:** 2026-06-12
**Scope:** The `/export/data_portal.json` feed (consumed by the vroomtv hub)
reported week-0 / no results while the live save was mid-season. Wire the feed
to the active sim so it mirrors the same season the `/data` page shows.

## Why
Reported in-session: "My current save is week 5 [and the portal] isn't pulling
current data." The on-page data portal (`/data?u=D1-men`) rendered the live
week-by-week season correctly, but the JSON export feeding the external hub
looked like a freshly-started league — preseason phase, no live results, no
scores — even though the world had been advanced for weeks.

## Root cause
`seasonmode.get_or_create(division, gender, *, seed)` matches the `division`
string **literally** against the `seasons` table (`app/seasonmode.py:200-207`).
Every surface that drives or reads the live sim uses the canonical **uppercase**
identifiers — `app.world.UNIVERSES` is `[("D1","men"), …]`, and the web
`_universe()` resolver hands pages `"D1"` (`app/web/server.py:137-142`).

The export route alone looped over **lowercase** divisions:

```python
for div in ("d1", "d2", "d3"):
    for gnd in ("men", "women"):
        portal = data_portal_view(div, gnd)   # "d1" != "D1"
```

So `get_or_create("d1", …)` never matched the advanced `"D1"` row and instead
**created a brand-new season** at preseason (week 0, no duals). `load_division`
lowercases its file path, so `"d1"` loaded a valid roster and nothing crashed —
the fork was silent. The feed served that phantom season; the live one was
untouched.

Reproduced directly — same call, two casings, against a world advanced a few
weeks (one active universe for speed):

| path                          | phase   | current_week | has_live_results | completed_duals | recent |
|-------------------------------|---------|--------------|------------------|-----------------|--------|
| `data_portal_view("D1", …)`   | regular | 4            | True             | 995             | 10     |
| `data_portal_view("d1", …)`   | regular | 1            | **False**        | **0**           | **0**  |

## Fix
Resolve each universe in the export route by its canonical identifier from
`UNIVERSES` — the same ids the `/data` page already uses — so the feed reads the
advanced season instead of forking a new one:

```python
for _u, division, gender, label in UNIVERSES:
    portal = data_portal_view(division, gender)   # canonical "D1"
    universes.append({"division": division.lower(), "gender": gender,
                      "label": label, **{...}})
```

The emitted `"division"` stays lowercase (`"d1"`) and the `"label"` is unchanged
(`"D1 Men"`), so the hub's consumer contract is preserved — only the data behind
it is now live. After the fix, against a world advanced to week 5 the feed
reports `phase=regular, current_week=6, has_live_results=True,
completed_duals=1227`, with populated rankings and recent scores.

The root-cause class — a lowercase caller silently forking a parallel season —
could be eliminated globally by canonicalizing division/gender inside
`get_or_create`. That was deliberately **not** done here: it's a broad change to
a core function with its own test surface, and every other caller already passes
canonical ids. The export route was the lone outlier, so the fix stays local and
reads like the rest of the app.

## Tests
`tests/test_web_season.py::test_data_portal_export_reflects_live_sim` — creates
the D1-men season, advances a few weeks, then asserts the export feed's d1-men
universe matches the advanced season (`current_week`, `has_live_results`,
`completed_duals > 0`) rather than a preseason fork. Fails against the old
lowercase-keyed route; passes now. Full season/web/seasonmode suites green.

## Files touched
- `app/web/server.py` — `export_data_portal()`: iterate canonical `UNIVERSES`
  instead of hardcoded lowercase divisions; comment explaining the literal-match
  fork hazard.
- `tests/test_web_season.py` — regression test above.

## Not touched (and why)
- The `/data` **page** (`data_portal()` → `_universe()`) was already correctly
  wired to the live season; no change needed.
- `seasonmode.get_or_create` case-normalization — see the trade-off note in
  **Fix**.
