# AAR — Career mode: preseason non-conference scheduling

Part of team-takeover/career mode (see `DESIGN-team-takeover-career-mode.md`).
A coaching lever the owner asked for: let the human-coached program **choose its
non-conference opponents in preseason** (schedule up for a statement win, or load
up on winnable duals).

## How the slate works (what I built on)
`seasonmode._gen_regular_schedule` builds each season's slate once (conference
round-robin + a greedy prestige-matched non-conf fill), and `create_season`
persists it to the `duals` table. At preseason (world week 0) nothing has been
played — every dual is `status='scheduled'`. One `duals` row IS the dual for both
teams (it has `home` and `away`; `team_schedule` returns rows where either equals
the school).

## The approach: edit the persisted slate, not the generator
Because the slate is already persisted and unplayed in preseason, the simplest and
most robust lever is to **edit the `duals` rows directly** rather than add an
override layer that re-runs generation. Editing one row keeps both sides consistent
for free — the chosen opponent gains the dual, the dropped one loses it. This also
sidesteps any regenerate-and-reconcile determinism concerns.

New `seasonmode` helpers (all guard to unplayed, non-conf, REGULAR-season duals the
school actually plays):
- `nonconf_duals(season_id, school)` → `{id, week, opponent, home}` list.
- `eligible_nonconf_opponents(...)` → same-division/gender programs not already on
  the slate (no double-booking) and not self.
- `swap_nonconf_opponent(...)` → replace the opponent, keeping the school on its
  home/away side; rejects ineligible opponents and non-editable duals.
- `set_nonconf_home(...)` → flip home/away.

## Web surface & gating
- `/my-program/schedule` (Clubhouse → "Plan schedule →", surfaced in preseason)
  renders the planner; `/my-program/schedule/edit` (POST) applies swaps/toggles.
- The school comes from `worldconfig.user_program()`, never the form, so you can
  only edit your own slate.
- **Preseason only:** the edit route no-ops once `world.week != 0`, and the planner
  renders read-only after that — your non-conf slate locks when the season starts.
- Each edit calls `reset_all()` to rebuild cached views.

## Why it's safe / respects the principles
- **Conference play is untouchable** (`is_conf=1` rejected) — only the games a real
  coach controls are editable.
- **No disadvantage for inaction:** leave the auto slate alone and nothing changes;
  the generator's prestige-matched schedule stands.
- **Symmetric & deterministic:** editing the shared row can't desync the two teams;
  no entropy introduced.

## Tests
`tests/test_career_schedule.py` (5): non-conf listing + eligibility exclusions;
swap is symmetric (lands on the new opponent, leaves the dropped one); can't book a
team already on the slate; conference duals aren't editable; home/away toggle.
