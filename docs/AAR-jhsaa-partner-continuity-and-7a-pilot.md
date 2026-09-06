# AAR — Doubles partner continuity, and 7A joins the 4S/5D pilot

Owner rules 2026-09.

## Partner continuity (`TeamSeason.pair_counts`)

The 2073 read showed the median doubles player using four different partners in a
season, with only 17-18% keeping one all year — while every elite pair in the file
was exactly a pair that didn't churn. Owner: partner switching, especially at the
top level, "should happen less once the season settles in … when partners work
together they should be more likely to stay together." Explicitly season-to-season
only, and it must not hurt the team.

### The mechanism — two doors the sibling rule already opened

- **Evidence**: `_credit` now counts every doubles line into
  `TeamSeason.pair_counts` (`{(pid, pid) sorted: [lines together, wins together]}`).
  A `TeamSeason` lives one season, so nothing persists across years by
  construction — no store, no override row, no migration.
- **Direct arrangers** (`_arrange_regular`, `_arrange_early`): an **established**
  pair — `PARTNER_ESTABLISHED_MIN` (6, the awards' own `MIN_PAIR_MATCHES` bar)
  lines together at a **non-losing** share — is kept together through the same
  `_force_pairs` swap a sibling pair rides, via `_established_units`. Siblings
  outrank continuity where the two claim one player. A pair losing together is
  never protected: the coach breaks it up, which is the realism and what keeps the
  mandate from costing the team.
- **Searching arrangers** (`_arrange_state`, `_arrange_wide` — the postseason,
  where the stakes argue against a mandate): continuity is a **chemistry bonus**
  on the pair score, `partner_chemistry` = `PARTNER_CHEMISTRY` (0.025, the
  `FAMILY_CHEMISTRY` scale, ~¼ sd of the pair-rating spread) evidence-weighted by
  `n/(n + PARTNER_PRIOR)`. It settles a near-tie toward the pair that has been
  playing together and can never override a real ability difference;
  `_order_pairs`'s anti-stacking rank-sum boundary still runs afterwards.

### Why two doors, not one

The regular-season strategies pair by **direct decision** (owner correction
2027-08 — no search), so a rating bonus there changes only which flight a pair
takes, never who partners; a mandate is the only lever. The postseason arrangers
**search**, so a bonus is exactly the right lever there — and forcing pairs in a
championship lineup is where "must not hurt the team" bites hardest.

### Traps

- The `_credit` guard `mates[0].pid != mates[1].pid` matters: a degraded side's
  wrapped lineup (`_slot_players` wraps rather than raises) would otherwise count
  a player as their own partner.
- `_established_units` sorts candidates on (-lines, pid key) — a deterministic
  order, never dict iteration luck.
- No new rng draws anywhere, so every seed stream stays aligned.

Pinned in `tests/test_jhsaa_lineup.py` (established pairs hold in all three
strategies; losing and short histories are not protected; siblings outrank;
chemistry is capped; postseason legality holds; `_credit` records pairs).

## 7A joins the 4S/5D pilot

JHSAA-approved 7A pilot: `WIDE_GROUPS` is now `("7A", "8A", "9A")`, and membership
is the whole change — road-to-State + early window at 4S/5D, TOC reverts to 1S/4D,
league season/showcases untouched, `jv_postseason_cut` moves to #15 (derived,
never typed), all fall out of the constant. `CHALLENGE_SLOTS` does **not** move:
the four contested seats are a property of the 40-team State field, and 7A's field
is still 32. No year gate, matching the 8A/9A pilot (owner: explicit).

## Pre-existing failure, noted not fixed

`test_maximize_never_scores_worse_than_traditional` fails on the clean tree too:
it still asserts the retired 105-partition search's optimality guarantee against
today's snake-pair heuristic (owner correction 2027-08). The test is the stale
side; whether to weaken it or drop it is the owner's call.
