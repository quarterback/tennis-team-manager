# AAR — the JV Team State Tournament at 36: at-larges through a Parastate (owner rule 2026-09)

The owner expanded the JV Team State Tournament from the twenty regional champions
(`docs/AAR-jhsaa-jv-team-state-tournament.md`) to a **36-team selected field**: the
twenty champions plus **sixteen at-large selections**, picked on an index of **30% JV
record + 70% varsity record**. The at-larges play a **Parastate** round; its eight
winners join the champions in a **28-team main draw** — seeds 1-4 bye, twelve
preliminary duals, then 16 → QF → SF → Final. The owner's one instruction on method
was "using the state machinery", and that phrase decided nearly everything below.

Shape, exactly as specified and as pinned by
`tests/test_jhsaa_jv_state.py::test_the_36_is_champions_plus_sixteen_at_large_through_a_parastate`:

```
36 selected -> 16 at-large play the Parastate (21v36 ... 28v29) -> 8 advance
-> 28 main draw = 20 champions (seeds 1-20) + 8 winners (21-28)
-> 4 byes (seeds 1-4) + 12 preliminary duals -> 16 -> QF -> SF -> Final
```

Decisions the owner settled before a line was written (asked, not assumed):

| Question | Decision |
|---|---|
| Which varsity record feeds the index | **Regular season only** — `jhsaa._reg_season_record`, the State Specials' rule. The varsity road has been played by the time the JV postseason runs, and a deep bracket run is how far the draw carried a program, not what it did across the season. |
| At-large pool and main-draw seeding | **Any JV entrant** that is not a regional champion, whether or not it reached its regional. Champions stay seeded **1-20 on the JV record**; Parastate winners are seeded **21-28 structurally**, ordered by the index. Byes go to the best four champions. |
| Parastate pairing | **High-low, 1v16 … 8v9**, higher seed on the home side; winners keep their seed. |
| From when | **The next unplayed season on the save** — an era gate, never a flag. |

---

## What was REUSED, and why it cost almost nothing

### 1. The archive is ONE `state` dict whose first round is NAMED

`jhsaa.run_state_parastate` already carries the varsity committee classes'
Parastate as the bracket's first round, with `round_names = ["Parastate"]` and the
main draw's rounds after it. The JV event now archives the identical shape:
`state["rounds"] = [parastate_games] + main_rounds`,
`state["round_names"] = [jhsaa.PARASTATE_NAME]`, `state["field"]` = the 36 in seed
order. Nothing else needed inventing, because every varsity reader keys on that
name and nothing else:

- `state._jh_split_state` splits at `len(round_names)` and hands the page **two
  trees** — the Parastate as its own canvas, the main draw as another — because a
  fresh draw sits between them and one positional tree would invent links.
- `world.jhsaa_state_result` files an at-large's exit as **"Parastate"** when its
  last round carries that name, so the region table, the selection table and the
  program page all say the same thing without a JV-specific branch.
- `world.jhsaa_state_rounds` names the round after it off the alive count — "Round
  of 28" at full size — and the school-page chip (`jv_round`) reads "Parastate" for
  the opening round exactly as a varsity 9A program's does.
- `jhsaa_bracket.html`'s `qual` toolbar tab and second `brk-region` section were
  copied into `jhsaa_jv_state.html` as-is, labelled Parastate.

**A phase is the archive's identity for an EVENT; a round name is the identity for
a ROUND.** The Parastate duals stay at `phase="jv_state"` — they are State duals,
the same as the varsity Parastate stays `phase="state"` — and `level='jv'` keeps
every one of them out of a varsity record as before.

### 2. The draw is `_run_bracket`, untouched

Twenty-eight into 32 slots on the TOC's strict seed lines gives seeds 1-4 the byes
and pairs 5v28 … 16v17 by construction — the spec's "top 4 seeds receive byes, the
other 24 play 12 preliminary State matches" is what the existing order fold does
when handed 28 names. No bye logic was written.

### 3. The Parastate is `run_state_parastate`'s loop, at JV types

`jvs.run_parastate` is the same eight lines: pair `bids[i]` with `bids[-1-i]`,
winners returned **in seed order** (they retain their seed), an odd field advances
its middle seed unplayed. The varsity function could not be called directly
because it plays `TeamSeason`s through the varsity `play_dual`; the JV event has its
own `play_dual` (five courts, no record mutation, JV-level rows). Copying the loop
was cheaper and safer than parameterising the varsity one.

### 4. The selection is archived the committee's way

`jhsaa_committee.select` archives what it read. `jvs.selection_rows` does the same:
one row per team in the field with `entry`, `region`, the JV and varsity
regular-season records, both percentages and the index — so the page can show the
audit and the export can flatten it without recomputing anything from a rebuilt
roster.

---

## What was deliberately OMITTED

- **No home-court lift on the Parastate**, though the owner picked "higher seed
  hosts". Every JV State dual is neutral-site, and so — it turns out — is the
  varsity Parastate: `phase="state"` is in `NEUTRAL_PHASES`, so "hosts" there has
  always been orientation only. Matching that was the honest reading of "use the
  state machinery"; the higher seed sits on the home side of the row and nothing
  else. Said plainly to the owner at delivery rather than buried here.
- **No `_recovery`-style ladder, no committee ballots, no Borda.** The index is two
  percentages and two weights; sixteen names fall out of a sort. A five-member
  committee for a JV event would be machinery the decision does not need.
- **No re-seeding of the 28 on the index.** The owner chose the structural floor
  (champions 1-20, at-larges after). An at-large can never take a bye.
- **No change to `REGIONS`, district berths, eligibility, the freeze, the roster cap
  or the 3S/2D format.** The at-larges dress from the same frozen championship
  roster as everyone else.
- **No migration.** Seasons archived at twenty are read through the same code:
  `_jh_split_state` returns `(br, None)` for a bracket with no `round_names`, the
  view's `qual_canvas` is None and the page renders the one tree it always did. The
  legacy play-in archives (the 2026-09 build) keep their existing on-read rejoin.

---

## The traps this expansion introduced

### 1. `ranked` changed meaning — it is now the FULL seed order

Before: `ev["ranked"]` was the twenty champions. Now it is `state["field"]`: the
champions, then the at-larges. Every consumer that built a seed map off `ranked`
(the view's `seeds`, the legacy `Round of {len(ranked)}` relabel) keeps working
because a seed map WANTS the full order — but anything that read `ranked` to mean
"the champions" would silently count 36. The champions are `region_champions`;
read that. `at_large` is the sixteen in seed order.

### 2. The at-large selection is a fold over a LIVE `TeamSeason`

`selection_index` reads `e.jv.team.schedule` for the varsity term. In `run_season`
the varsity postseason has been played by then and `_reg_season_record` filters it
out, so the term is right. **In a fixture that plays only `play_jv_season`, the
varsity schedule is empty and every varsity term is 0.0** — the index collapses to
30% of the JV record and the ranking still looks perfectly sensible. The smoke run
did exactly this and read as fine. `test_the_index_is_30_jv_70_varsity_regular_
season_only` pins the arithmetic on a constructed schedule instead, with postseason
rows present, because no cheap fixture contains the case.

### 3. The year gate resolves to a SEASON and must not be a literal

`jhsaa.jv_parastate_era()` is `_resolve_era("jhsaa_jv_parastate_era", …)` — the
`exchange_era` idiom: the first season the save has not archived, 0 on a fresh
save, pinnable in `worldconfig`. It is in `ERA_SETTINGS` (so `world.reset()` clears
it) and its memo is cleared by `reset_schools()`. A typed constant like
`JV_STATE_FROM = 2068` would have been wrong here: the owner's save is decades past
2068 and any fixed year either back-applies the shape to archived seasons or
holds it off the next one. `run_jv_state(expanded=)` exists so a test can pin either
shape without touching the setting; production passes nothing.

### 4. The Parastate is only NAMED when it was PLAYED

`state["round_names"]` is set only if `para` is non-empty. A world so small that the
at-large pool is empty archives a plain bracket with no `round_names` — correctly,
because there was no Parastate. A reader that assumes "expanded season ⇒ Parastate
round" will be wrong on tiny worlds; read `round_names`, never the era.

### 5. Bye count is a property of the FIELD, not the rule

Twenty champions + 8 = 28 in 32 slots = 4 byes. The test fixture crowns 18 regions,
so its main draw is 26 and byes 6 — the first draft of the test asserted 4 and
failed. `MAIN_BYES` (4) documents the full-size shape; the test derives byes from
`32 − alive` and asserts the constant only as `32 − (REGIONS + 8)`. Same lesson as
the varsity `sponsor_floor`: **a full-size run must land on the constant; a short
fixture must not be forced to.**

### 6. A truncated test file passed

While appending tests, a `s = s[:i] + new` slice cut every ORIGINAL test out of
`tests/test_jhsaa_jv_state.py`, and the file ran **4 passed** — green. Caught only
because 4 was an implausible count for a 24-test file. `grep -c "^def test"` before
and after any scripted edit of a test file; a green run says nothing about tests
that are no longer there.

### 7. The export flattens the ARCHIVED selection, never a recomputation

`jhsaa_jv_state.csv` (owner ask: "make sure the data gets exported … as well as
analytic for future analysis") is one row per team in the field — `entry`,
`region`, `jv_*`, `varsity_reg_*`, `selection_index`, `made_main_draw`,
`state_place`, `state_finish` — read off `selection` plus `jhsaa_state_result` on
the same archived bracket the JSON carries, so the two files cannot disagree.
Seasons archived at twenty have no `selection`; the file still lists their
champions (off `ranked`) with the index columns empty, so an analysis across the
expansion joins on one shape. It is a **flat table beside the JSON, not instead
of it**: the JSON keeps the regions, brackets and rounds. `jhsaa_standings.csv`
and every rating stay varsity-only; JV never enters TOSS, ATR, awards or a
varsity record, and this table gives it no new door.

---

## Files

- `app/jhsaa.py` — `jv_parastate_era()`, `ERA_SETTINGS`, `reset_schools()` memo.
- `app/jhsaa_jv_state.py` — `AT_LARGE`, `MAIN_BYES`, `INDEX_*`, `varsity_record`,
  `selection_index`, `select_at_large`, `selection_rows`, `run_parastate`,
  `run_jv_state(expanded=)`.
- `app/web/state.py` — `jhsaa_jv_state_view`: `_jh_split_state`, `qual_canvas`,
  `prelim_n`, the at-large `selection` table.
- `app/web/templates/jhsaa_jv_state.html` — Parastate tab and section, selection
  panel.
- `app/research_export.py` — `jhsaa_jv_state.csv` + manifest sentence;
  `analytics/README.md`.
- `tests/test_jhsaa_jv_state.py` (`big36`, five new tests),
  `tests/test_jhsaa_toc.py::test_the_research_export_carries_the_jv_events`.
