# AAR — Talent compression redesign (WIP: Stage 1 pass 1)

> **Status: in progress.** This is the calibration the sim was always meant to have — a
> lifted, compressed talent band where separation comes from *results/attributes/margins*,
> not baked-in talent gaps. Numbers below are a first pass being tuned with the owner; tests
> are NOT yet updated to the new calibration.

## The vision (owner)

Reject the "video-game pyramid" (a handful of greats, everyone else falls away). Instead:
- **Everything lifted + compressed.** A fat band of genuinely-good players; the floor rises;
  divisions overlap heavily instead of stacking. A great D3 kid can out-talent a mid-D1 kid
  — he's just "ranked lower because he didn't win."
- **Tight rosters, loose enough to be organic.** An elite roster runs **~2–3 UTR** deep, not
  the old 7-UTR cliff (and not the absurdly-stacked real Texas 0.7). Haves/have-nots still
  emerge — don't blow up the structure, just boost the levels.
- **Separation from the engine, not the generator.** With talent near-equal, match scores
  (attributes + margins) decide who's actually good — which is also the best **engine test**:
  1,000 duals of 68v69 / 71v72 / 77v77 should still separate the good from the rest.
- **A pro tier above blue-chip (Stage 2).** ~25 standing 80+ players, **green-badged,
  portal-only**, real STR, entering through all three portal cycles (~15–20/gender/cycle),
  cost 8.5–15 indexed to STR-vs-pool so they always get signed.

## Acceptance targets (owner's exact numbers — build to these)

- **Floor:** the absolute bottom (D3/D4, or rock-bottom D2) sits at **grade 36–49** (~UTR
  5–8); ~**10** players below that worldwide are fine, no more.
- **D3/D4 programs:** *average* roster **UTR 4–7**; the better programs reach **8–9**, with the
  **occasional 10** — because the talent pool shifted up, not because the floor was lifted to
  elite. (So don't over-lift D3/D4: average should read clearly below "good.")
- **80+ pro tier:** ~**25** standing in the world at any time.
- **Elite roster depth:** **~2–3 UTR** from #1 to #6 — deliberately *looser* than the real
  Texas super-team (0.7 is "egregiously wild and stacked"); most elite teams are baggier.
- **Structure preserved:** boost the levels so everything *looks like it does now* but higher;
  haves/have-nots still emerge organically. Do **not** flatten everyone equal — "not everyone
  across the board should have access to this talent; that's the point." More teams than real
  college tennis → a **college-basketball feel with tiny rosters** (the intended texture).

### Pro tier — full spec (Stage 2)
- **Volume:** up to **15–20 male and 15–20 female per transfer-portal cycle**, across **all
  three** portal cycles (pre-season, fall, year-end). Standing 80+ population settles ~25.
- **Identity:** grade **80+**, a **green badge**, and a **real STR/OVR** shown like any other
  player — the whole point is to see how they stack. **Recruitable only through the portal.**
- **Cost:** rolls **8.5–15**, **indexed to the recruit's STR relative to the current pool**, so
  a pro is never priced above what some program can afford → they **always get signed**.
- **Budget headroom:** elite programs' recruiting-budget cap raised so they can land them —
  blue-blood band top **→ 33.5**.

## Stage 1 pass 1 — what changed (uncommitted calibration, now checkpointed)

- **`recruit_economy.TIERS`** grades compressed + lifted (drives D1/D2 rosters): Blue Chip
  70→**74**, 5★ 64.5→**71**, 4★ 58.7→**67**, 3★ 52.9→**62**, 2★ 47→**56**, 1★ 41→**50**. The
  29-point cliff → a ~24-point ladder that a single roster only samples a slice of, so 1–6
  cluster and results separate them. Budget economy (who *signs* which star) is unchanged.
- **`_D1_TIER_BANDS["top"]`** blue-blood budget cap 26 → **33.5** (fund deeper elite cores).
- **`ncaa._TALENT`** bases lifted, spreads compressed (drives D3/D4 + program levels):
  D1 (56,23)→(60,16) · D2 (50,58)→(50,24) · D3 (33,44)→(43,20) · D4 (28,44)→(40,18) (+women).
- **Floor clamp** in `_talent_mean` / `_base_roster` raised 24 → **34** (lift the weakest).

### Resulting men's shape (pass 1)
Population peak moved up ~2 UTR; floor lifted to ~grade 34 (was a tail to UTR 1); top
fattened (75–79: 1→25, 70–74: 103→258). Per-division avg UTR: D1 10.2 · D2 9.3 · D3 7.4 ·
D4 7.3. Elite roster spread 5.7 → **3.4** (Texas); low-major D1 (Cornell) 2.1.

## Stage 1 — LOCKED (owner-approved)
Per owner: **no caps** (floor clamp reverted 34→24, "if they fall they fall"), **D3/D4 avg
UTR 7** kept (no engineered spread — it emerges from the sim). Population lifted ~2 UTR, top
fattened, elite roster depth ~3.4 UTR. This is the approved calibration.

## Stage 2 — pro tier: CORE done (`app/pros.py`), integration next
Built + unit-tested (`tests/test_pros.py`): `generate_pros(salt, gender, cycle_key)` →
a deterministic cohort of 15–20, grade 79–80 talent → **OVR ~76–77 / STR ~55** (a clear cut
above a blue-chip recruit), international-heavy nationalities, the green **PRO** badge
(`junior_badges`), `recruit_stars=6`. `pro_cost(pro, cohort)` indexes cost to STR-vs-cohort
across **8.5–15**, so the top pro costs 15 (≤ the raised 33.5 cap) and every pro is signable.

### Pros exceed 80 — how, without touching anyone else (owner: "no hard 80; pros 81-90")
The 80 grade ceiling is kept as the **normalization reference** (grade 80 == unit 1.0 ==
college ceiling), so every normal player is byte-identical. A separate, higher **hard
clamp** `player_attributes.GRADE_CEIL = 100` lets ONLY pros sit in the 80-90 headroom:
- `clamp_grade` upper bound → `GRADE_CEIL`; `current_grade` clamp → `GRADE_CEIL`
  (normal generation still clamps to `GRADE_MAX`, so ordinary players never reach it).
- `grade_to_unit` drops its `min(1.0, …)` cap: grade 80→1.0 (unchanged), a pro's 85→1.083,
  so pro drivers feed the engine ABOVE 1.0 and win more — the engine already clamps the
  *resulting probability* (`_clamp01`), so it's "clearly better, not superpowered."
- `pros.generate_pros` lifts every attribute into **80-90** → **OVR 83-85, STR 58-59**.
Verified: pros beat a blue-chip **130+/200** on court; a grade-74 blue-chip is unchanged
(OVR 78); `test_engine` + `test_pros` green. Every non-pro cap is untouched (33.5 is the
elite-only budget top; recruit tiers, D3/D4 levels, display bands all unchanged).

**Remaining integration (the live wiring):**
1. Emit a pro cohort each of the **three portal cycles** (pre-season, fall, year-end
   transfer), keyed by `<year>-<cycle>`, persisted so a save's pros are stable.
2. **Auto-sign** each pro to an affordable program (budget ≥ `pro_cost`), portal-only —
   they never appear on the HS recruit board.
3. **Green badge** render wherever players show (rankings, roster, player page) off
   `pros.is_pro`.
4. Persist signed pros into `world_roster`/`world_signing` so they play the season.

## Open tuning (next pass)
- **D3/D4 average is at the top edge of the 4–7 target** (~7.3) — nudge bases down ~1.5 UTR
  so average programs center ~UTR 5–6 and "better ones 8–10" reads as genuinely better.
- **Cap the D3/D4 gem grade** (~UTR 11) — the gem mechanic now pulls the lifted Blue-Chip
  grade, putting a UTR-15 kid in D3 (breaks "occasional 10").
- Then: **Stage 2 pro tier**, and the **1,000-dual engine test** as the lock gate.
- **Tests**: the calibration/UTR-band tests (`test_roster`, `test_development`, …) will need
  re-baselining to the new bands once numbers are locked. Not done yet.
