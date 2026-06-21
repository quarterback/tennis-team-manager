# AAR — recruiting prestige & budget redesign (incl. academic D3)

Triggered by "it's week 22 and elite juniors aren't signing" and a budget-distribution
that wouldn't widen. The thread reworked program prestige, the budget bands, and the
academic-D3 recruiting pull.

## Why nothing would widen
The weakest D1 teams were funded at ~10 and the low-major budget band (prestige < 0.50)
was NEVER reached. Root cause: the old prestige formula `base + (conf - 0.50) * 0.9`
(D1 base 0.66, clamp [0.12, 0.97]) compressed every D1 program into **0.516–0.970** and
let the divisions overlap (D2 ran to 0.71, D3 to 0.56). With no D1 program below 0.50,
the low-major band was dead code — lowering it did nothing, and a steeper multiplier
only pushed 2–3 conferences under the line before over-compressing D3.

## Prestige redesign — non-overlapping per-division bands (no multiplier)
Replaced the multiplier with explicit bands, mapping each conference into its division's
band + the blue-blood school bump:

| Division | Prestige band | Notes |
|---|---|---|
| D1 | 0.40 – 0.97 | by far the widest — spans low-major to blue-blood |
| D2 | 0.20 – 0.30 | |
| D3 | 0.10 – 0.20 | (before academic lift, below) |

Clean separation with a gap above D2. `DIVISION_PRESTIGE_RANGE` + `_CONF_PRESTIGE_REF`
in `ncaa.py`; the conference sets ~82% of the band, the bump adds the top slice.

**Result:** D1 budgets now span **6.7–24** (was 9.4–24) with **125 programs in the
low-major 6–10 tier (was 0)**, while 81 still clear the 5★ floor (13.5) so elite signing
is unaffected. Recalibrated the dependent D2 budget frac and `_ELITE_D2_PRESTIGE` to the
new D2 band.

## Budget bands
- Power band widened 14–16 → **15–24** so the blue-bloods separate.
- Low-major band 8–10 → **6–10**.
- Year-over-year swing: the band jitter was seeded only by salt + program key, so a
  program's budget was identical every season. Seeded it with the world `year` FOR THE
  TOP TIER ONLY (prestige >= 0.79) — the blue-bloods' funding rises/falls within the wide
  band season to season (Virginia ~22–24), while every other tier holds a fixed value.

## Academic D3 — the fallout and the fix
Compressing D3 prestige collapsed the appeal base `(0.15 + prestige)`, and since the
academic pull is a *multiplier* on that base, smart recruits flipped from academic D3s to
low-major D1 (Swarthmore-type appeal 1.94 → 1.07 vs low-D1 1.26). Two-part fix:

1. **Gate** (`world._div_ok`): 4★ can now choose academic-elite D3s (academics >= 0.85);
   blue-chips still never drop to D3; non-academic D3 keeps the rare 5% gate.
2. **Appeal** (`ncaa._prestige`): lift academic-elite D3 *conferences* (academic prior
   >= 0.80 — NESCAC/Centennial/SCIAC/NEWMAC/NCAC/SAA/MWC) out of the band to 0.26–0.42,
   scaled by how academic they are (NESCAC 0.39, MWC 0.26). Regular D3 stays 0.10–0.20.

A smart 2★ picks NESCAC (1.73) over low-D1 (1.26) again. D3 budgets are always 0, so no
funding side effect. The overlap with D2/low-D1 is the deliberate, narrow "academic D3
punches above its athletic division" exception — ~7 conferences, not D3 broadly.

## Dials
- `DIVISION_PRESTIGE_RANGE` / `_CONF_PRESTIGE_REF` — the per-division bands.
- `_D1_BANDS`, `_D2_BAND` — budget ranges; `_ITA…` no. The power-tier year swing scales
  with band width (0.30).
- `ACADEMIC_D3_LIFT = 0.80` and the 0.26–0.42 lift range — which D3 conferences qualify
  and how high they reach.

## Note / not verified end-to-end
The prestige/budget/appeal changes are verified by direct computation (distributions,
appeal scores, budget tiers). The full multi-week world recruiting sim was not re-run to
confirm the season-long signing OUTCOME (it hit SQLite lock/timeout issues in the
harness). Mechanisms are sound; an in-app season is worth a look.
