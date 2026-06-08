"""
Name-system wiring guards (ported from o27 baseball's test_name_regions).

regions.json references name buckets by key (first_keys / surname_keys). The
picker resolves a missing key to an EMPTY candidate list and silently falls
back to "Player <random>" — so a typo'd bucket key never raises, it just
quietly degrades the roster. These tests turn that silent failure into a loud
one:

  * every region/subregion bucket reference resolves to a real bucket;
  * every preset references real regions;
  * sampling every preset and every region yields real names, never the
    "Player N" fallback.
"""
from __future__ import annotations

import json
import os
import random
import re

from generators.names import (
    get_name_regions,
    get_name_region_presets,
    make_name_picker,
)

_NAMES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "generators", "data", "names",
)
_PLAYER_FALLBACK = re.compile(r"^Player \d+$")


def _load(fname: str) -> dict:
    with open(os.path.join(_NAMES_DIR, fname), encoding="utf-8") as fh:
        return json.load(fh)


def _iter_keysets(region: dict):
    """Yield (first_keys, surname_keys) for a flat region and each subregion."""
    subs = region.get("subregions")
    if isinstance(subs, list) and subs:
        for sr in subs:
            yield sr.get("first_keys", []), sr.get("surname_keys", [])
    else:
        yield region.get("first_keys", []), region.get("surname_keys", [])


def test_first_keys_resolve_to_male_first_buckets():
    male = _load("male_first.json")
    missing = []
    for rid, region in get_name_regions().items():
        if rid == "zaryanovia":
            continue
        for first_keys, _ in _iter_keysets(region):
            missing += [f"{rid}: {k!r}" for k in first_keys if k not in male]
    assert not missing, "first_keys with no male_first bucket: " + "; ".join(missing)


def test_surname_keys_resolve_to_surname_buckets():
    surnames = _load("surnames.json")
    missing = []
    for rid, region in get_name_regions().items():
        if rid == "zaryanovia":
            continue
        for _, surname_keys in _iter_keysets(region):
            missing += [f"{rid}: {k!r}" for k in surname_keys if k not in surnames]
    assert not missing, "surname_keys with no surnames bucket: " + "; ".join(missing)


def test_female_first_buckets_exist_for_every_first_key():
    """A key present in male_first but missing in female_first would silently
    shrink a mixed/female league — and tennis runs a full women's tour."""
    female = _load("female_first.json")
    missing = []
    for rid, region in get_name_regions().items():
        if rid == "zaryanovia":
            continue
        for first_keys, _ in _iter_keysets(region):
            missing += [f"{rid}: {k!r}" for k in first_keys if k not in female]
    assert not missing, "first_keys with no female_first bucket: " + "; ".join(missing)


def test_presets_reference_real_regions():
    regions = get_name_regions()
    bad = []
    for pid, preset in get_name_region_presets().items():
        for rid in (preset.get("weights") or {}):
            if rid not in regions and rid != "zaryanovia":
                bad.append(f"{pid} -> {rid!r}")
    assert not bad, "presets referencing unknown regions: " + "; ".join(bad)


def test_every_preset_generates_real_names():
    for pid, preset in get_name_region_presets().items():
        pick = make_name_picker(random.Random(1234), gender="mixed",
                                region_weights=preset["weights"])
        fallbacks = [n for n in (pick()[0] for _ in range(60)) if _PLAYER_FALLBACK.match(n)]
        assert not fallbacks, f"preset {pid!r} produced fallbacks: {fallbacks[:5]}"


def test_every_region_generates_real_names():
    for rid in get_name_regions():
        pick = make_name_picker(random.Random(99), gender="mixed", region_weights={rid: 1.0})
        fallbacks = [n for n in (pick()[0] for _ in range(40)) if _PLAYER_FALLBACK.match(n)]
        assert not fallbacks, f"region {rid!r} produced fallbacks: {fallbacks[:5]}"
