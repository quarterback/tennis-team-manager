# AAR — Career mode: prestige-gated job offers (coaching carousel)

Part of team-takeover/career mode (see `DESIGN-team-takeover-career-mode.md`).
The owner's framing: "prestige unlocks better jobs; you get job offers like the
portal runs." And the hard constraint from the same conversation: **no firing** —
there is no forced/downward move, only opt-in upward mobility.

## What it does
Once the coached program's season is **complete**, `state.job_offers` produces a
deterministic slate of offers from programs whose prestige sits in a band **above**
the current program. A strong season widens the reach: the band's upper bound grows
with how far the team overperformed its expectation (the report card's `delta`), so
overachieving at a low-major can open a mid-major or better; a flat year yields
lateral-plus options; you can always simply stay.

`band_lo = prestige + 0.02`, `band_hi = prestige + 0.06 + max(0, delta) * 0.6`.
Candidates are every program of the same gender across D1–D4 in that band; the slate
is the top few, ties broken by a per-save seeded RNG (`{seed}|offers|{year}|{school}`)
so it's stable for a given save/season.

## Accept flow
`POST /my-program/offers/accept` validates the pick is on the live slate, then:
1. archives the seat you're leaving to the coach career track
   (`worldconfig.push_coach_seat` — year, school, division, record, verdict, finish),
2. switches `worldconfig.user_program` to the new program,
3. force-activates the new program's universe (same guarantee as onboarding — the
   universe you coach always runs in detail),
4. `reset_all()`.

The new program takes over next season; the roster you built stays with the program
you left (you're the coach, not the owner). Declining is just advancing the world.

## Why it fits the constraints
- **No firing / no forced move.** Offers are strictly opt-in and never worse than
  your current job (`o.prestige >= current` is enforced by the band). Underperforming
  simply means fewer/smaller offers, never a demotion.
- **Reuses, doesn't fork.** Standing is read from the same prestige + report-card
  machinery the rest of career mode already computes; nothing new in the engine.
- **Per-save & spectator-safe.** Career history and the coached pointer live in
  `worldconfig` (per save). Spectator mode → `job_offers` returns None, no surface.

## Web surface
`/my-program/offers` (Clubhouse "💼 Job offers →", shown when the season is complete)
lists offers with tier/conf/prestige and a "Take this job" button, plus the coaching
history. School is always taken from the saved program, never the form.

## Tests
`tests/test_career_offers.py` (4): None in spectator mode; locked until the season is
complete; career-store round-trip; offers after a completed season are never a worse
job than the current one and never the current school.
