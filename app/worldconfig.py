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
    # ---- the owner's five (2027-08). Authored as CONTINENT targets and split
    # down to region ids in regions.json; every column sums to 100%. These lead
    # the list because they are the set that was balanced against each other.
    ("global_college", "Global College — realistic NCAA geography (default)"),
    ("latin_world", "Latin World — Americas 49%"),
    ("afro_global", "Afro-Global — Africa 22%"),
    ("asia_pacific", "Asia-Pacific — Asia 25%"),
    ("eurasian", "Eurasian — Europe 27%, Central Asia 3%"),
    # ---- the older bands, kept so an existing save's choice still resolves
    ("tennis_global", "Realistic tour geography"),
    ("pro_tour", "Pro Tour — global mix (ATP/WTA-shaped)"),
    ("global", "Worldwide — even mix"),
    ("us_majority", "USA-heavy"),
    ("european", "European"),
    ("americas_pro", "Americas"),
    ("asian_pro", "Asia-Pacific (legacy)"),
    ("africa_pro", "Africa (legacy)"),
    ("oceania", "Oceania"),
]

_VALID = {b for b, _ in BANDS}
_DEFAULTS = {"name_preset": "global_college"}
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


def match_fidelity() -> str:
    """Per-save dual-match fidelity. "full" (default) resolves every POINT through
    the rich attribute engine (engine.match) so real serve/return/rally talent
    decides outcomes AND produces the box stats from one consistent sim. It is also
    faster than "fast"+box-stats, which reconstructs stats by rejection-sampling.
    "fast" is the legacy game-level Bernoulli model (scoreline from an `overall`
    gap, no native stats) — kept as an opt-in speed mode for stat-free bulk runs.
    Read at sim time, so flipping it mid-season takes effect from the next dual on.
    An env var TTM_FIDELITY=fast forces the legacy model regardless of the switch."""
    import os
    if os.environ.get("TTM_FIDELITY", "").strip().lower() == "fast":
        return "fast"
    return "fast" if get("match_fidelity") == "fast" else "full"


def set_match_fidelity(full) -> None:
    set("match_fidelity", "full" if full else "fast")


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
    # Six regions (owner rule 2027-08), matching the association's own taxonomy.
    # The old shape filed Kenya with South Africa and Zimbabwe under
    # `africa_cricket`, and put Angola and Mozambique in a pan-African `africa`
    # bucket — so "West Africa" and "Central Africa" could not be expressed at all.
    ("Africa", ["north_africa", "west_africa", "central_africa", "southern_africa",
                "east_africa", "indian_ocean_africa"]),
    ("Americas", ["us", "canada", "latin_america", "south_america", "brazil", "mexico",
                  "argentina", "colombia", "chile", "peru", "ecuador", "uruguay",
                  "cuba", "dominican", "venezuela", "haiti", "curacao", "aruba", "suriname",
                  "guyana", "caribbean_dutch", "caribbean_cricket", "barbados", "bahamas",
                  "bermuda"]),
    ("Asia", ["east_asia", "china", "japan", "taiwan", "south_asia", "southeast_asia",
              "philippines", "malaysia",
              "indonesia", "thailand", "hong_kong", "mongolia", "south_korea", "north_korea",
              "afghan_central_asia", "central_west_asia", "kazakhstan"]),
    ("Europe", ["british_isles", "scotland", "france", "europe_western", "europe_eastern",
                "europe_southeast", "nordic", "netherlands", "italy", "finland", "sweden",
                "norway", "denmark", "turkey", "greece", "russia", "ukraine", "czechia",
                "germany", "croatia", "serbia", "slovenia", "hungary", "slovakia", "austria",
                "san_marino", "switzerland", "lithuania", "spain", "poland", "belgium",
                "albania", "bulgaria", "romania", "estonia", "georgia", "iceland", "latvia"]),
    ("Middle East", ["israel", "palestine", "lebanon", "iran", "gulf_cricket"]),
    # Guam is intentionally NOT here: it is a US territory generated as a domestic
    # dual-citizen origin (see app/juniors.US_STATES), not a selectable nationality.
    ("Oceania", ["anzac", "pacific_islands"]),
]


# ‼️ A REGION ID THAT NO LONGER EXISTS IS NOT AN ERROR ANYWHERE — it is a SILENT
# LOSS OF SHARE. `_draw_from_region` returns (None, None, "") for an id the region
# table has never heard of, so the picker just `continue`s: a mix that still holds a
# legacy key quietly redistributes that key's share across the others (a save with
# `africa_cricket: 90` out of 500 loses 18% of its authored geography and reports
# nothing), and a mix made ONLY of legacy keys burns all 500 retries and falls out
# to the `Player NNN` placeholder with an empty country — the one failure the
# exhaustion path was rewritten to make impossible.
#
# `region_w` is PERSISTED, so it outlives the build that wrote it. When 2027-08
# replaced the two African buckets with six, every existing save's authored mix
# still named the old ones. Migrate on READ rather than in a one-shot upgrade
# script: the rows are already out there in saves nobody will run a migration
# against, and the read point is the only place all of them pass through.
#
# Splits follow what each old region actually CONTAINED, so a save keeps both its
# total African share and roughly where in Africa it pointed.
_LEGACY_REGIONS: dict[str, dict[str, float]] = {
    # Sub-Saharan catch-all: NG .40, ET .20, GH .15, TZ .10, MG/MZ/AO .05 each.
    "africa": {"west_africa": 0.55, "east_africa": 0.30,
               "central_africa": 0.05, "southern_africa": 0.05,
               "indian_ocean_africa": 0.05},
    # Cricket nations: ZA .68, ZW .20, KE .12.
    "africa_cricket": {"southern_africa": 0.88, "east_africa": 0.12},
    "namibia": {"southern_africa": 1.0},        # NA
    "cape_verde": {"west_africa": 1.0},         # CV
    "mauritius": {"indian_ocean_africa": 1.0},  # MU
    "uganda": {"east_africa": 1.0},             # UG
}


def migrate_region_weights(weights: dict) -> tuple[dict[str, float], dict[str, str]]:
    """Fold any retired region id into its replacements. Returns the migrated map
    and a {old_id: "new_id, new_id"} note of what moved, so a caller can SAY so
    rather than changing the owner's authored mix behind their back."""
    out: dict[str, float] = {}
    moved: dict[str, str] = {}
    for k, v in (weights or {}).items():
        split = _LEGACY_REGIONS.get(k)
        if split is None:
            out[k] = out.get(k, 0.0) + v
            continue
        for new_id, frac in split.items():
            out[new_id] = out.get(new_id, 0.0) + v * frac
        moved[k] = ", ".join(split)
    return {k: round(v, 3) for k, v in out.items()}, moved


def region_weights_custom() -> dict[str, float]:
    """The player's authored absolute {region: weight} international mix, or {} when
    none is set (fall back to the chosen band). Retired region ids are migrated (see
    `_LEGACY_REGIONS`) and anything this build still cannot resolve is DROPPED — a
    weight the picker cannot draw is not a weight, it is a hole in the mix."""
    raw = get("region_w")
    try:
        d = json.loads(raw) if raw else {}
        d = {str(k): float(v) for k, v in d.items()
             if float(v) > 0 and str(k) not in _HIDDEN_REGIONS and str(k) != "us"}
    except (ValueError, TypeError, AttributeError):
        return {}
    migrated, _moved = migrate_region_weights(d)
    from generators.names import get_name_regions
    known = get_name_regions()
    unknown = [k for k in migrated if k not in known]
    if unknown:
        import logging
        logging.getLogger(__name__).error(
            "region_w names %d region(s) this build does not have: %s. They are "
            "dropped; their share goes to the rest of the mix. Re-author the mix on "
            "/start (or load a mix file) to say where it should go.",
            len(unknown), ", ".join(sorted(unknown)))
    return {k: v for k, v in migrated.items() if k in known}


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


def with_domestic(weights: dict, share) -> dict:
    """A COMPLETE name-picker map: the international mix scaled to fill `share`,
    plus the `us` weight that fills the rest. Non-US regions keep their relative
    proportions. Returns a new dict.

    ‼️ `region_weights()` OMITS `us` by contract — its share is the domestic split,
    not a region weight — so it is an *international* mix and is never a picker map
    on its own. Hand it to `make_name_picker` directly and the picker renormalizes
    over the international regions alone, i.e. the world generates 100% international
    players whatever split the owner chose. Nothing errors and every name is real, so
    the only symptom is a distribution that quietly ignores the setting. The pro
    league shipped exactly that bug. Every pipeline that turns the world mix into a
    picker goes through here.
    """
    try:
        share = max(0.0, min(0.95, float(share)))
    except (ValueError, TypeError):
        share = DEFAULT_INTL_SHARE
    rest = {k: max(0.0, float(v)) for k, v in (weights or {}).items() if k != "us"}
    rest_total = sum(rest.values())
    out: dict[str, float] = {}
    if rest_total > 0:
        for k, v in rest.items():
            out[k] = (v / rest_total) * share
    else:
        share = 0.0            # no international regions configured → all domestic
    out["us"] = 1.0 - share
    return out


def full_region_weights() -> dict[str, float]:
    """The world's complete picker map — `region_weights()` scaled to the configured
    `intl_share()`, with `us` taking the remainder. This is what a generator wants
    when it has no per-program share of its own (the pro league, free agents,
    generated rookies); college programs derive their own share and go through
    `ncaa.region_weights_for` instead."""
    return with_domestic(region_weights(), intl_share())


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


# --- Portable region mixes ------------------------------------------------------
# Authoring an international mix is ~90 numbers the owner is deliberately precise
# about, and it used to have to be retyped for every new save. A mix is now a
# PORTABLE DOCUMENT: it can be downloaded to a file, and a file can be loaded back
# into the editor before a world exists.
#
# ‼️ The FILE is the durable form, not the saved copy. Named mixes live in
# `world_setting`, which lives in the same `tennis.db` as everything else — so a
# saved mix dies with the save, which is exactly the situation the owner is trying
# to escape ("I create a new save once I've updated the file"). Saving is a
# convenience WITHIN a save; downloading is what survives one. Any UI that offers
# both has to say so, or it promises durability it does not have.
#
# Weights in a document are the EDITOR's own integers (the numbers in the boxes),
# not fractions — so a load round-trips to the same visible numbers. They are
# relative and every consumer renormalizes, so the absolute scale carries no
# meaning. A region at zero is OMITTED rather than stored as 0: `applyWeights`
# reads a missing region as zero, and storing an explicit 0 for ~60 unused regions
# would triple the file for no information.
PRESET_FORMAT = "ptc-region-mix"
PRESET_VERSION = 1
MAX_SAVED_MIXES = 40


def region_mix_doc(name: str, base_band: str, share, weights: dict) -> dict:
    """Build a portable mix document from raw editor state. Pure — takes what the
    editor has on screen rather than what is persisted, since the owner tunes the
    grid and exports before any world exists."""
    clean: dict[str, float] = {}
    for k, v in (weights or {}).items():
        try:
            f = float(v)
        except (ValueError, TypeError):
            continue
        rid = str(k)
        if f > 0 and rid not in _HIDDEN_REGIONS and rid != "us":
            clean[rid] = round(f, 3)
    try:
        share_f = max(0.0, min(0.95, float(share)))
    except (ValueError, TypeError):
        share_f = DEFAULT_INTL_SHARE
    return {
        "format": PRESET_FORMAT,
        "version": PRESET_VERSION,
        "name": (str(name or "").strip() or "Custom mix")[:60],
        "base_band": base_band if base_band in _VALID else _DEFAULTS["name_preset"],
        "intl_share": round(share_f, 4),
        "weights": dict(sorted(clean.items())),
    }


class MixFormatError(ValueError):
    """A file that is not a region mix at all — wrong format tag or shape."""


def parse_region_mix(doc) -> dict:
    """Validate a mix document and report what did NOT survive the round trip.

    Returns the doc plus `unknown` (regions in the file this build has never heard
    of) and `missing` (regions this build has that the file does not mention, so
    they load as zero). Both are REPORTED rather than swallowed: region ids get
    added and renamed between builds — this build alone split Africa into six and
    promoted a dozen countries out of shared buckets — so a mix authored against an
    older build is silently a different mix, with no error anywhere.
    """
    if not isinstance(doc, dict):
        raise MixFormatError("not a region-mix file")
    if doc.get("format") != PRESET_FORMAT:
        raise MixFormatError("not a region-mix file "
                             f"(format={doc.get('format')!r}, expected {PRESET_FORMAT!r})")
    try:
        ver = int(doc.get("version", 0))
    except (ValueError, TypeError):
        raise MixFormatError("region-mix file has no readable version")
    if ver > PRESET_VERSION:
        raise MixFormatError(f"region mix is version {ver}; this build reads "
                             f"up to version {PRESET_VERSION}")
    raw = doc.get("weights")
    if not isinstance(raw, dict):
        raise MixFormatError("region mix has no weights")

    from generators.names import get_name_regions
    known = {r for r in get_name_regions()
             if r not in _HIDDEN_REGIONS and r != "us"}
    # A retired id is FOLDED INTO its replacements, not dropped — a mix file is a
    # long-lived artefact and the whole point is that one authored last year still
    # loads. Only ids with no known successor are reported as lost.
    migrated, moved = migrate_region_weights({str(k): v for k, v in raw.items()})
    unknown = sorted(k for k in migrated if k not in known)
    out = region_mix_doc(doc.get("name"), doc.get("base_band"),
                         doc.get("intl_share"), {k: v for k, v in migrated.items()
                                                 if k in known})
    out["unknown"] = unknown
    out["migrated"] = moved
    # NB `set` is this module's config setter, not the builtin — dict keys already
    # support the set algebra, so nothing here needs it.
    out["missing"] = sorted(known - out["weights"].keys())
    return out


def saved_mixes() -> list[dict]:
    """The player's named mixes, newest first. Save-scoped — see the note above."""
    try:
        rows = json.loads(get("region_mixes") or "[]")
    except (ValueError, TypeError):
        return []
    out = []
    for r in rows if isinstance(rows, list) else []:
        try:
            out.append(parse_region_mix(r))
        except MixFormatError:
            continue
    return out


def save_mix(doc: dict) -> list[dict]:
    """Store a named mix, replacing any of the same name. Returns the new list."""
    doc = parse_region_mix(doc)
    keep = [m for m in saved_mixes() if m["name"].lower() != doc["name"].lower()]
    rows = ([doc] + keep)[:MAX_SAVED_MIXES]
    set("region_mixes", json.dumps([{k: v for k, v in m.items()
                                     if k not in ("unknown", "missing", "migrated")}
                                    for m in rows]))
    return rows


def delete_mix(name: str) -> list[dict]:
    rows = [m for m in saved_mixes() if m["name"].lower() != str(name or "").lower()]
    set("region_mixes", json.dumps([{k: v for k, v in m.items()
                                     if k not in ("unknown", "missing", "migrated")}
                                    for m in rows]))
    return rows
