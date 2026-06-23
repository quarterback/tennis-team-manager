# AAR — Bracket projection seeds AFTER selection; juniors National/International split

**Date:** 2026-06-23
**Scope:** `seasonmode._project` / `bubble_watch` + the projection/data-portal
templates; `juniors.intl_points_rankings` + `state.junior_ranking_rows` + the
junior-rankings board.

## 1. Bracket projection — "why is the cutoff #41 when the field is 64?"

### The mistake
An earlier change numbered the projection's at-large board as `field_rank =
aq_count + al_rank` — i.e. it parked the 23 AQs in field slots 1–23 and the
at-large teams in 24–64. That **treats automatic-qualifier status as a top seed**,
which is wrong. As the owner put it: selection, seeding, and bracketing are three
different processes and must never be conflated.

- **Selection** answers *"why is this team in?"* — AQ (won its conference) or AL
  (best of the rest by Power Index).
- **Seeding** answers *"how good is this team?"* — strength only. AQ status, champ
  status, and method of qualification are **not** inputs. A strong at-large can —
  and should — out-seed a weak conference champion.
- **Bracketing** answers *"who should it play?"* — only here may AQ/AL status be
  used (avoid AQ-vs-AQ, conference separation, rematch avoidance).

### What was already right
The *engine's* field builder (`bracket.select_field`) was already correct: it
auto-includes champions, fills at-large by seed value, then seeds the **whole
field together** (`seeded = sorted(field_progs, key=sc, reverse=True)`). AQs are
not floated to the top there. Only the projection **display** had the AQ-first
bug.

### The fix (`_project`)
After selection, build a single **seed list** of the chosen field ranked purely by
strength (ITA team points — the same metric the bracket seeds by), AQ and AL
interleaved. Number it 1…field. The unpicked teams are ranked just below the
field, so:
- `seed_list` — the field, 1…64, each tagged AQ or AL.
- `last_in` — the **weakest four IN** the field (seeds 61–64; may be weak AQs).
- `first_out` — the **strongest four left out** (seeds 65–68).

The projection page now shows a real **Seed List** with AQ/AL chips and a cut line
at `#field` (the last team in is #64, the first four out #65–68), matching how a
seed list actually reads. `bubble_watch` and the data-portal bubble use the same
`field_rank` (= seed). Verified on a D2 field: at-large teams seeded as high as #6
above weak AQs at #61–64; cutoff #64; first four out #65–68.

> Note on selection vs. seeding optics: a left-out at-large team (e.g. seed #65)
> can hold *more* points than a weak AQ that's in at #64. That's correct and
> intentional — the AQ was **selected** (champ), then seeded last; the at-large was
> **not selected** (at-large spots full) and ranks just outside. Ranking happens
> after the 64 are picked.

The full bracketing constraints (conference separation, regular-season-rematch
avoidance, AQ-vs-AQ avoidance, multiple-meeting penalties) are **not yet
implemented** — the draw is still a protected-seed random draw (`seeded_draw`).
Documented as the next step; see `docs/FEATURE-tournament-selection-seeding.md`
for the published methodology.

## 2. Junior rankings — National = US, International = non-US

The board dropdown's "International (all)" actually mapped to the whole-pool scope
(`points_rankings`), so it listed US players too, and there was **no all-non-US
board**. Fixed:

| Board | Scope | Set |
|---|---|---|
| All (US + International) | `world` | whole pool |
| National (US only) | `us` | all domestic (no longer capped at 100) |
| International (non-US) | `intl` | all non-US — new `intl_points_rankings` |
| By Nation (Top 10) | `nation` | one international country |

Verified the split is clean: US 1745 + non-US 755 = 2500, with zero domestic
players leaking into the International board.
