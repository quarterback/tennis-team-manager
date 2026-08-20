# AAR — JHSAA awards under the 3S/4D regular-season swap

## What changed upstream
`jhsaa.FORMATS['regular']`/`['early']` were swapped (owner rule 2027-08): the
league season now plays **3 singles / 4 doubles**, not 5S/2D. Under the fixed
3S/4D allocation (`_arrange_regular`), S1 is the team's #1 seed, the doubles
pool is exactly seeds #2-#9, and **S2/S3 are seeds #10-#11 — the team's worst
two starters**, not the 2nd/3rd-best players they were under 5S/2D.

## The bug this left in awards
`jhsaa_awards.py` scores a player's résumé off `FLIGHT_WEIGHTS`, a table
shared with TOSS seeding (S1 1.00, S2 0.75, S3 0.25, S4/S5 0.10, D1 1.00,
D2 0.50, D3 0.25, D4 0.10). That table still reads correctly for TOSS
(matches are matches, wherever a player sits), but for awards it silently
carried the *old* meaning forward: a regular-season S2 kept scoring like a
team's #2 player (weight 0.75) when the new allocation puts its actual #2-#9
players at doubles. All-District/All-Region/All-State were overrating S2/S3
and underrating doubles relative to how good the players occupying those
slots actually are now.

## The fix
`FLIGHT_S2S3_REGULAR = {"S2": 0.15, "S3": 0.10}` — an awards-only override in
`_weight()`, applied **only when `phase == "regular"`** (postseason/showcase
duals stay 1S/4D and are untouched; TOSS's own `FLIGHT_WEIGHTS` read is
untouched). This down-weights regular-season S2/S3 to reflect that they're
now depth seats, not the 2nd/3rd-best player on the team.

## Two regressions this caused, and the real fixes
1. **Tried tightening `FLIGHT_FLOOR` first** (`{"state":1,"region":2}`,
   reasoning it should scale with the shallower 3-deep singles ladder) — this
   broke `test_all_state_and_all_district_teams_are_the_same_size` (a 9A
   Third Team came up short on singles). `FLIGHT_FLOOR` gates by literal seat
   number (every team fields exactly one S1, one S2, regardless of ladder
   depth) — it was never a percentage-of-depth cut, so this was the wrong
   lever. **Reverted to the original `{"state":2,"region":3,"district":0}`.**
2. **The S2/S3 override itself broke `_hm_cut`** at aggressive values (S2=0.08,
   S3=0.05 — priced below D4's 0.10): an `_extraordinary`-admitted below-floor
   S2/S3 player scored near-zero under the crushed weight, became an outlier,
   and blew out `_hm_cut()`'s min-based reference point, producing runaway HM
   growth that pinned the `HM_MAX_MULT` guard. **Root cause was `_hm_cut`
   using literal `min()`** as its low reference — one outlier could distort
   the whole threshold. Fixed by switching `_hm_cut` to a 10th-percentile
   reference instead of `min()`, which is robust to a single low outlier.
   Once that was in place, moderate override values (0.15/0.10) worked fine
   and `HM_MAX_MULT` could stay at its original 2.5 — no guard-raising needed.

## Takeaway for a future agent
If a division/format's *slot semantics* change (which seed sits where),
check every consumer of the flight-weight table for whether it's reading
**match difficulty** (TOSS — weight is fine as-is, matches are matches) or
**player quality by seat** (awards — weight needs to track what that seat
now means). They can diverge even though they share one constants table.
