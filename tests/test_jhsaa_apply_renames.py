"""`scripts/jhsaa_apply_renames.apply` — the transform that rewrites the committed
`data/jhsaa/schools.json` from `import_jhsaa`'s tables.

‼️ A TOWN RENAME MUST REACH EVERY SCHOOL IN THE TOWN, not only the school being
renamed. `CITY_RENAMES` used to be applied BELOW the `RENAMES` gate, so a town
holding one renamed school and three untouched ones moved exactly one row: the
2026-09 owner pass retired Ditch Fork (keeping Cassius and King) and Tunnel
Diggings (keeping Mondale, Barkley, Bethel Christian, Lonepine Canyon and
Quartzburg), and those schools would have stayed in towns that no longer existed.
This pins the city-only path and its idempotency with a fixture, never the real
data file (the real tables move with every owner pass).
"""
import copy
import importlib.util
import os
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(os.path.dirname(_HERE), "scripts", "jhsaa_apply_renames.py")


def _load_script():
    spec = importlib.util.spec_from_file_location("jhsaa_apply_renames", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tables():
    """A stand-in for `import_jhsaa` carrying only what `apply` reads."""
    m = types.SimpleNamespace()
    m.RENAMES = {"Old Town": "New School"}          # the town-named school
    m.CITY_RENAMES = {"Old Town": "New Town"}
    m.PRIVATE_SCHOOLS = set()
    m.MASCOTS = {}
    m.COLORS = {}
    m.LOCALITIES = {}
    m._display_name = lambda name: name
    return m


def _rows():
    return [
        {"name": "Old Town", "city": "Old Town", "group": "8A"},       # renamed
        {"name": "Cassius", "city": "Old Town", "group": "1A"},        # NOT renamed
        {"name": "Elsewhere", "city": "Other Town", "group": "5A"},    # untouched
    ]


def test_a_town_rename_reaches_the_schools_that_were_not_renamed():
    script = _load_script()
    rows = _rows()
    moved = script.apply(rows, _tables())

    by_name = {r["name"]: r for r in rows}
    assert moved == [("Old Town", "New School")]
    assert by_name["New School"]["city"] == "New Town"
    assert by_name["New School"]["source"] == "Old Town", "identity stamped"
    # The city-only row: no RENAMES key, and its TOWN still moves.
    assert by_name["Cassius"]["city"] == "New Town"
    assert "source" not in by_name["Cassius"]
    assert by_name["Elsewhere"]["city"] == "Other Town"


def test_a_second_application_changes_nothing():
    script = _load_script()
    rows = _rows()
    script.apply(rows, _tables())
    once = copy.deepcopy(rows)
    moved = script.apply(rows, _tables())
    assert moved == []
    assert rows == once
