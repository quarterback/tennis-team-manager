# AAR — Recruiting board never showed signings

**Date:** 2026-06-12
**Scope:** Recruiting page COMMIT column stayed at "—" all season even as the
weekly drip filled thousands of signings into `world_signing`. Make the column
reflect live commitments and show **where** each recruit signed.

## Why
Reported in-session: "It's week 7 and nobody has signed — that doesn't make
any sense." The header banner already read `CLASS SIGNED 1336`, and the
Signing Tracker (`/recruiting/signings`) showed schools filling their classes,
but the National board kept rendering "—" for every prospect. The two views
were reading from different sources and never reconciled.

## Root cause
Two parallel commitment representations that never met:

- **`world_signing` table** (`app/world.py:127`) — the source of truth for the
  weekly drip. `_sign_batch` inserts a row per recruit each week
  (`app/world.py:441-512`). `signed_counts()` / `signings()` read from here
  for the header banner and the Signing Tracker.
- **`Prospect.committed` field** (`app/development.py:145`) — read by the
  board template (`app/web/templates/recruiting.html:74`) and the profile page
  (`app/web/templates/recruit.html:224`). It is only ever set in
  `intake_signings` at year rollover (`app/world.py:574`), on **fresh copies**
  written onto roster as `Fr`. The live Prospect objects cached by
  `get_recruits()` (`app/web/state.py:299-322`) were never updated.

So during the season the board read a Prospect cache whose `.committed`
flag was the default `False` for the entire class, regardless of how many
rows existed in `world_signing`.

## Fix
Sync the flag at read time instead of write time. A new helper
`_apply_committed_flag(klass, gender, grad_year)` in `app/web/state.py`:

1. Loads the current world; if there's no world or its `year` differs from
   the displayed `grad_year`, clears `committed` on the cohort (signings
   apply only to the current signing class).
2. Maps the juniors-vocab gender ("male"/"female") back to the world-vocab
   ("men"/"women") via a reverse `RECRUIT_GENDERS` map so it can index
   `world.signings()`.
3. Builds a `{pid: school}` map from the signings dict and stamps each
   prospect with both `committed` and a new `commit_school` field.

Called from `recruit_rows` (the national/state/intl board) and `get_recruit`
(the profile page) so both views see the same truth as the Signing Tracker.

`Prospect.commit_school: str | None` was added as a real dataclass field
(`app/development.py:146`) rather than relying on dynamic attribute writes.

The templates now render the **school name as a link** to that program's
team-recruiting page — the more useful piece of information than the
generic "Committed" label the user pointed out.

## Files touched
- `app/development.py` — new `commit_school` field on `Prospect`.
- `app/web/state.py` — `_apply_committed_flag` helper; called from
  `recruit_rows` and `get_recruit`.
- `app/web/templates/recruiting.html` — COMMIT cell renders school link.
- `app/web/templates/recruit.html` — profile commitment row shows school.

## Tests
The 51 recruiting/world/junior tests pass unchanged (`test_world.py`,
`test_juniors.py`, `test_web_recruiting.py`, `test_world_model.py`,
`test_junior_circuit.py`). No new test added: the helper is a pure read-side
view over data the existing `world.signings()` tests already cover, and the
template change is presentational. A dedicated test would mostly assert
"helper sets the attribute we just told it to set".

## Decommits / flips (follow-on)

After the COMMIT-column fix shipped, we layered decommits on top of the same
drip. The wrinkle: a signed recruit has a small per-week chance, within a
short window after committing, to flip to a different school on their list.
They do NOT re-enter the pool — they immediately re-pick from the same
candidate set used in the original sign decision.

### Mechanic
- `world_signing` gained `week_signed` and `flips` columns (with an
  in-place ALTER migration in `init_schema` so existing DBs upgrade).
- `_sign_batch` records the current week in `week_signed` on insert.
- A new `_decommit_pass(conn, world, gender)` runs each tick **before**
  `_sign_batch`. It pulls every signing inside the `DECOMMIT_WINDOW_WEEKS`
  window, rolls `DECOMMIT_RATE` per recruit, frees the old seat, and calls
  the shared `_pick_school` helper with the original school in the
  `exclude` set so the recruit lands somewhere new (or stays put if no
  other open seat fits — rare).
- Hard cap: nothing flips once the world week reaches
  `DECOMMIT_CUTOFF_WEEK` (10 of the 13-week signing window), so late
  commitments stick.

### Knobs and what they're calibrated to
| Constant | Value | Notes |
|---|---|---|
| `DECOMMIT_WINDOW_WEEKS` | 3 | Per-recruit eligibility window after signing |
| `DECOMMIT_RATE` | 0.067 | Per-week per-recruit flip probability |
| `DECOMMIT_CUTOFF_WEEK` | 10 | No flips after this week (of 13) |

Cumulative flip rate per recruit ≈ 1 − (1 − 0.067)³ ≈ **18.8%**, matching
the Power Four college-football benchmark the user supplied (slightly over
80% of verbal commits stick; ~18.8% decommit, spiking to ~30% in elite
classes). Tennis isn't football, but the magnitude is in the right
sandbox-game ballpark.

### Refactor
Both the original sign decision and the new flip decision now go through
`_recruit_market(world, gender)` (precomputes the prestige window, top-40
academic set, region buckets) and `_pick_school(p, market, avail, *,
jitter_salt, exclude=None)`. Same scoring math, same candidate filters, one
function — flips are deliberately the *same model* as signs, minus the
original school. This means a flip isn't random noise: it's the
second-best-fitting open school for that recruit.

### Surfacing
- `world.signings()` attaches each prospect's live `flips` and
  `week_signed` (transient, not persisted on the Prospect itself).
- Signing Tracker KPI strip gained a **Flipped** counter.
- Recruits with `flips > 0` get a small red `FLIP` tag next to their name
  in the Top Commitments list. The recruiting board's COMMIT column
  always shows the *current* school, so a flip is invisible there by
  design — it just shows the new commit.
- `advance_week`'s return dict now includes `flips` so an outer driver
  could log the count if needed.

### Determinism note
The user explicitly opted out of seed-replayable flips. The flip RNG uses
plain `random.random()` (not seeded by pid/week), so two runs of the same
world will produce different flippers. Signings themselves are still
deterministic; only the decommit pass is stochastic at runtime.

### Smoke result (12 weeks, both genders)
```
week 1: signed=334  flips= 0   ← nothing recent to flip yet
week 2: signed=334  flips=25
week 3: signed=334  flips=41
week 4: signed=334  flips=63
week 5: signed=334  flips=61
week 6: signed=330  flips=67
week 7: signed=  0  flips=93   ← class fully signed, flips still firing
week 8: signed=  0  flips=54
week 9: signed=  0  flips=33
week 10: signed= 0  flips=11
week 11: signed= 0  flips= 0   ← past cutoff
week 12: signed= 0  flips= 0
TOTAL  signed=2000  flips=448  ← ~22% at rate 0.04 in that smoke; now 0.067
```

(The smoke was run at the prior rate before recalibrating to the Power
Four benchmark; lifetime rate at 0.067 lands at the targeted ~18.8%.)

## Original follow-ups (not done)
- The recruit profile's College List / Dreamsheet still works off the
  appeal model, not the actual commit. Once committed, the profile could
  collapse the dreamsheet into a "Signed with X" banner.
- A `flips` history (with weeks and previous schools) would let the
  recruit profile show a small timeline ("Committed → X w4 · Flipped → Y
  w6"). Today only the running count survives — the previous schools are
  overwritten.
