# Calibration brief: tennis rating distributions & trajectories (for STR tuning)

Purpose: calibrate the simulator's synthetic rating **STR** (UTR-style, 1.0–16.5,
opponent-relative). Numbers-first. STR is meant to behave like UTR, so all
mappings below are stated in UTR points and translate 1:1 to STR.

Cross-cutting fact to bake in everywhere: **UTR is logistic, not linear.** A
1.0-point gap ≈ the higher player wins ~75–85% of the time; >1.0 point and the
lower player upsets only ~3% of the time; <1.0 point apart you get a competitive
match 2–3x as often. So a 0.3 STR gap is meaningful and a 1.0 gap is near-decisive.
(utrsports.net "how UTR works"; support.universaltennis.com algorithm summary.)

---

## 1. UTR scale & distribution by level

Scale is 1.00–16.50, age/gender/nationality-neutral, computed from last ~30
matches in 12 months.

**Pro top end (men), live snapshot 06/2026 (sofascore UTR-men):**

| Rank | Player | UTR |
| --- | --- | --- |
| #1 | Sinner | 16.39 |
| #10 | F. Cerundolo | 15.73 |
| #25 | Learner Tien | 15.56 |
| #50 | Norrie | 15.35 |
| #100 / #150 | (Brooksby / O'Connell) | ~15.0–15.2 (est.) |

Year-end 2025 peak men were Sinner 16.48 / Alcaraz 16.41. Women top out ~13.0–13.5.

**The razor-thin-top claim — confirmed and quantified:**
- #1 → #10 ≈ **0.66 UTR**
- #1 → #25 ≈ **0.83 UTR**
- #1 → #50 ≈ **1.04 UTR**
- i.e. ~50 of the best men on Earth fit inside **~1.0 UTR point**, and the entire
  Top ~150 sits in roughly **15.0–16.5 (a ~1.5 band)**.
- Average gap per rank near the top: ~0.07/rank (#1–10), falling to ~0.01/rank by
  #50. Margins compress hard at the elite end; one bad-luck point swings rank order.

**College & junior bands (UTR; utrsports.net college data-dive, NCSA, recruiting guides):**

| Level | Men UTR | Women UTR |
| --- | --- | --- |
| Top-25 D1 (Stanford/OSU/UCLA tier) | 13–14+ (often ITF/ATP-ranked) | 11.5–13 |
| Mid-major D1 | 11.5–13 | 10–11.5 |
| Low-major D1 / top D2 | 10.5–11.5 | 9–10 |
| D2 (general) | 5–13 (core 10–12) | 2–10 (core 8–10) |
| D3 / NAIA | 7–10.5 (top to 12) | 4–9 |
| Blue-chip junior (recruit-grade) | 12–14 | 11–13 |
| 3-star junior | ~9.5–11.5 | ~8–10 |

Distribution: across all divisions ~56% of college **men** sit UTR 3–10 and ~60% of
college **women** sit UTR 2–7 — the population is bottom-heavy; elite is a thin tail.

---

## 2. "Not all 12 UTRs are equal" — junior band width

- TennisRecruiting.net ranks ~16,000 boys (and ~16,000 girls) per year out of
  ~34,000 active junior competitors per gender. Thousands of juniors share any
  single integer UTR band.
- A static UTR is a **snapshot of current skill, not potential**. UTR explicitly
  does not adjust for age, so a 14-yo and a 30-yo at the same UTR are *not* the same
  prospect — the 14-yo has room, the adult is at ceiling.
- Outcome spread within one junior band is very wide: among the **top 25 12U boys,
  13 of 25 showed a UTR-vs-ranking mismatch** — i.e. shared/adjacent UTR maps to
  very different competitive standing. The 30-match window adds noise at junior
  level.
- Separating signals (who keeps rising vs plateaus): **(a) age relative to band**
  (younger-in-band = higher ceiling), **(b) trajectory/slope** — a player flat at
  10.5 since 8th grade reads as ceiling-reached; same number rising reads as live,
  **(c) results vs top competition** not just rating, **(d) physical maturity** —
  early physical maturity inflates junior UTR then plateaus ~U16 "when competition
  outpaces development," **(e) recruiting rank/star tier**.

Density rule of thumb: junior population is densest around UTR ~7–11; a single UTR
point in that range holds on the order of 10^3 ranked juniors per gender per band.

---

## 3. Development trajectories (age 16 → college → 22)

- General curve: UTR rises with size/strength/skill through late teens, typically
  flattening in early-mid 20s. Trajectory > absolute number for projection.
- **Early bloomers:** high junior UTR driven by early physical maturity; tend to
  **plateau ~U16–U18** as peers catch up. Net 16→22 gain often small (~+0.5 to +1.5).
- **Late bloomers:** modest junior UTR (e.g. 9–10 at 16), big gains in college from
  full-time training + match volume; can add **+2 to +3.5** over the same window.
- Realistic magnitudes 16→22:
  - Recruit-grade prospect at 16 (UTR ~11–13): typically **+1 to +2.5** to a college
    plateau around 12.5–14.
  - Mid junior at 16 (UTR ~9–10): **+1.5 to +3** is plausible with development;
    occasional +3.5 outliers.
  - Top D1 entrants gain little after arrival (already near ceiling); recruiting
    sources note 17→18 "the same ranges apply," focus shifts to fit not UTR jumps.
- Age benchmarks (boys / girls, D1-track, from ncaascholarshipguide):
  end-G9 ~9+/8+; G10 mid-major ~11+/9.5+; G11 top-25 ~13+/11.5+, mid-major ~11.5–13/10–11.5.

---

## 4. Transfer pathway (model this as "transfer up")

- No tennis-specific public rate exists; use NCAA all-sport DI baseline: in 2023,
  **23,021 DI athletes entered the portal ≈ 12% of ~190,000 DI athletes**; **~57%
  of enterers actually transferred** (8% stayed, 35% stayed active/unplaced).
  → effective transfer-out rate ≈ **12% × 57% ≈ 6.5–7% of DI athletes/yr**.
- Tennis is widely understood to run **above** the all-sport average for movement
  (small rosters, heavy international presence, unlimited transfers since 2024,
  one-line lineup churn). Treat ~8–12%/yr as a reasonable tennis "any move" rate.
- "Transfer **up**" (low-major/D2/D3/NAIA → higher) is a real, recurring pathway
  driven by: measurable **UTR gains** in 1–2 college seasons (a player who jumps
  ~+1 UTR becomes recruitable a tier higher), strong dual-match results/lineup
  position, and roster/scholarship openings created by graduating uppers. Net upward
  flow is a minority of all transfers (lateral and down also common) but is the
  storyline worth modeling.

---

## 5. Recruiting star distribution (per graduating class, TennisRecruiting.net)

Tiers are **count-based per class** (boys; girls ~symmetric):

| Tier | Rank range in class | Count |
| --- | --- | --- |
| Blue Chip | 1–25 | 25 |
| 5-star | 26–75 | 50 |
| 4-star | 76–200 | 125 |
| 3-star | 201–400 | 200 |
| 2-star | 401 → %-of-class cutoff | few hundred |
| 1-star | any qualifying rank | remainder of ranked pool |

- ~16,000 boys ranked/yr; a class is a slice of that. The starred (recruit-grade)
  pool is roughly the **top ~400–600 per class** = Blue/5/4/3 star ≈ **400** named
  recruit-grade prospects; everyone else is 2-/1-star or unranked.
- So per class: Blue Chip ≈ **top 0.1–0.2%** of active juniors, 4-star-and-up ≈ top
  ~1%, the vast majority **unrated**.

---

## Sim calibration recommendations (drop-in constants)

**STR level bands (set roster/team generation to sample from these):**
```
STR_BANDS_MEN = {
  "pro_top150":   (15.0, 16.5),
  "d1_top25":     (13.0, 14.5),
  "d1_midmajor":  (11.5, 13.0),
  "d1_lowmajor":  (10.5, 11.7),
  "d2":           (9.5, 12.0),
  "d3_naia":      (7.5, 10.5),
}
# women: shift each band down ~1.5–2.5 STR (e.g. d1_top25 = 11.5–13.0).
```

**Top-end thinness (most important):** compress STR gaps as STR rises. Target the
real curve: ~0.07 STR/rank near #1, ~0.01 STR/rank by #50, so the whole elite tier
lives in ~1.0–1.5 STR. Implement as a nonlinear rank→STR map, e.g.
`STR = 16.45 - 0.30*ln(rank)` (gives #1≈16.45, #10≈15.76, #50≈15.28, #150≈14.95) —
matches the snapshot within ~0.1. Do **not** spread the top 150 over more than ~1.5 STR.

**Win model:** logistic in STR diff. Calibrate to: diff 0 → 50%, diff 0.5 → ~70%,
diff 1.0 → ~80–85%, diff 2.0 → ~97%. (Scale `k ≈ 1.5–1.8` in `p = 1/(1+e^(-k*Δ))`.)

**Junior band variance ("not all 12s equal"):** give every junior a hidden
`potential_STR` separate from `current_STR`. Within one integer band, set the
spread of eventual peak to **±1.5–2.0 STR** (wide). Weight a junior's projected
slope by: age-in-band (younger = higher), recent slope sign, results-vs-top flag,
and a physical-maturity factor (early-maturity → higher current, lower remaining
upside / earlier plateau).

**Development curve (16→peak):**
- early bloomer: +0.5 to +1.5, plateau by ~18–19.
- typical: +1.0 to +2.5, plateau ~21–22.
- late bloomer (rare tail, ~10–15% of prospects): +2.5 to +3.5, plateau ~22–23.
Model as a logistic growth toward `potential_STR` with per-archetype rate + plateau age.

**Transfer-up feature:** each off-season, flag a player as a transfer-up candidate
if their season STR gain ≥ ~+0.8 and they outperform their current level band.
Set base annual "any transfer" probability ≈ **8–10%** per player; of transfers,
~**25–35% move up** a tier, rest lateral/down. Gate upward moves on an open slot at
the destination band.

**Star-tier proportions (per recruiting class of N ranked juniors):**
```
BlueChip = 25   (~top 0.15%)
FiveStar = 50
FourStar = 125
ThreeStar= 200          # ~400 named recruit-grade total
TwoStar  = ~3–5% of class
OneStar  = remainder
Unrated  = large majority of the junior population
```
Map star tier → starting `current_STR` band (Blue 12–14M, 5★ 11.5–13, 4★ 10.5–12,
3★ 9.5–11.5) **and** a `potential` multiplier so a 3-star can occasionally
out-develop a blue-chip (drives the transfer-up and late-bloomer stories).

---

## Sources
- UTR scale / win-prob math: https://www.utrsports.net/pages/how-utr-works ; https://support.universaltennis.com/en/support/solutions/articles/9000151830-understanding-the-algorithm-complete-summary ; https://en.wikipedia.org/wiki/Universal_Tennis_Rating
- Pro top-end UTRs (live): https://www.sofascore.com/tennis/rankings/utr-men ; year-end 2025: https://www.utrsports.net/blogs/news/utr-rating-top-10-mens-tennis-players-djokovic
- College UTR ranges & distribution: https://www.utrsports.net/blogs/news/data-deep-dive-range-of-utrs-in-college-tennis ; https://www.ncsasports.org/mens-tennis/ratings-recruiting-guidelines ; https://www.highaltitudetennis.com/single-post/is-your-utr-high-enough-to-play-college-tennis
- Age-by-age UTR benchmarks: https://www.ncaascholarshipguide.com/blog/utr-score-needed-by-age-college-tennis
- Junior band noise / 12U mismatch: https://juniortennisusa.substack.com/p/utr-can-be-right-but-its-wrong-for ; https://www.tenniswhisperer.com/2024/10/08/why-utr-ratings-hinder-junior-tennis-development/
- Physical maturity / plateau: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10564138/ ; https://thesportjournal.org/article/ability-for-tennis-specific-variables-and-agility-for-determining-the-universal-tennis-ranking-utr/
- Star-rating tiers & junior counts: https://www.tennisrecruiting.net/about/TopProspects.asp ; https://parentingaces.com/articles/the-ins-outs-of-tennisrecruiting-net/
- Transfer portal data: https://www.ncaa.org/sports/2022/4/25/transfer-portal-data-division-i-student-athlete-transfer-trends.aspx ; https://en.wikipedia.org/wiki/NCAA_transfer_portal
