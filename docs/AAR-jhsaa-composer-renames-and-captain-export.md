# AAR — the composer renames, captains on the research export, and two archetypes (2026-09)

Three owner requests in one session: rename a handful of redundantly-named JHSAA
programs after composers, make team captains legible in the research export, and
add archetypes worth having beside the four editable ones.

## 1. The composer renames

The owner named five replacements — Gershwin, Monk, Mendelssohn, Coltrane, Miles
Davis — and asked for "redundant or similarly named" programs to take them. The
targets came off the near-duplicate groups `scripts/jhsaa_name_list.py` leads
with, choosing programs whose leading word duplicated a neighbour's while the
second word carried no identity:

| was | now | why |
|---|---|---|
| Esperanza Basin (5A, Lake Esperanza) | Gershwin | beside "Esperanza" (9A) |
| Doyle Ridge (6A, Halbrook) | Monk | beside "Doyle" (6A), same city |
| Olive (5A, Olive Reach) | Mendelssohn | beside "Olive Head" (8A), same county, same mascot |
| Veles Central (5A, Port Veles) | Coltrane | one of five "Veles X" programs |
| Veles Union (5A, Port Veles) | Miles Davis | the other 5A "Veles X" |

Applied by `scripts/jhsaa_composer_renames.py`, the `jhsaa_owner_renames_2065.py`
pattern exactly. What the mechanics have to touch, and the traps:

- **Every one of these already had a `source`** (each was a `RENAMES` target), so
  the rename REWRITES that entry's target in place — never A → B → C — and the
  roster identity (`source or name`) does not move. `RENAMES` and `FORMER_NAMES`
  in `import_jhsaa.py` both carry the value; both were edited.
- **Display-name-keyed tables move their keys.** `MASCOTS["Veles Central"]`
  became `MASCOTS["Coltrane"]`; the one-off scripts that list display names
  (`jhsaa_2056_closures.py`, `jhsaa_secularise_2065.py`) were edited too.
- **`former_names.json`** gained `old → new` rows and had its existing values
  repointed, so archived seasons relabel on read.
- **Exact-text edits, never a blanket replace.** "Olive" is a town stem (Olive
  Reach, Olive Head) and a given name in the pools; "Veles" is the city.
- **The five are `OWNER_EDICTS`** (a review catch — the first commit left them
  out). Names the owner dictated are protected from the next naming sweep.
- **`scripts/jefferson_gazetteer.py` could not be re-run** here: it reads
  `prep-network`, which is not cloned in this environment. Re-run it beside
  `jhsaa_name_list.py` (which was re-run) on a machine that has both repos.

## 2. Captains on the research export

Captains existed only as a roster chip on the program page, so an analyst reading
the zip could not tell one from anybody else. `players.csv` now carries `captain`
(1/0) and `captain_order` (1 = the lead captain, best-known first; blank for
non-captains).

- **Read off the archive, never re-derived.** `jhsaa.pick_captains` reads the
  ladder as it stood at team-build time; a rebuilt roster cannot reproduce that.
  The archive path reads `world.jhsaa_captains` (the `world_jhsaa_standing` row
  `team_standing` writes) once per export and threads it onto each team; the live
  path reads `TeamSeason.captains`.
- **‼️ The archived key is the school's name AT ARCHIVE TIME.** Read raw, every
  program renamed since that season — the five above included — exported its
  captains as nobody. The map is relabelled through `jhsaa.current_name` before
  it is joined to today's school list. (Review catch.)
- **‼️ Unknown is not zero.** A season archived before captains existed yields
  an empty map. Writing `captain=0` for it makes "no data" indistinguishable from
  "known non-captain", so `captains=None` on every team and BOTH columns stay
  blank; an empty LIST is a known answer and writes 0. The manifest and
  `analytics/agents.md` say so. (Review catch.)
- Deliberately excluded: nothing on `programs.csv` (the per-player row is the
  natural home), no captain column on JV rows (captains are a varsity fact).
- Pinned on the injected path (`test_jhsaa_bundle_marks_the_team_captains`) and
  on the archive path inside `test_the_research_export_carries_the_jv_events`,
  because the injected path and the database path are two different code paths.

## 3. Archetypes: feeder and doubles_culture

Asked what was worth adding to blue_blood / coaching / turnout / neglect. Three
were proposed — feeder, doubles culture, retention — and the owner took the first
two and dropped retention (its effect has no surface to show on).

- **feeder** moves the START, the fifth lever after draw, rate and count. A
  per-school draw from `FEEDER_START` lifts the career model's starting ability,
  clamped at the career peak so no ceiling rises. `FEEDER_FADE` gives half of the
  head start back across the four years so it reads as an arrival tag rather than
  a strength tag — un-faded, the career model's additive gains carried the whole
  lift to senior year. Measured on 20 5A programs: freshmen +4.8, seniors +2.3,
  ceilings +0.2 (coaching's display residual, explicitly fine). Era-gated
  (`feeder_era`), because players are rebuilt from seed and an ungated head
  start rewrites every archived freshman. Career model only.
- **doubles_culture** is what the retired `doubles` should have been:
  arranger-only. It scales nothing the engine sees — no draw, no ceiling, no
  per-match lift, and `doubles_rating`'s synergy term is engine code left alone.
  A per-school draw (`DOUBLES_CULTURE`) rides `TeamSeason.culture`, resolved once
  per team like `sibling_ids`, and shortens `partner_chemistry`'s ramp and the
  lines a pair needs to lock as an established unit (never under two). The bonus
  itself is unchanged, so it stays a tiebreak. The roster with and without the
  tag is byte-identical, pinned.
- **Not measured:** the season-level effect of doubles_culture on doubles flight
  win rate. The tag is wired and unit-tested; the sweep is a run on a real save.
- `test_an_override_promotes_demotes_and_reverts` fails on the base branch too
  (a `StopIteration` unrelated to these changes) and was left alone.
