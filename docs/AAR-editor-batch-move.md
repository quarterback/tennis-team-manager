# AAR — Editor batch player moves (kill the one-by-one friction)

## The problem
Moving players between programs in the Editor was tedious and slow, so the owner
moved fewer players than they wanted:
1. **One by one:** each roster row was its own `<form>` POSTing a single
   `pid + dest` to `/editor/move` — moving N players took N page-reloading submits.
2. **Slow to "commit":** every single move ended in `reset_all()` — a world-wide
   cache flush — AND bumped `ov.move_version()`, which is the stamp
   `world.prime()`/`is_primed()` key on. So after EVERY move the next page had to
   re-prime the whole world's rosters and re-derive the season/ranking caches.
   Ten moves paid that rebuild ten times.

The invalidation itself is CORRECT — a move genuinely changes the developed roster
set, which is exactly what the move-version stamp exists for (see
`docs/AAR-cache-invalidation-scope-lineup-stall.md` §4: pins are display-only and
don't bump it; moves must). The fix is not to narrow it further, it's to **pay it
once per batch instead of once per player**.

## What changed
- **`/editor/move_batch`** (`app/web/server.py`): one POST for the whole roster.
  Every `dest_<pid>` field whose value differs from the current school becomes a
  move; unchanged rows are no-ops. All moves are written, then **one**
  `reset_all()` — shared helper `_apply_editor_moves` (also used by the legacy
  single-move route, kept for compatibility).
- **Editor UI** (`editor.html`): the per-row "Move" forms are gone. Each row's
  destination `<select>` binds to a single external form via the HTML `form`
  attribute (so it coexists with the per-row lineup ▲▼ forms — forms can't nest).
  Changed rows get a highlight outline, and a sticky **"Apply N moves"** button
  live-counts staged moves (tiny inline script, no dependencies). Single move =
  set one dropdown + Apply, same clicks as before; ten moves = ten dropdowns +
  ONE Apply and one rebuild.
- **Fall-portal window preserved:** during the `fall_portal` hold the batch is
  routed through the portal exactly like single moves were — each staged move
  becomes a portal ADD (`wd.add_fall_portal_mover`, two-stint history + balancing
  cascade) and the whole slate lands at portal commit, which was ALREADY batched
  (`world.commit_fall_portal` applies every rider + cascade under one
  invalidation).

## Why this shape
- The portals already proved the pattern: `commit_fall_portal` relocates dozens of
  players under a single `reset_caches()`; the editor was the only mover path
  paying per-player invalidation.
- Batch-per-viewed-school matches the navigation: you're looking at one roster at
  a time; stage every outgoing move on that page, apply, move on.
- Kept `/editor/move` (single) so nothing external breaks; it now shares
  `_apply_editor_moves`.

## Tests
`tests/test_web_editor.py` — batch applies all changed rows and skips unchanged
ones (movers arrive at the destination roster and leave the source), an empty
batch is a no-op, and the legacy single-move route still works.
