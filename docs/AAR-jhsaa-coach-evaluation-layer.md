# AAR — the JHSAA coach evaluation layer (owner rule 2026-09)

## The report

> "I have seen too many instances of seniors with pedigree getting bumped by
> freshmen and that's just not realistic even if there's a small talent difference,
> we have to rate records and performance ahead of ratings at the high school level."

And, separately:

> "I still see rare instances of teams having high OVR players who don't get into
> the lineup for some reason … there must be something in the selection."

Two reports, and only one of them was a selection problem.

## The second one first: it was injuries, not selection

Swept the owner's 2075 export, all 877 boys' programs, for anyone in his team's top
nine by OVR who dressed for under a quarter of its duals. **Seven cases.** Every one
has the same signature — a contiguous block of duals at the start of the season, then
silence (Vermillion's Lucas Cheung, OVR #2 on his roster: five duals, all in the first
week, then nothing for the remaining thirty).

Across the whole gender, **152 of 13,005 players (1.2%)** show that pattern, against
a predicted **~0.9%** from `injuries.BASE_RATE` (0.025/dual × 1-in-100 season-ending ×
~35 duals). That is the match, and there is no residual to explain.

‼️ **The reason it did not read as an injury is that `jhsaa.py`'s own JV-section
comment still said "with no injuries or fatigue in this association"** — written
before injuries landed (owner rule 2026-08) and never corrected, at the top of the
first place anybody reads about who dresses. Corrected. **A stale comment in a
load-bearing explanation costs a diagnosis**, and this one cost the owner a bug
report on working code.

## The first one: what was actually happening

`TeamSeason` is rebuilt every season with an empty `records`, so before the first dual
`_order` had exactly one input — ability. Every returning player, however long he had
held his seat, was re-ranked from scratch against an incoming freshman class the coach
had never seen play.

Measured across the owner's real 2072 → 2075 saves, both genders, three season
transitions:

| | |
|---|---:|
| returning varsity regulars per year (12+ appearances) | ~6,500 |
| …who fell under half their team's duals the next season | ~7% |
| …who essentially lost their place (<25%) | **~3.7%** (≈240/yr) |
| …of those, juniors and seniors | ~75% |
| **median OVR the displaced player was short of his team's 11th man** | **3.0** |
| p25 / p75 / p90 of that gap | 2 / 6 / 9 |
| displaced players with ≥1 newcomer now above them | **98%** |

So seats were changing hands on two or three rating points, decided entirely by who
walked in the door. That is the "small talent difference" in the report, quantified.

Recovery curve, from the same distribution — the share of displaced veterans put back
inside their team's top eleven if the coach's view of a proven player is worth N OVR:

| +2 | +3 | +4 | +5 | +6 | +8 | +10 |
|---:|---:|---:|---:|---:|---:|---:|
| 40% | 53% | 65% | 75% | 81% | 90% | 95% |

## The first design, and why it was wrong

The first cut was an **incumbency bonus**: three tiers of prior-season standing worth
(3, 5.5, 8) OVR, added inside `ladder_score`, scaled by a per-program `veteran_bias`.

It produced the right numbers and it was the wrong abstraction, and the owner said so:

> "Do not call it an incumbency bonus in the model. Make it a coach evaluation layer
> that sits between raw player ability and lineup selection."

The difference is not cosmetic. A bonus is a thumb on a talent ranking — it says the
ranking is right and we are distorting it. A coach evaluation says the ranking was
never the thing being computed: **`_order` is not a talent ladder, it is one person's
judgment of who is useful to him**, and that judgment can be wrong without any rating
being wrong. Once the layer exists, incumbency is not a special case bolted on; it is
just one of the things a coach knows.

```
RAW ABILITY  →  COACH EVALUATION  →  LINEUP SELECTION  →  MATCH ENGINE
                                                          (raw ability)
```

The separation is what buys realistic lineup **mistakes** without corrupting the
ratings — and it is what turns coaching quality from a cosmetic attribute into a
mechanic.

## What shipped

`coach_eval(p, record, *, prior, lens, read)` — replacing `ladder_score`, which was
renamed rather than kept beside it (two names for one concept is how this file's
vocabulary drifts). Four inputs:

- **Ability lens** — `current_overall()` plus a per-coach, per-player misread, drawn
  once per season and **stable within it** (redrawn per dual it would be a lineup that
  flickers, not a coach with an opinion).
- **Recent form** — the existing `LADDER_SWING` term, now weighted by the coach,
  because chasing form is a coaching flaw rather than a constant.
- **Varsity proof** — `PriorSeason`: appearances, postseason starts, an individual
  state draw, an award, and how many consecutive years of it. Three tiers
  (contributor / established / decorated) worth (3, 5.5, 8) OVR at full strength.
- **Experience** — `PROOF_GRADE` scales proof by class year, so a senior's two years
  outweigh a sophomore's one, and a ninth-grader scores zero by construction.

**One coach-quality draw drives all three weights** (`coach_lens`, seeded on the
school alone, durable). That was deliberate: the failure modes the owner listed —
misreads ability, sticks with incumbents too long, chases recent results — are the
*same* failure. A coach who cannot read a roster leans on the things he can read. One
variable, three consequences, rather than three unrelated knobs.

Proof **decays toward `PROOF_FLOOR` (0.35), never to zero** (the `program_level_floor`
idiom): it gets a returning starter into the September lineup, and by October his own
results are carrying him — but a coach never fully forgets.

## The properties that matter, and why

**It is a displacement threshold, not a reserved seat.** Nothing is excluded from
anything. Because the whole thing is an *ordering*, a genuinely better newcomer is not
held back: he enters at his own rank and everyone below him shifts down exactly one
seat, which is what happens to a real team when a real player walks in. What stops
happening is a proven No. 5 falling to No. 15 because four newcomers are one to three
points better.

**Nobody is advantaged, because every coach evaluates.** The selection *rule* changed
association-wide; it is not one program's entitlement. The owner made this point
before the code was written and it is the reason no balancing was needed anywhere.

**‼️ The misread shrinks with evidence (`READ_PRIOR`), and that is an anti-ratchet
guard, not decoration.** A persistent negative misread would bury a player for a
season in exactly the way the win-COUNT ladder used to (see `LADDER_SWING`'s note):
ranked low, so never dressed, so nothing ever corrects the coach. The bench rotation
(`_ROTATE_ONE`) and rest staffing put him on court anyway, and from his first match
his own results start outweighing the first impression.

## Two components deliberately NOT in the ordering

The owner's model also listed role fit and leadership. Both belong in this layer
conceptually; neither can ride on `_order`.

**Role fit (doubles suitability, partnership quality)** — three existing rules forbid
it:

1. the 3S/4D allocation is **fixed** (owner rule 2027-08): S1 is the top seed, the
   doubles pool is exactly #2–#9, S2/S3 are exactly #10–#11. A coach chooses
   *pairings*, never who plays singles;
2. the postseason Order of Ability is an **anti-stacking** instrument — weighting it
   by doubles value is close to the thing the rule exists to forbid;
3. `jhsaa_individuals.entry_sheet` reads `_order`, so a doubles specialist would be
   entered at No. 1 **singles**.

Role value already lives where it is legal — `doubles_rating`, `partner_chemistry`,
`_established_units`, `_sibling_units`, in the arrangers. What is genuinely missing
there is **cross-season pair continuity** (the owner's A/B/C example: a 62 with no
chemistry should not break an established 59/58 pair). That needs `pair_counts` seeded
from last season, which reverses `TeamSeason.pair_counts`'s documented
"season-scoped by construction" note — so it is its own change, kept separate so this
one can be measured cleanly.

**Leadership / captaincy** — a captain should be *selected* through this layer and
then be worth a small team-level composure effect in close duals, never an OVR boost.
That is an engine change. Not built; noted at the constants.

## The store

`world_jhsaa_standing` — one row per program per season, `{pid: [apps, wins, losses,
rank, flags, years]}`, only for players who finished the year carrying proof.

‼️ **It is the only per-player thing the JHSAA persists, and it had to be.** A player
is otherwise regenerated from (school, gender, entry year, seat) and a whole career is
derived on demand — but "how many duals did he dress for" is a fact about a season
that was *played*. The only other place it exists is `world_jhsaa_dual.lines`, which
archives **names, not pids** (so a name is not an identity), and folding a gender's
~10k duals to answer it per roster is the query storm this repo has already paid for
twice.

Read as **one indexed query per gender per season**, resolved at the top of
`run_jhsaa` and threaded down through `district_teams` — never per program, never per
player. Flattened to `{pid: PriorSeason}` on read rather than kept per school, so an
owner-authored transfer carries the record the player earned, which is the answer a
coach would give about a junior who started two years somewhere else.

‼️ **The memo key had to grow.** `run_season` is memoised, and last season's evidence
moves every ladder in the association — keyed without it, a save would serve its first
year's no-memory season to every year after. Digested with `blake2s` (never `hash()`,
which is salted per process), once per `run_season` call, which plays ~10,000 duals.

## What a caller with no archive gets

Byte-identical to the pre-layer ladder. Every argument defaults to "no opinion", so a
test, the JHSAA lab's opening year, and every calibration script evaluate on ability
and results alone. That is pinned rather than assumed
(`test_with_no_evidence_and_no_coach_evaluation_is_exactly_ability`), because the
alternative is a layer that has silently become mandatory.
