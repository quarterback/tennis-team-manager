# AAR — the Special Challengers: a bridge round in front of the State Specials

**Date:** 2026-08
**Status:** Owner rule, 2026-08
**Extends:** `docs/AAR-jhsaa-state-specials.md` (read that first — this round is a
patch on that design, not a replacement)
**Naming (owner):** formally **Special Challengers**; **Challengers** on the
ledger/finish, **CHALLENGE** as the schedule chip.

## Background

State Specials made the Conference winners earn their berths on court against the
best remaining regular-season teams, and the follow-up data (2053–2056, both
genders) says it is doing its job: of the 30 district champions that missed State
in those seasons, 24 at least reached the Specials — the intended last crack.

The same data measured the leak that remained, and it is narrow. Across ~2,990
teams eliminated in Areas/Wards/Sectionals without reaching State:

| "Good team" definition | Early-exit non-State teams |
| --- | ---: |
| Class rank top 16 | 1 |
| Class rank top 24 | 12 |
| TOSS .700+ | 4 |
| Win pct .650+ | 7 |

Widening to everyone eliminated before the Specials (Semi-Conference and
Conference exits included), top-24 profiles rise to ~40 and .700+ TOSS teams to
22 over four seasons. The failure case is a team like 2056 boys Irrigon (2A,
16–8, .720 TOSS, class No. 16) losing once in Wards: the Specials' challenger
side is selected on **regular-season record** (pct → wins → ATR), so a
high-TOSS, high-rank team whose record misses the formula cut has no route back
— the last-chance mechanism never sees it.

So the fix is deliberately narrow too: not a bigger State field, not a
ranking-based rescue, not a loser's bracket. The weakest formula-selected
challenger **seats** are now **defended on court**.

## The rule (owner spec, exactly)

For each classification and gender, after the Conference and before the
Specials (`jhsaa._special_challengers_round`):

```
seats      = CHALLENGE_SLOTS[class] — 2 per class, 4 in the 40-field
             classes (see the cap section). ‼️ A QUOTA: the round convenes
             EVERY season ("there should always be challenger specials")

holders    = the `seats` WEAKEST selected challengers — the teams that
             would otherwise take direct entry to the Specials on the
             challenger formula's last rows

contenders = the `seats` BEST teams outside the pool: the next names down
             the SAME `_challenger_key` ranking that drew the challenger
             cut (reg-season pct, wins, ATR tiebreak — record over TOSS,
             the owner's call: "teams that have good seasons, not just
             teams that load up on TOSS"), from everyone not qualified and
             not already on the slate — with DISTRICT CHAMPIONS taken
             first, ordered among themselves by that same ranking

pairing    = best contender vs weakest holder, second vs second, … the
             seat-holder hosts, no rematch repair — the pairing IS the
             seeding (the Specials' rule)

winner     = holds that challenger seat INTO the State Specials
```

**There are no eligibility gates, and that is load-bearing.** The round has no
conditions of its own: two ranked lists, meeting in the middle.

**The one priority: district champions.** A champion that lost early is
reconsidered here ahead of the rest of the field (owner rule 2026-08) — and
that, with the PROTECTED Regionals entry and their existing first tier in the
Semi-Conference pool, is the whole of what a district title buys. Still never
a berth: they take a contender seat, and they have to win the dual. It is a
priority and not a gate, so once the champions are used the seats carry
straight on down the ranking. Being in this pool already means the champion
did not qualify and holds no Specials seat, so "lost early" needs no test of
its own — adding one would put a gate back.

**Zero extra berths.** The Specials field is the same size with the same bids;
Conference winners are untouched; a bridge winner still has to win its Special.
The design distinction from the parent AAR holds one level down:

- **Specials = the final State bubble.**
- **Special Challengers = access to a seat on that bubble.**

## Why 2, and why 4 in the 40-field classes (owner rationale, 2026-08)

The default cap is two contested seats per class because the early-exit
recovery problem is rare in most classes. The 40-field classes carry four,
because the wider valve is a property of the BIG-FIELD SHAPE, not of any
named class: a 40 Conference sends 14 teams to the Specials against the
32-shape's 6, so its formula-selected tail is both longer and softer — the
largest and noisiest bubble pools in every Specials audit, the highest
concentration of low-ranked entrants and credible early-exit misses. The
higher cap is a targeted correction for that boundary volatility, not a
general expansion of the postseason.

The session's own field retunes proved the rule by moving it twice: 3A/4A
carried the 4 while they were the 40-field holdouts, dropped to the standard
2 the moment their fields came down to 32 ("3A/4A can match the rest of the
state with only the 2 worst qualifiers"), and 8A/9A inherited the 4 when they
went back up to 40 ("they can inherit the 4 state challengers spots that
3A/4A had"). If a field size moves again, move the cap with it.

The design goal is **proportional correction, not symmetry**:

```
2 = normal recovery valve
4 = expanded recovery valve for the classes with the dirtiest bubble
```

If every class got 4, the bridge would contest too much of the Specials field
in classes where the data showed one or two meaningful stranded teams across
seasons — heavier than the problem, and in a 24-shape class (4 bids) it would
put the ENTIRE formula-selected side up for grabs, tilting the Specials'
regular-season currency back toward TOSS. If every class got 2, 3A/4A would
keep their edge-field problem: more low-end qualifier noise, more room for a
good-but-stranded team to fall through. The round is supposed to test the
softest part of the qualification model, never rewrite it — the caps protect
that, alongside the untouched berth arithmetic and Conference winners.

## Deliberate boundaries

- **Conference winners' seats are never contested.** They earned their Specials
  entry on court through the whole ladder; the formula-selected side is the one
  a contender may contest.
- **A weak team never reaches a seat in practice, without a rule saying so.**
  The contenders are the BEST teams outside the pool by construction, so in
  any real class the seats land on good teams that lost early — which is what
  "i don't want a bunch of losing teams playing more losing teams" asked for.
  A sub-.500 exclusion was tried as the instrument and was the wrong one (see
  the addendum); do not re-add it.
- **The seat count never grows** — contenders compete for the existing
  weakest seats; the Specials field and bids are untouched at every setting.

## Wiring (a phase is the archive's identity for an event)

- New phase **`special_challenger`**, in `jhsaa.POSTSEASON` between
  `conference` and `state_special` — which for free gives it: 1S/4D (2S/3D in
  1A, whose road plays the pilot shape), the order-of-ability freeze,
  exclusion from the cutoff TOSS and from `_reg_season_record`, inclusion in
  the prestate recomputes (its duals ARE part of the pre-State results graph,
  like the Specials'), the awards `PHASE_WEIGHT`, and its calendar-lane slot.
- `_select_challengers` is split out of `_state_specials_round`, which now
  takes the (possibly contested) challenger list as a parameter.
- Archived per group under `special_challenger`; readers `.get` it (pre-2056
  archives carry no key). Duals numbered statewide
  (`renumber_special_challenges`, "Challenge N" — the Specials' pattern).
- Finish string **"Challengers"** for both losers, superseding the rung that
  sent them in; `jh_road_ladder` ranks it between Conference and Specials.
  Title board column **CHAL** (a Challenge win is a contested seat, never a
  berth). Schedule chip **CHALLENGE** (`web/state.py::_KIND`).
- The bridge arc joins the emergency `_state_specials` stage walk, so its
  losers are latest-eliminated bodies if the field still runs short.
- Seeded on **blake2s**, not `hash()` — the sibling seeds' `hash(group)` is
  the acknowledged wart this module is told not to copy.

## Lessons

- **The bridge decides who holds a seat, so it must run BEFORE the Specials
  selection is consumed** — which forced the challenger selection out of
  `_state_specials_round` into `_select_challengers`. A round that reorders
  another round's inputs cannot live downstream of it.
- **"Special entrants" needed narrowing.** The spec said the N weakest
  entrants; contesting a Conference winner's seat would have broken the
  parent AAR's `bids = len(conference_winners)` arithmetic and the "a team
  that survives Conference has earned the right to play for State" principle.
  The formula-selected side is the challengeable one.
- **The measured caseload (≈a dozen meaningful rescues over four seasons) is
  what the FORMULA answers, not what the ROUND is sized to** — see the
  addendum below, where reading it the first way shipped a round that almost
  never played. Track the parent AAR's follow-up metrics, plus how often a
  bridge winner then wins its Special and how often the seats go to tier-2
  (non-formula) contenders.

Pinned by `tests/test_jhsaa_special_challengers.py`;
`tests/test_jhsaa_state_specials.py` carries the refactored call shape.

## Addendum (2026-08): the always-convene reversal, and the misread behind it

The round shipped, rendered nowhere, and the owner asked why the Road to
State showed no Challenges. The answer was not a wiring gap — every surface
carried the round — but the design as first built: the eligibility formula
was implemented as a **hard screen**, with an invented
**postseason-entrants-only** rule on top, and the AAR proudly filed "a quiet
year plays none (the usual case)" as the feature. By the audit's own numbers
the screen finds ~0.5 teams per class-year, so nearly every archived arc was
empty and the fold correctly hid an unplayed stage. The owner's actual
design: **"there should always be challenger specials"** — the round convenes
every season in every class, and the formula decides who gets the seats
FIRST, not whether anyone gets them.

What changed, owner-directed across two reviews:

1. **Formula → priority, then gone entirely.** The first correction made the
   formula a priority tier over the remaining winning-record teams and
   retired the postseason-entrants-only rule. That still was not the spec:
   the round *again* fired in some classifications and not others, and the
   owner cut the last gates — "just leave it to anyone who qualifies … it's
   not as conditional as you kept gating it to be."
2. **Record over TOSS.** Contenders rank on `_challenger_key` — the Specials'
   own challenger ranking (reg-season pct, wins, ATR tiebreak) — "teams that
   have good seasons, not just teams that load up on TOSS."
3. **No sub-.500 exclusion either.** It was added to honour "i don't want a
   bunch of losing teams playing more losing teams" and it was the wrong
   instrument: see the measurement below. The ranking already answers that
   concern, because the contenders are the *best* teams outside the pool by
   construction.

### The measurement that ended the gates (2058 export, both genders)

| class | Conference | **Challenges** | Specials |
|---|---:|---:|---:|
| 1A, 2A, Group 3 | 4 | **2** (1 in 1A boys) | 4 |
| 6A girls | 6 | **2** | 6 |
| 3A, 4A, 5A, 7A, Group 1, Group 2 | 6 | **0** | 6 |
| 8A, 9A | 14 | **0** | 14 |

The pattern has nothing to do with class quality and everything to do with
arithmetic: **`_select_challengers` already takes the best non-qualified
teams by record, so the pool BEHIND the challenger cut is the weak tail of
the class by construction.** In a 32-field class, 32 qualifiers + 6
Conference winners + 6 challengers account for the top ~44 of ~70 programs;
what is left is the bottom third, which in a round-robin league is sub-.500
almost by definition. So the sub-.500 screen emptied the contender pool
outright in the big classes, while the 24-field classes (fewer teams
qualified away, only 4 challengers taken) still had winning-record teams
spare. **A gate stacked on top of a ranking that already sorts for quality
can only remove bodies — it cannot improve the selection.**

The misread, named so the next design pass does not repeat it: the spec's
tight eligibility screen and its "solving maybe a dozen meaningful cases"
framing were read as **sizing the round** (fire rarely, only for the
measured victims), when they actually **sized the privilege** (who gets
first claim on seats that are contested every year). A cap was turned into
a trigger. The tell was available from the start — the owner's own summary
said the Specials "get the intended final shot" language about a round that
runs every season — and the cheap check was to ask one question: *"should a
class-year with no formula-eligible team play this round at all?"* When a
new round's convening condition is inferred rather than stated, ask it
before shipping; a stage that silently never plays looks identical to a
stage that was never wired, and costs a debugging pass to tell apart.

Seasons archived before the reversal keep their empty arcs — an archive is
the record of what was played, and the fold hiding an empty stage is
correct for them.
