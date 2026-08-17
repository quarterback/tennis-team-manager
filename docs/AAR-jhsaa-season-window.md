# AAR — the season ran until it ended, instead of fitting the season

## The report

Two reports, a day apart, about the same page.

**"You all keep skipping entire months in the schedule."** A boys' card showed
invitationals on Aug 28 and Sep 4, then three showcases dated **Oct 2**, then league
play resuming **Sep 22**. The dates ran backwards, and there was an eighteen-day hole
where the showcases should have been.

**"The entire season has to be done by the end of October for boys / early June for
girls."** The postseason was finishing in **December**.

## ‼️ The season had no end date. That is the whole story.

`world.jhsaa_match_dates` laid four slots a week — Mon/Wed/Fri/Sat — onto the round
order and stopped when it ran out of rounds. **Nothing in the function knew when a
season is supposed to be over.** A fall sport finishing in December is not a rounding
error; it is a calendar with no closing date being asked to produce one.

The window is now the input, not the output: the day pattern is chosen so the last
dual of the postseason lands inside it. Mon/Wed/Fri/Sat when that fits, Tuesday added
when it does not, Thursday after that. Never a Sunday — 6 is in no pattern, which is a
guarantee rather than an intention. A season that genuinely cannot fit renders on the
densest pattern rather than being silently rescheduled into the winter, because a
too-long season should be visible on the card.

`_JH_SEASON_CLOSE` is Oct 31 for boys and Jun 7 for girls, with a week of grace — the
owner's "early November at the absolute latest".

## The missing fortnight was the showcases, thrown a month forward

`_jh_showcase_days` landed each window on a Saturday, and kept them on distinct
weekends by walking forward from the **previous window**:

```python
while last is not None and sat - _dt.timedelta(days=1) <= last:
    sat += _dt.timedelta(days=7)
```

`last` is the previous window's Saturday. Nothing in that loop refers to the round the
window was actually played in, so the error compounds: with six to eight windows in a
season, the last of them lands a month past its own rounds. The league duals around it
keep their round-derived dates, so the card shows October showcases sitting between
September league duals — and an empty fortnight where those showcases belonged.

Both halves of the report were the same bug. **The "skipped month" was not a gap in
the schedule; it was matches that had been moved out of it.**

A window is now anchored to its own round and nudged only within its own span. Distinct
weekends still matter — nobody is at two showcases in one day — but a collision moves a
week at most, never unbounded.

### And a guarantee, since this class of fault will recur

Anything that dates a dual outside the ordinary round pattern can put it before a match
its own team already played. The showcase weekends do it; a future event would too. So a
final pass walks the play order and holds each dual on or after the last date either of
its teams has been given. Nothing is reordered — the sequence is the archive's and is not
up for revision — only pushed to the next slot, which is what a real fixture list does
when a date slips.

## Why nobody caught either of these

The same reason the [postseason lanes](AAR-jhsaa-postseason-calendar-lanes.md) went
unnoticed, and it is worth stating a second time because it is now three faults deep:

- **The calendar is presentation.** Nothing reads a date back, no simulation decision
  depends on one, so no test asserts on it and none would have.
- **Every individual row was right.** Correct opponent, correct score, correct tag. Only
  the RELATIONSHIP between rows was wrong — order in one case, span in the other — and no
  single row shows a relationship.
- **The symptom pointed away from the cause.** "Skipping a month" reads as a scheduling
  gap. It was a dating bug in a different feature entirely.

## What to check first if this looks wrong later

- **A card reading out of order.** The monotonic pass at the end of `jhsaa_match_dates`
  is what prevents it; if it is bypassed, whatever assigns dates outside the round
  pattern is the suspect, not the round packer.
- **A season running past its close.** Print `_jh_pattern`'s inputs — the round total and
  the weeks available. A total that no pattern can hold means the ROUNDS grew (a longer
  ladder, a bigger district), and the fix is there rather than in the calendar.
- **A hole in one program's card.** Check the gap against the whole gender: a program not
  in a showcase window genuinely has an idle weekend, which is not the same fault.
