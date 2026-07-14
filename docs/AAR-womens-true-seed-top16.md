# AAR — Women's tournament "true seed" for the top 16

## What changed
Beginning the season after the 2026 NCAA change, the **women's** NCAA team
tournament brackets its **top 16 overall seeds in their true ranking regardless
of conference affiliation**. Previously the bracketer could shuffle a conference's
top teams into different regions (dropping, e.g., the #5 overall to the #7 slot) to
keep same-conference teams from meeting early. That conference-separation principle
is now **dropped for the women's top 16** — they stay exactly where their seed puts
them.

The **men's** tournament is unchanged: its committee still separates a conference's
top four seeds across regions, so nothing about the men's draw moves.

## Why (real-world basis)
Mirrors the NCAA women's basketball committee decision (chair Amanda Braun, 2026):
"We put a lot of time into establishing those top 16 teams in the order they go
in… the work we did and the work those teams did justifies keeping them where they
are in that group of 16." The men's selection committee kept the conference
separation rule. In practice the change mainly affects the deepest conferences (the
ones that land four or more teams in the field).

## How it's implemented (`app/seasonmode.py`)
Seeding and bracket construction are already separate: teams are placed by pure
seed, then the draw hill-climbs by swapping WITHIN a seed band to minimise
first-round penalties (`_pair_penalty`: same-conference, regular-season rematch,
AQ-vs-AQ). See `docs/AAR-ncaa-bracketing.md` and `docs/AAR-regional-bracket-scurve.md`.

The true-seed rule is a **conference-charge exemption** for protected teams:

- `_true_seed_protected(s, schools)` returns the top `_TRUE_SEED_TOP` (**16**)
  national seeds for `gender == "women"`, and an **empty set** for men.
- `_pair_penalty(..., protected)` skips the `_PEN_SAME_CONF` charge whenever either
  team is in `protected`. Because the same-conference penalty is what drove the
  band swaps, exempting the top 16 means the optimizer never moves them for
  conference reasons — they hold their pure-seed slot.
- The set is threaded through every bracketing path so it applies uniformly:
  `_deconflict_playin`, `_seed_bracket`, `_region_play_in`, `_region_r16`,
  `_region_main_draw`, `_region_main_draw_64`. `_advance_ncaa_round` builds
  `protected` from the national seed order (`schools[:16]`) at both the first-round
  and main-draw seeding steps.

### Scope decisions (deliberate)
- **Only the conference principle is dropped.** Rematch and AQ-vs-AQ avoidance still
  apply to the top 16 — the real rule changed conference bracketing, not the other
  draw principles. A protected team can still be shifted to avoid a heavy
  regular-season rematch; it just isn't shifted to avoid a conference clash.
- **Only the top 16.** Seeds 17+ still get full conference separation for the women
  too — the rule is explicitly about the top-16 group.
- **Men untouched.** `protected` is empty for men, so `_pair_penalty` behaves
  exactly as before; every existing men's-draw invariant holds.
- **D1 (96-team field):** the top seeds are byes placed by the S-curve and were
  never moved by the swap machinery anyway, so the visible effect is largest in the
  64-team divisions (D2/D3/D4) where `_seed_bracket` does band swaps on the top
  lines. The exemption is wired through the D1 path regardless, for consistency.

## Tests (`tests/test_bracketing.py`)
- `test_true_seed_protected_only_women_and_only_top16` — women get exactly the top
  16; men get an empty set.
- `test_pair_penalty_exempts_protected_from_same_conf` — a protected team on either
  side zeroes the conference charge, while rematch/AQ charges survive.
- `test_seed_bracket_true_seed_keeps_top16_in_place` — an all-one-conference top
  band is left in pure-seed order under the exemption (and would still be charged /
  separated without it, i.e. for men).

Existing bracketing tests are unchanged: `protected` defaults to `frozenset()`, so
the men's / legacy behavior is the default everywhere.
