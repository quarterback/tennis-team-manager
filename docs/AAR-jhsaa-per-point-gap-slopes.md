# AAR — the JHSAA gap-response curve becomes a per-point slope array (2026-09)

**Owner spec (2026-09):** replace the banded slope table (`BAND_EDGES_OVR` /
`BAND_SLOPES`, 3-wide bands accumulating width × slope per band) with a
**per-point array indexed by integer OVR gap**, cumulative, with linear
interpolation for fractional gaps and a plateau at 2.85 a point past 35.
Nothing else moves: not how the gap is computed, not which number the engine
reads, not the point/game/set/match simulation, not the formats, not how a
doubles pair is reduced to one side rating.

## What changed, exactly

`engine.fast.PER_POINT_SLOPES` — 35 marginal slopes, index 0 = gap 1.
`get_effective_delta(gap)` is the cumulative effective delta in OVR points
(Paradigm A, incremental summation): `sum(PER_POINT_SLOPES[:g])`, linearly
interpolated inside a point (a 4.5 gap is four full points plus half of the
gap-5 slope), continuing at `PLATEAU_SLOPE` (2.85) beyond the array — the
per-point RATE plateaus, the cumulative total is never clamped, and there is no
`IndexError` at any gap. Gap 0 contributes nothing.

`band_gap(unit_gap)` keeps its historical name as the one entry point
`effective_gap(..., bands=True)` routes to under `HS_PROFILE`, and now reads
`get_effective_delta(|gap| × 60) / 60`, sign-symmetric. `_hold_prob`, `_tb_prob`
and `engine.doubles._fast_gap` are untouched: they still hand a unit gap in and
multiply what comes back by their own slope inside the per-game logistic.

Checkpoints the array produces (pinned in `tests/test_jhsaa_scorelines.py`):

| gap | cumulative delta |
|---:|---:|
| 1 | 1.05 |
| 3 | 3.39 |
| 5 | 6.34 |
| 10 | 15.74 |
| 15 | 27.54 |
| 22 | 46.56 |
| 30 | **69.36** |

The owner's checkpoint sheet said 69.38 at 30; the array sums to 69.36
(46.56 at 22 plus eight points at 2.85). The array is authoritative, the sheet
had a two-hundredths arithmetic slip, and the test pins what the array does.

## ‼️ The peer band is deliberately soft

Gaps 1–2 sit at 1.05 / 1.10. Close matches staying close is the intent, not an
artifact — do not "fix" the bottom of the array to make small favourites win
more. What the curve buys is above it: a ramp through 10, a mid-tier cliff at
11–15, the heavy advantage at 16–22 (the three-set collapse), and a lockout
plateau from 23.

## ‼️ The win-rate column is a MEASUREMENT, not a setting

The owner's sheet carried target favourite win rates beside the deltas (1 →
52.3%, 3 → 57.5%, 5 → 64.5%, 10 → 80.0%, 15 → 90.2%, 30 → 99.1%). Those are
what the table PRODUCES once `skill_slope` (0.9), `tb_slope` (0.68) and ~20
games of logistic compounding are applied — the table does not set them, so
they are reported, not asserted to the decimal. `scripts/jhsaa_band_calibration.py`
(now a describe-only tool: nothing is fitted or installed) prints the marginal
slope, the cumulative delta, the implied hold % and the measured win / three-set
rates at every integer gap; run it after any change to the array or the dials.
The measured values at the time of this change are recorded in
`tests/test_jhsaa_scorelines.py::test_simulation_plays_on_the_per_point_curve`
with sampling headroom, and the table's `band_gap` docstring points here.

## Where it shows up

The by-OVR-gap-band panel on `/jhsaa/realism` (this season vs last, favourite
win % and set decisiveness per band) is where this lands in the owner's own
data: the 0–6 band should barely move between the last season on the banded
table and the first on this array, and the 15+ bands should turn more
favourite wins and more lopsided sets. `world.OVR_GAP_BANDS` (the five display
bands there) is unrelated to this table.

## Superseded

`docs/AAR-jhsaa-band-recalibration.md` describes the banded table and the
solver that fitted it; both are gone. Its lessons about reading the code path
before tuning a dial, and evaluating the transform rather than eyeballing the
tuple, carry straight over.
