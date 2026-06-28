# AAR — TennisEye: a results-based second star rating

**Date:** 2026-06-26
**Scope:** `juniors.tenniseye_rankings` / `_tenniseye_score`; `world.recruit_class`
(computes it); `web/state` (board rows); `recruiting_hub.html` + `junior_rankings.html`
(the TE star column).

## The problem it fixes

The recruiting board's stars come from `rank_class`, which sorts on
`_recruiting_score = 0.6·current_overall + 0.4·service-ceiling` — projected ability
and ceiling, the **scout's eye**. It deliberately ignores results. Because the
*overall composite* is itself a function of that same board rank, the consensus
star and the overall rating are **correlated by construction** — they're one view,
restated.

That view alone produces a tell-tale absurdity: sort the class by what juniors
actually **won** and the top of the list wears low stars. On the real 2027 class,
the #1 points-getter (Ricardo Tapia, 7,113 pts) was a **4★ ranked 183rd**, and
**24% of the top-100 results-getters were 3★/2★**. A consensus #1 / junior-slam
winner being a 2★ isn't a charming sleeper story; it's the rating ignoring the
single most public signal in the sport.

## What TennisEye adds to the evaluation

A **parallel** star rating from what a junior **did**, not what a scout projects:

```
tenniseye_score = 0.6 · (junior_points / max_points) + 0.4 · (junior_str normalized)
```

— ranking points (accomplishments) plus demonstrated junior STR (level) — ranked on
the *same* TIER_CUTOFFS pyramid as the consensus board, so the two star sets are
directly comparable. On the same class, the top-100 results-getters jump from 49
five-stars (scout) to **92** (TennisEye), and Tapia is correctly 5★.

Crucially, this does **not** overwrite the scout star. Both now sit on the board
(SCT and a teal TE). Teams read two services, exactly like the real world reads
247 vs. Rivals vs. ITF/UTR results — and **the gap between them is the product**:

- **high TE / low SCT** → proven-but-unhyped (a riser the scouts are slow on)
- **high SCT / low TE** → hype without a résumé (a projection yet to cash)
- **both high** → consensus blue-chip; **both low** → role player

## How it serves the fog of war

The fog was muddled before because the star tried to be two things at once — a
public rating *and* a peek at hidden ceiling — and did neither cleanly. TennisEye
lets each input do one honest job:

- **Scout star (SCT)** = the projection. What evaluators *think* a body can become.
- **TennisEye (TE)** = the receipts. What the player has *already produced*.
- **Hidden true ceiling** = the fog. Never shown; it drives whether a recruit
  *develops* in college (the bust/boom), independent of either star.

So a recruit can be a TE-blue-chip who never grows (his ceiling was low — he was
*already* at it: a polished junior who plateaus), or a modest TE who explodes (high
hidden ceiling the results hadn't surfaced yet). The stars are now honest
observable signals; the surprise lives where it belongs — in development, not in a
rating that contradicts the box score.

## Reading a player's actual ability across the inputs

There are now five public signals, and triangulating them is the skill the game
asks of you:

| Input | What it measures | Trusts |
|---|---|---|
| **STR** | demonstrated on-court level (UTR-style, solved from results) | recent matches |
| **Match results / points** | accomplishments — who you beat, how far you went | the season's body of work |
| **TennisEye star** | the above two, bucketed into a comparable star tier | results |
| **Scout star (SCT) / overall** | projected ability + ceiling | the eye |
| **Rank (board vs. points)** | the two orderings; their split is the signal | — |

Practical reads:
- **STR + TennisEye agree, SCT lags** → a real player the board hasn't caught up to.
  Buy now, before the consensus reprices him.
- **SCT high, STR and TennisEye soft** → a projection bet. You're paying for ceiling
  the results haven't shown; right sometimes, a bust often.
- **STR high but points low** → a strong player on a thin schedule (under-the-radar
  for a *legible* reason — he just hasn't been tested), distinct from the old
  illegible "#1 in points, 2★" nonsense.
- **Everything aligns** → no edge, no mystery; pay market price.

The honest answer the game now supports: a player's *current* ability is read off
STR + results (and TennisEye summarizes them); his *future* is the bet you place
with the scout star — and the hidden ceiling decides who was right.

## Notes for the next agent
- `tenniseye_stars` is set in `world.recruit_class` (cached with the class) right
  after `points_rankings`, so it's present anywhere the board reads a recruit.
- Weights `_TE_W_POINTS / _TE_W_STR (0.6/0.4)` are the knobs. Points are
  zero-inflated (most juniors accumulate little), so the points term is a one-sided
  bonus normalized by the class max — it lifts proven winners without sinking the
  field.
- Next step if desired: let the recruiting AI *weight* TennisEye in its offers
  (right now it surfaces to the human; the sim's signing logic still leans on
  `recruit_caliber` = current ability).
