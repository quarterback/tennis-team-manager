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
    ("africa_pro", "Africa"),
    ("oceania", "Oceania"),
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


def snapshot() -> dict[str, str]:
    """All persisted settings as a {key: value} dict. Used to hand the active
    config to generation worker processes so they don't depend on the DB being
    readable from a child (see app.parallel)."""
    conn = _conn()
    rows = conn.execute("SELECT key, value FROM world_setting").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def prime_cache(values: dict[str, str]) -> None:
    """Seed the in-process config cache directly (no DB read) — for a worker
    process that received the parent's `snapshot()`."""
    _cache.update(values or {})


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
_ALL_DIV = ["D1", "D2", "D3", "D4"]
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


# --- Coached program (career mode) ---------------------------------------------
# The single program the human manages, as (division, school, gender). Unset =>
# spectator mode (the "Your Team" surface hides entirely). Division is stored
# alongside the school so we never have to scan divisions to find which one a
# school belongs to. The coached universe is always force-activated at world
# creation (see web.server.world_new), so a program is never stuck dormant.
def user_program() -> dict | None:
    """The coached program as {"division","school","gender"}, or None if unset."""
    school = get("user_school")
    gender = get("user_gender")
    division = get("user_division")
    if school and gender in _ALL_GEN and division in _ALL_DIV:
        return {"division": division, "school": school, "gender": gender}
    return None


def has_user_program() -> bool:
    return user_program() is not None


def set_user_program(division: str, school: str, gender: str) -> None:
    """Persist the coached program. No-op on a malformed (div, school, gender)."""
    if division in _ALL_DIV and gender in _ALL_GEN and (school or "").strip():
        set("user_division", division)
        set("user_school", school.strip())
        set("user_gender", gender)


def clear_user_program() -> None:
    for k in ("user_division", "user_school", "user_gender"):
        set(k, "")


def get_coach_career() -> list:
    """Past coaching seats (career mode), oldest first. Each: {year, division,
    school, gender, wins, losses, verdict, finish}. The CURRENT seat is
    user_program(); this is only the programs you've LEFT."""
    car = get_json("coach_career", [])
    return car if isinstance(car, list) else []


def push_coach_seat(entry: dict) -> None:
    car = get_coach_career()
    car.append(entry)
    set("coach_career", json.dumps(car))


# --- International share --------------------------------------------------------
# Fraction of the incoming RECRUIT class that is international. Real college tennis
# skews far more international than the US-junior pool alone, so this is tunable.
# (Base college rosters set their international SHARE by program level —
# ncaa.region_weights_for / recruiting.intl_share_for — and use the band mix only
# for which nations the internationals come from; this knob targets the recruit
# pipeline, the "players coming in".) Stored as a plain float; the default mirrors
# the engine constant world.RECRUIT_INTL_SHARE.
DEFAULT_INTL_SHARE = 0.30
INTL_SHARE_CHOICES = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]


def intl_share() -> float:
    """Effective international fraction of the recruit class (0..0.95)."""
    return get_float("intl_share", DEFAULT_INTL_SHARE, lo=0.0, hi=0.95)


def set_intl_share(value) -> None:
    try:
        f = max(0.0, min(0.95, float(value)))
    except (ValueError, TypeError):
        return
    set("intl_share", repr(f))


def box_stats_enabled() -> bool:
    """Per-match box stats (aces/DFs/winners/UEs/serve+return/BPs) recorded on
    every season dual via the engine.boxstats overlay. On by default; the world
    hub exposes a per-save switch to turn it off (scoreline-only persistence,
    ~4x faster dual sims). Read at sim time, so flipping it mid-season simply
    stops/starts stat recording from the next dual on."""
    return get("box_stats") != "off"


def set_box_stats(on) -> None:
    set("box_stats", "on" if on else "off")


DEFAULT_PRESEASON_PORTAL_CAP = 250


def preseason_portal_cap() -> int:
    """Max risers the one-time PRE-SEASON portal promotes per gender (the world-gen
    misallocation fix). Tunable per save; the fall portal keeps its own fixed cap."""
    try:
        return max(0, int(get("preseason_portal_cap") or DEFAULT_PRESEASON_PORTAL_CAP))
    except (ValueError, TypeError):
        return DEFAULT_PRESEASON_PORTAL_CAP


def set_preseason_portal_cap(value) -> None:
    try:
        set("preseason_portal_cap", str(max(0, int(value))))
    except (ValueError, TypeError):
        return


DEFAULT_PROS_PER_CYCLE = 18          # per gender, per portal cycle (kept EVEN)


def pros_per_cycle() -> int:
    """How many pros enter PER GENDER each portal cycle (the elite portal-only tier).
    Always even so men and women get the same count; tunable so a spike can be dialled
    down. 0 disables the pro tier entirely."""
    try:
        n = int(get("pros_per_cycle") or DEFAULT_PROS_PER_CYCLE)
    except (ValueError, TypeError):
        n = DEFAULT_PROS_PER_CYCLE
    return max(0, n - (n % 2))       # clamp to even


def set_pros_per_cycle(value) -> None:
    try:
        n = max(0, int(value))
        set("pros_per_cycle", str(n - (n % 2)))    # store even
    except (ValueError, TypeError):
        return


# --- Analytics Bureau "fit" band (Underplaced Talent → FITS column) -------------
# How wide the calibre band is, in OVR grade points, that a talent is matched to a
# program for. Reach UP = a slight stretch above their level; reach DOWN = how far
# below they'll still be surfaced as a fit. Wider DOWN → more tiers / more spread.
DEFAULT_FIT_REACH_UP = 3.0
DEFAULT_FIT_REACH_DOWN = 15.0


def fit_reach_up() -> float:
    try:
        return max(0.0, min(20.0, float(get("fit_reach_up") or DEFAULT_FIT_REACH_UP)))
    except (ValueError, TypeError):
        return DEFAULT_FIT_REACH_UP


def set_fit_reach_up(value) -> None:
    try:
        set("fit_reach_up", repr(max(0.0, min(20.0, float(value)))))
    except (ValueError, TypeError):
        return


def fit_reach_down() -> float:
    try:
        return max(1.0, min(40.0, float(get("fit_reach_down") or DEFAULT_FIT_REACH_DOWN)))
    except (ValueError, TypeError):
        return DEFAULT_FIT_REACH_DOWN


def set_fit_reach_down(value) -> None:
    try:
        set("fit_reach_down", repr(max(1.0, min(40.0, float(value)))))
    except (ValueError, TypeError):
        return


# --- Per-region weights ---------------------------------------------------------
# A chosen band is a STARTING point; the editor then exposes a DIRECT weight per
# region, so any bespoke international mix is expressible — e.g. a European core
# with meaningful Latin America / Canada / Africa — instead of capped multipliers
# on a fixed preset (where ×8 on a tiny base still renormalizes to ~nothing).
# Stored as the full authored {region_id: weight} map; empty = use the band as-is.
# Editor weights are on a band×WEIGHT_SCALE integer scale; the values are RELATIVE
# (every consumer renormalizes), so the absolute scale is purely cosmetic.
WEIGHT_SCALE = 1000

# Regions that exist in the name data (so the picker can still draw their names for
# OTHER purposes) but must NEVER be selectable as a standalone nationality in the
# editor, nor reintroduced into the international mix. `guam` only backs the Chamorro
# name picker for US-territory recruits (app/juniors); it is a US origin, not a nation.
_HIDDEN_REGIONS = {"guam"}

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
              "indonesia", "thailand", "hong_kong", "mongolia", "south_korea", "north_korea",
              "afghan_central_asia", "central_west_asia", "kazakhstan"]),
    ("Europe", ["british_isles", "scotland", "europe_western", "europe_eastern",
                "europe_southeast", "nordic", "netherlands", "italy", "finland", "sweden",
                "norway", "denmark", "turkey", "greece", "russia", "ukraine", "czechia",
                "germany", "croatia", "serbia", "slovenia", "hungary", "slovakia", "austria",
                "san_marino", "switzerland", "lithuania", "spain", "poland", "belgium",
                "albania", "estonia", "georgia", "iceland", "latvia"]),
    ("Middle East", ["israel", "palestine", "lebanon", "iran", "gulf_cricket"]),
    # Guam is intentionally NOT here: it is a US territory generated as a domestic
    # dual-citizen origin (see app/juniors.US_STATES), not a selectable nationality.
    ("Oceania", ["anzac", "pacific_islands"]),
]


def region_weights_custom() -> dict[str, float]:
    """The player's authored absolute {region: weight} international mix, or {} when
    none is set (fall back to the chosen band)."""
    raw = get("region_w")
    try:
        d = json.loads(raw) if raw else {}
        return {str(k): float(v) for k, v in d.items()
                if float(v) > 0 and str(k) not in _HIDDEN_REGIONS and str(k) != "us"}
    except (ValueError, TypeError, AttributeError):
        return {}


def set_region_weights(weights: dict) -> None:
    """Persist the authored {region: weight} international mix. A region at 0 is
    dropped (excluded from the pool); an empty/all-zero map clears back to the band."""
    clean = {}
    for k, v in (weights or {}).items():
        try:
            f = float(v)
        except (ValueError, TypeError):
            continue
        if f > 0 and str(k) not in _HIDDEN_REGIONS and str(k) != "us":
            clean[str(k)] = round(f, 3)
    set("region_w", json.dumps(clean))


def region_weights() -> dict[str, float]:
    """The effective {region_id: weight} international mix every generator uses: the
    player's authored mix if set, else the chosen band. US is omitted (its share is
    the domestic split — see intl_share); hidden regions (guam) are excluded. Weights
    are relative; consumers renormalize."""
    custom = region_weights_custom()
    if custom:
        return dict(custom)
    from generators import region_preset
    base = dict(region_preset(name_preset()))
    return {k: v for k, v in base.items()
            if v > 0 and k not in _HIDDEN_REGIONS and k != "us"}


def region_groups() -> list[dict]:
    """Editor model: continents → regions, each with its current editor WEIGHT — the
    authored value if the player set one, else the band weight on the WEIGHT_SCALE
    integer scale. Covers every region in the data (unmapped → 'Other')."""
    from generators.names import get_name_regions, region_preset
    meta = get_name_regions()
    base = region_preset(name_preset())
    custom = region_weights_custom()

    def _weight(rid: str):
        if rid in custom:
            return round(custom[rid], 2)
        if rid in base:
            return max(1, round(base[rid] * WEIGHT_SCALE))
        return 0

    def _row(rid: str) -> dict:
        label = (meta.get(rid) or {}).get("label") or rid.replace("_", " ").title()
        return {"id": rid, "label": label, "weight": _weight(rid),
                "is_domestic": rid == "us"}

    groups: list[dict] = []
    placed = {r for _c, rids in _CONTINENTS for r in rids if r in meta}
    for cont, rids in _CONTINENTS:
        rows = [_row(r) for r in rids if r in meta and r not in _HIDDEN_REGIONS]
        if rows:
            groups.append({"continent": cont, "regions": rows})
    other = [_row(r) for r in sorted(meta)
             if r not in placed and r not in _HIDDEN_REGIONS]
    if other:
        groups.append({"continent": "Other", "regions": other})
    return groups
