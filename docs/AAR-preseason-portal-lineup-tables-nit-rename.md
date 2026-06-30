# AAR — Pre-season portal, Lineup Lab table rebuild, ITA → Preseason NIT rename

Three changes shipped together. The pre-season portal is the substantive one; the
other two are a UI fix and a display rename.

---

## 1. Pre-season portal (week-0 misallocation reshuffle)

### Why

A freshly generated world scatters some D1/D2-caliber players into D3/D4 — the
talent model's spread is wide on purpose (`ncaa._TALENT`), so a weak program can
draw a stud by chance. The owner did **not** want to constrain the generator (who
can be at what level), because that over-allocation is partly *intended*: those
top players naturally leave the lower divisions through the **fall portal** after
the NIT window. What was missing was a way to fix the worst cases **before the
season even starts**, so the owner asked for "a third portal for the pre-season."

### What it does

At week 0 (before any matches), the sim proposes a cross-division reshuffle of the
most mis-allocated players; the owner reviews/edits on `/preseason-portal` and
commits. Committed movers simply **start the season at their new school** — so the
Preseason NIT and everything after see the corrected rosters.

It is deliberately **the same engine as the fall portal** (owner choice: "match
fall portal"): `world._FPPlanner.discover` finds top-2 lower-division players who
clear a higher division's median expected level (`div_level`), rises them up, and
cascades each overfilled roster's weakest player down so no program loses a spot.
Same keep / drop / redirect / add / commit UX.

### Why it's simpler than the fall portal

The fall portal runs *after* the NIT, mid-season, so it carries a lot of
bookkeeping the pre-season portal does **not** need:

- **No NIT stint, no two-stint history.** A pre-season move happens before any dual
  is played, so the player has exactly one stint — the whole season at the new
  school. That is precisely what the editor's plain `kind='move'` override already
  does, so **commit is just `overrides.set_move(pid, dest)` per mover.** No
  `_stamp_ita_stint`, no `(year, stint)` history surgery, no `_bake_fall_moves`.
- **No phase hold.** The fall portal holds the world driver at a `fall_portal`
  phase and releases on commit. The pre-season portal is an optional tool available
  whenever `week == 0`; it never touches the world driver or phase machine. Lower
  risk, and it can't deadlock a single-season fixture.

### How it's wired

- **Engine** (`world.py`): `preseason_portal_proposals(rosters, gender)` is a thin
  wrapper over `_FPPlanner(...).discover(FALL_PORTAL_MAX_RISERS)` — byte-identical
  riders to the fall portal's. `run/resolve/commit/add/redirect_preseason_portal_*`
  mirror their fall counterparts (intents → resolve → commit), minus the
  ITA-lookup / stint / release steps. `commit_preseason_portal` `set_move`s every
  move (riders **and** cascades) and keeps the committed slate in the table so a
  re-open shows what happened instead of re-proposing it.
- **At week 0 the planner reads intrinsic ability.** `_str_of(player_str, p)` falls
  back to `p.str_value()` when there are no results yet — exactly the talent signal
  we want for fixing generation, so `player_str` is passed empty (`{}`).
- **Commit propagates correctly because of the two roster paths.**
  `developed_rosters` (what `_FPPlanner` snapshots) reads the *base* rosters and
  ignores `move` overrides; `ncaa.build_roster` applies `get_moves()` on top of the
  primed base. So a committed `set_move` flows to the NIT, season sims, team pages
  and the bureau via `build_roster`, while the planner always proposes from a clean
  base.
- **Persistence** (`overrides.py`): its own `preseason_portal` table (same shape as
  `fall_portal` minus the ITA columns, plus a stored `name`), with `ps_*` helpers
  (`ps_set_proposals`, `ps_get_proposals`, `ps_set_status`, `ps_set_dest`,
  `ps_clear_year`). A **separate** table is required — the pre-season and fall
  portals run in the **same world year**, so sharing `fall_portal` would have them
  clobber each other.
- **UI**: `/preseason-portal` + `preseason_portal.html` (modeled on
  `fall_portal.html`), reachable from a new **Preseason setup** step
  (`state.preseason_view`). On first visit at week 0 the route seeds the slate
  (`run_preseason_portal`) only if none exists yet — idempotent, so it never
  clobbers edits or a committed run. After commit the view renders the committed
  slate read-only (`done=True`).

### Gotchas / invariants

- **Same shallow-copy rule as the fall portal.** `_FPPlanner` mutates roster lists
  to relocate players, and `developed_rosters` is the shared `_dev_cache`; the
  planner already shallow-copies each list, so reuse is safe — do not "optimize"
  that copy away.
- **Idempotent seeding.** `run_preseason_portal` no-ops if any rows exist for the
  year, so navigating back to the page after editing/committing won't regenerate.
- **Default slate is large on a fresh world** (riders + cascades across every active
  universe) — same scale as the fall portal, by design. The owner curates down. If
  a tighter default is ever wanted, filter `discover` candidates to `div in
  ("D3","D4")`.

### Tuning knobs

Shares the fall portal's: `world.FALL_PORTAL_MAX_RISERS` (per-gender cap),
`UP_THRESHOLD`, the `div_level` median bar.

---

## 2. Lineup Lab tables rebuilt (Analytics Bureau › Lineup Lab)

### Why

The team-depth and league-strength tables were unreadable — nothing lined up, rows
wrapped to a second line. **Root cause:** they reused the bracket classes
(`.bl-brk-match` / `.bl-stand-hdr`) with an inline `grid-template-columns`, but
`bracket.css` loads *after* `app.css` and redefines `.bl-brk-match` as
`display:block`. The inline style only set the columns, never `display:grid`, so
the rule never took effect — every "row" was a block and its cells flowed and
wrapped.

### What changed

Both tables now use dedicated, self-contained grid markup
(`.ll-tbl` / `.ll-thead` / `.ll-tr`, scoped in `intel_lineups.html`) where the
header and every row share one `--ll-cols` track, so columns line up exactly.
Stats are right-aligned tabular; the **1→6 ladder is a fixed 6-column micro-grid**
(`.ll-lad6`) so positions stack vertically down the table instead of running
together behind `·` separators. The STR/UTR/OVR lens toggle is preserved — the JS
still rewrites `.ll-num[data-str|data-ovr]` cells. (Note: the league-strength
"Tms" count is intentionally **not** a `.ll-num`; it has no `data-str`, so tagging
it would render `NaN` on lens toggle.)

The bracket-class collision is not fixed globally (other pages rely on it); the
Lineup Lab simply stops borrowing those classes.

---

## 3. ITA opener renamed to "Preseason NIT" (National Indoor Tournament)

**Display-only** rename, owner request. Nav label, phase labels, badges
(`ITA`→`NIT`, `ITA KO`→`NIT KO`, `ITA Indoor`→`NIT`), champion / honor labels, and
opener copy across `ita.html`, `season.html`, `season_dual.html`, `teams.html`,
`fall_portal.html`, `data_portal.html`, `server.py` (`_LBL`, nav), `state.py`
(`_LABELS`, world-hub action) and the `seasonmode` honor label
(`"Preseason NIT Champion"` / `"…Runner-Up"`).

**Left unchanged on purpose:** internal phase strings (`ita_kickoff`,
`ita_indoor`), round codes (`ITAK` / `ITAI`), the `season_ita` route, the `ita.py`
module, and the per-save honor records already stamped before the rename. Also left
as-is: "**ITA-style ranking points**" tooltips in `rankings.html` /
`methodology.html` — those describe the real-world ITA *ranking algorithm*, not the
event, so "NIT-style" would be wrong.

---

## Tests

- `tests/test_preseason_portal.py`: the engine wrapper matches the fall portal's
  riders, the cascade keeps every roster within cap, the `preseason_portal` table
  round-trips (proposals / status / redirect), and it stays independent of the
  `fall_portal` table for the same year.
- Verified end-to-end with a web smoke (fresh world, primed): the Lineup Lab renders
  the new `.ll-tbl` markup with real data, the nav shows "Preseason NIT", and
  `/preseason-portal` renders a proposal slate.
- Note: `test_intel_bureau_live.py::test_bureau_player_links_resolve_after_rollover`
  errors with `no such table: seasons` **only when run alongside other web test
  files** (a pre-existing test-isolation artifact in `_release_fall_portal`,
  untouched here); it passes when run alone.
