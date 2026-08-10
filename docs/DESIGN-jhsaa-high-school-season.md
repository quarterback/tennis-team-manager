# DESIGN — Simulating the JHSAA high school season

Status: **BUILT.** `scripts/import_jhsaa.py`, `app/jhsaa.py`, `app/jhsaa_marks.py`,
`data/jhsaa/schools.json`, the swap in `world.recruit_class`, and the High School panel on
the recruit page. This doc is now the design record rather than a proposal; where the
build diverged from it, the code and the notes below are what happened.

Two things the build changed:
  * **Careers are grades 9-12 and persist by construction.** A player is keyed on the year
    they ENTERED, not the season played, so the same person keeps one pid, name and
    ceiling for four years and matures into it. Nothing is stored — the world rebuilds an
    identical career, which is also how `jhsaa.career()` renders four seasons on a recruit
    page in ~16ms.
  * **The hand-off swaps IDENTITY ONLY, not ability.** Copying a graduate's grades onto
    their recruit slot re-calibrated the national board (Jefferson's median recruit hit
    #278 of 2500). The national class decides how many Jefferson recruits exist and how
    they spread; the JHSAA decides who they are and what they did.

## Why

Two reasons, both the owner's:

1. **Immersion.** The point is to follow Jefferson the way you follow the colleges —
   watch a kid play four years at a real school in a real league, then sign him. Today a
   Jefferson recruit is a name with a high-school string attached and no history behind
   it.
2. **A live testbed.** The `cheesybook` tool (oregontennis.org/cheesybook.html) needs a
   high-school league in operation to test against, and real Oregon HS tennis can't be
   simulated. A deployed JHSAA gives it one.

Explicitly **not** a reason: fog of war. The owner has ruled that knowing who is good is
fine — it's a single-player game. Do not design around hiding results.

Also not a concern: that only Jefferson has a visible high-school layer while every other
state's recruits stay invented. That asymmetry is the feature.

## What this is not

Not an import of `prep-network`'s simulated players. That repo supplies **institutions**
— schools, classifications, cities, leagues — and the season is played *here*, by this
engine, with players generated and developed here. The earlier integration got this
backwards; see the AAR.

---

## 1. Dual formats (owner-decided, 2027-08)

| Phase | Format | Points | Ties |
|---|---|---:|---|
| Regular season | **5 singles / 2 doubles** | 7 | impossible |
| Postseason (dual-team state tournament) | **1 singles / 4 doubles** | 5 | impossible |

Both totals are **odd**, so a tie cannot occur and no tie-breaking logic is needed
anywhere — not in `duals.winner`, not in standings, not in the Power Index. This is worth
stating because an earlier 3S/3D proposal would have required all three.

**Every match plays to completion.** No clinch, ever, in either phase. The engine already
supports this: `simulate_dual(play_all=True)`, used today for D3/D4 regular-season and ITA
duals (`docs/AAR-d3-d4-play-play-format.md`).

Both formats drop straight into the existing dataclass — `DualFormat` is already
parameterised on exactly these fields:

```python
JHSAA_FORMATS = {
    "regular": DualFormat(n_singles=5, n_doubles=2, doubles_team_point=False),
    "post":    DualFormat(n_singles=1, n_doubles=4, doubles_team_point=False),
}
```

Read the shape through a helper, never by literal — the same rule `ncaa.dual_format` /
`ncaa.lineup_size` enforce on the college side.

**Roster floor is 9** with no player doubling up (5+4 regular, 1+8 postseason). Carry
10–12 for depth and injuries.

## 2. Which schools sponsor tennis

`prep-network` marks sponsorship per school, but its generator rolled `boys-tennis` and
`girls-tennis` independently, producing 202 boys / 441 girls teams and only 117 schools
fielding both — 3A alone has 10 boys teams against 81 girls. That is a generator artifact,
not a design, and it makes the boys' season unschedulable (20 single-team leagues).

Re-derive sponsorship at import instead, on the real-world pattern: **girls-sponsoring is
the superset; boys is a ~88% subset of it.** Schools that field girls tennis but not boys
are common; the reverse essentially does not happen. Co-op programs (a small school
feeding a host school's team) are **not modelled** — single schools only, co-ops imagined.

Rate by classification, applied once per school for girls, then a second roll for boys:

**These are the AUTHORITATIVE numbers — as built, from `data/jhsaa/schools.json`.**
Earlier drafts of this doc quoted 313/269 and 340/297 from separate modelling runs;
regenerate any downstream table from the committed data, never from a prose figure.

| Class | Girls rate | Schools | Girls teams | Boys teams | G districts | B districts |
|---|---:|---:|---:|---:|---:|---:|
| 7A | 85% | 119 | 102 | 90 | 9 | 8 |
| 6A | 70% | 118 | 80 | 65 | 7 | 6 |
| 5A | 55% | 123 | 69 | 62 | 6 | 6 |
| 4A | 35% | 141 | 52 | 48 | 5 | 4 |
| 3A-1A | 18/8/2% | 339 | 32 | 27 | 3 | 3 |
| **Total** | | **840** | **335** | **292** | **30** | **27** |

43 girls-only schools, zero boys-only. ~37% of schools sponsor tennis, which is right for
a mid-participation sport, and 1A stays near 2% because a school with a median enrollment
of 192 cannot field nine tennis players.

## 3. Districts

Do it the way Oregon does: **districts drawn per classification**, balanced, up to 12
teams. Districts are how playoff qualifiers get decided, which is their whole job — so
draw them for balance and geography and don't inherit anything.

`prep-network`'s 99 conferences can't carry this: they are all-sport geographic groupings
and 92 of them span multiple classifications, so filtering to one classification and to
tennis sponsors shatters them (even 7A leaves only four leagues with six or more teams).
Oregon's leagues are classification-pure, which is why an Oregon 6A league *can* host its
own tennis season. Jefferson's can't, so tennis draws its own map. Since this sim plays no
sport but tennis, a school's district simply **is** its league — there is no
home-conference or affiliate distinction to preserve.

Algorithm: sort each classification's sponsors by area → county → city (keeps a district
contiguous), then chunk into the fewest districts of ≤12 and balance. Name each for its
dominant **area**, falling through to its dominant **county** when that area name is
already used in the same classification.

Districts as built — 30 girls, 27 boys, every one 6-12 teams. Names come from the
committed data (`girls_district` / `boys_district`); a district is keyed by
(group, gender, name), since the same place name recurs across classifications the way
6A-1 and 5A-1 PIL would in Oregon.

Boys mirrors the same draw at ~86% of the teams. A district of 9–12 supports a double
round-robin inside a ~14-dual season, and the top N from each district advance to the
state tournament.

## 4. Talent

**Well below the college floor, and far wider.** College `_TALENT` bands are deliberately
dense — every D1 starter is a real player. High school is the opposite: a 7A #1 might be a
future D1 signee and a 1A #1 might not break a college walk-on's serve. The spread within
a single dual is the character of the level.

Needs its own per-classification band (mean, spread), 7A down to 1A, with the top of 7A
overlapping the bottom of the college recruit pool and the bottom of 1A far beneath it.
Calibrate against `scripts/eval_realism.py` once it exists. Do **not** reuse the college
bands scaled — the shape is different, not just the level.

## 5. Season shape and the state tournament

```
district double round-robin (16-22 duals by district size, 5S/2D)
  + non-district crossover, up to the season limit
  -> state dual-team tournament, 1S/4D, one bracket per classification group
```

**The regular-season dual limit is 28-33 (owner rule 2027-08)** — closer to baseball's
than to a college tennis schedule — and the **postseason is exempt from it**. An earlier
draft said "~14 duals", which no district size can satisfy: a 9-12 team district is 16-22
duals in a double round-robin on its own. The balance is played as non-district crossover
against schools in other districts of the same classification, which is what a real
high-school schedule looks like.

District place is decided on **district duals only** (`TeamSeason.district_record`);
crossover counts toward the overall record and therefore toward at-large selection. Both
are tracked separately for exactly this reason.

**Field sizes and qualification (owner-decided, 2027-08).** 7A takes the **top two from
each district**; every other classification takes the **district champion**. At-large by
record fills the remainder in all five.

| Class | Field | Auto bid | Girls teams | Boys teams | Districts (G/B) |
|---|---:|---|---:|---:|:---:|
| 7A | **32** | top 2 per district | 102 | 90 | 9 / 8 |
| 6A | **24** | district champion | 80 | 65 | 7 / 6 |
| 5A | **24** | district champion | 69 | 62 | 6 / 6 |
| 4A | **16** | district champion | 52 | 48 | 5 / 4 |
| 3A-1A | **8** | district champion | 32 | 27 | 3 / 3 |

Ten brackets in all, five per gender. A field that isn't a power of two seeds into the
next one up and the top seeds take first-round byes, so a 24-team field is a 32 draw with
8 byes.

`app/bracket.py` does NOT support this: it has no `build_bracket` and its `Matchup` has no
`bye` field — its team API is `run_bracket`, which keeps byes as implicit empty draw
slots. `jhsaa.run_state` therefore runs its own single-elimination draw, where a bye is a
`None` slot that advances the paired team. Do not "reuse" bracket.py here without
checking what it actually exposes.

7A is deliberately the most district-driven classification: 18 of its 32 girls' berths
(16 of 32 for boys) are won on the court in a district, and finishing second in a strong
district is worth as much as winning a weak one. The other four classifications lean the
other way — one automatic bid each, the rest selected on record — so a strong team in a
deep district is never squeezed out.

Reuses `bracket.py`, `state._bracket_canvas` and `templates/_bracket.html` — the Preseason
NIT already proved a third consumer can share that tree without forking the markup
(`docs/AAR-preseason-nit-bracket.md`).

## 5b. Cost, and where the season actually runs

**Known deviation from §6.** The season is NOT yet a rung on `advance_week`. It runs
lazily inside the first `world.recruit_class` build for a (salt, gender, grad_year),
because that is what needs the graduates. It is memoized per (salt, gender, year, seed),
so it happens once per world-year and never again.

That cost is real and was nearly an outage: at the engine's default `full` fidelity a
season is ~5,100 duals per gender and added **103 seconds** to the first recruit-class
build — on the request thread, which is precisely the failure CLAUDE.md documents twice.
High school now runs at **`fast` fidelity** (`jhsaa.FIDELITY`), which is 6.7x cheaper and
changes no winner, score or individual record — only per-point box detail, which nobody
is reading for a 9th-grade dual. Measured after: **19 seconds** for both genders, once.

Moving it onto the ladder as its own visible rung is still the right end state, and would
take the cost off the recruit path entirely. Until then, do not raise `FIDELITY` back to
`full` without re-measuring that number.

## 6. The clock

**Do not make the JHSAA a week-by-week universe under `advance_week`.** That fights the
one-world-one-clock rule and doubles the desync surface
(`docs/AAR-universe-desync-season-hub-advance.md`).

**When it runs.** The ladder is `awards → Davis/BJK cups → year rollover → pro-league
offseason → preseason`, and `_finalize_year` mops up unsigned recruits before the incoming
class arrives. The JHSAA rung therefore sits **between the pro-league offseason and
preseason**: last year is fully rolled over, the college season is about to start, and the
seniors the JHSAA just graduated are precisely the class that college season will recruit
and that enrols the year after. That is the real sequence — play your senior season, sign
that same year, arrive the next fall.

The rung does three things in one step: **age the high-school rosters** (freshmen up a
year, seniors out), **play the season**, and **graduate the seniors into the recruit
pool**. Mark it done by the rows it writes, the way `world_cups` rows mark the cups — not
by a new flag, per `docs/AAR-offseason-visible-steps-cups-and-pros.md`.

Resolve the whole high-school season in **one advance step** — a single visible rung on
the offseason ladder, marked by the rows it writes, in the style
`docs/AAR-offseason-visible-steps-cups-and-pros.md` requires. Cheap, and it keeps
`POST /world/advance` the only advance surface.

Scale supports this: ~582 team-seasons × ~14 duals ≈ 8,000 duals, against ~5,100 players.
The college world is roughly five times that.

## 7. Graduation — the payoff

This is what the feature is for. Today `juniors.generate_class` invents all 2,500 recruits
per gender. After this, **Jefferson's slice of that class is not invented** — it is the
graduating JHSAA senior class, ranked by what those players actually did.

- Their `current` ratings come from four years of results.
- Their `potential` stays hidden, so who *develops* is still unknown — the gem/bust
  dynamic survives intact even with full result visibility.
- `history` arrives already populated, so a recruit's page shows their high-school
  career.

The state weight (`US_JUNIOR_TENNIS_ORIGIN_WEIGHTS["JF"]`, currently 0.1400 ≈ 188
recruits/gender) becomes a *consequence* of how many seniors graduate rather than an input
— worth deciding whether to keep the weight as a cap or let the HS pipeline set it.

## 8. Reuse map

| Reuse unchanged | Build new |
|---|---|
| `engine/dual.py` — `DualFormat`, `simulate_dual(play_all=…)` | `app/jhsaa.py` — schools, leagues, schedule, postseason |
| ~~`app/season.py`~~ — see note below | sponsorship + league derivation at import |
| `app/bracket.py`, `state._bracket_canvas`, `templates/_bracket.html` | per-classification talent bands |
| `app/development.py` — growth curves, `Prospect` | graduation hand-off into `juniors` |
| `app/injuries.py` — keyed `(scope, team)` | one rung in `advance_week` + one route tree |
| `data/jhsaa/schools.json` from prep-network's `records/orgs/` | |

**`season.dual_between` is NOT reusable** — this was wrong in the original plan.
`season._dual_record` hard-wires `dual_fmt=ncaa.dual_format(a.division)`, so an unknown
high-school division silently falls back to the classic 6S/3D, and `dual_between` only
enables `play_all` for D3/D4 — so JHSAA duals would play the wrong courts AND abandon
matches at the clinch. `jhsaa.play_dual` calls `engine.dual.simulate_dual` directly with
an explicit `dual_fmt=dual_format(phase)` and `play_all=True`. The engine is the reusable
layer; the college season helpers are not.

## 8b. Awards

Individual honours, off individual records — every line of every dual is attributed back
to the players who played it, by the same indexing that dressed the lineup.

* **All-District** — top 6 per district, per gender.
* **All-State** — top 6 per classification group.
* **Player of the Year** — one per classification group.

Ranked on wins, then win rate, then ability as the tiebreak. Jefferson is the only
association with a simulated high-school season, so it is the only state whose recruits
arrive carrying honours — which is the asymmetry the owner already accepted as the point.

Honours, individual record, ladder position, district, team record and whether the school
won a state title all ride on `Prospect.jhsaa`, a **real dataclass field**. That matters:
`world.prospect_to_dict` is `asdict()`, so an ad-hoc attribute would have been dropped the
moment a recruit signed, taking their whole high-school past with them. It survives
signing, JSON round-trip and `world_roster`, so a fifth-year senior still shows where they
came from.

## 9. Resolved (owner, 2027-08)

**The JHSAA senior class is Jefferson's entry into the college recruit rankings.** Not a
parallel invention — the players on the national board from Jefferson *are* the kids who
just finished four years in the JHSAA, carrying their real records. At ~10 per roster that
is ~780 girls and ~670 boys graduating a year, against ~188 board slots per gender at the
current origin weight, so roughly a quarter of each senior class surfaces nationally and
the rest simply don't play college tennis — which is realistic. Selection is by high-school
results. The origin weight therefore sets *how many* Jefferson kids appear; the JHSAA sets
*which ones* and what they've done.

**Careers persist.** JHSAA players are stored across world years, so a senior has three
prior seasons behind them rather than a generated backstory — ~5,800 persisted players at
a 10-man roster, ~7,000 at 12. This needs a **high-school tab on the player page**
showing per-season results, alongside the existing college career view.

**School marks are ported, not drawn.** `prep-network/site/marks.py` generates identity as
inline SVG from a school's mascot plus the two hex colours already on its record — shield,
roundel, banner or hex badge picked deterministically from the name, with a mascot glyph
overlaid. Porting it gives all ~340 schools crests with **no image files at all**, which
is a better fit than the college PNG/badge pipeline. Mascots, names and colours all come
across from `records/orgs/schools.json`.
