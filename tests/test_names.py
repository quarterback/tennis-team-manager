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
