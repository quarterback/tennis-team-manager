# AAR: Talent ceiling compression — the top of the game, 15-20% down

**Landed:** 2026-08 (owner rule). **Where:** `app/development.py`
(`compress_talent` / `trim_prospect_ceiling` / `elite_talent`), wired at all
three generation feeds; era-gated in the JHSAA (`jhsaa.talent_era()`).
**Measured by:** `scripts/talent_compression_calibration.py`.

## The problem

The universe was tuned when it held 100-200 schools. At ~850 JHSAA programs
plus a 2,500/gender/year national pool, the SAME distributions buy five times
the lottery tickets, so the tail piled onto the 80 clamp: measured on the
full association, **5,573 boys' / 7,103 girls' ceilings sat above the new
cap**, best seniors played at UTR 15+, and players were "maxing out my
college scales, which was never supposed to happen". Owner: the ceiling
should come down 15-20% — ordinary talent topping out around **UTR 12-13
(boys) / 10-11 (girls) as a ceiling**, with a rare elite still reaching where
today's elite sit. The distribution never changed; the number of draws did.
That is the diagnosis to remember: **a tuned tail is a statement about N.**

## The mechanism — two halves, one exemption

- **Shape** (`compress_talent`): the drawn talent is squashed above a knee
  (tanh, identity below, monotonic throughout — every ordering survives), so
  the top of the range compresses instead of translating. Anchors, in the
  20-80 ⇄ STR 31-57 ⇄ UTR 1-16.5 chain: boys knee UTR 10 → cap UTR 13; girls
  knee UTR 8.5 → cap UTR 11.
- **Guarantee** (`trim_prospect_ceiling`): `ceiling_overall()` sits a
  measured **median +6 / p90 +7 / max +16 ABOVE the talent passed to
  `generate_prospect`** (attribute potentials scatter around it and playstyle
  shaping spikes signature attributes). A squashed centre alone therefore
  still leaked ~500-950 over-cap ceilings per gender. After generation the
  overshoot is subtracted uniformly from every attribute potential (never
  below the attribute's current value), landing on a deterministic spread
  over [cap-2, cap] — NOT one number, because a wall of identical maxed
  ceilings is exactly the artefact this rule removes.
  ‼️ The squash also aims `_ATTR_LIFT` (7.0) below the displayed targets for
  the same reason. **If you retune the caps, retune them in DISPLAYED terms
  and let `_ATTR_LIFT` translate — and re-measure the lift if attribute
  generation changes**, or the anchors silently drift by the lift.
- **The elite exemption** (`elite_talent`): **1 in 500**, rolled on blake2s
  off the player's stable identity — never `hash()` (process-salted), never
  the main rng (an extra draw would regenerate everyone; the PRODIGY stream's
  lesson). An elite key skips both halves and keeps the old sky. The same key
  answers the same way forever, so an elite kid is elite all four years.
  Measured: **36 boys / 33 girls elites** live in the association at once —
  a couple per class per gender, the "one transcendent kid per era" texture.

## ‼️ Era-gated in the JHSAA — the one hard rule

JHSAA players regenerate deterministically, so an un-gated change to the
talent draw rewrites every archived roster's attributes and re-orders every
archived ladder silently. `talent_era()` is the `dev_era()` idiom exactly
(worldconfig key `jhsaa_talent_era`, self-configured to newest archive + 2,
memoised, cleared by `reset_schools()`): cohorts ENTERING at or after the era
are compressed, everyone earlier keeps their numbers byte-for-byte. Both
halves are transforms on already-drawn values with the elite roll on its own
keyed stream, so **the main rng consumes identical draws either side of the
gate** — pre-era players cannot shift.

Consequences, decided knowingly (owner, 2026-08):
- The association converges over one four-year graduating cycle; for those
  seasons the seniors are stronger than the freshmen BY DESIGN — a golden
  age aging out, and downstream (college, pros, if ever resumed) a hot
  generation rides above a cooler one for ~8 years. Owner: "who cares."
- The pinned talent-shape claims (class ladder inside each tag, smaller =
  thinner + wider) survive — compression is monotonic per draw — but the
  measured top-end gaps shrink. (Three `test_jhsaa_talent_shape` assertions
  were already failing before this change: they walk `GROUPS` as one ladder,
  the exact trap the GB-groups note in that table documents. Not fixed here.)

## Cross-source consistency

Three feeds generate talent and all three now share one ceiling law — no
feed runs hotter than the others:

1. **JHSAA** `_gen_seat` (era-gated, key `("jhsaa-elite", ident, gender,
   entry, seat)` — pid identity, so a transfer stays the same person).
2. **National recruit pool** `juniors.generate_class` (key on the pid's own
   `("recruit", grad_year, gender, i)` identity). Un-gated: recruits are
   generated per class year and no college save is live (owner: JHSAA-only
   save, "there's nothing to break").
3. **College year-0 base rosters** `ncaa` build — applied at the ONE point
   both talent paths (star-plan `tier_grade` and the gauss around the
   program mean) flow through. Un-gated, same reason. The `ncaa._TALENT`
   annotation "elite D1 #1s land ~UTR 13-14" now reads ~UTR 12-13 with the
   rare elite above; the bands themselves were not retuned.

`generate_prospect`'s `nation_talent.talent_shift` applies AFTER the squash
(inside the generator) — a small per-nation nudge past the cap for boosted
markets; the trim catches what matters.

## ‼️ Every BAR compared against a player must compress too

The first full signing-cycle run after wiring the feeds dropped the
"essentially everyone signs" rate 95→93%: the division radar's program level
(`level_cal`) was still derived from the RAW strength→talent formula, so
compressed recruits were measured against uncompressed floors and the bottom
of every board went unsigned. The general rule: **a threshold lives on the
same scale as the thing it gates** — compress one side and every comparison
against it moves. Fixed by routing all such bars through the same law:

- `ncaa.program_level_caliber` — the ONE builder for the radar's `level_cal`
  (production `world._decide_market` and the signing tests both use it).
- `world._prog_level` and `league._program_level` — the fall-portal /
  transfer-up bars; uncompressed they would sit above every eligible riser
  and quietly dry the portal up.
- `league.py`'s standalone freshman intake turned out to be a FOURTH
  generation feed and is wired like the other three.

`ncaa._talent_mean` itself stays RAW — rosters compress at the draw, and
compressing the mean too would double-compress them. If a new comparison
against player ability is ever added, it goes through `compress_talent`
(no key — bars have no elite roll).

## Measured (full association + a 2,500 pool, deterministic census)

| | legacy | compressed |
|---|---|---|
| Boys top-100 ceiling | 78.9 (UTR 16.2) | **67.7 (UTR 13.3)** |
| Boys over-cap ceilings | 5,573 | **56** |
| Boys best senior (current) | 76.0 (UTR 15.5) | 72.0 (UTR 14.4, an elite) |
| Boys senior top-100 current | 73.2 (UTR 14.7) | **64.1 (UTR 12.4)** |
| Girls top-100 ceiling | 78.4 (UTR 16.1) | **63.6 (UTR 12.3, elites incl.)** |
| Girls over-cap ceilings | 7,103 | **139** |
| Girls senior top-100 current | 72.3 (UTR 14.5) | **60.2 (UTR 11.4)** |
| Pool 5★ by absolute grade (m/f) | 77 / 78 | 9 / 6 |

The recruit BOARD's stars are rank-based (`tier_for_rank`), so the board
looks the same; the absolute `star_rating()` thresholds (5★ = grade ≥ 62)
now mean what they say. Elite tops (78-79 ceiling) sit exactly where the
legacy elite sat — the owner's anchor.

## What did NOT change

TOSS (opponent-relative), awards (record-based), ladders (orderings),
`_TALENT` bands at every source (the compression is a transform after the
draw, so the class structure and archetype behaviour underneath are
untouched), scholarship/budget economy, and every pre-era JHSAA cohort.

## Traps for the next agent

- **Do not "fix" the compression back** because a test or an old annotation
  expects UTR 14-15 college tops — this rule is the owner lowering that
  anchor deliberately.
- **A cost/shape figure that decided something must be re-measured when its
  input changes** (`_ATTR_LIFT` — re-run the calibration script's probe if
  attribute or playstyle generation is touched).
- The elite rate is per SEAT at the college base build and per RECRUIT in
  the pool — a program cannot bank elites; do not key it on anything that
  varies season to season or elite status will flicker.
- `tests/test_talent_compression.py` pins: identity below the knee,
  monotonic + capped squash, elite exemption + ~1/500 rate, gender-label
  normalisation, the JHSAA era gate (same pids either era, squash real,
  non-elite ceilings bounded), and the compressed pool.
