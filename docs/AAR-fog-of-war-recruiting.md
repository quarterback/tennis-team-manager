# AAR — Fog-of-war recruiting (the model it was always supposed to be)

**Date:** 2026-06-27
**Scope:** What computer programs *see* when they recruit, and the junior circuit's
real job. This is a CORE DESIGN FIX, not a tweak — it makes recruiting work the way
it was intended from the outset. It also resolves the "app is spinning" crash-loop,
which was a symptom of the same wiring.

> ⚠️ For the next agent: the recruiting AI now runs on **perceived** caliber, never
> the truth. If you see the AI reading `current_overall` / `recruit_caliber` in a
> recruiting decision, that's the bug this AAR removed — do not put it back.

---

## The intent (what the owner always wanted)

Recruiting is a **fog-of-war** game. The owner (god-mode) sees everything — true
ability, the portals, scout_intel. **Computer programs must NOT.** They should decide
off *public, imperfect signals* and therefore make mistakes: over-draft a flashy bust,
miss a quiet stud. Those mistakes are the whole point — they scatter misallocated
talent for the owner (and the fall portal, and scout_intel's "buried gems" boards) to
exploit. If the AI knows the truth, it never errs, and that entire loop has nothing to
correct.

Three public signals, each with a distinct job:

| Signal | What it is | Source |
|---|---|---|
| **Points** | Pure junior-circuit *performance* — the results ledger. | `junior_points` (circuit) |
| **STR** (`junior_str`) | Pure *performance* — results-based rating that bounces around with what they actually did. | junior circuit |
| **Stars** | The recruiting service's *interpretation of talent*: a **noisy projection** (the scouting "feel") — sometimes dead-on, sometimes badly off. **Independent of performance.** | `scouting_report` |

Every program sees all three and weighs them into its **own decision matrix** — and
**philosophies differ**: a "trust-the-tape" staff chases points/STR (winners), a
"trust-the-service" staff chases stars (the projection). Each gets fooled in its own
way.

## How it was ACTUALLY working (the unintended drift) vs. intended

| | **Was actually doing (wrong)** | **Intended / now** |
|---|---|---|
| AI signing signal | `recruit_caliber(p)` = `current_overall` — **raw true ability** | `perceived_caliber(p, coach.results_bias)` — a per-program blend of stars + performance, **never the truth** |
| Stars (`_recruiting_score`) | `0.6·current_overall + 0.4·scouting` — **60% raw truth** | `scouting_report` only — the service's noisy talent projection |
| Junior circuit's role | Display-only flavor on the board | **The performance axis the AI actually recruits on** |
| Teams differ? | No — every program read the same true number | Yes — per-coach `results_bias` (stars↔results) |
| Result | AI never erred → no misallocation → scout_intel's gem boards & half the fall portal had nothing to act on | AI errs like a real program → gems scatter → the correction loop has a job |

So the junior circuit was doing real work (a full simulated season) that **nothing
consumed for decisions** — pure cost. That cost (a season simulated over the whole
~2,500/gender pool) is also what made the app spin: it ran on the world-advance hot
path and, for both genders, blew past gunicorn's 120s worker timeout → worker killed
mid-build → never cached → permanent crash-loop. Wiring it into signing (where it
belongs) and bounding its field fixes both problems at once.

## Changes

### 1. Perceived signals — the only thing the AI sees (`recruiting.py`)
- `talent_caliber(p)` — the star read: `scouting_report` (noisy ceiling), 0..1.
- `perf_caliber(p)` — junior STR (band 31..57) mapped to 0..1; 0 with no record.
- `perceived_caliber(p, results_bias)` = `(1−w)·talent + w·perf`, where
  `w = results_bias · junior_str_reliability`. **You can only trust results that
  exist** — a thin/absent junior résumé is judged on the star projection even by a
  tape-trusting staff (without this, unproven kids read as half-caliber and go
  unsigned).
- `consensus_caliber(p)` = `perceived_caliber(p, 0.5)` — the market's balanced read,
  used for a recruit's own sense of their level.
- `recruit_caliber(p)` (true ability) is now documented owner-only; the AI must not
  use it.

### 2. Stars rank on talent projection only (`juniors._recruiting_score`)
Dropped the `current_overall` term → stars are the service's noisy *talent* call,
decoupled from performance. Stars↔points can now genuinely diverge (the gem signal).

### 3. Per-coach philosophy (`coaches.py`)
New `Coach.results_bias ∈ [0,1]` (0 = trust the service's stars, 1 = trust the tape),
drawn `gauss(0.5, 0.22)` so most staffs are balanced and the tails are distinctly one
or the other.

### 4. The AI matrix runs on perception (`world._pick_school`)
- Recruit-side aspiration (window, division ceiling, budget floor, level) uses
  `consensus_caliber`.
- The **program funding gate** uses `perceived_caliber(p, coach.results_bias)` — so the
  *same* recruit clears one program's bar and not another's.
- **No vanished talent:** on signing day (`progress≈1`) a still-unsigned recruit takes
  the best open seat regardless of floor *or division* — an under-scouted gem slides
  DOWN a level (where scout_intel / the fall portal find them) instead of disappearing.

### 5. Circuit before signing, bounded (`world.board_class` / `national_class`)
The AI needs performance at decision time, so the junior circuit runs before signing
(via `board_class`), memoised per class (`circuit_done`). It's simulated over the
**recruited cadre** — the top `CIRCUIT_FIELD = 1500` by talent — because the walk-on
tail sits below every funding floor and signs as a walk-on regardless, so it needs no
junior résumé. This bounds the once-per-world cost. Gunicorn timeout raised 120 → 300
(Procfile/Dockerfile) so the one-time build always completes and caches.

## Dials for future tuning (don't over-calibrate — it's meant to be loose)
- `Coach.results_bias` spread (`gauss` σ in `coaches.generate_coach`) — how extreme the
  stars-vs-tape philosophies get.
- `scouting_report` fog (`Prospect.fog`) — how wrong the service's "feel" is.
- `CIRCUIT_FIELD` — cadre size: more tail fidelity vs. more compute.
- `perceived_caliber` blend / reliability weighting.

## Notes
- **Determinism preserved** within a world (salt-seeded); the circuit is just bounded
  to the cadre, so the walk-on tail has no junior résumé by design.
- The owner still sees truth everywhere (editor, `scout_intel` god-mode). Fog is for
  the computer programs only.
- This intentionally breaks the old invariant "true elites always sign at an elite
  program." The new invariant: **the market signs whom it perceives as good, and
  nobody good vanishes** (they slip down a level). Tests assert that, not golden tiers.
