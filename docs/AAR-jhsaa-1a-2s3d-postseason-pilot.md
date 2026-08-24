# AAR — the 1A 2S/3D postseason pilot

Owner rule 2026-08. **1A alone plays 2 singles / 3 doubles on its road to State.**
Every other classification keeps 1S/4D, 1A's own TOC entry reverts to 1S/4D, and
1A's regular season and mid-season Match Showcases are untouched.

`app/jhsaa.py`: `FORMATS["state_1a"]`, `PILOT_GROUPS`, `dual_format(phase, group)`,
`lineup_need(phase, group)`, `_arrange_1a_postseason`.
Calibration: `scripts/jhsaa_1a_format_pilot_calibration.py`.
Coverage: `tests/test_jhsaa_lineup.py` (three tests, at the bottom).

---

## Why this classification, and why now

The association has never, in fourteen seasons, run a state playoff format that put
more than one singles player on court. The owner had rejected 2S/3D repeatedly for
one reason: it dresses **eight** where 1S/4D dresses **nine**, and dropping a kid
from the playoff roster is a real cost. The alternatives were worse — 2S/4D can tie
(the association has no tie-break logic anywhere and does not want any), and 2S/5D
is a bigger change than the question warranted.

1A is where that cost is smallest and the upside largest:

- **1A already has bespoke postseason wiring** (`_recovery_24`, the fixed 24-team
  shape — see `AAR-jhsaa-1a-2a-classification-split.md`). A per-class carve-out in
  the format layer is not a new KIND of exception for 1A, it is the same pattern one
  axis further. Every other class would have been the first.
- **A 24-team playoff is where a format change has the most leverage.** Owner: it
  "adds some real juice", and needing one fewer kid to compete for a title is a
  genuine competitive win for the association's smallest programs, not just a cost.
- Roster depth scales by classification (`ROSTER_SIZE_BAND_BY_CLASS`, 1A 14-16), so
  1A is also where the ninth player is least likely to be a meaningful contributor.

## What the pilot actually changes, in one line

**A real player gets a second singles court.** Owner: *"the only real difference is
that 2/3 has a 2nd singles spot so that person can be someone actually good, not the
10th best player on a 1A team."* That is the whole feature. Everything below is the
measurement of what it costs and what it does.

---

## ‼️ THE ANTI-STACKING RULE IS ONE MECHANISM, GENERALISED — NOT A SECOND RULE

This was got wrong twice in one session and is the most important thing in this
document.

**The rule is: the top N of the frozen Order of Ability are consumed by the singles
seats plus D1, and the coach chooses WHICH of them plays singles.** The best player
is **not** pinned to S1 — a team may pair its #1 into D1 and start #2 or #3 at
singles if that scores better. That has always been true of 1S/4D (`_arrange_state`
pools the top THREE and searches which ONE plays singles, the other two forming D1).
2S/3D pools the top **FOUR** and searches which **TWO** play singles, the other two
forming D1. Same idea, one seat wider.

Owner, correcting a first draft that pinned S1 to rank #1: *"the rule isn't S1 always
at S1, it's top 4 have to play S1/S2 or D1, meaning 3 can play S1 if a team wants to
take their top singles and team them up"* — and, on scope: *"it should be that way
across the board, not just for 1A"*, with the clarification that *"obviously 1/4
doesn't have singles for playoffs so [it's] moot there"*. So **no change to
`_arrange_state` was needed** — it already implements the general rule; 2S/3D is the
same rule at a wider pool. Do not write these up as two different anti-stacking
regimes, and do not "fix" `_arrange_1a_postseason` to pin S1.

D2/D3 replay `_arrange_state`'s own logic on the remaining four (#5-#8): a search
over the three ways to pair them, best total doubles ability wins, then
`_order_pairs`'s rank-sum boundary (`PAIR_SUM_TOL`, adjacent-seat only — the chained
case stays legal, per the standing owner ruling in `AAR-jhsaa-order-of-ability.md`).

---

## The calibration, in full

`scripts/jhsaa_1a_format_pilot_calibration.py`, run against all **179** 1A programs
with a full postseason roster (**93 girls / 86 boys**), 2039 rosters, `FIDELITY="fast"`.
The ladder here is pure ability (no season played), so this measures the FORMAT, not
a particular year's results.

### Participation — what it costs, and who it promotes

| | |
|---|---|
| Player cut entirely from the postseason roster (was seat #9 of 9) | mean OVR **27.8**, median 28.0 |
| Gap from that player up to seat #8, the last who still dresses | mean **2.03** OVR, **median 1.00** |
| Programs where the cut player is within 2 OVR of dressing | **127 / 179 (71%)** |

**This is the cost, stated plainly: for 71% of 1A programs the kid who loses their
postseason spot is within two OVR of the last player who keeps one.** It is not a
scrub being trimmed; it is a close call, 179 times. The owner accepted it knowingly —
a 24-team playoff where a program needs one fewer kid to contend is worth it — but
the number belongs on the record beside the upside, not under it.

Who gets the new S2 court, by rank in the top-four pool:

| Rank | Programs | Share |
|---|---|---|
| #2 | 141 | **79%** |
| #3 | 35 | 20% |
| #4 | 3 | 2% |

So the format overwhelmingly promotes the **#2 player to a real singles court** —
which is the stated point of the change — while leaving the coach a live choice that
actually fires ~21% of the time. A rule that produced 100% "#2 plays S2" would have
been a fixed allocation wearing a search's clothes; this one is a real decision.

### Competitiveness — same pairings, both formats, matching seeds

Two pairing sets per gender: **evenly matched** (adjacent by team strength — what a
bracket's later rounds look like) and **mismatched** (top half vs bottom half).
**20 trials per pairing** (`--trials`, the default): each pairing is replayed under 20
distinct seeds, both formats always seeing the same one, so the comparison stays
paired. That is ~1,780 duals a cell against the ~45 a single trial gives.

| | Girls, even | Boys, even | Girls, mismatched | Boys, mismatched |
|---|---|---|---|---|
| Duals | 920 | 860 | 920 | 860 |
| **Same winner under both formats** | **70%** | **73%** | 85% | 90% |
| Upset rate, 1S/4D → 2S/3D | 47% → 50% | 49% → 50% | 16% → 16% | 11% → 10% |
| Mean margin (of 5 points), 1S/4D → 2S/3D | 1.73 → 1.67 | 1.66 → 1.76 | 2.79 → 2.72 | 3.05 → 3.09 |
| **Nailbiters (3-2), 1S/4D → 2S/3D** | **67% → 70%** | **70% → 68%** | 35% → 40% | 33% → 33% |

**Headline 1: in evenly-matched duals the format decides ~27-30% of outcomes.** Only
70% (girls) / 73% (boys) of close pairings produce the same winner under both shapes —
the same eight or nine kids, the same opponent, the same seed, a different answer.
That is the "flips outcomes" property the owner wanted, and it is exactly where you
want it: in the bracket's close matches, not in the blowouts.

**Headline 2 — and this is a FEATURE, not a caveat (owner, 2026-08):** an
evenly-matched 1A dual lands on **3-2 about 70% of the time, under BOTH formats**. A
five-point shape in a flat field is a coin-flip-adjacent tournament by construction,
and that is the juice a 24-team 1A bracket is supposed to have. An earlier draft of
this document filed the nailbiter row under "noise, do not build a rule on it", which
buried the most characteristic number in the study. The format does not create the
nailbiters — the field does — but it is the reason they matter, and 2S/3D preserves
the property rather than flattening it.

**It does NOT make the association more chaotic.** Mismatched duals agree 85-90% of
the time and the upset rate barely moves in any cell (≤3 points, and DOWN in boys'
mismatched). A clearly better team stays clearly better under either shape; 2S/3D
reshuffles WHICH close matches flip.

### ‼️ THE BOYS/GIRLS SPLIT IS STRUCTURAL, AND IT IS NOT A FORMAT EFFECT

A single-trial run reported the nailbiter rate moving in **opposite directions by
gender** (boys 81%→53%, girls 63%→72%). That specific swing was **sampling noise** and
is gone at 20 trials (boys 70%→68%, girls 67%→70%) — which is exactly why the trial
count exists, and why no rule should ever be built on a ~45-dual cell.

But there IS a real gender difference underneath, and it belongs on the record because
it explains the durable part of the table. Owner's read — *"1A teams are kind of
balanced weird; boys tennis has higher STR abilities meaning the top teams kind of
separate themselves, whereas the girls are more evenly matched by design"* — is
confirmed by direct measurement of the 1A field:

| 1A programs | Girls (93) | Boys (86) |
|---|---:|---:|
| Team strength, top-9 mean OVR | 38.52 | **42.09** |
| Spread (sd) | 4.27 | **4.64** |
| p90 − p10 | 10.78 | **12.11** |
| Best player OVR | 58.22 | **60.76** |
| Best player STR | 47.56 | **48.66** |

Boys' 1A is both **stronger and more spread**: the good programs separate. Girls' 1A
is flatter. That shows up in the calibration exactly where you would expect — the
**mismatched** cells, not the nailbiter row:

| Mismatched | Girls | Boys |
|---|---:|---:|
| Same winner under both formats | 85% | **90%** |
| Upset rate (2S/3D) | 16% | **10%** |
| Mean margin | 2.79 | **3.09** |

**More separation → bigger margins, fewer upsets, and less room for the format to
change anything.** So 2S/3D has more leverage in girls' 1A than boys', and that is a
property of the FIELD, not of the shape. Do not "fix" it, and do not read a
girls/boys gap in a future run as a format regression without checking the strength
distribution first.

---

## ‼️ THE CALIBRATION SEED MUST BE A STABLE DIGEST, NEVER `hash()`

The first version of the script seeded each pairing with `abs(hash((name_a,
name_b)))`. Python **salts `hash()` of str/tuple per process** (`PYTHONHASHSEED`), so
every ordinary invocation produced different pairing seeds and therefore different
numbers — a review running it at `PYTHONHASHSEED=1` vs `=2` moved **concordance by up
to 8 points and upset rate by up to 16**. Every figure in the table above would have
been unreproducible, and nothing would have looked wrong: the script ran clean and
printed plausible percentages both times.

`_pair_seed` now uses `hashlib.blake2s`, which is the idiom this module already uses
everywhere it needs a stable per-entity seed (`_coach_strategy`, `neglect_severity`,
`_reclass_enrollment`, the doubles lift). Verified by running the whole script at two
different `PYTHONHASHSEED` values and diffing the output: byte-identical.

**A calibration script's output is an ARGUMENT, and an irreproducible argument is
worth nothing.** Any number in this document could have decided the feature; check
determinism before quoting one.

## ‼️ AND ONE SEED PER PAIRING IS NOT A SAMPLE

Determinism is necessary and not sufficient. The first run was perfectly
reproducible and still reported a gender divergence that does not exist, because
~45 duals a cell cannot separate a format effect from dual-to-dual variance. The
`--trials` default is **20** (~1,780 duals a cell) and the divergence vanishes at
that size.

The trap is that a one-trial run looks like a census, not a sample: it covers EVERY
1A program, so "n = every program in the classification" reads as exhaustive. It is
exhaustive over PROGRAMS and a single draw over OUTCOMES, and the outcome is the
thing being measured. **When the quantity is a rate over simulated results, the
sample size is the number of DUALS, never the number of teams.**

## ‼️ AND A CALIBRATION MUST EXERCISE THE SHIPPED CODE

The first draft also reimplemented the 2S/3D arranger inside the script, because the
production one did not exist yet. That is defensible while designing, and a trap the
moment the real function lands: the script then measures a stand-in, and the two can
drift silently while the report keeps printing. Once `_arrange_1a_postseason` existed,
the script was rewritten to call `jh.dual_format` / `jh._arrange_state` /
`jh._arrange_1a_postseason` directly. Every number above is the real code path.
(This mattered here — the anti-stacking rule changed after the first run, and only a
script calling the shipped function picks that up automatically.)

---

## Scoping: three axes, three separate ways to get it wrong

The pilot is narrow, and each boundary is enforced in `dual_format(phase, group)`:

1. **By group.** `PILOT_GROUPS = ("1A",)`. Every other class resolves to `state`.
2. **By phase — and `POSTSEASON` is NOT the right set.** `POSTSEASON` includes
   `"toc"`, and the **Tournament of Champions fields every classification's champion
   at one shape**, so 1A's entrant plays it at 1S/4D like everyone else (owner: *"1A
   just goes back to 1/4 for TOC"*). The branch is `phase in POSTSEASON and phase !=
   "toc"`. Reading `POSTSEASON` wholesale would have shipped a six-team meta-event
   where one team played a different sport.
3. **By season half.** The regular season stays the universal 3S/4D league card and
   the mid-season Showcases stay 1S/4D — **including for 1A**. Owner's reasoning:
   *"3/4 is fundamentally contained within 2/3, so a coach can see it without any
   tweaks."* A 1A coach already manages three singles courts every league dual; a
   showcase specifically rehearsing two adds nothing they have not run all season.
   This is the one place the pilot deliberately does NOT follow the showcases' own
   stated purpose (rehearsing the postseason shape), and the reason is that the
   league card already over-covers it.

## The freeze reads ONE order at two slice lengths

`_postseason_nine` freezes the **full ladder** (`ts.order_of_ability` = every pid in
ladder order) and slices `lineup_need(phase, group)` off the front. That is what lets
1A's road dress eight and its TOC entry dress nine **off the same frozen order**,
with no second freeze. Freezing a fixed-length slice instead would have forced a
re-freeze for the TOC — which is precisely the mid-postseason re-rank the
anti-stacking rule exists to forbid. Pinned by
`test_a_1a_program_reads_one_frozen_order_at_two_slice_lengths`.

## ‼️ `_slot_players` MUST be told the shape its side was dressed with

`_slot_players` resolves a doubles slot as `f.n_singles + 2*(i-1)`. Called without an
explicit format it falls back to `dual_format(phase)` with **no group**, i.e. 1S/4D —
so on a 1A postseason dual every D-slot would resolve against 1 singles instead of 2
and name the **wrong players** in the box score, the award résumés and the archive.
Nothing would raise; the names are all real players from the right team.

This is the same trap the JV season already documented ("‼️ `fmt` MUST be passed to
`_slot_players`"), and it now has a second instance. Both `_credit` and `play_dual`
thread the dressing side's own group through. `_credit` gained an `opp_group`
parameter for the same reason — the opponent's slot resolution is a separate lookup,
and in a bracket both sides share a group but the call must still be explicit rather
than relying on that.

**Rule: any function that maps a slot name back to players needs the format that side
was DRESSED with. Never let it re-derive one from the phase alone.**

## What did not need to change

- **`FLIGHT_WEIGHTS`.** S1/S2/D1/D2/D3 are all already weighted (1.00 / 0.75 / 1.00 /
  0.50 / 0.25) — the 2S/3D shape needs no new number. `rating._flight_score`
  normalises by the weight actually CONTESTED per dual, which is exactly the
  machinery that already lets 5S/2D, 3S/4D and 1S/4D share one table; a fourth shape
  is not a new problem for it.
- **`ROSTER_FLOOR` / `ROSTER_SIZE_BAND_BY_CLASS` / `jv_pool`.** All key off the
  REGULAR-season shape (`lineup_need("regular")` = 11), which the pilot does not
  touch. 1A rosters and its JV season are unchanged.
- **The 24-team bracket, seeding, TOSS, recovery ladder, awards.** The pilot changes
  what happens ON court, not who gets there or how they are rated.

## Known-stale test, not caused by this work

`tests/test_jhsaa_lineup.py::test_maximize_never_scores_worse_than_traditional` fails
on a clean tree (verified by stashing). Its docstring describes the 105-partition
search that the owner **removed in 2027-08** (`_arrange_regular` now makes one direct
decision); the test is the stale side, exactly the situation CLAUDE.md's "a failing
test is NOT proof the code is wrong" warns about. Left alone here — it is a separate
decision about whether to retire or rewrite it.

## Files

| file | what changed |
|---|---|
| `app/jhsaa.py` | `FORMATS["state_1a"]`, `PILOT_GROUPS`, `dual_format`/`lineup_need` gain `group`, `_arrange_1a_postseason`, `_postseason_nine` takes `phase`, `_lineup` branches, `_squad`/`_credit`/`play_dual` thread the group |
| `scripts/jhsaa_1a_format_pilot_calibration.py` | the calibration above — stable seeds, shipped code path |
| `tests/test_jhsaa_lineup.py` | three tests: scoping, anti-stacking legality, one-freeze-two-slices |
