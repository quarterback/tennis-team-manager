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

### …and the roster never said so either

> "Injured players do not have anything on the roster list telling you. It's on
> their page, but it's not indicated when they're actually hurt."

The injury log existed only on the player page. The **roster** — the one surface
where "why does this 92-OVR senior have five matches?" is actually asked — showed
nothing. So the archive had the answer and the page that raises the question did not
carry it, which is most of why this was reported as a selection fault at all.

Now an `INJ` / `OUT` chip on the roster row, beside the honours and family chips,
with the detail in the title. Outlined like `unit` because it annotates a row rather
than decorating it; the season-ending case fills in, since that is the one a reader
must not miss.

‼️ **It is a season LOG and can never be a live status.** A JHSAA season is simulated
whole at the world's week 0, so by the time any page renders it the season is over
and nobody is currently hurt — as the owner put it, *"that's because the season runs
and it's done so it would never persist."* So the chip says what happened (how many
duals he missed, or that it ended his year) and never "OUT" as though he were
unavailable now. One query per page, folded per pid beside the family fingerprint —
never inside the per-player comprehension.

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

## What it actually did

Two consecutive scaled seasons, boys, run with the layer and again with no memory at
all (the same fixture, the same salt, so the only difference is the evidence):

| | with the layer | no memory |
|---|---:|---:|
| returning varsity regulars | 4,949 | 4,957 |
| held 50%+ of their team's duals | **95.8%** | 94.0% |
| lost their place (<25% of duals) | **1.7%** (83) | 2.8% (137) |
| freshman share of varsity appearances | **20.3%** | 21.2% |

Displacement down about 40%, and the freshman share of varsity court time barely
moved — 20.3% against 21.2%. That second number is the one that matters: it is the
evidence that the lineups did not fossilise. Newcomers still take the same share of
the season; what changed is *which* newcomers, and on what margin.

### ‼️ The measurement also caught a calibration fault, and it was mine

The first tier mix came out **5,706 established : 1,856 decorated : 435 contributor**
— tier 1 nearly unused, and the *ordinary* returning starter sitting on the middle
value instead of the small one. The cause is structural and obvious in hindsight:
every program in this association enters the road to State and every road dual dresses
the top nine, so `PROOF_POSTSEASON` is true of essentially every returning starter. A
tier keyed on it alone is not a tier, it is a synonym for "was a starter".

Tier 2 now requires a season that actually went well — the appearances *and* a
winning record *and* a top-nine seat or a postseason lineup. A losing starter drops
to contributor, which is what the owner's spec said in the first place: *"a player
with one ordinary varsity year might be protected only into the varsity 11."*

**Three tiers that collapse to two is a calibration that reads fine in code review and
only shows up when you count what the population actually lands on.**

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

**Leadership / captaincy** — built, and it turned out to need no engine change at
all. See the next section.

## Captains (owner rule 2026-09)

A program names **1 to 3**. They change nothing about any player.

### Who, and how an ordinary one earns it

Three seats, in the owner's own terms:

1. **The best player, almost always.** ‼️ The coin turns out to be decisive only for
   an *underclassman*: a senior No. 1 who loses it is still the best remaining
   candidate for seat 2 and gets named anyway. So a senior No. 1 is captain
   essentially always and a ninth-grade No. 1 at the coin's rate. That fell out of
   the two rules rather than being designed, and it is the right shape — the
   exception the rule leaves room for is a young star who does not lead the room.
2. **The best DOUBLES player**, no grade gate. This started as "the best senior" and
   the owner corrected it twice: seat 1 is almost always No. 1 singles, so seat 2
   should be the other half of the team; and juniors must not be excluded, because
   "teams benefit from having captains who have been around a bit". Judged on
   `net_rating` — the engine's own "engine of doubles" — never on ladder position,
   which is a singles ordering and would just re-pick No. 2. Measured over 38
   programs it lands at ladder rank 2 most of the time but reaches to 5, which is
   the evidence it is doing something a ladder read would not.
3. **The glue** — the longest-serving varsity player not already named, drawn from
   the whole dressing group irrespective of ladder position or grade. ‼️ **No new
   attribute was needed**: work ethic is not modelled and does not have to be,
   because `PriorSeason.years` already counts consecutive seasons of standing and
   the longest-serving player who is not a star *is* that archetype. Measured, the
   seat lands anywhere from #1 to #11.

**Held until graduation** (`PROOF_CAPTAIN`). A captain named as a tenth-grader is
captain for three years; returning captains are re-seated first and unconditionally,
and `want` is a floor of their count rather than a cap on it — drawn first and
applied to them, a one-captain year would have had to strip the C off somebody still
enrolled. **A transfer does not carry it**: the evidence map is keyed on pid so it
follows a mover by design, which is right for his record and wrong for a captaincy,
which is a thing one particular room gave him.

### What it is worth

**A flat 1.5 OVR off the coach's misread, per team**, one captain or three — the
count is flavour, not arithmetic, which is also what stops anyone naming three to
farm a bonus. It bites hardest where the coach is worst: against the 0–2.5
`COACH_READ` band a 1.5 takes the weakest coach to 1.0 and a good one to zero.

**Captains dress**, from the naming point on, regular season and postseason alike. It
does not breach anti-stacking — the frozen Order of Ability still decides the
*order*, which is what that rule governs; this substitutes who is in the dressing
group, exactly as the injury filter already does. ‼️ The force is deliberately **not**
a safety net: a glue captain who slides down the ladder is still played and it costs
the team. That is the incentive the owner wanted — "it creates an incentive by the
coach NOT to pick kids who won't play" — and it exists only because the force is
real. An injured captain is not forced back on, which holds by construction because
`_healthy` has already dropped him.

### Presence, and what it absorbs

The three seats say *who*; **presence** says how much each carries, and it had to be
answerable for a captain with no awards — most of them. Earned four ways, all of them
things already recorded: **awards** (ranked — POY, All-State, All-Region,
All-District, best only, never summed), **tenure**, **a winning record**, and a small
term for topping the ladder.

Measured: a three-year Player of the Year is at the ceiling (0.34), an All-District
pick in his first year 0.17, a three-year glue captain with a *losing* record 0.135,
a first-year captain 0.045. That middle number is the one that matters — the player
the team actually trusts is not worth a rounding error next to a decorated one.

**What it does** is the owner's own rule: *"if you roll a negative form, a decorated
captain can absorb a % of that."* A player's standing already moves with their
record; a team with strong captains **slides less**. The team's absorption is the
**sum** of its captains' presence, capped at 100% — so three decorated captains can
roll a whole slump off, which is the incentive for multiples — and it covers the
**entire team**, "which is why they're captains".

‼️ **THE ASYMMETRY IS THE WHOLE THING.** Only the downside is softened; a winning run
is never inflated. That is what keeps this from being a team-wide ability bonus
wearing a different hat, and it is why it needed no engine change and no calibration
sweep: it changes where the coach *ranks* a slumping player, so a well-led team stops
benching people over a bad fortnight. Nobody plays any better.

‼️ **AND I HAD THE SIGN WRONG FIRST.** I proposed reduced match volatility and warned
it would hurt underdogs, because suppressing variance also suppresses the upsets a
weak team needs. The owner's version inverts that — good players *elevate* their
teams — and softening a slump helps whoever is slumping, which a weak team does more
of. The objection was to my mechanic, not to the idea, and I should have looked for
the version that helped rather than reported the one that hurt.

### Archived

Captains ride on the standing row as `[pid, name]` pairs. ‼️ **The name is stored on
purpose**: the program's Captains history walks every archived season, so deriving it
would mean rebuilding forty rosters on a page load — the same call the individual
draws already make in storing a player's grade with the entry. A `C` chip on the
roster, ahead of the honours chips because a captaincy is a role rather than an
award, and a **Captains panel under History** listing every season's, which is what
the owner asked the archive for. Rows written before any of this read back as the
bare shapes they were, never migrated.

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
