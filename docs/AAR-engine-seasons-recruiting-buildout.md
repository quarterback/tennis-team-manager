# AAR — Engine, Seasons, Ratings, Recruiting & Web Build-out

## Segment Summary

This segment took the repo from an abandoned TypeScript scaffold to a working,
deployable **college dual-match tennis simulator** in Python: a deterministic
match engine, six simulated NCAA universes, two ratings (team Power Index + a
results-based player **STR**), a player development model, a multi-season league
with a transfer portal, and the full web UI in the oregontennis.org-derived
"Baseline" design — plus the deploy pipeline. It then **merged with a parallel
agent's player/coach model** that landed on `main`.

Guiding choices set by the user along the way: reuse the O27 baseball substrate
(don't rebuild); hardcourt **conditions, not surfaces**; STR on a distinctive
**31–57 band** (not raw UTR); transfers are high-churn, bidirectional and
STR-driven; players' *current* ability is visible (UTR-style) while their
*trajectory* is hidden.

The work stayed additive and seed-deterministic throughout, which is what made
the late three-way merge with the other agent tractable.

## What Was Built

### Engine (`engine/`)
- Point → game → set → match singles engine (deuce/ad, tiebreaks, best-of-3/5),
  a fast game-level model for bulk sims, and the NCAA **dual-match** layer
  (3 doubles + 6 singles, clinch at 4, abandon-after-clinch).
- `MatchFormat` toggles: no-ad, set tiebreak, 10-pt match tiebreak, **8-game pro
  set**. Named presets (`ncaa_dual`, `grand_slam`, …).
- **Pazzah-style pressure/clutch:** a pressure value per point (game/set/match
  point, tiebreaks) drives a non-linear clutch swing off the `mental` gap.
- (From the parallel agent, merged) a hardcourt **MatchContext** — indoor/
  outdoor/wind/heat/crowd — defaulted so old calls are unchanged.

### Ratings
- **Team Power Index** (`app/rating.py`): TOSS = 40% APR + 40% FQI + 20% oGS,
  opponent-weighted, from simulated dual results. (User-calibrated: a gentle
  SoS nudge, deliberately lossy rather than hard-tiered.)
- **STR** (`app/str_rating.py`): the results-based, recency-weighted player
  rating on the 31–57 band — opponent-anchored match ratings, "what have you
  done lately" decay, ~5-match reliability, ±2.00 exclusion, `converge_ids`
  fixed point.

### Seasons, brackets, data
- `app/season.py`: schedule → fast-sim every dual → standings → conference
  tournaments (autobids) → Power Index. Six universes (D1/D2/D3 × M/W) from real
  conference rosters in `data/ncaa/` (D1 32 conf/366; D2 23/296; D3 43/425).
- `app/bracket.py`: NCAA field selection (autobids + at-large), PI seeding,
  single-elim **dual-match** bracket modeled on March-Madness sims (favorites
  favored, real upsets). Configurable field size (16–128; 32/64/76/96).

### Players, development, recruiting
- Development model (now backed by the parallel agent's rich attributes):
  hidden potential/trajectory + interest-rate tiers (ordinary/late/super), two
  noisy scouting reports (±fog), gem/bust. Calibrated to
  `docs/calibration-tennis-trajectories.md` (top-150 thin margins, ±0.5–3.5 STR
  development window, count-based star tiers).
- `app/juniors.py`: recruit-class generator + National/State/International boards
  with count-based tiers (Blue Chip 25 / 5★ / 4★ / 3★).
- **Persistent rosters + live STR** (`app/ncaa.py`, `app/season.py`): each
  program fields a stable 8-player roster (pids, class years, scholarship vs
  **walk-on**); singles results feed live STR.
- **Multi-season League** (`app/league.py`): graduate → develop → retain
  walk-ons (scholarship promotion) → high-churn bidirectional **transfer portal**
  (stars up to lines 3–6 at powerhouses; buried starters down to play 1–3 or out
  to D2/D3; walk-ons seek scholarships) → intake → re-sim. Each player keeps a
  **career history** (school/class/STR/record per season → transfers visible).

### Web (`app/web/`) + deploy
- Baseline design (tokens/components lifted from the design handoff): Rankings,
  Dual Simulator (setup + scoreboard + win-prob sweep), NCAA Bracket,
  **Recruiting** (boards + tennisrecruiting.net-style recruit profile), **Teams**
  (live-STR roster, SIDEARM-style) + college **player card**, Methodology.
  `generators/majors.py` (~180 real + invented majors) on every bio.
- Deploy: gunicorn/WSGI container, `Dockerfile`/`fly.toml`, and a **GitHub
  Action** that deploys to Fly on push to `main` (web-only workflow). Documented
  why Cloudflare Workers can't host a stateful Flask sim.

## Merge With the Parallel Agent

Both branches diverged from one base; the only file-level conflicts were
`app/development.py` and `app/ncaa.py`. Resolution took the agent's richer
versions as the base and re-applied this branch's additions:
- `Prospect`: kept their rich `current`/`potential`, `traits`, `academic_rating`;
  re-added `walk_on`, `major`, `history`; **reconciled `class_year`** (their int
  ≈ grad_year → this branch's eligibility string `"Fr"/"So"/"Jr"/"Sr"`, which
  league/web depend on); `generate_prospect` gained a `pid` param + `major`.
- `ncaa.py`: kept their `_stable_seed`/`_latent_strength`; replaced their
  anonymous `build_squad` with the **roster-based** one (so the rich Prospect
  model now actually powers college lineups — it didn't on `main`).
Everything else (their `player_attributes.py`, `coaches.py`, match-context
engine; this branch's `season`/`league`/`str_rating`/`juniors`/web) merged clean.

## Determinism / Stability
- No `hash()` for seeds anywhere (process-salted) — `blake2s`/`_stable_seed` and
  string-seeded `random.Random`. Player ids (`make_pid`) are stable across
  develop/graduation/transfer so the STR corpus and career history track a person.
- The League deep-copies rosters so each instance is isolated from the global
  roster cache; caches are reset/primed per simulated year.

## Tests / Verification
- **62 tests pass** post-merge (`pytest`), spanning engine determinism/scoring,
  clutch, STR behaviors, development gem/bust, rosters, league determinism +
  transfer invariants, juniors boards, web routes, and the parallel agent's
  player/coach suites.
- Smoke-verified: `manage.py season|league|recruits|prospects`, all web routes
  (200s), gunicorn boot + `/api/health`, and a multi-season league showing
  development + transfers + career history with a visible school change.

## Known Gaps / Next Work
- **Up-transfer calibration after the merge:** the rich-attribute shift moved the
  STR↔program-level relationship; up-moves dropped (≈0 some years). The portal's
  up-gate (`UP_THRESHOLD`/`UP_SUCCESS`/program-level bar in `app/league.py`)
  needs a light retune so lower-major #1s reliably climb again.
- **Multi-year career view on the web:** the player card's Historical tab is a
  stub (history lives in the League/CLI; the web is single-season). Needs a
  cached League. Match-by-match stats likewise need per-match persistence.
- **Cross-division portal** (D3→D2→D1) — currently single-division.
- **Junior circuits (P6)** to feed the recruit Activity tab; **recruiting economy
  (P7)** — offers, commit prediction, academic fit, and the P5-walk-on-vs-D2-
  scholarship decision (the academic_rating + coach pipelines now on `main` are
  the hooks).
- Reconcile the rankings footnote vs methodology page on TOSS weighting wording.
