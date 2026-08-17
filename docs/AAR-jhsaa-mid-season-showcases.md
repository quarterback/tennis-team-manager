# AAR — JHSAA mid-season Match Showcases (the 1S/4D weekend events)

## The report

Owner (2027-08): the association's postseason "completely shifts to a 1S/4D model",
so programs need real in-season opportunities to test doubles pairings and build
chemistry — **without extending the calendar**. The answer specified: mid-season
showcases on open Saturdays and Friday–Saturday blocks, "NON-COMPETITIVE SHOWCASES
(not tournament brackets, not compass draws, zero elimination, no champions)", a set
number of fixed duals in the 1S/4D format against cross-regional / cross-classification
opponents, and a **hard guardrail that a program never meets a same-district opponent**.

Four corrections arrived while it was being built, and all four are in the code. Three
of them corrected ME, not the spec:

1. **Drop the data-integration section entirely** — "we already track the data." No
   Doubles Pairing Efficiency metric was written. Individual and pairing résumés
   already come off `TeamSeason.matches`, which showcase duals feed like any other.
2. **"Full Best-of-3 Standard Advantage Sets"** — "we play no-ad scoring always in
   JHSAA play." The two-day block is the ordinary `PRESETS["high_school"]`.

   ‼️ I first wrote this correction up as the spec contradicting itself, and that was
   my error, not the spec's. **The three scoring switches are independent and none of
   them implies another** — worth stating plainly, because getting them tangled is how
   a format gets silently mis-set here (see the terminology note below).
3. **A non-district dual is an INVITATIONAL** — "instead of NON-DIST, they are called
   'Invitationals' (Invite)". `NON-DIST` was a literal string on the schedule card.
4. **The showcase results ARE TOSS-rated** — I shipped them excluded and the owner
   reversed it: "that's the point of doing them… it doesn't matter if the format is
   different, it's still really important power scoring… the matches still count."
   See the section below; this is the one that would have quietly made the rating
   worse.

## Terminology — three independent switches, and a tiebreak is TWO different things

`engine.format.MatchFormat` models these as separate flags for a reason; conflating
any two of them mis-sets a format with nothing erroring, because every combination
produces plausible scorelines.

- **No-ad** (`no_ad`) is about **deuce**: the next point wins the game. It says nothing
  about sets, tiebreaks or match length. All JHSAA play is no-ad — league, showcase,
  State (owner rule).
- **A SET tiebreak** (`set_tiebreak`, `set_tiebreak_target`, `set_tiebreak_at`) is
  played **inside a set that is level near its end** — at 6-6 in a standard set, or at
  8-8 in an 8-game pro set — first to 7 by 2. The pod's "7-Point Tiebreaker at 8–8" is
  this one.
- **A MATCH tiebreak** (`final_set_tiebreak`, `final_set_tiebreak_target`) is played
  **in lieu of a third set**, when the players have split sets — first to 10 by 2. It
  is the thing that makes a match *not* a full best-of-3.
- **An advantage set** is a set with no set tiebreak at all: win by two games, however
  long that takes. Independent of both of the above.

So "Full Best-of-3" is a statement about the **match** tiebreak — there isn't one, the
third set is played for real — and that is what the two-day block does
(`final_set_tiebreak=False`), which is also exactly why it "replicates State length".
`high_school` is: no-ad, standard six-game sets with a set tiebreak at 6-6, and a real
third set.

Sources: [USTA — Tennis Scoring: Points, Sets & Games](https://www.usta.com/en/home/improve/tips-and-instruction/national/tennis-scoring-rules.html) ·
[USTA — Standard Tiebreak summary (PDF)](http://s3.amazonaws.com/ustaassets/assets/840/15/standard_tiebreak.pdf)

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

### Not a tournament, but fully rated — and I got this backwards first

I shipped `SHOWCASE_RATED = False`, reasoning that TOSS seeds every draw the association
runs, so a rated showcase would be a competitive event by the only measure that matters
here. The owner reversed it immediately: **the matches are TOSS-rated, and that is the
point of playing them.** "Literally playing power teams is precisely what people want,
it doesn't matter if the format is different — it's still really important power
scoring… the matches still count."

The error was reading "non-competitive" as "the results don't count". It means **no
advancement** — no bracket, no elimination, no champion, no title. It says nothing about
whether a played result is real, and a rating is exactly where a real result belongs.

And the rating is the part of the system that wants these duals most. TOSS is
40% APR + 40% FQI + 20% oGS and all three are opponent-weighted, so a program that plays
its league twice and a handful of nearby non-league opponents is rated on a nearly
disconnected results graph. A showcase is three or four duals against cross-district,
cross-classification programs the schedule would never otherwise produce — the cross
edges the whole composite is starved of. Throwing them out would have discarded the
best evidence in the season and left the rating measurably worse than before the events
existed.

**Two dual shapes in one rating is fine, and it is worth knowing why.** `_flight_score`
divides by the weight actually CONTESTED in each dual, not by a constant, so a 1S/4D
showcase (S1 1.00 + D1 1.00 + D2 0.50 + D3 0.25 + D4 0.10 = 2.85) and a 5S/2D league
dual (3.70) each yield a 0–1 share and average together correctly. `_game_share` is a
ratio too, so the pod's shorter pro sets do not under-weight it. Verified on a mixed
fixture: no raise, and the ordering is sensible.

‼️ The consequence to remember: `FLIGHT_WEIGHTS`'s **D3/D4 are now load-bearing in the
regular season**. They were added for the in-postseason recomputes with a comment saying
the cutoff TOSS never sees them; that comment was true until this feature and is now
wrong. A missing weight there raises by design — which is the correct behaviour, but it
means the cutoff table and the 1S/4D shape are coupled from here on.

They also count in the **record** (a record is a record — the postseason is carried the
same way) and feed every individual and pairing résumé the awards read, which is why
correction #1 above cost nothing: that data was already being tracked.

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
- **A showcase MISSING from a ranking.** `SHOWCASE_RATED` should be True and the
  `drop` tuple in `rating_duals` should not name the phases — and remember
  `prestate=True` is a second drop list.
- **`_flight_score` raising on D3 or D4.** Those weights are load-bearing in the
  regular season now, not only in the in-postseason recomputes.
- **Three duals on three different days.** Something is playing events sequentially
  rather than session by session, so the window is no longer a contiguous block of
  rounds and `_jh_showcase_days` cannot see it.
