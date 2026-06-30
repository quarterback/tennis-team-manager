# AAR — Region-mix editor: direct weights (replacing capped multipliers)

## Context / problem

The onboarding "Fine-tune by nation/region" editor let you scale each region with a
**multiplier** (0–8×) on top of the chosen band preset. Two structural failures:

1. **Multipliers preserve relative proportions.** Effective share is
   `intl_share · (base·mult) / Σ(base·mult)`, so setting *every* region to 8× cancels in
   the ratio — identical to all-1×. Raising one region meant lowering others, and the
   knob only went down to 0.25×/0×.
2. **8× ceiling on a tiny base.** Asia/Africa regions have band weights ≈0.02; ×8 ≈
   0.16, which renormalizes to ≈0.6%. So Asia/Africa stayed negligible no matter what,
   and a bespoke mix like **"European core + meaningful Latin America / Canada / Africa"**
   was simply unreachable.

Owner decision: replace multipliers with **direct per-region weights**, world-level
(one authored mix per world, as before — just expressive).

## Change

The editor now shows a **weight input per region** (the band preset just pre-fills the
values), with the existing live `%` readout — the share of the *whole* world, updating
as you type. Weights are relative; the engine renormalizes, so the absolute scale is
cosmetic. A region set to 0 is excluded; "Reset to band" re-fills from the current band.

- `app/worldconfig.py`: removed `region_mult` / `set_region_mult` / `MULT_CHOICES` /
  `_INTRO_FLOOR`. Added `region_weights_custom()` + `set_region_weights()` storing the
  full authored `{region: weight}` map under the `region_w` key. `region_weights()`
  returns the authored mix when set, else the chosen band — **US omitted** (its share is
  the domestic split, `intl_share`) and **hidden regions (`guam`) excluded**.
  `region_groups()` returns each region's current editor weight (authored value, else
  `band_fraction × WEIGHT_SCALE`, `WEIGHT_SCALE = 1000`).
- `app/web/templates/onboarding.html`: per-region `<input type=number name="w_<id>">`
  replacing the `×N` `<select>`; live-% JS rewritten for absolute weights (non-US weights
  renormalized to fill the international slice, mirroring `ncaa.region_weights_for` /
  `juniors.generate_class`); "Reset to band" button; band change / reset re-fill the
  inputs.
- `app/web/server.py`: `/world/new` reads `w_<id>` and calls `set_region_weights`
  (US row skipped); `/start` passes `weight_scale` instead of `mult_choices`/`intro_floor`.

## Verify
```python
from app import worldconfig as wc
wc.set_region_weights({"europe_western":160,"canada":40,"africa":60,"latin_america":60})
assert "us" not in wc.region_weights() and wc.region_weights()["africa"] == 60
wc.set_region_weights({})           # cleared -> band fallback
assert "canada" in wc.region_weights()
```
End-to-end (the capability that was impossible before): with `generate_class`,
an `africa`-heavy authored mix yields **~74%** African recruits in the international
pool vs **~0%** for a Euro-core mix. Tests green: `test_world_single_gender`,
`test_web_recruiting`, `test_name_regions`, `test_regions`, `test_world_model`.

## Note
This is the world-level mix only. Per-league / saveable named mixes were explicitly
deferred (owner chose "world mix as today").
