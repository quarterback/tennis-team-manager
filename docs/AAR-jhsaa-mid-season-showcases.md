# AAR — JHSAA mid-season Match Showcases (the 1S/4D weekend events)

## The report

Owner (2027-08): the association's postseason "completely shifts to a 1S/4D model",
so programs need real in-season opportunities to test doubles pairings and build
chemistry — **without extending the calendar**. The answer specified: mid-season
showcases on open Saturdays and Friday–Saturday blocks, "NON-COMPETITIVE SHOWCASES
(not tournament brackets, not compass draws, zero elimination, no champions)", a set
number of fixed duals in the 1S/4D format against cross-regional / cross-classification
opponents, and a **hard guardrail that a program never meets a same-district opponent**.

Three corrections arrived while it was being built, and all three are in the code:

1. **Drop the data-integration section entirely** — "we already track the data." No
   Doubles Pairing Efficiency metric was written. Individual and pairing résumés
   already come off `TeamSeason.matches`, which showcase duals feed like any other.
2. **"Full Best-of-3 Standard Advantage Sets" was wrong** — "we play no-ad scoring
   always in JHSAA play." The two-day block is the ordinary `PRESETS["high_school"]`.
   The written spec was self-contradictory anyway (an *advantage set* is a set with no
   tiebreak; a *standard set* has one), and the sentence beside it — "replicates exact
   JHSAA State Championship match length" — was the half that survived.
3. **A non-district dual is an INVITATIONAL** — "instead of NON-DIST, they are called
   'Invitationals' (Invite)". `NON-DIST` was a literal string on the schedule card.

## What the shape had to satisfy, and why the numbers are what they are

The spec fixed a daily load rather than a field size, and the field sizes fall out of it:

| | daily load | field | rounds | why that field |
|---|---|---|---|---|
| 1-Day Pod | 3 duals, one Saturday | **4** | 3 (full RR) | four programs is the only round robin that gives every entrant exactly three duals — and **three pro sets is the USTA junior daily limit**, which is also why the pod is scored as a pro set rather than a best-of-3 |
| 2-Day Tiered | 2 duals × 2 days | **6** | 4 | a 6-team round robin's **first four rounds are four perfect matchings** — every program plays in all four sessions, so the block falls 2 + 2 with nobody sitting out a day |

Five would have been the obvious tier size (a full round robin of 5 is four duals each)
and it is wrong: those four duals come in **five** rounds with a bye in each, so a
program sits out a session and the "2 per day" claim stops being true of the event.

## The decisions worth writing down

### A showcase is TWO phases, not one label

The mid-season *challenge* that already existed is a `challenge` flag on a non-district
dual, deliberately — it plays the ordinary format and belongs in the rating. A showcase
is the opposite on both counts: a different dual shape (1S/4D), a different scoring
format for the pod, a different place on the calendar. So it is a **phase**, which is
this archive's identity for an event — and it is *two*, `showcase_pod` and
`showcase_tiered`, because written as one phase a card could not tell a pod from a
tiered block and `world._jh_showcase_days` could not date either one.

### Not a tournament means not rated

"No bracket, no champion, no title" is easy to honour and would have been cosmetic on
its own. **TOSS is what seeds every draw the association runs** — Wards, Regionals,
Zonals, the recovery ladder, the State field — so a showcase feeding TOSS would be a
competitive event by the only measure that matters here, whatever the card called it.
`SHOWCASE_RATED = False` and `rating_duals` drops the phases from the cutoff table AND
from the in-postseason recomputes (which do rate 1S/4D duals, so the exclusion had to be
explicit in both).

They still count in the **record** — a record is a record, and the postseason is carried
exactly this way — and they still feed every individual and pairing résumé the awards
read. That is the data the events exist to generate, and it is why correction #1 above
cost nothing: it was already being tracked.

### The district guardrail is enforced at GROUP formation, not per pairing

The spec's pseudocode validates matchups and swaps on conflict. A showcase group is a
round robin, so **every member plays every other member** — validating the pairings that
were drawn would pass a 6-team tier block in which two league-mates simply happened not
to be paired in the four rounds played, and a redraw would then expose them. `_fits`
therefore rejects a candidate that shares a `(classification, name)` district with *any*
member of the group being filled, and the passed-over program is picked up by a later
group. That is the spec's "swap across pods" expressed as placement rather than repair,
and it makes an intra-district showcase match structurally impossible rather than
screened for. `showcase_conflicts` is the spec's `ensure_zero_district_conflicts`, kept
as a report so it can name offenders, and `play_showcases` refuses to play a slate that
fails it.

‼️ The key is the PAIR, never the name: the JHSAA reuses its district names at every
classification, so a name-only comparison both permits real league-mates through
(different name spellings never occur) and *blocks* pairs that have never met — measured
on the shipped slate, same-name cross-classification pairings are common and correct.

### The allowance vs the trade

Showcase duals are non-district, and counting them in the `NONDISTRICT_MIN/MAX`
allowance would have been the silent bug: a program's three pod duals would have eaten
its whole remaining card and it would have finished the season under the association's
minimum, with every individual number correct. What a showcase *does* cost is the trade
the spec names — a two-day block is played on a Friday and takes **one standard weekday
date** back with it — so `play_showcases` returns what each program traded and the late
tune-up shortens by that, and only that. A one-day pod is an open Saturday and costs
nothing.

### It must not freeze the Order of Ability

The freeze is the association's anti-stacking rule (`docs/AAR-jhsaa-order-of-ability.md`)
and it binds from a program's **first postseason dual**. A showcase plays the postseason
*card* in April, so the obvious implementation — reuse `_postseason_nine` — would have
frozen every attendee's championship lineup to its mid-season ladder and handed the rule
a month of drift it exists to prevent. A showcase dresses the LIVE ladder with the
league's bench rotation (a showcase is where a coach tries people) and arranges it onto
the 1S/4D card with the same `_arrange_state`.

### Ranking mid-season, without TOSS

The participation priority and the Open/B/C cut both need a statewide order, and TOSS
does not exist yet — it is computed once on the finished regular season, because it is
both the seeding input and rung 4 of the district tiebreak. `_showcase_rank` is
therefore the two things that do exist at the break: how the program has actually gone,
then the strength of the nine who dress. It decides who gets a scarce seat and which
tier they land in. Nothing is crowned off it.

### A window is one weekend

There is no clock inside a JHSAA season, so a dual's position in the play order is the
whole calendar and `world.jhsaa_match_dates` lays that order on a spring one. Left
alone, a pod's three duals would have been packed into three successive rounds and dated
Monday, Wednesday, Friday — a different event, with a daily load the pro-set scoring was
chosen to respect. `play_showcases` therefore plays **session by session across every
event in a window** (not event by event), which makes a window a contiguous block of
rounds, and `world._jh_showcase_days` lands that block: a pod on one Saturday, a tiered
block on Friday–Friday–Saturday–Saturday. A run is cut at the event's own session count,
so two back-to-back windows of the same kind are two weekends rather than one long one,
and the weekends walk forward so no program is shown at two showcases on one day.

## Measured on the shipped association (857 girls' programs)

```
events 86 · conflicts []
windows  0 pod · 1 tiered · 2 pod · 3 tiered · 4 pod · 5 tiered · 6 pod · 7 tiered
participation 44.9%   events per program: 1 → 363 (94.3%) · 2 → 19 (4.9%) · 3 → 3 (0.8%)
sizes  pod (4 teams, 3 rounds) · tiered (6 teams, 4 rounds)
```

Against the spec's 50% / 95% / 4–5% / ~1% (max 2–3 statewide at three): on target. The
participation share lands slightly under 50% because a group seed that cannot be filled
cleanly does not attend — a group is never completed with a league-mate and never played
short, and that is the correct way for the guardrail to lose.

## What to check first if this looks wrong later

- **A same-district showcase pairing.** `showcase_conflicts` should be empty and
  `play_showcases` should have raised. If it did not, look at `_dkey` before `_fits`.
- **Programs finishing under the non-district minimum.** Check that `spent` in
  `play_regular_season` still excludes `SHOWCASE` phases; that exclusion is the whole
  separation between the allowance and the events.
- **A showcase appearing in a ranking.** `SHOWCASE_RATED` and the `drop` tuple in
  `rating_duals` — and remember `prestate=True` is a second drop list.
- **Three duals on three different days.** Something is playing events sequentially
  rather than session by session, so the window is no longer a contiguous block of
  rounds and `_jh_showcase_days` cannot see it.
