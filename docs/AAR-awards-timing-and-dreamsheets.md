# AAR — Awards gated to season's end + dreamsheet realism

**Date:** 2026-06-15
**Scope:** Two fixes from a recruiting/awards review pass, both genders, both
additive: (1) honors (All-American, All-Conference, Player/Coach of the Year)
were being shown mid-season as a live "Projected" board — they should only
appear once the season concludes; (2) every recruit's Dreamsheet was the
identical academic-elite four (Stanford / Columbia / Penn / Princeton),
regardless of talent.

## 1 — Awards only at season's end

### Why
"Players should not be awarded all-conference or any awards til the season
concludes — they aren't weekly awards." The Awards page rendered a live board
each week (labelled "Projected"), and the same live honors leaked onto player
cards via career-honor previews. Reads as if players are already decorated.

### Root cause
`awards.season_awards`, `awards.honor_records` (players) and
`awards.coach_honor_records` (coaches) all computed honors directly from the
current STR board with **no season-phase gate**. The awards route showed them
under a "Projected" banner; `player_career_honors` / `coach_career_honors`
spliced the same live records onto profiles as a current-year "live" group.

### Fix
A single conclusion gate. New `awards._concluded(division, gender, seed)` →
`seasonmode.load_season(sid)["phase"] == "complete"`. (Phases run
`regular → conf_tournaments → ncaa → complete`.)

- `season_awards` returns `_empty_awards()` (with `concluded: False`) until the
  season completes — and does **not cache** the in-progress empty, so it fills
  the moment the season concludes.
- `honor_records` and `coach_honor_records` return `[]` until concluded — which
  also empties the live current-year group on player/coach career pages.
- Awards route drives `final` off `aw["concluded"]` (was
  `phase in ("ncaa","complete")`); the page shows an **"In progress — honors are
  named after the NCAA Championship"** banner with the live Power Index linked,
  instead of projected teams.

Year-end persistence is unaffected: `stamp_world_honors` only runs at the awards
phase / via `/world/awards` once `season_complete`, when the gate passes and
`honor_records` returns the real rows.

### Verified
Men's and women's seasons in `regular` phase → `concluded=False`, zero
All-American tiers, no POTY. `test_web_awards.py` (plays a full season to
`complete`, then asserts real All-American tiers) and `test_web_recruiting.py`
pass — 8/8.

## 2 — Dreamsheets vary and chase brand

### Why
A #1 blue-chip, a #2 blue-chip and a 3★ all showed the **identical** Dreamsheet:
Stanford, Columbia, Penn, Princeton. Aspirations should chase prestige
(powerhouses), not academies — and shouldn't be the same four for everyone.

### Root cause
`recruiting.build_recruiting` built the dreamsheet from a fixed key —
`sorted(schools, key=lambda s: s.prestige + 0.6 * s.academics)` — with no talent
gating and no per-recruit variation. The one academic-and-prestigious cluster
(Stanford + Ivies) topped it for every recruit.

### Fix
Reuse the talent gate from the interest model (see
`AAR-recruiting-interest-and-commitment-timing.md`) plus a per-recruit jitter:

```
gate = academic_gate(caliber)                  # 0 at/above the ~5★ line
key  = s.prestige + 0.6 * s.academics * gate + rng.uniform(-0.09, 0.09)
```

Elite recruits (gate 0) sort on prestige alone → major-conference powerhouses;
the jitter (seeded by the recruit's existing recruiting RNG) reshuffles the tight
top-prestige band so two blue-chips don't surface the same list. Sub-elite
recruits keep an academic lean (gate > 0) but still vary.

### Verified
- Men #1 → Virginia, Texas, Texas A&M, Tennessee · #2 → Virginia, Florida, TCU,
  Auburn · #4 → Stanford, Florida, Wake Forest, Baylor.
- Women #1 → Stanford, Wake Forest, North Carolina, Georgia · #2 → Texas,
  Stanford, Oklahoma, TCU.
Stanford still appears where it's a genuine fit, but no longer monopolises and no
two recruits get the identical four.

## Files
- `app/web/awards.py` — `_concluded`, `_empty_awards`; gates in `season_awards`,
  `honor_records`, `coach_honor_records`; `concluded` flag in the result.
- `app/web/server.py` — awards route `final = aw["concluded"]`.
- `app/web/templates/awards.html` — "In progress" banner copy.
- `app/recruiting.py` — talent-gated + jittered dreamsheet sort.

## Notes / follow-ups
- "Concluded" = phase `complete` (after the NCAA Championship). If All-Conference
  should instead post after conference tournaments, the gate is one comparison to
  loosen (`phase in ("ncaa", "complete")` for conference-only honors).
- The recruit profile's College List + Dreamsheet are still the generative appeal
  model, not the actual sim signing, so a committed school can sit outside the
  shown offer list — a known disconnect to reconcile later.
