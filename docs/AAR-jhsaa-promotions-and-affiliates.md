# AAR — 11-school promotion to 8A, and JHSAA's first out-of-state affiliates

## What started it

Two owner-supplied lists, done as one pass since both are one-time transforms
over the committed `data/jhsaa/schools.json`: (1) 11 named schools promote to
8A from 7A/6A/3A, and (2) JHSAA admits 13 out-of-state affiliate members —
the same way OSAA/WIAA/CIF/Arizona/Nevada admit border schools for geography
and proximity — via 13 sunset-and-replace swaps.

## Part A — 11 promotions to 8A

A real RECLASSIFICATION (`RECLASSIFY_TO_2A` precedent): moves BOTH
`classification` and `group` to "8A" for Vespertine, Covenant, Cook City,
Ditch Fork, Olive Head, Olivet County (all 7A→8A), Plainfield, Paddock County
(6A→8A), Bardsley County, Mesa Dorada, Crater View (3A→8A). Geography,
mascot, colors, enrollment, private status and history are untouched — only
the class they compete in and generate talent for changes.

- **"Bardsley County" is NOT "Bardsley County High."** A different, earlier
  rename this session (`jhsaa_heritage_valley_renames.py`) retitled a
  different school, "Bardsley County High," to "Violet City." "Bardsley
  County" (no "High") is a distinct, unrelated program in the same county —
  verified by exact name match before touching anything. Two schools sharing
  a county name is not a collision by itself.
- Districts were forced to redraw for every touched class — the 3 source
  classes (7A, 6A, 3A) AND the destination (8A) — rather than relying on a
  league-count-match check, per the lesson from the earlier Heritage Valley
  P1 fix: a class can lose exactly the schools it's about to lose without its
  league COUNT changing, which leaves stale membership behind invisibly.

## Part B — 13 out-of-state affiliates

Same RETIRE_AND_REPLACE shape as `jhsaa_heritage_valley.py`: the donor's
sponsorship goes off (row stays — `former_school` precedent, archived history
resolvable), and a brand-new school takes its classification/group and
sponsorship pattern. The difference from every prior replacement in this
association: these 13 carry **real** geography — real city, real county,
real US state — never a fictional Jefferson county.

| Donor (sunset) | New affiliate | Real location |
|---|---|---|
| Mountain House | Peregrine | Boise, Ada County, Idaho (private) |
| Copperview | Baker | Baker City, Baker County, Oregon |
| Meadowbrook | Lower Lake | Lower Lake, Lake County, California |
| Shenango | Bend Senior | Bend, Deschutes County, Oregon |
| Bahía Vista | Mountain View | Bend, Deschutes County, Oregon |
| Empire Milling | Summit | Bend, Deschutes County, Oregon |
| Junction | Caldera | Bend, Deschutes County, Oregon |
| Crow Basin | Ukiah | Ukiah, Mendocino County, California |
| Emigrant | Rock Springs | Rock Springs, Sweetwater County, Wyoming |
| St. Gabriel Academy | Green River | Green River, Sweetwater County, Wyoming |
| Harrow | Jackson Hole | Jackson, Teton County, Wyoming |
| Buckhorn | Spring Harvest | Spring Harvest, Box Elder County, Utah |
| Mirage Siding Regional | Money | Money, Box Elder County, Utah |

(Names shown post-correction — see "Naming correction" below. The affiliates
were first created carrying "High"/"School" suffixes and renamed once the
owner flagged it.)

## A new field: `School.state`

`state: str = ""` on the `School` dataclass (`app/jhsaa.py`) — empty for
every ordinary Jefferson program, a real state name for an affiliate. Wired
through both `load_schools` and `former_school`. This is the ONLY thing that
marks a program as an affiliate; nothing about how it COMPETES changes —
classification, leagues, districts, rankings, honors, postseason and TOSS
all treat it as an ordinary member, per the owner's explicit rule.

**Two geographies, two different jobs:**
- `city`/`state` — the school's REAL location. This is what a page displays.
- `county`/`area` — INTERNAL clustering geography ONLY, so district/league
  draws still have something to sort schools by. Chosen for real-world
  adjacency to the existing Jefferson footprint (via
  `docs/GAZETTEER-jefferson.md`): Boise Frontier borders Ada County, ID
  (Peregrine School); Cascade Divide (Cinder/Siskiyou CA — Tamarack/Klamath
  OR) borders the Bend/Baker City/Ukiah/Lower Lake corridor; the five
  Group-system affiliates (Rock Springs, Green River, Jackson Hole, Spring
  Harvest, Money) join Bear River Country — the SAME real Wyoming/Utah ground
  the Heritage Valley migration already stood the Group system on earlier
  this session. **`area`/`county` on an affiliate must NEVER reach a page** —
  only `city`/`state` do.

## Display rules (owner spec, exact)

- **Never a state suffix on the NAME**, anywhere — "Bend Senior High," never
  "Bend Senior High (OR)." No code path appends one; the rule is enforced by
  omission (nothing reads `state` when building `name`-facing strings).
- **School page** (`jhsaa_school.html`): the header subtitle and the "where"
  line branch on `view.state` — an affiliate shows `city, state · Out of
  State`, everything else identical (district link, enrollment). An ordinary
  school is byte-identical to before this change.
- **Program Directory** (`/jhsaa/schools`, `jhsaa_schools_view`): county mode
  groups every affiliate under one **"Out of State"** heading (blank section
  meta — the bucket spans several real states, so no single meta line could
  describe it; each row's own `where` already carries its real city/state).
  Non-county modes (class, A–Z) suppress the county suffix a row would
  otherwise print, since that county is internal-only. The header's
  "Counties" count excludes affiliates so it keeps meaning "Jefferson
  counties," not "real + internal-clustering counties combined."
- **Extended to every surface that prints a school's geography.** The first
  pass touched only the school page and the Program Directory, per the
  explicit ask. The owner then asked to "remove the bare string" — four more
  templates printed a hardcoded `, Jefferson` (`jhsaa.html` hub,
  `jhsaa_bracket.html`, `jhsaa_player.html`, `jhsaa_toc.html`), each in a
  champion/header line. All four now branch on `state`/`view.state` the same
  way: `{{ ...city }}, {{ ...state if ...state else 'Jefferson' }}`. Three of
  the four (hub, bracket, TOC) read through the ONE shared decoration helper,
  `state._jh_deco`, so adding `"state": s.state` to its two return dicts fixed
  all three at once; `jhsaa_player.html` reads `view.state` off
  `jhsaa_player_view`'s own return dict directly.

## Where affiliate players are "from"

`_gen_seat` (the one function that builds every JHSAA `Prospect`) had
`hometown`/`region` hardcoded unconditionally to Jefferson —
`f"{school.city}, JF"` and `region = "Jefferson"` — for every seat on every
roster, which was silently wrong the moment a school could carry a real
out-of-state `city`. A Bend Senior player was generating as "Bend, JF" /
region "Jefferson" instead of "Bend, OR" / region "Oregon". Fixed by keying
both off `school.state`, matching the `f"{city}, {abbr}"` convention already
used elsewhere (`development.py`, `juniors.py`, `ncaa.py`):
```python
p.hometown = f"{school.city}, {_state_abbr(school.state)}"
p.region, p.domestic = (school.state or "Jefferson"), True
```
`_state_abbr` is a small new helper that reuses `juniors.US_STATES` (the
canonical `(full_name, abbr)` list) rather than inventing a second
state-abbreviation table. `region` matters beyond display: it is a player's
home-STATE string, read by `juniors.state_players` for state-based recruit
filtering — an affiliate player must show up under their REAL state there,
not under Jefferson. Verified for all 13 affiliates (e.g. Peregrine →
"Boise, ID" / region "Idaho"; Rock Springs → "Rock Springs, WY" / region
"Wyoming"); ordinary Jefferson schools are byte-identical (`school.state`
empty → falls back to the old "JF"/"Jefferson" values exactly).

## Naming correction — the affiliates missed the no-suffix rule

11 of the 13 new affiliate names were created carrying "High" or "School"
("Baker High," "Peregrine School," …) — a plain miss of the standing
CLAUDE.md rule that a JHSAA school's display name carries no institutional
suffix, which every OTHER school in the association (real or generated)
already follows. Caught by the owner directly, not by review.

Fixed with a small one-time rename script, `scripts/jhsaa_affiliate_names.py`
— the same shape as every other rename this session: it only ever touches
`name` (the display/archive identity), never `source` (the roster identity
that seeds player generation and pids), per the standing JHSAA
display-rename rule. `Spring Harvest` and `Money` already carried no suffix
and were left alone. Verified after running it: 0 name collisions, sponsor
counts unchanged (957 girls'/883 boys', 0 empty districts), and roster
generation for four spot-checked renamed schools (Peregrine, Baker, Bend
Senior, Rock Springs) produces identical players with correct
hometown/region — renaming `name` alone cannot touch generation, which
keys on `source`.

## Verification

Per this session's standing "no full suite" convention for a construction
pass — targeted checks only:
- `load_schools()` round-trip: 957 girls'/883 boys' sponsors (net-zero — 13
  off, 13 on), 0 empty districts, 0 display-name collisions (984 total rows
  now: 957 + 13 RETIRE_AND_REPLACE donors from earlier this session + 13 new
  from this pass + 1 net from the earlier renames pass).
- `sponsor_floor()` clears for every group in both genders (preflight ran
  clean, no `sc_head` degrade warnings).
- Spot-checked promoted schools (Vespertine, Bardsley County, Plainfield) —
  correct `classification`/`group`/`district`.
- Spot-checked affiliates (Peregrine School, Bend Senior High, Rock Springs
  High, Money) — correct city/county/state/private/district.
- `jhsaa_schools_view` and `jhsaa_school_view` called directly (not through
  a live server) for an affiliate and an ordinary school each — both render
  without error, the Out of State section appears with all 13 rows showing
  real city/state.

New script: `scripts/jhsaa_promotions_and_affiliates.py`.
