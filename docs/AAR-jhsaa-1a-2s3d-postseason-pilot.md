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

## The calibration — headline numbers

**‼️ THE FULL DATA RECORD IS `docs/reports/REPORT-jhsaa-dual-shape-competitiveness.md`**
— every table, the method, the cross-shape sweep and both measurement traps. It is the
single source; what follows is the summary the decision was made on, and if the two
ever disagree the report is right.

Measured with `scripts/jhsaa_1a_format_pilot_calibration.py` over all **179** 1A
programs (93 girls / 86 boys), 2039 rosters, **20 trials per pairing** (920 duals a
cell in girls, 860 in boys), `FIDELITY="fast"`. Ladder is pure ability, so this
measures the FORMAT rather than a particular year's results.

**What it costs.** 2S/3D dresses eight where 1S/4D dresses nine. The cut player
averages 27.8 OVR and sits a **median 1.0 OVR** below the last player who still
dresses; for **71% of programs (127/179)** that gap is inside 2 OVR. This is a close
call 179 times over, not a scrub being trimmed — the number belongs beside the upside,
not under it.

**What it buys.** The new S2 court goes to the **#2 player 79%** of the time, #3 20%,
#4 2% — the stated point of the change, with a coaching choice that genuinely fires
~21% of the time rather than a fixed allocation wearing a search's clothes.

**What it does to a match.** In evenly-matched duals the format decides **~27-30% of
outcomes** (same winner under both shapes only 70% girls / 73% boys) — the same kids,
opponent and seed, a different answer. Mismatched duals agree **85-90%** and the upset
rate moves ≤3 points in any cell, so it flips close matches without making the
association chaotic.

**And the nailbiter rate is a FEATURE, not a caveat** (owner, 2026-08): an
evenly-matched 1A dual lands 3-2 **~70% of the time under BOTH formats**. A five-point
shape in a flat field is coin-flip-adjacent by construction, and that is the juice a
24-team 1A bracket is meant to have. An early draft of this document filed that row
under "noise" and buried the most characteristic number in the study.

### ‼️ THE BOYS/GIRLS SPLIT IS THE FIELD, NOT THE FORMAT

Boys' 1A is both stronger and more spread (top-9 mean OVR **42.09 vs 38.52**, sd 4.64
vs 4.27, p90−p10 12.11 vs 10.78) — the good programs separate, while the girls' field
stays flat by design. So 2S/3D has **more leverage in girls' 1A**: mismatched duals
agree 85% (girls) against 90% (boys), upsets 16% against 10%. That is a property of the
FIELD, not of the shape — never read a gender gap in a future run as a format
regression without checking the strength distribution first. Full table in the report.

### ‼️ WHY FIVE COURTS — and why 2S/3D was the only shape that could work

The report's cross-shape sweep (eight odd shapes, both genders) is what justifies the
pilot's *particular* shape rather than any other second-singles format.

**Court count dominates.** Five-court duals finish on a single court **61-73%** of the
time; seven-court duals **58-60%**, whatever their composition. Holding doubles share
roughly fixed and changing only court count (3S/4D, 57% doubles, 7 courts → 2S/3D, 60%
doubles, 5 courts) moves it **8-13 points**. The mechanism is sampling, not tennis: a
dual is an average over its courts and fewer courts average less.

**Doubles share is a real secondary term** — ~6-10 points across a full 80%→0% sweep at
five courts. ⚠️ An earlier version of both documents said doubles was irrelevant, on
the strength of a narrow seven-court sweep that genuinely is flat; the full sweep
reversed that. **Do not state a conclusion wider than the range swept.**

So the shape is forced: adding a real second singles seat while holding five courts
means taking it from doubles — **2S/3D**. 2S/4D and 3S/3D are six courts and can TIE
(no tie-break exists, by design); 2S/5D and 3S/4D are seven and give the closeness up.
The pilot is not a step toward tradition — it is the maximum singles content available
at five courts, and it sits at or near the **peak** of the doubles-share curve in both
genders (girls 73%, highest of any shape measured; boys 67%, tied with 1S/4D).

For reference, **3S/2D — the classic American format** — lands at 70% (girls) / 62%
(boys), level with 1S/4D in girls and clear of every seven-court shape, dressing only
seven. Legitimate, measured, not adopted (owner: *"I'm not gonna switch to it, but I am
curious how it compares"*); 40% doubles is where the doubles-forward identity goes.

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
`--trials` default is **20** — 920 duals a cell in girls, 860 in boys, against the
~45 a single trial gives — and the divergence vanishes at that size.

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
