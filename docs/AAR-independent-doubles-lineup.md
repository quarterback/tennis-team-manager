# AAR — Independent doubles lineup (coach-set pairings, doubles specialists)

## Why

In US college tennis the doubles lineup (3 pairs) is its **own** lineup, separate
from the singles six — a player can be "1 doubles / 5 singles" (a doubles
specialist who pairs at the top but isn't a top-six singles player). The sim only
ever auto-paired doubles as a permutation of the singles six (`season.DOUBLES_PERMS`
→ `random.choice`), so the coach had **zero** control over pairings and a specialist
who isn't a singles starter could never play doubles. The owner asked to be able to
set the three pairs, explicitly including non-singles players.

## What it does

The coached team can pin an **independent doubles lineup**: three pairs drawn from
*anywhere on the roster*, decoupled from the singles ladder. Leave it unset and
nothing changes — every team (and a coached team that never touches it) auto-pairs
exactly as before. Set in the editor (the same surface that pins the singles
ladder); applies to the coached team's season duals.

## How it's wired

- **Engine** (`engine/dual.py`, backward-compatible): `Team` gains an optional
  `doubles_players: list[Player] | None`. `_pair` now indexes the pairing into
  `doubles_players` when set, else into `singles` (the classic behavior). Every
  existing caller passes only `singles`, so default behavior is unchanged. The
  pairings (`Team.doubles`) are index pairs as before — into whichever pool applies.
- **Lineup builder** (`season.coach_lineup`): new `doubles_pin` param (6 pids →
  pairs `[(0,1),(2,3),(4,5)]`). The function now returns a **third** value,
  `chosen_doubles` (the Prospects in doubles slots, parallel to
  `Team.doubles_players`). With a valid pin it builds a separate doubles roster;
  otherwise `chosen_doubles is chosen` and the engine auto-pairs from singles. The
  pin is honored only if **all six pids are on the available (healthy) roster** —
  otherwise that dual falls back to auto (so one injury can't field a broken pair).
- **Identity / box score** (`season._line_identity`, `_dual_record`): doubles slots
  resolve their player identity (names + pids) from the **doubles** Prospect lists
  (`la_d`/`lb_d`), not the singles list — so a specialist's name shows on the
  doubles line. Both default to the singles list, so the other `_dual_record` caller
  (the prebuilt-squads all-play path) and any auto team are unaffected.
- **Coached-team guard** (`season._coached_doubles`): mirrors `_coached_pin` — the
  pin is read **only** for the human-coached program; every other team returns None
  and auto-pairs. Cheap identity check, no DB read for the ~all non-coached teams.
- **Persistence** (`overrides.py`): a new `kind='doubles'` row (key=school, value=
  JSON list of 6 pids), with `get/set/clear_doubles`. Added to `roster_version`
  (so caches refresh the instant the pin changes) and `clear_all`.
- **UI** (`editor.html` + routes `editor_doubles` / `editor_clear_doubles`): a
  "Doubles lineup" panel under the singles table — three pair rows, each a pair of
  roster dropdowns (every option labeled with the player's singles line, e.g.
  "· S5", so a "1 doubles / 5 singles" pick is obvious). Saved only if the six picks
  are distinct roster pids. Surfaces in the "Active overrides" panel with an Undo.

## Gotchas / scope

- **`coach_lineup` now returns a 3-tuple.** Its only production caller is
  `season.dual_between` (updated); `tests/test_injuries.py` unpacks it too (updated
  to `team, chosen, _`).
- **Sandbox `/dual` is unaffected** — it builds teams via `build_squad` (no coach
  pins of any kind), so, exactly like the existing singles pin, the doubles pin
  applies only to the real season path. Consistent, not a regression.
- **Injury fallback is all-or-nothing** for now: if any pinned doubles player is out
  that week, the whole doubles lineup reverts to auto for that dual. Per-seat
  substitution could be added later but adds complexity for a rare case.
- **No two-pairs-share-a-player guard beyond distinctness**: the editor enforces six
  *distinct* pids, which is correct (a player can't be in two pairs at once).

## Tests

`tests/test_doubles_lineup.py`: overrides round-trip; a pinned non-singles
specialist plays doubles but not singles; no/invalid pin falls back to auto; and the
engine pairs from `doubles_players` when set (dual completes, 3 doubles + 6 singles
lines). Verified end-to-end with a web smoke: a pinned specialist appears on the
doubles lines of a real coached-team season dual, and the editor renders the form.
