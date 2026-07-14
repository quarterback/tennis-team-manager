# AAR — True seed: no conference separation in the NCAA bracket

## What changed
The NCAA team tournament is now **true-seeded**: the bracket is **never rearranged
to keep same-conference teams in separate regions**. This applies to the **whole
game** — both genders, every division (D1/D2/D3/D4), and every seed line, with **no
conditional logic**.

Previously the bracketer carried a large `_PEN_SAME_CONF` penalty and hill-climbed
by swapping teams within a seed band to push same-conference teams apart (which could
drop, e.g., a #5 overall into the #7 slot). That penalty — and all the conference
plumbing that fed it — is **removed**.

## Why
Real NCAA basketball separates a conference's top seeds because that sport is very
top-heavy, so several teams from one league can bunch at the very top. This
simulator's strength distribution isn't top-heavy that way, so the separation
principle isn't needed. The committee's earned seed order is honoured as-is: the team
that earned the #5 overall seed is bracketed at #5, regardless of who else is in its
conference. (This started as the women's-only 2026 NCAA rule change but was
generalised to the entire game — a single rule with no gender/seed special-casing is
simpler and matches how this sim actually plays.)

## What the draw still avoids
Only two, non-conference principles remain in `_pair_penalty`:
- **Regular-season rematches**, scaled by how many times the teams met
  (`_PEN_REMATCH` / `_PEN_MEET2` / `_PEN_MEET3`) — a third meeting is a near-veto.
- **AQ-vs-AQ**: two conference champions meeting in round one (`_PEN_AQ_VS_AQ`). This
  is about autobid pedigree, not conference *affiliation*, so it stays.

Seeding and bracket construction remain separate; the within-seed-band swap machinery
(`_seed_bracket`, `_deconflict_playin`, `_region_r16`, and the regional layout) is
unchanged except that it no longer has a conference term to optimise against.

## How it's implemented (`app/seasonmode.py`)
- Removed the `_PEN_SAME_CONF` constant and the same-conference branch in
  `_pair_penalty`. Its signature is now `_pair_penalty(a, b, played_pairs, autobid_set)`.
- Dropped the `conf_of` argument from the entire bracketing chain
  (`_deconflict_playin`, `_seed_bracket`, `_region_play_in`, `_region_r16`,
  `_region_main_draw`, `_region_main_draw_64`).
- `_ncaa_seeds` no longer computes or returns `conf_of` — it returns
  `(schools, autobid_set, played)`. `_advance_ncaa_round` updated to match.
- No gender or seed-threshold conditional exists anywhere in the bracketer.

## Tests (`tests/test_bracketing.py`)
- `test_pair_penalty_ignores_conference` — two same-conference teams draw no penalty;
  the only remaining signals are rematch and AQ-vs-AQ.
- `test_seed_bracket_true_seed_ignores_conference` — an all-one-conference field is
  left in pure-seed order.
- Existing rematch tests updated to the new (conference-free) `_pair_penalty`
  signature and still assert the swap machinery pulls heavy rematches apart.
