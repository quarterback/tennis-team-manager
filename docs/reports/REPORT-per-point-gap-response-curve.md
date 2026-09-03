# The gap-response curve goes per-point

**What changed:** the OVR-gap slope table moves from twelve 3-wide bands to a
per-point array indexed by integer gap, and the shape inside it changes — a softer
peer band, a much steeper 3-15 region, and a plateau from gap 22 instead of a slope
that kept climbing to the top of the scale.

**Why now:** the 2067 → 2068 diffusion change worked, and the measurement of it showed
exactly where the remaining slack was. This is the follow-on, tuned against the same
match-level data.

---

## 1. What the previous change established

The 2068 curve was measured against 2067 on real match exports, per OVR-gap band. The
result: the peer band did not move, and everything above 13 points stiffened.

| OVR gap | Favorite win 2067 → 2068 | Three-set 2067 → 2068 |
|---|---|---|
| 0-3 | 53.7% → 53.9% | 48.9% → 48.9% |
| 13-15 | 77.0% → **79.6%** | 40.0% → 38.5% |
| 16-18 | 82.4% → **84.3%** | 37.0% → **33.7%** |
| 25-27 | 93.5% → **96.2%** | 22.6% → **18.4%** |

(boys; girls tracked the same pattern, in places more strongly)

The three-set collapse was the more convincing half: a monotone 3-4 point drop across
every band from 16 up, in both genders, is a structural change in how matches resolve
rather than sampling noise in who wins them.

**‼️ The aggregate page could not see any of this.** Most matches sit in the low-gap
bands, so a change conditional on gap gets averaged into invisibility in a statewide
histogram. The conditional view is the only one that can answer a conditional question —
the same lesson the scoreline-realism page taught when its 6-0 rate turned out to be
talent architecture rather than a calibration fault.

## 2. What is still slack

Measured on the 2068 export (boys, n per gap in the table below), the observed curve
through the single digits is nearly flat where it should be climbing:

| gap | n | observed favorite win |
|---|---:|---|
| 1 | 5,025 | 52.3% |
| 3 | 4,604 | 55.1% |
| 5 | 4,178 | 61.7% |
| 7 | 3,556 | 64.6% |
| 10 | 4,845 | 70.8% |

Five points of separation buying nine points of win probability is a soft peer zone.
The intent for this pass: **1 point should feel like an advantage** — and by gap 10 a
player should be a decisive favorite, not a 71% one.

## 3. The array

```python
# Index 0 corresponds to Gap 1  ->  PER_POINT_SLOPES[gap - 1]
PER_POINT_SLOPES = [
    # Gaps 1-10: locked peer band + early acceleration
    1.05, 1.10, 1.24, 1.38, 1.57, 1.66, 1.76, 1.87, 1.99, 2.12,
    # Gaps 11-15: mid-tier cliff ramping
    2.20, 2.28, 2.36, 2.44, 2.52,
    # Gaps 16-22: heavy advantage, three-set collapse
    2.57, 2.62, 2.67, 2.72, 2.77, 2.82, 2.85,
    # Gaps 23-35+: top-end plateau / lockout ceiling
    2.85, 2.85, 2.85, 2.85, 2.85, 2.85, 2.85, 2.85, 2.85, 2.85, 2.85, 2.85, 2.85,
]
```

Cumulative, not lookup: the effect at gap *g* is the sum of every point's slope from 1
through *g*. Gaps past 35 continue at 2.85 per point.

### Four named regions

| region | gaps | slope | what it is |
|---|---|---|---|
| Locked peer | 1-2 | 1.05-1.10 | dead-heat rivalry; three-setters stay near 47% |
| Early acceleration | 3-10 | 1.24-2.12 | development gets rewarded; 65% by gap 5, ~78% by gap 10 |
| Mid-tier cliff | 11-15 | 2.20-2.52 | double digits become a real wall; past 85% |
| Heavy advantage | 16-22 | 2.57-2.85 | three-set collapse; 95%+ |
| Lockout ceiling | 23+ | 2.85 | plateau — see below |

## 4. Projected against the 2068 export

Both genders, projected by rescaling observed odds by the cumulative-effect ratio:

| gap | slope | fav win (B / G) | three-set (B / G) |
|---|---|---|---|
| 1 | 1.05 | 52.4 / 51.1% | 47.0 / 47.6% |
| 3 | 1.24 | 55.8 / 56.4% | 44.2 / 43.3% |
| 5 | 1.57 | 64.2 / 61.4% | 39.0 / 39.6% |
| 8 | 1.87 | 73.4 / 73.9% | 33.7 / 33.7% |
| 10 | 2.12 | 78.1 / 79.4% | 31.3 / 32.6% |
| 12 | 2.28 | 85.7 / 86.0% | 28.1 / 27.6% |
| 15 | 2.52 | 89.8 / 91.9% | 24.9 / 25.8% |
| 18 | 2.67 | 95.0 / 95.1% | 20.0 / 21.2% |
| 21 | 2.82 | 97.1 / 96.1% | 19.5 / 20.1% |
| 24+ | 2.85 | 97.8 / 98.2% | 15.0 / 13.1% |

Boys and girls track each other within ~2 points at every gap, so the curve behaves
symmetrically across two differently-shaped talent distributions rather than needing a
per-gender variant.

## 5. Two decisions worth recording

**Per-point gates instead of 3-wide bands.** An intermediate version kept 3-wide bands
with the same endpoints. It produced *identical* cumulative totals — the two are the same
curve. The reason to write it per-point is control: any single gap can be retuned without
restructuring a band, and a discontinuity at a band edge becomes impossible to introduce
by accident.

**The plateau at 2.85 is deliberate, not laziness.** By gap 22 the favorite already wins
97-98% and three-setters are down to ~15%. More slope there cannot meaningfully move who
wins; it can only drive the per-point win probability high enough to distort scorelines.
The ceiling caps the curve where additional steepness stops buying competitive realism
and starts buying absurd scores.

## 6. What to check in the next season's export

- **Favorite-win and three-set rate by gap**, conditional — not the aggregate histogram.
  Expect gaps 1-2 to be unchanged and gap 10 to move from ~71% to ~78%.
- **Varsity individual chalk.** In 2068 the top seed won 51% (boys) / 57% (girls) of the
  72 varsity flights, versus **100% of the four JV flights**. That gap exists because
  varsity flights pair near-peers while JV draws span a wide talent range. Under the new
  curve varsity chalk should rise, but should stay clearly below JV.
- **One-point dual rate.** 2068 ran 45-46% of duals decided by a single point and only
  ~21% at a 5+ margin. A dual aggregates seven flights, most of them near-peer, so team
  results should stay tight even as individual matches get more decisive. If one-point
  duals collapse, the curve overshot.
- **Small-class determinism.** 1A, 2A and Group 3 carry the widest internal talent
  spreads relative to their fields and will feel the mid-band change hardest. Champion
  seeds collapsing to 1-2 in those classes while the big classes stay competitive is the
  signal that the change went too far at the bottom of the ladder.
