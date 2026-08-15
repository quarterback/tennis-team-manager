# AAR — JHSAA State expansion: recovery rounds, the district guarantee, team honours

## What started it

The owner watched a 5A season where **Rosa Salcedo (TOSS #14) missed State
while Crown Hill (#23) got in**, and asked whether it was a bracket bug. It was
not: under the old spec (Zonal champions + the top eight post-Zonal TOSS
non-champions as wild cards, into a 16-team field) Crown Hill *beat* Rosa
Salcedo 4-1 in the Regional and then won its Zonal, while RS's one postseason
data point was that loss, which dropped it below the wild-card line. Working as
designed — and the design was the problem:

> "this just proves we need to expand the state brackets across the board…
> make teams PLAY for the remaining State berths rather than benefit from
> sitting home while TOSS is recomputed."

## The new structure (owner spec 2027-08)

**Field sizes:** 7A 32, every other classification 24. The 24 is load-bearing:
a 24-team seeded draw has exactly eight first-round byes, and those byes ARE
the Zonal champions' privilege.

**Three ways in, and no others:**

1. **Zonal champions** (8) — automatic, and the draw's top seeds, so the byes
   fall to them by construction rather than by a special case.
2. **The district guarantee** — a district champion has State ACCESS even if it
   loses in the ladder. Access only: no bye, no seeding help, and no extra
   berth if it also won its Zonal. A geographic-access safeguard, in the
   owner's words, so no district is shut out because TOSS dislikes it.
3. **The recovery rounds** — Super Regionals → Semi-State, two new named
   stages with their own archived phases. The 16 Regional losers (plus, in 7A,
   the best-TOSS Ward losers) enter Super Regionals; the 8 Zonal losers join at
   Semi-State; Semi-State's survivors take exactly the berths that remain.

**TOSS's role is now bounded**: it seeds, it arranges draws, and in 7A it
decides *which Ward losers get another chance to play*. It never hands anyone a
berth.

## Implementation notes worth keeping

- **The arithmetic is DYNAMIC, per the spec.** `berths = state_field -
  zonal_champions - unique non-Zonal district champions`, and the two recovery
  rounds together always eliminate `RECOVERY_CUT` (8, scaled). For a 24-team
  field this falls out of the loser pool by itself: the pool and the berths
  shrink by the same district-champion count, so the eliminations are always 8
  regardless of how many champions the guarantee admits. Measured across a full
  boys' season, district-champion counts ranged 2-4 per classification and every
  field still landed exactly on 24 (7A on 32).
- **7A needs bodies, not berths.** A 32-team field consumes almost the whole
  24-team loser pool, leaving the recovery rounds nothing to play for. So
  `_recovery` computes the shortfall and tops the Super Regional field up with
  the best-TOSS Ward losers — measured: 7A ran SR 21→17 and SS 24→20 (4 duals
  each), the same shape as everyone else's 14→10 / 16→12.
- **Recovery seeding uses a post-Zonal TOSS recompute, and State a second one**
  (`power_index(prestate=True)`, which now includes the recovery duals) — the
  ratings are inputs to draws, never to qualification.
- **Finish labels supersede.** `jhsaa_postseason_result` checks the recovery
  stages BEFORE the ladder round a school lost, so a Regional loser that fought
  through Super Regionals reads "Semi-State", never "Regionals".
- **Old archives keep working.** Pre-expansion seasons have no recovery keys and
  a `wildcards` list; every reader treats both shapes, and the ledger/bracket
  surfaces degrade to what was archived.

## ‼️ Bye selection and pairing are ONE problem (review catch)

The draw rule is: never immediately replay the opponent that just eliminated
you (hard), avoid same-district pairings where practical (soft). The first
implementation assigned byes to the top seeds and *then* repaired the pairing
of the playing tail — so a bye recipient was frozen before the repair could see
it. A review found the exact case: a 7A side took a Super Regional bye and met,
at Semi-State, the team that had knocked it out at Wards, **with other
opponents available in the field**. The repair was structurally unable to reach
it.

`_draw_recovery` now chooses both together: the pure-TOSS bye set is the
starting point, and if it leaves a hard rematch on the board a bye is traded
with a playing team until the rematch clears — lowest bye traded first, so
seeding privilege bends only as far as removing the rematch requires. Pinned by
`test_recovery_draws_never_replay_the_team_that_just_eliminated_you`, which
walks every recovery dual in the association and checks each side's PREVIOUS
archived dual — bye recipients included, since a bye means the previous dual is
the one from the round before.

## Team honours (same session, owner rule)

> "right now only state champions and TOC participants get any honours and
> that's not realistic."

Every non-state postseason dual is a named, numbered unit on purpose, so
winning one is an honour the program keeps:

- **Unit wins, in ROMAN numerals** — "Region IX", "Ward IV", "Super Region II"
  (Zonals keep their letters: "Zone C"). All of a season's unit wins render on
  **one line**, because there are several a year and State has plenty of its
  own.
- **Reaching State is its own honour line**, coloured by tier so the medals stay
  readable: gold = the title, silver = finalist, bronze = semifinalist, and
  **blue** for every other State finish ("STATE OCTOFINALIST").
- `honoured` (what the panel filters on) widened accordingly — it is now
  `honors or champion or toc_champion or unit_wins or made_state`. A season
  with none of those is still unhonoured, and the TOC test that pinned the old
  narrow rule was rewritten to assert the new definition *and* that at least one
  program in the association still has an unhonoured season, which is the real
  invariant (the panel must not become the ledger twice).

## Validation

- `tests/test_jhsaa_ladder.py` (21) rewritten for the new structure: field
  composition and sizing, champions-as-top-seeds, State byes belonging to
  champions, the district guarantee, berths earned on court, recovery round
  names/units/phases, finish supersession, the rematch rule, and the honours.
- All other JHSAA suites green (103) — toc, routes, format, lineup, schedule,
  bracket scores, archetypes, talent shape.
- Full-size season run end-to-end: every classification's field landed exactly
  on 32/24, zero immediate rematches in recovery draws, and the bracket page and
  school schedule render the new stages under their own names.

## Traps for later

- **Never re-add a rating-selected berth.** TOSS seeds, arranges and (in 7A)
  invites to *play*. The moment it selects a qualifier again, the Rosa Salcedo
  complaint is back.
- The **district guarantee is access, not seeding** — if a guaranteed champion
  ever starts drawing a bye, the privilege ordering in `run_season` has been
  broken (champions first, then guarantee + recovery together by TOSS).
- `RECOVERY_CUT` is what makes the shape statewide-uniform; changing the State
  field sizes without re-deriving it is how a classification ends up with a
  recovery round that eliminates nobody.

---

## Addendum (2027-08): no double byes, byes rendered, and the handbook gap

The owner met the recovery rounds in the wild before meeting them in the
documentation: a No. 19-TOSS team lost its Regional 1–4 and appeared in the
State draw three days later with no Super Regional or Semi-State dual anywhere
on any page. *"Is something broken?"* Nothing was — the rounds only eliminate
their cut, byes go to the top of each round's TOSS order, and that team was
comfortably the strongest side in the loser pool, so it sat out both rounds.
Working exactly as built, and completely illegible. Three separate failures:

1. **The handbook never explained the mechanism.** The Guide named the stages
   and said "berths are earned on court" — which the double bye quietly made
   false — but not the cut arithmetic, the TOSS protection, or that byes
   existed at all. ("You were really lazy about explaining how it really
   works.") The Guide now walks the berth arithmetic, the cut-not-a-bracket
   shape, the bye, and the lucky-loser identity.
2. **Byes rendered nowhere.** The Road to State folds list only played duals,
   and the schedule only shows things that happened. A double-bye team's path
   was invisible on every surface. Each recovery fold now ends with a plain
   footnote — `Byes: A, B, C` — and deliberately nothing more: no counters, no
   explainer copy ("i absolutely hate all that superfluous microcopy"), and
   nothing on the schedule.
3. **The double bye itself violated the design intent.** The rounds exist so
   the last berths are earned on court; a team reaching State having played
   zero recovery duals is the exact thing they were built to prevent ("it
   feels a bit unfair for a team to skip rounds I designed specifically to
   ensure everyone who makes it to State played their way in").

The fix for (3) is the owner's agent's design, chosen over a bigger
everyone-plays rewrite I had drafted (which changed the round shapes and game
counts; rejected for exactly that): **keep the arithmetic, ban the double
bye.** A Super Regional bye forces a Semi-State dual; the Semi-State bye can
only land on a team that played and won its Super Regional (or a Zonal loser,
whose one bye it would be). TOSS still assigns protection and pairings; game
counts are untouched. Implementation is a `must_play` set threaded through
`_draw_recovery`'s joint bye-and-pairing selection, plus one arithmetic
consequence: Semi-State's byes must all fit on bye-eligible teams, which works
out to `pool >= 2*(berths − zonal_losers)` — independent of how eliminations
split across the rounds — so the Ward-loser body top-up now fills to that
floor too. Pinned by `test_nobody_gets_a_bye_in_both_recovery_rounds`.

Also recorded for the next reader: my first explanation reasoned about the
second round's byes from the pre-Super-Regional TOSS, and the owner correctly
objected that the ranking shifts the moment the next matches are played — a
round's byes are a fact about that round's own draw, and should be presented
(and reasoned about) per-stage, never projected forward.

### Addendum 2 (same day): the Zonal-loser hole, and byes-first

The no-double-bye rule closed one door and left its twin open: a **Zonal
loser** enters recovery at Semi-State, had no prior bye, and was therefore
still bye-eligible — so a No. 4-TOSS district runner-up lost its Zonal, took
the Semi-State bye, and reached State having won nothing ("a team loses in
zonals and gets to state without winning their district"). The two reports
add up to one principle: **a bye is never the ticket into State.**

The final shape is the owner's algorithm, replacing the `must_play`
matching-search I had built: **decide the byes first, then pair.**

1. Compute how many Semi-State byes the bracket requires.
2. Award exactly that many, by TOSS, from the eligible set — non-guaranteed
   teams that **played and won a Super Regional dual**. SR bye takers and
   Zonal losers are not eligible; district champions are already guaranteed
   and never enter the pool.
3. Pair everyone remaining with the normal seeding/pairing method. "Must
   play" is not a constraint on the draw — it is simply what not being
   bye-eligible means.

Two consequences worth recording. A bye no eligible team can hold is **played
off** — extra duals, cutting deeper than the round's target — rather than
handed down the pool; the State draw already tolerates a short field. And the
rematch rule is now explicitly a *pairing preference*: with byes fixed by
rule, a degenerate pool (a two-team Semi-State whose teams just played each
other) forces the rematch, and the test asserts no **avoidable** rematch —
checking every perfect matching of the playing set — instead of none at all.
Small playing sets (≤8) get an exact minimum-penalty matching rather than the
greedy repair, which the tighter bye rules had been out-manoeuvring.

`_draw_recovery` (the joint bye-and-pairing search, including its bye-trading
repair) is deleted. Its reason for existing — a bye recipient frozen into a
rematch — is handled by the pairing method itself now that byes are a rule
rather than a search variable.

### Addendum 3: the State field is fixed; recovery conforms to it

Owner patch on the play-off degrade: extra Semi-State duals shrank the State
field, and the field is the invariant — **32 in 7A, 24 elsewhere, always**. A
bye shortage is solved UPSTREAM by adding the highest-TOSS eligible Ward
losers to the Super Regional field until enough SR winners can exist (the
feasibility floor `pool + zonal losers ≥ 2×berths` already drives the top-up);
the recovery bracket never plays extra duals, never cuts deeper, never shorts
the qualifier count. When bodies genuinely run dry (only reachable in a
scaled-down test class), the overflow byes fall to ineligible teams — **Zonal
losers before Super Regional bye holders**, because one bye is less bad than a
double — loudly logged, and the field still arrives full. First cut of that
fallback took the best-TOSS ineligible team and handed a double bye straight
back to a Super Regional sitter; the tiering exists because of it.
