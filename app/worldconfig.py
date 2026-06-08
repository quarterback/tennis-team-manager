"""Tiny persisted key/value config for the one world — e.g. the nationality
"band" chosen at onboarding.

Leaf module: depends only on `dbpath`, so any generator (rosters, coaches,
recruits) can read the chosen band without an app-level import cycle. The value
is read at generation time, so it must be set BEFORE a new world is seeded.
"""
from __future__ import annotations

from . import dbpath

# Friendly nationality bands offered at onboarding -> name-region preset id.
# Each value must be a real preset in generators/data/names/regions.json.
BANDS: list[tuple[str, str]] = [
    ("tennis_global", "Realistic tour geography (default)"),
    ("global", "Worldwide — even mix"),
    ("us_majority", "USA-heavy"),
    ("european", "European"),
    ("americas_pro", "Americas"),
    ("asian_pro", "Asia-Pacific"),
]
_VALID = {b for b, _ in BANDS}
_DEFAULTS = {"name_preset": "tennis_global"}
_cache: dict[str, str] = {}


def _conn():
    conn = dbpath.connect(dbpath.resolve_db_path())
    conn.execute("CREATE TABLE IF NOT EXISTS world_setting (key TEXT PRIMARY KEY, value TEXT)")
    return conn


def get(key: str) -> str:
    if key in _cache:
        return _cache[key]
    conn = _conn()
    row = conn.execute("SELECT value FROM world_setting WHERE key=?", (key,)).fetchone()
    conn.close()
    val = row["value"] if row else _DEFAULTS.get(key, "")
    _cache[key] = val
    return val


def set(key: str, value: str) -> None:        # noqa: A001 (tiny config API)
    conn = _conn()
    conn.execute("INSERT INTO world_setting (key, value) VALUES (?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()
    _cache[key] = value


def name_preset() -> str:
    """The nationality-band preset for roster/coach/recruit generation."""
    p = get("name_preset")
    return p if p in _VALID else _DEFAULTS["name_preset"]


def set_name_preset(preset: str) -> None:
    set("name_preset", preset if preset in _VALID else _DEFAULTS["name_preset"])
