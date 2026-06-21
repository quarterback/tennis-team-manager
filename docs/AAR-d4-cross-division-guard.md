# AAR — Guard D4 against non-adjacent cross-division duals

**Date:** 2026-06-21
**Scope:** One-line-of-logic fix in `world._allowed_cross`, flagged by a review of
the D4 work.

## The bug

Cross-class non-conference scheduling lets teams play **one classification away**
(adjacent), plus a single exception: an academically elite D3 (NESCAC/UAA-type) may
reach up to D1. The exception was coded with a fallback that *assumed* one side of a
non-adjacent pair was D3:

```python
d3 = a if a.division == "D3" else b
return d3.academics >= ELITE_D3_ACADEMICS
```

Before D4 existed every non-adjacent pair was indeed D1+D3, so this held. Adding D4
to `DIV_RANK` introduced D1/D4 (rank gap 3) and D2/D4 (gap 2) pairs where **neither
side is D3** — the fallback then tested whichever side wasn't D3, so an academic D4
team (academics ≈ 0.94) cleared the bar and got scheduled. `cross_schedule` produced
hundreds of D1/D4 and D2/D4 duals: D4 teams playing two or three classifications up.

## The fix

Guard the exception to exactly the D1+D3 pairing it was written for; everything else
non-adjacent is rejected:

```python
if {a.division, b.division} == {"D1", "D3"}:
    d3 = a if a.division == "D3" else b
    return d3.academics >= ELITE_D3_ACADEMICS
return False
```

D4 now only ever draws its **adjacent** class (D3) — the geographic, capped
cross-class sliver — and never D2/D4 or D1/D4.

## Verification

`cross_schedule(2026, 2026)` pairings after the fix:

| pairing | duals |
|---|---|
| D1–D2 | 1360 |
| D2–D3 | 350 |
| D3–D4 | 928 |

Zero D1/D4 or D2/D4; D4 pairs only with D3. World/season/season-mode tests pass; no
new failures.
