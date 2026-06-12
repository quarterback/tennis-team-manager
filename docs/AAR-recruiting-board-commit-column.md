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

## Follow-ups (not done)
- The recruit profile's College List / Dreamsheet still works off the
  appeal model, not the actual commit. Once committed, the profile could
  collapse the dreamsheet into a "Signed with X" banner.
- The team-recruiting page could light up the newly-committed prospect with
  a "this week" badge, since `world_signing` doesn't currently carry a
  week-stamp. That'd need a schema column.
