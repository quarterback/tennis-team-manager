# AAR — the JHSAA display calendar is fitted to the sport's season, not to the schedule graph (2026-10)

## What the owner saw
On the 2030 boys' save a private program's card ran August → September → December
(two league duals on Dec 6, four on Dec 27) → January → March: a fall sport dated
into the following spring, every card internally in order.

## Why
`jhsaa_match_dates` packed the whole gender into statewide ROUNDS (duals with no
team in common) off the transitive "X played M before N" graph. That makes a season
exactly as long as the longest dependency chain through the association, and the
chain grows with the association, not with any card: on a real 860-program save
the regular season needed ~185 rounds, the ladder another ~25, and the window held
~84 dates. The pattern fell to six days a week and the calendar simply extended.
The fault hid because every individual card still read correctly — only the SPAN
was wrong, the same way `AAR-jhsaa-postseason-calendar-lanes.md` hid.

## Owner rules (2026-10)
- Dates are cosmetic. Never derive the season's length from statewide dependency
  depth; `_jh_global_order` orders the processing and sizes nothing.
- Girls March–June, boys August–October with early November for the end of the
  postseason. Postseason at the end of the same window. Never into another season.
- Preserve each school's generated order; a school cannot have incompatible duals on
  one date; unrelated duals may share a date statewide.
- JV shares dates with varsity ("they just can't use the same players" — a lineup
  rule, not a calendar rule); JV may double up on a Saturday.
- The regular season is already too long; district play, the road and State are what
  matter, everything else is ancillary and may be compressed.
- Mixed doubles (summer) and the individual tournaments (preseason) carry no date.

## Design — `world._jh_lay_out`
1. `_jh_choose_slots`: the loosest day pattern (Mon/Wed/Fri/Sat → +Tue → +Thu → every
   day) whose dates inside the fixed window hold `_jh_need` — the busiest card per
   block at 1.25 plus the ladder depth plus the lag.
2. `_jh_blocks` slices each school's regular card off its own district duals into
   early → pass 1 → mid → pass 2 → late; each block's share of the regular calendar
   follows the busiest card in it; a school's j-th dual in a block targets the j-th
   slice of that share. The postseason tail is the ladder's depth, measured by a
   cursor walk over the postseason keys; a dual's target is its rung.
3. A dual lands on the later of its two schools' targets and cursors (strictly after
   each school's last dual), so both cards agree and read in order.
4. Compression, in this order and never past the window: a school more than
   `_JH_LAG` behind plays a doubleheader (non-district, non-postseason, never onto a
   showcase weekend); a league round may run `_JH_LAG` slots into the tail; a regular
   dual is never dated into the postseason tail proper; a postseason dual never past
   the last slot.
5. Showcases keep their shape through `share` (3 pod duals a date, 2 tiered) and
   `snap` (a pod opens on a Saturday, a tiered block on a Friday).
6. JV: the same layout from the JV opener on Tue/Thu/Sat/Sun, Saturday doubleheaders
   allowed, `jv_state` at the tail, no `busy` set.

## Measured (full association, season 2027 fixture)
| | boys | girls |
|---|---|---|
| varsity span | Aug 2 – Nov 5 | Mar 1 – Jun 14 |
| order faults | 0 | 0 |
| district doubleheaders statewide | 85 | 264 |
| late tune-up doubleheaders | 971 | 881 |
| Sunday varsity duals | 0 | 0 |

The busiest cards are 33–34 regular duals (16 league + up to 10 showcase duals + the
non-district allowance); the median is 23. If the owner wants the late tune-up to
stop compressing, the lever is upstream (fewer showcases or a smaller non-district
allowance) — the calendar is not a second scheduling engine.

## Not done
Archived seasons re-date on read (the calendar is derived, never stored), so the
2029/2030 cards straighten out with this change; nothing in the archive moved.
