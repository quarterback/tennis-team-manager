# DESIGN — Team Takeover / Career Mode

Status: **proposed** (design doc, pre-build). Forward-looking, not an AAR.
Owner decisions captured below; see "Open questions" for what's still loose.

The "Your Team" tab today is a **dead feature**: three nav links hardcoded to
`MY_TEAM = "Oregon"` that point at the generic team/roster/schedule pages. It
works, but there is no concept of *you* — no chosen program, no decisions scoped
to one club, no stakes. This doc specifies turning it into a real one-program
career mode.

---

## Owner decisions (the scoping forks)

1. **Scope = one program.** You coach a single `(school, gender)` — e.g. Oregon
   men. This matches the engine's natural grain (universes are keyed by
   division × gender; a "program" internally is `(school, gender)`). Everything
   else in your universe and all other universes run on autopilot.
2. **No fail state.** You are never fired. Instead, each season ends with an
   **end-of-season report card** (expectation vs. result, prestige delta, class
   grade, notable results).
3. **Pick any program to start.** Free choice at onboarding — take over a
   blue-blood or rebuild a low-major.
4. **Upward mobility via job offers (later phase).** Prestige unlocks **job
   offers**, surfaced between seasons **exactly like the fall portal runs**: the
   sim proposes a slate, you view it on a dedicated page, and you accept one
   (switch your program) or stay. "No firing" means there is no *downward* forced
   move — only opt-in offers.

---

## Architecture

### The spine: persisted program identity

The whole feature hangs off one persisted fact: *which `(school, gender)` is
mine?* That lives in `worldconfig` (the existing `world_setting` k/v store),
alongside `name_preset`, `intl_share`, etc.

```python
# app/worldconfig.py — new accessors
def user_program() -> tuple[str, str] | None:
    """(school, gender) the human coaches, or None if unset (spectator mode)."""

def set_user_program(school: str, gender: str) -> None: ...
def has_user_program() -> bool: ...
```

Division is **derived** from the school (a school belongs to exactly one
division in `ncaa`), so we store only `(school, gender)`.

**`MY_TEAM` becomes dynamic.** Today it is a module constant in 4 places:

| Location | Use | Change |
|---|---|---|
| `server.py:52` | nav `args={"school": MY_TEAM}` | resolve per-request in `_inject_chrome` |
| `server.py:290` | `my_team=MY_TEAM` in chrome context | `my_team = worldconfig.user_program()` |
| `server.py:179` | active-nav highlight | compare against chosen school |
| `state.py:15,263` | rankings `me=` flag | thread chosen school in (drop the constant) |
| `state.py:1892` | preseason CTA `args` | chosen program |

Crucial nuance: the "Your Team" nav links must pin **`?u` to the user's own
universe** (their division-gender), not whatever universe they happen to be
browsing. So those links carry the user's `(division, gender)`, not the global
`u`. Spectator mode (no program set) hides the "Your Team" group entirely.

### Phases

**Phase 1 — Identity + honest tab.** *(~1 day, low risk, self-contained.)*
- `worldconfig` accessors above.
- Team picker at onboarding (`/start` → `/world/new`). Schools are static data
  (`ncaa` / conferences), independent of seed, so we can list them before the
  world is seeded. Picker is constrained to the **active** divisions/genders the
  player already chose on that screen. A program is required to enter career
  mode; "spectate only" is an explicit opt-out.
- Dynamic `MY_TEAM`; "Your Team" tab follows the chosen program; rankings
  highlight it; spectator mode hides the group.
- **Outcome:** the tab stops lying. Still mostly a viewer — but it's *yours*.

**Phase 2 — Season loop / agency.** *(~3–5 days; recruiting is the risky part.)*
The decision surfaces already exist; takeover *scopes* them to your program.
- **Lineup** — `overrides` already stores per-program lineup reorders; surface
  YOUR lineup as the headline weekly/preseason action.
- **A real preseason page for your program** — replace the generic "your class
  signs automatically" dashboard with your roster, departures, incoming class,
  and budget.
- **Recruiting as a decision** — today your class auto-signs. ⚠️ This is the
  **invariant-heavy** part: the recruit economy (budget by tier, `TIERS` costs,
  `_TIER_FLOOR` gates) is intentional design. Takeover must **direct the same
  budget the sim would already spend** — never hand your program a bigger budget
  or bypass the floors. v1 keeps it light: *approve / re-prioritize your signed
  class within the budget the economy hands you*, not bidding wars. Full
  recruiting battles are a stretch goal, explicitly downstream.

**Phase 3 — End-of-season report card.** *(~1–2 days, low risk — derived/read-only.)*
- `world._update_prestige_momentum` already computes per-`(school, gender)`
  over/under-performance at rollover. Surface it: projected finish vs. actual,
  prestige delta, signed-class grade, notable wins/upsets, conference result.
- Read-only. Reads momentum; does **not** override it.

**Phase 4 — Job offers (prestige-gated, portal-style).** *(~3–5 days, medium risk.)*
- New between-seasons **hold** modeled on `fall_portal`: at rollover the world
  pauses at a `coaching_carousel` phase, the sim proposes offers from programs
  whose tier is at/above your current prestige standing (intents stored like
  `fall_portal`; slate derived/editable), you view on `/job-offers`, and you
  **accept one** (switch `user_program`) or **stay**.
- A persisted **coach career track** records your moves (school, seasons, record)
  — a small new table, or reuse `coachreg`.

---

## Interaction with the design invariants (must-not-break)

Per `CLAUDE.md`, these are intentional and takeover must respect them:

- **Recruiting budget economy** — your program spends the *same* budget the
  economy dictates (`recruit_economy` bands by conference/prestige tier). Takeover
  *directs* spend; it does not inflate it or skip `_TIER_FLOOR`.
- **Dynamic prestige momentum** — your team's prestige keeps drifting YoY like
  everyone else's. The report card *reads* momentum; it never freezes or forces it.
- **Injuries (non-deterministic, per-save)** — your lineup already filters
  `unavailable` pids via `coach_lineup`; no change needed.
- **Fall portal** — your program already participates. Phase 4's carousel is a
  *separate* between-seasons hold; it reuses the portal's intents→resolve→commit
  *pattern*, not its table.
- **Aid-display caps** (`scholarships.py`) — untouched; orthogonal to takeover.

---

## Effort summary

| Phase | What | Effort | Risk |
|---|---|---|---|
| 1 | Program identity + honest "Your Team" tab | ~1 day | low |
| 2 | Season loop: real preseason, lineup-as-action, recruiting-as-decision | ~3–5 days | med (recruiting) |
| 3 | End-of-season report card | ~1–2 days | low |
| 4 | Prestige-gated job offers (carousel) | ~3–5 days | med |

Phases are independently shippable. Phase 1 alone already removes the "Oregon
lie." Each later phase is opt-in value on top.

## Open questions

- Report-card "expectation" — reuse the prestige-momentum baseline directly, or
  show a friendlier projected-finish number derived from it?
- Job-offer cadence — every offseason, or only when you clear a prestige
  threshold? (Default: offers appear only when a higher-tier program's bar is met.)
- Does switching programs mid-career carry any roster/recruiting penalty, or is
  it clean? (Default: clean — sandbox.)
