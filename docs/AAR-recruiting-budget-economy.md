# AAR — UTR-true talent + a recruiting budget economy

The throughline: make on-court talent read like real college tennis (UTR-anchored)
and make elite talent **cluster** at the programs that can pay for it, instead of
being spread evenly by conference. This replaced the old flat conf-strength roster
model entirely.

## 1. Calibrating talent to the UTR ladder
The strength→talent slope had collapsed the whole conference-prestige band into a
few points, so matches were coin-flips. Widening it fixed the parity but exposed
the opposite problem: rosters were jammed in the top of the 20–80 scouting scale,
which on the UTR map (grade 20 ≈ UTR 1, grade 80 ≈ UTR 16.5) put ordinary college
teams near **Grand Slam level**.

Using real 2025–26 UTR ladders (top college men ≈ 14.3, women ≈ 11.5; D2 forum
data — "12+ UTR" players, an 11.8 D1/D2 border, Barry's ~9-UTR lineup) we
recalibrated so college sits where it belongs and **nobody touches the pro
ceiling**:

- **Grade ↔ STR ↔ UTR** (the calibration reference): `UTR = 1 + (grade−20)×0.2583`,
  `STR = 31 + (grade−20)×26/60`. So grade 50 ≈ STR 44 ≈ UTR 8.8; grade 70 ≈ STR 53
  ≈ UTR 14.
- Lowered division talent bases + tightened the within-conference draw (gauss SD
  0.11 → 0.06) so the top stays a *tight* band and variety among similar players
  comes from the STR rating's **decimals through play**, not big talent gaps.

## 2. The recruiting budget economy (replaces flat conf-strength)
A scholarship-budget economy now builds rosters — initial **and** running-save —
so roster quality is *earned* by where a program sits.

- **Per-program budget** by prestige tier, with a **per-world random jitter** so
  every sim funds differently:
  - D1 — power **14–16** · high-major **12–14** · mid **10–12** · low **8–10**
  - D2 — **2–9** (the worst D2s are genuinely thin; standout programs, prestige
    ≥ 0.50 / ~21 schools, **fully fund** at 9 every year so jitter never drops
    them off the 4★ floor)
  - D3 — **none** (no athletic money; stays on the fit/academics prior)
  - Same for men and women (full funding — the new rule).
- **Recruit cost by star:** blue-chip 3 · 5★ 2 · 4★ 1.5 · 3★ 1 · 2/1★ free.
- **Budget floors gate the elite tiers:** a program can only *attract* a tier if
  its budget clears that tier's floor (blue-chip ≈ 14, 5★ ≈ 10.5, 4★ ≈ 8.5). So a
  budget-8 program can't simply buy blue-chips — they won't come. Programs spend
  greedily on the best attainable tier, then fill with free depth.
- **Star tiers → UTR-calibrated talent grades**, so team strength still lands on
  the ladder.
- **Running-save recruiting** mirrors this: `_pick_school` gates elite recruits to
  programs that can fund them, so the clustering holds as a save runs forward.

## Result (verified)
- **Clustering works:** blue-chips appear at **~100% of power programs** (avg ~5
  each) and **0% of low-budget programs**.
- **On the UTR ladder, with earned spread:**
  - D1 men — best team top-6 **13.1**, median **11.5**, worst **9.6**; top player ≈ 14.3.
  - D1 women — best **11.5**, median ~9.4; top player ≈ 11.7.
  - D2 men — best **10.9** (standout 4★ programs), median **8.5**, worst **6.3**.
  - D3 — fit-driven, ~UTR 4–8.
- Divisions sit right relative to each other: D1 clearly above D2 in the aggregate,
  with **top D2 ≈ low-mid D1** (the real overlap).
- All world / recruit / season suites pass.

## 3. Late D1 expansion
Two more promotions on top of the season's long realignment: **Chicago, the UAA +
Colorado College, Johns Hopkins, Occidental, Tampa/Valdosta State/Rollins, Alaska
Anchorage**, and finally **Linfield → WAC** and **Augustana (SD) → Summit**. D1
now totals **392** schools per gender (D2 286, D3 406), every roster validated
(no school in two divisions, men/women rosters identical).

## Files
- `app/recruit_economy.py` — budgets, star costs, tier floors, tier→grade, the
  running-recruit budget floor.
- `app/ncaa.py` — `_base_roster` builds D1/D2 from the budget economy (D3 keeps the
  prior); `_TALENT` bases + `_latent_strength` SD (UTR calibration).
- `app/world.py` — `_recruit_market` carries per-program budgets; `_pick_school`
  gates elite recruits by budget floor.
- `data/ncaa/*.json` — all promotions/realignment.
- `tests/test_season.py` — bracket test reframed to "not pure noise" (a low seed
  winning is fine; we want the best team to win).

## Known cosmetic nit
Parenthesized school names ("Union (NY)", "Augustana (SD)") render a crest badge
like `U(` / `A(` — the crest generator grabs the first two characters including
the paren. Harmless; fix in the crest logic when convenient.
