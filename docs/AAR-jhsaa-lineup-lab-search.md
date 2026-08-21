# AAR — the Lineup Lab becomes a talent search (the college model)

## The report

Owner, 2026-08: *"the lineup lab needs to work like the college one does where
i can search by talent level so that i can find all kinds of players — right
now it's locked to 10 programs only and i can only see top talent or misplaced
talent but the college lineup lab works better so just use the same model."*

The old lab had exactly two pools — Talent-Mismatch qualifiers, or every player
sorted best-ceiling-first — and dealt up to ten squads off the top. Whatever
you did, you only ever saw the head of the distribution; a scout looking for,
say, solid 40-50-ceiling depth pieces had no way to ask the question.

## What changed

`state.jhsaa_lineup_lab` now filters its candidate pool the way
`scout_intel.portal_search` does before dealing squads:

- **Talent bands**: min/max current OVR and min/max ceiling (Pot). This is the
  ask verbatim — search by talent LEVEL, not just from the top down.
- **Source classification** (`from_group`) — where the players come FROM,
  distinct from the target class squads are ranked against.
- **Name/school search** (`q`), beside the existing pool/grade-pool filters.

Squads still deal best-first, but **within the filter** — a 40-50 band builds
40-50 squads, which is the point. And the filtered pool itself is returned
(`cands`) and rendered as a paginated **Candidate pool** table under the
squads, so the page doubles as a finder rather than only a squad dealer.

Route (`/jhsaa/lineup-lab`) parses the new args and paginates; the template
grows the filter row and the pool table (same row shape as `/jhsaa/players`).
Everything still reads the cached census (`_jhsaa_all_players`) — no new roster
builds, no resimulation.

## Verified

Rendered with combined filters and pagination against a scratch world; asserted
a 40-50 Pot band bounds both the pool (3,416 of ~15k players) and every dealt
squad, with squad ranks computed against the target class's 120 real programs.
