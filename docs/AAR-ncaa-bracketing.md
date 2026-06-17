# AAR — NCAA bracket: real bracketing constraints

## How it was before
The national-championship bracket was built by pairing **straight off the true
seed list**. `select_field` ranked the field by Power Index, then `_round1_pairs`
dropped that ranked list into the standard bracket skeleton (`_seed_positions`)
and paired adjacent slots — so the first round was effectively seed *k* vs its
complement (1 vs 64, 2 vs 63, …) with **no bracketing logic at all**:

- conference champions (AQs) could draw each other in round one,
- two teams from the **same conference** could meet in round one,
- a **regular-season rematch** could happen in round one,

…purely as an accident of where the seed math placed them. Mathematically
"correct" pairings, but not a credible committee bracket.

## What was done
Separated **seeding** from **bracketing** (the product owner's spec):

1. **Seed + classify** — unchanged: `select_field` returns the PI-ranked field
   plus the autobid (AQ / conference-champion) set.
2. **Place by seed band** — `_seed_bracket` puts teams into the standard bracket
   by band (1-seeds vs 16-seeds, 8 vs 9, …) so seed integrity holds.
3. **Minimise bracketing penalties** — a hill-climb then swaps teams **within
   their own seed band** (slight, integrity-preserving moves) to lower a penalty
   total:
   - same conference `+5000` (avoid),
   - regular-season rematch `+2500` (avoid),
   - AQ vs AQ `+1000` (keep conference champions apart in round one).

   Same-band-only swaps mean a 1-seed always still faces a 16-seed — what changes
   is *which* 16-seed, exactly the freedom a real committee uses. The loop stops
   when no improving swap remains (or the penalty hits zero).

Context fed in at `_advance_ncaa_round`: AQs from `select_field`, each team's
conference from the division, and the rematch set from that season's own stored
REG duals. Conference tournaments deliberately keep the simple seed pairing — a
single-conference bracket can't violate the same-conference / AQ constraints.

## Why this shape
- **Deterministic** — the hill-climb is a fixed-order scan with no RNG, so the
  same season reproduces the same bracket (the sim's core invariant).
- **Within-band only** — guarantees seed integrity for free (no need for the
  spec's "+500 seed violation" term), and keeps the search small (n=64 resolves
  in well under a second, ×6 universes).
- **Real played bracket only** — `/ncaa` is what the league actually plays and
  what crowns the champion. The `/bracket` simulator is a separate projection
  (its own random protected-seed draw) and was left as-is.

## Verification
- Synthetic stress field (64 teams, 10 conferences, 24 AQs, sprinkled
  rematches): naive direct pairing produced 5 same-conference + 3 rematch
  first-rounders; constraint bracketing eliminated **all** (0 / 0 / 0) while the
  seed-band structure stayed identical.
- A full simulated D1-men season: NCAA round 1 had **0 same-conference** and
  **0 regular-season-rematch** matchups, and the tournament still ran to a
  champion. Awards/season web suites pass.

## Files
- `app/seasonmode.py` — `_seed_bracket` (+ penalty constants); `_advance_ncaa_round`
  now builds AQ/conference/rematch context and calls it instead of `_round1_pairs`.
  `_round1_pairs` retained for conference tournaments.
