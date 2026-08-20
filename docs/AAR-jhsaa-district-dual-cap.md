# AAR — the district season cap (goodbye, 22-dual league years)

## The report

Owner, 2026-08, immediately after moving Evans Larsen Day into a 12-team league:
*"update the scheduling logic because double round robins are bad when leagues are
more than 10 teams. i don't want teams playing more than 16-18 district matches in
a year."*

This REVERSES an owner rule this codebase had carried since the schedule redesign —
"to shorten seasons shrink `MAX_DISTRICT` … never cut the second league leg" — and
it reverses it cleanly: the old rule existed to stop an agent quietly halving the
league to save simulation time; the new one is the owner deciding the league's
actual shape. Both were product decisions. The newer one wins.

## What changed (`app/jhsaa.py`)

**`DISTRICT_DUAL_CAP = 18`.** A league whose full double round robin fits under the
cap plays it unchanged — 10 teams is 18 duals, exactly at the line, so nothing ≤10
moved at all. A bigger league plays **pass 1 complete** (everyone meets everyone —
that is what a league season *is*) and then only the first rounds of the mirrored
pass 2 until the cap is reached. Measured across every real league size:

| League size | Full double | Under the cap |
|---|---|---|
| ≤10 | ≤18 | unchanged |
| 11 | 20 | 17–18 |
| 12 | 22 | 18 |
| 13 | 24 | 17–18 |
| 14 | 26 | 18 |

(Odd sizes land 17–18 because each kept round sits one team out.) Every pairing
still meets at least once; twice-met pairings still get one home and one away; and
because the truncation runs on the seasonally-rotated pass-2 order, **which
opponents rematch varies by year** rather than freezing one privileged set.

## ‼️ The trap: the mid-season split point

`play_regular_season` used to split the round list at `len(rounds) // 2` — correct
for a symmetric double, and silently wrong the moment the second pass is shorter
than the first: on a capped 12-team league (11 + 7 rounds) a halfway split lands at
round 9, breaking pass 1 mid-stride and gluing its tail onto pass 2. The split
point is now `district_pass1_rounds(n)` (n−1 rounds for even n, n for odd), which
is the *end of pass 1* whatever the second leg's length. For uncapped leagues the
two formulas agree exactly, which is why the old one had never been caught.

## What the second leg's truncation does NOT break

- **Tiebreaks** — the ladder's head-to-head and series-aggregate rungs read the
  meetings *actually played*, so one-meeting and two-meeting pairings coexist
  without special-casing. (An unbalanced second leg is how real oversized
  high-school leagues schedule; district win % over slightly different cards is a
  known, accepted property of them.)
- **Dual seeds** — seeded off the ordered (home, away) pairing, never a round
  index, so removing rounds changes no surviving dual's result.
- **Separation and venue rules** — the mirror-separation floor and the
  one-orientation-bit-per-pairing rule are properties of round *positions*, which
  truncation only removes from the end of.
- **OOWP** — `district_oowp` filters by exclusion, not by counting legs.

**Venue balance drifts a little, and that is accepted:** a full double balances
home/away exactly; keeping a subset of the mirrored leg can skew a team's totals.
Measured over the whole association the worst drift is 3 (e.g. 10 home / 7 away in
a 17-dual card); the test bound is 4.

## Tests: five were the stale side

`test_jhsaa_schedule.py` pinned the OLD rule on real-size (11–12 team) fixture
districts — "every league opponent exactly twice", exact venue balance, `len // 2`
as the pass boundary. All five were rewritten to pin the new rule instead (cap
respected, ≥1/≤2 meetings, twice-met = home+away, pass-1-complete structure, the
measured venue-drift bound). Per CLAUDE.md's own opening: a failing test is not
proof the code is wrong — here the tests were the stale side, and the owner's
directive is the authority. The two other failures in that file
(`test_the_season_opens_and_breaks_for_non_district_play`,
`test_non_district_count_is_an_allowance_not_a_season_total`) predate this change
— verified by stashing and re-running on the untouched tree — and are untouched.

## What to check first if this looks wrong later

- A league playing >18 district duals → the cap or the truncation was removed, or
  a new consumer built its own round list without going through `district_rounds`.
- A league card whose mid-season window sits mid-pass → someone reverted the split
  to `len // 2`; use `district_pass1_rounds`.
- "Team X played opponent Y twice but Z once, unfair" → that is the design, not a
  bug: an unbalanced second leg is the cost the owner chose over 22-dual seasons.
  The rotation makes it a different unfairness every year, which is as fair as a
  capped schedule gets.
