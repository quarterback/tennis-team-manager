# AAR — World phase stuck on 'regular' in single-gender saves

**Date:** 2026-06-15
**Scope:** A women-only save sat on "Regular season in progress" at world week
21–25 and kept letting the player "Advance week," even though the women's
seasons were already in the NCAA bracket / complete. Reported as the sim being
"a week ahead" and "letting me simulate week 21 when it's supposed to be the
playoffs."

## Why
The world runs one shared clock across six universes (D1/D2/D3 × men/women), but
a player can activate only some of them — the rest are seeded (players exist) but
left **dormant** to save memory/CPU. In a women-only save the men's seasons stay
frozen at week 1 in `phase='regular'`. The World Hub counted those dormant
universes toward the world's state.

## Root cause
Three spots aggregated over **all** universes (or hardcoded D1-men), while the
actual finalize trigger (`world._all_complete`) correctly filtered to active
ones — so the engine kept advancing while the UI misreported the phase:

1. `state.world_hub` looped over all `UNIVERSES`. `stage = min(phase)` was pinned
   to `regular` by the dormant men; `complete = all(phase=='complete')` could
   never be true (dormant men never finish) → the stepper never reached
   Awards/Offseason and "Advance week" ran the world clock forever.
2. `state.world_hub` `awards_done` hardcoded `honors.has_season(year, "D1",
   "men")` — never stamped in a women-only save.
3. The `/world/advance` route gated on that same hardcoded D1-men honors check,
   so once the women's seasons finished, progression would have **jammed**
   entirely (waiting on men's awards that never stamp).

The "week ahead" was cosmetic: `seasonmode` `current_week` is the *next* week to
play (1-based, bumped after playing), so a division's "wk X/total" reads one
ahead of the world clock.

What was NOT the cause: the recent awards-display gating and dreamsheet changes —
those touch presentation and recruit shortlists only, never season progression.
A both-genders simulation confirmed the engine transitions on schedule
(D1 regular weeks 1→18, then conf_tournaments).

## Fix
Make the hub and the advance gate active-universe-aware, mirroring
`_all_complete`:

- `world_hub` builds `divisions` from active universes only
  (`worldconfig.is_active`); `stage`/`complete` derive from those; `awards_done`
  requires honors stamped for **every active** universe (never a dormant one).
- `/world/advance` holds at the awards step only while honors are pending for an
  **active** universe (`world._active_unis()`), not `("D1","men")`.

No engine, scheduling, or finalize changes — those were already correct.

## Verified
End-to-end women-only run progressed cleanly:

```
week  0 -> stage=regular            complete=False awards_done=False
week 18 -> stage=conf_tournaments   complete=False
week 21 -> stage=ncaa               complete=False
week 27 -> stage=awards             complete=True  awards_done=False
        -> run awards (2407 honors)
        -> stage=offseason          awards_done=True
```

New `tests/test_world_single_gender.py` guards the regression (World Hub counts
only active universes); `test_world.py` passes (9/9 with the new test).

## Follow-ups (not done)
- Other surfaces may still assume all universes are active (e.g. dashboard /
  data-portal loops over `UNIVERSES`); they render dormant universes' week-1
  state but don't gate world progression, so they're cosmetic — worth a sweep if
  single-gender saves become common.
- The per-division "wk X/total" could subtract one (or relabel as "next week")
  to remove the cosmetic off-by-one against the world clock.
