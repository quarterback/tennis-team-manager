# AAR — Portal Rankings (transfer-class board, On3/247 style)

> **Status:** shipped. A **Portal Rankings** board ranks every program's transfer-portal
> "class" (risers + pros IN, players OUT) per **year / gender / classification** — recruiting
> class rankings, but for the portal. Modeled on On3's Team Transfer Portal Index + 247's
> transfer team rankings.

---

## 1. The ask (owner)

"Aggregate the portal acquisitions after a window completes so I can see top classes in order —
like recruiting classes but for the portals." With reference shots of On3 / 247:

1. **Net IN/OUT**, not acquisitions-only — "how much a school improved, maintained, or lost
   talent." Count incoming risers + pros AND show who was lost.
2. **Same scoring metric** as recruiting classes (top-3).
3. **History** — go back to past years to see where talent has come and gone.
4. **Dropdowns for gender / year / classification** — see the best **D1 through D4** classes
   plus an aggregate **All**. Explicitly: *"crucial for playing lower divisions — seeing who
   got better."*

---

## 2. Why it was cheap — the data already existed

Every committed portal move already carries `src/dest school+div`, `str`, and a riser-vs-cascade
flag; pros are in `world_pro`. The board is a `GROUP BY` over that, mirroring the existing
`signing_tracker` (recruiting class rankings). No engine changes.

The one gap: the **transient** slate tables (`preseason_portal`, `fall_portal`) are **cleared at
rollover** (`_bake_fall_moves` → `ov.clear_year`). So a durable record was needed for history.

## 3. Design

### 3a. Durable archive — `world_portal_move` (written at COMMIT)
A new table records every committed move the moment it happens, so it outlives the rollover:

```
world_portal_move(world_id, year, cycle, gender, kind, pid, name, str,
                  src_school, src_div, dest_school, dest_div)
```
- **kind**: `riser` (rose UP), `cascade` (displaced DOWN to make room), `pro` (signed from the
  synthetic Pros pool — `src_school='Pros'`, so a pro is never an OUT for a real program).
- Written by `_archive_portal_moves` from `commit_preseason_portal` / `commit_fall_portal`
  (cycle `preseason`/`fall`), and pros by `_commit_pro_signings` (kind `pro`). Both capture
  **name + STR at commit**, so past-year history never depends on re-resolving old rosters.
- Idempotent per `(world, year, gender, cycle)`, scoped by kind so the transfer replace and the
  pro replace don't clobber each other. Cleared only by `reset()` (new-league). **This is the
  "snapshot" — a live archive, not a lossy rollover dump.**
- Readers: `world.portal_moves(seed, year, gender?)`, `world.portal_years(seed)`.

### 3b. Aggregation — `state.portal_class_rankings(seed, gender, division, year)`
Per program: **IN** = every move landing there (risers + pros + cascade depth); **OUT** = every
move leaving (rose away / bumped down). Then:
- **SCORE** — the incoming class, top-3 STR (`_portal_score`, same shape as recruiting's
  `_class_score` but on STR, since portal movers carry a live STR, not a recruit rank). This is
  the rank.
- **NET Δ** — SCORE(in) − SCORE(out): improved (+) / maintained / lost (−). A program can top its
  division's class board yet net small if it also lost a star (the On3 idea).
- Breakdown: # risers / # pros / # depth in; IN & OUT count + avg STR; top-5 haul.
- **Filters**: `year` (default latest), `gender` (men / women / **all** = both combined per
  school), `division` (D1–D4 or **All**). KPI cards: total moves, risers, pros, avg STR, top
  pickup.

### 3c. UI (`/portal-rankings`, `templates/portal_rankings.html`)
On3/247-style: title + KPI card row + a ranked table (Rank · Program+div · SCORE · IN n·avg ·
OUT n·avg · NET Δ · haul with a green PRO chip), driven by the three dropdowns. Nav item
**"Portal Rankings"** under Management, next to Transfer Portal. Empty-state until a window
commits.

## 4. Lower-division payoff (the owner's real goal)

Because the ladder is blended and cascades flow DOWN, a lower-division program "gets better" when
it receives bumped-down players (cascade-in) or a pro. Filtering **Classification → D2/D3/D4**
surfaces exactly those risers/pros/depth a lower program picked up vs the studs it lost up the
ladder — so a D3 coach can see who actually improved in the window. (On a fresh world with open
D1 slots there are few cascades yet; they grow as rosters fill over seasons.)

## 5. Verified

Committed a pre-season window (200 risers + 2 pros): 202 moves archived; board renders 200 with
KPIs + all three dropdowns; Texas #1 (2 pros, net +12.1); **D2 programs surface as class leaders**
(cross-division works); year filter resolves a past-year view; 18 pros/portal tests still pass.

## 6. Files touched

- `app/world.py` — `world_portal_move` table + reset; `_archive_portal_moves` + hooks in both
  commits; pro archiving in `_commit_pro_signings`; `portal_moves` / `portal_years` readers.
- `app/web/state.py` — `portal_class_rankings` + `_portal_score`.
- `app/web/server.py` — `/portal-rankings` route + nav item + active-id mapping.
- `app/web/templates/portal_rankings.html` — **new** (KPI cards + ranked table + dropdowns).
