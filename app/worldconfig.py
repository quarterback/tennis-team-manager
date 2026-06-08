"""Tiny persisted key/value config for the one world — e.g. the nationality
"band" chosen at onboarding.

Leaf module: depends only on `dbpath`, so any generator (rosters, coaches,
recruits) can read the chosen band without an app-level import cycle. The value
is read at generation time, so it must be set BEFORE a new world is seeded.
"""
from __future__ import annotations

import json

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


# --- Typed accessors (caller supplies the default, so the code stays the single
# source of truth — config only OVERRIDES). Malformed/out-of-range values fall back.
def get_int(key: str, default: int, *, lo: int = 1, hi: int = 10_000) -> int:
    try:
        return max(lo, min(hi, int(float(get(key)))))
    except (ValueError, TypeError):
        return default


def get_float(key: str, default: float, *, lo: float = 0.0, hi: float = 1e9) -> float:
    try:
        return max(lo, min(hi, float(get(key))))
    except (ValueError, TypeError):
        return default


def get_json(key: str, default):
    try:
        raw = get(key)
        return json.loads(raw) if raw else default
    except (ValueError, TypeError):
        return default


def name_preset() -> str:
    """The nationality-band preset for roster/coach/recruit generation."""
    p = get("name_preset")
    return p if p in _VALID else _DEFAULTS["name_preset"]


def set_name_preset(preset: str) -> None:
    set("name_preset", preset if preset in _VALID else _DEFAULTS["name_preset"])


# --- Active universes (memory): only the chosen divisions × genders are seeded,
# primed and simulated in detail; the rest are left dormant. ------------------
_ALL_DIV = ["D1", "D2", "D3"]
_ALL_GEN = ["men", "women"]


def _list(key: str, allv: list[str]) -> list[str]:
    raw = get(key)
    try:
        v = list(json.loads(raw)) if raw else []
    except (ValueError, TypeError):
        v = []
    v = [x for x in allv if x in v]      # keep canonical order, drop junk
    return v or allv                     # empty/none → all (default)


def active_divisions() -> list[str]:
    return _list("active_divisions", _ALL_DIV)


def active_genders() -> list[str]:
    return _list("active_genders", _ALL_GEN)


def is_active(division: str, gender: str) -> bool:
    return division in active_divisions() and gender in active_genders()


def set_active(divisions: list[str], genders: list[str]) -> None:
    set("active_divisions", json.dumps([d for d in _ALL_DIV if d in (divisions or [])] or _ALL_DIV))
    set("active_genders", json.dumps([g for g in _ALL_GEN if g in (genders or [])] or _ALL_GEN))


# --- Per-region fidelity --------------------------------------------------------
# A chosen band is just the starting weight map; on top of it the player can dial
# any individual region/nation up or down with a multiplier. This lets you, say,
# make African or Oceanian players proliferate without abandoning the preset.
# Stored sparsely: only regions whose multiplier != 1.0. A region absent from the
# base band is introduced at a small floor (so a boost can surface rare nations).
_INTRO_FLOOR = 0.004
MULT_CHOICES = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]

# Continents → ordered region ids, for grouping the editor. Any region not listed
# here is appended to "Other" so the editor always covers every region in the data.
_CONTINENTS: list[tuple[str, list[str]]] = [
    ("Africa", ["africa", "africa_cricket", "north_africa", "namibia", "cape_verde",
                "mauritius", "uganda"]),
    ("Americas", ["us", "canada", "latin_america", "south_america", "brazil", "mexico",
                  "cuba", "dominican", "venezuela", "haiti", "curacao", "aruba", "suriname",
                  "guyana", "caribbean_dutch", "caribbean_cricket", "barbados", "bahamas",
                  "bermuda"]),
    ("Asia", ["east_asia", "south_asia", "southeast_asia", "philippines", "malaysia",
              "indonesia", "thailand", "hong_kong", "mongolia", "north_korea",
              "afghan_central_asia", "central_west_asia", "kazakhstan"]),
    ("Europe", ["british_isles", "scotland", "europe_western", "europe_eastern",
                "europe_southeast", "nordic", "netherlands", "italy", "finland", "sweden",
                "norway", "denmark", "turkey", "greece", "russia", "ukraine", "czechia",
                "germany", "croatia", "serbia", "slovenia", "hungary", "slovakia", "austria",
                "san_marino", "switzerland", "lithuania", "spain", "poland", "belgium",
                "albania", "estonia", "georgia", "iceland", "latvia"]),
    ("Middle East", ["israel", "palestine", "lebanon", "iran", "gulf_cricket"]),
    ("Oceania", ["anzac", "pacific_islands", "guam"]),
]


def region_mult() -> dict[str, float]:
    raw = get("region_mult")
    try:
        return {str(k): float(v) for k, v in (json.loads(raw) if raw else {}).items()}
    except (ValueError, TypeError, AttributeError):
        return {}


def set_region_mult(mult: dict) -> None:
    """Persist only the regions the player actually changed (multiplier != 1)."""
    clean = {}
    for k, v in (mult or {}).items():
        try:
            f = float(v)
        except (ValueError, TypeError):
            continue
        if f >= 0 and abs(f - 1.0) > 1e-9:
            clean[str(k)] = f
    set("region_mult", json.dumps(clean))


def region_weights() -> dict[str, float]:
    """The effective {region_id: weight} mix = the chosen band, with each region's
    per-region multiplier applied. This is what every generator should use."""
    from generators import region_preset
    base = dict(region_preset(name_preset()))
    mult = region_mult()
    if not mult:
        return base
    out = dict(base)
    for region, f in mult.items():
        if region in out:
            out[region] = out[region] * f
        elif f > 0:
            out[region] = _INTRO_FLOOR * f      # surface a region the band omits
    return {k: v for k, v in out.items() if v > 0}


def region_groups() -> list[dict]:
    """Editor model: continents → regions with label + current multiplier, plus
    the region's share in the *base band* (so the UI can show what's already
    prominent). Covers every region in the data (unmapped → 'Other')."""
    from generators.names import get_name_regions, region_preset
    meta = get_name_regions()
    base = region_preset(name_preset())
    total = sum(base.values()) or 1.0
    mult = region_mult()
    groups: list[dict] = []

    def _row(rid: str) -> dict:
        label = (meta.get(rid) or {}).get("label") or rid.replace("_", " ").title()
        return {"id": rid, "label": label, "mult": mult.get(rid, 1.0),
                "base_pct": round(100 * base.get(rid, 0.0) / total, 1)}

    placed = {r for _c, rids in _CONTINENTS for r in rids if r in meta}
    for cont, rids in _CONTINENTS:
        rows = [_row(r) for r in rids if r in meta]
        if rows:
            groups.append({"continent": cont, "regions": rows})
    other = [_row(r) for r in sorted(meta) if r not in placed]
    if other:
        groups.append({"continent": "Other", "regions": other})
    return groups
