# AAR — Postseason lineups: strict best six (no resting in elimination play)

**Date:** 2027-07-17
**Scope:** `season.coach_lineup` (+ new `best_six` flag), `season.dual_between`,
`seasonmode._play_and_store`, `seasonmode._sim_round`.

## The bug this fixes

AI programs were benching their best players **in the NCAA tournament**. The
regular-season bench-rotation device in `coach_lineup` ran in *every* dual:

```python
gap = prog.prestige - opp_prestige
rotate = 2 if gap > 0.18 else 1 if gap > 0.05 else 0   # rest starters vs weaker teams
if rotate == 0 and rng.random() < BASELINE_REP_CHANCE: rotate = 1
```

A top seed drawing a low-prestige autobid in the Round of 64 — the most common
NCAA pairing — rested one or two starters for random bench players in a match
where losing ends the season. Uninjured stars sat; seeds lost duals they should
not have.

## Owner's rules (locked)

- **NCAA team tournament + conference tournaments:** the lineup is STRICTLY
  form / record / level — the healthy top six by results-based STR (ability as
  the fallback before results exist), in that order. **No starter-resting, no
  baseline bench reps, and no coach-discretion noise.**
- **ITA events (Kickoff + Indoor) keep the normal rotation on purpose** — they
  are early-season tournaments whose point is that different people play.
- **Injuries still apply everywhere** (`unavailable` filtering is untouched):
  an injured starter pulls up the next healthy body; the short-handed safety
  (playing hurt rather than forfeiting) is unchanged.

## How it works

`coach_lineup(..., best_six=False)` gains one flag:

- `best_six=True` → `rotate = 0` (no resting / no baseline rep) and the ladder
  score is the raw form STR (no `LINEUP_NOISE` gauss), so the six seats are the
  top six by form in form order.
- Default `False` → the regular-season behavior is bit-identical in intent:
  rotation vs weaker opponents, baseline reps, coach noise, playing-time
  guarantees (`forced_appearances`, non-conference only).

`_sim_round` — the single driver for ALL bracket rounds (ITAK, ITAI, CT, NCAA)
— sets `best_six = rnd_tag in ("CT", "NCAA")` and threads it through
`_play_and_store` → `dual_between` → `coach_lineup`. Regular-season weeks call
`_play_and_store` without the flag.

## Verification

- With an explicit form ladder on a high-prestige D3 program vs a weak opponent
  (`opp_prestige 0.05`): `best_six=True` fields exactly the top six by form, in
  form order, across 30 dual seeds; `best_six=False` rotated the lineup in
  29/30 duals (the by-design regular-season behavior).
- ITA rounds tag as `ITAK`/`ITAI` → not gated → rotation preserved.

## Watch-outs

- The human coach's pinned lineup (career mode) still wins in every round —
  `pinned` takes the branch before rotation, so a hand-set NCAA lineup is
  honored as-is. `best_six` only disciplines the AI ladder.
- Don't extend `best_six` to the ITA events without an owner decision — their
  rotation is a feature, not the same bug.
- Skipping the noise draws in `best_six` shifts the `srng` stream (doubles-perm
  choice), so postseason doubles pairings differ from pre-fix saves at the same
  seed. Deterministic per seed either way.
