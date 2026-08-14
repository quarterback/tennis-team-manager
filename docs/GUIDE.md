# Play to Clinch — The Game Guide

*A complete, sectioned reference to how the game actually works: the rules, the
economy, the ladder of systems, and the numbers behind them.*

This is the definitive game document for **Play to Clinch**, a college
dual-match tennis season simulator and team manager. It's written for three
audiences at once, on purpose:

- **You, the player**, who wants to understand what a rule does and why, not
  just where the button is.
- **A future you**, six months from now, who forgot exactly how the
  scholarship economy works and doesn't want to reread forty AARs to find out.
- **An LLM sidecar** — if you want to point an assistant at "how does this
  game work" for a question, a balance idea, or a feature pitch, point it at
  this file. It is the one place meant to answer that question completely.

The same content, formatted for the browser, lives in-app under **Tools →
Guide**. This file is the source of truth; the in-app page is a rendering of
it for players who'd rather not leave the game. Update this file first when a
system changes, then bring the in-app page in line.

**How this differs from `CLAUDE.md` and the `docs/AAR-*.md` files:** `CLAUDE.md`
is guardrails for an editing agent — "don't casually change this number, here's
why." The AARs are the changelog — one report per change, in the order it
happened, with the reasoning and the mistakes. This guide is neither of those:
it's the rulebook, written once, organized by system rather than by when it was
built. **Appendix B** indexes every AAR by topic if you want the origin story
behind a rule.

---

## Table of Contents

**Part I — Getting Started**
1. [What Is Play to Clinch](#what-is)
2. [Starting a League](#starting)
3. [The World Clock](#world-clock)

**Part II — The Competitive Structure**
4. [Divisions, Conferences & Prestige](#divisions)
5. [Dual Match Formats](#dual-formats)
6. [The Season Calendar & the Offseason Ladder](#calendar)

**Part III — Building a Program**
7. [Rosters & Walk-Ons](#rosters)
8. [The Recruiting & Scholarship Economy](#economy)
9. [Scholarship Aid Display](#aid-display)
10. [Coaching & Player Development](#coaching)
11. [The Player Model — STR, OVR & Playstyles](#player-model)

**Part IV — Living Seasons**
12. [Injuries](#injuries)
13. [The Transfer Portal](#portal)
14. [Rankings — the Power Index (TOSS)](#rankings)

**Part V — Championships & Cups**
15. [The Preseason NIT (ITA Kickoff & National Team Indoor)](#nit)
16. [The NCAA Championship](#ncaa)
17. [Singles & Doubles Individual Championships](#individuals)
18. [Davis Cup / Billie Jean King Cup](#cups)
19. [Awards & the Hall of Fame](#awards)

**Part VI — The Wider World**
20. [Jefferson — the 55th State](#jefferson)
21. [The JHSAA — Jefferson's High School Season](#jhsaa)
22. [The Pro Tour (GTT)](#gtt)

**Part VII — Reference**
23. [Quick-Reference Tables](#quickref)
24. [Glossary](#glossary)
25. [Appendix A: Design-Invariant Guardrails](#appendix-a)
26. [Appendix B: Engineering Changelog Index (AARs by topic)](#appendix-b)

---

## Part I — Getting Started

### 1. What Is Play to Clinch <a id="what-is"></a>

Play to Clinch is a single-player, god-mode-friendly tennis dynasty sim. You
run a **world**: every NCAA-style division (D1, D2, D3, D4) across men's and
women's tennis, all evolving together on **one shared clock**. You can coach
one program's roster and lineup directly ("career mode") or simply watch the
whole universe unfold as a spectator — every game still simulates in full
either way.

Matches are simulated point-by-point by a real engine (serve/rally
probabilities, box scores, playstyles), not dice-rolled at the final-score
level. Seasons run on real schedules with conferences, postseason brackets,
recruiting classes, a transfer portal, injuries, coaching carousels, a pro
league, and a whole second sport (high-school tennis) feeding into the
college one. Almost everything is **seed-deterministic** — the same seed
replays the same world — with exactly one deliberate exception: injuries roll
on real entropy, so the health of your roster can never be save-scummed away
by rerolling. Everything else can be, and that's fine — it's a single-player
sandbox, and reproducibility is a feature, not a purity test.

### 2. Starting a League <a id="starting"></a>

`/start` is the onboarding screen. It asks four questions:

- **Which divisions and genders are active.** You can run the whole NCAA
  (D1–D4, men's and women's) or a subset — a smaller active set advances
  faster.
- **A name/region preset and international share.** Controls where players
  come from (which countries and US regions the generator draws from) and
  what fraction of rosters are international. This is cosmetic flavor, not a
  competitive lever — the region weights are just where the generated names
  and hometowns are sampled from.
- **A program to coach, or spectator mode.** Pick a school (division, gender,
  school) to play as its coach — you get a "Your Team" sidebar group
  (Clubhouse, Preseason, Roster, Schedule) and control over its lineup,
  recruiting priorities, and job decisions. Leave it blank to spectate the
  whole world with no team of your own; every division still plays for real.
- **A world seed.** Optional. Leave it blank for a fresh random world every
  time; type one in to get a reproducible universe (the same seed always
  builds the same rosters, same recruits, same everything except injuries).

Starting a new league always throws away the previous save — there is exactly
**one world per save file** (see [§25](#appendix-a)).

### 3. The World Clock <a id="world-clock"></a>

Every active division × gender universe advances **together**, on **one
clock**, behind **one button**: the "Advance week" control in the top bar.
This is a deliberate design constraint, not an accident of the UI: if D1
men's and D1 women's could advance independently, they'd drift to different
weeks with different conference races and nobody would notice until the
numbers stopped making sense next to each other. There is exactly one advance
surface in the whole app.

Clicking it does one of several things depending on where the world is in its
cycle:

- **Most of the time**: plays one week of duals across every active universe,
  runs the cross-division non-conference slate, drips a slice of the season's
  recruiting class, and processes portal decommits/flips.
- **At a fall-portal hold**: instead advances by taking you to review and
  commit the fall transfer portal proposals (see [§13](#portal)).
- **At the end of a season**: steps through the **offseason ladder** — one
  event per click, never bundled (see [§6](#calendar)).

The bar above the button also shows the season number, the calendar year, the
current week, and the game phase, so you always know exactly where the world
is.

---

## Part II — The Competitive Structure

### 4. Divisions, Conferences & Prestige <a id="divisions"></a>

Four divisions, each its own self-contained tournament ladder, run for both
men's and women's tennis:

- **D1** — the top tier. Conferences are tiered (Blue Blood / Major /
  High-major / Mid-major / Low-major) by prestige percentile, not a fixed
  list, so realignment doesn't need special-casing.
- **D2** — a wide middle tier that recruits aggressively and takes players
  D3/D4 can't reach.
- **D3** — the widest-variety, lowest-recruiting-floor tier, with a thin
  "gem" allocation for its top-20 programs by prestige.
- **D4** — an **academic-first** tier carved out of D3's stronger LACs
  (NESCAC/UAA/SCIAC/NCAC-style programs): real academic gates on who a
  program can admit, but a scholarship-budget economy that plays more like
  D1/D2 than like D3.

**Prestige** is a program's standing, and it's **dynamic** — it drifts every
year by how a program over- or under-performs its own expectation. A
low-major that keeps winning above its station climbs the prestige ladder
(and its recruiting budget with it); a sliding blue-blood drifts down. The
drift is bounded and self-correcting, not a runaway snowball, and shows up on
the Data Portal as a program's history over seasons.

**Conference realignment** happens periodically as a world-design decision
(new conferences, programs moving conferences, splits like the Western
Sky/Western Seas division) — these are curated content changes, not something
that happens automatically inside a save.

### 5. Dual Match Formats <a id="dual-formats"></a>

Real college tennis plays 6 singles + 3 doubles (consolidated to one doubles
point) everywhere, for court-availability and Title IX reasons this game
doesn't have to honor. Play to Clinch instead gives **each division its own
shape**, because a bigger singles card is a much better lever for expressing
"how deep does this division's talent actually run":

| Division | Format | Points | Clinch at |
|---|---|---|---|
| **D1** | 10 singles + 5 doubles, doubles **consolidated to one point** | 11 | 6 |
| **D2 / D3** | 8 singles + 3 doubles, **every doubles line its own point** | 11 | 6 |
| **D4** | 10 singles + 3 doubles, **every doubles line its own point** | 13 | 7 |

D1 is the only division that keeps doubles consolidated into a single point —
a deliberate cap on how much a team can win purely by stacking doubles depth.
The engine's own bare-call default (used for the exhibition dual simulator,
cups, and tests) is the classic 6-singles/3-doubles, clinch-at-4 shape; it's
never what an actual division plays a real season under.

Because the singles card is so much deeper than real college tennis, the
recruiting/scholarship economy was **deliberately not resized to match** — a
D1 program's paid recruiting core still only covers six scholarship-caliber
starters (see [§8](#economy)), so courts 7–10 are walk-on and portal depth by
design. A full, deep lineup that thins out toward the bottom is the intended
shape of a D1 roster, not a bug to "fix" by expanding the budget.

**Play-play in D3/D4:** in the regular season and the Preseason NIT, D3/D4
duals play **every singles match to completion** instead of abandoning dead
rubbers once the dual is clinched — real ITA D3 format, and it exists purely
to generate fuller player stats for portal/move-up evaluation. It never
changes who won the dual (the clinching point still locks the result, and the
loser can never catch up past 3 team points) — it only fills in the margin,
so a D3 final line of 6–2 or 7–0 is normal, not evidence of an engine bug.
D1/D2 and all divisions' **postseason** duals stop at the clinch, as usual.

**Postseason lineups are strict best-six:** in conference tournaments and the
NCAA Championship, the healthy top six players by results-based rating start
— no rotation, no resting, no coach-personality noise. The regular season and
the Preseason NIT deliberately keep rotation (everybody plays at some point);
elimination duals do not.

### 6. The Season Calendar & the Offseason Ladder <a id="calendar"></a>

A season plays out over a real calendar shape: non-conference play front-loads
the early schedule (a team's conference duals don't start until it has cleared
its own non-conference slate, typically weeks 4–5), D1 layers **6 preseason
ITA weeks** on top of that, and conference races heat up in the back half. It
is completely normal to see a team with a big overall record and an 0–0 or
2–1 conference record early in a season — that's front-loading, not a bug.

Once every universe reaches the end of its postseason, the world enters the
**offseason ladder** — a sequence of distinct, visible events, each its own
click of the advance button, never silently bundled together:

1. **Awards** — individual and team honors are stamped for the year (see
   [§19](#awards)).
2. **Davis Cup / Billie Jean King Cup** — the national-team cups play over the
   year's rosters, before anyone graduates, so departing seniors get one last
   cup run (see [§18](#cups)).
3. **Year rollover** — graduation, development, recruiting classes signed,
   prestige momentum applied, the world's calendar year advances.
4. **Jefferson's high-school season (JHSAA)** — Jefferson's ~600 high-school
   programs play their entire season in one step, before the next college
   recruiting cycle needs their graduating seniors (see [§21](#jhsaa)).
5. **Pro-league offseason** — GTT drafts the class that just graduated (see
   [§22](#gtt)).
6. **Preseason** — the new college season begins: ITA/Preseason NIT play,
   then a **fall transfer portal** hold once every division has finished its
   opener (see [§13](#portal)), then the regular season.

Each rung is marked done by the real rows it writes (a cup result, a rollover
stamp), not by a hidden flag — so the sequence is always resumable and always
inspectable from outside.

---

## Part III — Building a Program

### 7. Rosters & Walk-Ons <a id="rosters"></a>

Rosters are **not** a flat number — capacity and sourcing both vary by
division:

| Division | Roster cap | Walk-on sourcing |
|---|---|---|
| **D1** | 12 | **None.** D1 never recruits walk-ons; its class tops out at the 6-seat scholarship core and stops. Depth backfills from the transfer portal or runs short — rosters thinning toward ~6–8 players over a program's lifetime is the intended shape of D1 depth, not attrition to fix. |
| **D2** | 10 | From the recruit pool **only**, never auto-generated — "up to" the cap; a program that doesn't sign enough simply runs fewer walk-ons. |
| **D3 / D4** | 16 | Leftover recruit-pool players are placed first (no junior goes unsigned), then any still-empty seats are auto-generated. |

Every division carries a **hard floor**: it must field its own full lineup
card (D1/D4 ten players, D2/D3 eight) at minimum — that floor is enforced at
year-end. "D1 carries no walk-on depth" is about keeping D1 rosters smaller
than everyone else's, never a license to field an unplayable lineup. If a
side does come up short mid-season, the engine degrades gracefully (clamps
court/pairing indices) rather than crashing, and an entirely empty side is
the one condition that stops the world outright.

### 8. The Recruiting & Scholarship Economy <a id="economy"></a>

This is the game's central resource-management system, and it deliberately
diverges from real NCAA rules in several places. The short version: **a
program does not have a flat number of scholarships.** It has a **budget**
(scholarship-equivalent units, set by conference tier) and it **spends** that
budget on recruits, who **cost** scholarships by star rating. The "8" you'll
see on a roster's aid page is a completely separate, downstream **display**
layer — see [§9](#aid-display) — not the actual economy.

**The budget, by tier** (`recruit_economy`; jitter per world, so no two saves
land identically):

| Tier | Budget band |
|---|---|
| D1 Blue Blood | **16–26** (wide — separates blue-bloods from each other; redraws yearly) |
| D1 Major / High-major | 9–16 |
| D1 Mid-major | 6–9 |
| D1 Low-major | 6–7 (the floor, just above D2) |
| D2 | 4–6 (elite D2 at prestige ≥0.28 funds at 6) |
| **D4** | **3–8** — funds a 3 floor / 6–8 top, but only admits recruits above a per-program **academic gate** (~SAT 960 floor up to ~1400 for MIT-tier programs). D2 still out-recruits D4 *on average* (most D4 sits at 3–4) because D2 will take anybody and D4 can't admit everyone it can afford. |
| D3 | **0**, except a thin **1–3 "gem" allocation** for the top 20 D3 programs by prestige. |

Conference tier sets the *starting* band; a program's own prestige sets where
inside that band it lands, and prestige drifts year to year (see
[§4](#divisions)).

**What the budget buys** — recruit cost by star, a steep curve on purpose so
a premium recruiting core is a real investment rather than something every
program can casually assemble:

| Recruit tier | Cost (scholarship units) |
|---|---|
| Blue Chip | 7 |
| 5★ | 3.5 |
| 4★ | 3 |
| 3★ | 2 |
| 2★ | 1 |
| 1★ | free (0) |

**Attainment is gated, not just afforded** — clearing the budget cost isn't
enough to *attract* a tier of recruit; a program also needs to clear a
**floor**: blue chips need ≥16.5 budget (blue-bloods only), 5★ needs ≥10.5
(Major and up), 4★ needs ≥5.0 (any funded D1, or a top D2 — this floor
cascades so 4★ talent always has somewhere to land), and 3★-and-below can go
anywhere. Clustering at the top is earned, not arbitrary: only blue-bloods
land blue chips, majors top out at a 5★/4★ core, mid/low-majors build on
4★/3★, and a low-major will never land a 5★.

**A program's recruiting radar only reaches its own level, mid-cycle** — a D1
program simply never sees a sub-45-strength recruit on its in-season board
(it still *dreams* about D1 like every recruit does — the gate is about
signing-time visibility, not aspiration). D1 chases ceiling/hype in its
evaluation; D2 reads a recruit's current ability; D3/D4 blend current and
potential evenly. D1's class tops up its 6-seat scholarship core and stops —
it never signs a recruit into a walk-on seat. D2 is the one deliberate
exception with a wider reach band, so it absorbs mid-tier talent aggressively
rather than letting it leak all the way down to D3/D4.

**Other realism levers**, each marginal by design:

- **Playing time** matters to a recruit's decision (weight 0.35, below
  prestige's own pull): recruits lean toward programs where they'd realistically
  crack the current top six, and away from where they'd be buried. Shown on
  the recruiting board as a Roster Fit column.
- **Warm weather / big-city appeal** are small tiebreaks (weight 0.06 each) —
  they can nudge a recruit against their home-state pull, never override it.
- **Home-state / regional pull** is the dominant geographic signal.

### 9. Scholarship Aid Display <a id="aid-display"></a>

Separate from the budget economy above: `app/scholarships.py` spreads a
per-division **aid cap** across the recruited roster as full-ride/partial
display fractions. This is what you see on a roster page as "scholarships" —
it's a display of how aid is distributed, **not** what determined roster
quality (the budget economy already did that). Caps: **D1 8.0**, **D2 6.0**,
**D4 6.0**, **D3 0.0** — and, deliberately, **the same cap for men and
women** (not real college tennis's men's 4.5-scholarship equivalency rule).
Don't read this layer as the economy; it's the accounting on top of it.

### 10. Coaching & Player Development <a id="coaching"></a>

Coaches are persistent entities with careers of their own — they take jobs,
get poached, retire, and build a lineage (former players can become coaches).
A coach's **development score** drives how fast their roster's players grow
each year, and the effect is strong: **±30%** on growth, anchored to the
*observed* range of generated development scores (roughly 40–65) rather than
the full theoretical 20–80 scale, so the swing is felt rather than
compressed to nothing. Recruiting is also coach-flavored: a coach's localism
and home-country ties tilt which recruits their program actually lands.
Juniors and pro-tour decline are not affected by coaching — development only
applies to active college rosters.

### 11. The Player Model — STR, OVR & Playstyles <a id="player-model"></a>

Every player carries a rich set of attributes on a **20–80 scouting scale**
(serve power, groundstrokes, movement, mental game, doubles skills, hardcourt
comfort, and more — the game is hardcourt-only, no clay/grass modeling).
Two different numbers summarize a player, and they mean different things:

- **OVR (Overall)** — a static, card-based evaluation of raw talent. It's
  what a scout would write down looking at the attribute sheet. It doesn't
  move based on results.
- **STR** — a UTR-style rating on a distinctive **31–57** scale, solved from
  actual **results**. It's the number that drives seeding, rankings, and the
  Power Index. Two players with identical OVR can carry very different STR if
  one's been winning and the other hasn't.

Pros (the one tier generated above the normal 80-grade ceiling, into a
100-grade headroom) read measurably better than any college player on both
scales — that headroom is exclusive to the pro tier.

**STR ↔ UTR ↔ WTN conversion.** UTR (1.00–16.50) is the upward-facing
real-world comparison; WTN runs the other way (40 beginner → 1 elite pro).
`UTR = 1 + (STR − 31)/26 × 15.5` · `WTN = 40 − (STR − 31)/26 × 39`.
Endpoints are exact; off-anchor values are approximate. (Also in-app:
Analytics Bureau → Lineup Lab, the collapsed "STR ↔ UTR ↔ WTN scale" fold.)

| STR | UTR | WTN | | STR | UTR | WTN | | STR | UTR | WTN |
|---|---|---|---|---|---|---|---|---|---|---|
| 31 | 1.00 | 40.0 | | 40 | 6.37 | 26.5 | | 49 | 11.73 | 13.0 |
| 32 | 1.60 | 38.5 | | 41 | 6.96 | 25.0 | | 50 | 12.33 | 11.5 |
| 33 | 2.19 | 37.0 | | 42 | 7.56 | 23.5 | | 51 | 12.92 | 10.0 |
| 34 | 2.79 | 35.5 | | 43 | 8.15 | 22.0 | | 52 | 13.52 | 8.5 |
| 35 | 3.38 | 34.0 | | 44 | 8.75 | 20.5 | | 53 | 14.12 | 7.0 |
| 36 | 3.98 | 32.5 | | 45 | 9.35 | 19.0 | | 54 | 14.71 | 5.5 |
| 37 | 4.58 | 31.0 | | 46 | 9.94 | 17.5 | | 55 | 15.31 | 4.0 |
| 38 | 5.17 | 29.5 | | 47 | 10.54 | 16.0 | | 56 | 15.90 | 2.5 |
| 39 | 5.77 | 28.0 | | 48 | 11.13 | 14.5 | | 57 | 16.50 | 1.0 |

OVR has no conversion — it's the separate static 20–80 scouting scale, not a
rating.

**Playstyles** are weighted archetype profiles (not flat attribute buckets),
so a serve-and-volleyer's volley moves further than their overhead, and the
league's prevailing "meta" rotates by era — the game's texture shifts across
decades the way real tennis has moved through serve-and-volley, power
baseline, and athletic-defense periods. Doubles-specific archetypes apply an
ephemeral per-match boost that only reaches the doubles lineup, never singles.

---

## Part IV — Living Seasons

### 12. Injuries <a id="injuries"></a>

Injuries are the **one deliberately non-deterministic system** in the game —
they roll on real entropy, not the world's seed. Every other system will
replay identically from the same seed; injuries will not, on purpose ("I
never wanted a deterministic sim… save-scumming is fine, I'm the only
player," to quote the design rule behind it).

Calibration: a base injury rate of 2.5% per dual, scaled by a player's
durability, tuned so **roughly half a starter is hurt at any given moment**
across a program. About **1 in 100** injuries is season-ending; otherwise a
player is out for **1–6 duals**. A season-ending injury triggers a **medical
redshirt** — the player repeats their class year with an `RS-` tag (so
RS-Jr → RS-Sr → a fifth year of eligibility before graduating) that persists
until they finally graduate.

### 13. The Transfer Portal <a id="portal"></a>

The **fall transfer portal** is the only in-season player movement, and it
runs once, right after the ITA opener, as a deliberately **curated**
reshuffle rather than a free-for-all migration:

- Movers ("risers") are picked on **ability**, not early-season results — a
  handful of opening duals aren't enough data to trust. A riser has to be a
  top-2 starter on their current team **and** clear the *median* strength of
  a higher division to be eligible to move up.
- The move is capped at **30 risers per gender** on a fresh world — roughly
  60 total moves, not a mass exodus. A receiving program takes at most one
  riser, so the movement spreads out instead of funneling into a handful of
  blue-bloods; players displaced by an incoming riser cascade down to fill
  the seats that opens up.
- A mover's season splits into two **stints** — their record at the old
  school (frozen at the portal) and their record at the new school for the
  rest of the year (regular season + postseason) — both preserved in their
  career history.
- The slate is **editable**: you can redirect a proposed mover, add one the
  simulation missed, or drop a proposed move entirely before committing.

Outside the fall portal window, the **Recruiting Board**, **Portal Rankings**,
and **My Transfer Targets** pages surface the broader recruiting pipeline —
signings drip across the season rather than resolving all at once, skewed so
higher-ranked recruits commit later, the way real recruiting cycles play out.

### 14. Rankings — the Power Index (TOSS) <a id="rankings"></a>

Every team is rated by the **Power Index**, a composite built from three
weighted components — full formula and methodology at **Methodology** in the
nav (`/methodology`), summarized here:

```
Power Index = (APR × 40%) + (FQI × 40%) + (oGS × 20%)
```

- **APR** (Adjusted Power Rating) — an RPI-style blend of a team's own
  win percentage and its opponents' (and their opponents') win percentage.
  Strength of schedule dominates: beating a strong team means more than
  beating a weak one.
- **FQI** (Flight Quality Index) — how well a team performs at each *flight*
  (each individual singles/doubles position), weighted both by how
  competitively significant that flight is (#1 singles counts far more than
  #4) and by the strength of the specific opponent faced.
- **oGS** (opponent-weighted Game Share) — the share of actual *games* (not
  just flights) a team won, scaled the same way — so a 6–2 flight loss that
  went 49–30 in games reads as more competitive than one that went 50–5.

Flight weights are **per division** — because each division plays its own
dual shape (see [§5](#dual-formats)), the weight table for a D1 ten-singles
card is different from D2/D3's eight, and there is deliberately **no
fallback**: an unweighted flight is a missing decision, not a free 0.3.

Head-to-head results break close ties after Power Index is computed, in two
phases (in-conference within 2 rank spots, then overall within 2%) — enough
to honor a direct result without letting one upset leapfrog a large rating
gap.

---

## Part V — Championships & Cups

### 15. The Preseason NIT (ITA Kickoff & National Team Indoor) <a id="nit"></a>

D1's season opens with a **six-week** preseason event before the regular
season begins (non-D1 gets three weeks): the top 60 D1 teams by prior-year
ranking are snake-distributed into 15 cosmetic four-team **Kickoff
Weekend** sites (seeded 1v4/2v3, two rounds, single elimination); the 15 site
winners plus a top-ranked auto-bid host form a 16-team **National Team
Indoor** bracket. D2/D3 skip Kickoff Weekend entirely and run their own
8-team Indoor straight from the prior year's ranking.

Results here count toward a team's live Power Index and its NCAA
at-large/seeding résumé (never toward conference record, since none of it is
conference play). The Preseason NIT shares the exact same bracket-drawing
machinery as the NCAA Championship page — it's presented as a real
elimination tree, not a separate simplified view, and its seeds are read back
from the persisted draw rather than recomputed live (which would relabel a
week-one bracket every time the ranking moved).

### 16. The NCAA Championship <a id="ncaa"></a>

**Selection and seeding are one score, computed once and locked:**

```
Committee Seed Score = (Power Index rank × 45%) + (ITA points rank × 30%)
                      + (auto-bid tier bonus × 15%) + (last-5 form × 10%)
```

The auto-bid bonus is tiered by conference strength (top conferences ~100
points, mid ~40, low ~12), so a champion from a weak conference still gets a
bid but merit still dominates the score overall. This single score both
selects the at-large field *and* seeds it — selection, seeding, and
bracketing are treated as three separate questions, but only the first two
share this one input.

**Field size:** 96 teams in D1 (the top 32 seeds get a bye; 33–96 play a
within-region play-in round), 64 teams in D2/D3/D4 (no play-in). The field
splits into **four S-curve regions**, dealt serpentine (seed line 1 goes
A/B/C/D, seed line 2 goes D/C/B/A, and so on) so every region carries
balanced overall strength; region champions meet at the national semifinal
stage. Region *names* are purely cosmetic and rotate — they carry no
geography.

**True seeding — no conference separation.** The bracket is never rearranged
to keep teams from the same conference apart, in any division or gender, for
either gender. The only anti-collision rules that do apply are avoiding a
regular-season rematch too early (scaled by how many times the teams already
played) and avoiding two conference auto-bid teams meeting in round one.
Once the field, seeds, and regions are locked, they're always read back from
that lock rather than recomputed — so labels can never drift mid-tournament
even as live rankings keep moving.

### 17. Singles & Doubles Individual Championships <a id="individuals"></a>

Run once a division's team bracket finishes, using the same
seed-deterministic, locked-at-selection contract as the team event:

- **Singles** pools every program's top 2 players and takes the best 128 by
  ability. **Doubles** takes each program's #1 pair plus the best 64 pairs
  overall by doubles rating, played through the real four-player doubles
  engine (not an averaged-pair shortcut).
- **Format:** best-of-3, no-ad scoring, set tiebreaks, with a 10-point match
  tiebreak deciding the third set.
- **Seeding:** only the top quarter of the draw is seeded (32 of 128 in
  singles, 16 of 64 in doubles) — seeds 1 and 2 anchor opposite ends of the
  bracket, deeper seed tiers shuffle among mirrored anchor points, byes go to
  the top seeds, and everyone else draws at random. That's real
  tournament-style seeding, not a fully fixed bracket.

Past champions and runners-up are shown on the singles/doubles pages and the
Hall of Fame, read straight from the year's persisted championship snapshot.

### 18. Davis Cup / Billie Jean King Cup <a id="cups"></a>

National-team knockout cups — **Davis Cup** (men) and **Billie Jean King
Cup** (women) — run every offseason, before the year rolls over, so
graduating seniors get to represent their country one last time before they
leave college tennis. Squads regroup the *entire* current player pool by
country, pulling from **every division at once** — a standout D2 or D3 player
can absolutely make a thin nation's national team.

- Any nation with at least 4 eligible players fields a squad; the field trims
  to the largest power of two (at most 32 nations) by squad strength, with
  the top squads seeded.
- A **tie** is 4 singles (in rank order) plus one doubles rubber (each
  side's top pair), first to 3 rubbers wins — dead rubbers are never played
  out.
- Titles are stamped as real honors onto the player's actual career record,
  under an "INTL" division — so a Davis Cup or BJK Cup title shows up
  alongside a player's college and pro-tour honors on one career page.

### 19. Awards & the Hall of Fame <a id="awards"></a>

**Individual honors** — National/Conference Player of the Year, All-American
(First/Second/Honorable Mention), All-Conference — are computed purely from
**position-weighted wins**, not rating or win percentage:

| Singles line | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Weight | 1.00 | 0.80 | 0.60 | 0.40 | 0.20 | 0.10 |

| Doubles line | 1 | 2 | 3 |
|---|---|---|---|
| Weight | 0.75 | 0.50 | 0.25 |

Wins count at the line a player actually played, from their real per-line box
record — not from the team's overall STR rank. For *national* honors only, a
small résumé tiebreak (team win% plus conference prestige, capped at ±10% of
a player's own score) can lift a player over someone within about 10% of
their score — never over a clearly stronger record.

All awards are gated to the very end of the season (after the NCAA
Championship completes) — there's no "Projected All-American" board floating
mid-season. **Coaches** are persistent entities too, with their own pages;
Coach of the Year (national and conference) follows the same stamping rule
and tracks a coach through job changes.

**Hall of Fame** works differently for the two leagues:

- **College** (`/hall-of-fame`) is a year-by-year **archive** — each
  universe's national champion, national Player and Coach of the Year, and
  singles/doubles individual champions, browsable back through every season
  played.
- **Pro tour (GTT)** is **manual enshrinement** — a one-time, user-triggered
  action from a retired player's page that freezes their attributes, career
  record, and honors into a permanent entry, separate from the college
  archive above.

---

## Part VI — The Wider World

### 20. Jefferson — the 55th State <a id="jefferson"></a>

**Jefferson (JF)** is a fictional alternate-history state (~17.6M people)
standing on real ground across southern Oregon, northern California, northern
Nevada, and western Idaho — the Pacific Northwest's own "what if this had
been a state." It's the 55th entry alongside the real 50 states, DC, and the
territories, and it's treated as an **entirely ordinary** state in every
system: it has its own region ("W" — no special geographic pull table), its
own recruit generation, and its own D1 through D4 college programs.

**Four D1 programs**, in existing conferences — no new D1 league was created
for it: the flagship **University of Jefferson** (Pac-16), **Jefferson
State** (WAC), **Southern Jefferson** (Big West), and **Jefferson A&M**
(CUSA). The **Jefferson Valley Conference** is D2 (8 programs). In total,
Jefferson hosts **39 colleges across D1–D4** — deliberately kept to about
2.2 programs per million people (matching California's density) rather than
the dozen-plus D1 programs a state that size might otherwise "deserve," which
would have broken immersion. A few of Jefferson's colleges are real programs
that stand on Jefferson ground and were simply renamed to keep their own
identity (Oregon Tech → Cascade Polytechnic, Southern Oregon → Siskiyou, and
similar), rather than being invented from scratch.

**Jefferson develops talent; it doesn't hoard it.** Jefferson produces
recruits at a rate matched by very few states (second only to California in
raw numbers) — and most of that talent leaves to play elsewhere, exactly the
way California, Texas, and Florida's talent does in this game. A big in-state
D1 footprint was never the intended way to express "this is a good tennis
state" — a state's *production*, not its retention, is the signal.

Jefferson is otherwise deliberately unremarkable in the systems that would
normally give a region a thumb on the scale: it isn't in the warm-weather
appeal table (it's the Pacific Northwest), it isn't in the local-territory
recruiting boost table (its ordinary regional pull already covers that), and
it isn't in the city-heat weighting table. A real flagship program is never
folded into or renamed as Jefferson — Jefferson adds new ground and takes
some regional publics, but it never absorbs an existing power program's
identity.

### 21. The JHSAA — Jefferson's High School Season <a id="jhsaa"></a>

Jefferson's own high-school athletic association — roughly 335 girls' and 292
boys' programs — plays a **complete season inside this engine**, browsable at
`/jhsaa`, and its graduating seniors *are* Jefferson's entries on the college
recruiting board. It's simulated once per year, in one step, at the very
start of the offseason ladder — before the recruit board needs its output.

- **Two separate format axes.** The dual **shape**: regular season is 5
  singles + 2 doubles, the state tournament is 1 singles + 4 doubles — both
  intentionally odd numbers, so a dual can never tie. The **scoring**: every
  JHSAA match is no-ad, and doubles is a full best-of-3 (not the college
  8-game pro set) — high-school tennis, correctly modeled as its own format
  rather than a shrunk college one.
- **A real double round-robin schedule.** Every district opponent is played
  home and away, so district size sets season length (roughly 22 league
  duals in a 12-team district, ~26 total with non-district games added on
  top). Non-district opponents are matched first by geography (same county →
  area → anywhere) and then by talent, gated to the same classification or
  one apart, so weak programs aren't fed to teams that would blow them out.
- **Seeding runs on TOSS** — the same APR/FQI/oGS composite the college game
  uses, computed over the whole gender at once (crossing classification
  lines, since non-district play does too) and over the regular season only
  (postseason results don't feed back into the seeding that produced them).
- **State qualification is a ladder**, the same shape for every classification
  and both genders: **Sectionals** (every non-protected team; byes/play-ins as
  needed; cuts to 32 — a multi-round Sectionals opens with **Areas**) →
  **Wards** (32→16) → **Regionals** (the 16 Ward champions + 16 protected
  entrants — district champions first, then best cutoff TOSS) → **Zonals**
  (16→8). Three ways into State:
  1. The eight **Zonal champions** qualify automatically, with the privileged
     path: they are the State draw's top seeds, so a 24-team field's eight
     first-round byes are exactly theirs.
  2. A **district champion is guaranteed access** even if it loses in the
     ladder — access, never a bye or a seed. This is a geographic safeguard:
     no district is excluded from State because TOSS dislikes it.
  3. Every remaining berth is **earned on court in the recovery rounds**:
     Regional losers (plus, in 7A, the best-TOSS Ward losers — TOSS buys them
     another chance to *play*, never a berth) enter **Super Regionals**;
     Zonal losers join at **Semi-State**; Semi-State's survivors complete the
     field. Recovery draws avoid immediate rematches with the opponent that
     just eliminated a team, and same-district pairings where practical.
  State is **32 teams in 7A, 24 in every other classification** (no reseeding
  between rounds). The retired wild-card model — top post-Zonal TOSS
  non-champions straight into a 16-team field — is gone precisely because it
  let teams sitting at home out-qualify teams still playing.
  The **Tournament of Champions** is its own event on top of State, reserved
  for the six classification champions.
- **Postseason awards are résumé selections, on the Honors tab.** Per
  classification and gender, in one pass off the **completed** season — every
  dual including the state tournament and the TOC: **State Player of the
  Year**; **All-State First / Second / Third Team** — plus a **Fourth Team in
  7A**, whose talent pool is much larger — then **Honorable Mention**; one
  **All-Region team** per geographic region; and for every district, a
  **District Player of the Year** and one **All-District team**. Every team is
  the same size: **10 singles + 8 doubles teams** — 26 athletes.
  What the selectors weigh, in the association's own order: the player's
  record and how much they played; the **flight** they played it at; the
  **quality of the individual opponents** faced, not just the opposing team;
  **quality wins** over other award candidates; **good losses**, which cost very
  little when they come against elite opposition; **head-to-head** between
  candidates whose résumés are otherwise level; and **postseason matches**,
  weighted up.
  Ability ratings are deliberately *not* an input — no OVR, talent, class year,
  recruit ranking or last season's honours. A great player on a poor team can
  win Player of the Year, and an unbeaten record against a weak slate does not
  automatically beat a strong record against the best in the class.
  **Honorable Mention is a threshold, not a team** — there is no slot count, so
  a deep classification honours a couple of dozen extra players and a thin one
  only a handful, and a good season can miss it entirely. At most **two HM
  selections per school**; the numbered teams have no such cap.

  **Doubles honours go to pairings, not to individual doubles players.** "8
  doubles" means eight doubles *teams* — sixteen athletes. A doubles selection
  is two players who actually competed together, judged only on the matches
  they played **as a team** against other teams, so a player who partnered
  around is a separate candidate with each partner and the record shown beside
  a pairing is the partnership's. Which category an athlete is considered in
  follows **where they actually played** that season, so nobody holds a singles
  slot and a doubles slot on the same team, and no athlete appears twice on one
  team. A team is only as large as the candidates who cleared the bar, so a thin
  region occasionally crowns one pairing fewer rather than honouring one that
  did not earn it.

  **Flight is structural, not a bonus.** A 19–7 season at #1 singles is a bigger
  season than 25–1 at #5, because the #1 spent the year playing every other
  program's best player. So **All-State is a #1/#2 honour** and **All-Region
  reaches #3**; below that a player is selected only on extraordinary evidence
  — a near-perfect record *and* at least one win over somebody who played higher
  up the card. **All-District** broadens further down, because a district is a
  smaller pond, but the hierarchy still holds. Every season archives a **Flight
  check**, visible on the Honors page: how many selections came from each flight
  at each level, and every below-band pick named with its position and record.

  The Honors page itself is four views of one slate — All-State, All-Region,
  All-District and the method — with a dropdown for the classification, one for
  the region and one for the district, so a team can be read (and cited) without
  scrolling past four hundred selections. Every season is archived exactly as it
  was awarded, and the year selector reads it back.
- **A program's record is one continuous number**, not split into "regular"
  and "postseason" halves that could double-count games — the postseason is
  folded into the same season total real high-school and NCAA records use,
  with a separate finish label (state/TOC result) shown alongside it.
- **Program archetypes** are a durable, editable school-level trait —
  `blue_blood` (better talent that clusters at the top of a lineup),
  `development` (ordinary incoming talent that grows into the best seniors
  in the state over four years), `doubles` (a small per-match doubles-only
  boost), and `upstart` (a temporary, expiring multi-year hot streak). These
  represent facilities, coaching tradition, and program culture — not a
  school's classification or public/private status, and never hardcoded to a
  specific school name.

### 22. The Pro Tour (GTT) <a id="gtt"></a>

**Global Team Tennis** is a persistent, multi-season, co-ed professional
league layered on top of the college game, built around one idea: **player
continuity**. A college graduate keeps their real player identity into the
pros, so a college Player of the Year and a later GTT MVP can be the exact
same person, visible on one career page.

- **Format:** 8 franchises, a double round-robin regular season, and a
  top-4 single-elimination playoff. Each **tie** is 9 lines — 3 men's
  singles, 3 women's singles, 3 mixed doubles — first to 5, with every line
  a single no-ad Fast4 set (first to 4, tiebreak at 3–3). Doubles carries far
  more relative weight here than in the college game (a third of every tie,
  versus one point of seven in a dual), so net-game skills matter
  disproportionately more for pro success. A per-date "form" swing
  (roughly −30% to +45% on every fielded player's effective level) keeps
  favorites winning around 70% of ties — high, but with real upset room, well
  short of the college game's ~80%.
- **College → pro pipeline:** every offseason, that year's real graduating
  class is drafted in via a reverse-standings snake draft (5 players per
  gender per franchise: a 3-line starting lineup plus 2 reserves). About 95%
  of intake is D1 talent, with a small D2–D4 slice that has to clear ability
  bars to make the cut.
- **Grad-transfer ("Gr") pros** — players who used a fifth year of college
  eligibility as a pro before turning fully pro — enter through a standalone
  **Pro Round** at the very top of each draft (one pick per franchise, best
  available of either gender); anyone left over retires immediately rather
  than entering the general pool.
- **In-season movement is a waiver wire, not a trade market:** deterministic,
  no RNG, weekly. A club may replace only its weakest reserve, and only with
  a genuine upgrade (at least a 0.40 STR margin) — starters are never at
  risk, and roster churn stays deliberately low.
- **Locked to the college world's clock:** GTT season *i* runs alongside
  college calendar year 2026+*i*, and a class that graduates college in year
  *y* joins the pros for season *y*+1. The pro offseason can't advance until
  the college world finishes that year and auto-triggers once it does — see
  [§6](#calendar).
- **Alumni and Hall of Fame:** retired players stay visible for roughly 12
  years unless they hold an honor, a coaching job, or a Hall of Fame spot.
  Retired players and grads can also become **club coaches**, whose own
  archetype shapes how their franchise develops its roster over time — the
  same continuity idea, one layer up.

---

## Part VII — Reference

### 23. Quick-Reference Tables <a id="quickref"></a>

**Recruiting budget by tier** (see [§8](#economy) for detail)

| Tier | Budget |
|---|---|
| D1 Blue Blood | 16–26 |
| D1 Major | 9–16 |
| D1 Mid-major | 6–9 |
| D1 Low-major | 6–7 |
| D2 | 4–6 |
| D4 | 3–8 |
| D3 | 0 (1–3 gem, top 20 by prestige) |

**Recruit cost by star**

| Blue Chip | 5★ | 4★ | 3★ | 2★ | 1★ |
|---|---|---|---|---|---|
| 7 | 3.5 | 3 | 2 | 1 | 0 |

**Roster caps & walk-on sourcing**

| Division | Cap | Lineup floor | Walk-ons from |
|---|---|---|---|
| D1 | 12 | 10 | never generated (portal only) |
| D2 | 10 | 8 | recruit pool only |
| D3 | 16 | 8 | pool, then auto-fill |
| D4 | 16 | 10 | pool, then auto-fill |

**Dual formats**

| Division | Points | Clinch | Doubles |
|---|---|---|---|
| D1 | 11 | 6 | 5 lines, 1 consolidated point |
| D2/D3 | 11 | 6 | 3 lines, each its own point |
| D4 | 13 | 7 | 3 lines, each its own point |
| CLASSIC (bare engine calls) | 9 | 4 | 3 lines, 1 consolidated point |

**Aid-display caps** (display only — see [§9](#aid-display))

| D1 | D2 | D3 | D4 |
|---|---|---|---|
| 8.0 | 6.0 | 0.0 | 6.0 |

**Power Index formula**

`(APR × 40%) + (FQI × 40%) + (oGS × 20%)`

**Committee Seed Score formula**

`(Power Index rank × 45%) + (ITA points rank × 30%) + (AQ tier bonus × 15%) + (last-5 form × 10%)`

**Injuries**

~0.5 starters hurt at any time · 1-in-100 season-ending · otherwise out 1–6 duals

**NCAA field sizes**

D1: 96 (32 byes) · D2/D3/D4: 64 (no byes)

### 24. Glossary <a id="glossary"></a>

| Term | Meaning |
|---|---|
| **APR** | Adjusted Power Rating — the RPI-style win%/opponent-win% component of the Power Index |
| **CUSA** | Conference USA |
| **D1–D4** | NCAA-style divisions, each with its own dual format and recruiting economy |
| **Dual** | A single team-vs-team match, made up of doubles and singles lines |
| **FQI** | Flight Quality Index — flight-level, opponent-weighted competitiveness |
| **Gr** | A "grad transfer" pro — one season of pro tennis on a college graduate's final year of eligibility |
| **GTT** | Global Team Tennis — the pro tour |
| **JHSAA** | Jefferson High School Athletic Association — the simulated high-school season |
| **NIT (Preseason)** | The season-opening event: ITA Kickoff Weekend feeding the National Team Indoor |
| **oGS** | opponent-weighted Game Share — the games-based component of the Power Index |
| **OVR** | Overall — a player's static, card-based talent rating (20–80 scale) |
| **Power Index** | The primary team rating: 40% APR + 40% FQI + 20% oGS |
| **STR** | A player's results-based rating (31–57 scale), UTR-style, drives seeding/rankings |
| **TOSS** | Tennis Opponent-Strength System — the Power Index's underlying model name, borrowed from oregontennis.org, also used by the JHSAA |
| **Universe** | One division × gender combination — its own independent season and bracket |
| **World** | The whole save — every active universe advancing together on one clock |

### 25. Appendix A: Design-Invariant Guardrails <a id="appendix-a"></a>

The recruiting/scholarship economy, roster caps, dual formats, injury
calibration, and a number of other systems in this guide are **intentional
game-design decisions**, several of which deliberately diverge from real NCAA
rules. If you're an agent (or a person) about to change one of these numbers
because a test looks wrong or a rule looks unrealistic — stop and read
[`CLAUDE.md`](../CLAUDE.md) first. It documents exactly which numbers are
load-bearing design choices, why, and which AAR to read for the full
reasoning before touching them. This guide explains *what* the rules are;
`CLAUDE.md` explains *which ones are not up for a casual rebalance*.

### 26. Appendix B: Engineering Changelog Index <a id="appendix-b"></a>

Every change to Play to Clinch is documented as an **AAR** (after-action
report) in `docs/` — one file per change, with the reasoning, the mistake (if
there was one), and the fix. There are 150+ of them. This index groups every
one by the system it touches, so you can go straight to the origin story
behind any rule in this guide instead of reading them all in date order.

**Divisions, Conferences & Realignment**
- [`AAR-conference-division-restructure.md`](AAR-conference-division-restructure.md) — Conference / division restructure, single-sex fix, HBCU Legacy League
- [`AAR-cross-division-scheduling-NOT-DONE.md`](AAR-cross-division-scheduling-NOT-DONE.md) — Cross-division non-conference scheduling (NOT DONE — deferred)
- [`AAR-d3-d4-play-play-format.md`](AAR-d3-d4-play-play-format.md) — Division III/IV "play-play": D3/D4 finish every match
- [`AAR-d4-academic-realignment.md`](AAR-d4-academic-realignment.md) — D4 academic realignment: lifting stranded elite LACs above D3
- [`AAR-d4-cross-division-guard.md`](AAR-d4-cross-division-guard.md) — Cross-division scheduling: geography- and prestige-gated reach
- [`AAR-division-4-academic-tier.md`](AAR-division-4-academic-tier.md) — NCAA Division IV: an academic-first tier carved out of D3
- [`AAR-division-dual-formats.md`](AAR-division-dual-formats.md) — per-division dual formats: the expanded singles cards
- [`AAR-independent-doubles-lineup.md`](AAR-independent-doubles-lineup.md) — Independent doubles lineup (coach-set pairings)
- [`AAR-meridian-academic-realignment.md`](AAR-meridian-academic-realignment.md) — Meridian "nerdy major" build + academic-school realignment (round 2)
- [`AAR-postseason-best-six-lineups.md`](AAR-postseason-best-six-lineups.md) — Postseason lineups: strict best six (no resting in elimination play)
- [`AAR-realignment-acc-bigten-sec-round.md`](AAR-realignment-acc-bigten-sec-round.md) — Realignment round: ACC/Big Ten/SEC reshuffle, UAA & Yankee rebuild, three promotions
- [`AAR-realignment-bracket-utr-calibration.md`](AAR-realignment-bracket-utr-calibration.md) — Conference realignment, a 96-team D1 bracket, and a UTR-true talent scale
- [`AAR-realistic-schedules-and-realignment.md`](AAR-realistic-schedules-and-realignment.md) — Realistic 25-dual schedules (+ the conference realignment behind them)
- [`AAR-recruit-territory-israel-canada.md`](AAR-recruit-territory-israel-canada.md) — D3 trim, Sarah Lawrence academic move, per-school recruiting territories
- [`AAR-western-sky-seas-conference-split.md`](AAR-western-sky-seas-conference-split.md) — Late conference swap: Western Sky / Western Seas splits + SLIAC / USA South moves

**Recruiting & Scholarship Economy**
- [`AAR-base-roster-nationality-by-level.md`](AAR-base-roster-nationality-by-level.md) — Base-roster nationality by program level (international share + regional bias)
- [`AAR-coach-localism-recruiting.md`](AAR-coach-localism-recruiting.md) — Coach-dictated recruiting: localism, nationality tilt & home-country pipeline
- [`AAR-conference-tier-economy.md`](AAR-conference-tier-economy.md) — Conference-tier economy: re-leveled tiers, tier-keyed budgets, steep costs, D3/D4 gems
- [`AAR-diii-d4-economy-and-recruit-realism.md`](AAR-diii-d4-economy-and-recruit-realism.md) — DIII/D4 economy overhaul + recruiting realism
- [`AAR-dynamic-prestige-momentum.md`](AAR-dynamic-prestige-momentum.md) — Dynamic prestige (YoY momentum from over/under-performance)
- [`AAR-elite-signings-and-schedule-colors.md`](AAR-elite-signings-and-schedule-colors.md) — elite junior signings, play-in de-confliction, conference strength, schedule colors
- [`AAR-fog-of-war-recruiting.md`](AAR-fog-of-war-recruiting.md) — Fog-of-war recruiting (the model it was always supposed to be)
- [`AAR-junior-rankings-doubles.md`](AAR-junior-rankings-doubles.md) — Junior Ranking Points Ledger & Doubles
- [`AAR-name-pool-diversity.md`](AAR-name-pool-diversity.md) — Name pool expansion + country diversity (diaspora names)
- [`AAR-nation-talent-rankings.md`](AAR-nation-talent-rankings.md) — National talent rankings (investment / grassroots)
- [`AAR-nationality-editor-live-percentages.md`](AAR-nationality-editor-live-percentages.md) — Nationality editor: live percentages + the US "multiplier" no-op
- [`AAR-polls-regional-rankings-hometown-territory.md`](AAR-polls-regional-rankings-hometown-territory.md) — Media/Coaches polls, regional rankings, hometown breadth, territory recruiting
- [`AAR-portal-polish-junior-season.md`](AAR-portal-polish-junior-season.md) — Portal polish, badges, scholarships & the 36-week junior season
- [`AAR-recruit-rating-clarity.md`](AAR-recruit-rating-clarity.md) — Recruit rating clarity: the board reads today, not the ceiling
- [`AAR-recruit-redesign-analytics-bureau.md`](AAR-recruit-redesign-analytics-bureau.md) — Recruit-page redesign + Analytics Bureau
- [`AAR-recruiting-board-commit-column.md`](AAR-recruiting-board-commit-column.md) — Recruiting board never showed signings
- [`AAR-recruiting-budget-economy.md`](AAR-recruiting-budget-economy.md) — UTR-true talent + a recruiting budget economy
- [`AAR-recruiting-division-radar.md`](AAR-recruiting-division-radar.md) — Division radar recruiting: D1 never sees sub-level recruits; D3 signs all season
- [`AAR-recruiting-elite-signing-and-division-filter.md`](AAR-recruiting-elite-signing-and-division-filter.md) — Elite recruits weren't signing + signing tracker showed every division
- [`AAR-recruiting-fill-transfer-portal.md`](AAR-recruiting-fill-transfer-portal.md) — Recruiting fill (prestige-aspirational), transfer portal, flip trail
- [`AAR-recruiting-interest-and-commitment-timing.md`](AAR-recruiting-interest-and-commitment-timing.md) — Recruiting realism: interest diversity + commitment timing
- [`AAR-recruiting-juniors-portal.md`](AAR-recruiting-juniors-portal.md) — Recruiting & Juniors Data Portal
- [`AAR-recruiting-prestige-budget-redesign.md`](AAR-recruiting-prestige-budget-redesign.md) — recruiting prestige & budget redesign (incl. academic D3)
- [`AAR-recruiting-realism-and-bureau.md`](AAR-recruiting-realism-and-bureau.md) — Recruiting realism (prestige tiers, star gates) + Bureau usability
- [`AAR-recruiting-signing-pace.md`](AAR-recruiting-signing-pace.md) — Recruiting signing pace (drip across the season, skewed by rank)
- [`AAR-region-mix-editor-weights.md`](AAR-region-mix-editor-weights.md) — Region-mix editor: direct weights (replacing capped multipliers)
- [`AAR-scholarship-economy-and-program-cities.md`](AAR-scholarship-economy-and-program-cities.md) — Scholarship economy, program cities & persisted player origins
- [`AAR-scholarship-full-funding-rule.md`](AAR-scholarship-full-funding-rule.md) — Scholarship caps: I reverted a rule change, then corrected course
- [`AAR-us-state-allocation-guam.md`](AAR-us-state-allocation-guam.md) — Organized US-state recruit allocation + Guam as a US territory
- [`AAR-world-model-flags-recruiting.md`](AAR-world-model-flags-recruiting.md) — International world model, flags & the recruiting board

**Rosters, Talent & the Player Model**
- [`AAR-player-coach-model-foundation.md`](AAR-player-coach-model-foundation.md) — Player and Coach Model Foundation
- [`AAR-power6.md`](AAR-power6.md) — Power 6 (roster strength)
- [`AAR-roster-display-and-conf-abbrev.md`](AAR-roster-display-and-conf-abbrev.md) — full roster in My Program lineup + conference-name abbreviation
- [`AAR-roster-expansion-walkons-recruit-pool.md`](AAR-roster-expansion-walkons-recruit-pool.md) — Roster expansion, walk-on sourcing, and a recruit pool sized to demand
- [`AAR-roster-floor-and-walkon-personas.md`](AAR-roster-floor-and-walkon-personas.md) — a program with fewer than six players crashed the engine
- [`AAR-service-academy-us-only-rosters.md`](AAR-service-academy-us-only-rosters.md) — Service academies roster US citizens ONLY
- [`AAR-str-one-results-stat-ovr-cards-only.md`](AAR-str-one-results-stat-ovr-cards-only.md) — One STR (results-based stat); OVR/attributes are card-only evaluation
- [`AAR-str-semantics-results-only-overall-static.md`](AAR-str-semantics-results-only-overall-static.md) — STR is results-only; OVERALL is the static talent number (two-STR defect)
- [`AAR-talent-compression.md`](AAR-talent-compression.md) — Talent compression + the pro tier
- [`AAR-team-class-ranking-score.md`](AAR-team-class-ranking-score.md) — Team class rankings: rank × STR × star-value scoring
- [`AAR-tenniseye-results-star-rating.md`](AAR-tenniseye-results-star-rating.md) — TennisEye: a results-based second star rating

**The Transfer Portal**
- [`AAR-fall-transfer-portal.md`](AAR-fall-transfer-portal.md) — Fall transfer portal (post-ITA talent reshuffle)
- [`AAR-my-transfer-targets.md`](AAR-my-transfer-targets.md) — My Transfer Targets (Fit Finder, inverted) + team-picker by conference
- [`AAR-portal-batch-edit-paging.md`](AAR-portal-batch-edit-paging.md) — Portal batch editing + settable page size / slate search
- [`AAR-portal-rankings.md`](AAR-portal-rankings.md) — Portal Rankings (transfer-class board, On3/247 style)
- [`AAR-portal-search.md`](AAR-portal-search.md) — Portal Search (searchable placeable pool by hometown / region / class)
- [`AAR-preseason-portal-all-division-scan.md`](AAR-preseason-portal-all-division-scan.md) — Pre-season portal: scan ALL divisions, and the design intent behind it
- [`AAR-preseason-portal-lineup-tables-nit-rename.md`](AAR-preseason-portal-lineup-tables-nit-rename.md) — Pre-season portal, Lineup Lab table rebuild, ITA → Preseason NIT rename
- [`AAR-transfer-realism.md`](AAR-transfer-realism.md) — Transfer realism (division-respecting, one per career)

**Rankings & the Power Index**
- [`AAR-toss-per-division-flight-weights.md`](AAR-toss-per-division-flight-weights.md) — the Power Index had no weights for two thirds of a D1 lineup

**Injuries**
- [`AAR-injuries.md`](AAR-injuries.md) — Injuries: dice rolls on talent + a lever that forces depth

**Championships, Cups & Brackets**
- [`AAR-bracket-projection-seeding-and-juniors-split.md`](AAR-bracket-projection-seeding-and-juniors-split.md) — Bracket projection seeds AFTER selection; juniors National/International split
- [`AAR-committee-seed-reveal-and-zero-point-fixes.md`](AAR-committee-seed-reveal-and-zero-point-fixes.md) — Committee seed score: reveal/sim seeding drift + zero-point résumé spread
- [`AAR-committee-seed-score-and-conference-tiers.md`](AAR-committee-seed-score-and-conference-tiers.md) — Committee Seed Score + prestige-percentile conference tiers
- [`AAR-davis-bjk-cups.md`](AAR-davis-bjk-cups.md) — Davis Cup / Billie Jean King Cup (national-team cups, V1)
- [`AAR-doubles-engine-and-championship.md`](AAR-doubles-engine-and-championship.md) — Doubles Engine, NCAA Individual Championships & Tennis Seeding
- [`AAR-individual-champions-past-winners.md`](AAR-individual-champions-past-winners.md) — Past winners of the NCAA singles & doubles championships
- [`AAR-individual-championship-uncached-recompute.md`](AAR-individual-championship-uncached-recompute.md) — NCAA individual championships recomputed on every request (dead cache)
- [`AAR-ita-kickoff-indoor-opener.md`](AAR-ita-kickoff-indoor-opener.md) — ITA Kickoff Weekend + National Team Indoor (season opener)
- [`AAR-ita-rankings-and-seeding.md`](AAR-ita-rankings-and-seeding.md) — ITA-style rankings (team, singles, doubles) + seeding
- [`AAR-ncaa-bracket-region-drift.md`](AAR-ncaa-bracket-region-drift.md) — the NCAA bracket's regions drifted, and the page was never a bracket
- [`AAR-ncaa-bracketing.md`](AAR-ncaa-bracketing.md) — NCAA bracket: real bracketing constraints
- [`AAR-ncaa-region-seed-display.md`](AAR-ncaa-region-seed-display.md) — NCAA field shown by region seed (1–24 / 1–16), not overall 1–96
- [`AAR-ncaa-seed-power-conference-preference.md`](AAR-ncaa-seed-power-conference-preference.md) — power-conference preference in NCAA seeding
- [`AAR-postseason-and-archives.md`](AAR-postseason-and-archives.md) — Postseason visibility, clarity & season archives
- [`AAR-postseason-record-and-performance-awards.md`](AAR-postseason-record-and-performance-awards.md) — Postseason record, bracket-seed persistence, performance-based awards
- [`AAR-postseason-visibility-and-bracket.md`](AAR-postseason-visibility-and-bracket.md) — Postseason visibility: results browser, real bracket, reveal phase
- [`AAR-preseason-nit-bracket.md`](AAR-preseason-nit-bracket.md) — the Preseason NIT is now the same bracket as the NCAA tournament
- [`AAR-regional-bracket-scurve.md`](AAR-regional-bracket-scurve.md) — Regional (S-curve) NCAA bracket structure
- [`AAR-true-seed-no-conference-separation.md`](AAR-true-seed-no-conference-separation.md) — True seed: no conference separation in the NCAA bracket

**Awards, Honors & the Hall of Fame**
- [`AAR-awards-name-quality.md`](AAR-awards-name-quality.md) — Awards-list name quality (gender pools, junk surnames, list length)
- [`AAR-awards-position-weighted-wins.md`](AAR-awards-position-weighted-wins.md) — Awards select on position-weighted wins (rating removed)
- [`AAR-awards-timing-and-dreamsheets.md`](AAR-awards-timing-and-dreamsheets.md) — Awards gated to season's end + dreamsheet realism
- [`AAR-career-honors-coaches.md`](AAR-career-honors-coaches.md) — Career Honors, Coaches as Entities, Hall of Fame
- [`AAR-program-honors-season-history.md`](AAR-program-honors-season-history.md) — Program Honors & Season Results on school pages

**Coaches**
- [`AAR-coach-career-lineage-and-player-conversion.md`](AAR-coach-career-lineage-and-player-conversion.md) — Coach career lineage and player-to-coach conversion
- [`AAR-coach-careers-and-moves.md`](AAR-coach-careers-and-moves.md) — Coach careers, moves, and the assistant award
- [`AAR-coach-development-growth.md`](AAR-coach-development-growth.md) — Coach development score drives player growth (±30%)
- [`AAR-coach-move-cascade.md`](AAR-coach-move-cascade.md) — Coach "Move to any program" as a Gender → Conference → School cascade
- [`AAR-coach-retire-and-editor-moves.md`](AAR-coach-retire-and-editor-moves.md) — Coach moves in the Editor + Retire
- [`AAR-staff-search.md`](AAR-staff-search.md) — Staff Search (scout coaches by ability, spot HC-ready assistants)

**Jefferson & the JHSAA**
- [`AAR-jefferson-state-integration.md`](AAR-jefferson-state-integration.md) — Jefferson: a fictional US state, its juniors and its colleges
- [`AAR-jhsaa-bracket-score-sides.md`](AAR-jhsaa-bracket-score-sides.md) — the bracket showed the winner losing, and half of it was right
- [`AAR-jhsaa-district-schedule-passes.md`](AAR-jhsaa-district-schedule-passes.md) — a correct double round robin that no high school has ever played
- [`AAR-jhsaa-high-school-season.md`](AAR-jhsaa-high-school-season.md) — The JHSAA: a simulated high-school season inside the college sim
- [`AAR-jhsaa-program-history-and-design-pass.md`](AAR-jhsaa-program-history-and-design-pass.md) — the JHSAA becomes a world surface: program history, and the design pass
- [`AAR-jhsaa-talent-identity-and-toc.md`](AAR-jhsaa-talent-identity-and-toc.md) — what a program IS, and the tournament that proved it wasn't working
- [`AAR-jhsaa-resume-awards.md`](AAR-jhsaa-resume-awards.md) — postseason awards become résumé selections, on a Honors page of their own
- [`AAR-jhsaa-order-of-ability.md`](AAR-jhsaa-order-of-ability.md) — NFHS anti-stacking: the frozen Order of Ability, and the regular season's lineup philosophies
- [`AAR-jhsaa-state-expansion-recovery-rounds.md`](AAR-jhsaa-state-expansion-recovery-rounds.md) — State grows to 32/24 and the remaining berths are earned on court
- [`AAR-jhsaa-upset-variance-recalibration.md`](AAR-jhsaa-upset-variance-recalibration.md) — the hinged gap response, and outcomes that read ability shape

**The Pro Tour (GTT)**
- [`AAR-gtt-add-drop-waiver-wire.md`](AAR-gtt-add-drop-waiver-wire.md) — GTT in-season add/drop waiver wire
- [`AAR-gtt-college-graduate-pipeline.md`](AAR-gtt-college-graduate-pipeline.md) — GTT college graduate pipeline
- [`AAR-gtt-pro-tour-pipeline.md`](AAR-gtt-pro-tour-pipeline.md) — Global Team Tennis: the Pro Tour & the College→Pro Pipeline
- [`AAR-gtt-world-clock.md`](AAR-gtt-world-clock.md) — GTT runs on the college world's clock (lockstep)
- [`AAR-pro-grad-transfers.md`](AAR-pro-grad-transfers.md) — Pros are grad transfers ("Gr"): one season, then gone
- [`AAR-pro-league-parity-injuries-and-development.md`](AAR-pro-league-parity-injuries-and-development.md) — building out the pro league: injuries, development, and club playing styles
- [`AAR-pro-tour-global-mix.md`](AAR-pro-tour-global-mix.md) — "Pro Tour" global nationality mix + international-share dial

**Career Mode, Analytics Bureau & Editor Tools**
- [`AAR-analytics-bureau-stale-rosters.md`](AAR-analytics-bureau-stale-rosters.md) — Analytics Bureau linked to stale rosters; every player click 404'd
- [`AAR-career-coached-lineup.md`](AAR-career-coached-lineup.md) — Career mode: the coached team's lineup reaches the court
- [`AAR-career-history-search-bureau-links.md`](AAR-career-history-search-bureau-links.md) — Player career history, player search, Bureau profile links
- [`AAR-career-job-offers.md`](AAR-career-job-offers.md) — Career mode: prestige-gated job offers (coaching carousel)
- [`AAR-career-nonconf-scheduling.md`](AAR-career-nonconf-scheduling.md) — Career mode: preseason non-conference scheduling
- [`AAR-career-record-boxes.md`](AAR-career-record-boxes.md) — Career record boxes (per-line W-L), singles + doubles
- [`AAR-editor-batch-move.md`](AAR-editor-batch-move.md) — Editor batch player moves (kill the one-by-one friction)
- [`AAR-lineup-architect-and-editor-card-fix.md`](AAR-lineup-architect-and-editor-card-fix.md) — Lineup Architect + editor's stale 6+3 card
- [`AAR-lineup-lab.md`](AAR-lineup-lab.md) — Lineup Lab (Analytics Bureau): every team's singles ladder by conference
- [`AAR-team-scanner.md`](AAR-team-scanner.md) — Team Scanner: cross-division team board, OVR-first
- [`AAR-underplaced-fit-diversity.md`](AAR-underplaced-fit-diversity.md) — Underplaced Talent "FITS" diversity (calibre-band by grade)

**Match Engine, Simulation & Box Stats**
- [`AAR-box-stat-persistence.md`](AAR-box-stat-persistence.md) — Box-stat persistence: real per-match stats without touching outcomes
- [`AAR-dual-concurrent-singles-box-score.md`](AAR-dual-concurrent-singles-box-score.md) — Dual box score: team labels + concurrent singles with partial scores
- [`AAR-engine-box-stat-balance.md`](AAR-engine-box-stat-balance.md) — Box-stat balance: winners, aces, double faults, UE variety
- [`AAR-engine-realism-playing-time-unification.md`](AAR-engine-realism-playing-time-unification.md) — Match Realism, Playing-Time Guarantee, Season-Mode Unification & Staged UI
- [`AAR-engine-seasons-recruiting-buildout.md`](AAR-engine-seasons-recruiting-buildout.md) — Engine, Seasons, Ratings, Recruiting & Web Build-out
- [`AAR-engine-upset-recalibration-and-rating-scale-map.md`](AAR-engine-upset-recalibration-and-rating-scale-map.md) — Engine upset recalibration, realism eval harness & rating-scale map
- [`AAR-point-attribution-winner-error-mix.md`](AAR-point-attribution-winner-error-mix.md) — box scores said a player hit zero winners (and another hit 47)
- [`AAR-talent-engine-calibration.md`](AAR-talent-engine-calibration.md) — Match Engine & Talent/Ratings Calibration

**World Engineering — Saves, Caches, Performance & Infra**
- [`AAR-boot-cache-warm.md`](AAR-boot-cache-warm.md) — boot-time cache warm (stop the crash-on-reload loop)
- [`AAR-bureau-lineup-stale-after-fall-portal.md`](AAR-bureau-lineup-stale-after-fall-portal.md) — Analytics Bureau & Lineup Lab stale after the fall portal (week-only cache stamp)
- [`AAR-cache-invalidation-scope-lineup-stall.md`](AAR-cache-invalidation-scope-lineup-stall.md) — a one-team lineup edit rebuilt the whole world (cache-invalidation SCOPE)
- [`AAR-coach-staff-cache-isolation.md`](AAR-coach-staff-cache-isolation.md) — coach-staff cache stale across registry resets
- [`AAR-cold-prime-loader-health-503-loop.md`](AAR-cold-prime-loader-health-503-loop.md) — Instant loader + health that never blocks on a cold prime (the 503 loop)
- [`AAR-data-portal-sim-integration.md`](AAR-data-portal-sim-integration.md) — Data portal export feed read a phantom preseason season
- [`AAR-editor-roster-overload.md`](AAR-editor-roster-overload.md) — Editor built every roster just to list teams
- [`AAR-export-portal-health-check.md`](AAR-export-portal-health-check.md) — Export-Portal Health-Check Timeout
- [`AAR-new-save-stale-cups-pros.md`](AAR-new-save-stale-cups-pros.md) — new save inherits the prior save's cups & pro leagues (stale players)
- [`AAR-offseason-visible-steps-cups-and-pros.md`](AAR-offseason-visible-steps-cups-and-pros.md) — the cups and the pro league ran invisibly inside the rollover
- [`AAR-one-world-binding.md`](AAR-one-world-binding.md) — One world per save: the seed-matching failure (GTT + World Cups)
- [`AAR-oom-recruit-cadre-memory.md`](AAR-oom-recruit-cadre-memory.md) — Memory & Preseason segment: OOM fix, nationality bands, universe selection, preseason gate
- [`AAR-parallel-generation.md`](AAR-parallel-generation.md) — Parallel world build + junior circuit (use the cores)
- [`AAR-perf-regression-and-power-index-thread-race.md`](AAR-perf-regression-and-power-index-thread-race.md) — ranking-cache perf regression, the power_index thread-race outage, and the infra thrash
- [`AAR-single-gender-world-phase.md`](AAR-single-gender-world-phase.md) — World phase stuck on 'regular' in single-gender saves
- [`AAR-str-cache-race-condition.md`](AAR-str-cache-race-condition.md) — Production 500: race condition KeyError in `season_player_str`
- [`AAR-takeover-hang-loader-salt-keying.md`](AAR-takeover-hang-loader-salt-keying.md) — Team-takeover hang: cold-prime loader must key on the league salt, not a process flag or rowid
- [`AAR-unified-world-session.md`](AAR-unified-world-session.md) — Unified world, recruiting realism, lineups (PR #14)
- [`AAR-universe-desync-season-hub-advance.md`](AAR-universe-desync-season-hub-advance.md) — two advance buttons desynced the universes (women's rankings looked "wrong")
- [`AAR-world-aware-generation.md`](AAR-world-aware-generation.md) — World-Aware Generation & Unified Recruit Class

**UI, Onboarding & Content**
- [`AAR-atp-wta-data-portal.md`](AAR-atp-wta-data-portal.md) — ATP/WTA-style Data Portal
- [`AAR-cta-individual-rankings-census-regions.md`](AAR-cta-individual-rankings-census-regions.md) — CTA individual rankings (national / regional / newcomer) + census-division regions
- [`AAR-logo-backfill.md`](AAR-logo-backfill.md) — Real-logo sweep (every school gets a mark)
- [`AAR-mobile-responsive-recruiting-intl-share.md`](AAR-mobile-responsive-recruiting-intl-share.md) — Mobile responsiveness, recruiting consistency, tunable international share
- [`AAR-onboarding-ui-pagination-awards.md`](AAR-onboarding-ui-pagination-awards.md) — Onboarding, Rename, Pagination, Player History & Awards

---

*This guide is a living document — when a system in the game changes, update
this file (and its in-app rendering under Tools → Guide) alongside the code.*
