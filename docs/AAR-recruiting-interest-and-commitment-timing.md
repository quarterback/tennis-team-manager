# AAR — Recruiting realism: interest diversity + commitment timing

**Date:** 2026-06-15
**Scope:** Two model fixes to how the national class behaves during a signing
cycle, both reported in-session after the recruiting UI shipped: (1) every
academically-strong recruit shortlisted the same program (Stanford); (2) every
top-tier prospect signed in week 1, leaving only lower tiers on the board. Both
are additive, deterministic, and leave *where* a recruit signs governed by the
same fit model — they change *who academics move* and *when commitments land*.

## 1 — Academics only pull sub-elite talent (interest diversity)

### Why
"Every academic player short-lists Stanford." Elite talent should be ruled by
prestige and spread across major-conference programs; only sub-elite recruits
with good grades should opt for a program beneath their athletic station.

### Root cause
The academic term in the fit score was flat — `(1 + 0.9·academics·gpa)` —
applied to **every** recruit, in BOTH places that score programs:
`recruiting.program_appeal` (the offer/shortlist surface) and
`world._pick_school` (the actual signing decision). Stanford is the one program
that is simultaneously elite-prestige and elite-academic, so for any
high-GPA recruit it topped the board regardless of the recruit's talent.

### Fix
Gate the academic pull by talent. New `recruiting.academic_gate(caliber)`:

```
gate = max(0, (ELITE_CALIBER - caliber) / ELITE_CALIBER)   # ELITE_CALIBER = 0.70 (~5★ line)
academic = school.academics * recruit.gpa01 * gate
appeal  *= (1 + ACA_PULL * academic)                       # ACA_PULL = 2.5
```

- At/above the ~5★ line (caliber ≥ 0.70) the gate is **0** — blue-chips ignore
  academics; prestige rules outright.
- Below it the gate rises, so the further a recruit sits beneath the elite line
  the more a strong GPA can tug them down to an academic program.

`ACA_PULL = 2.5` is calibrated so a strong-GPA 3★ keeps roughly its prior
academic lean. Applied identically in `program_appeal` and `_pick_school`
(world.py imports `academic_gate` + `ACA_PULL`) so shortlist and signing agree.

### Verified
On one class: the **top-60 elite now spread across 46 distinct favourites**
(Georgia Tech, Ohio State, Washington, Houston, TCU, NC State, …) instead of
funnelling to one blue-blood; blue-chip gate = 0.000. Sub-elite, high-GPA
recruits correctly drop to academic programs beneath their station (Swarthmore,
Emory, Case Western, Kenyon, Wesleyan).

## 2 — Per-recruit decision week (commitment timing)

### Why
"Everyone signed pretty much after week 1, at least all the top-tier prospects."
Expected, given the design — but unrealistic. Real cycles stagger elite
commitments and interleave tiers.

### Root cause
`advance_week` signs a flat weekly quota, `quota = senior_openings //
SIGNING_WEEKS = 2172 // 13 = 167`, and `_sign_batch` fills it **strictly
best-first**. The whole 4★+ tier is only 120 recruits — smaller than one week's
quota — so a single tick cleared every blue-chip/5★/4★ plus the top of the 3★
tier. Rank *was* the timing.

### Fix
Give each recruit a deterministic **decision week** decoupled from rank.
New `world._decision_week(p, salt)`:

```
rng = Random(f"{pid}|decision|{salt}")
week = int(rng.triangular(0, SIGNING_WEEKS, SIGNING_WEEKS * SIGNING_PEAK))  # SIGNING_PEAK = 0.45
```

`_sign_batch` gained a guard — `if not final and _decision_week(p, salt) >
world["week"]: continue` — so a recruit only signs once their week arrives;
among those who have, the pass is still best-first (so when an elite IS ready,
they get their pick). The finalize call passes `final=True`, lifting the gate so
anyone still uncommitted signs before the class arrives. (`_pick_school`-returns-
None now `continue`s instead of `break`s, so a recruit whose range is full
doesn't block lower recruits who fit elsewhere.)

Rank still decides WHERE a recruit signs; the decision week decides WHEN.

### Verified
Full simulated cycle, per-week new signings by tier (men):

```
wk  0: + 16   5*:1  3*:1  2*:7  1*:5
wk  1: + 36   5*:1  4*:3  3*:9  2*:9  1*:10
wk  4: +132   BlueChip:3  5*:5  4*:7  3*:23  2*:32  1*:46
wk  6: +175   BlueChip:2  5*:3  4*:19 3*:34  2*:52  1*:43
wk  9: + 78   BlueChip:2  5*:3  4*:7  3*:18  2*:23  1*:17
wk 12: +  7   4*:1  1*:4
```

Week 0 no longer clears the top tier (16 sign, mixed); blue-chips trickle in
weeks 4–9; every week interleaves 5★→1★ with a mid-cycle peak — exactly the
"blue-chip holds out to week 9 while a mid-3★ commits early" target.

## Files
- `app/recruiting.py` — `ELITE_CALIBER`, `ACA_PULL`, `academic_gate`; gated
  `program_appeal`.
- `app/world.py` — import `academic_gate`/`ACA_PULL`; gate `_pick_school`;
  `SIGNING_PEAK`, `_decision_week`; decision-week guard + `final` flag on
  `_sign_batch`; `final=True` at finalize.

## Tests
`test_world.py` (incl. `test_finalize_rollover_deterministic…`) and
`test_web_recruiting.py` pass — 14/14. Both changes are deterministic (seeded by
pid + league salt), so seed-replayable runs are unaffected.

## Knobs
| Constant | Value | Effect |
|---|---|---|
| `ELITE_CALIBER` | 0.70 | talent line above which academics stop mattering (~5★) |
| `ACA_PULL` | 2.5 | academic weight for gated (sub-elite) recruits |
| `SIGNING_PEAK` | 0.45 | mode of the decision-week distribution (× window) |
| `SIGNING_WEEKS` | 13 | nominal signing window length |

## Follow-ups (not done)
- Decision-week could take a mild rank tilt (the very top courted longest) if a
  late-elite-commit bias is wanted; today it's deliberately rank-independent.
- A small per-recruit "early/late signing period" split would mirror real
  recruiting's bimodal calendar more closely than the single triangular peak.
