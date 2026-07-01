# AAR — Pre-season portal scans ALL divisions (not just active universes)

## Symptom

On a full D1–D4 world the **pre-season portal** showed `0 rising · 0 cascading` /
"No moves on the slate," even though the Analytics Bureau's **Underplaced Talent** (873
players) and **Playing Time** (2,673 walk-ons) boards were full of cross-division talent —
including D4 schools (Elizabethtown, Puget Sound, Carroll MT, George Fox).

## Root cause — two different roster sources

The Bureau boards and the portal read the world's talent through **different doors**:

- **`scout_intel.scan`** (Underplaced / Playing-Time) iterates **every** division via
  `ncaa.build_roster`; a **dormant** division simply builds fresh on a cache miss. So the
  boards always show the whole universe.
- **`world.run_preseason_portal` / `resolve_preseason_portal`** sourced rosters from
  `developed_rosters(w)`, which is **restricted to the ACTIVE universes** (`_active_unis`).

The intended, correct setup is **all four levels active** (D1–D4). The portal should be
tied to the same all-division view the boards use so it can never silently diverge from
them — whatever the active-division set is. Keying the portal to `developed_rosters`
(active-only) made it fragile to that config in a way the boards are not; sourcing it the
same way the boards do removes the coupling entirely.

Confirmed by repro: a freshly built world produces the documented ~60 moves through the
new all-division source, riders drawn from across every level.

## Fix

New `world.scan_rosters(seed)` — the portal's roster source, built the exact way the Bureau
boards are: `prime()` then `build_roster` for **every** division×gender in `UNIVERSES`
(dormant ones build fresh). `run_preseason_portal` (seeding) and `resolve_preseason_portal`
(view/commit cascades) both now call `scan_rosters` instead of `developed_rosters`, so the
portal scans exactly the universe the Underplaced/Playing-Time boards show — never only the
active persisted subset.

Riders discovered from a dormant division move UP into the active divisions (becoming active
players); cascades still settle displaced players down as before. Walk-ons remain excluded
as risers (`discover` skips `p.walk_on`), so a D1 bench walk-on is never yanked out of the
division they earned.

## Verify
```python
import app.world as world, app.worldconfig as wc
wc.set_active(['D1','D2','D3'], ['men','women'])   # D4 dormant
world.run_preseason_portal()
res = world.resolve_preseason_portal()
# risers now include players sourced from the dormant D4 division
assert any(m['src_div']=='D4' for m in res['women'] if m['cascade_from'] is None)
```
Tests: `test_preseason_portal`, `test_fall_portal`, `test_world*` all pass.

## Not done (open design items raised alongside this)
- **First-advance as a roster-lock step** (sim nothing, just set/persist, then the portal
  moves everyone before real matches) — a season-flow change, not attempted here.
- **Protecting D1 walk-ons from the down-cascade** when a riser displaces a full roster's
  weakest — `discover` already never promotes a walk-on, but a riser landing on a full team
  can still cascade its weakest (possibly a walk-on) down. Left as-is pending a decision.
