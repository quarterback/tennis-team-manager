# AAR — the Conference round, ATR, and the retirement of the district guarantee

**Date:** 2026-08-16
**Status:** Landed. Owner rules 2027-08.
**Scope:** `app/jhsaa.py` (`ATR_TOSS_WEIGHT`, `atr_of`, `atr`, `_atr_key`,
`CONFERENCE_NAME`, `POSTSEASON` + `_RECOVERY_NAMES`/`_RECOVERY_UNITS`,
`_recovery`, `run_season` standings row), `app/world.py` (`run_jhsaa` archive,
`jhsaa_group_ranking`), `app/web/state.py` (bracket stage folds),
`app/web/templates/jhsaa_rankings.html`, `tests/test_jhsaa_ladder.py`,
`CLAUDE.md`, `docs/JHSAA-road-to-state.md`.

## Three owner rules, one shape

They arrived separately over one session and turned out to be the same design:

1. **There is no district guarantee — you win your way in.** The guarantee was
   the owner's own earlier rule, and they retired it themselves on noticing it
   contradicted the rule it sat beside: "a district champion could keep losing
   and automatically get into the field at state, and that's not what I want at
   all." A district title now buys a PROTECTED seat (entry at Regionals) and
   nothing at State.
2. **A conditional last rung**, because berths move with membership: "it can be
   like other rounds where if we don't need it, it doesn't trigger."
3. **No Ward playbacks.** Ward losers were being drafted into the Super Regional
   pool as bodies, which gave them Super Regionals, a readmission to Semi-State
   and then Divisionals — two or three bites, while a Zonal loser got one — and
   berths were being earned off them three rounds early. They now enter at the
   **Conference** and nowhere else.

The recovery ladder as it stands:

| Round | Field | Takes berths |
|---|---|---|
| Super Regionals | the 16 Regional losers | no |
| Semi-State | SR winners + Zonal losers + readmitted SR losers | yes |
| Divisionals | the best Semi-State losers | yes |
| **Conference** | Divisional losers → district champions still outside the field → top Ward/Sectional/Area losers **by ATR** | **every berth still outstanding** |

Measured full size, both genders, every field full and every round pairing its
entire field:

```
24-classes   SR 16   SS 22   DV 10   Conference —      24/24
40-classes   SR 16   SS 24   DV 12   Conference 28     40/40
```

The Conference is dormant in the 24s and load-bearing in the 40s, which is
exactly the "if we don't need it, it doesn't trigger" shape — the trigger just
happens to be pulled every year in the big classes.

## ATR — the one thing not rated on TOSS

`ATR_TOSS_WEIGHT` (0.5) × `pi_raw` + the rest win percentage. The owner's
reasoning, which is the whole justification and belongs next to the constant:

> "i'd take a 18-20+ win team regardless of schedule strength if they win a
> post-season game of consequence over a middling team in a hard district
> propped in TOSS by their opponents"

TOSS is an opponent-strength composite. That trade is right for **seeding a
draw** and wrong for **the last seat in the tournament** — and the Conference
pool is the only place in the association that is deciding the latter, which is
why it is the only place ATR is used. Entering on ATR is still a chance to
PLAY, never a berth.

It is **archived** on the standings row beside `pi` and read back, never
recomputed — the Power Index rule, and it binds harder here because ATR is what
an actual pool was ordered by. `atr_of(pi, win_pct)` is the single formula both
the archive and the pool ranking call, so the number on the rankings sheet and
the number the round ran on cannot drift apart.

## What I got wrong, for the record

**I answered a design question with the fixture instead of the association.**
Asked whether Divisionals could fill a 40 field, the honest answer needed a
full-size run; the test fixture is `ladder_scale`d and cannot see the arithmetic
that matters. The full-size run found **4A one berth short, 39 of 40**, while
every other classification filled — the Semi-State floor `ceil(4·berths/3)` was
rounded up to even AFTER the reservoir had been sized to the un-rounded value,
so the window asked for one pair more than had been gathered and the odd-drop
took a pair back off. An odd floor is the only case that triggers it. **Round
the constraint before sizing to it, not after.**

**I proposed widening a pool to fix a starvation that was upstream of it.**
When the owner suggested dropping Ward playbacks, I offered "widen the
Conference pool" as a fix and had to walk it back one message later: without
playbacks the entire recovery universe is 16 Regional + 8 Zonal losers = 24
candidates, and no round structure produces 32 berths from 24 teams. Widening
the last round cannot help when every candidate it would draw on is already
counted. The owner's own answer — let Ward losers in at the Conference — was
the right one precisely because it brings NEW teams in rather than giving the
same teams more chances. **Count the candidate universe before designing the
rounds that divide it.**

**I built a cross-draw nobody needed.** The Conference briefly paired two pools
against each other, which needed a `pairs=` override threaded through
`_recovery_round`. The owner: "can you just drop this rule entirely and reseed
the field like we do for all the other rounds." One pool, one pairing rule,
override deleted. The special case was mine, not the design's.

**I ran things without showing them.** Several full-size simulations went by
with nothing surfaced between them, on work whose whole value was the numbers
they produced. The owner had to ask twice. On a design change, the measurement
IS the deliverable — show it before it is codified, not after.

## Related

- `docs/AAR-jhsaa-qualifiers-round.md` — the expanded fields the Conference
  exists to fill.
- `docs/AAR-jhsaa-state-expansion-recovery-rounds.md` — the byeless-recovery
  design this extends.
- `docs/JHSAA-road-to-state.md` — the player-facing explainer.
