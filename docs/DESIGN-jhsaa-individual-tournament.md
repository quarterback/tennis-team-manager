# DESIGN — the JHSAA individual state tournament

Owner spec, 2026-08. **Jefferson crowns individual state champions in each
classification**, at each flight, in both genders — plus a mixed doubles title.
The association has never had one; the college side has had singles and doubles
national championships in every division for years, and this is that structure
ported to high school.

Status: **designed, not built.** This records the decisions taken and the
questions still open, so nothing gets re-litigated or silently re-invented.

---

## The shape, as decided

| | |
|---|---|
| **Format** | **Flighted** — 3 singles + 3 doubles per classification per gender |
| **Flights** | S1 · S2 · S3 · D1 · D2 · D3 (six per class per gender = **108 titles**) |
| **Mixed doubles** | A separate state title, run **in the summer** |
| **When** | **PRESEASON**, before the league season |
| **Field** | Every school enters its holder of each flight — **no district quota** |
| **Draw** | Statewide qualifying rounds → a **32-team championship draw** |
| **Results** | **Credit `records`** (so they move the ladder) |
| **Awards** | **Excluded** — no interaction with All-State / POY |
| **Honours** | Champion gets its own colour tag; OF / QF / SF / F recorded per player |

### Why preseason

Owner's call, and it turns out to be the strongest version of the feature rather
than a scheduling convenience.

1. **It resolves the qualification conflict instead of violating it.** The
   association's hardest rule is that berths are *earned on court* — the TOSS wild
   cards were retired for exactly this. But the college port (`app/individuals.py`)
   selects and seeds purely on **ability**. Run preseason, there are no results yet,
   so ability is the only honest input and nobody is handed something another player
   earned. The rule isn't bent; it doesn't apply yet.
2. **‼️ IT IS A LADDER EVENT, AND THAT IS THE POINT.** Because results credit
   `TeamSeason.records`, they land in `ladder_score` *before the first dual*:

   ```
   ladder_score = ovr + LADDER_SWING × (pct − ½) × n/(n + LADDER_PRIOR)
   ```

   So a sophomore who makes a deep run opens the season ranked above teammates who
   out-rate them on paper, and that propagates through `_order` into who dresses,
   who plays S1, and eventually the frozen Order of Ability. Owner: *"it's good for
   teams to know who is good and it's a great barometer for early season results
   akin to real life."* **An end-of-season individual tournament affects nothing —
   the season is over. A preseason one is an input.** This association had no
   mechanism for the real-life preseason challenge ladder; this is it.
3. **It costs the calendar nothing.** `_JH_SEASON_CLOSE` already squeezes the
   postseason (boys done by end of October, girls early June) and the season-span
   problem has shipped unflagged once. Preseason lands in empty calendar space.
4. **Precedent:** the NCAA individual championships in this same repo are already
   ability-selected and derived, not earned through a season.

> A champion crowned before a ball is struck is **not** a lesser champion — owner,
> explicitly. The NCAA event in this repo works the same way. This is the state
> singles (1st singles) and state doubles (1st doubles) title, full stop.

---

## Field and bracket sizing

### ‼️ NO DISTRICT QUOTA — talent is not evenly distributed geographically

Owner rule, from real OSAA experience: a strong league's third-best player is
better than a weak league's champion, so "top N per league" sends the wrong people.
Every school enters its flight holder; nobody is cut on geography.

This also happens to be **cheaper**, which is counter-intuitive enough to state
plainly. Per-flight fields are **82–107** (see below), so:

| Structure | Qualifying | Championship | Total | vs season |
|---|---:|---:|---:|---:|
| District quota → 32 draw | 8,856 | 3,348 | 12,204 | +17% |
| **Open field, statewide qualifying → 32** | — | — | **10,569** | **+15%** |

A district gate makes every program's matches *extra*, on top of the state draw.
An open field pays for them once.

### ‼️ THE QUALIFYING / MAIN-DRAW SPLIT IS FREE

Single-elimination total matches = **entries − 1**, whatever shape it is cut into. So
"state qualifying rounds feeding a 32-team championship draw" costs *exactly* the
same as one flat 128 bracket. The split is presentation, not cost — which means it
should be chosen for how it reads, and it reads well: it mirrors the team side's
own **"a 40 is a 24 with a qualifiers round in front of it"** (`run_state(champions=)`),
whose bracket page already renders **two trees** (`state._jh_split_state`) precisely
because there is no positional path from a qualifying slot to a main-draw slot.

### Per-flight field, by classification

Every school enters one entry per flight, so the field IS the program count:

| Class | Girls | Boys | Bracket | Byes G | Byes B | Mixed-eligible |
|---|---:|---:|---:|---:|---:|---:|
| 9A | 90 | 82 | 128 | 38 | 46 | 82 |
| 8A | 85 | 83 | 128 | 43 | 45 | 83 |
| 7A | 97 | 84 | 128 | 31 | 44 | 84 |
| 6A | 107 | 92 | 128 | 21 | 36 | 92 |
| 5A | 100 | 88 | 128 | 28 | 40 | 88 |
| 4A | 100 | 95 | 128 | 28 | 33 | 95 |
| 3A | 97 | 87 | 128 | 31 | 41 | 87 |
| 2A | 95 | 89 | 128 | 33 | 39 | 89 |
| 1A | 93 | 86 | 128 | 35 | 42 | 86 |

`engine.run_tournament` already sizes the bracket itself (next power of two, byes to
the top seeds via `seeded_draw`), so a 107-entry field needs no special handling. The
byes are a large share, but the team State draw already runs 24-in-32 (33% byes), so
this is the association's existing shape at a larger size.

### If a smaller field is ever wanted

Cost scales with field size only:

| Per-flight field | 6 flights × 18 | + mixed | Total | vs season |
|---|---:|---:|---:|---:|
| **All schools** | 9,792 | 777 | **10,569** | +15% |
| Top 64 | 6,804 | 567 | 7,371 | +10% |
| Top 48 | 5,076 | 423 | 5,499 | +8% |
| Top 32 | 3,348 | 279 | 3,627 | +5% |

A cut of any kind must be **statewide by seed**, never per-district — that is the
whole point of the rule above.

---

## ‼️ Flight assignment: the S2/S3 inversion does NOT apply here

A trap worth stating, because it would be natural to reach for `_arrange_regular`.

In the **league** 3S/4D format the allocation is fixed and doubles-forward:

```
S1 = rank #1        doubles pool = ranks #2-#9        S2, S3 = ranks #10, #11
```

— so "#2 singles" in a league dual is the tenth-best player. **Do not use that
mapping for the tournament.** Preseason there are no results, no `order_of_ability`
freeze (it binds from the first *postseason* dual) and no lineup to protect, so the
entry list is simply the ability ladder:

```
S1 = #1   S2 = #2   S3 = #3   D1 = #4+#5   D2 = #6+#7   D3 = #8+#9
```

Nine players per school — the same nine the postseason dresses, which is a pleasing
symmetry and not a coincidence. Monotonic in ability, so the flights read the way
every other state's do, and no anti-stacking machinery is needed because there is
nothing yet to stack against.

---

## Mixed doubles

A separate state title, **run in the summer** (owner: *"running mixed doubles state
title in the summer is the best idea when there are no matches"*).

- **Mechanically free.** `engine/gtt.py` already runs mixed doubles (*"one man + one
  woman a side"*) and `engine.doubles` is gender-agnostic, so `simulate_doubles` on a
  (boy, girl) pair works today. The GTT tour is the existing model — it has simply
  never been run as a tournament.
- **Eligibility: 786 schools sponsor both genders**, so every boys' program has a
  girls' program at the same school. 82–95 per classification.
- **Why summer.** Boys play a fall calendar and girls a spring one, so no in-season
  date has both squads available. Summer sits after the girls' spring season and
  before the boys' fall one — the only slot where both rosters are idle, which is
  exactly why it works.
- Cost: ~1,000 matches (777 qualifying-equivalent + 279 championship), **+1.4%**.

---

## Records, ladder and awards

- **Results credit `TeamSeason.records`** — this is what produces the ladder effect
  described above, and it is the main reason the event is preseason.
- **Results do NOT enter `TeamSeason.matches`** — which is what keeps them out of the
  awards. `jhsaa_awards.build_pool` reads `matches` (via `_collect`), so writing
  records only is a one-line separation rather than a filter every award reader has
  to remember. ‼️ `_credit` currently writes **both**; the individual tournament needs
  a records-only credit path.
- **Awards are explicitly out of scope** (owner: *"we can exclude this from awards if
  it's not included currently and adds more complexity, that's easy"*). `jhsaa_awards`
  today states in as many words that Jefferson has no individual tournament and none
  is invented — that comment needs updating to say the event exists but is deliberately
  not an awards input, so a future pass does not "fix" the omission.

> ⚠️ Known consequence of crediting records: entering and losing early is a small
> ladder *penalty* relative to a teammate who did not enter. At `LADDER_PRIOR` 8 a 1-1
> record moves almost nothing, so this is believed fine — but it is a real effect, not
> a free upside, and it should be measured once the event exists.

---

## Honours and surfacing

Modelled on the TOC, which already has its own gold tag distinct from the state
event's green.

- **Individual State Champion** — its own colour tag, third in the set.
- **Per-player finish**, recorded on the profile exactly as team finishes are:
  **Octofinals · Quarterfinals · Semifinals · Final · Champion**, labelled with the
  flight (*"Individual State Champion — 1st Singles"*, *"Semifinalist — 2nd Doubles"*).
  `state._FINISH_SHORT` already bands CHAMP · F · SF · QF · OF · R1 · QUAL and
  `world.JH_STATE_COLUMNS` already renders that set — both reuse directly.
- **Doubles credits BOTH players**, the rule `honors.py` already applies to the NCAA
  doubles title.
- Title board columns and the champions grid will both want the new events.

---

## What already exists

| Piece | Gives |
|---|---|
| `engine.run_tournament` + `seeded_draw` | Arbitrary field size, auto bracket sizing, byes to top seeds. Already shared by the NCAA bracket, the NIT and the JHSAA state draw |
| `engine.simulate_match` / `simulate_doubles` | Individual + doubles matches; gender-agnostic, so mixed needs nothing new |
| `engine/gtt.py` | The working mixed-doubles model |
| `app/individuals.py` | The whole shape — entry dataclasses, `Championship`, `_assemble`, `championship_to_dict`, JSON-blob persistence, **no new phase needed** |
| `state._bracket_canvas` + `_bracket.html` | Bracket rendering, round tabs, and the **two-tree split** a qualifying round needs |
| `state._FINISH_SHORT` / `honors.py` | Finish banding and both-players doubles credit |
| `jhsaa._order` | The preseason entry list, straight off the ability ladder |

Genuinely new: the event's own archive rows, the records-only credit path, calendar
placement, and the flight/entry rules above.

**Persistence.** Not `world_jhsaa_dual` — those rows are duals with team context and
every varsity reader iterates `lines`; an individual match has no team result. Either
a `world_jhsaa_individual` table keyed `(world, year, gender, group, flight)` or the
college JSON-blob pattern (`world_championship`). Unlike the title board this genuinely
must be **stored**, not folded — nothing else can reproduce it.

---

## Cost

| | Matches | Note |
|---|---:|---|
| Six flights, all schools | 9,792 | 82–107 per flight × 6 × 18 class-genders |
| Mixed doubles | 777 | 786 eligible schools, 9 classes |
| Championship draws | *included above* | the split is free — `entries − 1` either way |
| **Total** | **~10,600** | **+15%** on the ~71,400-match season |

The week-0 rung is currently ~7 minutes for both genders including JV. ~10,600 added
matches should land it around **8–9 minutes** — **an estimate from a match-rate guess,
not a measurement.** Time it before committing; the JV season's +40% was measured, and
this should be too.

---

## Open decisions

1. **Mixed doubles entry pool.** Owner suggested *"in lieu of 4th doubles… those kids
   in that pool"*. With three doubles flights covering ranks #4-#9, the D4-equivalent
   tier is roughly #10-#11 in each gender — a depth event. The alternative is each
   school's **top boy + top girl**, which makes it a marquee event instead. Not decided.
2. **Qualifying/main-draw cut size.** 32 is the working assumption; 16, 48 and 64 are
   all free to choose since cost depends only on the field.
3. **Number of seeds.** `run_tournament` defaults to a quarter of the bracket
   (128 → 32). Fine unless a reason appears.
4. **Match format.** The NCAA event uses best-of-3, no-ad, with a 10-point match
   tiebreak as the final set (`INDIV_FMT`). JHSAA play is all no-ad and doubles is a
   full best-of-3, so a decision is needed on whether the individual event keeps the
   match tiebreak or plays a real third set.
5. **Does 1A's 2S/3D pilot touch this?** It should not — the tournament flights are
   defined independently of any dual format — but worth an explicit test.
6. **Naming.** "State qualifying" for the preliminary rounds (owner's phrasing: *"it's
   still state it's just called state qualifying"*).

---

## Correction on file

An earlier draft of this analysis claimed CHSAA still decides its team championship
from individual tournament points, and flagged that as something not to import.
**That is out of date** — Colorado dropped points-based team titles roughly four or
five years ago, as Oregon did from 2027. The concern is moot: Jefferson crowns its
team champion through the dual-team bracket, and the individual tournament crowns
individuals only.
