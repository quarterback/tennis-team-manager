# AAR — the "Bar" schools and the Pine/Tamarack duplicate-name renames (2026-09)

## What changed

Eight school display names moved, across three commits, all owner-picked (never
agent-proposed — see CLAUDE.md's naming-authority rule):

| School | Town (unchanged) | New name |
|---|---|---|
| Hawk Bar | Hawk Bar | Lassen |
| High Bar | High Bar | Fall River Valley |
| Jessup Bar | Jessup Bar | Fort Paynes |
| Mill Bar | Fellows Mill | Lewiston |
| Tamarack Harbor | Tamarack Harbor | Cape Blanco |
| Tamarack (San Cordero) | San Cordero | Bonanza |
| Pine | Pine Siding | Winchester Bay |
| Pine Rim | Sage Spur | Hamburg |

Two different problems, same fix shape:
- **"Bar" schools** (Hawk Bar, High Bar, Jessup Bar, Mill Bar): the school's
  display name read as a saloon, not an institution. Four of these are a real
  Gold-Rush "gravel bar" naming style (Rich Bar, Indian Bar) that works fine for a
  TOWN and reads wrong for a SCHOOL.
- **Coincidental duplicate names** (Tamarack/Tamarack Harbor, Pine/Pine Rim): two
  unrelated towns — different counties, different leagues, 100+ miles apart —
  whose schools happened to share a leading word in the SAME classification, so
  they sit next to each other on every 9A/1A list with nothing to tell them apart.

**The town's own name is deliberately untouched in every case.** `city` stays what
it was; only the school's `name` (and `source`, where the roster identity needs
to survive the move) changed. This is the standard shape CLAUDE.md's identity
section describes: a school has three identities (roster/`source`, archive/
display, and prep-network/source-of-record), and a rename only ever moves the
display one unless the owner says otherwise.

## How the names were picked

Not invented from nearby flavor — the first attempt at that (three iterations of
guessed names) collided with schools already on the map eight separate times,
because "sounds plausible for the setting" and "is actually unused" are different
checks and only one of them was being run. The fix: use `docs/GAZETTEER-jefferson.md`
to find the REAL county each fictional one stands on (Ferris → Shasta Co. CA,
Olivet → Tehama Co. CA, Sablewood → Trinity Co. CA, Weller → Curry Co. OR,
Tamarack → Klamath Co. OR, Antler → Douglas Co. OR, Cinder → Siskiyou Co. CA),
`WebSearch` for genuine place names in that specific real area (a real creek, a
real ghost town, a real fort, a real lighthouse), and check every candidate
against the FULL current name list — not a spot check — before ever presenting
it. Only then did the owner pick from real options.

## The reused rename machinery

Nothing new was built. Every rename went through the existing pipeline:
1. Edit `scripts/import_jhsaa.py`'s `RENAMES` dict, keyed on the ROSTER identity
   (`source or name`), never the current display name if the school has already
   been renamed once — **renaming twice REWRITES the target in place**, it never
   chains. This bit twice in this batch: "Mill Bar" and "Tamarack" were both
   already rename TARGETS (from "Fellows Mill International (School)" and
   "Svenja Bianchi" respectively) and had to be rewritten in place at their real
   keys, not given a new key under their current display name. Same for "Pine" —
   its true key is "Pine Siding" (it had already been renamed once, Pine Siding →
   Pine, before this batch); a first attempt keyed the new rename on "Pine" itself
   and it silently did nothing, because `RENAMES` is keyed on the identity the
   school has never stopped carrying, not on whatever it's called today.
2. Move any `MASCOTS`/`COLORS`/`PRIVATE_SCHOOLS`/`LOCALITIES` entries keyed on the
   OLD display name to the new one (Mill Bar's "Quarrymen" and Tamarack's
   "Snowcaps" both had to move).
3. Run `scripts/jhsaa_apply_renames.py --dry-run`, then for real — it validates
   identity uniqueness, stamps `source`, moves the display-keyed tables, and
   writes `data/jhsaa/schools.json`. It refused nothing this time; all names
   were checked clean before being proposed.
4. Regenerate `docs/JHSAA-school-names.txt` (`scripts/jhsaa_name_list.py`) and
   `data/jhsaa/former_names.json` + the `FORMER_NAMES` block inside
   `import_jhsaa.py` (`scripts/jhsaa_former_names.py`).

## ‼️ The trap: a brand-new RENAMES key needs a COMMITTED revision before its alias exists

`scripts/jhsaa_former_names.py` rebuilds `FORMER_NAMES` by walking `git log` for
every revision `RENAMES[source]` has ever held, then folding in whatever the LIVE
(possibly uncommitted) file currently says. That's why its own docstring says
"run pre-commit" — for a school that has ALREADY been renamed before, the git
history supplies the old target and the live file supplies the new one, so the
alias is correct even before you commit.

**That reasoning breaks for a school being renamed for the FIRST time.** Hawk Bar,
High Bar, Jessup Bar, Tamarack Harbor, and Pine Rim had never been a `RENAMES` key
in ANY prior commit — so `chain[source]` is empty, the school is never visited by
`collect()`'s main loop, and no alias is produced, no matter how many times you
rerun the script before committing. The old name silently has no path back to the
new one until the rename itself lands in a commit that `git log` can see.

This shipped invisibly for five of the six schools in the FIRST commit of this
batch, because by the time the SECOND commit's session ran the regenerator again,
the first commit was already in git history and those five picked up their
aliases for free. **Pine Rim did not**, because it was a first-time rename added
in that same second commit and regenerated in the same, still-uncommitted,
session — exactly the gap this trap describes. `--check` caught it (683 expected,
682 on disk) only after the commit landed and a *third* commit re-ran the
regenerator against now-committed history.

**The fix, and the pattern to repeat:** commit the `RENAMES` edit first, THEN run
`scripts/jhsaa_former_names.py` again and commit the result separately. This is
the two-commit shape already established elsewhere in this repo's history
("JHSAA: mascot survey picks + Shasta and Furrow renames" followed by "JHSAA:
regenerate FORMER_NAMES for Shasta and Furrow") — it is not a new invention, it
was just missed here because a same-turn rename batch reads as one unit of work.
**A first-time rename's alias is never trustworthy until you've committed once
and regenerated again.** `scripts/jhsaa_former_names.py --check` is the tripwire;
run it after every rename batch, not just once at the end of a longer session.

## ‼️ The gazetteer generator needs a sibling checkout this environment doesn't have

`scripts/jefferson_gazetteer.py` reads `prep-network/records/orgs/cities.json`
from a sibling repo checkout — it is not vendored into this repo and was not
present in this session's environment (`FileNotFoundError` on
`/home/user/prep-network/records/orgs/cities.json`). A full regeneration of
`docs/GAZETTEER-jefferson.md` and its root mirror `GAZETTEERjefferson.md` (the
generator deliberately writes BOTH so the two references cannot drift) was not
possible here.

**What was done instead:** the eight affected lines — the indented school line
under each town's bold heading, never the town heading itself — were hand-patched
identically in both files to the new names. This keeps the doc internally
consistent for THESE eight schools without inventing new source data, but it does
NOT re-derive anything and does not catch drift elsewhere in the document (the
"Pine Siding" school line was already stale before this batch touched it — a
sign the doc is due a real regeneration, not just a patch). **Run
`scripts/jefferson_gazetteer.py` for a real regeneration the next time this repo
is worked on somewhere with the `prep-network` sibling checkout available** —
this patch is a stopgap, not a substitute.

## Tests

`tests/test_jhsaa_ladder.py::test_display_names_are_unique_identities` and
`tests/test_jhsaa_rivalries.py::test_the_two_rivalry_tables_agree` were re-run
after each commit in the batch and stayed green throughout.
