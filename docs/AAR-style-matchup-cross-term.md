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
