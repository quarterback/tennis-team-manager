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
    see test_diaspora_is_directed). With it off, every draw must be coherent."""
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


def _first_tokens(full):
    """Candidate FIRST-name readings of a full name.

    Some cultures have multi-word given names ("Chee Wee Tee" is Chee Wee + Tee),
    so a bare `split(" ", 1)[0]` reads the first word only and calls a perfectly
    coherent name a violation. The existing coherence test does the same
    two-reading dance; anything checking a first name has to."""
    return {full.split(" ", 1)[0], full.rsplit(" ", 1)[0]}


def test_diaspora_is_directed_not_a_second_roll_on_the_world_mix():
    """‼️ THE SIEVE. Diaspora used to pick its donor with a second, independent
    draw from THE WHOLE WORLD MIX, so any region could donate a name to any other
    — Russian names on Dominicans, Chinese names on Africans, at ~11% of all
    players. Owner, 2027-08: "the pool is a sieve … it's breaking my immersion."

    A region may now only receive a name from a heritage it DECLARES
    (`diaspora` in regions.json), and a region that declares none is
    monocultural. This drives the blend as hard as it goes and asserts every
    single crossing lands on a declared route."""
    import json
    import os
    import random

    import generators.names as _names
    from generators import make_name_picker
    from generators.names import _NAMES_DIR

    pools = {k: json.load(open(os.path.join(_NAMES_DIR, f"{k}.json")))
             for k in ("male_first", "female_first", "surnames")}
    regions = json.load(open(os.path.join(_NAMES_DIR, "regions.json")))["regions"]

    def firsts(rid, kind):
        out = set()
        for sr in (regions[rid].get("subregions") or [regions[rid]]):
            for k in sr.get("first_keys", []):
                out |= set(pools[kind].get(k) or [])
        return out

    # Every declared donor must be a real region, or the route silently does
    # nothing and the region quietly becomes monocultural.
    for rid, reg in regions.items():
        for donor in (reg.get("diaspora") or {}):
            assert donor in regions, f"{rid} declares unknown heritage {donor!r}"

    saved = _names.DIASPORA_SHARE
    _names.DIASPORA_SHARE = 1.0            # every eligible draw crosses
    try:
        for rid in sorted(regions):
            if rid == "zaryanovia":
                continue
            for gender, kind in (("male", "male_first"), ("female", "female_first")):
                own = firsts(rid, kind)
                if not own:
                    continue
                legal = set(own)
                for donor in (regions[rid].get("diaspora") or {}):
                    legal |= firsts(donor, kind)
                fn = make_name_picker(random.Random(hash(rid) & 0xffff), gender=gender,
                                      region_weights={rid: 1.0})
                for _ in range(60):
                    full, _c = fn()
                    if full.startswith("Player "):   # pool exhausted — see below
                        continue
                    assert _first_tokens(full) & legal, (
                        f"{rid} drew {full!r}, a heritage it never declared — the "
                        f"donor pool is not being taken from `diaspora`")
    finally:
        _names.DIASPORA_SHARE = saved


def test_a_region_without_declared_heritage_is_monocultural():
    """The DEFAULT is no mixing. An insular nation reading as insular is correct;
    an insular nation reading as a melting pot is the bug this rule removes."""
    import json
    import os
    import random

    import generators.names as _names
    from generators import make_name_picker
    from generators.names import _NAMES_DIR

    regions = json.load(open(os.path.join(_NAMES_DIR, "regions.json")))["regions"]
    silent = [r for r in ("dominican", "japan", "china", "south_korea", "africa",
                          "north_africa", "mexico")
              if r in regions and not regions[r].get("diaspora")]
    assert silent, "expected the insular regions to declare no heritage"

    pools = {k: json.load(open(os.path.join(_NAMES_DIR, f"{k}.json")))
             for k in ("male_first", "surnames")}

    saved = _names.DIASPORA_SHARE
    _names.DIASPORA_SHARE = 1.0
    try:
        for rid in silent:
            own = set()
            for sr in (regions[rid].get("subregions") or [regions[rid]]):
                for k in sr.get("first_keys", []):
                    own |= set(pools["male_first"].get(k) or [])
            fn = make_name_picker(random.Random(5), gender="male",
                                  region_weights={rid: 1.0})
            for _ in range(80):
                full, _c = fn()
                if full.startswith("Player "):
                    continue
                assert _first_tokens(full) & own, \
                    f"{rid} is monocultural but drew {full!r}"
    finally:
        _names.DIASPORA_SHARE = saved
