# AAR — 6A format continuity (3S/4D through State) and Record Over Expected (2026-09)

Two decisions off the 2079 analyst reports (`docs/reports/REPORT-jhsaa-6a-state-format-
study-2079.md`, `docs/reports/REPORT-jhsaa-2079-format-selection-companion.md`).

## 1. 6A plays its league 3S/4D through the postseason

- **The change is membership.** `LEAGUE_SHAPE_GROUPS = ("6A",)`; `dual_format` returns
  `FORMATS["regular"]` for a 6A road/State dual and a 6A-hosted showcase; the TOC is
  excluded by the same `road` test every other pilot uses. `lineup_need`,
  `jv_postseason_cut`, `_postseason_nine` and `_slot_players` all derive from the format.
- **The postseason arrangement is `_arrange_wide`, not the league allocation.** The
  league's 3S/4D rule seats #10-#11 at S2/S3 (doubles-forward, fixed). Carried into the
  postseason that would (a) contradict the Order of Ability, and (b) hit an awards trap:
  `FLIGHT_S2S3_REGULAR` deflates S2/S3 only when `phase == "regular"`, so a #10 at a
  State S2 would be scored as a genuine No. 2 with postseason weight on top. The wide
  arranger pools the top five for three singles seats plus D1, which is what the format
  study measured.
- **What was measured and accepted.** 3S/4D at State is a seven-court shape: 60-63%
  one-point in even duals against 1S/4D's 68-70%, margins wider, favourite win rate
  unchanged. The owner chose continuity over closeness for 6A; the companion report's
  pre-registered measurements (flight participation, role persistence, competitive shape,
  roster construction, the 5A/7A continuity controls) are the yardstick.
- **Not touched:** the early window (5S/2D), the league season, FLIGHT_WEIGHTS (S1-S3
  and D1-D4 already priced), TOSS (postseason excluded anyway).

## 2. Record Over Expected on the committee page

- `jhsaa_committee.flight_record` counts flights won/lost, duals won/lost and one-flight
  duals from `TeamSeason.schedule`, skipping JV rows and the State phases; a tie counts
  its flights and no dual. `expected_win_pct` is the Pythagorean expectation at
  `XW_EXPONENT` 1.83; `record_context` builds the per-team panel with a descriptive
  flag at `ROE_FLAG` 0.10.
- **Archived, never recomputed.** `run_jhsaa` writes `sel["context"]` beside the
  selection; the view reads it and a pre-context season shows no columns
  (`has_context`). `select()` never sees it — the only path by which the panel could
  pick a team is a human reading it.
- **Calibration is a tool, not a season step.** `fit_xw_exponent` (golden-section least
  squares on W%) exists for the scripts; the 2079 fit was boys 1.815 / girls 1.850.
- **Vocabulary:** flights, never courts.
