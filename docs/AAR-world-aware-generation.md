# AAR — World-Aware Generation & Unified Recruit Class

## Segment summary

This segment started from two user-reported symptoms and ended in a core
generation refactor:

1. **`/recruit/<pid>` 404s** when clicking players in the recruiting pool —
   especially anyone already tied to a team.
2. **"New League" regenerates the identical world** — same schools always
   produce the same rosters and recruits, which is no fun to test.

Both traced to the **same architectural miss by the previous agent**: the world
was deterministic *by school identity and a single fixed seed*, with **two
separate recruiting universes** that never shared pids. The fix makes all
generation **world-aware via a per-league salt** and collapses the two recruit
universes into **one canonical class**. Determinism now holds **only within a
created league**; each New League is a fresh world. All work is on
`claude/team-selector-conference-73ksv8`; the full test suite stays green and the
fix is verified end-to-end.

## The architectural miss (root cause)

Three independent decisions compounded into the broken behavior:

1. **Rosters were world-agnostic.** `ncaa._base_roster` seeded its RNG and pids
   purely from the program key: `_stable_seed("{school}|{division}|{gender}")`
   and `make_pid(p.key, i)`. No world seed, no salt. So **every New League rebuilt
   byte-identical rosters with identical pids** — "fresh start" was an illusion.

2. **Two recruit universes that never matched.** The web board and the
   simulation generated *different* recruiting classes:
   - Web (`state.get_recruits`): rng `"2026|recruits|{gender}|{grad_year}"`,
     `talent_sd=6.5`, default intl share, `grad_year` used directly.
   - Sim (`world.national_class`): rng `"{seed}|worldrecruits|{gender}|{year}"`,
     `talent_sd=7.0`, `intl_share=0.32`, `grad_year=BASE_YEAR+year+1`.

   Different seed string **and** different grad_year ⇒ **different people with
   different pids.** Committed players are persisted (`world_signing`, full JSON +
   pid) with **sim** pids; the `/recruit/<pid>` route regenerated the **web**
   class and never found them → 404.

3. **A single hardwired seed (`DEFAULT_SEED = 2026`).** "New League"
   (`world.start_new()`) always reused 2026, and the web layer passed
   `DEFAULT_SEED` everywhere with no notion of an "active world seed." Nothing
   could vary between saves.

The lesson: in a stateless web app, **determinism is the mechanism that avoids
persistence — but it must be keyed to the save, not to global identity.** Keying
generation to `(school)` instead of `(league, school)`, and running two parallel
RNG streams for "the same" recruiting class, was the miss.

## What was done

### 1. Per-league salt (`app/ncaa.py`, `app/world.py`)
- `ncaa.WORLD_SALT` (module global) is mixed into the roster RNG and roster pids:
  `_stable_seed(f"{WORLD_SALT}|{p.key}")` and `make_pid(WORLD_SALT, p.key, i)`.
- `world` stores a random `salt` column on the `world` row, generated fresh on
  creation (`secrets.token_hex`) and on every `start_new()`. It is **published to
  `ncaa.WORLD_SALT` before any roster is built**, via `get_or_create` /
  `active_salt()`, and re-published on each request by a `before_request` hook in
  `server.py`.
- Result: the same `school|division|gender` yields **different players,
  attributes, and pids in every New League**, but is stable within a league
  (caches are cleared on reset).

### 2. One canonical recruit class (`app/world.py`, `app/web/state.py`)
- New `world.recruit_class(gender, grad_year, salt)` is the single source of
  truth — one generator, one seed (`"{salt}|recruits|{gender}|{grad_year}"`), one
  class-year/grad-year mapping, one distribution, one pid construction. It is
  enriched with the junior circuit so the web board keeps its results/rankings.
- `world.national_class()` (the sim's signing pool) and `state.get_recruits()`
  (the web board, detail pages) both **delegate to it**. The web board and the
  sim signing pool are now provably the **same 1000 pids**.

### 3. Strict `/recruit/<pid>` lookup order (`app/web/state.py`, `app/world.py`)
`get_recruit` now resolves in order:
1. `world.find_persisted_player(pid)` — committed signees (`world_signing`) then
   rostered players (`world_roster`, newest year first).
2. the canonical active-world recruit class.
3. **never** `DEFAULT_SEED` / the old web-board class.

So anyone already tied to a team is found via persisted data regardless of which
class they originally came from.

### 4. New League is fresh (`app/world.py`)
`start_new()` takes an optional `salt` (random by default) and clears
`_class_cache` + `ncaa.WORLD_SALT` on reset. Each New League is a different world.

## Verification
- Full test suite: green.
- Roster freshness: the same school (Texas) fields entirely disjoint pids/players
  across two salts.
- Unification: `recruit_class` web view and the sim signing pool share all 1000
  pids for the same `(salt, gender, grad_year)`.
- 404 fix: a committed player inserted into `world_signing` resolves via
  `find_persisted_player` and `get_recruit` step 1; a live recruiting-pool link
  (`/recruit/<pid>`) returns 200.

## Strength varies per league too
Per follow-up, `_latent_strength` is now salted as well: a program's on-court
strength is drawn fresh each New League from the gaussian centered on its
(fixed) conference prestige prior. So standings vary between saves while the
prestige baselines stay constant.

## Conference prestige priors (`CONF_PRESTIGE`)
- D1/D2/D3 priors were retuned to user-supplied values. Latent bug fixed: the old
  dict keyed the American conf as `"AAC"` (data abbr is `"American"`) and carried a
  dead `"Mountain West"` duplicate alongside the real `"MW"` — both silently
  defaulted to 0.50.
- D2/D3 abbrs collided across divisions (`MIAA`, `GNAC`). Rather than a
  division-aware lookup, the colliding instances were **renamed in the data** to
  `MIAA-D3` / `GNAC-D2` / `GNAC-D3`, so a single flat abbr-keyed table works.
- Three D3 conferences have no supplied value and default to 0.50:
  **NJAC** (New Jersey Athletic), **MWC** (Midwest), **CCS** (Collegiate
  Conference of the South).

## Boundaries / follow-ups
- Prestige *baselines* (`CONF_PRESTIGE`, `PRESTIGE_SCHOOLS`, `DIVISION_PRESTIGE`)
  stay fixed across leagues — they are the league's identity. Only the per-program
  draws (strength, roster, recruits) are salted.
- Existing pre-migration saves have `salt = NULL → ""` (legacy seeds preserved);
  the first New League after this change gives them a real random salt.
