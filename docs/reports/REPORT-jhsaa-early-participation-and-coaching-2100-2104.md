# JHSAA: early participation and coaching, 2094–2104

Owner analysis off the research exports through the 2104 export (the repo's season
retrospectives relabel 2104 as canonical 2030; the world years are kept here as the
exports carry them). Two studies: how the 7th/8th-grade rule (JHSAA rule 2100) and the
rising-freshman portal have played out, and how much a head coach is worth. A third
section sizes the maturity settings against what the data now shows. The two studies
were written first; the settings table was added when the owner asked to boost early
participants' longer-term potential impact on a gradient.

Sources: the early participation data (7th and 8th graders since 2100) and the coach
data since 2093, both from the exports. The `early_seasons` field is a list of years
and was counted as such. Older seasons lack a `squad` column; the coach study fills it
before folding.

---

## 1. Middle school (7th and 8th graders in 1A, 2A and Group 3)

**It launched with a one time wave.** In 2100, 2,587 seventh graders and 2,619 eighth
graders appeared across both genders. The average roster in those three classes went
from 25 to 36. By 2102 it settled to about 500 to 600 early players a year statewide.
That's about one per small program, and about 2 percent of their varsity seats.

**They play and hold their own.**

| 2104 | Played varsity | Won their flights |
|---|---|---|
| 7th graders | 67% | 50% |
| 8th graders | 70% | 49% |
| Freshmen in the same classes | 75% | 48% |

Measured against their own teammates, early players in grades 9 to 11 win within a
point of everyone else. Their raw numbers look worse only because they cluster on
weaker programs.

**It fills rosters.** Each year 63 to 95 small programs, roughly one in six, would be
under the 20 player floor without them.

**No development payoff yet.** Small school freshmen win 48 percent of their flights,
against 49 before 2100. Players who played early aren't pulling ahead of classmates by
grade 11. Varsity playing time in those classes dipped about 4 to 6 points because
rosters are bigger. The first full six season careers reach senior year in 2105, so
the real test starts then.

**The rising freshman portal:**

- **Volume:** 2,303 moves, 1,147 in 2101, 880 in 2102, then 138 a year.
- **Playing time:** 93 percent were on the new roster, and every one of them played
  varsity.
- **Results:** they won 23 percent of their flights, against 52 percent for other
  freshmen. That's 21 percent for moves into bigger classes and 25 percent for moves
  to another small class. Players proposed into seats 1 to 3 also won 23 percent.

So the portal buys a varsity seat but not wins.

---

## 2. Coaching

About 20,000 head coach seasons from 2094 to 2104. Coach quality isn't tied to school
size (correlation of negative 0.03), so the pattern below is a real effect, not a
matter of good coaches landing good jobs.

| Head coach tier | Program seasons | Win rate | Made State | Titles per 100 seasons |
|---|---|---|---|---|
| Bad | 1,087 | 43.6% | 38% | 0.6 |
| Poor | 1,651 | 46.4% | 42% | 1.5 |
| Below average | 3,121 | 47.7% | 42% | 1.2 |
| Average | 6,189 | 47.4% | 43% | 1.0 |
| Good | 4,132 | 49.2% | 44% | 1.6 |
| Excellent | 2,537 | 50.6% | 46% | 1.9 |
| Elite | 1,227 | 53.5% | 51% | 1.9 |

- **Size:** Elite against Bad is about 10 points of win rate, roughly 2.5 wins in a 25
  dual season. One tier of coach quality is worth about 2 points.
- **How it works:** about three quarters of the effect runs through the roster. The
  other quarter shows up on court with the same roster.
- **It takes years.** Win rate points gained per tier of head coach quality:

| Years in the seat | Gain |
|---|---|
| 1 to 2 | +0.2 |
| 3 to 5 | +1.4 |
| 6 or more | +3.2 |

- **Swaps barely register at first.** In the two seasons after a head coach change,
  programs that got a 15 point upgrade or downgrade saw no difference, up 2.0 and up
  3.0 points.
- **On court:** only Changeover clearly shows in results. Between evenly matched teams
  the better changeover side wins 54.5 percent of duals, and 52.2 percent of one point
  duals. Clutch shows nothing: the better clutch side won 50.9 percent of one point
  duals.
- **Roster side:** Program builder is the strongest, then Feeder ties. Development
  shows up only weakly.

**Pacific Gate.** The boys won 92 percent of their duals in Cameron's 11 seasons,
against 93 percent predicted from their rosters alone. Their dominance comes from the
roster she built, so replacing her won't sink the program quickly.

---

## 3. Sizing the pre-high-school maturity boost

The pre-HS boost today is about 0.4% of ceiling per early player. The settings table
below shows what higher would look like.

**What the data shows now (2104 export)**

| | Early seasons | Ever had an event | Average reveal per player, share of ceiling | Reveal of 10% or more |
|---|---|---|---|---|
| Not early | 0 | 7.8% | 0.40% | 1.5% |
| Early | 1 | 12.9% | 0.75% | 3.0% |
| Early | 2 | 16.0% | 0.81% | 2.8% |

Those are players in grades 10 to 12. The boost from being early is about 0.4
percentage points of ceiling on average, roughly 0.25 rating points on a 60 ceiling.

- **Event rate:** a maturity event fires 5.2% of the time at 7th grade, 6.0% at 8th,
  and 7.6% to 8.2% at 9th. The 9th grade rate is the same for early and non-early
  players, so early play adds two extra rolls at about 5 to 6 percent each.
- **Size when one fires:** the average reveal is about 5% of ceiling, and the top ones
  reach 24% to 28%.
- **Results:** an 8th grade event almost never lands in a player's first two years on
  the varsity.

**What different settings would do for the pre-HS events** (7th and 8th grade only)

| Setting | 8th grade only: any event / 5%+ reveal / 10%+ reveal / average | 7th and 8th: any event / 5%+ reveal / 10%+ reveal / average |
|---|---|---|
| Now (rate 0.35, caps 6% and 15%) | 6.0 / 2.5 / 1.1 / 0.30 | 10.6 / 3.0 / 1.1 / 0.40 |
| Rate 0.60 | 10.3 / 4.3 / 1.9 / 0.51 | 17.5 / 5.2 / 2.0 / 0.69 |
| Rate 0.60, caps 10% and 25% | 10.3 / 5.7 / 3.8 / 0.86 | 17.6 / 8.2 / 4.0 / 1.16 |
| Rate 0.90, caps 10% and 25% | 15.4 / 8.6 / 5.7 / 1.29 | 25.2 / 12.1 / 6.2 / 1.73 |
| Rate 0.90, caps 12% and 30% | 15.4 / 9.2 / 6.5 / 1.54 | 25.1 / 13.3 / 8.0 / 2.09 |

- **Method:** these use the maturity and playing time mix the export implies, with the
  `u²` skew and halved realisation left as they are.
- **Ceiling on the rate:** at today's playing time, even rate 0.90 leaves three
  quarters of 8th graders with no event.
- **Caps:** raising the caps moves the top of the distribution far more than raising
  the rate does.
- **Size of the lift:** the best row is about five times today's average reveal.

The constants these rows move are `jhsaa.MATURITY_RATE` and `jhsaa.MATURITY_POT_CAP`
(`docs/AAR-jhsaa-early-participation.md` §4). No setting has been changed on the
strength of this table; the decision is the owner's.
