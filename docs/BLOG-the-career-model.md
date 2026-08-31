# Nobody waits their turn: rebuilding player development in a tennis sim

I coach high school tennis. Last spring I graduated a pair of two-time state doubles
champions, and to finish second at state I needed two sophomores, two other seniors who
didn't win a match, and a freshman who made the singles final. This year my two
returning starters are seniors and neither is close to the best player on the team — my
best players are ninth and tenth graders. For the last few seasons I've had eighth
graders good enough to play varsity.

That's just what the sport looks like. So when I went back to the high school
association inside my tennis sim and saw that **seniors held 85.7% of the No. 1 singles
seats**, I knew the development model was wrong. Not miscalibrated. Wrong in its
premise.

This is the story of finding out what it was actually doing, what I replaced it with,
and the several times my own diagnosis turned out to be the thing that needed fixing.

It's a sequel to [the baseball post](https://gamedesign.leaflet.pub/3mn7c3uzctk2a) about
interest-rate development and access lenses. I thought I'd ported that model into tennis
already. I had, sort of. That turned out to be the problem.

## Two models, sharing nothing

The first surprise was that there were two development systems in the same repository
and they had almost nothing in common.

The college side runs the baseball model, right down to the vocabulary —
`interest_rate`, `tier_mult`, `fog`, the 75/20/5 tier split. Growth closes a fraction of
the gap to a fixed ceiling every year:

```
frac = interest_rate × GROWTH_K (0.12) × tier_mult
current[a] += frac × (potential[a] − current[a])
```

The high school side never calls that function at all. JHSAA rosters aren't persisted —
every player is regenerated from `(school, gender, entry year, seat)` — so
"development" there is the same fixed ceiling read through a grade-dependent maturity
number. Two halves of one sim, arriving at "nobody regresses, everyone improves" by
completely different routes, tuned independently, neither aware of the other.

Both were doing less than I thought.

### The college side barely moves anybody

Multiply out the tier table and the ordinary player — 75% of every class — closes
**0.6% to 6.0% of their remaining gap per year**. A median ordinary player with a 60
ceiling entering college at 51.9 finishes senior year at **52.7**.

That's +0.8 OVR across a four-year career. And because college freshmen already arrive
at 83–90% of their ceiling, there was nothing to develop in the first place. The college
problem isn't "wait your turn," it's that class year means nothing at all.

### The high school side is a queue

The JHSAA had a per-player trajectory model I'd added a while back: arrival band, finish
band, a curve shape. Better than the lockstep bands before it. Measured on three
consecutive archived seasons (2057–2059, ~17,800 girls and ~17,300 boys per season):

| grade | mean access | p10 | p50 | p90 |
|---|---:|---:|---:|---:|
| 9 | 0.614 | 0.455 | 0.596 | 0.800 |
| 10 | 0.706 | 0.569 | 0.702 | 0.842 |
| 11 | 0.781 | 0.675 | 0.781 | 0.885 |
| 12 | 0.870 | 0.791 | 0.875 | 0.938 |

**13.4% of freshmen reach the junior median. 1.3% reach the senior median.** The old
lockstep model put that second number at 0.0%, so the trajectory pass had moved it —
from zero to almost zero.

## Measuring before changing

I wrote a script to fold three seasons of research exports into a baseline, because I
wanted the "after" to have something honest to be compared against. Some of what came
back reframed the problem.

**The amount of development was fine.** Tracking the same player across two seasons,
freshmen gained **+8.5 OVR (girls) / +9.7 (boys)**, p10 +2 to p90 +16. That's real
movement with a real spread. I'd assumed I had a growth problem. I had an *ordering*
problem — everyone was improving in parallel, so nobody passed anybody.

**The ceiling was immobile.** Same player, two years: the ceiling moved for **1.0% of
players, mean +0.02**. In practice, fixed. Which means every bit of surprise in the sim
had to come from access — and access was tightly ordered by grade. There was nowhere for
a surprise to come from.

**A quarter of the association never plays.** Of players present all three seasons,
**25.4%** never once reached the varsity lineup.

**And a lot of talent was sitting invisible.** Rank each roster by ceiling instead of
current ability and freshman lineup presence goes from 31.9% to **54.8%** — 1.7× the
freshmen who'd earned a spot weren't getting one.

One thing I nearly got fooled by: the 2059 seniors' ceilings read about five points
higher than the freshmen's, which looks like a development effect and isn't. It's a
talent-compression rule that phased in at entry year 2057, so the seniors were the last
pre-compression cohort. Any before/after measurement spanning that boundary has to
control for entry year. Ceilings are fixed at generation, so comparing *those* across
the boundary is the clean read; comparing current ability is dominated by the fact that
the older cohorts are mostly seniors.

## The Oregon detour

I have six seasons of real OSAA results sitting in
[a repo](https://github.com/quarterback/or-tennis-data) — 295,219 varsity appearances
across 11,135 players — so I went and looked at what a real lineup is shaped like.

The data has no usable grade field. Every player carries a `grade`, but 99% of rows read
"Graduated," and the `graduatedDate` beside it is mostly a bulk data-entry stamp:
deriving grade from it puts 30.8% of appearances in grades 13 through 15. So grade has
to be inferred from each player's own appearance span, which has no unbiased form —
assume everyone's last season was senior year and you count every dropout as a senior;
assume everyone's first season was freshman year and you count every late starter as a
freshman. I bracketed it both ways and read the middle: players with a full four-season
career, where both assumptions agree and nothing is inferred.

Share of No. 1 singles:

| | 9 | 10 | 11 | 12 |
|---|---:|---:|---:|---:|
| Oregon boys | 5.3% | 19.7% | 32.3% | 42.7% |
| Oregon girls | 6.3% | 27.0% | 30.1% | 36.6% |
| **my sim** | **1.7%** | **4.6%** | **12.2%** | **81.5%** |

And the measure that needs no grade at all: **a returning No. 1 keeps the seat 63.6%
(boys) / 63.4% (girls) of the time.** More than a third get passed. My sim passed one in
ten.

Two things jumped out. The bigger miss was **sophomores**, not freshmen — 20–27% of real
No. 1 seats against my 3–5%. And a real varsity lineup is nearly flat by grade
(15/25/29/30), not a queue.

I want to be careful about how I'm using this, because I've had to say it out loud more
than once since: **Oregon is a reference point, not a target.** Jefferson's talent
distribution is my own and it's better than Oregon's. I looked at these numbers to
understand the *shape* of a real lineup, not to fit to them. Any time an optimization
loop starts pointing at that table, the loop is wrong.

## The first fix, and why it wasn't enough

My first instinct was to keep the fixed-ceiling architecture and just make access
schedules more individual. I built a harness that swaps only the access model over the
same real rosters, same real ceilings, same real grades, so anything that moves is
attributable to the model and nothing else.

The control — a reimplementation of the shipped model — reproduced the measured baseline
to within a few tenths, which is what let me trust the rest of the table.

Then I found the actual lever, and it wasn't the one I expected. `DEV_FINISH` was
`(0.76, 0.94)` — narrow — while arrival spanned `0.40–0.82`. The schedules *converge*.
Almost everyone lands near 0.87 of their ceiling as a senior. Which means:

> Under a fixed ceiling and a converging access schedule, the senior-year ladder is
> ceiling-ordered — and the ceiling is fixed at generation. **The senior ladder is
> decided at birth.** Every shape in the curve table just varies the route to a
> predetermined finish.

Widening the finish band helps. It moved No. 1 retention from 90.7% to 84.8% and
freshman No. 1 share from 1.3% to 3.8%. But then I bounded the whole approach by
building a deliberately illegal model — access redrawn freely every year, violating both
the no-reroll rule and monotonicity — just to see the ceiling of what *any* fixed-ceiling
access model could do:

| | swaps | No. 1 retention | senior No. 1 |
|---|---:|---:|---:|
| shipped | 7.3% | 90.7% | 87.4% |
| best legal recalibration | ~9% | ~75–85% | 75–81% |
| *unconstrained (illegal)* | *36.3%* | *24.2%* | *51.0%* |

Recalibrating gets you to the mid-to-high 70s and stops. That's when I stopped trying to
retune the thing and went back to the premise.

### A metric that was measuring the wrong thing

Worth flagging, because I'd been leaning on it: my headline success metric — the rate at
which returning teammates swap ladder order — was mostly measuring roster size. It counts
every pair, including the No. 2 player against the No. 18 player, who are twenty points
apart and will never trade places.

Restrict it to pairs that could actually cross and the *shipped* model already reordered
25.0% / 27.4% of them. The number that was genuinely broken was No. 1 retention. Pick a
metric that can only move for the reason you care about.

## The model I settled on

Stop treating development as "age reveals a fixed ceiling." A player is four things,
drawn once at entry, and grade only says which point of their own path to read:

```
PLAYER
├── STARTING ABILITY     where they are on day one
├── CAREER PEAK          the best they get to be DURING high school
├── YEARLY CAPACITY  ×4  how much they can realise each year
└── EXPOSURE             what they actually played, scaling realisation
                              ↓
                    realised gain = capacity × exposure
                              ↓
                        clamped at career peak
```

The break from everything before it is that **starting ability and career peak are drawn
separately**. They correlate; neither is derived from the other. So all of these are
ordinary outcomes:

```
61 / 63    already a finished player as a freshman
51 / 70    elite upside
38 / 64    a project
44 / 47    basically done at fourteen
31 / 55    ordinary, with room
```

Career peak is not a debt the engine owes anybody by senior year. A 34/67 player whose
capacities come up mediocre finishes 34 → 37 → 43 → 49 and simply never becomes what he
might have been. That needs no regression mechanic — it's just unrealized capacity. And
there's no privileged senior development year anywhere in the model; the biggest growth
year can land in any grade.

Career shapes — ready, early, steady, late, spike, stagnant, high-peak-never-realized —
are *emergent* from the capacity draws. They're never labeled and never stored.

### Playing time is an odometer, not a category

Exposure accumulates as varsity-equivalent units — a JV appearance worth half a varsity
one — saturates, and maps to a realization factor from 0.55 (rostered, never dressed) up
to 1.0 (a full varsity season). One continuous rule, so split-time players land between
the levels without needing a category of their own, and the JV ladder matters: a JV No. 1
who plays every dual banks more than a JV kid who barely appears.

It multiplies the player's *own* capacity, which is what keeps it from homogenizing
anybody. A stagnant player with +1 capacity gets about +1 no matter how much he plays.
An explosive sophomore with +12 gets ~12 on varsity, ~10 on JV, ~6 sitting. Adolescence
happens either way, which is why the floor is 0.55 and not zero.

Nothing in it reads wins, records, opponent quality, team finish, or state
qualification. The system doesn't care whether you won. It cares that you played.

### Two things I got wrong building it

**The clamping artifact.** My first parameterization drew starting ability as a blend of
a peak-anchored term and an independent population draw, then clamped it at peak. For
low-peak players that clamp fires constantly and silently sets start = peak. It
manufactured a 26% "already finished" share and 53% of players with no real growth year,
and it looked like a design outcome. Draw the *fraction* and multiply — never blend and
clamp.

**The taper isn't authored.** I'd asked for breakouts to land sophomore and junior year
with the senior year incremental, which is how it actually works — the leaps happen
before then. When the model produced exactly that, I initially read the low senior number
as the model under-weighting the senior year and started to "fix" it.

It isn't a fix, and there's no age rule anywhere in the model. Capacity is drawn
identically in all four years. Senior years grow less **because most players have already
reached their peak and a big late draw has nowhere to land**. The clamp produces the
taper. That means the overflow constant — how much of a gain still lands once you're past
peak — is load-bearing in both directions:

| overflow past peak | 9→10 | 10→11 | 11→12 | Y3 ÷ Y1 |
|---:|---:|---:|---:|---:|
| 0.00 (hard wall) | 3.9 | 3.3 | 2.5 | **0.62** |
| 0.20 (shipped) | — | — | — | **~0.73** |
| 1.00 (no cap) | 4.5 | 4.6 | **4.5** | **1.00** |

At full overflow the senior year gains exactly as much as the freshman year — the
seniority leap I'd just ruled out, back through the side door. I shipped 0.20: about a
third of players finish above their career peak, so peak reads as a projection rather
than a wall, and the taper survives. There's a test that sets overflow to 1.0 and asserts
the taper *disappears*, because I want the mechanism pinned, not a description of it.

## The matchup curve, which turned out to be a separate disaster

Along the way I asked for the match engine to read OVR differences in roughly
seven-point competitive bands — 0–6 peers, 7–14 modest, 15–21 clear, 22–28 strong, 29+
major — with volatility preserved among peers and the favorite strengthening
progressively above that.

I'd assumed this was a matter of retuning the hinge in the gap curve. It wasn't. Under
the shipped high school profile:

| OVR gap | favorite wins | favorite wins, hinge removed entirely |
|---:|---:|---:|
| 3 | **94.7%** | **92.9%** |
| 6 | **100.0%** | 92.9% |

A three-point gap was already a 95% favorite, and deleting the hinge barely moved it.
The gap is a per-*game* hold edge compounded over twenty games and two or three sets, so
the slope saturates the match long before any knee matters. The bands were unreachable by
touching the hinge; the whole curve had to come down — from a slope of 6.0 to 0.9, with a
banded piecewise map replacing the single hinge.

| gap | band | target | measured |
|---:|---|---|---:|
| 0 | peer | 50% | 50.1% |
| 6 | peer | ~62% | 60.5% |
| 14 | modest | ~75% | 73.2% |
| 21 | clear | ~87% | 85.5% |
| 28 | strong | ~95% | 95.2% |

There's a real cost: the old curve had been fitted against real Oregon *set-score*
distributions, and the flatter curve doesn't reproduce them — 6-0 sets collapse from
~28% to ~2% at a six-point gap. I took that trade knowingly. It may resolve itself, since
the steep curve produced blowouts partly because matched-line gaps on a compressed talent
distribution are small, and the distribution is no longer compressed. That's a
re-measurement for after everything settles, not before.

## Freeing the high school scale

The last piece. Jefferson's rating scale had been doing two jobs — representing how good
someone is *within high school tennis*, and guaranteeing that graduates fit onto the
college scale. Those are separate problems and one of them was distorting the other.
Talent compression was squashing ceilings so they wouldn't overrun a scale high school
doesn't play on.

So high school became internally unconstrained, and translation happens at graduation.
A Jefferson player can legitimately be an 84 or a 96; those numbers mean something only
inside the JHSAA.

The thing I expected to be the hard part turned out to already exist. The hand-off into
the college recruit board was *already* a pure identity swap — the national class is
generated on the college scale, and Jefferson graduates get rank-matched into its
Jefferson slots with ability deliberately not transferring. Someone (me, years ago) had
tried copying grades across, found it recalibrated the entire board, and reverted it with
a comment explaining why. That rank-match *is* percentile-primary translation. Freeing
the high school scale can't leak into the college game by construction. All I had to add
was the record — exit rating and percentile stamped on the player so the history survives.

I also had the size of this backwards at first: I'd written that going past 80 would be a
change across display, STR, and grade normalization. It mostly isn't. The scale ceiling
is already 100, the unit conversion deliberately has no upper clamp, and the pro tier has
been generating above 80 for ages. The path was already there.

## Where it landed

Same association, all four grades on the new model. Share of No. 1 singles:

| | 9 | 10 | 11 | 12 |
|---|---:|---:|---:|---:|
| **before** | 1.5% | 3.3% | 9.4% | **85.7%** |
| **after** (girls) | 13.3% | 18.3% | 26.7% | **41.7%** |
| **after** (boys) | 15.0% | 19.4% | 31.7% | **33.9%** |

Lineup share went from 32/49/66/81 to 42/52/62/71 — much closer to flat. Freshmen
reaching the senior median went from 1.3% to 8.7%.

To be explicit, since I keep having to be: these are **not** Oregon's numbers and aren't
meant to be. The freshman share sits well above Oregon's 5–6% and I want it there. My
talent generation is different and better, and the point was never to reproduce another
state's distribution — it was to stop roster order being decided by birthday.

## What I'm watching for

The model is gated by entry year, so it phases in over four seasons as classes turn
over. The association won't be fully converted until every pre-era cohort graduates,
which means the next few seasons are mixed and any measurement across them has to
control for entry year — the same trap the talent-compression boundary set for me
earlier.

Beyond that, in rough order of how much I care:

**Career shape variety in seasons I actually play.** Not the census — the felt
experience. Do I get a sophomore who wasn't there last year? Does a kid I wrote off as a
JV player turn into a starter as a junior? Does a highly-rated freshman plateau and get
passed? The numbers say those exist; I want to see them happen in a season I'm following.

**Whether stagnation reads as stagnation or as a bug.** It's only 3–4% of careers at the
current settings. If a flat career looks broken rather than true, the fix is more of them,
not fewer — a stagnant player should be a recognizable type, not an anomaly.

**The exposure gradient.** Sitting < JV < varsity is wired but the constants are a first
guess. I want to see whether a kid who splits time genuinely arrives ahead of one who
spent the year at JV, and whether that difference is legible on a player card.

**The scoreline distribution, after everything settles.** The flat curve and the free
scale push in opposite directions on blowouts. I'll re-measure once the association is
fully converted, on the distribution that will actually exist, rather than defending a fit
that was made under different conditions.

**Whether the top of the scale needs more room.** Ceilings now reach into the 90s, and
the hard clamp is at 100. If generational players start bunching against it, that's a
number to move, not a distribution to squash.

---

The thing I keep coming back to: the old model wasn't producing bad players. It was
producing bad *careers* — everyone improving on the same schedule, so a player's rank in
their first season was very nearly their rank in their last. Fixing that wasn't about
growing anyone faster. It was about making two players with similar talent capable of
having genuinely different four years, and letting the kid who's ready at fourteen simply
be ready at fourteen.

Which is, more or less, what I see every spring.
