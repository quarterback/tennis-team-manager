# AAR — Cross-division scheduling: geography- and prestige-gated reach

**Date:** 2026-06-21
**Scope:** `world._allowed_cross` + `world.cross_schedule`. Started as a bug fix for
D4 cross-class scheduling; refined into a geography- and prestige-gated cross-class
model.

## The bug

Cross-class scheduling let teams play one class away plus an "academically elite D3
reaches D1" exception, coded with a fallback that assumed every non-adjacent pair was
D1+D3:

```python
d3 = a if a.division == "D3" else b
return d3.academics >= ELITE_D3_ACADEMICS
```

Adding D4 created D1/D4 (gap 3) and D2/D4 (gap 2) pairs where neither side is D3; the
fallback tested the wrong side, so an academic D4 (academics ≈ 0.94) cleared the bar
and `cross_schedule` produced hundreds of duals two/three classes up.

## The model (after iterating with the user)

Cross-class play stays a **local, capped sliver** but is allowed to reach up when it
makes sense — driven by geography and, for the top tier, prestige:

1. **`cross_schedule` only pools same / adjacent-region opponents** and caps each team
   at `MAX_CROSS` per gender (unchanged).
2. **Class-distance weighting** (`CROSS_GAP_DECAY = 0.10`): a candidate's pick weight
   decays by `0.10` per extra class of separation (adjacent = 1, two up = 0.10, three
   up = 0.01). So a team plays mostly its adjacent class, with bigger reaches rare —
   without this, D1 (large and everywhere) buried D4 schedules in D1 games.
3. **`_allowed_cross` asymmetry by the higher class:**
   - adjacent classes always pair (D1-D2, D2-D3, D3-D4);
   - a **D2** may reach down to D4 anywhere nearby (geography is enough);
   - a **D1** reaches down to a D3/D4 only when the smaller school is a **prestige
     peer** (`prestige ≥ CROSS_D1_PRESTIGE = 0.25`, i.e. a lifted academic program) or
     a **same-region** neighbor — a top program doesn't drop two/three classes for a
     random small school far afield. UAA stays in D1; this is what lets an academic D4
     (Williams-tier) still draw a nearby/peer D1.

## Measured (`cross_schedule(2026, 2026)`)

| pairing | duals | note |
|---|---|---|
| D1–D2 | 1305 | adjacent |
| D3–D4 | 900 | adjacent — D4's main cross-class |
| D2–D3 | 311 | adjacent |
| D2–D4 | 94 | D2 reaches D4 (geographic) |
| D1–D3 | 85 | D1↔D3, same-region only |
| D1–D4 | 53 | 26 prestige-peers + 27 same-region |

D4 cross-class opponents land ≈ 78% D3 / 9% D2 / 12% D1 — adjacent dominant, the
reach up a thin geographic/prestige sliver. Deterministic; world/season tests pass,
no new failures.
