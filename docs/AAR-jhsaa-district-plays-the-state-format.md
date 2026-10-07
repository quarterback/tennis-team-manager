# AAR — District duals play the class's State format; Individual State widens to match (owner rule 2026-10)

## The rule

**A district dual plays its classification's State format.** The district title is
what qualifies a program for the road to State and protects its entry, yet most classes
spent that league season playing a different version of tennis from the championship it
fed. The showcases rehearsed the championship format; nothing *lived* in it. Now each
class plays its own format all through league play:

| Class | District before | District now | Dressed |
|---|---|---|---|
| 9A · 8A · 7A · Group 1 · 10B | 3S/4D | **4S/5D** | 14 |
| 5A | 3S/4D | **6S/5D** | 16 |
| 6A · 11B | 3S/4D | 3S/4D | 11 |
| 4A · 3A · 2A · Group 3 | 3S/4D | **1S/4D** | 9 |
| 1A | 3S/4D | **2S/3D** | 8 |
| Group 2 | 3S/4D | **3S/3D** | 9 |

Unchanged: the early window (5S/2D, every class), invitationals — every non-district
regular-season dual, rivalries, the challenge and old-league pairs included — (3S/4D),
showcases (the host class's State format), the TOC (1S/4D).

The season therefore reads: 5S/2D early → 3S/4D invitationals → the class's own format
in district play → the same format on the road to State.

**Individual State keeps its core six championships and adds every flight the class's
State format contests** — 84 → 110 championships a gender:

| Class | Slate |
|---|---|
| 9A · 8A · 7A · Group 1 · 10B | S1–S4 + D1–D5 |
| 5A | S1–S6 + D1–D5 |
| 6A · 11B · 4A · 3A · 2A · Group 3 | S1–S3 + D1–D4 |
| 1A · Group 2 | S1–S3 + D1–D3 |

No class loses No. 2 or No. 3 Singles because its championship dual seats one singles
flight. And **entries are seated by the class's State arrangement**, not by rank: the
preseason ability order is the input and `jhsaa._arrange_postseason` decides the seats.
5A's top eight supply S1–S6 and D1 and the strongest configuration decides who plays
singles; #9–#16 form D2–D5 in doubles-strength order. A D5 individual champion in 5A is
somebody who has played D5 all through district play — the championship corresponds to a
real season-long position.

## How it is wired

- **`dual_format(phase, group, district=True)`** — a district regular-season dual is the
  third "rehearsal" member beside the road and the showcases, so it falls out of the
  existing branches: `district_format(group)` *is* `dual_format("state", group)` and
  must never become a second table. `district_need(group)` is its lineup size.
- **District duals stay `phase="regular"`.** The phase is the archive's identity for an
  event, and the archive row already carried `district`. What changed is that `phase`
  alone no longer names a shape, so `play_dual` threads `district` everywhere a shape is
  resolved: `_lineup`, `_credit`, `shape_group`, and `rating_duals` →
  `flight_weights(..., district=)` (a 9A league dual rates on `FLIGHT_WEIGHTS_4S5D`, a
  5A one on `FLIGHT_WEIGHTS_6S5D`).
- **The résumé log gained a seventh field** (`district`), appended last so every
  indexed reader (`m[2]`, `r[4]`) is untouched; the awards unpack with a trailing `*_`.
  The awards price each appearance on the table it was actually played at.
  ‼️ One six-field unpack (`jhsaa_awards._pairs`) was missed on the first pass and only
  a FULL-SIZE season found it — the targeted suites passed, because their fixtures never
  reached `build_pool` with district duals in the log. Grep every `= m` unpack, not only
  the `for ... in log` ones.
- **Lineup.** A district dual takes the ordinary regular-season branch of `_lineup` —
  live ladder, participation rule, talent-aware rest, bench rotation, captains — dressed
  to the district size, then arranged by `_arrange_postseason` at the shape (no Order of
  Ability freeze: that binds from the first postseason dual and still does). 6A/11B's
  district format is 3S/4D and keeps `_arrange_regular`'s philosophies.
- **Group 2 district duals can tie.** 3S/3D is even. Regular season, so the JV ladder
  (points, sets, games) and then a TIE: `TeamSeason.dties`, half a win in
  `district_pct`, a W-L-T `district_record`. `world._wl` partitioned on the first hyphen
  and read "12-3-1" as 0-0 — fixed. (None occurred in the measured boys season's 436
  Group 2 district duals; the tests pin the path with a program played against a copy
  of itself.)
- **Roster-facing readers follow the district lineup.** The preseason store's V1 cut
  and the rising-freshman portal's projected V1 seat read `district_need`; captains are
  drawn from the smaller of the district and invitational dressing groups, so a captain
  dresses for every league dual by construction.
- **Readers that meant "the 3S/4D regular season"** — the format profile's regular
  sample and the analytics sidecar's derived regular card shape — now read non-district
  regular duals only. A most-common vote over a phase that now carries six shapes would
  pick whichever class is biggest.
- **Individual State**: `flights_for` / `flight_counts` / `slate_format` /
  `arrange_sheet` / `flight_ranks` (positions in the ARRANGED sheet) / `entry_count` /
  `mixed_from_rank` in `jhsaa_individuals`. `FLIGHTS` is the union S1–S6, D1–D5 for name
  lookups and the repeat-champions flight ranking. The bracket page reads a season's
  slate off the archive (`world.jhsaa_individual_flights`), so a season played on six
  flights renders six, never empty S4 tabs.

## Measured (full-size boys association, season 2031, before → after)

| | before | after |
|---|---|---|
| Season wall time | 383 s | 442 s (+15%) |
| Individual State draws | 84 | 110 |
| Players with ≤5 varsity matches, all classes | 47.0% | 46.0% |
| 5A — ≤5 matches / median matches | 40.8% / 10 | **29.8% / 21** |
| 9A — | 50.0% / 6 | 45.1% / 12 |
| Group 1 — | 48.6% / 7 | 43.1% / 15 |
| 1A — | 44.8% / 9 | 51.5% / 5 |
| 4A — | 47.1% / 8 | 51.3% / 5 |
| Group 2 — | 51.7% / 4 | 56.7% / 3 |

That is the consequence accepted deliberately: the wide classes put three to five more
players on court in every district dual, the narrow ones two to three fewer. The
classifications now demand different things of a roster.

## Open / decided after

- **`jv_pool` now follows the district lineup** (owner decision, the same day):
  JV starts directly below the class's district dressing group — #15 in the 4S/5D
  classes, #17 in 5A, #12 in 6A/11B, #10 in the 1S/4D classes and Group 2, #9 in 1A.
  Measured at roster level, 16 of 82 girls' and 14 of 77 boys' 5A programs drop
  below `JV_MIN_SPARE` and field no JV; every other class keeps all its JV teams.
  The JV State freeze (`jv_postseason_cut`) did not move.
- **The 1S/4D classes' and 1A's slates are arranged one or two singles seats wider than
  their State format** (4A arranges S1–S3 + D1–D4 off its top eleven, with S1–S3 and D1
  drawn from the top five), because they keep No. 2/No. 3 Singles that their State
  dual does not seat. The alternative — arrange the State nine exactly and seat S2/S3
  from #10/#11 — makes "No. 2 Singles" the tenth player and was not taken.
- No year gate, following the 2070 (4S/5D) and 2094 (6S/5D) precedent: archived seasons
  are read, never re-simulated.
