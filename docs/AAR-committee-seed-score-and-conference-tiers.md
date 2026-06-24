# AAR — Committee Seed Score + prestige-percentile conference tiers

**Date:** 2026-06-24
**Scope:** `seasonmode.committee_seed_score`, `_conf_tier_map`, `_CONF_TIER_PCTL`,
`_AQ_BONUS`; `_project` / `_ncaa_seeds`; `projection.html` blurb;
`FEATURE-tournament-selection-seeding.md`.

## What changed and why

The field was previously selected **and** seeded by a single sort of ITA team
ranking points. The owner's selection-committee directive asked for a *committee*:
a blended seed value that weighs more than one thing, the way a real committee
does. The blend (`committee_seed_score`), weights summing to 1.0:

| Weight | Ingredient | Source |
|---|---|---|
| **45%** | Power Index rank score | `power_index` (0–1 strength) → 0–100 rank score |
| **30%** | ITA team-points rank score | `ita_team_points` (0–92 résumé) → 0–100 rank score |
| **15%** | Championship bonus (AQ only, tiered) | `_AQ_BONUS[tier_of[conf]]` |
| **10%** | Recent form | last-five W% from `team_form` |

Each rating is converted to a **rank score** (`100·(n−rank+1)/n`, best ≈ 100)
before blending so the 0–1 and 0–92 scales combine on equal footing. The same
score both SELECTS the at-large field and SEEDS the whole field, so a
power-conference champion can out-seed a comparable at-large **without any
hand-sorting** — the AQ bonus does it, and it's capped at 15% so merit still
dominates. Selection vs. seeding vs. bracketing remain three separate processes;
AQ status only ever enters seeding through that capped bonus.

## Conference tiers: prestige percentile, NOT a canon list

The directive named "power conferences" (SEC/ACC/Big Ten/Big 12/Pac-16, later
Yankee). Rather than hardcode names — which wouldn't travel to D2–D4 or survive
realignment — `_conf_tier_map` ranks a division's conferences by
`ncaa.conf_prestige` and assigns a tier by **percentile**:

```python
_CONF_TIER_PCTL = [(0.75, "top"), (0.40, "mid"), (0.0, "low")]
_AQ_BONUS       = {"top": 100.0, "mid": 40.0, "low": 12.0}
POWER_TIERS     = {"top"}
```

### Tier shape (owner-tuned, 2026-06-24)
The original had four tiers (top/major/mid/low). The owner collapsed **major into
the elite tier** and **widened mid-major**, landing on three tiers. Cutoffs were
chosen to land on real breaks in the D1 men's prestige ladder (elite ends at CIC
0.60; mid ends at Patriot 0.48, just above the 0.48→0.45 gap). Result on D1 men
(34 leagues):

- **top / Elite (9):** Pac-16, SEC, ACC, Big 12, Big Ten, Ivy, **Yankee**, WCC, CIC
- **mid / Mid-major (12):** **MW, Big West, CUSA, Sun Belt**, A-10, ASUN, SoCon,
  Big East, WAC, MAC, CAA, Patriot
- **low / Low-major (13):** Southland, Meridian, UAA, Big Sky, MVC, Summit, Big
  South, Horizon, America East, OVC, MAAC, NEC, Heritage

The owner explicitly wanted MW/Big West/CUSA/Sun Belt in mid-major and Yankee in
the elite tier; both hold.

## Verified
On the live D1 men's projection: Elite-conference AQ champs seed at the top
(Stanford 96.0, Mississippi State 95.4, …); weak low-major AQ champs (OVC,
America East, NEC) still get in on automatic bids but seed at the very bottom
(27–39); strong at-larges from elite leagues (Princeton, George Washington) sit
just outside the full field at ~64. Monotone within the field; the AQ/AL chips
explain why a higher-scored at-large can be the "first out" while a lower-scored
champ is the "last in."

## Gotchas for the next agent
- Weights must sum to 1.0 (`_W_PI + _W_PTS + _W_AQ + _W_RESUME`).
- Tiers are **percentile-relative**, so adding/removing conferences shifts
  membership. If a count changes materially, re-eyeball the cutoffs against the
  prestige ladder rather than assuming the old breaks still land cleanly.
- The AQ bonus is a *seeding* nudge only; it never changes selection (champions
  are auto-included regardless) and never changes bracketing penalties.
