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

**Cut-line, take 2 (review catch):** `last_in` was briefly `in_board[-edge:]` (the
at-large bubble) on a reviewer's note that a protected AQ can't be bumped by
`first_out`. But on a real D1 page that read as confusing: the at-large teams span
the *top* of the field while weak auto-bids cluster at the bottom, so "Last Four
In" landed at ~#69–72 while the seed-list cut sat at #96 — two unrelated cut
points. Reverted to **`last_in = seed_list[-edge:]`** (the four weakest teams
actually IN the field), so the panel lines up with the seed-list cut at `#field`.
Every cut-line row now carries an **AQ/AL chip**, which is what answers the
reviewer's concern *in the UI*: you can see a weak champ is in on an automatic bid
while a higher-rated at-large is the first out.

**Display metric bug (same review):** the seed list was **ordered by ITA team
points** (`ita_team_points` — the 0–92 metric the real bracket actually seeds by)
but **displayed Power Index** (0–1). So the list looked unsorted — a 0.845 team
could sit below a 0.763 team. Fixed by displaying the *same* metric it's ordered
by: the row now carries `pts` (ITA team points), the column is **Pts**, and the
blurb says "team ranking points" instead of "Power Index." `_bubble.html` shows
`pts` too (falling back to `pi` for any legacy caller).

> Note on selection vs. seeding optics: a left-out at-large team can hold *more*
> points than a weak AQ that's in at the bottom of the field. That's correct and
> intentional — the AQ was **selected** (champ), then seeded last; the at-large was
> **not selected** (at-large spots full) and ranks just outside. The AQ/AL chips
> make this visible instead of mysterious.

**Correction (same day):** the bracketing constraints are in fact already
implemented in the seasonmode tournament — `_seed_bracket` / `_deconflict_playin`
place by seed then hill-climb swaps **within a seed band** to minimise
same-conference (5000), regular-season-rematch (2500), and AQ-vs-AQ (1000)
first-round penalties, with seed integrity preserved. The only piece missing from
the owner's spec was the **multiple-meeting penalty** (`played` was a set, so a
2nd/3rd meeting collapsed to one rematch). Added: `played` is now a `Counter` of
meeting counts and `_meeting_penalty` escalates 1→2500, 2→3000, 3+→6000. See
`docs/FEATURE-tournament-selection-seeding.md` for the published methodology.

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
