# AAR — Lineup Architect + editor's stale 6+3 card

**Date:** 2026-08-03
**Scope:** Follow-up to `AAR-team-scanner.md`, same branch. Two items: a new
Bureau tool that assembles whole squads from buried talent, and the Editor
still rendering the old universal 6-singles/3-doubles card.

## 1. Lineup Architect (`/intel/architect`)
**Ask:** the Team Scanner surfaces buried players one at a time; the owner
(god-mode, NIL-era scouting-department fantasy) wants them assembled into whole
teams — "take players buried on rosters and build a competitive lineup for a
target level, gated by OVR and/or STR", mainly to stock lower-division teams
faster than hand-picking.

**Built:** `scout_intel.lineup_architect(gender, target_division, pool,
min_ovr, min_str, n_squads)`:
- Pool: `buried` (Underplaced-board qualifiers — same constants, not a fork),
  `below` (anyone rostered under the target division), `any`. Optional min
  current-OVR / min live-STR gates.
- Deals the pool best-first (current OVR) into up to 6 **non-overlapping** full
  singles cards (`ncaa.lineup_size(target)` — never a literal 6).
- Ranks each squad against the target division's REAL teams on the same metric
  (avg current OVR of the talent card, from the scan's `top6_cur`): "Squad 1 ·
  #4 of 214 in D2". Also reports the division's top/median card OVR.

Route validates/clamps all params; template is the terse Bureau style (no
microcopy — standing owner rule from the Team Scanner AAR). Nothing moves
players; you take a squad to the Editor to enact it.

## 2. Editor was still 6+3 (per-division dual-formats miss)
`CLAUDE.md` bans `range(6)`/`[:6]` for anything lineup-shaped; the 2027-07
dual-format change (D1 10+5, D2/D3 8+3, D4 10+3) converted `my_program` but the
**Editor** was missed in three places:
- `state.editor_roster` — `line = i if i <= 6` (LN column capped at 6),
- `editor.html` — doubles pinner hardcoded 3 pairs / 6 pids and "lines 1–6",
- `server.editor_doubles` — validated exactly the fixed `d1a…d3b` slots.

All three now key off `ncaa.lineup_size` / `ncaa.dual_format(...).n_doubles`,
mirroring `my_program_doubles`. A stale 6-pid pin on a 5-pair D1 team fails the
length check and falls back to auto (season.py already required
`>= 2*n_dbl` pids, so the sim was never wrong — only the editing surface).
Verified rendered: D1 shows D1–D5 pairs and lines 1–10; D2 keeps 3 pairs.

## Tests
`tests/test_intel_architect.py` — full non-overlapping cards dealt best-first;
pool gates (buried predicate, below-target divisions, OVR/STR floors, empty
pool); rank recomputed against the division's real cards; route renders and
survives junk params. Pre-existing failures noted in the Team Scanner AAR
(`test_web_awards`, one `test_injuries` case) fail identically on clean main.
