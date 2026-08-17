# AAR — the JHSAA postseason ran eight classifications through one queue

## The report

Owner, 2026-08, browsing a program page: *"it doesn't matter but why is the season
stretching so far out — what is the logic doing that makes the season last through July
for girls and making it skip October for boys?"*

A 2A-1A boys card ended its regular season on **Oct 11** and played its Regionals on
**Jan 17**. The girls' season, opening in March, ran into **July**.

## ‼️ The part that matters most: nobody told them

This was not a subtle bug. **A high-school tennis season ending in July is wrong from
across the room** — you do not need the code, the data or a test to see it. It shipped
anyway, and the owner found it themselves, months later, and had to ask.

The decision that caused it was made by an agent, in a function that had no owner rule
behind it, and its consequence was never surfaced. That is the failure being recorded
here — the arithmetic below is the easy part.

**When a change makes a season span a different number of MONTHS, that is a
user-visible product decision, not an implementation detail.** It belongs in the
message to the owner, in the commit body, and — if it looks wrong — in a question
before the commit rather than an explanation eight months later.

The reason it stayed hidden is worth naming too, because it will recur:

- The calendar is **presentation**. Nothing reads a date back; no simulation decision
  depends on one. So no test asserted on it, and none would have.
- **Every card was individually plausible.** Espoo's schedule reads correctly: duals in
  order, dates ascending, both sides agreeing. Only the SPAN was absurd, and a span is
  a property of the whole season that no single page shows.
- The Espoo card looked like it "skipped October", which is a third thing again: Espoo
  was protected and entered at Regionals, so those weeks are other teams playing. The
  visible symptom did not point at the cause.

## What the code was doing

`world.jhsaa_match_dates` paints dates onto the finished archive. There is no clock in
a JHSAA season — the whole association runs in one rung at week 0 — so a dual's date
comes from its POSITION in the play order, packed into rounds and laid on a Mon/Wed/
Fri/Sat pattern.

The postseason advanced stage by stage on a single global floor:

```python
if r_rank != cur_rank:            # a stage opens after the previous one closes
    floor_r, cur_rank = top_r + 1, r_rank
```

`top_r` is the highest round used by ANY dual so far — **across the entire gender**. So
7A's Regionals could not be dated until 2A-1A's Sectionals had finished. Eight
classifications that never play each other were serialised into one queue, and an
eleven-stage ladder therefore cost roughly eight times what any one class actually
plays.

## The fix

Each classification gets its own lane. A stage waits only on the previous stage OF ITS
OWN CLASS; every lane opens at the same postseason window and advances independently.
The postseason now runs as long as the longest single class's ladder instead of the sum
of all eight.

Three things were deliberately left alone:

- **The regular season keeps one shared calendar.** Invitationals and showcases cross
  classifications, so those duals genuinely do share a queue.
- **‼️ The TOC is not a lane.** It fields the champions of every classification, so it
  is the one postseason event with a real cross-class dependency and it still waits on
  all of them. Given a lane of its own — keyed on either school's group — it could be
  dated before a state final it depends on.
- **Match order, qualification and results.** This function reads a finished archive
  and decides nothing but what day a dual is printed on.

**Lanes key on the classification the season was ARCHIVED in**, read off
`world_jhsaa`'s standings, never off today's school list: reclassification and play-up
both move a program, so the live map would file an old season's duals under the wrong
lane. With no archive the map is empty, every dual falls into one lane, and the
behaviour is exactly what it was before.

Verified on a two-classification fixture: both ladders run side by side on identical
dates, and the TOC lands after both finals.

## What to check first if this looks wrong later

- **A postseason spanning months again.** Print `min`/`max` of the dates per
  `(classification, phase)`. Two classes' matching stages should share a date; if they
  ladder past each other, a lane key is coming back empty and everything has collapsed
  into one lane.
- **A TOC dual dated before a state final.** The `phase == "toc"` branch in the lane
  floor is what prevents it — it takes `max(lane_top.values())`, not one group's.
- **An archived season's duals in the wrong lane.** `_jh_school_groups` reads the
  standings of that year. A program that has since reclassified or started playing up
  will be right in the archive and wrong in any live lookup.
