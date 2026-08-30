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

contenders = every team not qualified and not on the Specials slate,
             in PRIORITY order — the formula is a priority, NOT a filter:
               1. the eligibility formula:
                    class TOSS rank <= 24        (CHALLENGE_RANK_CUT)
                    OR TOSS >= .700              (CHALLENGE_TOSS_FLOOR)
                    OR district champion
                  — and no losing regular-season record unless the
                  TOSS floor clears it
               2. the rest with a NON-LOSING regular-season record
             — and nobody else: a losing record without the TOSS excuse is
             excluded outright (owner: "i don't want a bunch of losing
             teams playing more losing teams"). Within each tier, the
             Specials' own challenger ranking (`_challenger_key`: reg-season
             pct, wins, ATR tiebreak) — record over TOSS, the owner's call:
             "teams that have good seasons, not just teams that load up on
             TOSS". TOSS survives only inside the formula's gates.

pairing    = best contender vs the WEAKEST selected challenger,
             second-best vs second-weakest, … the seat-holder hosts, no
             rematch repair — the pairing IS the seeding (the Specials' rule)

winner     = holds that challenger seat INTO the State Specials
```

The first draft shipped the formula as a HARD SCREEN, plus a
postseason-entrants-only rule, and framed "a quiet year plays none" as the
feature — and the round almost never fired (the formula finds ~0.5 teams per
class-year). The owner reversed it in review: the round always plays, the
formula decides who goes first. An empty archived arc now means a pool with
no winning-record team left in it (a tiny test world), never a formula with
no takers.

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
- **A losing record is excluded outright** unless the .700 TOSS clears it
  into the formula tier: a class short of winning-record bodies plays fewer
  duals rather than dressing losers — the round exists for teams that had
  good years and simply lost early.
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

What changed, all owner-directed in one review:

1. **Formula → priority.** Contenders are every non-qualified,
   non-slated team, formula tier first, then the remaining winning-record
   teams; the postseason-entrants-only rule is retired outright (it was
   never in the owner's spec).
2. **Record over TOSS.** Within each tier, contenders rank on
   `_challenger_key` — the Specials' own challenger ranking (reg-season pct,
   wins, ATR tiebreak) — "teams that have good seasons, not just teams that
   load up on TOSS". TOSS survives only inside the formula's gates.
3. **Losers stay out.** A losing record without the .700 TOSS excuse is
   excluded, not merely sorted last — "i don't want a bunch of losing teams
   playing more losing teams"; a short class plays fewer duals.

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
