# AAR — JHSAA exchange students (owner rule 2026-09)

**Owner ask.** Copy the mechanic that puts flag-bearing internationals in the
college game into the high-school game, as exchange students — "a realistic
wrinkle … usually a really good way to help smaller programs infuse talent."

**Scope:** `app/jhsaa.py` (the `EXCHANGE_*` block, `_exchange_weights`,
`exchange_student`, one append in `build_roster`), `app/web/state.py` and two
templates (flags), `tests/test_jhsaa_exchange.py`.

## ‼️ HALF OF IT ALREADY EXISTED AND NOTHING RENDERED IT

`_draw_name` has drawn new-era cohorts at ~90% weighted-US / 5% Canada / 5%
international since 2026-08, and its own comment calls that slice "the
exchange-student slices". Measured in the owner's 2075 boys export: **1,722 of
17,718 players (9.7%) already carry a foreign flag** — 827 Canada, then Spain,
Italy, Germany, Russia. `p.country` is stamped on every one of them, and the
college, coach, portal and GTT pages have rendered flags all along.

**The JHSAA simply never passed the field to a template.** So the first half of
this feature was a view-model line and a Jinja conditional, and it is worth
having on its own: a tenth of the association had a nationality nobody could see.

Those cohort players are NOT exchange students, and that draw is untouched here.
They are four-year seats, born in Jefferson, generated as US with the flag
stamped after — an immigrant-family veneer. Widening or re-cutting that draw
would rename every archived roster (it is era-gated for exactly that reason).

## The arrival

A real exchange student is a different object, and the owner's spec settled every
question that would otherwise have needed machinery:

| | |
|---|---|
| **Duration** | ONE season. "Like a senior that graduates in terms of how the game treats them the next year." |
| **Grade** | 11, always. |
| **Eligibility** | Everything — league, postseason, individual draws. "JHSAA allows exchange students in the post-season." |
| **Displacement** | Allowed. "That's not a problem." |
| **Visibility** | A flag on the player profile and NOTHING else. "It's all behind the scenes … they're like any other student to the UI." |

**Grade 11 is load-bearing beyond flavour.** `jhsaa_recruit_class` takes
`x.grade == 12` and `apply_to_class` swaps those graduating seniors into the
national recruit class's Jefferson slots. An eleventh-grader is never in that
set, so *a real exchange student goes home* with no filter written anywhere. If
`EXCHANGE_GRADE` is ever allowed to be 12, that exclusion becomes hand-built.

**One season needs no deletion and no table.** A JHSAA season is rebuilt from
seed, so the year they played still produces them — their box scores, honours and
player page keep resolving forever — and the next year's build simply does not.
Nothing is stored, nothing is migrated, nothing expires.

## ‼️ THE ROLL IS PER SCHOOL — the `upstart` lesson, and why there is no table

A first instinct is a global draw: pick N programs a season. That is **non-local**
— adding or dropping one program changes which OTHERS host, retroactively
rewriting archived seasons' rosters, and archived box scores would then name
players the rebuilt roster no longer contains. `upstart` already learned this
("the draw runs over the WHOLE pool and skips tagged schools AT APPLICATION").

`exchange_student` is a per-school Bernoulli keyed on `(school, year, salt)`. One
school's answer cannot depend on another's existence, so an archived season
rebuilds identically after a sponsorship edit, a rename or a reclassification
elsewhere. Expected ~41-44 arrivals a gender against ~870 programs (**~5%**,
measured).

## ‼️ NOT A SMALL-SCHOOL MECHANIC — one rate, four excluded archetypes

The first build rationed arrivals by classification (1A 0.08 down to 9A 0.02).
That was **inferred, not asked for**: the owner said this is "usually a really
good way to help smaller programs infuse talent", which describes the EFFECT on
a small program, not a request to ration it by class. Corrected (owner rule
2026-09): *"any school from Group 3 to 9A can roll an exchange student … it's not
exclusively a mechanic for smaller programs."*

- **`EXCHANGE_RATE` is a single number** (0.05) for the whole association.
- **`EXCHANGE_EXCLUDED_ARCHETYPES`** — `blue_blood`, `coaching`, `neglect`,
  `turnout` — do not host. Each is a program whose story is already about its own
  intake. `upstart` is deliberately not among them: a rolled run, not a standing
  property, and the owner did not name it.

Measured: 44 arrivals (boys) / 41 (girls), ~5% of programs, spread across every
classification (9A 6, 1A 4, Group 3 4 in one boys season).

‼️ **And the class table was broken as well as unwanted.** It keyed on
`school.group` — the CHAMPIONSHIP a program enters — so a played-up 3A competing
in 7A drew 7A's rate rather than 3A's. **Anything reading a program's class must
read `classification` (what it IS), never `group` (where it plays)** — the same
distinction `_TALENT` turns on, and the same one the play-up rule exists to
protect. There is now no class term at all, so neither fault can return.

## The talent lift

`EXCHANGE_MEAN` +6.0 and `EXCHANGE_SPREAD` ×1.35 on the program's own modifier —
the same lever `blue_blood` (+15.0) and `upstart` use, so a blue blood's arrival
is still drawn on a blue blood's numbers. Measured: arrivals land at a **median
80th percentile** of their class, **19% arrive as their team's No. 1**, and ladder
ranks on arrival run 1 to 17 — usually a real addition, sometimes an ordinary
squad player. A flat lift with the class's own spread would make nearly every
arrival a No. 1 and turn the mechanic into a championship lottery, which is the
fall portal's curated-flow lesson in another costume.

## The nationality mix (owner, 2026-09)

Built from the owner's own **`global_college`** preset — the widest one, whose
docstring is "realistic NCAA geography, Africa fully represented" — with the
Americas re-cut. **Derived, never typed**, so an edit to the preset moves it.

‼️ Deliberately **not** `_intl_weights`'s `tennis_global`, which is a PRO-TOUR
mix: it carries Africa at ~3% and no meaningful Caribbean, the opposite of who
actually crosses for a school year.

The Americas are **14%** of the mix, split **1% Canada** ("they almost never are
exchange students"), **8% West Indies**, **5% Latin America**, with
country-by-country South America dropped ("Americas should just be caribbean,
latin america"). Everything else keeps the preset's proportions:

| | share |
|---|---:|
| Europe | 29.9% |
| Africa | 23.3% |
| Asia | 23.0% |
| Americas | 14.0% |
| Oceania | 8.1% |
| Middle East | 1.5% |

The three pinned blocks are shares of the FINISHED mix and the rest of the world
is scaled to fill what they leave, so changing one is one number.

## ‼️ THE ROLLOUT ERA — the defect that would have corrupted a real save

The first build called `exchange_student` unconditionally. **Every archived JHSAA
season is rebuilt from seed** — `jhsaa_school_view`, `jhsaa_player_view` and the
research export all replay history through `build_roster` — so on a save with ten
years of history, ~5% of rosters in EVERY one of those years would have grown an
extra player who was not there when that season's duals, ladders and honours were
written. Phantom team-mates, shifted ladder positions, and stored results
disagreeing with the roster rendered beside them.

`exchange_era()` is the `name_era` idiom (`_resolve_era`) and gates on the
SEASON: a save with an archive starts arrivals at the first UNPLAYED season, a
fresh save gets 0, and an explicit `worldconfig` value wins. Verified on a
fabricated ten-season save — 2036 and earlier produce nothing, 2037 onward is
live.

‼️ It gates on the SEASON where the other four gate on an entry-year COHORT,
because an arrival belongs to one season rather than to a class of players.
`_resolve_era` returns the right number for both: the newest archive's season is
`BASE_YEAR + index + 1`, so the first unseen season and the first unseen cohort
are the same year. Cleared in `reset_schools()` with the rest.

**The general lesson:** in this section a new roster ingredient is retroactive by
default. Anything that changes who is on a roster needs an era gate before it
needs anything else.

## Traps this build stepped around

- **The name is redrawn, the player is not.** `_gen_seat` generates AS US and
  stamps the flag afterwards — deliberately, because `generate_prospect` branches
  on country and consumes the rng differently, so passing the real country would
  shift every attribute roll. The arrival's nationality comes from a different
  mix, so it is restamped on its own rng after generation. The name stream inside
  `_gen_seat` is a sub-rng, so replacing its result shifts nothing.
- **The arrival is appended after the `ROSTER_FLOOR` top-up**, like a transfer. A
  program's floor is what it fields on its own; counted toward it, a thin program
  would run a seat short in the years one turns up and be fine in the years one
  does not.
- **`EXCHANGE_SEAT_BASE` is 900**, far above anything `_freshman_class_size`
  rolls (real rosters run 12-36) and above the floor top-up's continuation, so an
  arrival's pid can never collide with a cohort seat's.
- **No marker exists and none may be added.** No badge, no roster label, no
  record column, no `Prospect` field — the only thing distinguishing an arrival is
  `country`, which ~10% of ordinary players carry too. A test pins this.

`EXCHANGE_ENABLED` is the kill switch and first diagnostic: off, every roster is
byte-identical to the pre-feature association.
