# Design — Forking O27 into a College Dual-Match Tennis Simulator

*Research + architecture + roadmap. Origin record for this standalone repo.*

## Context

Fork the structures in the `hybrid-baseball` (O27) repo — plus `viperball` and
`or-tennis-data` — into a **college dual-match tennis simulator**: real schools /
fictional players, a globally-expanded footprint via the existing name
generators, **D1/D2/D3 × men's/women's simulated concurrently**, a **juniors +
high-school circuit** that exists mainly to populate *accomplishments for
recruiting*, and a **modified-UTR rating** as the connective metric.

**Headline finding:** this is not a from-scratch fork. ~70–80% of the *ecosystem*
already exists in working form — the college tier is the recruiting premise
already built, the youth tier is the juniors/HS feeder, the peer-universe config
runs concurrent independent leagues with a `gender` field, the name generators are
global + gender-aware, and the **currency / valuation / auction / motivation**
systems are exactly the substrate for a scholarship economy + recruit-decision
engine. The genuinely new builds are the **tennis match engine**, the
**modified-UTR rating**, the **junior/HS tournament & ranking circuits**, and the
**recruiting layer** (scholarships, academics, pro-defection).

**Decisions locked:** new **standalone repo**; **hybrid** match fidelity
(point-by-point for college/showcase, fast model for bulk juniors/HS); **true
UTR-style** rating but **remapped to a distinctive band** (not 1–17 — see §2);
deliverable now is this **architecture + roadmap doc** (no code yet).

> Scope note: the name pools here are already "viperball-derived," so viperball's
> contribution is largely present. `or-tennis-data` + public sources (UTR site,
> USTA/ITF junior schedules, college recruiting sites/sims) are the **data
> sources** — flagged per phase in §7–§8.

---

## What already exists and should be lifted (don't rebuild)

| Capability | Where it lives now | Tennis mapping |
|---|---|---|
| **Recruiting w/ hidden potential + scouting reveal** | `o27v2/college.py`, `college_potential.py`, `college_league.py` (`docs/aar-college-tier.md`) | The recruiting model itself: hidden `potential_X` + static `access_X` lens; displayed = `round(potential×access)`; growth via interest-rate × cap; **two independent scouting reports** (shared service + own dept) blurred ±fog; **reveal on commit**. Re-skin grades as tennis attributes. |
| **Juniors / HS feeder** | `o27v2/youth.py`, `youth_sim.py` (YPI suppression) | Youth tiers that accrue results/accomplishments at suppressed visibility, then feed recruiting. |
| **Concurrent independent leagues (D1/D2/D3 × M/W)** | `data/league_configs/*.json`, `_UNIVERSE_SPEC.md`, `schedule_mode:"independent"`, `gender` field, `teams.league`/`division` cols | Six co-equal universes in one DB, each its own talent style + locale. |
| **Global, gender-aware name generation** | `zaryan_names.py`, `league.py:make_name_picker`, `data/names/{regions,male_first,female_first,surnames,team_naming}.json` | Global, locale-weighted, gender-aware, ISO-country-tagged for flags. Per-school locale blends skew rosters; a tunable domestic/intl slice (§5) rides on this. |
| **Scholarship money substrate** | `o27v2/currency.py` (guilder + tier-caps), `valuation.py` (`estimate_player_value`, `trade_value`) | Per-division cap → per-program scholarship budget; player value → asking price. |
| **Competing-offer mechanics** | `o27v2/auction.py` (personality-driven bid profiles, tranched caps) | Re-tool from sealed single-lot to **open multi-offer** recruiting. |
| **Recruit-decision engine** | `o27v2/trades.py` + `front_office.py` (motivation scorers `(value,ctx)`, acceptance thresholds scaled by context) | Near-perfect fit: swap trade motivations for prestige / playing-time / location / pro-development / **academic-fit**; threshold seeded from player character attrs. |
| **Pro-defection mechanic** | `college.py:sign_to_pro` + scouting fog | Invert: a recruit's "go pro / never enroll" is the same reveal machinery — discovered when they decline you. |
| **Character attrs for decisions** | `players.leadership`, `work_ethic`, `work_habits`, `grit` (`db.py`) | Seed loyalty / training-drive; **add a new `academic_rating`** (§5). |
| **DB + persistence, season archive, career, HOF, awards, leaders, aging** | `db.py`, `sim.py` atomic writes, `season_archive.py`, `player_career_lines`, `hof.py`, `awards.py`, `development.py` | Accomplishments ledger + rankings history + career/All-American/HOF; tennis age curve. |
| **Deterministic seeded engine skeleton** | `o27/engine/game.py:run_game`, event-provider, single `random.Random(seed)`, renderer/stat accumulation, persisted `games.seed` | Keep the shape; swap the sport inside. |
| **Stats site + LLM narrative** | `o27/almanac/`, `o27/gazette/` | Rankings/recruiting site + recruit narrative profiles. |

---

## What is genuinely new

### 1. Tennis match engine (hybrid fidelity)

Mirror the `o27/engine` skeleton (deterministic, event-provider, renderer):

- **Point-by-point** (college + showcase): serve (1st/2nd, **ace/double-fault/
  in-play**) → rally → point outcome (**winner/forced/unforced error**) → game
  (15-30-40, deuce/ad) → set (first-to-6 by 2, **tiebreak at 6–6**) → match
  (best-of-3, optional 3rd-set match-tiebreak). Native stats: aces, DFs, 1st-serve
  %, serve points won, break points faced/saved/converted, winners, UEs, set
  scores; full PBP like `game_pbp`.
- **Fast game-level** (bulk juniors + HS): per-server **hold probability** from
  rating diff → games → sets → scoreline only. For volume.
- **Tier routing:** `simulate_match(..., fidelity="full"|"fast")`.
- **Dual-match team layer (NCAA format):** 3 doubles → **1 team point** (win 2 of
  3), then 6 singles → 6 points; **first to 4 of 7 clinches** (model
  abandoned-after-clinch as a flag). Lineup ordering (singles 1–6 by rating),
  doubles pairings. *(or-tennis-data: confirm per-division/gender format + no-ad.)*
- **Attributes → outcomes:** serve power, serve placement, return, forehand,
  backhand, movement, stamina, mental/clutch, consistency — feeding the serve/rally
  tables (same "talent shifts the distribution" idiom as `o27/engine/prob.py`).
  Optional **surface** (hard/clay/grass) modifier — deferred unless wanted in v1.

### 2. Modified-UTR rating (the metric)

True-UTR math, **remapped display band**:

- Each match → a **match rating** from **% of games won** vs an
  **expected-games-won-vs-rating-diff** curve (fitted logistic). Beating the
  expected share against a strong opponent pulls you up.
- Player rating = **reliability/recency/competitiveness-weighted** average of
  recent match ratings (rolling window); reliability grows with match count and is
  shown alongside.
- Opponent-relative → **cross-division & cross-gender comparable on one axis** —
  the single recruiting yardstick spanning juniors → HS → college → (pro).
- **Display band:** keep the internal computation, then **linearly remap to a
  distinctive band** (e.g. **31.0–48.0**, tunable) so the number reads as "ours,"
  not real UTR's 1–16.5. Final band is a one-line tunable; 31–48 is the working
  default. Separate from the **points-ranking** (§4) — rating ≠ ranking.
- Implementation: post-event **iterative convergence pass** over the match corpus
  (ratings depend on opponents' ratings → fixed point). Persist **rating-history**
  per player; surface on profiles + a global rankings page. *(or-tennis-data / UTR
  site: calibrate the expected curve.)*

### 3. Tennis stat catalog + recruiting profile

A `docs/stats-reference.md` analog (every tennis stat + formula) and a recruiting
profile (rating + reliability, W/L, results-vs-top-N, titles, surface splits,
**academic band**, ranking lists) — built on career-line / leaders / almanac code.

---

## §4 — Junior/HS tournament & ranking circuits (new)

Mirror the real competitive structure; bulk-sim with the fast model; output drives
rankings + UTR + accomplishments.

- **Junior tournament tiers — mirror real:**
  - **USTA national pyramid:** Level 5 → Level 4 → Level 3 → Level 2 → Level 1
    (sectional → national), each with its own draw size, field strength, and
    **ranking-points table**.
  - **ITF World Tennis Tour Juniors:** grades (J30 … J500 / Grade A) +
    **junior Grand Slams** as the apex events.
  - A **calendar/schedule** placing these across the year, so juniors accumulate a
    real results record (not just a season W/L).
- **Ranking lists (the recruiting surface):**
  - **National Top 100 by graduating class** (so coaches recruit a class).
  - **State-by-state lists** (domestic depth).
  - **International:** generated **Top 100 juniors** worldwide + **Top 10 by
    nation**.
  - Rankings are **points-based** (from tournament results) and live alongside the
    modified-UTR number — two distinct signals.
- **High school:** model from college-website HS-sports conventions / existing
  college-recruiting sims; produces the domestic class/state lists above and the
  pool eligible for **US scholarships**.

---

## §5 — Recruiting model (the core of the sim)

### Availability & pro-defection (discovered through the reveal)

- A configurable top slice of juniors (e.g. **Top ~10–15 globally**, tunable N,
  plus high-end domestic) carry a hidden **`pro_track` propensity**: they may
  **turn pro / never enroll**, making them unavailable to recruit.
- **Discovery via the reveal:** for some it's **apparent early** (strong signal in
  scouting); for others it's a **dice roll resolved late** — you invest recruiting
  effort, then they **decline and go pro**. This reuses the college scouting-fog +
  the `trades.py` motivation-acceptance threshold, and is literally the inverse of
  `sign_to_pro`.

### Scholarship economy (equivalency-sport, partial scholarships)

- **Fractional offers:** full, **½, ¼, ⅙** (an equivalency-sport budget split),
  on top of `currency.py` per-division caps → **per-program scholarship budget**.
- **Division weighting:** **D1 weighted highest**, D2 middle; **D3 = commitment
  slots** (no athletic money IRL) — but **top-tier D3 + Ivy prestige** carries a
  **multiplier** that makes them competitive with D1 *for the right recruit*
  (because tennis skews academic). This is what makes the D3/Ivy path real.
- **Domestic-signing knob:** a tunable **% of D1 signings reserved for domestic
  (US) players** — HS players (domestic and international) *can* get US
  scholarships, but you dial the domestic/intl mix at D1.
- **Offer flow:** open competing offers (re-tooled `auction.py`), recruit weighs
  them via the **motivation engine** (`trades.py`/`front_office.py`):
  prestige · playing-time path · location · pro-development · **academic fit** ·
  scholarship size — threshold seeded from `leadership`/`work_ethic`/new attrs.

### Academic model (directs top students to top schools)

- New **`academic_rating`** attribute on players (banded distribution); programs
  carry an **`academic_strength`** rating (Ivies, UAA, NESCAC, Stanford, etc.).
- An **academic-fit motivation** routes high-academic recruits toward
  high-academic programs — the lever that lets Ivy/top-D3 out-recruit a lesser D1
  for an academically-inclined player.

---

## §6 — Proposed new-repo architecture (mirror the o27v2 split)

```
tennis-sim/
  engine/      match.py (point→game→set→match) · rally.py (serve/rally tables)
               · fast.py (hold-prob scoreline) · dual.py (doubles+6 singles, clinch)
               · state.py · render.py (stats + PBP)
  app/         db.py (lifted schema/txn) · league.py · schedule.py · sim.py
               · season_archive.py · rating.py (NEW modified-UTR + convergence + history)
               · circuits.py (NEW juniors/HS tournaments + points rankings)
               · recruiting.py (college.py+youth.py re-skinned: potential/access/scouting,
                 scholarships, academics, pro-defection, commit-reveal)
               · economy.py (currency.py+valuation.py+auction.py re-skinned)
               · awards.py · hof.py · development.py · web/ (Flask + templates)
  generators/  zaryan_names.py + data/names/*   (lifted verbatim)
  data/        schools/ (D1/D2/D3 × M/W) · conferences/ · tournaments/ (USTA L5–L1,
               ITF grades, junior slams) · league_configs/ (6 peer universes)
  almanac/ gazette/   (lifted)   docs/   (tennis stats-reference, AARs, this plan)
```

**Ecosystem flow:** juniors + HS circuits (fast sim, suppressed visibility, real
tournament calendar) → results accrue rating + ranking + accomplishments →
**recruiting** (hidden potential/access; scholarship offers; academic + motivation
fit; pro-defection discovered via reveal) → committed players enter the six
concurrent college divisions → dual matches (full fidelity) → rating updates
continuously across all tiers and both genders → career archive / All-American /
HOF. The modified-UTR is the single currency spanning every tier.

---

## §7 — Roadmap (phased; each phase demoable)

- **P0 — Scaffold + lift.** New repo; copy generators, `db.py` idioms, engine
  skeleton, currency/valuation/auction/motivation modules. Build schools /
  conferences / locale data per division × gender (seed from `or-tennis-data`;
  reuse the college-tier 195-program catalog pattern).
- **P1 — Singles match engine (full).** Point→game→set→match, deterministic,
  stats + PBP, `simulate_match --seed N`. Determinism + scoring tests.
- **P2 — Dual-match team layer.** Doubles + 6 singles, lineup order, clinch-to-4.
- **P3 — Fast model + tier routing.** Hold-prob model; `fidelity` switch for bulk.
- **P4 — Leagues/seasons/schedule.** Six concurrent peer-universe divisions
  (D1/D2/D3 × M/W); schedules, standings, atomic persistence, season archive.
- **P5 — Modified-UTR rating.** Match-rating + reliability + convergence +
  history; remapped display band; global rankings page. Calibrate vs. real UTR.
- **P6 — Junior/HS circuits + rankings.** USTA L5–L1 + ITF grades + junior slams
  calendar; points-based national-by-class / state / intl-Top-100 / Top-10-by-
  nation lists.
- **P7 — Recruiting layer.** Scholarship economy (fractions, division weighting,
  D3/Ivy prestige, domestic-signing knob); academic-rating + academic-fit;
  pro-defection + commit-reveal; recruiting board.
- **P8 — Web UI + content.** Rankings, recruit profiles, match/dual box scores,
  recruiting board; almanac site + gazette narratives.
- **P9 — Career/awards/HOF.** Career archive, All-American/conference honors,
  points-based HOF analog; optional pro tier graduates feed into.

---

## §8 — Data sourcing (what to mirror, from where)

- **Modified-UTR calibration & shape:** UTR site (rating semantics, reliability,
  games-won model) → fit the expected curve; pick the display band.
- **Junior tournament tiers & points:** USTA Level 5→1 structure; ITF World Tennis
  Tour Juniors grades + junior Grand Slams; build the points tables + calendar.
- **HS + recruiting conventions:** college-website HS-sports data and/or existing
  college-recruiting sims; national Top-100-by-class + state-by-state lists.
- **International juniors:** generated Top-100 + Top-10-by-nation lists.
- **Schools/rosters/results:** `or-tennis-data` (real programs per division ×
  gender, roster sizes, dual-match format specifics, results to validate against).
- **Names/footprint:** already in-repo (viperball-derived pools); extend regions
  for any missing tennis nations.

---

## §9 — Verification

- **Determinism:** same seed → identical transcript + scoreline, per fidelity.
- **Scoring correctness:** deuce/ad, tiebreak at 6–6, best-of-3, dual clinch-at-4
  (incl. abandoned-after-clinch), optional no-ad.
- **Rating sanity:** rating diff predicts games-won share within the fitted curve;
  convergence stable/idempotent; reliability rises with matches; cross-division/
  gender numbers land in plausible bands; display remap is monotonic.
- **Circuit/ranking sanity:** points tables produce sensible Top-100/state/nation
  ordering; better players rise; class lists are stable across a season.
- **Recruiting sanity:** scholarship budgets never exceed caps; fraction sums are
  valid; pro-defection rate ≈ the configured top-N; domestic-signing knob moves the
  D1 mix; academic-fit routes high-academic recruits to high-academic programs.
- **Stat invariants:** tennis `test_stat_invariants.py` (points won+lost=total;
  aces ≤ 1st-serve points; BP saved+lost=faced; team points ≤ 7, clinch at 4).
- **End-to-end:** seed all six divisions + juniors/HS, sim a full year, run the
  convergence pass, smoke-test rankings + a recruit profile + a dual-match box.

---

## §10 — Open questions (early-build, non-blocking)

1. **Pro tier ceiling?** Model a pro circuit graduates/defectors enter (the
   baseball side already signs college→pro), or stop at college?
2. **User role:** does the user play a coach recruiting against hidden grades (the
   college-tier draft board), or is recruiting fully simmed?
3. **Final modified-UTR band:** 31–48 (default) vs 51–67 vs other.
4. **Surfaces in v1** (hard/clay/grass), or defer?
5. **Tunable defaults:** top-N pro-defection size; D1 domestic-signing %; D3/Ivy
   prestige multiplier magnitude.

---

## §11 — Build log + juniors/recruiting reference (banked from the user)

**What's built (this fork, not the doc's hypothetical):**
- **Engine:** deterministic singles (full) + fast model + NCAA dual layer
  (`engine/`), with toggleable `MatchFormat` (no-ad, set tiebreak, 10-pt
  match-tiebreak-in-lieu-of-3rd-set, **8-game pro set**).
- **Web UI (Flask, `app/web/`)** in the oregontennis.org "Baseline" design
  language: Power Index rankings (live), Dual Simulator (setup + scoreboard +
  win-prob sweep), NCAA Bracket, Methodology.
- **P4/P5:** `app/season.py` (schedule → sim → standings → conference
  tournaments/autobids), `app/rating.py` (Power Index = 40% APR + 40% FQI +
  20% oGS), `app/bracket.py` (autobids + at-large, PI seeding, single-elim
  **dual-match bracket** modeled on March-Madness sims — favorites favored,
  real upsets). Real **D1** conference data in `data/ncaa/d1_{men,women}.json`
  (32 conferences, 366 programs, full membership copied 1:1).

**Done since:** D2/D3 data + all six universes; pazzah pressure/clutch port
(`engine/rally.py` + `match.py`); configurable division bracket sizes
(16–128, presets 32/64/76/96, default 64); and the **player talent &
development model** (`app/development.py`).

**Player talent & development model (`app/development.py`)** — adapted from the
O27 baseball prospect model but **corrected for tennis**: you can't hide current
ability behind scouting grades because every player has a UTR-style rating and
results don't lie. So:
- **Current ability is VISIBLE** — each attribute has a `current` value the
  engine plays; results / ranking / **UTR** reflect it. You can see how good a
  junior is *now*.
- **The trajectory is HIDDEN** — each attribute has a true `potential` ceiling,
  and a static `interest_rate` (tiers ordinary 75% / late bloomer 20% /
  super-bloomer 5%) deterministically closes the gap each year. No rerolls, no
  regression; the slope is set at birth, you just don't know it.
- The recruiting gamble is **growth, not measurement**: the high-UTR early
  bloomer near his ceiling is the bust; the modest-UTR late bloomer with a high
  hidden ceiling + steep slope is the gem. `star_rating` tracks visible current
  ability (so gems are under-rated, busts over-rated).
- **Scouting fog:** two independent reports (shared service + own dept) project
  the hidden *ceiling* ±fog (7–31). Per-attribute breakdowns hidden until a
  recruit signs; ceiling stays a projection until the pro reveal.
- `Prospect.engine_player()` feeds the match engine; `manage.py prospects
  [--reveal]` demos the gem/bust dynamic.

**STR — the results-based rating (`app/str_rating.py`).** STR is the game's
synthetic UTR, on a distinctive **31–57 band** (not raw UTR 1–17). The engine is
results-based, not an ability readout: each match yields an opponent-anchored
match rating (invert an expected-games-share logistic), so you get **credit for
competing well vs good players and a boost for beating better players**. It's
**recency-weighted over a rolling 30-match window** ("what have you done lately")
— so a slump/inactivity makes STR **decay downward** even though ability never
regresses. Reliable at ~5 matches; thin records blend toward a prior; matches
with a >2.00-UTR (±3.35 STR) gap are excluded; opponent-rating reliability
weights each result. `converge_ids()` solves a whole population to a fixed point.
(Ability-derived STR from the development model seeds players without a match
record; the results engine takes over once they've played.)

**Juniors / recruiting surface (`app/juniors.py`).** Recruit-class generator
with origins (US city+state, intl city+nation incl. Canada) and the ranking
lists — National Top-N by class, state-by-state, international Top-N / Top-N by
nation — with **count-based star tiers** (Blue Chip top 25 / 5★ / 4★ / 3★ /
Unrated, TRN convention). Boards rank on consensus (visible STR + scouts'
ceiling projection), so they can mis-rank gems/busts. Calibrated to
`docs/calibration-tennis-trajectories.md`.

**Deferred (large, separate system):** the **team-chemistry model** (Voice /
Glue / Pull / Reach + Drama / Fit / Head, Franchise/Big-Stage/Baggage flags,
coach archetypes, spine/resilience) from the user's chemistry post — to layer
on once rosters carry multi-year prospects.

**Next:** the **juniors / HS circuits + recruiting** (P6/P7) on top of this
talent model.

**Juniors / HS + recruiting layer (P6/P7/P8) — reference to honor when built:**
- **No HS teams rendered** — generate *players* only. Origin fields:
  **US = birth city + state**; **international (incl. Canada) = birth city +
  nation**.
- **Ranking tiers:** juniors carry an **ITF junior world ranking + national
  ranking**; HS kids carry **UTR + state rankings**. Mirror
  **tennisrecruiting.net**: National / Regional / State lists, **star ratings**
  (Blue Chip / 5-star…), TennisRPI, "activity vs star tiers," commitments feed.
- **Recruit profile page** = the tennisrecruiting.net player-record layout
  (rankings panel · highest rankings · schools-of-interest/commitment ·
  activity overview). Reuse the **recruit-page models already in `viperball`
  (Recruiting Hub + recruit profile w/ commit-prediction %, dreamsheet,
  timeline, scouting report) and `superinnings`** (displayed-grades vs noisy
  scouting reports; hidden potential/access/fog, `?debug=true` reveal).
- **HS data sourcing (later):** scrape MaxPreps / On3 / recruiting sites for a
  national spread of high schools across all 50 states + DC.
