# AAR — Match Engine & Talent/Ratings Calibration

## Segment summary

This segment started as a question — *how much is the match engine optimized for
upsets, and does player talent/rating do the real work?* — and became a full
recalibration of how matches are decided and how player talent is generated,
distributed, rated, and allocated. The throughline, set by the user: **talent
decides; randomness is only the residual; competitiveness comes from the talent
distribution, not from rigging individual matches.** All work is on
`claude/peaceful-faraday-ah5sE`; **130 tests green** throughout. The living
reference is `docs/match-engine-and-ratings.md`.

## What was done

### 1. Match engine → talent vs talent (`engine/fast.py`)
First pass added situational dials (stamina fatigue, grit/clutch multiplier,
recent-form nudge, serve/return texture). The user correctly pushed back: that's
*manufacturing* outcomes. Reverted to a single calibrated signal — the gap in
`overall` (the bounded average of all 9 drivers, each itself an average of rich
attributes) + environment + residual variance. At equal `overall` it's a
coin-flip regardless of profile. Calibrated to UTR (the band is ~1.677 STR/UTR):
`skill_slope = 2.2` → 2 UTR ≈ 75%, 3 UTR ≈ 90%.

### 2. Talent distribution → one bulb-shaped scale (`app/ncaa.py`, `app/development.py`)
The old pool was flat, low (median ~UTR 5), gender- and division-blind. Rebuilt
on one scale (`_talent_mean(strength, division, gender)`):
- D1 > D2 > D3; men a ceiling above women (women's pool lower *and* compressed).
- Fixed the maturity bug (juniors-level maturity suppressed college ability) with
  class-scaled maturity (Fr→Sr 0.83→0.99) + headroom.
- Tight within-program spread (σ≈2.5) → **dense lineups**: top-12 D1-men programs'
  #1s span ~0.8 UTR; elite-vs-elite duals go to the favorite only ~69%. The
  grade/STR clamp is the governor (best near, rarely at, the ceiling).
- Realized D1-men season: **favorite ~66% overall** (most matchups inside ~1.5
  UTR → genuinely unpredictable), with the per-gap curve still hitting 2 UTR→~80%,
  3+→90%.

### 3. Recruits → one national pool, full star ladder (`app/world.py`, `app/web/state.py`, `app/juniors.py`)
- **One national pool per gender** (thousands), viewed nationally / by state /
  internationally; every program D1–D3 recruits from it — no per-division pools or
  stars. Same `_talent_mean` scale, thin margins, juniors keep low maturity so
  they develop into rosters (distribution persists year over year).
- **Full star pyramid as a function of talent** (rank within the gender class):
  Blue Chip ~1.5% / 5★ 2.5% / 4★ 8% / 3★ 18% / 2★ 28% / 1★ 27% / unrated 15%.

### 4. Recruiting allocation (`world._sign_batch`) — verified + extended
Already a greedy best-first model (athletic fit × academics × geo × facilities).
Verified it works with the new scale and added a near-home cross-division path.
Measured: corr(recruit rank, prestige) **−0.89** (tiers on the visible signal),
but corr(**true potential**, prestige) only **0.37** — **~38% of the top-100 by
true potential sign D2/D3** and develop into diamonds-in-the-rough. Talent "falls"
via scouting imperfection + development, not by forcing a blue-chip down.

## Design principles (kept)
- Talent (the bounded full-attribute average) carries the bulk; stamina/grit are
  *not* special match-time dials — they matter only through `overall`.
- The displayed scale stays internal STR 31–57 (no UTR remap); calibration is
  expressed in UTR-equivalents.
- Stars and the recruiting board are *views of talent*; STR is the results rating.

## Validation
- `pytest -q` → **130 passing** after every step.
- Distribution, density, star-pyramid, season-by-UTR-gap, and allocation outcomes
  all measured directly (see `docs/match-engine-and-ratings.md` §4–§5 and the
  "How to evaluate" section to reproduce).

## What I did NOT change / growth
- **Multi-year stability** not yet verified by a multi-season sim (scales are
  aligned for it; wants a dedicated eval).
- Men/women top gap is ~2.3 UTR vs ~2.7 real — widen via `_TALENT` women bases if
  desired.
- Distinct playstyles (server/grinder/shot-maker) only if emergent from talent.
- Doubles still a synthetic pair-average.
