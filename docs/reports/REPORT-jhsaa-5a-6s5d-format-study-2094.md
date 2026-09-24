# JHSAA 5A format study — the 6S/5D petition (2092–2094 exports)

**Question.** 5A member schools petitioned to replace 1S/4D with **6S/5D** — eleven
flights, the most expansive format in the state — arguing it would make 5A the singles
class and get more players in the lineup. The association's objection was roster capacity.
Should it be granted?

**Answer.** Yes, and the capacity objection is unfounded. It was already falsified by
play the association has been running for years. What the petition *does* force is a
roster-floor decision, because a sixteen-player lineup against a floor of sixteen leaves a
floor-sized program with no bench — and that turned out to collide with a second,
unrelated problem: the JV ladder had outgrown bands that were never resized for it.
Both were fixed in the same rule.

Adopted as **JHSAA rule 2094**. See `docs/AAR-jhsaa-2094-5a-6s5d-and-roster-bands.md`
for what changed in the code.

Script: `scripts/jhsaa_5a_6s5d_roster_study.py` (reads the exports — a measurement of
seasons as played, not an engine counterfactual like `jhsaa_6a_format_study.py`).
Data: 2092/2093/2094 exports, both genders, all classifications — 5,373 program-seasons,
152,522 varsity dual-sides, ~1.13m flight results.

---

## 1. Capacity

Players in the lineup is **S + 2D**. Verified rather than assumed: across all 152,522 varsity
dual-sides in the three exports, one player occupies exactly one flight. No forfeits, no
double-booked lines anywhere in the archive.

5A, 445 program-seasons, against the old band (18, 20) and the old floor of 16:

| shape | flights | in the lineup | min spare | median spare | % unable to field |
|---|---|---|---|---|---|
| 1S/4D *(the old format)* | 5 | 9 | 7 | 10 | 0.0% |
| 3S/4D | 7 | 11 | 5 | 8 | 0.0% |
| 4S/4D | 8 | 12 | 4 | 7 | 0.0% |
| 3S/5D | 8 | 13 | 3 | 6 | 0.0% |
| 4S/5D | 9 | 14 | 2 | 5 | 0.0% |
| **6S/5D** | **11** | **16** | **0** | **3** | **0.0%** |

Not one 5A program-season in three seasons falls short of any candidate shape, 6S/5D
included — but at 6S/5D the thinnest programs dress their entire roster, which is the
finding that moved the floor (§3).

**It is not theoretical.** 5A dual-sides by shape as actually played:

| shape | 5A dual-sides | failed to fill the format |
|---|---|---|
| 3S/4D | 9,071 | 0 |
| 1S/4D | 1,949 | 0 |
| 5S/2D | 1,012 | 0 |
| **4S/5D** | **231** | **0** |

Fifty-five distinct 5A programs have played 4S/5D — a fourteen-player lineup — in showcase pods
and tiered showcases, because under "the wider format wins" a 5A side drawn against a
wide-class host simply plays nine flights. Seventy-eight of those sides were played by
programs carrying seventeen players or fewer, several at exactly the sixteen-player
floor. None came up short. The association's objection describes a constraint that was
not operating.

## 2. The petition was for the weighting, not the width

Singles share of every postseason shape the association runs:

| shape | flights | singles share | who |
|---|---|---|---|
| 1S/4D | 5 | 20.0% | 2A, 3A, 4A, Group 3 |
| 2S/3D | 5 | 40.0% | 1A |
| 3S/4D | 7 | 42.9% | 6A |
| 4S/5D | 9 | 44.4% | 7A, 8A, 9A, Group 1 |
| 3S/3D | 6 | 50.0% | Group 2 |
| **6S/5D** | **11** | **54.5%** | **5A** |

Nothing in the association is singles-majority in the postseason; Group 2's 3S/3D is
exactly even. The claim that 6S/5D would make 5A distinct is correct on its own terms,
and it is a claim about **weighting** — a class that wanted width alone would have asked
for 4S/5D, which was available and is not what was petitioned for. `FLIGHT_WEIGHTS_6S5D`
carries it through to what a flight is worth: singles take 500 of the table's 895 (55.9%)
across six flights, while S1 and D1 stay tied at 2.00 as they are on the 4S/5D table. The
total is odd in hundredths by construction, which puts half of it out of reach of any subset
and so makes a level FWS unreachable — FWS is the anti-stacking signal, and a level result
prices nothing. Checking that invariant turned up three older formats mispriced the same way
(5S/2D 370, 2S/3D 350, 4S/5D 750, which tied on S1+S2+S3+D5); all three are corrected to odd
under the same rule.

Eleven flights is odd, so a 6S/5D dual cannot tie. That is the reason to prefer it over
4S/4D and 3S/5D, the two other expansive shapes considered: both are eight flights, both
tie in 10.7–15.5% of duals (measured by re-scoring the 3,658 duals that actually
contested all nine flights), and adopting either would have meant adopting a tiebreak
regime alongside the format.

## 3. What it forced: the floor, and the JV ladder

The old floor of 16 was never arbitrary — it was **the varsity eleven plus the five a JV
dual needs**. Two things broke it at once, and only one of them is about 5A.

**5A's format needs sixteen.** A floor-sized program would dress its whole roster with
nothing in reserve — the same "no bench at all" failure the original floor of 12 existed
to prevent, arriving by a different door.

**The JV ladder had outgrown the bands.** `jv_format` is unbounded and reaches 6S/5D at
sixteen spare, but the bands still reflected the table it launched with. Measured on the
old settings, every class in the association bottomed out at the same three-flight JV
minimum, and **three bands had minima below the floor** (1A 14, Group 3 14, 2A 15) —
dead numbers the floor was silently overriding.

Both fixed together: floor **16 → 20**, every band re-cut, and 5A split from the band it
shared with 4A since 2027-08.

| class | old | new | JV spare | JV format at min → max |
|---|---|---|---|---|
| 9A, 8A | (20, 24) | (26, 30) | 15–19 | 5S/5D → 7S/6D |
| Group 1 | (19, 22) | (25, 29) | 14–18 | 4S/5D → 6S/6D |
| 7A, 6A | (19, 22) | (24, 28) | 13–17 | 5S/4D → 5S/6D |
| Group 2 | (17, 20) | (24, 28) | 13–17 | 5S/4D → 5S/6D |
| **5A** | (18, 20) | **(23, 26)** | 12–15 | 4S/4D → 5S/5D |
| 4A | (18, 20) | (22, 24) | 11–13 | 3S/4D → 5S/4D |
| 3A | (17, 19) | (21, 24) | 10–13 | 4S/3D → 5S/4D |
| 2A | (15, 17) | (21, 23) | 10–12 | 4S/3D → 4S/4D |
| Group 3 | (14, 17) | (20, 23) | 9–12 | 3S/3D → 4S/4D |
| 1A | (14, 16) | (20, 22) | 9–11 | 3S/3D → 3S/4D |

Every class now reaches at least 3S/3D on JV, every band minimum is at or above the
floor, and a floor-sized 5A program dresses sixteen with four spare.

## 4. ‼️ The JV SEASON is not touched by this, and an earlier pass got that wrong

Worth recording because it inverted a conclusion. `jv_pool` cuts at
`lineup_need("regular")` — the **eleven-player league format**, hardcoded — not at the
postseason format. A road/State shape change therefore does not move the JV pool at all.

An earlier pass of this study assumed the cut followed the postseason format and reported
that 6S/5D would leave 61% of 5A programs unable to field a JV team and put 425 fewer 5A
players in a match. Both figures are wrong and neither was a reason for anything. What
*does* move is `jv_postseason_cut`, the JV **championship** field's eligibility freeze,
which is derived from `lineup_need` precisely so it follows a pilot's shape: 5A's freezes
at #17 down instead of #12, as designed.

## 5. What this study does NOT claim

No conclusion here rests on competitive balance — sweep rates, one-point rates, upset
rates. Those were measured and deliberately set aside: the petition was not made on
parity grounds and was not granted on them. (For the record, on the metric the 2079 6A
study used — one-point rate — 5A was unremarkable among the five-point classes at 31.2%
of State duals.)

This also supersedes recommendation 5 of `REPORT-jhsaa-6a-state-format-study-2079.md`
("Leave 5A, 4A, 3A and 2A alone"), which was reasoning about a different question on
thirteen earlier seasons.

## Caveats

- **No 6S/5D dual had ever been played**, in any class, in any archived season when this
  was decided. Everything about the shape itself is arithmetic on roster sizes and flight
  counts. The capacity case rests on 4S/5D play and on the roster distribution; the
  shape's own behaviour is unobserved until it runs.
- Only ten of the 231 5A dual-sides at 4S/5D were 5A-versus-5A; the rest were against
  larger classes in showcases. For "can they fill the format" the opponent is irrelevant.
- **Roster counts are season rosters, not per-dual availability.** The archive records
  who played, not who was held back. The zero-spare risk in §1 is structural — no 5A team
  has ever been asked to dress sixteen, so there are no forfeits to measure.
- The 2092 export keys ~1.9% of its `line_players` rows by name rather than player id,
  which collapses a few distinct players and shows up as an apparent short count on 46 of
  152,522 dual-sides. Keying artifacts, not shortfalls; excluded from the fill counts.
- Rosters reflect the current association configuration applied to archived seasons, per
  the export's own documentation.
