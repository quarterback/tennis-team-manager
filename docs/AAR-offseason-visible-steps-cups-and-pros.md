# AAR — the cups and the pro league ran invisibly inside the rollover

**Date:** 2026-07-29
**Status:** FIXED.
**Scope:** `world.run_world_cups` / `cups_done` / `cup_rosters` / `run_pro_offseason`
/ `pros_rolled` (new), `world.advance_week` (offseason ladder), `world._finalize_year`
(cups + GTT tail removed), `world._store_world_cups` (no silent swallow),
`state.get_world_cup` (archive-only), `state.world_hub` + `server._game_context`
(stages), `tests/test_offseason_steps.py`.

## Symptom

Owner: *"does the BJK/Davis Cup sim automatically every year? it's not clear right
now"*, and then the real one: *"right now i'm afraid to run [the pro leagues]
because if i run them i can't be sure if it's connected to messing up my college
leagues."*

Both events DID run every year. Neither was visible. Clicking **Finalize season**
ran, in one indivisible step: the individual championships, career history, the fall
portal bake, graduation, the Davis/BJK cups, honors, the year-end portal, the
recruiting intake, the year increment, and — as a `try/except`-wrapped tail — the
pro league's entire off-season. Nine things behind one button, so the only way to
find out what a click did was to go looking afterwards.

## Root causes

1. **No step of their own.** `_store_world_cups` and `_gtt.on_world_rollover` were
   interior lines of `_finalize_year`. Nothing in the UI marked either as having
   happened, and there was no way to run one without running all nine.
2. **Cup failures were silent.** `_store_world_cups` wrapped the per-gender body in
   `except Exception: pass`. A cup that threw left the year with no cup row and no
   honors, and said nothing — the exact "graceful fallback hides wrong data" trap
   CLAUDE.md warns about.
3. **Two roster sources that could disagree.** The live preview
   (`state.get_world_cup`, shown once the seasons completed) built its pool from
   `world.scan_rosters()` — every division×gender, with dormant ones **re-derived
   from the generator**. The archive built its pool from `developed_rosters(w)` —
   **active universes only**. So the cup you watched before finalizing was drawn from
   a different player set than the cup that went on the record and stamped honors.
   (Measured on a live D1-only save: 28,720 players scanned vs 9,096 developed. The
   pid sets happened to agree with `world_roster`, so no players were literally
   fabricated, but the two cups were computed from different pools.)

## The fix — the offseason is a ladder, one step per click

```
season complete → Run awards → Run Davis / BJK Cup → Begin <next> season → Run pro league offseason → preseason
```

* **Cups first, before the rollover.** `advance_week` runs `run_world_cups` while the
  season is still complete-but-unrolled, so the seniors graduation is about to remove
  play their last cup — the property the old inline call got by sitting above
  `_save_graduates`, now held by ordering the steps instead.
* **`world_cups` rows ARE the done-marker** — no parallel flag to drift out of sync.
* **Pro offseason is its own step** at week 0 of the new year, gated by a
  `pros_rolled_year` setting. It only ever READS college state (the `world_graduates`
  table the rollover just wrote); nothing in it writes a college roster, season or
  dual, so running it cannot disturb the college world. That was always true — it was
  just impossible to see.
* **One roster source, real players only.** `world.cup_rosters(w)` = the ACTIVE
  universes developed to now, plus the DORMANT universes' rows as persisted in
  `world_roster`. Never `scan_rosters`, which regenerates dormant divisions instead of
  reading the save. `get_world_cup` is now archive-only — it never computes a second,
  differently-sourced edition on a request thread.
* **Cup failures raise.**

## Verification (live world, D1 men + women)

```
seasons complete at week 21   stage: awards        | Run awards →
awards: 1872 stamped          stage: world_cups    | Run Davis / BJK Cup →
advance → {'event': 'world_cups', 'champions': {'men': 'Serbia', 'women': 'United States'}}
                              stage: offseason     | Begin 2027 season →
advance → rollover (2266 graduated), year 1 week 0
                              stage: pro_offseason | Run pro league offseason →
advance → {'event': 'pro_offseason', 'leagues_rolled': 0}
advance → week 1 of the new season
```

Both cups archived (32-nation fields), and the prior year's edition survives the
rollover. Champions match what the old preview path produced from the same pool.

## Rule

An event that changes the world gets its **own advance step**. If it can only be
observed by inspecting the database afterwards, it will be distrusted — and a step
nobody trusts is a step nobody runs. Do not fold a new world-changing event into
`_finalize_year`; add a rung to the offseason ladder in `advance_week`, marked by
state that already exists (the rows it writes) rather than a new flag.
