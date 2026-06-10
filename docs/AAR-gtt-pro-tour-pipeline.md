# AAR — Global Team Tennis: the Pro Tour & the College→Pro Pipeline

## Segment summary

This segment built the **Pro Tour** (Global Team Tennis, GTT) — a co-ed
professional team-tennis league layered on top of the college sim — from a
thought experiment to a fully playable, browser-only feature. The session
started as pure contemplation ("could WTT-style team tennis fit this engine?"),
produced a design doc, and then shipped the whole thing in phases. Along the
way it surfaced and fixed two long-standing name-generation bugs in the college
game that had nothing to do with GTT but everything to do with how the sim
reads.

- **The GTT dual** — 3 men's singles + 3 women's singles + 3 mixed doubles,
  first to 5 of 9 lines, on the existing engine (`engine/gtt.py`).
- **A persistent career league** — multi-season franchises with real persisted
  players who age, decline, retire, and refresh from a keeper + snake draft
  (`app/gtt_seasonmode.py`, forked from `seasonmode`).
- **The college→pro pipeline** — graduates keep their real `pid`, so honors
  follow a player from a college Player-of-the-Year to a GTT MVP on **one
  career page**.
- **Full web wiring** — league hub, franchise pages with a cosmetic editor,
  player pages, ATP-style per-game box scores, Hall of Fame, awards archive.
- **Two name-system fixes** — the `men`/`women` gender fall-through and six
  melting-pot regions that violated the O27 one-subregion-per-draw rule.

Shipped on `claude/sharp-feynman-gvl21l` (design doc merged earlier as PR #30).

## Design intent: not WTT, and the league is not the feature

Two early decisions shaped everything:

**1. Don't replicate WTT.** Real World TeamTennis scoring (cumulative games,
five fixed set-configs, supertiebreakers) was deliberately rejected. A GTT dual
is scored like any other team sport — each line is a point, team W/L records,
standings. This kept the entire format inside machinery the engine already had:
`simulate_match` for singles, the real 2-on-2 doubles engine for mixed (which
is attribute-driven and gender-blind, so co-ed doubles needed **no cross-gender
model at all** — both sides build symmetrically).

**2. The league is the stage; player continuity is the feature.** The stated
motivation was "knowing what happens to players after they graduate and having
a place to keep favorites around to watch them." That reframed the build: the
load-bearing requirement is that a graduate keeps the same identity across
contexts, and everything else (draft, retirement, archives) is in service of
watching a career unfold.

## The pivotal simplification

The original plan assumed pro rosters would need persisted college players from
day one. The user's correction — **"the founding pros never went to college;
only subsequent players need a pathway in"** — collapsed the risk:

- The inaugural league is *generated* (founders with no college history, which
  is correct — they predate the college game's output).
- Each off-season pulls that year's graduating seniors straight out of
  `world_roster` (read through the same connection — **zero changes to the
  college finalize path**, the riskiest code in the repo).
- Honors stamp to the graduate's real college pid via the existing
  `app.honors` table, so `career_by_year(pid)` returns college and pro
  accomplishments as one timeline for free.

Verified end-to-end: a college National Player of the Year (2026) graduated,
was drafted (`origin: college`), and won GTT MVP + Champion (2029) — all on one
page.

## What was reused vs. built

| Need | Source | Note |
| --- | --- | --- |
| Co-ed dual | `engine/dual.py` pattern + `engine/doubles.py` | new `gtt.py`, ~115 lines |
| Season/playoffs | forked `app/seasonmode.py`, stripped of conferences/NCAA | flat double round-robin → top-4 single elim |
| Honors | `app.honors` stamp/career | new awards: `gtt_mvp`, `gtt_champion` |
| Decline | `Prospect.develop()` inverted | `decline()` = development in reverse, dormant until past peak (28), steepening with age |
| Match stats | engine `PlayerStats` | captured per line at play time, ATP-layout box score |
| Franchise identity | new `gtt_franchises` registry | **everything keys off ids, never names** — renaming/relocating is provably cosmetic (tested) |

The id-keyed identity rule is the editor guarantee: the user can rename any
franchise to anything ("a team's name needn't contain its city") and not a
single result changes.

## Both speeds, by demand

A mid-session misunderstanding produced a real requirement: the user wants to
*watch* this league, not batch it. The hub therefore keeps **both** controls —
"Advance week (full engine)" plays one slate with every point simulated and
every game inspectable; "Simulate to champion (fast)" remains as the shortcut.
Week results link to per-dual box scores: each of the 9 lines expands into an
ATP-style stats panel (aces, DFs, 1st-serve %, service/return points won, break
points, winners/UEs, total points) with player and franchise names linked.

## The name-system fixes (found by playing, not by tests)

Mid-session the user noticed male names in a women-only college sim. Two
distinct bugs, both pre-dating this segment:

1. **Gender fall-through.** `make_name_picker` matched only `"male"`/`"female"`;
   the world passes `"men"`/`"women"`, which silently fell through to the
   mixed 50/50 branch. One normalization line fixed every women's class in the
   college game.
2. **Melting-pot regions.** The picker *code* implemented O27's coherence rule
   (one subregion per draw; first, surname, and country all from it), but six
   hand-rolled regions in `regions.json` violated it — `europe_western` rolled
   first-cohort × surname-cohort × country as three independent dice
   ("Diana Pérez (IT)", "Sonja Littlejohn (DE)"); `us` crossed
   `asian_american` firsts with `american_general` surnames ("Hina Opelka").
   All six were rewired into per-cohort subregions with countries attached,
   `make_country_pinned_picker` was added for O27 API parity, and a mechanical
   coherence test now asserts every draw across the main presets is
   satisfiable by a single subregion — the "Babar Iqbal, never Babar Iyer"
   rule is CI-enforced.

The lesson worth keeping: the *data wiring* is part of the algorithm. The
mechanism was correct and the pools were the full O27 set (152 buckets, ~27k
names), yet six wrong region entries made the whole nameset look hand-rolled.

## Archives: freeze, don't recompute

The Hall of Fame **freezes** a profile — attributes, career record, honors
snapshot — into `gtt_hof` at enshrine time and never updates it, even as the
live player declines or retires. The awards archive (champion + MVP per
season) persists in `gtt_seasons` and renders on both the hub and the HoF
page. Both follow the repo's honors philosophy: stamped once, never recomputed.

## Engineering notes

- **Same-file SQLite discipline.** Three deadlocks came from opening a second
  connection mid-transaction (honors stamping, world reads, franchise reads).
  The fixes are patterns to reuse: read sibling tables *through the caller's
  connection* (`_world_graduates`, `_fr_rows`), and defer cross-module writes
  until after commit (`_flush_honors` carries honor rows out of the
  transaction).
- **Transaction visibility.** Public helpers that open fresh connections can't
  see rows inserted in a still-open transaction — `_build_schedule` silently
  produced an empty schedule until it read franchises through the open conn.
- **Determinism held throughout**: dual seeds derive from
  `blake2s(seed|fid|fid|tag)`, retirement rolls from `blake2s(pid|retire|year)`,
  same seed ⇒ identical league history (tested).
- Pre-existing flake (`test_season.py::test_higher_seeds_usually_advance`) is
  statistical and unrelated; full suite otherwise green (208 passed).

## P4 — STR continuity feed (built)

Pros now carry a live, results-based STR, not a frozen profile number.
`league_player_str` builds the corpus from the stored singles box scores
(`pid → [(opp, games_won, games_lost)]`, oldest→newest, games parsed back out
of the winner-perspective scorelines) and converges it with the **same**
`str_rating.converge_ids` the college game uses. Each player's prior is their
profile STR — and a graduate's profile *is* their college-exit snapshot, so the
rating crosses college→pro with no seam and drifts as pro matches accumulate.
Mixed doubles is display-only; there is deliberately **no pro ranking page** (the
number computes and shows on profiles, never a leaderboard).

One real engine finding fell out of the first run: a 14–0 MVP came back at
reliability 0.00. UTR's 2.00 blowout-gap rule (`MAX_DIFF`) assumes a large
population where close-rated opponents always exist; in a small drafted pool the
best player out-rates the entire field by more than the gap, so **every** one of
his matches was excluded. Fix: `converge_ids` gained a `max_diff` parameter
(college default unchanged at 2.00); GTT passes 6.0. Worth remembering that
UTR-style margin math is calibrated to a deep ladder and needs a wider window in
a closed league.

## Chaos: the pro game is built to be volatile

The user's brief: "team tennis should be hella chaotic and variable.
Unpredictable" — but not a coin toss. Getting there was an instructive tuning
loop, and the dead ends matter as much as the result:

1. **Additive per-attribute jitter did nothing.** A gaussian nudge on each of
   the nine drivers is symmetric and cancels; over a match it washed out.
   ("The jitter doesn't work" — correct.)
2. **Multiplicative per-player form barely moved the dual.** Scaling a player's
   whole level by a wide factor swings individual *lines* hard — but a dual is
   first-to-5-of-9, and **independent** per-player noise averages out over nine
   lines, so the favourite still took ~70%. The law of large numbers is the
   real adversary here, not the noise magnitude.
3. **Team-correlated form is the lever that moves the dual.** One factor for the
   whole squad's night drops favourite-win much further — but the user
   explicitly preferred **player-based** form and was fine with ~70% at the dual
   level, because the chaos that matters is the one you *watch*: the box scores.

Two levers shipped:

- **Fast4 lines.** Every GTT line (singles and mixed) is a single Fast4 set —
  first to 4 games, no-ad, tiebreak at 3-3. Short sets are inherently
  high-variance where a best-of-3 lets class grind it out. This needed a real
  engine extension: `MatchFormat.set_tiebreak_at` (the games count the tiebreak
  is played at; `None` ⇒ games-all, so college/juniors are untouched), wired
  through both the singles and doubles set loops.
- **Per-play-date player form.** Each play date every fielded player's whole
  level is multiplied by a fresh **−30% .. +45%** factor, drawn per player. A
  star can show up flat, a journeyman can catch fire.

Outcome, measured over 40 leagues: favourites take **~70% of duals** (vs ~80% in
college), the better player drops **~35% of individual singles lines**, and class
still sorts the season. Deterministic (form seeded off the dual seed), and tuned
from one place (`CHAOS_FORM_LO/HI`).

The throughline of this whole tuning episode: **where variance is injected
matters more than how much.** Match length (Fast4) and correlation structure
(player vs team) determined the feel; raw noise magnitude barely did.

## What's deliberately not built

- **Vickrey auction** — designed (deterministic private values on the
  scholarship-economy substrate; balance emerges from need-aware valuation)
  but the snake draft ships first; the allocation step is isolated behind
  `_draft` for a clean swap.
- **Team-correlated form** — prototyped and measured (it drives dual-level
  chaos harder), but player-based form was the chosen design; the swap is a
  one-function change if the season race ever wants more upset.
- **Pro rankings** — by design, never: STR computes, no pro leaderboard.
