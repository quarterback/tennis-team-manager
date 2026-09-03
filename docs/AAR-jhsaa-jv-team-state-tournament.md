# AAR — the JV Team State Tournament (JHSAA pilot, 2068)

The association approved a **JV team championship** and the owner added it **after the
2067 season of a longstanding JHSAA save**, which is the whole reason `jhsaa.
JV_STATE_FROM` is **2068** and not a flag: every season already archived in that save
has to keep reading as the year it was played, with no JV team event in it. A year
gate is the same device the 1A 2S/3D pilot is gated on, for the same reason.

## What it is

One statewide bracket per gender, no classifications. District berths are earned over
the JV season (2-5 teams → 1, 6-9 → 2, 10-15 → 3, 16+ → 4), the **twenty geographic
areas** each crown a champion, those twenty rank statewide, seeds 1-12 go straight to
State and **13v20 / 14v19 / 15v18 / 16v17** play in for the last four seats. The State
draw is then **16 → 8 → 4 → 2**, played in full.

Five courts — **S1/S2/S3 + D1/D2, first to 3** — seven on court, and a championship
roster of **up to 16** that lineups may change between rounds from.

---

## What went wrong, and what it cost

### 1. "Complete" meant the engine, and nothing else existed

The pilot was reported finished when `app/jhsaa_jv_state.py` played the event and
returned an archive dict. Nothing read that dict. `world.run_jhsaa` never touched
`season["jv_state"]`, so **the whole event was computed and thrown away** on every
rung; its duals were played through `simulate_dual` directly and appended to no
schedule, so they never reached `world_jhsaa_dual` either. No route, no template, no
rail entry.

It took the owner asking *"where is the bracket going to live in the UI?"* to surface
it. The tests all passed — every one of them called the module directly, which is
exactly what a module that is wired to nothing still supports.

> **A simulation feature is not done when it simulates.** The three layers are the
> event, the archive and the surface, and a feature that stops at the first is a
> feature nobody in the game can ever see. Say which layers shipped.

### 2. The roster size was invented

`ROSTER = 8` came from "one more than the seven who dress" and was written into the
module, the doctrine and a test as though it were the spec. The spec says **up to 16**.
It is a CEILING, not a squad size: entry needs `LINEUP` (7) and nothing more, so a thin
program carries fewer rather than being excluded.

> A number that has to be reasoned to is a number to ask about. Deriving one and then
> pinning it in a test makes the invention look like a decision.

### 3. The doctrine was framed as an authority to argue against

The module opened by announcing it "REVERSES A STANDING 'NO JV TEAM PLAYOFFS' RULE"
and then rebutted three objections point by point. Owner: *"there is no standing rule,
CLAUDE.md is not my boss I am the boss."* `CLAUDE.md` is a record of decisions and
their traps — it is not a body of precedent, and a new feature does not need to
overturn it. What survived is the part that does work: the three mechanics (seeding on
the record, the eligibility freeze, one fixed shape) and the reasons they exist.

### 4. ‼️ A SMALL FIXTURE CANNOT SEE A FULL-SIZED FIELD

The owner said it plainly: *"my save has a lot more teams and full rosters on them so
I'm far more likely to fill out all 20 regions than you are in your smaller tests."*

That was not a general caution. It was a live bug, and it fired within the hour:

```python
qualified = set(winners)      # TypeError: unhashable type: 'JVEntry'
```

`JVEntry` is an ordinary dataclass, so `__eq__` is field-wise and `__hash__` is
`None`. The line is only reached when a season crowns **more than `DIRECT_SEEDS` (12)
regions** — i.e. only when a play-in is actually played. Measured on real districts:

| fixture | regions crowned | play-in |
|---|---:|---|
| 4 classifications × 4 districts | 12 | never runs |
| 4 classifications × 5 districts | 12 | never runs |
| 6 classifications × 8 districts | 17 | 2 games |
| the real association | **20** | **4 games, every year** |

Every test passed, the event ran end to end, and the single code path the owner's save
takes *every season* had never once been executed. The fix is one line; the lesson is
that **the graceful degradation of a fold is not evidence the full-sized case works** —
it is the reason the full-sized case never got run.

The module and the doctrine now both say the real save fills all twenty, and the
suite forces a play-in rather than hoping a fixture reaches one.

### 5. The odd court count is load-bearing, not stylistic

Three of the eight elastic `JV_FORMATS` have an even court count and `jv_outcome`
genuinely returns draws (~0.24% of JV duals; 2S/2D alone is about a fifth of the league
slate). A bracket cannot advance a tie and this association has no tie-break anywhere,
by design. 3S/2D is five courts and cannot draw — which is why the event fixes ONE
shape rather than sizing per dual off the thinner side, and why that shape is odd.

Measured: 3S/2D needs 7 spare, which ~63% of boys' and ~60% of girls' programs have; a
seven-court format would have cut that to ~27%.

---

## Decisions worth keeping

- **Seeding reads the JV RECORD, never ability.** `JVTeam` has always carried
  `wins`/`losses`/`ties` and `points_for`/`against`. What it must not read is
  `jv_strength`, and a test constructs two identically-recorded programs with very
  different rosters to pin it — **constructed, not hunted for in the fixture**, since
  those are floats over ~15 duals and never tie by chance.
- **‼️ POSTSEASON DUALS DO NOT MOVE THE RECORD THEY ARE SEEDED FROM.** `play_dual`
  writes the schedule row and the box score but never touches `wins`/`points_for`. A
  region final that moved them would re-rank the statewide field the play-in and the
  State draw are cut from — the mid-event drift `freeze_eligibility` exists to stop,
  arriving through the record instead of through the roster.
- **Eligibility freezes once**, at the start of the JV postseason: ladder rank #12+
  (`jv_pool`, the one cut — no second roster split is invented) AND actual JV
  participation, read off the `played` list `play_jv_dual` already records.
- **The event archives the VARSITY STATE DRAW'S SHAPE** (`{champion, field, rounds,
  round_names}`), which is why the page needed no bracket code: `state.
  _jh_bracket_cols` → `_bracket_canvas` → `templates/_bracket.html` reads it unchanged,
  materialising byes and ordering cards by their real feeders. Emitting a different
  shape would have meant a fourth bracket implementation for a draw that draws like the
  other three.
- **Its duals go in `world_jhsaa_dual` at `level='jv'`, `phase='jv_state'`** — that is
  what puts them on a program's schedule and folds them into the JV column of the
  career ledger, and `level` is what keeps them out of every varsity record. Only the
  DRAW lives in the new `world_jhsaa_jv_state` table.
- **‼️ NOT in `world_jhsaa_individual`.** That table holds per-PLAYER draws and two of
  its readers scan every flight (the champion-history rolls); a team bracket dropped in
  there would be served under an individual heading with no error anywhere. And not on
  the `world_jhsaa` summary blob, which every JHSAA page reads in full.
- **‼️ `_relabel` HAD TO BE TOLD THE REGION KEYS ARE PLACES.** `regions` and
  `region_champions` are dicts keyed by geographic area, and ten retired school names
  are also live Jefferson town names (Port Veles, Ashbury, Telfair, Orellana) — walked
  unguarded, a region would be filed under some school's current name and its bracket
  would vanish from the page. Adding the two keys to `_NOT_A_SCHOOL` protects that
  level's keys only; the recursion still relabels the champions under them.
- **The qualifying round is its own panel, never a column of the tree.** Eight teams
  into four seats is not a halving and `_bracket_canvas` links positionally. It is also
  **not the Round of 16** (owner: *"20 champions → 16 → 8, 4, 2, don't skip the R16"*):
  a play-in winner has qualified FOR the draw, not through its first round.
- **`jhsaa_jv_individuals.run_jv_state` was renamed `run_jv_individuals`.** Two
  different events had the same function name and only avoided collision because
  `jhsaa.py` aliased one at the import — a trap for the next reader.

## Tests

`tests/test_jhsaa_jv_state.py` runs a **real JV season** — an empty-state check cannot
see a single rule in this event, since every one of them is about who a played season
made eligible. It now also forces a field big enough to play the qualifying round,
because a fixture that crowns twelve regions silently skips the path the association
takes every year.
