# AAR — Recruiting fill (prestige-aspirational), transfer portal, flip trail

**Date:** 2026-06-16
**Scope:** A run of recruiting-realism fixes: major programs were signing nobody
despite open spots; there was no way to track transfers; the FLIP label carried
no information; and the profile had hand-holding microcopy.

## 1 — Prestige-aspirational signing (majors fill)
**Symptom:** Power programs (Texas, Arizona State, Kansas…) signed **0** recruits
despite having senior openings; only ~48% of programs with openings got anyone,
and only ~34/64 top programs filled.

**Root cause:** The model had each recruit independently maximise their *own*
fit. A level-match (prox) term made mid recruits prefer their own level, the
candidate window hard-capped the upside (`cal ± 0.30`), and the thin elite tail
(pool centred on D2-median talent) couldn't cover every major's seats — so the
top programs that the few elite didn't pick simply starved, and mid recruits
were barred from reaching them.

**Fix (`world._pick_school`):** recruits now **aspire up** — each chases the most
prestigious program that still has a seat for them. Window widened upward; the
no-seat fallback reaches for the best *open* program (not the lowest). With
**best-recruits-first + seat caps**, the class tiers itself top-down: power
programs fill first with the best available, and when the elite run short the
next tier calibrates in to fill the spots instead of leaving them empty. A mild
own-level pull keeps elite talent from slumming; academics still pull sub-elite
recruits to academic programs (gated by talent). Removed the level-match/lineup-
need experiments that had it backwards (they penalised a recruit for filling a
3/4 spot at a major vs. being #1 at a D3 — the opposite of intended).

**Verified (women-only, full cycle):** ALL top-64 programs fill (64/64), top-200
all get recruits, talent tiers top-down. The 503/1085 that fill are the top
programs by prestige; the rest take walk-ons (1000 recruits vs ~2170 openings).
World tests 9/9.

**Design note:** this is not a literal draft (no fair draft order exists). It's a
congestion market — recruits chase up, seats cap each program, and "turning
elsewhere" falls out of best-first + availability. Schools effectively recruit
within their prestige band because that's who's left when their level signs.

## 2 — Transfer Portal (Management nav)
A recruiting-style menu for transfers: every completed move with where the player
started and where they went (from → to crests), plus year/class/STR, newest
off-season first. Reconstructed from career history (a school change between
seasons is a transfer). The sim resolves the portal at year rollover, so there's
no persistent "in the portal" limbo — it shows completed moves. Populates after
the first off-season (verified: women-only year 1 lists 188 transfers).

## 3 — FLIP commitment trail
The FLIP label gave no context. World signings now persist a `commit_history`
(original school + each reopen/flip with its week); the recruit profile shows a
"Commitment Trail" — where they originally signed and when they reopened — for
any prospect who flipped. Accrues from flips going forward.

## 4 — Microcopy
Stripped over-explanatory panel subtitles on the recruit profile ("every opponent
was a fellow recruit", "two independent ceiling reads", "¼ weight into the
combined ranking", etc.). Left the crystal ball and dreamsheet untouched per
request.

## Files
- `app/world.py` — `_pick_school` prestige-aspirational rewrite; `commit_history`
  column + tracking in `_sign_batch`/`_decommit_pass`; `find_persisted_player`
  attaches the trail.
- `app/web/state.py` — `transfer_portal_view`.
- `app/web/server.py` — `/transfers` route + Management nav.
- `app/web/templates/transfers.html` (new); `recruit.html` (trail + microcopy).

## Follow-ups
- Recruit pool is 1000 vs ~2170 openings, so only the top ~500 programs sign
  *recruits* (rest take walk-ons). Raising the pool would let more programs sign
  recruits, but it was capped at 1000 for memory (see AAR-oom-recruit-cadre-
  memory) — check headroom before bumping.
- Transfer portal shows completed moves only; a real portal-entry window (intent
  to leave) would need the sim to model transfers as a staged process.
