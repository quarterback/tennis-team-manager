# AAR — doubles lineup optimization was a no-op, the league format swapped to 3S/4D, and rosters got real depth

## The report

Owner: "the game is still bad at lineup optimization... specifically in doubles."
Checked directly against the code rather than taken on faith, and the finding was
worse than "bad optimization" — it was **no optimization at all**, hiding behind
code that looked like it worked.

## Finding 1: `doubles_rating` was purely additive, so "best pairing" was mathematically undefined

```python
def doubles_rating(a, b):
    return (idx(a) + idx(b)) / 2.0
```

For any fixed group of players, the *sum* of this across every possible way you
pair them up is identical — proven algebraically (it's just `sum(idx)/2`
regardless of grouping) and confirmed empirically on 240 real rosters plus a full
15-way partition check over 6 real players: **every partition produced the exact
same total.** The postseason's own `_arrange_state` comments claim *"every
partition... best total doubles ability wins"* — that search was tied on every
candidate and silently fell through to the tiebreak. Half the league's regular-
season programs (the non-"doubles-forward" half) didn't even reach that far —
they paired doubles by raw ladder rank with no rating input at all.

**Fix**: added `engine.doubles._pair_synergy`, a bounded (`SYNERGY_CAP=0.06`)
complementarity term on top of the additive base, so partitions actually differ.

## ‼️ The fix's first version had the SAME bug in a new shape, and I didn't catch it — a review did

The first `_pair_synergy` used `max(sa,sb)+max(ra,rb)` (coverage) and
`|aa-ab|+|ca-cb|` (balance). Both look reasonable — "reward the pair's peak on
each axis," "reward spread on aggression/steadiness" — and both **discard which
player supplied which strength**. A pair where one player is great at *everything*
and the other is weak at *everything* scored identically to a pair where each
player is great at a genuinely *different* thing:

```
X: serve=0.9 return=0.9   Y: serve=0.3 return=0.3   -> coverage = 0.30  (NOT complementary)
X: serve=0.9 return=0.3   Y: serve=0.3 return=0.9   -> coverage = 0.30  (genuinely complementary)
```

Identical score, opposite meaning. Since the additive base is invariant across
partitions (finding 1), the synergy term is the *entire* thing the search
optimizes for — so this bug wasn't cosmetic, it meant `maximize` could just as
easily reward stacking a strong player with a weak one as pairing real
complements, exactly backwards from the stated design.

**The lesson**: "reward spread/peak on an axis" is a tempting shape for a
complementarity metric and it is *not* complementarity — it's just variance, and
variance doesn't know who owns which value. A real complementarity term has to be
a **cross term** between the two axes, not two independent one-axis spreads
summed together. Fixed with `-(sa-sb)*(ra-rb)`: positive only when the two
per-axis differences have *opposite sign* (different players lead on different
axes), zero when the same player leads on both (that's inequality, not
complementarity). Verified directly against both scenarios above post-fix: the
lopsided pair scores 0, the genuinely complementary pair scores the full bonus.

I should have caught this myself — both terms in the original version share the
exact same structural flaw, and "does this formula know WHO contributed WHAT" is
a checkable question I didn't ask before shipping it. It took an external review
to name it precisely. Filed here so the next complementarity-shaped metric in
this codebase gets that question asked up front.

## Finding 2 (design, not a bug): the regular-season format was backwards from what the postseason trains for

Separately from the rating fix, the owner swapped which shape the league season
plays: **regular season is now 3S/4D** (was 5S/2D), the **early non-district
window is now 5S/2D** (was 3S/4D) — a straight swap of `FORMATS['regular']` /
`FORMATS['early']`. The postseason has always been 1S/4D; playing 3S/4D all
season (not just the early window) means the league year now trains the shape
programs actually need for State, and dresses 11 of a 12-man roster every dual
instead of 9.

**The lineup allocation for that card is fixed, never searched**: S1 is always
the top seed, the doubles pool is always exactly #2-#9, S2/S3 are always exactly
#10-#11. Strategy (maximize/balanced/traditional) only decides how the *fixed*
8-player pool pairs into D1-D4 — not who plays singles vs. doubles. My first pass
at this over-engineered it: I proposed searching which of #2-#9 should play
singles too, before being corrected — "the lineup allocation rule is already
defined... do not create a combinatorial search over singles allocation." The
partition search that's actually needed is 105 combinations (8 players into 4
pairs), not the much larger space I'd started building.

## Finding 3 (design): 12-man flat rosters couldn't support the new format at all

3S/4D dressing 11 of 12 players every dual left almost no bench — an existing
test (`top plays 3x more than the bottom`) started failing because ranks #10-11
are now guaranteed starters, not reserves. This wasn't a test bug to patch around
in isolation; it was a symptom of the roster being too shallow for the format
that now runs all season. Fixed at the source, not the symptom:

- **`ROSTER_SIZE_BY_CLASS`**: roster depth now scales by classification (9A 24
  down to 1A 13), mirroring `ncaa.ROSTER_CAP`/`roster_cap` exactly rather than
  inventing a new pattern — bigger schools get real additional players at the
  SAME talent distribution as everyone else in their classification, not weaker
  filler. Modeling a varsity+JV blend, since the association has no separate JV
  system to represent that with.
- **Grade distribution stopped being an even ~3-per-grade split.** `build_roster`
  is a pure function of `(school, year)` with no persisted state — every call
  regenerates all four grades from formulas keyed on entry year. That
  architecture doesn't have a natural "this is year 1" vs "this is year 5" event
  to branch on, so instead of adding one, the randomness was pushed into the
  right PRIMITIVE: `_freshman_class_size(school, entry_year, classification)` is
  rolled ONCE per `(school, entry_year)`, and grades 10-12 in any viewing year
  simply reuse THEIR OWN entry year's roll, aged forward unchanged. That one
  change produces both halves of what was asked without a branch: year 1's
  snapshot mixes four independently-rolled entry years (a naturally random class
  mix), while every later year's growth comes entirely from that year's own
  freshman roll — verified directly, 2027's grade-9/10/11 sizes reappear
  unchanged as 2028's grade-10/11/12. No non-freshman players are procedurally
  generated at all, on purpose — a real sophomore/junior arrival is meant to be
  a TRANSFER (scaled from the college game's portal), a separate future
  mechanic, not a generation roll dressed up as one.
- After the roster widened, the failing bench-depth test passed with no
  threshold retuning — it was genuinely a depth problem, not a test-tuning one.

## What to check first if this resurfaces

- **A "best pairing" search that never seems to change anything**: check whether
  the rating function it's optimizing is additive across the two players with no
  cross term. If `f(a,b) = g(a)+g(b)`, the sum over ANY partition of a fixed pool
  is invariant, and every search built on it is silently a no-op. This exact bug
  hit `doubles_rating` once already; watch for the same shape anywhere else a
  "pair rating" gets introduced (compatibility scores, chemistry systems, etc.).
- **A complementarity/synergy term that "looks right"**: explicitly test it
  against a lopsided pair (one player strong at both relevant axes, partner weak
  at both) versus a genuinely complementary pair (each strong at a different
  axis) with the SAME total ability. If they score the same, the formula is
  measuring variance, not complementarity — it needs a cross term
  (`-(a1-a2)*(b1-b2)`-shaped), not two independent spreads summed.
- **JHSAA roster/lineup counts look wrong for a classification**: `roster_size`
  and `_freshman_class_size` both take `classification` as an explicit parameter,
  not something inferred from a School object internally — if a school's
  displayed roster doesn't match its classification's target, check what
  classification was actually passed in (play-up moves `group`, not
  `classification` — see the play-up rules elsewhere in this file).

## Follow-up (owner correction, same day): the pairing search itself was the bug

This shipped `maximize`/`balanced` as an exhaustive search — score all 105 ways
to split the 8-player doubles pool, keep the best — which was a reasonable cost
when only the early non-district window played 3S/4D (a handful of duals per
team). The format swap above puts 3S/4D on EVERY regular-season dual instead,
for ~1,600 JHSAA programs playing ~26 duals each. Nobody re-costed the search
against its new call volume: the first world advance after this landed ran for
7+ minutes and counting instead of the usual ~60s, and it wasn't a bug in the
search — it finished, correctly, it was just doing 105-way scoring roughly
30,000+ times a season across the association.

Measured directly (a ~35%-of-association slice, both strategies exercised):
forcing the cheap `traditional` branch alone — no other change — cut the
slice's wall time in half. `doubles_rating` itself profiled at ~19µs/call, so
420 calls (105 partitions × 4 pairs) per lineup decision, twice a dual, was the
entire story.

The first fix attempted was a per-team memo cache (player ability is constant
for a `TeamSeason`'s whole life, so the same 8-identity pool under the same
strategy always resolves to the same pairing — a legitimate, behavior-preserving
optimization). It worked, but the owner's correction cut deeper than "make the
search cheaper to repeat": **the search should not exist at all**. Direct quote:
"it needs to not do that you can just cheaply decide on the fly, it doesn't
need to run permutations like that... just make a decision it doesn't have to
be optimal, real life isn't optimal." Two things made this the right call, not
just an available one:

- `doubles_rating`'s own synergy term is capped tiny by design (`SYNERGY_CAP`
  in `engine/doubles.py`, "well below individual-talent spread") specifically
  so pairing choice stays a minor factor. A 105-way exhaustive search was
  spending real per-dual compute, at world-advance scale, to optimize a term
  the engine deliberately keeps small.
- This codebase already has a standing precedent for exactly this trade
  (`showcase_schedule`'s group dealing, "GROUPS ARE SHUFFLED AND DEALT —
  SIMPLER MATCHING BEATS PRECISE MATCHING HERE," owner rule 2026-08): where a
  choice's precision doesn't materially change the outcome, a cheap direct
  decision beats a search for the same reason it did there.

`_arrange_regular` now makes one direct, ability-ordered decision per strategy
instead of searching: `maximize` snake-pairs the pool by serve-minus-return
skew (best server with best returner, and so on down); `balanced` snake-pairs
by overall ability (strongest with weakest). Both still call `doubles_rating`
exactly 4 times per lineup — to order the four pairs onto the card, strongest
plays D1 — never to search. `traditional` (already a fixed adjacent pairing)
and `_arrange_state`'s postseason search (15 partitions over a small qualifying
field, never the cost driver here) are untouched.

**What to check first if this resurfaces**: a search or optimization loop whose
input pool scales with a format/schedule change should be re-costed against the
NEW call volume, not just validated for correctness at the old one — a change
can alter a function's cost class while leaving its signature identical (the
same lesson CLAUDE.md's `plays_up()` fingerprint-query-storm entry names for a
memoized DB read; this is the same shape one level up, for a CPU-bound search
instead of a DB round trip). And before reaching for a cache to make an
expensive computation cheaper to repeat, ask whether the computation needs to
happen at all — capped-impact objectives (like `SYNERGY_CAP` here) are a signal
that a direct decision was always going to be good enough.
