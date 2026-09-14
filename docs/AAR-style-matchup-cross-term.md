# AAR — Style matchups: the cross term (owner rule 2026-09)

## The ask

`play_style` (`counterpuncher` · `serve_first` · `balanced` · `aggressive_baseliner`
· `all_court`, a flat 1-in-5 draw at generation) measured as noise: a season-wide
style-vs-style win matrix on the research export sat in a 53-60% band with no
pattern, in both genders. The owner wanted style to matter the way
rock-paper-scissors does — specific pairs with a real, stable edge — small
relative to the rating gap, and detectable on that same matrix.

Decisions taken on the way (all owner's): the effect flows through
**attributes, not the label**; it reaches **every league**; a favoured matchup
lands **~56/44 at equal rating** and fades with the gap; the JHSAA side is
**era-gated**; doubles reads it too. The tournament, after the owner flipped one
edge and closed the cycle:

| beats → | aggressive_baseliner | all_court | serve_first | counterpuncher |
|---|---|---|---|---|
| counterpuncher | **yes** | no | **yes** | – |
| aggressive_baseliner | – | **yes** | no | no |
| all_court | no | – | **yes** | **yes** |
| serve_first | **yes** | no | – | no |

`balanced` is neutral against everyone.

## What the engine actually did before

There WAS a shape hook. `development._apply_style_profile` shifts attribute
clusters by style (weight-normalised, overall preserved) and the fast model's
`_edges` plays serve-vs-return and rally-vs-rally composites, written so that
"what changes is WHO a given shape works against". Measured at equal overall
through the shipped model, every cell of the 5×5 sat at 47-52% under both the
college dials and the HS profile.

**It could not have worked, at any magnitude.** The lanes are linear. Averaged
over the two players' service games, A's edge over B collapses to

    edge(A,B) = 0.22·[(serve+ret)_A − (serve+ret)_B] + 0.32·(rally_A − rally_B)

a per-player scalar minus the same scalar for B — a transitive ranking. No
cluster shift can make A > B > C > A out of that; "amplify the attribute hook"
(the first route chosen) would only have made some styles stronger overall. It
is the fault `engine.doubles._pair_synergy` already documents from the other
side: a complementarity effect must be a CROSS term, never two per-player
spreads summed.

## What shipped

- **A style plane.** `engine.fast.style_vector(p)` maps a player's five
  attribute-cluster DEVIATIONS (cluster mean minus the mean of all five, off the
  rich table) onto two fitted axes (`STYLE_AXIS_X/Y`). A flat player is at the
  origin; synthetic `random_player`s carry no rich table and sit there too, so
  every pre-existing engine test and calibration is byte-identical.
- **An antisymmetric cross term.** `style_edge` = `k · w · (y_a·x_b − x_a·y_b)`,
  where `w` fades linearly to 0 as |Δoverall| reaches `style_fade` (0.15 units,
  ~9 OVR). Antisymmetric ⇒ zero-sum inside a match and zero-mean over a league;
  the rating gap is untouched and a 40 never beats a 95 on style. On the plane a
  style beats every style within a half-turn behind it, which is exactly the
  tournament once the four shaped styles sit at 0° / 90° / 240° / 300°.
- **Wired into BOTH fidelities.** The fast model adds it to the hold and
  tiebreak gaps (`TUNE["style_k"]`, `HS_PROFILE["style_k"]`; doubles through
  `d_style_k` on the pair-mean vector). ‼️ The college season runs the POINT
  ENGINE by default (`worldconfig.match_fidelity` → "full"), so the fast-model
  wiring alone would have left college untouched: `rally._server_rally_win_prob`
  adds it to the neutral-rally logit (`rally.TUNE["style_k"]`) and
  `doubles._play_point` to the net-exchange logit (`doubles.TUNE["style_k"]`),
  on their own dials because a per-POINT edge compounds 4-6× a game.
- **A v2 shift table** (`development._STYLE_BIAS_V2`, `generate_prospect(shape=)`)
  — roughly twice the legacy shifts, so the LABEL predicts where a player lands
  against the ±1.2 per-cluster jitter and the 18% net-specialist roll. Still
  weight-normalised: overall is preserved to the clamp (pinned).
- **Era gate** — `jhsaa.style_era()` (the `dev_era` idiom, in `ERA_SETTINGS`):
  JHSAA cohorts regenerate from seed, so pre-era cohorts keep the v1 table
  byte-for-byte (pinned). College and pro rosters are PERSISTED (`world_roster`),
  so there only players generated from now on carry v2; no gate needed.
- `scripts/style_matchup_calibration.py` — the matrix at equal overall through
  the shipped functions (`--fidelity full` for the point engine, `--doubles`,
  `--k` to try a dial, `--solve` to re-fit the axes), and
  `tests/test_style_matchups.py`.

## Lessons

1. **A flipped edge is a geometry problem.** "Counterpuncher beats serve-first"
   plus "aggressive baseliner beats all-court" put the two natural OPPOSITE
   pairs (return-vs-serve, ground-vs-net) head to head. Two opposites are
   neutral on any plane, so a table whose four vectors spanned only those two
   directions could not realise the tournament at all — the ridge fit collapsed
   CP onto AC and SF onto AB. The shipped table separates the four styles across
   serve / return / baseline / movement so the vectors are well conditioned, and
   the axes are FITTED (least squares, bounded weights), not semantic. Re-solve
   whenever a row moves.
2. **Fit on REALISED positions, not the shift table.** Per-attribute talent
   noise, the weight normalisation and the net-specialist roll all move where a
   label's players actually land; a fit on the raw table drifted serve_first 25°
   and shrank the baseliner's radius by a third.
3. **"Overall is preserved" is a statement about the GRADE, not about strength.**
   The point engine prices net play only in doubles, so a big net+/net− trade
   is a free singles upgrade for the net− styles: a draft with net −9 on the
   baseliner and +9 on the all-courter measured, at ZERO cross term and equal
   overall under full fidelity, all_court 39-47% and aggressive_baseliner 55-65%
   against the field. The net trade is now ±2 and the calibration prints a
   "strength vs field" line at `--k 0` that must sit near 50 for every style —
   the cross term is meant to be the ONLY style effect.
4. **Key the calibration's seeds per cell.** Shared across cells, one lucky
   seed set moved every cell the same way and the whole matrix read +2 — a
   uniform "bias" that was correlated noise.
5. **Check which fidelity the league actually runs before calling it wired.**
   The fast model is what the JHSAA and the calibration scripts use; the college
   season runs the point engine.

## Measured (equal overall, row beats column, both ways; fast 1,800 matches a cell, point engine 600)

Dials: fast `style_k` 4.0 (HS profile 5.5), `d_style_k` 1.5 (HS 1.8); point engine
`rally.style_k` 3.0, `doubles.style_k` 1.2; `style_fade` 0.15.

| edge | fast / college | fast / HS | point engine (college season) | point engine at k=0 |
|---|---:|---:|---:|---:|
| counterpuncher > aggressive_baseliner | 59.5 | 58.8 | 55.2 | 46.5 |
| counterpuncher > serve_first | 57.8 | 56.7 | 60.8 | 49.0 |
| serve_first > aggressive_baseliner | 63.9 | 61.2 | 55.8 | 46.1 |
| all_court > counterpuncher | 63.3 | 62.8 | 54.8 | 47.2 |
| aggressive_baseliner > all_court | 54.9 | 55.4 | 60.7 | 57.6 |
| all_court > serve_first | 54.2 | 52.9 | 55.0 | 48.6 |
| same style vs itself | 49-52 | 49-52 | 50-54 | 50-54 |
| balanced vs the field | 46-54 | 46-52 | 43-53 | 47-56 |

Reading it: the four edges where the two styles sit 60-90° apart on the plane
land ~57-64; the two at 150° (`aggressive_baseliner > all_court`,
`all_court > serve_first`) are half the logit by geometry and land ~53-55.
**Uneven edges are the signature of a real plane** — six cells at one magnitude
would mean the geometry had collapsed back toward a line. The k=0 column is the
point engine's own pricing of the v2 shapes (every style's mean vs the field
48-53%); the term is what moves the cells off it. Doubles (same-style pairs,
fast): counterpuncher pair > baseliner pair 57-60%, all_court pair > serve_first
pair 49-52%; point engine: 58.8% and 64.8% — the pair MEAN halves the vectors'
separation in the fast model, and the point engine's net exchange reads it per
point, so the two fidelities sit either side of the singles figure.

**For the data side:** rerun the season-export style-vs-style matrix after a
season under this build. Expect the asymmetric, non-transitive structure above
(rows and columns complementary, edges of DIFFERENT sizes), diluted by the
rating gaps a real season carries and by the fade — not a uniform band.

## Before / after: the owner's 2083 export as the baseline

The owner's agent audited the 2083 boys+girls research bundle (played on the
PRE-change build) with rating control — expected win probability from the
grade differential, home/away, gender and flight — so the residuals below are
what style did AFTER ability is accounted for. Keep this as the "before" so
the same audit on the first season played under this build is the proof.

**Singles, before** (78,071 varsity matches): the largest controlled style edge
in the whole 5×5 was counterpuncher over all_court at **+1.6 points**; every
other cell was under one point. That is the flat matrix this AAR opens with,
confirmed on the owner's own data.

**Singles, after — what to expect:** a CYCLE, not a ranking. At equal grade
(the calibration above) the four 60-90° edges land ~57-64 and the two 150°
edges ~53-55; on a real season those shrink, because most matches carry a
grade gap and the term fades with it, and because the export mixes v1 and v2
cohorts for four years (only players entering from `style_era()` on carry the
v2 shapes; older cohorts sit closer to the origin). Expect the strong edges at
roughly +4 to +8 points controlled, the weak ones +2 to +4, rows and columns
complementary. If every off-diagonal cell shows the SAME size, the geometry
has collapsed toward a line — that is the failure signature.

**Doubles, before** (99,746 matches): a real and coherent PAIR-COMPOSITION
signal — all_court+all_court +3.1, all_court+serve_first +2.9,
serve_first+serve_first +2.9 … aggressive_baseliner+counterpuncher −3.4 — the
same in both genders. ‼️ This is NOT a matchup effect and it predates this
change: `doubles_rating` weights serve and net play, the audit's expectation
uses the overall grade, so net- and serve-heavy players carry more doubles
strength than their grade shows and ground-heavy players less. It is a
straight ranking of pair types ("these pairs are better"), and the big
pair-vs-pair cells (+6 to +7) are that ranking stacked, a good pair type
against a bad one. It is realistic (net players ARE better at doubles) and
untouched here. After the update it stays, and the new antisymmetric term
sits ON TOP of it: expect the composition ranking to persist and, within it, a
pair-vs-pair asymmetry that reverses when the sides swap.

**Program/flight residual tables:** rows of 25-35 matches have a standard
error of ~9 points, and ~900 programs × 7 flights is 6,000+ rows, so a handful
of ±25-30 outliers arise by chance. Multi-flight, same-direction cases
(Robledo 7A boys, three doubles flights +16) are the credible ones;
single-flight anomalies need a second season. The "flight | actual | expected
from grade | ± | N" table the agent proposes is worth adding to the analytics
UI — a separate change, not started.

## Open decisions (what to revisit against "does it feel like tennis")

1. **The flipped edge.** The owner set counterpuncher > serve_first and closed
   the cycle; that puts the two natural opposite pairs (return-vs-serve,
   ground-vs-net) head to head, which is why the axes had to be FITTED and why
   the six edges come out uneven. The alternative that the attributes express
   on their own — a rotation where opposites are neutral (counterpuncher >
   aggressive_baseliner, aggressive_baseliner > serve_first, serve_first >
   all_court, all_court > counterpuncher, with CP–SF and AB–AC even) — gives
   six equal-sized edges and semantic axes. Either is a one-table change plus
   a re-solve; the owner's call.
2. **Edge size.** 57-64 at equal grade on the strong edges is the top of
   "small relative to the rating gap". Each fidelity has one dial
   (`fast.STYLE_K`/HS `style_k`, `rally.TUNE["style_k"]`) if the season-level
   audit reads too loud.
3. **Net play is dead weight in singles under the point engine.** Seven of
   the 49 attributes count toward overall and decide nothing in a singles
   point; an all-court player's approach/transition game never wins a point.
   This is what forced the small net trade in the v2 table. Pricing net play
   in the singles rally model (approach → net exchange) is the realism fix,
   and a separate, engine-calibration change.
4. **Doubles composition vs pair shape.** The existing serve/net weighting in
   `doubles_rating` already makes "pair two all-courters" the right
   doubles-construction rule; the new term adds who a pair TROUBLES. If the
   owner wants doubles pairing advice surfaced in the lineup editor, the
   composition ranking is the stronger, simpler signal to show.

## Second cut (owner rules 2026-09, same week): the rotation, eight styles, net play, and the flight pages

The owner took the alternative offered above — the rotation the attributes
express on their own — and widened the brief: the classic styles real tennis
has always had, the singles net-play gap fixed in the engine, and the
flight-efficiency table as a page in the game and in the analytics sidecar.

**The plane is SEMANTIC now.** X = defence (return + movement) vs serve, Y = net
vs baseline, both over attribute-cluster deviations (a sixth `touch` cluster —
drops, lobs, slice, court vision, passing — carries the junkballer's tools and
has zero axis weight). The fitted axes of the first cut are gone with the
flipped edge that forced them. Every style is one point and the whole set is one
rotation, a style beating everything within a half-turn behind it:

| style | angle | what the shifts say |
|---|---:|---|
| counterpuncher | 0° | return +8, movement +7, serve −5 |
| junkballer | ~51° | touch +9, net +3, return/movement +4, baseline −3 |
| all_court | ~103° | net +9, baseline −6, serve +3 |
| serve_and_volley | ~154° | serve +10, net +3, return −6, baseline −4 |
| serve_first | ~206° | serve +10, baseline +5, return/movement −5, net −5 |
| aggressive_baseliner | ~257° | baseline +11, net −8 |
| pusher | ~309° | return +6, movement +5, baseline +6, net −8 |
| balanced | origin | flat — neutral against everyone |

On the four cardinals that is the owner's rotation: counterpuncher >
aggressive_baseliner > serve_first > all_court > counterpuncher, opposites even.

**‼️ The seven shaped styles are EVENLY spaced (51.4°), and that is a fairness
requirement, not tidiness.** The first placement kept the four cardinals at 90°
and squeezed the three new styles between two of them; measured, serve_and_volley
and serve_first sat at 59-61% against the field and counterpuncher and pusher at
40% — a style with five styles behind it and one ahead is simply stronger. Even
spacing gives every style three behind and three ahead. The realised angle drifts
+5-10° in Y from the 18% net-specialist roll and the weight normalisation, so
`--angles-only` is the check after any table edit.

**The draw is weighted** (`STYLE_DRAW_V2`: balanced 18 · aggressive_baseliner 20 ·
counterpuncher 16 · all_court 14 · serve_first 12 · serve_and_volley 8 · pusher 7 ·
junkballer 5) — the added styles are real but rarer, as in any field. `rng.choices`
is one draw like `rng.choice`, so the seed stream is unchanged; the v1 five-way
flat draw stays behind the same `style_era()` gate as the v1 table.

**Net play in singles is priced now.** Seven of the 49 attributes (net_play,
volley_touch, overhead, approach_shot, transition_game, poaching,
doubles_chemistry) counted toward a player's grade and decided nothing in a
singles point, which is what made the first cut's net trade a free upgrade for
the net− styles. `engine.rally` now sends a neutral rally to the net at a
per-player rate (`approach_base` 0.14, plus `sv_base` behind a first serve, moved
by `approach_game − rally_skill`), and the exchange adds `net_slope × (netter's
net_game − passer's passing_game)` to the rally logit. ‼️ Both as DEVIATIONS from
each player's own rally level: read raw the net term was a second copy of the
level gap and lifted the favourite ~4 points across the 3-12 OVR bands (measured
67.7 → 72.4 at 3-6, 79.3 → 83.6 at 6-9); as deviations the curve is unchanged to
the point (55.1/67.7/79.3/88.6/94.9/97.8 off vs 53.8/67.3/80.3/87.5/94.9/97.5 on).
`PlayerStats.net_points` / `net_points_won` (`npt`/`npw`) record the approaches.
The fast model's rally composite carries 10% net game so a net player is not dead
weight there either; synthetic players fall back to `rally_skill` and are
net-neutral, so nothing pre-existing moves.

**Flight efficiency shipped twice.** `/jhsaa/flights` (Rankings sub-rail): every
program and flight in the class — N, wins, actual %, expected % (a logistic on
the OVR gap plus home court, FITTED on the season's own varsity flights by
Newton's method), the difference, and who held the flight most; class, flight and
min-matches filters, sortable. Rosters are rebuilt to resolve the archive's names
the way `jhsaa_gap_bands` does, so it runs behind the deferred job and memoises in
`_flighteff_cache`. The sidecar's `metrics/flights.html` is the same table off
`ability.flight_table`, priced by the `WinCurve` the Talent view already fits.
Both say what the 2083 audit found out the hard way: a row of 25-35 matches
swings ~9 points by chance, so read N and trust programs that move the same way
across several flights.


## Third cut (owner rule 2026-09): compositional styles — primary + secondary trait

The owner's brief: expand only with styles that change what the engine DOES —
rally geometry, point length, net frequency, variance — and make style partly
compositional rather than 25 exclusive buckets. So a player is a PRIMARY (the
eight above) plus, about 60% of the time, one SECONDARY trait:

| trait | shifts (half a primary's size) | tendencies |
|---|---|---|
| net_rusher | net +5, movement +2, baseline −3 | approach +0.12 |
| chip_and_charge | return +4, net +4, baseline −4 | chip +0.15 (approach off the return), retspec 0.2 |
| first_strike | baseline +4, serve +3, movement −3, touch −2 | strike 0.6 |
| grinder | baseline +3, movement +3, serve −3, net −3 | grind 0.6 |
| retriever | movement +6, return +2, net −3, serve −3 | cover 0.6, grind 0.15 |
| heavy_topspin | baseline +4, net −2 | topspin 0.5 (opponent approaches less), grind 0.15 |
| flat_hitter | baseline +3, serve +2, movement −2, touch −2 | strike 0.4 |
| slice_specialist | touch +6, baseline −3 | slice 0.6 (blunts the opponent's strike), approach 0.04 |
| return_specialist | return +7, movement +2, serve −5 | retspec 0.6 |
| big_server | serve +8, return −3, movement −3 | bigserve 0.5, sv 0.05 |

Primaries carry tendencies too (counterpuncher grind 0.25, aggressive_baseliner
strike 0.3, all_court approach 0.06, serve_and_volley sv 0.30, serve_first
bigserve 0.15, pusher grind 0.35 / cover 0.15 / topspin 0.2, junkballer slice
0.4), so the pairs the owner named apart really are apart: counterpuncher +
grinder refuses to miss AND redirects, aggressive_baseliner + first_strike wants
it over now, all_court + net_rusher lives at the net, serve_first + big_server's
serve wins the point outright.

**What a tendency does in the engine** (`engine.rally`, point engine only — the
fast model sees a trait through the plane position it moves):
- `approach` / `sv` / `chip` add to the per-rally approach rates (server, behind
  a first serve, returner).
- `strike`, `grind`, `cover` are rally-logit MATCHUPS on attribute deviations:
  a first-striker's attack deviation against the opponent's steadiness
  deviation, a grinder's steadiness against the opponent's attack, a
  retriever's court cover against the opponent's attack. `slice` blunts the
  opponent's strike term. Deviations, never levels — the favourite-rate curve
  is unchanged.
- `retspec` and `bigserve` scale the return's and the serve's share of the ace
  model and of `serve_plus_swing` — the new RETURN PRICING: the server's serve+1
  edge flexes with (serve deviation − return deviation), which is what lets a
  return-built player beat a serve-built one at equal grade (before it, the
  return reached a singles point only through the ace offset and the
  counterpuncher measured ~44% against the field).
- `tend_share` tilts how a won point is labelled: first-strikers post more
  winners AND more errors, grinders fewer of both.

Pinned by `tests/test_style_matchups.py`: traits are weighted in v2 and absent
in v1; every emitted tendency is one the engine reads; a net rusher approaches
>1.4× a balanced player, a first-striker's winners and errors both rise, a
grinder's both fall; return_specialist beats big_server at equal grade.


## Measured, final dials (equal grade, row beats column, both ways)

Dials: fast `style_k` 1.5 (HS 2.4), `d_style_k` 0.6 (HS 0.75); point engine
`rally.style_k` 1.6, `doubles.style_k` 0.5; `style_fade` 0.15; `net_slope` 0.35,
`approach_base` 0.14, `serve_plus_swing` 0.4, `tend_return_cross` 0.35.

| cardinal edge | fast / college | fast / HS | point engine |
|---|---:|---:|---:|
| counterpuncher > aggressive_baseliner | 58.3 | 58.4 | 59.7 |
| aggressive_baseliner > serve_first | 58.4 | 58.9 | 55.7 |
| serve_first > all_court | 62.8 | 60.1 | 58.6 |
| all_court > counterpuncher | 61.5 | 59.5 | 67.9 |
| every style vs the field (spread) | 48-52 | 49-52 | 45-56 |
| same vs the field at ZERO cross term | 49-51 | 49-51 | 46-56 |

Fast: 1,800 matches a cell; point engine 600. The added styles' edges follow
their angles (serve_and_volley > counterpuncher 59-65, pusher > aggressive_
baseliner 55-63, all_court > pusher 58-69, junkballer > counterpuncher 54-61,
serve_first > junkballer 52-59).

**Residual, documented and dialled:** with the cross term OFF the point engine
still prices net- and serve-built shapes ~5 points above defensive ones
(all_court/serve_and_volley 55-56, counterpuncher/pusher/aggressive_baseliner
46-47) — net play is priced in singles now and net-built shapes convert
slightly better there; the fast model is even to ±1.5. That is why the point
engine's all_court > counterpuncher runs hot (68) and aggressive_baseliner >
serve_first cool (56). `net_slope` (0.35) and `serve_plus_swing` (0.4) are the
two dials; both were swept (1.1 → 65/37, 0.5 → 55/46) and left here rather than
zeroed, because zeroing them is what made net play dead weight in the first
place.

**Favourite-rate curve, point engine (favourite win % by OVR gap band 0-3 /
3-6 / 6-9 / 9-12 / 12-15 / 15-18):** before any of this 55.1 / 67.7 / 79.3 /
88.6 / 94.9 / 97.8; after, net play on, 56.9 / 69.7 / 77.0 / 88.1 / 93.7 /
98.2 — unchanged within a point or two, which is the constraint every term here
was written as a deviation to satisfy.

**Behaviour, point engine, equal grade vs balanced opponents (net points % /
winners per point % / unforced errors per point %):** none 14.3 / 13.7 / 13.8;
net_rusher 25.4 / 13.9 / 13.9; chip_and_charge 21.0; first_strike 14.1 / 16.4 /
15.8; grinder 14.1 / 11.1 / 11.9; retriever 11.8 winners; slice_specialist 17.7
net; serve_and_volley (primary) 25.9 net. return_specialist vs big_server 56.6%,
vs serve_and_volley 53.8%.
