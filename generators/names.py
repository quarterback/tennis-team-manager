"""
Global, gender-aware player-name generation for the tennis sim.

Lifted in spirit from o27v2's `league.make_name_picker`: a single
`random.Random` drives every draw so a seeded picker is fully
deterministic. Names come from the viperball-derived pools in
`data/names/` — `male_first.json`, `female_first.json`, `surnames.json`
keyed by ~40 cultural buckets, with `regions.json` mapping high-level
world regions (and named presets) onto those buckets.

Region shape (regions.json):
  - A region either has flat `first_keys`/`surname_keys` (legacy) OR a
    list of `subregions`. Subregions are the atomic draw unit: one is
    chosen by weight and BOTH first name and surname come from that
    subregion's keys, keeping pairs culturally coherent (so south_asia
    yields "Aarav Sharma", not "Babar Iyer").
  - Country codes resolve via a direct `country` field, else a sampled
    `country_weights` map, for ISO-tagged flags.

The `zaryanovia` region routes through the dedicated creole converter in
`generators/zaryan_names.py`.

Public API
----------
  make_name_picker(rng, *, gender="male", region_weights=None) -> _name()
      where _name() -> (full_name: str, country_code: str)
  region_preset(name) -> {region_id: weight}     # named presets from regions.json
  list_presets() -> list[str]
"""
from __future__ import annotations

import os
import json
import random
from typing import Callable, Optional

from . import zaryan_names as _zy

_NAMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "names")

_name_pools: Optional[dict] = None
_regions_meta: Optional[dict] = None


# ---------------------------------------------------------------------------
# Pool / meta loaders (cached)
# ---------------------------------------------------------------------------

def _load_name_pools() -> dict[str, dict]:
    """Load the raw first/surname pools, keyed by cultural bucket."""
    global _name_pools
    if _name_pools is None:
        _name_pools = {}
        for kind in ("male_first", "female_first", "surnames"):
            with open(os.path.join(_NAMES_DIR, f"{kind}.json"), encoding="utf-8") as fh:
                _name_pools[kind] = json.load(fh)
    return _name_pools


def _load_regions_meta() -> dict:
    global _regions_meta
    if _regions_meta is None:
        with open(os.path.join(_NAMES_DIR, "regions.json"), encoding="utf-8") as fh:
            _regions_meta = json.load(fh)
    return _regions_meta


def get_name_regions() -> dict[str, dict]:
    return _load_regions_meta().get("regions", {})


def get_name_region_presets() -> dict[str, dict]:
    return _load_regions_meta().get("presets", {})


def list_presets() -> list[str]:
    return sorted(get_name_region_presets().keys())


def region_preset(name: str) -> dict[str, float]:
    """Return the {region_id: weight} map for a named preset (e.g.
    "global", "us_only", "european"). Raises on unknown preset."""
    presets = get_name_region_presets()
    if name not in presets:
        raise ValueError(f"Unknown name-region preset: {name!r}")
    return dict(presets[name]["weights"])


# ---------------------------------------------------------------------------
# Weight helpers
# ---------------------------------------------------------------------------

def _default_region_weights() -> dict[str, float]:
    presets = get_name_region_presets()
    if "americas_pro" in presets:
        return dict(presets["americas_pro"]["weights"])
    return {"us": 1.0}


def _normalise_weights(weights: Optional[dict[str, float]]) -> dict[str, float]:
    cleaned = {k: max(0.0, float(v)) for k, v in (weights or {}).items()}
    total = sum(cleaned.values())
    if total <= 0:
        return _default_region_weights()
    return {k: v / total for k, v in cleaned.items() if v > 0}


def _pick_weighted_key(rng: random.Random, weights: dict[str, float]) -> str:
    r = rng.random()
    cumulative = 0.0
    last_key = None
    for k, w in weights.items():
        cumulative += w
        last_key = k
        if r < cumulative:
            return k
    return last_key or next(iter(weights))


# ---------------------------------------------------------------------------
# Picker
# ---------------------------------------------------------------------------

# Diversity / diaspora: the share of draws where a citizen of one region carries
# a name from ANOTHER culture (the country/flag stays the home region's, only the
# name comes from elsewhere) — so diverse nations field diverse people, not a
# monoculture. A region can override this with a `diversity` field in regions.json
# (e.g. crank the melting-pot nations up, keep insular ones near 0). Only fires
# when the world mix spans more than one region. See AAR-name-pool-diversity.
DIASPORA_SHARE = 0.12


def make_name_picker(
    rng: random.Random,
    *,
    gender: str = "male",
    region_weights: Optional[dict[str, float]] = None,
) -> Callable[[], tuple[str, str]]:
    """Return a callable `_name() -> (full_name, country_code)` drawing
    unique gender-aware names over the configured world-region mix.

    gender: "male" | "female" | "mixed" (per-draw 50/50).
    region_weights: {region_id: weight}, auto-normalised; falls back to
                    the americas_pro preset when None.
    """
    pools = _load_name_pools()
    regions_meta = get_name_regions()
    weights = _normalise_weights(region_weights)
    used: set[str] = set()
    # Accept the team-sport spellings too: callers pass "men"/"women" (the
    # division-gender values) as well as "male"/"female". Without this they fall
    # through to the mixed (50/50) branch and a women's pool draws male names.
    g_lower = (gender or "male").lower()
    g_lower = {"men": "male", "women": "female"}.get(g_lower, g_lower)

    def _first_pool_kind() -> str:
        if g_lower == "male":
            return "male_first"
        if g_lower == "female":
            return "female_first"
        return "male_first" if rng.random() < 0.5 else "female_first"

    def _resolved_gender() -> str:
        if g_lower in ("male", "female"):
            return g_lower
        return "male" if rng.random() < 0.5 else "female"

    def _gather(bucket_kind: str, keys: list[str]) -> list[str]:
        bucket = pools.get(bucket_kind, {})
        out: list[str] = []
        for k in keys:
            v = bucket.get(k)
            if isinstance(v, list):
                out.extend(v)
        return out

    def _resolve_country(node: dict) -> str:
        c = node.get("country")
        if isinstance(c, str) and c:
            return c
        cw = node.get("country_weights")
        if isinstance(cw, dict) and cw:
            return _pick_weighted_key(rng, _normalise_weights(cw))
        return ""

    def _draw_from_region(region_id: str) -> tuple[Optional[str], Optional[str], str]:
        if region_id == "zaryanovia":
            full, country = _zy.draw_zaryan_name(rng, _resolved_gender())
            if not full:
                return None, None, country or "ZR"
            # Two-part name; split on the last space into first/last.
            if " " in full:
                first, last = full.rsplit(" ", 1)
            else:
                first, last = full, ""
            return first, last, (country or "ZR")

        region = regions_meta.get(region_id)
        if region is None:
            return None, None, ""
        subregions = region.get("subregions")
        if isinstance(subregions, list) and subregions:
            sr_weights = _normalise_weights(
                {str(i): float(sr.get("weight", 0.0)) for i, sr in enumerate(subregions)}
            )
            idx = int(_pick_weighted_key(rng, sr_weights))
            sr = subregions[idx]
            first_candidates = _gather(_first_pool_kind(), sr.get("first_keys", []))
            last_candidates = _gather("surnames", sr.get("surname_keys", []))
            country = _resolve_country(sr) or _resolve_country(region)
            if not first_candidates or not last_candidates:
                return None, None, country
            return rng.choice(first_candidates), rng.choice(last_candidates), country
        # Flat region.
        first_candidates = _gather(_first_pool_kind(), region.get("first_keys") or [])
        last_candidates = _gather("surnames", region.get("surname_keys") or [])
        country = _resolve_country(region)
        if not first_candidates or not last_candidates:
            return None, None, country
        return rng.choice(first_candidates), rng.choice(last_candidates), country

    def _country_for(region_id: str) -> str:
        """The nationality/flag for a region, independent of which culture's name
        we draw. Samples the home subregion by the SAME weights a normal draw uses,
        so a multi-country region (latin_america, south_america) still follows its
        weighted country mix on a diaspora draw — not always the first-listed one."""
        region = regions_meta.get(region_id)
        if region is None:
            return ""
        subregions = region.get("subregions")
        if isinstance(subregions, list) and subregions:
            sr_weights = _normalise_weights(
                {str(i): float(sr.get("weight", 0.0)) for i, sr in enumerate(subregions)}
            )
            idx = int(_pick_weighted_key(rng, sr_weights))
            sr = subregions[idx]
            return _resolve_country(sr) or _resolve_country(region)
        return _resolve_country(region)

    multi_region = len(weights) > 1

    def _name() -> tuple[str, str]:
        for _ in range(500):
            region_id = _pick_weighted_key(rng, weights)
            # Diversity: sometimes this citizen carries another culture's name. The
            # flag stays this region's; only the name is drawn from elsewhere.
            name_region = region_id
            if multi_region:
                reg = regions_meta.get(region_id) or {}
                share = reg.get("diversity")
                share = DIASPORA_SHARE if share is None else float(share)
                if share > 0.0 and rng.random() < share:
                    name_region = _pick_weighted_key(rng, weights)
                    if name_region == "zaryanovia":    # fictional, procedural — not
                        name_region = region_id        # a real diaspora heritage
            first, last, country = _draw_from_region(name_region)
            if name_region != region_id:
                country = _country_for(region_id)      # nationality = home region
            if not first or not last:
                continue
            full = f"{first} {last}"
            if full not in used:
                used.add(full)
                return full, country
        return f"Player {rng.randint(100, 999)}", ""

    return _name


def make_country_pinned_picker(
    rng: random.Random,
    region_id: str,
    country_code: str,
    *,
    gender: str = "male",
) -> Callable[[], tuple[str, str]]:
    """O27-parity helper for single-nation draws: names come only from the given
    region's subregions whose country matches `country_code` (falling back to the
    whole region when none match), and every draw is tagged with that country."""
    regions_meta = get_name_regions()
    region = dict(regions_meta.get(region_id) or {})
    subs = region.get("subregions")
    if isinstance(subs, list) and subs:
        matched = [sr for sr in subs if sr.get("country") == country_code]
        if matched:
            region = {**region, "subregions": matched}
    # make_name_picker reads the regions dict at construction time, so build the
    # picker under a temporarily pinned view; the closure keeps that view.
    global _regions_meta
    saved = _regions_meta
    presets = (saved or {}).get("presets", {}) if isinstance(saved, dict) else {}
    try:
        _regions_meta = {"regions": {region_id: region}, "presets": presets}
        base = make_name_picker(rng, gender=gender, region_weights={region_id: 1.0})
    finally:
        _regions_meta = saved

    def _pinned() -> tuple[str, str]:
        full, _c = base()
        return full, country_code

    return _pinned
