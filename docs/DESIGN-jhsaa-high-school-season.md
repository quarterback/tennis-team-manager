# DESIGN — Simulating the JHSAA high school season

Status: **proposed, not built.** Written against the Jefferson integration
(`docs/AAR-jefferson-state-integration.md`), which put the state's juniors and colleges
in the sim but generates its recruits from nothing.

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

| Class | Girls rate | Schools | Girls teams | Boys teams |
|---|---:|---:|---:|---:|
| 7A | 85% | 119 | 101 | 88 |
| 6A | 70% | 118 | 75 | 65 |
| 5A | 55% | 123 | 70 | 57 |
| 4A | 35% | 141 | 44 | 39 |
| 3A-1A | 18/8/2% | 339 | 23 | 20 |
| **Total** | | **840** | **313** | **269** |

44 girls-only schools, zero boys-only. ~37% of schools sponsor tennis, which is right for
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

Girls, at the sponsorship rates above — 31 districts of 9–12:

| Class | Teams | Districts | Names |
|---|---:|---:|---|
| 7A | 99 | 9 | Cascade Divide · Gold Valley · Halbrook Basin · Halbrook · Vance · Bidwell · Harborline · Sage Plains · South Coast |
| 6A | 87 | 8 | Ashbury Metro · Marlow · Gold Valley · Halbrook Basin · Halbrook · Vance · Harborline · Sage Plains |
| 5A | 69 | 6 | Ashbury Metro · Gold Valley · Halbrook Basin · Vance · Harborline · South Coast |
| 4A | 53 | 5 | Ashbury Metro · Gold Valley · Halbrook Basin · Vance · South Coast |
| 3A-1A | 32 | 3 | Gold Valley · Juniper Highlands · Sage Plains |

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
district schedule (double round-robin, ~14 duals, 5S/2D)
  -> district tournament
  -> state dual-team tournament, 1S/4D, one bracket per classification group
```

**Field sizes (owner-decided, 2027-08).** Qualification is every district champion,
then at-large by record to fill the bracket:

| Class | Field | Girls teams | qual % | Boys teams | qual % | Districts (G/B) | Champs + at-large (G) |
|---|---:|---:|---:|---:|---:|:---:|---|
| 7A | **32** | 99 | 32% | 86 | 37% | 9 / 8 | 9 + 23 |
| 6A | **24** | 87 | 28% | 77 | 31% | 8 / 7 | 8 + 16 |
| 5A | **24** | 69 | 35% | 61 | 39% | 6 / 6 | 6 + 18 |
| 4A | **16** | 53 | 30% | 48 | 33% | 5 / 4 | 5 + 11 |
| 3A-1A | **8** | 32 | 25% | 25 | 32% | 3 / 3 | 3 + 5 |

Ten brackets in all, five per gender. The 24-team fields are seeded into a 32 draw with
**first-round byes for the top 8** — normal for high school and already supported by
`bracket.build_bracket` / `Matchup.bye`.

Note the at-large share is large by design (7A takes 9 champions and 23 at-large), so a
district title is a guarantee of entry rather than the main route in. If district races
should matter more, the alternative is top-3-per-district first (27 at 7A) with at-large
filling only the remainder — a selection-rule change, not a structural one.

Reuses `bracket.py`, `state._bracket_canvas` and `templates/_bracket.html` — the Preseason
NIT already proved a third consumer can share that tree without forking the markup
(`docs/AAR-preseason-nit-bracket.md`).

## 6. The clock

**Do not make the JHSAA a week-by-week universe under `advance_week`.** That fights the
one-world-one-clock rule and doubles the desync surface
(`docs/AAR-universe-desync-season-hub-advance.md`).

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
| `app/season.py` — `dual_between`, `_schedule`, `_conf_tournament`, standings | sponsorship + league derivation at import |
| `app/bracket.py`, `state._bracket_canvas`, `templates/_bracket.html` | per-classification talent bands |
| `app/development.py` — growth curves, `Prospect` | graduation hand-off into `juniors` |
| `app/injuries.py` — keyed `(scope, team)` | one rung in `advance_week` + one route tree |
| `data/jhsaa/schools.json` from prep-network's `records/orgs/` | |

`season.dual_between(a, b, seed=…)` takes two `Program` objects, so if JHSAA schools are
Program-shaped most of the season machinery runs unmodified. This is mostly assembly.

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
