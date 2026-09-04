# AAR — the 8A/9A 4S/5D postseason pilot (owner rule 2070)

The JHSAA approved a pilot for **2070**: 8A and 9A play **4 singles / 5 doubles** —
nine points — instead of 1S/4D. It replaces 1S/4D from the moment the regular season
ends, exactly where 1S/4D used to start, and it takes the **early non-district
window** with it (that window was the last 5S/2D block in the association, and it
exists to rehearse the card a program will have to win with).

Everything else in those two classifications is untouched: the league season is still
3S/4D, the mid-season showcases are still 1S/4D, the **Tournament of Champions is
still 1S/4D** — an 8A/9A champion simply reverts to nine on court there, since the TOC
fields every classification's champion at one shape — and the individual state
tournaments are still 3S+3D and read no dual format at all.

## Why (the backtest the board decided on)

Every 8A/9A State qualifier 2064-2068 (774 team-seasons) replayed a round robin
against its own field under each card, on identical rosters.

| | 1S/4D | 2S/5D | 4S/5D |
|---|---|---|---|
| Access (on court) | 9 | 12 | **14** |
| Doubles share | 80% | 71% | 56% |
| Correlation with DEPTH (#10-#14) | +0.561 | +0.659 | **+0.683** |
| Correlation with the TOP player | +0.586 | +0.507 | **+0.465** |
| Players on court with <5 matches | 0.1% | 3.6% | 15.4% |

Two findings did the work. **The current card is the one that most rewards a single
dominant player** — the board's stated fear about adding singles courts is the
opposite of what the data says, because S2-S4 are contested by near-peers across
programs while the lone S1 is where one great player decides everything. And **depth
overtakes top-end**, +0.683 to +0.465, which is the redistribution the board chose:
Elysian Valley 2065 girls goes .41 → .76, Carondelet 2067 boys .58 → .24.

The one real cost is preparation — the league card dresses eleven and the State card
needs fourteen, so about one in six state participants is a player the regular season
barely used. Accepted as stated (owner: those players all play JV, and some get
varsity starts on injuries anyway). It is not compensated for anywhere.

## ‼️ ONE SHAPE PER DUAL, AND THIS IS THE FIRST PILOT WHERE THE TWO SIDES CAN DISAGREE

Every earlier pilot was postseason-only, and a bracket never crosses a
classification, so `play_dual` resolved the shape from the **home side's group** and
said so in a comment. This pilot reaches the **early window**, which pairs a program
with one in its own classification *or one apart* — so an 8A-vs-7A early dual has one
side wanting 4S/5D and the other 5S/2D.

Read off one side, the other team dresses for a card it is not playing and
`_squad` / `_slot_players` **wrap** rather than raise (`at(i % len(r))`, by design, so
a short side degrades instead of 500ing the page): the same players on two courts at
once, a plausible-looking box score, nothing logged, nothing to see on the card.

`jhsaa.shape_group(phase, a, b)` is the fix, and the rule is **the wider card wins**
(owner rule 2070) — not a fallback to the narrower one. Every program in this
association carries the bench for a nine-court dual: `ROSTER_SIZE_BAND_BY_CLASS` puts
7A/6A at 19-22 and `ROSTER_FLOOR` is a hard 16, against fourteen on court. So an
8A-vs-7A early dual plays 4S/5D and the 7A side simply dresses fourteen. A first pass
dropped that dual to 5S/2D on the theory that the smaller school could not staff nine
courts, which is defending a constraint this simulation does not have — the owner's
correction. It is resolved once per dual and threaded to both lineups, both squads,
both slot resolutions and both credits; nothing downstream reads a side's own group
any more.

## ‼️ THE FLIGHT WEIGHT TABLE IS PER-DUAL NOW, BECAUSE ONE NAME HAS TWO PRICES

The association re-priced the whole card rather than bolting two rows onto the old
table (owner's numbers, `FLIGHT_WEIGHTS_4S5D`): S1 and D1 **2.00** each, then
1.00/0.80/0.65/0.45/0.30/0.20/0.10, max **7.50**. So **S1 is worth 2.00 on the
nine-court card and 1.00 on every other JHSAA shape** — the same flight name, two
prices — and `compute_ratings`'s single `weights` argument could no longer describe
the graph.

A dual may now carry its own table under a `"weights"` key, which wins for that dual
alone. It composes for the reason the association's three existing shapes already
share one TOSS table: `rating._flight_score` normalises by the weight actually
**contested** per dual, so a 7.50-max shape and a 3.85-max one each contribute a 0-1
share and a table's absolute scale never reaches the rating. The table is resolved
from **`shape_group`, not the home side** — for the same reason the shape is.

`D5` had to be weighted at all: an unrecognised flight **raises**, deliberately (see
`docs/AAR-toss-per-division-flight-weights.md` — a `.get(slot, 0.30)` default once
ran a D1 lineup's index backwards for a release).

## ‼️ AND THE AWARDS SCALE IS NOT THE DUAL'S SCALE

`jhsaa_awards._weight` reads the association's table per slot, and a résumé score is
compared **across** classifications — All-Region is region-wide and class-blind. Taken
raw, the new prices would hand every 8A/9A postseason appearance twice the credit of a
7A one *for the same court*, on nothing but the card's arithmetic. `_weight` therefore
normalises by the table's top court: the association's **ordering** is the decision it
made, its **scale** is a property of the card and not a statement about players. The
ordinary table's maximum is 1.00, so every other classification is untouched to the
last bit.

`FLIGHT_WEIGHTS` also gains a `D5` at 0.05 — contested in no shape on that table, and
there so a generic per-slot reader ranks the nine-court card's last court *below* its
fourth instead of taking the bare `.get(slot, 0.25)` default and pricing it above four
of the others.

## The rest of the wiring

* **The arrangement is one mechanism at a third width.** `_arrange_state` pools the
  top three and picks which one plays S1; 1A's 2S/3D pools four and picks two; 4S/5D
  pools **six** and picks four, the other two being D1. `_arrange_wide(players,
  n_singles, sibs)` is that generalisation and 1A's arranger now delegates to it. The
  best player is **not** pinned to S1 — that draft was written and corrected once
  already. D2-D5 pair by real `doubles_rating` over every legal partition of #7-#14,
  then `_order_pairs`'s adjacent rank-sum boundary.
* **The freeze needed nothing.** `_postseason_nine` already stored the FULL ladder and
  sliced it per phase, which is what lets 8A/9A dress fourteen on the road and nine at
  the TOC off one frozen order — the same property that let 1A dress eight and nine.
* **`_arrange_early` took a width.** The early window's allocation is the format's
  (top `n` singles, the rest paired in ladder order) and stays a plain order at either
  width; only the sibling swap moves anybody.
* **Nine is odd**, so a 4S/5D dual cannot tie — there is no tie-break anywhere in this
  association and none was added. High school has no clinch, so all nine are played.
* **The JV *playoff* cut moves; the JV *season* cut does not.** `jv_pool` is rank #12
  down for every classification, 8A/9A included — the JV league season is staffed off
  the varsity eleven and the pilot does not touch it. The JV state tournament's
  eligibility freeze is cut below the varsity playoff lineup instead
  (`jv_postseason_cut`, derived from `lineup_need` rather than typed), so 8A/9A freeze
  at **#15 down**. It is **not** an exclusion: a player may dress for the varsity
  playoff fourteen *and* the JV championship squad. The JV *individual* events are
  preseason and needed nothing.

## What no year gate means

There is none, by owner decision — the 2070 date is for the record, not a branch. Every
8A/9A season already archived therefore re-reads at the new shape's rules where a page
recomputes anything. Nothing about an archived dual's own row changes (the lines, the
scores and the points are stored), and the shapes that decided those seasons are still
in `FORMATS`; what a page will not do is claim an old 8A State dual was nine courts —
it stores the five it played, and the flight box derives its width from what is there.

## Known consequence, not compensated for

`jhsaa_jv_state.entries` needs seven frozen-eligible players. Cut at #15, a 20-player
8A program has six, so a handful of the thinnest 8A/9A rosters cannot enter the JV team
state tournament. The event drops a program rather than degrading a dual, which is the
association's posture everywhere; the twenty regions still fill.

## Files

`app/jhsaa.py` (`FORMATS["state_4s5d"]`, `WIDE_GROUPS`, `dual_format`, `shape_group`,
`_arrange_wide`, `_arrange_early`, `_postseason_nine`, `_lineup`, `_credit`,
`play_dual`, `FLIGHT_WEIGHTS_4S5D`, `flight_weights`, `rating_duals`,
`jv_postseason_cut`, `jv_state_pool`) · `app/rating.py` (per-dual `"weights"`) ·
`app/jhsaa_awards.py` (`_weight` normalisation) · `app/jhsaa_jv_state.py` (the freeze
reads `jv_state_pool`) · `tests/test_jhsaa_lineup.py`.
