import random

from generators import make_name_picker, region_preset, list_presets


def test_picker_deterministic():
    fn1 = make_name_picker(random.Random(1), gender="male", region_weights=region_preset("global"))
    fn2 = make_name_picker(random.Random(1), gender="male", region_weights=region_preset("global"))
    a = [fn1() for _ in range(20)]
    b = [fn2() for _ in range(20)]
    assert a == b


def test_names_unique_and_shaped():
    fn = make_name_picker(random.Random(5), gender="female", region_weights=region_preset("global"))
    names = [fn() for _ in range(50)]
    fulls = [n for n, _ in names]
    assert len(set(fulls)) == len(fulls)            # unique
    assert all(" " in n for n in fulls)             # first + last
    assert any(c for _, c in names)                 # at least some country codes


def test_presets_exist():
    presets = list_presets()
    assert "global" in presets and "us_only" in presets


def test_us_only_skews_us():
    fn = make_name_picker(random.Random(3), gender="male", region_weights=region_preset("us_only"))
    countries = [c for _, c in (fn() for _ in range(40))]
    assert countries.count("US") >= 30


def test_draws_are_subregion_coherent():
    """O27 rule: ONE subregion per draw — first name, surname, AND country must
    all be satisfiable by a single subregion (no 'Babar Iyer', no 'Pérez (IT)').

    Guards the BASELINE pools, so the intentional diversity/diaspora blend is held
    OFF here (it deliberately pairs a home country with another culture's name —
    see test_diaspora_pairs_real_names). With it off, every draw must be coherent."""
    import json
    import os
    import random

    import generators.names as _names
    from generators import make_name_picker, region_preset
    from generators.names import _NAMES_DIR

    _saved_share = _names.DIASPORA_SHARE
    _names.DIASPORA_SHARE = 0.0

    pools = {k: json.load(open(os.path.join(_NAMES_DIR, f"{k}.json")))
             for k in ("male_first", "female_first", "surnames")}
    regions = json.load(open(os.path.join(_NAMES_DIR, "regions.json")))["regions"]

    def units(region):
        subs = region.get("subregions")
        return subs if subs else [region]

    def in_buckets(kind, keys, token):
        return any(token in (pools[kind].get(k) or []) for k in keys)

    def coherent(first, last, country, gender_kind):
        for region in regions.values():
            for sr in units(region):
                c = sr.get("country") or region.get("country")
                cw = sr.get("country_weights") or region.get("country_weights") or {}
                if (c and c != country) or (not c and country not in cw):
                    continue
                if in_buckets(gender_kind, sr.get("first_keys", []), first) and \
                   in_buckets("surnames", sr.get("surname_keys", []), last):
                    return True
        return False

    try:
        for preset in ("global", "americas_pro", "european", "us_only"):
            for gender, kind in (("male", "male_first"), ("female", "female_first")):
                fn = make_name_picker(random.Random(99), gender=gender,
                                      region_weights=region_preset(preset))
                for _ in range(300):
                    full, country = fn()
                    if country == "ZR" or " " not in full:     # zaryanovia is procedural
                        continue
                    first, last = full.rsplit(" ", 1)
                    # multi-word firsts: recheck with the leading token split too
                    ok = coherent(first, last, country, kind) or \
                         coherent(full.split(" ", 1)[0], full.split(" ", 1)[1], country, kind)
                    assert ok, f"incoherent draw: {full!r} ({country}) [{preset}/{gender}]"
    finally:
        _names.DIASPORA_SHARE = _saved_share


def test_diaspora_pairs_real_names():
    """The diversity blend must produce REAL names — a home-country flag paired
    with another culture's genuine first+surname — never junk or fallbacks. So
    every draw's name is coherent for SOME subregion even if the country differs."""
    import json
    import os
    import random

    import generators.names as _names
    from generators import make_name_picker, region_preset
    from generators.names import _NAMES_DIR

    pools = {k: json.load(open(os.path.join(_NAMES_DIR, f"{k}.json")))
             for k in ("male_first", "female_first", "surnames")}
    regions = json.load(open(os.path.join(_NAMES_DIR, "regions.json")))["regions"]

    def name_is_real(first, last, kind):
        # first+last both live in SOME single subregion's buckets (a genuine name
        # from some culture), regardless of which country it was tagged to.
        for region in regions.values():
            for sr in (region.get("subregions") or [region]):
                fk, sk = sr.get("first_keys", []), sr.get("surname_keys", [])
                if any(first in (pools[kind].get(k) or []) for k in fk) and \
                   any(last in (pools["surnames"].get(k) or []) for k in sk):
                    return True
        return False

    saved = _names.DIASPORA_SHARE
    _names.DIASPORA_SHARE = 0.5                 # force lots of diaspora draws
    try:
        cross = 0
        for gender, kind in (("male", "male_first"), ("female", "female_first")):
            fn = make_name_picker(random.Random(7), gender=gender,
                                  region_weights=region_preset("global"))
            for _ in range(400):
                full, country = fn()
                if country == "ZR" or " " not in full:
                    continue
                first, last = full.rsplit(" ", 1)
                assert name_is_real(first, last, kind) or \
                    name_is_real(*full.split(" ", 1), kind), \
                    f"diaspora produced an unreal name: {full!r}"
                cross += 1
        assert cross > 0
    finally:
        _names.DIASPORA_SHARE = saved
