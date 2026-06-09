# AAR — Full Two-on-Two Doubles Engine & NCAA Doubles Championship

## Segment summary

This segment replaced the sim's **doubles placeholder** with a real game. Doubles
had always been a shortcut: a pair was averaged into one synthetic singles player
and run through the singles point engine (`engine.dual._pair_player`, and a
tilted variant `junior_circuit._pair_engine`). That was explicitly flagged in the
code as "a later build." This is that build — plus the event it unlocks.

- **A genuine four-player doubles engine** (`engine/doubles.py`) — serve rotation,
  court-based returners, a return played under the net man's poach pressure, and a
  net exchange decided by both teams' net presence and the serving team's serve+1
  edge. Full (point-by-point + stats) and fast (bulk) fidelity.
- **Doubles is now its own skill** — a per-pair `doubles_rating` weighted toward
  serve and net play, so a serve-and-volley pair rates **above** its singles level
  and a pair of baseline grinders below. A player's doubles level ≠ their singles
  level, the same divergence the junior tilt used to fake.
- **Wired everywhere doubles is played** — the three dual-match doubles lines and
  the junior-circuit doubles draws now play real two-on-two matches; the
  averaged-pair hacks are gone.
- **NCAA Individual Doubles Championship** (`app/individuals.py`) — the 64-pair
  (128-player) draw that runs **after** the team tournament: each program's #1
  pair, seeded by doubles rating, every round a simulated two-on-two match. A
  derived, seed-deterministic view (like the team bracket projection), plus a web
  bracket page.

Shipped on `claude/ncaa-singles-doubles-brackets-mt4yey`.

## Why a real doubles model (and the research detour)

Averaging a pair into one player throws away everything that makes doubles a
different sport: the serve sets up the partner's poach, the return has to dip at
the net man's feet, and the point is won at the net in a fast volley exchange —
not from the baseline. A serve+net specialist who is ordinary in singles is a
weapon in doubles, and the old model could never surface that.

A research pass confirmed the right shape. The serious public tennis simulators
(`tennisim`, the academic points-based models) all share one spine: **per-player
service-win and return-win probabilities feeding a point→game→set scoring
layer** — exactly the architecture this engine already uses. Doubles-specific
analytics (the *Dou8les Numbers* corpus, ATP doubles point-ending studies) add
three facts the model is built to honor: **points end at the net and winners are
the #1 way they end**, the **serving team has a clear edge on short points**, and
**holds run high**. (A repo surfaced mid-segment, `tennis-match-tool`, turned out
to be a human-umpire scorekeeper — `input("who won the point?")` — with no
outcome model to borrow; useful as a scoring reference only.)

## The point model

Each doubles point resolves in four stages, all draws through one
`random.Random(seed)` so a seeded match is reproducible:

| Stage | Driven by | Notes |
| --- | --- | --- |
| Serve | server `serve_power` / `serve_placement` | first/second serve, double fault — reuses the singles serve-in + conditions math |
| Ace / unreturnable | server serve vs returner return | rarer than singles (a returner stands in, the net man crowds) |
| Return under poach | returner `return_game` vs server serve, **minus** the net partner's poach pressure | most returns come back (~82% at parity); a missed return is a net putaway |
| Net exchange | both teams' **net presence** (`movement`/`forehand`/`mental`) + serving team's **serve+1** edge + clutch | where most points are decided; winners dominate |

**Service rotation** is real: the four players serve in a fixed order, partners
alternating service games; each player owns one court (deuce/ad) and returns every
ball struck to it. Stronger server serves first, stronger returner takes the ad
court (the bigger points) — deterministic, no coin flip.

The four doubles ratings (`serve_rating`, `return_rating`, `net_rating`,
`poach_rating`) are the levers that make doubles distinct, and `doubles_rating`
combines them into the seeding / fast-model signal.

## Calibration (college, deliberately)

The full point model was tuned so its **win-rate-vs-rating-gap curve tracks the
fast hold model** (e.g. gap 0 → ~50%, +0.06 → ~69% for both); identical pairs
split 50/50 (the engine is unbiased — confirmed directly). Serve-points-won sits
at **~61%**, the college no-ad level: the user explicitly chose to keep it there
rather than push toward the ~84% ATP doubles hold figure, since this is the NCAA
game (no-ad, lots of breaks, deep parity). Aces ~9–10/match, net-ending winners
dominant — consistent with the doubles-analytics references.

## The championship: derived, not a new phase

The season machine is `regular → conf_tournaments → ncaa → complete`. Rather than
splice a new persisted phase in (broad blast radius, new tables, migrations), the
doubles championship mirrors the team bracket's **projection** path: a pure,
seed-deterministic computation off the program rosters
(`run_doubles_championship`), unlocked once the team bracket is `complete`. This
is faithful to the sim's core contract — *rosters/results regenerate from the
seed; only schedules/results are persisted* — so the same seed reproduces the
same champion exactly, with no schema change.

Field: each program's #1 pair (its two strongest players, exactly how the dual
builds its top doubles team), the strongest 64 by doubles rating, seeded the same
way. The draw runs on the existing `engine.run_tournament` framework — the same
one the junior circuit uses — with `simulate_doubles` as the play callback.

The field is **deep**: across a 64-draw the top ratings run ~0.92 down to ~0.87, a
thin spread, so the title takes six straight wins and is genuinely open. Over many
seeds the champion's mean seed is ~21 (random would be ~32.5) — favorites are
favored, but upsets and Cinderellas are common, which is what college doubles
looks like.

## Web

A `/doubles-championship` page (nav: Simulate → Doubles Championship) renders the
bracket — champion card, top seeds, semifinal path, round-by-round results with
scorelines — reusing the team bracket's visual language adapted for pairs. It
stays locked ("played after the team tournament") until the team bracket
completes. The match-line score column is scoped CSS (`:has(.bl-team-score)`) so
the team bracket layout is untouched.

## Files

- `engine/doubles.py` — the four-player engine, ratings, full + fast fidelity,
  `DoublesTeam` / `DoublesResult` (with a `.players` alias so a doubles result
  duck-types as a singles `MatchResult` wherever dual lines render/persist).
- `engine/dual.py`, `app/junior_circuit.py` — rewired onto the engine; the
  averaged-pair shims (`_pair_player`, `_pair_engine`, `_DOUBLES_TILT`) removed.
- `app/individuals.py` — field selection, seeding, the championship runner.
- `app/web/state.py`, `app/web/server.py`, `templates/doubles.html`,
  `static/css/bracket.css` — the web view.
- `tests/test_doubles.py`, `tests/test_individuals.py`, `tests/test_web_doubles.py`.

## What's deliberately left for later

- **Singles 128-draw individual championship** — the same `run_tournament` spine
  with `simulate_match` as the play callback; this segment scoped to doubles.
- **Persisting** the championship into season history / honors (it is currently a
  live derived view).
- **Lineup doubles tactics** (which two players pair, formations as a chosen
  strategy) — the engine models the geometry; choosing it is a future lever.
