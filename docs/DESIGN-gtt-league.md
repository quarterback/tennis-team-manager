# Design — Global Team Tennis (GTT): a post-college pro league

*Architecture + roadmap. Captures the design worked out in conversation; written
as the build plan for the feature.*

## Build status

- **P0 — the dual** ✅ `engine/gtt.py` (`simulate_gtt_dual`): 3 MS + 3 WS + 3 XD,
  first to 5 of 9, abandon-after-clinch. Mixed doubles run through the real 2-on-2
  `engine.doubles` engine (gender-blind), not the old averaged-pair trick.
- **P1 — the season** ✅ `app/gtt_seasonmode.py`, **forked from `app.seasonmode`**
  and stripped of divisions/conferences/NCAA: a flat league of co-ed franchises
  plays a double round-robin → single-elimination playoff → champion, persisted in
  SQLite. Two deliberate divergences from the college fork:
  - **Franchises are a stored, editable registry** (`gtt_franchises`: name + city +
    abbrev). College programs regenerate from the seed and are never stored; GTT
    teams have user-owned identities that can be renamed/relocated at will.
  - **All seeds and rosters key off the franchise *id*, never its name** — so
    renaming or relocating a team is purely cosmetic and changes no result. This is
    what makes the editor safe.
- **P2 — playoffs** ✅ folded into the P1 fork (top-N single elimination).
- **P3 — honors** ✅ GTT **MVP** (most line wins, win% tiebreak) + **Champion**
  credited to the whole winning roster, derived by replaying the stored line
  results against the deterministic rosters (no schema change). Honors surface on
  the franchise and player pages. *Caveat:* player identity is still
  league-internal (`{league}-{fid}-{m|w}-{idx}`); the real cross-context pid
  linkage (so a GTT title lands on the same career page as the player's college
  honors) waits on the **P5** graduate pipeline.
- **Web UI** ✅ fully wired: a "Global Team Tennis" nav group → **League Hub**
  (create league, advance week / simulate-to-champion, standings, honors, recent
  results), **franchise pages** with the **inline name/city/abbrev editor**, and
  **player pages** with match logs + honors. (`app/web/server.py` routes under
  `/gtt`, templates `gtt_hub` / `gtt_franchise` / `gtt_player`.)
- Next: **P4 STR continuity**, **P5 lifecycle/persistence**,
  **P6 acquisition (Vickrey)** — see roadmap below.

## Context

A co-ed professional team-tennis league bolted onto the existing world clock,
running **after** the college season each year. It is **not** a faithful World
TeamTennis (WTT) reproduction — it borrows the *idea* of mixed-gender team duals
and drops the WTT scoring oddities (cumulative-game match scoring, five fixed
set-configs, supertiebreaks). GTT is scored like any other team sport: each dual
is a team win or loss, and franchises carry season W/L records.

**The real motivation is not the league — it's player continuity.** The point is
to know what happens to players after they graduate and to have a place to keep
favorites around and watch them keep playing. The league is the *stage*;
**player-identity continuity across juniors → college → pro is the actual
feature.** Everything below is in service of that: the same `pid` and one
career arc that doesn't end at graduation.

**Headline finding:** this is mostly reuse, not new construction. The match
engine, season simulation, standings, playoffs bracket, awards/honors pipeline,
Hall of Fame, the editor, and an economy/budget substrate all already exist. The
genuinely new surface is small: a **3/3/3 co-ed dual orchestrator**, an
**acquisition pass** (keeper + draft/auction), and **persisting pro rosters
across the year-end rollover**. Estimated ~80% reuse.

---

## The format — the GTT dual

A GTT dual is **9 lines**, co-ed:

- **3 men's singles** (MS1–MS3)
- **3 women's singles** (WS1–WS3)
- **3 mixed doubles** (XD1–XD3)

First franchise to **5 of 9** lines clinches; the dual records as one team W/L.
This maps almost 1:1 onto the existing `engine/dual.py` (`simulate_dual`, which is
3 doubles + 6 singles): we fork it into `simulate_gtt_dual`, swap the lineup
composition, and change the clinch threshold. It reuses `simulate_match`, the
`MatchFormat` presets, `_pair_player`, `DualLine`/`DualResult`, and `render.py`.

**Mixed doubles is free.** `engine/dual.py:_pair_player` already collapses a
doubles pair into one synthetic `Player` by averaging attributes. A man+woman
pair collapses identically to a man+man pair, and because both sides' XD lines
are built the same way, the matchup is **symmetric** — no cross-gender model is
needed. (A richer doubles model — serve+volley, net play — is a later, optional
build, same as for college doubles.)

**Roster minimum:** to field 3 MS + 3 WS + 3 XD a franchise needs **≥3 men and
≥3 women**, and the XD pairs draw from those same six. The acquisition mechanism
must respect this (see §Acquisition).

---

## The calendar — and the graduate pipeline

GTT runs as a phase **after** college, inside the existing world year:

```
Juniors  →  College  →  GTT
```

This is the keystone idea. `app/world.py` already FINALIZES each year by
graduating seniors — who currently **vanish**. Instead, graduates flow into the
**GTT talent pool**. This does two things at once:

1. Gives graduation *meaning* — it's an entry into the pro pool, not a dead end.
2. Gives the pro league a *source of players with zero new generator* — and it's
   the natural **convergence point** where the six parallel gendered universes
   (D1/D2/D3 × M/W) merge into one co-ed pool.

So "season-to-season portability," the one piece flagged as genuinely hard early
on, becomes a *feature* of the existing year-end boundary rather than a new
subsystem: GTT is a phase that runs at FINALIZE and consumes that year's
graduating classes.

---

## What already exists (reuse — do not rebuild)

| GTT need | Where it lives now | Note |
|---|---|---|
| Week-to-week season sim + standings | `app/seasonmode.py`, `app/web/sim.py` | Reuse wholesale; standings become team W/L |
| Playoffs for *n* teams → championship | `app/bracket.py` | Already seeds a field and **plays the dual each round** (`play_dual → simulate_dual`); handles non-power-of-two via play-ins |
| MVP + title credited to roster + shown on player page | `app/web/awards.py` | `credit_roster()` already stamps team titles onto every roster member; `player_honors(pid)` surfaces them. "GTT MVP" / "GTT Champion" are new labels through the same machine |
| Off-season preservation of a `pid`/profile | Hall of Fame view + `app/honors.py` | HoF index + season stamping exist; add a small manual-enshrine hook |
| Manual player moves | `editor` (`app/web/templates/editor.html`) | User-curated roster edits |
| Mixed doubles synthetic pairing | `engine/dual.py:_pair_player` | Average-attributes pair → one `Player`; symmetric, gender-blind |
| Player STR (UTR-style) | `app/str_rating.py:converge_ids` | Opponent-driven convergence; no population/gender input (see §Rating) |
| Finite per-team budget + allocation | `app/economy.py`, `app/scholarships.py` | Budget/cap/allocate pattern for the auction purse (see §Acquisition) |
| Year-end rollover as pure functions over roster dicts | `app/world.py` | GTT phase hooks the FINALIZE step |

## What is genuinely new

1. **`simulate_gtt_dual`** — the 3/3/3 co-ed orchestrator. Small.
2. **The acquisition pass** — keepers + draft *or* Vickrey auction. The only new
   *subsystem*, and it's a once-per-off-season allocation pass (a pure function
   over roster dicts, in the style `world.py` already uses).
3. **Pro-roster persistence across the rollover** — the one structural change.
   `world.py` deliberately persists very little ("only each year's starting
   rosters and the signing class"). Pro rosters are new persisted state that
   survives the year roll. The acquisition pass *produces* this state, so #2 and
   #3 are the same chunk of work.

---

## Rating — STR yes, rankings no

Pros **keep a computed STR**; they just get **no ranking leaderboard**. This is
exactly how UTR works (a number first; the ranking is a derived sort), and the
code supports it directly:

- `str_rating.converge_ids` takes `pid → [(opp_id, games_won, games_lost)]` and
  solves a fixed point. It is **purely opponent-driven** — no division,
  population, or gender parameter anywhere. Feed GTT singles lines in and STR
  keeps computing with **zero new rating code**.
- **"No pro rankings" = simply never rendering a pro leaderboard.** A ranking is
  a `sorted()` over a population plus a template; omitting it removes nothing
  from the per-player computation or the player page.
- **Continuity is built in.** `converge_ids(..., priors=...)` plus the thin-record
  blend (`raw = reliability*raw + (1-reliability)*prior`) means a graduate enters
  GTT carrying their **college-exit STR as prior**, anchored until they build a
  pro record, then drifting as they play. One continuous rating life across
  college and pro — the continuity payoff, for free.
- **Cross-gender is fine.** STR is a single scale with no gender axis;
  `MAX_DIFF = 2.00` already excludes blowout-gap matches, gender-blind. (Real
  rationale: mixed-level/mixed-gender UTR events happen IRL and rate normally.)

**Open knob — does mixed doubles feed STR?** Singles lines feed cleanly (one real
`pid` per side). XD uses the synthetic averaged pair (no `pid`), so its games
can't drop straight into an individual's singles STR. Options:
- **(a) Display-only XD** — XD doesn't touch STR. Cheapest, defensible.
- **(b) Credit both partners** — each partner takes the XD games vs the averaged
  opponent STR. Easy, slightly hand-wavy.
- **(c) Separate doubles STR** — true UTR analog (UTR keeps singles/doubles
  apart), but a second rating to carry.

Recommendation: ship **(a)** first; revisit **(c)** if doubles identity matters.

---

## Player lifecycle (the continuity engine)

Each off-season, at the GTT phase of FINALIZE:

1. **Intake** — that year's college graduates enter the free pool, carrying their
   final college STR as prior.
2. **Retirement** — a deterministic `x%` of the pro pool retires (age/decline
   weighted). Retirees leave active rosters.
3. **Hall of Fame as the keepsake** — the user can manually enshrine any
   player (active or retiring) into the existing HoF to **preserve their
   `pid`/profile** permanently. This is the curation layer: instead of
   auto-persisting every retired scrub, the user keeps who matters. Reduces
   persistence cost to *active rosters + HoF-curated players*.
4. **Keepers** — each franchise retains a few players across seasons; the rest
   return to the pool for re-acquisition.

---

## Acquisition — keepers + Vickrey auction

Players reach franchises via a once-per-off-season allocation pass. Two
interchangeable mechanisms occupy this one slot:

- **Roto/snake draft** — simplest. Worst record drafts first (or snake). But a
  draft must *enforce* the ≥3M/≥3W roster floor as a hard rule.
- **Vickrey auction (preferred)** — ported from the O27 baseball sim (IPL-style
  second-price sealed-bid; the O27 substrate's "currency / valuation / auction"
  systems are noted as portable in `DESIGN-college-tennis-sim-fork.md`).

**Why Vickrey fits an AI-run league:** second-price sealed-bid makes **truthful
bidding the dominant strategy**, so AI franchises need no bid-shading or
game-theory logic — each bids its honest valuation and the mechanism is robust.
The whole problem reduces to one valuation function: *what is player X worth to
franchise Y?* — with inputs we already have (STR, raw attributes, roster need).

**Gender balance emerges instead of being enforced.** Unlike the draft, the
auction needs no hard roster-floor rule: a franchise short on women simply
*values* female players higher and bids more. Roster construction falls out of
willingness-to-pay — **provided the valuation includes a roster-need term**
(`value = base(STR/attrs) × need_multiplier(roster_gaps) + private_roll`). The
need-multiplier is what makes balance emerge; drop it and a team can roll nine
men again.

**Valuation model (as used in the O27 sim):** deterministic private values — each
franchise rolls a **private valuation from the seed, hidden from other clubs**.
This is a private-values auction, which composes cleanly with Vickrey: the roll
sets each franchise's *own* valuation, and second-price still makes bidding that
valuation truthfully the dominant strategy. The roll is the source of valuation
heterogeneity (so the same player doesn't deterministically land on the same
team every seed), not bid-shading.

**Budget substrate — honest caveat.** `app/economy.py` gives the right
*machinery* (per-team `cap`, `allocate_*`, `budget_summary`, `remaining`), but it
is **fraction-denominated and explicitly currency-free by design** ("a coach does
not spend dollars, they spend fractions of a fixed scholarship allotment"). An
auction purse re-introduces a currency unit that was deliberately stripped here.
So the port is: **reuse the budget/cap/allocate container, redefine the unit**
from scholarship-fraction to purse-currency (or restore O27's currency model,
which the auction originally lived alongside). This is a reinterpretation, not a
drop-in.

**Determinism (sacred in this repo).** Bids must derive from a stable seed —
e.g. `hash(base_seed, season_year, franchise_id, player_pid)` — so re-running the
off-season reproduces identical bids, consistent with how `dual.py` derives
per-match seeds and how season/awards are seed-derived.

**Auction edge cases to specify:** lot ordering (sequential), a "cannot bid above
remaining purse" rule, budget-exhaustion mid-auction, and ties (near-impossible
with continuous private rolls, but define a deterministic tiebreak).

---

## Awards & honors

- **GTT MVP** — a per-season league award via `awards.py`, computed from a GTT
  performance metric (reuse the existing Player-of-the-Year style metric over GTT
  box scores).
- **GTT Champion** — credited to the winning franchise's whole roster via the
  existing `credit_roster()` pattern.
- Both surface on player pages through `player_honors(pid)`, exactly as college
  honors do today — directly serving the continuity goal (a favorite's page shows
  their college *and* pro accomplishments in one career timeline).

## Playoffs

Reuse `app/bracket.py` unchanged in spirit: seed the GTT field by team Power
Index over GTT duals, then play each round as a real dual. `n` playoff teams →
single-elimination → championship.

---

## Open design decisions (taste calls)

| Decision | Options | Default lean |
|---|---|---|
| Acquisition mechanism | Roto draft / Vickrey auction | Auction (balance emerges) |
| Keeper count per franchise | e.g. 2–4 | TBD |
| Retirement rate `x%` per off-season | age-weighted % | TBD; tune for pool turnover |
| XD → STR feed | display-only / both-partners / separate doubles STR | display-only first |
| Purse unit | reinterpret scholarship cap / restore O27 currency | reinterpret cap |
| Season length (weeks) | `x` | match college cadence |
| Playoff field size `n` | e.g. 4–8 | TBD |
| Number of franchises | TBD | TBD |

---

## Phased roadmap

Each phase is independently runnable and testable, mirroring the repo's existing
P0/P1 build discipline.

- **P0 — The dual.** `simulate_gtt_dual` (3 MS + 3 WS + 3 XD, clinch at 5). Two
  hand-built rosters, box-score render, determinism + scoring tests. Pure
  sandbox; nothing wired into the world. *(A weekend.)*
- **P1 — GTT season.** Schedule + week-to-week sim + team W/L standings via
  `seasonmode`. Co-ed franchise roster model.
- **P2 — Playoffs + championship.** Wire `bracket.py` to GTT franchises and the
  GTT dual; seed by Power Index over GTT duals.
- **P3 — Honors.** GTT MVP + GTT Champion through `awards.py`; surface on player
  pages via `player_honors`.
- **P4 — STR continuity.** Feed GTT singles results into `converge_ids` with
  college-exit STR as prior. (Near-free; resolve the XD-feed knob = display-only.)
- **P5 — Lifecycle + persistence.** Graduate intake at FINALIZE, `x%` retirement,
  manual HoF enshrine hook, and **pro-roster persistence across the rollover**
  (the one structural change). Keepers.
- **P6 — Acquisition.** Vickrey auction ported from O27 onto the economy
  substrate (purse-currency reinterpretation), deterministic private-value bids,
  need-aware valuation so balance emerges. (Roto draft as a simpler fallback.)
- **UI** — woven through P1–P6: GTT standings, dual results, franchise pages,
  the auction/draft view, and GTT honors on player pages.

---

## Scope guardrails (explicitly NOT doing)

- **No faithful WTT scoring** — no cumulative-game match scoring, no five fixed
  set-configs, no supertiebreaks. GTT is team W/L.
- **No contracts / free agency / multi-year salaries.** A purse is a one-shot
  per-season spend, not a contract. Manual moves happen in the editor.
- **No pro rankings/leaderboard.** STR is computed but never ranked.
- **No new player generator.** The pro pool is fed entirely by college graduates.
- **No real players.** Generated fictional players only, consistent with the rest
  of the sim.
