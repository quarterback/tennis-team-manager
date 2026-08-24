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
| **Mixed doubles** | A **consolation** event — **one flight, one bracket**, one entry per school from below #9, run **in the summer** |
| **When** | **PRESEASON**, before the league season |
| **Field** | Every school enters its holder of each flight — **no district quota** |
| **Draw** | **One flat 128 bracket** — R128 · R64 · R32 · Octofinals · QF · SF · Final, with byes |
| **Results** | **Full credit** — `records` (ladder) *and* `matches` (awards), like any other match |
| **Awards** | **Included** for the six same-gender flights (zero new code). **Mixed doubles: no awards credit at all** |
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

### ONE FLAT 128 DRAW — no qualifying event

Owner rule: *"NJSIAA runs a 128-person state tournament over several weeks, so JHSAA
can run one too… R128, R64, R32, 8F, QF, SF, F and byes work."*

So there is **no separate qualifying event and no two-tree bracket.** Every school's
flight holder enters one draw; the field (82-107) sits in a 128 bracket and the top
seeds take byes into R64. `engine.run_tournament` produces exactly this natively —
it sizes the bracket to the next power of two and `seeded_draw` places the byes on the
top seeds, so a partial first round is the normal case, not a special one.

Rounds: **R128 → R64 → R32 → Octofinals → Quarterfinals → Semifinals → Final.**

**Cost is identical either way**, which is why the structure could be chosen purely on
how it reads: single-elimination total matches = **entries − 1** whatever shape it is
cut into, so a flat 128 and a qualifying-plus-32 split cost exactly the same. The flat
draw simply needs less machinery — no `_jh_split_state` equivalent, one tree, one page.

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
byes are a large share — 21-46, i.e. a 43-107 match R128 and a full 64 into R64 — but
the team State draw already runs 24-in-32 (33% byes), so this is the association's
existing shape at a larger size.

### If a smaller field is ever wanted

Cost scales with field size only:

| Per-flight field | 6 flights × 18 | + mixed | Total | vs season |
|---|---:|---:|---:|---:|
| **All schools** | 9,792 | 777 | **10,569** | +15% |
| Top 64 | 6,804 | 567 | 7,371 | +10% |
| Top 48 | 5,076 | 423 | 5,499 | +8% |
| Top 32 | 3,348 | 279 | 3,627 | +5% |

No cut is currently applied — the whole field enters the 128 draw. Were one ever
wanted, it must be **statewide by seed**, never per-district; that is the whole point
of the rule above.

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

## Mixed doubles — the consolation event

**‼️ THIS IS NOT A MARQUEE EVENT.** Owner, correcting a draft that offered "each
school's top boy + top girl" as an option: it is *"a consolation event essentially for
all those kids who don't get into the main draw flighted state tournament"* — i.e.
**everyone below #9**, the players the six-flight slate has no seat for.

- **Pool: roster ranks #10 and down**, both genders, same school.
- **Run in the summer** (owner: *"when there are no matches"*). Boys play a fall
  calendar and girls a spring one, so no in-season date has both squads available;
  summer sits after the girls' season and before the boys', the only window where both
  rosters are idle. That is why it works, not merely where it fits.

### ONE FLIGHT, ONE BRACKET, ONE ENTRY PER SCHOOL

**‼️ MIXED DOUBLES IS NOT FLIGHTED** (owner rule). Unlike the main event's six flights,
it is a **single draw**: one bracket per classification per year, **one entry per
school**, 82-95 entries in a 128 bracket with byes — the same shape as one main-event
flight, but it is the whole event rather than one seventh of it.

There is therefore no XD1/XD2/XD3 ladder, and no per-flight seeding question.

The entry is each school's **best available pair from below #9** — its rank #10 boy
with its rank #10 girl. Every roster clears this trivially: `ROSTER_FLOOR` is 16 and
the main draw consumes the top nine, so **every school in the association carries at
least 16 − 9 = 7 players below #9 in each gender**, measured median 8 and never fewer
than 7 across a 25-school-per-class sample of real 2039 rosters. There is no
eligibility edge case to handle.

That depth is worth recording anyway, because it is what a future "more than one entry"
decision would be sized against:

| Class | Girls below #9 (median) | Boys below #9 | Fieldable pairs (median) | Worst case |
|---|---:|---:|---:|---:|
| 9A | 13 | 13 | 12 | 8 |
| 8A | 14 | 12 | 10 | 7 |
| 7A | 11 | 10 | 9 | 7 |
| 6A | 12 | 12 | 10 | 7 |
| 5A | 10 | 8 | 7 | 7 |
| 4A | 10 | 9 | 8 | 7 |
| 3A | 9 | 10 | 7 | 7 |
| 2A | 7 | 8 | 7 | 7 |
| 1A | 7 | 7 | 7 | 7 |

Seven flights would have been fieldable association-wide and would have served the
entire below-#9 cohort — at 5,439 matches against 777, i.e. +21% on the season rather
than +15%. **One entry per school was chosen instead**; the alternative is priced here
rather than re-derived later.

- **Mechanically free.** `engine/gtt.py` already runs mixed doubles (*"one man + one
  woman a side"*) and `engine.doubles` is gender-agnostic, so `simulate_doubles` on a
  (boy, girl) pair works today. The GTT tour is the model; it has simply never been run
  as a tournament.
- **Eligibility: 786 schools sponsor both genders** — every boys' program has a girls'
  program at the same school. 82-95 per classification.

### Cost

**777 matches** (786 eligible schools − 9 classification draws), **+1.1%** on the
season. The cheapest part of the whole event.

---

## Records, ladder and awards — FULL CREDIT

Owner call: *"the easiest implementation is full credit to state matches, treat them
like the regular season + playoffs, easiest idea no fuss."* Correct, and it is not
merely easier — **for the six same-gender flights it is literally zero new code.**

The options, which an earlier draft asserted past instead of presenting:

| Option | Ladder | Awards | Work |
|---|---|---|---|
| **A — full credit (CHOSEN)** | yes | yes | **none** |
| B — records only | yes | no | a records-only path on `_credit` |
| C — neither | no | no | none, but loses the whole point |

Why A is free:

- `_credit` **already** writes both `ts.records` and `ts.matches`.
- `_phase_weight` applies `PHASE_WEIGHT` only `if phase in postseason`, so a new phase
  that is simply *not* in `POSTSEASON` weights at **1.0** — an ordinary match — with
  nothing to configure. "Treat them like the regular season" is the default behaviour.
- The flights price themselves: `FLIGHT_WEIGHTS` already carries **S1 1.00 · S2 0.75 ·
  S3 0.25 · D1 1.00 · D2 0.50 · D3 0.25**, which is exactly the tournament's six.
- Opponents are real players with real pids, so `_q_singles` / `_q_pairs` resolve
  normally.

Option B was the version needing new machinery. Good instinct.

### ‼️ BUT MIXED DOUBLES CANNOT TAKE FULL CREDIT — two concrete faults

`jhsaa_awards.build_pool` is **per gender**, and a mixed pair spans both. Credit an XD
match into `matches` and two things go wrong, neither loudly:

1. **`_weight` silently prices an unknown flight at 0.25** —
   `FLIGHT_WEIGHTS.get(slot, 0.25)`. An `XD3` slot is not in the table, so it takes a
   default nobody chose. This is the same class of fault CLAUDE.md already documents
   for `rating._flight_score` (*"a missing weight is a missing DECISION"*) — except the
   rating path **raises** and the awards copy **defaults**.
2. **A mixed partnership can reach an All-State doubles team with a cross-gender
   partner.** `_pairs` builds EVERY partnership keyed on sorted pids, deliberately
   ungated by discipline, so a (boy, girl) pairing logged in the boys' pool is a
   candidate there. `MIN_PAIR_MATCHES` is 6 and a mixed finalist plays 6-7 matches, so
   this is **reachable, not hypothetical** — and it would put a girl on the boys'
   All-State team. Opponent pids from the other gender also fail to resolve in
   `_q_pairs` and fall back to 0.5, the documented cross-class default.

**‼️ OWNER RULE: mixed doubles gets NO awards credit for anything.** It credits
`records` only — it still moves the ladder, which is the whole point of a consolation
event for depth players — and never enters `matches`. One boolean on the credit call
for one event, rather than the blanket split option B would have imposed everywhere.

That rule is what makes the two faults above moot rather than merely mitigated: an XD
slot never reaches `_weight`, so nothing is priced at a default nobody chose, and a
cross-gender pairing never reaches `_pairs`, so it cannot surface on an All-State team.
**Do not "complete" the integration later** — reversing this needs XD entries in
`FLIGHT_WEIGHTS` *and* a same-gender gate in `_pairs`, and it was declined on purpose,
not left undone.

`jhsaa_awards`'s module docstring currently states that Jefferson has no individual
tournament and none is invented. It must be updated to say the event exists, that the
six same-gender flights **are** an awards input, and that **mixed doubles is excluded
by owner rule** — so a later pass neither "fixes" the omission nor reads the exclusion
as an oversight.

> ⚠️ Known consequence of crediting records: entering and losing early is a small
> ladder *penalty* relative to a teammate who did not enter. At `LADDER_PRIOR` 8 a 1-1
> record moves almost nothing, so this is believed fine — but it is a real effect, not
> a free upside, and it should be measured once the event exists.

---

## ‼️ `_finish_short` IS WRONG FOR A 128 DRAW — fix before shipping

`state._finish_short` bands a finish for the narrow column, and its "Round of N" arm is:

```python
return "QUAL" if (n.isdigit() and int(n) > 24) else "R1"
```

That is correct for the TEAM event and its own docstring explains why — *"every field
converges on the same 24-team main draw at the Octofinals, so a team still alive above
24 went out in the QUALIFIERS… That holds at any field size, which is why this needs no
field parameter."*

**It does not hold here.** A 128 individual draw has no qualifying round and no 24-team
convergence, so under the current function **"Round of 128", "Round of 64" and "Round
of 32" all render as `QUAL`** — a round nobody played — and three distinct rounds
collapse into one label.

This is the recurring shape in this codebase: a helper whose invariant is true for every
existing caller, reused by a new caller for which it is silently false. The docstring
even asserts the field-independence that the new caller breaks.

### The fix, as specified

Owner: *"just needs to change the finish-label logic for individual tournaments so
those rounds display correctly as R128, R64, R32, then R16/OF, QF, SF, F, CHAMP as
appropriate."*

So: **a separate banding for the individual event**, scoped to it —

| Round | Alive | Tag |
|---|---:|---|
| Round of 128 | 128 | `R128` |
| Round of 64 | 64 | `R64` |
| Round of 32 | 32 | `R32` |
| Octofinals (Round of 16) | 16 | `OF` |
| Quarterfinals | 8 | `QF` |
| Semifinals | 4 | `SF` |
| Final | 2 | `F` |
| Champion | 1 | `CHAMP` |

Notes that matter for whoever builds it:

- **`R16` and `OF` are the same round.** The association already says *Octofinals* for
  the team event, so `OF` is the tag; `R16` is only the arithmetic name for it. Do not
  emit both.
- **‼️ DO NOT TOUCH THE TEAM PATH.** `_finish_short`'s `> 24 → QUAL` rule is *correct*
  for the team event and load-bearing there — every team field converges on a 24-team
  main draw, so a team out above 24 genuinely went out in the qualifiers. The bug is
  reusing it here, not the rule itself. The individual event needs its **own** function;
  do not add a field parameter to one whose docstring states it needs none.
- `_FINISH_SHORT`'s named labels (Champion / Runner-up / Semifinalist / Quarterfinalist
  / Octofinalist) carry over unchanged — only the "Round of N" arm differs, and only for
  this event.

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
| Mixed doubles | 777 | 786 eligible schools, 9 classes, one entry each |
| Championship draws | *included above* | the split is free — `entries − 1` either way |
| **Total** | **~10,600** | **+15%** on the ~71,400-match season |

The week-0 rung is currently ~7 minutes for both genders including JV. ~10,600 added
matches should land it around **8–9 minutes** — **an estimate from a match-rate guess,
not a measurement.** Time it before committing; the JV season's +40% was measured, and
this should be too.

---

## Open decisions

1. **Number of seeds.** `run_tournament` defaults to a quarter of the bracket
   (128 → 32). Fine unless a reason appears.
2. **Match format.** The NCAA event uses best-of-3, no-ad, with a 10-point match
   tiebreak as the final set (`INDIV_FMT`). JHSAA play is all no-ad and doubles is a
   full best-of-3, so a decision is needed on whether the individual event keeps the
   match tiebreak or plays a real third set.
3. **Does 1A's 2S/3D pilot touch this?** It should not — the tournament flights are
   defined independently of any dual format — but worth an explicit test.
4. **Round naming on the card.** "Octofinals" is the association's existing word (the
   team event uses it); R128/R64/R32 need labels that read as rounds of one tournament,
   not as a qualifying stage — see the `_finish_short` section above.

---

## Correction on file

An earlier draft of this analysis claimed CHSAA still decides its team championship
from individual tournament points, and flagged that as something not to import.
**That is out of date** — Colorado dropped points-based team titles roughly four or
five years ago, as Oregon did from 2027. The concern is moot: Jefferson crowns its
team champion through the dual-team bracket, and the individual tournament crowns
individuals only.
