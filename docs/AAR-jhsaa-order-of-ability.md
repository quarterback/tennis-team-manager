# AAR — JHSAA Order of Ability: the postseason anti-stacking rule

## The report

Owner (2027-08): NFHS rules require playing in order of ability, and the sim
"has been having teams do some illegal stacking without realizing it." The
owner researched real state enforcement models and specified a hybrid: North
Carolina/Kentucky-style assessed ability + West Alameda (California) ladder
arithmetic for doubles, with Texas-style movement limits across rounds — and
the framing that **the association does not govern regular-season lineups; the
Order of Ability binds JHSAA championship competition only.**

## What the "stacking" actually was (diagnosis before code)

The generator was NOT burying stars in low flights. `_squad` has always
dressed the ladder in strict descending order — S1 = #1, D1 = #2+#3,
D2 = #4+#5, D3 = #6+#7, D4 = #8+#9 — which trivially satisfies every
anti-stacking constraint. What actually violated the NFHS model:

1. **The ladder re-ranked itself between postseason rounds.** `_lineup`
   recomputed `_order(ts)` live before every dual, and `ladder_score` folds in
   results — so a hot Sectionals could re-seat the roster at Wards, players
   jumping several rungs mid-bracket (the thing Texas's movement rule exists
   to stop). It also made cards read out-of-ability-order: results can swing
   seats by up to ±7 OVR, which LOOKS like stacking next to displayed ratings.
2. **There was no legality layer at all.** Lineup shape was an accident of a
   naive generator, not a rule — nothing would have caught a future code path
   (or an editor feature) producing an illegal card. Equally, the coach AI had
   no access to the legal freedoms every real state allows: choosing which of
   the top three plays singles, or pairing doubles by actual chemistry.

## The rule (`app/jhsaa.py` — `order_of_ability`, `_postseason_nine`, `_arrange_state`)

- **Establish, then freeze.** Before a program's first postseason dual its
  Order of Ability is established from the ladder as it stands
  (`ladder_score`: ability seeded, season results stabilising it — the
  Kentucky model, ratings + competitive evidence) and stored on the
  `TeamSeason` (`order_of_ability`, pids). It binds for the entire postseason:
  no movement between rounds at all — the simplest form of the Texas
  constraint, chosen over "one rung per round" because the JHSAA has no
  injury system to need the slack.
- **The nine who dress are the frozen top nine.** Strict, no rotation
  (unchanged owner rule).
- **S1 + D1 consume ranks #1-#3.** No top-three player may appear at D2-D4.
  Which of the three plays singles is the coach's choice, scored by what it
  does for the two points those players cover (`S1.overall` + the other two's
  `doubles_rating`).
- **D2-D4 are ordered on combined ladder rank — as a BOUNDARY.** Two-stage
  legality, exactly as specified: the rank sum is the anti-stacking line, not
  the final sporting judgment (Iowa's point: the best singles players are not
  automatically the best pairs). Within `PAIR_SUM_TOL` (2) of each other,
  pairs order on the engine's real `doubles_rating`; beyond it, ladder
  arithmetic wins regardless of chemistry. #5+#8 outplaying #4+#7 is a
  lineup; #2 hiding at D4 is stacking.
- **The coach uses the legal freedom.** #4-#9 partner up by best total
  `doubles_rating` over all 15 partitions (ties break toward ladder-natural
  pairs), then the pair order is bubble-fixed against the boundary. So the
  postseason Flip is solved with the roster the team actually has — creative
  partnerships, no generator exploits.
- **Regular season untouched.** League play keeps the live ladder and the
  bench rotation (`_ROTATE_ONE`/`_ROTATE_TWO`); `order_of_ability` stays
  empty until the postseason starts, and a test pins that.

## Mechanics worth knowing

- `_arrange_state` returns the nine IN SLOT ORDER
  (`[S1, D1a, D1b, D2a, D2b, D3a, D3b, D4a, D4b]`) — `_squad` dresses by
  position and `_slot_players` resolves who played a slot by the SAME
  indexing, so records/credits/line displays stay truthful with zero changes
  to the recording layer. That invariant (one indexing rule, no second
  opinion) is why the arrangement happens in the lineup list rather than
  inside `_squad`.
- A degraded side (fewer than nine) skips arrangement and plays the plain
  order — degrade, never crash, as everywhere else in the engine.
- Nothing is persisted: the Order of Ability is season-state on `TeamSeason`,
  frozen lazily on first postseason use, deterministic from the same inputs.
  Archived duals record lineups per dual exactly as before.
- The calibration harness (`scripts/jhsaa_upset_calibration.py::eff`) measures
  postseason strength off the ARRANGED lineup now, so its per-line signals
  match what actually takes the court. The upset-by-gap tables re-measured in
  the target shape (0.10+ gaps ~1%, 3-2 only; near-equal bands unchanged).

## Traps for later

- **Do not "fix" the freeze by re-deriving the order per round** — that is the
  original violation. If the owner ever wants mid-postseason movement, it is
  a bounded swap (one rung), never a live re-sort.
- **The rank sum is a boundary, not a sort key.** Sorting D2-D4 purely by rank
  sum deletes the doubles-chemistry freedom the owner explicitly wanted;
  sorting purely by `doubles_rating` deletes the anti-stacking rule. Both
  halves are load-bearing; `PAIR_SUM_TOL` is the dial between them.
- Pinned by `tests/test_jhsaa_lineup.py` (legality of every constraint, the
  freeze, and the regular season staying free).
