# AAR — Real-logo sweep (every school gets a mark)

## Context / problem

Team logos render inline beside school names (rankings/standings/schedule/team pages)
via `app/web/formatters.py::team_logo` → `/static/logos/<slug>.png`, mapped in
`data/ncaa/logos.json`. Coverage had gaps and bugs:
- **349 in-game schools** (small D2/D3/NAIA — including the ~200 schools added earlier
  this session) were on **generated monogram placeholders**, and 30+ of those had **no
  PNG on disk at all** (broken images), because their `logos.json` entries were added
  without generating the art.
- **Shared-id collisions:** several "X College" schools showed flagship **X University**'s
  logo (owner flagged **Colorado College → University of Colorado**; also Idaho/Hartford,
  Boston College/Boston University, Cornell College, Penn College, etc.).
- Owner goal: **every team has some real logo**; correct where findable, a real
  substitute otherwise ("any will do — minor-league, same city, same letter"), and a
  **clean badge** (not the old crude monograms) only for what's truly unfindable.

## What was done

### 1. Real-logo backfill (`scripts/backfill_logos.py`)
Per school, a source cascade, each fetched image rasterized + scaled to the logo box (PIL):
1. **ESPN athletic logo** — own name match (guarded against the "College of X" → flagship
   collapse that ESPN's stopword-normalizer causes).
2. **Wikipedia** article logo/seal (`pageimages`, exact-title resolved so we don't grab a
   city or "List of…" page).
3. **Wikidata** logo/seal (`P154`/`P158`).
4. **ESPN close-name substitute**, then **same-first-letter** real logo — a real stand-in.

Resumable + checkpoints `logos.json` every 15 so partial progress persists (committed in
batches). `scripts/substitute_logos.py` is a fast ESPN-CDN-only finisher for the tail.

### 2. Collision fixes
Detected 12 shared-id pairs; kept the flagship, reassigned each "X College"/mis-mapped
loser off the flagship id to its own or a substitute logo (Massachusetts/UMass left — same
school).

### 3. Clean GitHub-style badges (`scripts/make_badges.py`)
For the ~45 with no findable real art (and download 404s): a flat rounded-square badge,
deterministic tasteful color from a curated palette, crisp white monogram, **supersampled
(4×) then downscaled** for smooth edges. Flagged `"badge": true`. Replaces the old crude
monograms the owner disliked.

## Result

**All 1,090 in-game schools have a mark; 0 placeholders, 0 broken/blank.** By source:

| Source | Count |
|---|---:|
| ESPN athletic (original + own-match) | ~704 |
| Wikipedia own logo/seal | ~61 |
| Wikidata own logo/seal | ~33 |
| ESPN close/region substitute | ~247 |
| Clean GitHub-style badge | ~45 |

`logo_source` in `logos.json` records each origin, so a future re-run can upgrade
substitutes/badges to a school's own logo if one becomes available.

## Notes / limits
- Substitutes are real logos of a *different* close-named team (owner-accepted: "any will
  do"). ESPN's index (~900 D1-centric teams) simply doesn't carry most NAIA/tiny-D3 schools,
  and Wikipedia/Wikidata coverage of their logos is partial — hence substitutes + badges for
  the tail rather than 1:1 marks.
- Trademarks belong to their institutions; used for nominative identification in a personal,
  non-commercial sim (see `app/web/static/logos/README.md`).

## Follow-up (Codex review)
- **Don't persist borrowed ESPN ids.** `sub:`/`any:` substitutes were storing the
  borrowed team's `espn_id`; on a re-run the collision pass groups by `espn_id`, so a
  borrowed id would flag the *real* owner as a loser and exclude its own match. Stripped
  the id from all 260 substitute entries (provenance stays in `logo_source`) and both
  scripts now persist `espn_id` only for a school's OWN ESPN logo. Also reassigned the one
  lingering real collision (Dallas Baptist off Loras's id → badge).
- **Keep campus logos distinct.** The lookup dropped the parenthetical qualifier, so
  disambiguated campuses (Emmanuel GA/MA, Dominican CA/NY, North Central IL/MN, Saint
  Mary's IN/MN, Union NY/TN, Johnson & Wales Charlotte/Providence) resolved to one
  article and shared a logo. Fixed those six pairs (disambiguated wiki art where found,
  else a distinct badge) and `wiki_logo`/`wikidata_logo` now query the state-qualified
  title first, so campuses get their own mark.

## Verify
```python
import json, glob, os
logos = json.load(open('data/ncaa/logos.json'))
schools = {t for f in glob.glob('data/ncaa/[d]*_men.json')
           for c in json.load(open(f))['conferences'] for t in c['teams']}
missing = [s for s in schools if s not in logos
           or not os.path.exists(f"app/web/static/logos/{logos[s]['slug']}.png")]
assert not missing and not any(v.get('placeholder') for v in logos.values())
```
