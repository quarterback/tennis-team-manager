# AAR — Doubles Engine, NCAA Individual Championships & Tennis Seeding

## Segment summary

This segment replaced the sim's **doubles placeholder** with a real game, built the
**individual championships** (singles 128 + doubles 64) for every division×gender,
and gave **every bracket** proper tennis seeding. Doubles had always been a
shortcut: a pair was averaged into one synthetic singles player and run through the
singles point engine (`engine.dual._pair_player`, and a tilted variant
`junior_circuit._pair_engine`), flagged in the code as "a later build." This is
that build — plus the events it unlocks and the seeding they all needed.

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
- **NCAA Individual Championships** (`app/individuals.py`) — the **128-player
  singles** and **64-pair doubles** draws that run **after** the team tournament:
  the best players/pairs in the field, seeded by rating, every round a simulated
  match (`simulate_match` for singles, the four-player `simulate_doubles` for
  doubles). Derived, seed-deterministic views (like the team bracket projection),
  with web bracket pages. Every division×gender has its own — **D1/D2/D3 × men and
  women**.
- **Tennis-style seeding for every bracket** — only the top **quarter** of a draw
  are seeded and protected (128→32, 64→16, 32→8); seeds 1 and 2 anchor the ends,
  each deeper tier is shuffled among its mirror anchors, byes go to the top seeds,
  and **everyone else is drawn in at random**. One implementation
  (`engine.tournament.seeded_draw`) powers the individual draws, the junior
  circuit, and the team bracket.

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

## Seeding: a quarter of the draw, the rest random

The brackets used to seed the *entire* field deterministically — everyone had a
seed number and the draw was fixed by rating. Real tennis seeds only the top
**¼** of a draw (128→32, 64→16, 32→8); those seeds get protected, isolated
placement, and **all remaining players are drawn in at random**. That randomness
is the point: an unseeded player can land anywhere, a brutal section is bad luck,
and a deep run off a tough draw is earned — none of which a fully-seeded bracket
can express.

It's one shared implementation, `engine.tournament.seeded_draw(n_real, n,
n_seeds, rng)`: it places seeds tier by tier (1 and 2 anchored at opposite ends,
[3,4] shuffled between the two open quarters, [5–8] among the eighths, [9–16]
among the sixteenths, …), gives the byes to the top seeds' opponents, then draws
the unseeded field into the open slots — all off one seeded `rng`, so the draw is
reproducible. `run_tournament` uses it for the individual events and juniors; the
team bracket (`app.bracket.run_bracket`) calls the same helper. `seed_count`
encodes the ¼ rule. Seed numbers now display only for actual seeds; unseeded
entrants (and unseeded champions — they happen) carry none.

## The championships: derived, not a new phase

The season machine is `regular → conf_tournaments → ncaa → complete`. Rather than
splice a new persisted phase in (broad blast radius, new tables, migrations), the
championships mirror the team bracket's **projection** path: pure,
seed-deterministic computations off the program rosters (`run_singles_championship`
/ `run_doubles_championship`), unlocked once the team bracket is `complete`. This
is faithful to the sim's core contract — *rosters/results regenerate from the
seed; only schedules/results are persisted* — so the same seed reproduces the
same champions exactly, with no schema change.

Field: **singles** pools every program's top 2 players and takes the best 128 by
ability; **doubles** takes each program's #1 pair (its two strongest, exactly how
the dual builds its top doubles team) and the best 64 by doubles rating. Both run
on the existing `engine.run_tournament` framework — the same one the junior
circuit uses — with `simulate_match` / `simulate_doubles` as the play callback, and
the new seeding applied (top 32 / top 16 protected).

The field is **deep**: across a doubles 64-draw the top ratings run ~0.92 down to
~0.87, a thin spread, so a title takes six straight wins and is genuinely open.
Over many seeds the champion's mean rating-rank is ~21 (random would be ~32.5) —
favorites are favored, but upsets and Cinderellas (including unseeded champions)
are common, which is what deep college fields look like.

## Web

Two pages — `/singles-championship` and `/doubles-championship` (nav: Simulate →
Singles / Doubles Championship) — render each draw: champion card, top seeds,
semifinal path, round-by-round results with scorelines, reusing the team bracket's
visual language adapted for players/pairs. Each stays locked ("played after the
team tournament") until that universe's team bracket completes, and the universe
pills switch freely between **men and women** (and D1/D2/D3). The match-line score
column is scoped CSS (`:has(.bl-team-score)`) so the team bracket layout is
untouched; seed numbers render only for seeded entrants.

## Files

- `engine/doubles.py` — the four-player engine, ratings, full + fast fidelity,
  `DoublesTeam` / `DoublesResult` (with a `.players` alias so a doubles result
  duck-types as a singles `MatchResult` wherever dual lines render/persist).
- `engine/tournament.py` — `seed_count` + `seeded_draw` (the ¼ seeding + random
  draw), `TournamentResult.n_seeds` / `seed_no`.
- `engine/dual.py`, `app/junior_circuit.py` — rewired onto the doubles engine; the
  averaged-pair shims (`_pair_player`, `_pair_engine`, `_DOUBLES_TILT`) removed.
- `app/individuals.py` — singles + doubles field selection, the championship runners.
- `app/bracket.py` — the team bracket now uses the shared seeded draw.
- `app/web/{state,server}.py`, `templates/{singles,doubles}.html`, `bracket.html`,
  `static/css/bracket.css` — the web views.
- `tests/test_doubles.py`, `tests/test_individuals.py`,
  `tests/test_web_{singles,doubles}.py`.

## What's deliberately left for later

- **Persisting** the championships into season history / honors (they are currently
  live derived views).
- **Seeding the persisted season-mode bracket & conference tournaments** — the
  played-out NCAA/conference draws still schedule by full deterministic seeding
  (`seasonmode._round1_pairs`); only the *displayed* team bracket got the ¼-seed
  random draw this pass.
- **Lineup doubles tactics** (which two players pair, formations as a chosen
  strategy) — the engine models the geometry; choosing it is a future lever.
