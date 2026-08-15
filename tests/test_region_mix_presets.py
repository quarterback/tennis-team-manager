"""Portable region mixes — download a mix, load it into a future world.

The owner authors ~90 weights precisely and used to retype them for every new
save. The FILE is the durable form: `world_setting` lives in the same tennis.db
as everything else, so a saved mix dies with the save.
"""
import json

import pytest

from app import worldconfig as wc


@pytest.fixture(autouse=True)
def _clean():
    wc.set("region_mixes", "[]")
    wc._cache.pop("region_mixes", None)
    yield
    wc.set("region_mixes", "[]")
    wc._cache.pop("region_mixes", None)


def _mix(**kw):
    base = {"name": "Euro core", "base_band": "global_college", "share": 0.4,
            "weights": {"france": 160, "canada": 40, "west_africa": 60}}
    base.update(kw)
    return wc.region_mix_doc(base["name"], base["base_band"], base["share"],
                             base["weights"])


# --- the document ---------------------------------------------------------------

def test_a_mix_round_trips_through_json_unchanged():
    """The file is the product. Anything that does not survive a dump/load is a
    mix the owner authored and did not get back."""
    doc = _mix()
    back = wc.parse_region_mix(json.loads(json.dumps(doc)))
    assert back["weights"] == doc["weights"]
    assert back["base_band"] == doc["base_band"]
    assert back["intl_share"] == doc["intl_share"]
    assert back["name"] == doc["name"]


def test_weights_are_the_editors_own_integers_not_fractions():
    """A load must show the numbers the owner typed. Normalising to fractions on
    save round-trips the MIX but not the DISPLAY, so 160 comes back as 561."""
    doc = _mix()
    assert doc["weights"]["france"] == 160
    assert doc["weights"]["canada"] == 40


def test_zero_and_domestic_regions_are_omitted():
    """A missing region reads as zero on load, so storing ~60 explicit zeros would
    triple the file for no information. `us` is the US/world split, not a weight."""
    doc = _mix(weights={"france": 160, "japan": 0, "us": 500, "italy": -3})
    assert doc["weights"] == {"france": 160}


def test_a_hidden_region_never_enters_a_mix():
    doc = _mix(weights={"france": 10, "guam": 99})
    assert "guam" not in doc["weights"]


# --- what did not survive the build ---------------------------------------------

def test_a_region_this_build_lacks_is_reported_not_swallowed():
    """Region ids get added and renamed between builds — this build alone split
    Africa into six and promoted a dozen countries out of shared buckets. A mix
    authored against an older build is silently a DIFFERENT mix unless the gaps
    are named."""
    doc = _mix(weights={"france": 160, "not_a_place": 12, "atlantis": 3})
    parsed = wc.parse_region_mix(doc)
    assert parsed["unknown"] == ["atlantis", "not_a_place"]
    assert "not_a_place" not in parsed["weights"]
    assert parsed["weights"]["france"] == 160


def test_regions_absent_from_the_file_are_reported_as_loading_at_zero():
    parsed = wc.parse_region_mix(_mix())
    assert "japan" in parsed["missing"]
    assert "france" not in parsed["missing"]


def test_every_known_region_is_either_weighted_or_missing():
    """The two lists have to cover the editor exactly, or the report understates
    what changed."""
    parsed = wc.parse_region_mix(_mix())
    known = {r["id"] for g in wc.region_groups() for r in g["regions"]
             if not r["is_domestic"]}
    assert set(parsed["weights"]) | set(parsed["missing"]) == known
    assert not (set(parsed["weights"]) & set(parsed["missing"]))


# --- rejecting things that are not a mix ----------------------------------------

@pytest.mark.parametrize("doc", [
    None, [], "hello", {},
    {"format": "something-else", "version": 1, "weights": {}},
    {"format": wc.PRESET_FORMAT, "version": 1},                       # no weights
    {"format": wc.PRESET_FORMAT, "version": 1, "weights": "france"},  # weights not a map
    {"format": wc.PRESET_FORMAT, "version": wc.PRESET_VERSION + 1, "weights": {}},
])
def test_a_file_that_is_not_a_readable_mix_raises(doc):
    with pytest.raises(wc.MixFormatError):
        wc.parse_region_mix(doc)


def test_the_error_says_what_the_file_actually_was():
    with pytest.raises(wc.MixFormatError, match="tennis-save"):
        wc.parse_region_mix({"format": "tennis-save", "version": 1, "weights": {}})


# --- the save-scoped store ------------------------------------------------------

def test_saving_and_reading_back_a_named_mix():
    wc.save_mix(_mix(name="Euro core"))
    names = [m["name"] for m in wc.saved_mixes()]
    assert names == ["Euro core"]
    assert wc.saved_mixes()[0]["weights"]["france"] == 160


def test_saving_the_same_name_replaces_rather_than_duplicates():
    wc.save_mix(_mix(name="Mine", weights={"france": 10}))
    wc.save_mix(_mix(name="mine", weights={"italy": 20}))
    rows = wc.saved_mixes()
    assert len(rows) == 1
    assert rows[0]["weights"] == {"italy": 20}


def test_deleting_a_mix():
    wc.save_mix(_mix(name="A"))
    wc.save_mix(_mix(name="B"))
    wc.delete_mix("a")
    assert [m["name"] for m in wc.saved_mixes()] == ["B"]


def test_a_corrupt_stored_row_is_skipped_not_fatal():
    """The store is JSON in a settings row; a hand-edit or an older build must not
    take the onboarding page down with it."""
    wc.set("region_mixes", json.dumps([{"nope": 1}, _mix(name="Good")]))
    wc._cache.pop("region_mixes", None)
    assert [m["name"] for m in wc.saved_mixes()] == ["Good"]


def test_the_store_is_bounded():
    for i in range(wc.MAX_SAVED_MIXES + 5):
        wc.save_mix(_mix(name=f"mix {i}"))
    assert len(wc.saved_mixes()) == wc.MAX_SAVED_MIXES


def test_saved_rows_do_not_persist_the_derived_report():
    """`unknown`/`missing` are computed against the CURRENT build. Persisting them
    would freeze one build's answer into the store and go stale on the next."""
    wc.save_mix(_mix())
    raw = json.loads(wc.get("region_mixes"))
    assert "unknown" not in raw[0] and "missing" not in raw[0]


# --- the route ------------------------------------------------------------------

def test_the_editor_can_save_and_delete_over_http():
    from app.web.server import create_app
    client = create_app().test_client()

    r = client.post("/world/mix/save", json=_mix(name="Over the wire"))
    assert r.status_code == 200 and r.get_json()["ok"]
    assert [m["name"] for m in r.get_json()["mixes"]] == ["Over the wire"]

    r = client.post("/world/mix/delete", json={"name": "Over the wire"})
    assert r.get_json()["mixes"] == []


def test_a_junk_upload_is_a_400_not_a_500():
    from app.web.server import create_app
    client = create_app().test_client()
    r = client.post("/world/mix/save", json={"format": "nope"})
    assert r.status_code == 400
    assert not r.get_json()["ok"] and r.get_json()["error"]


def test_the_onboarding_page_offers_the_controls():
    from app.web.server import create_app
    wc.save_mix(_mix(name="Shows up"))
    html = create_app().test_client().get("/start").get_data(as_text=True)
    for hook in ("ob-mix-download", "ob-mix-load", "ob-mix-save", "ob-mix-file",
                 "Shows up", wc.PRESET_FORMAT):
        assert hook in html, hook


# --- the complete picker map ----------------------------------------------------
# `region_weights()` omits `us` by contract, so it is an INTERNATIONAL mix and never
# a picker map on its own. Handing it straight to make_name_picker generates a 100%
# international world whatever split the owner chose, and nothing errors.

def test_the_world_map_restores_the_us_share():
    full = wc.full_region_weights()
    assert "us" not in wc.region_weights()
    assert full["us"] == pytest.approx(1.0 - wc.intl_share())


def test_the_international_regions_keep_their_proportions():
    intl = wc.region_weights()
    full = wc.full_region_weights()
    a, b = sorted(intl)[:2]
    assert full[a] / full[b] == pytest.approx(intl[a] / intl[b])
    assert sum(v for k, v in full.items() if k != "us") == pytest.approx(wc.intl_share())


@pytest.mark.parametrize("share", [0.0, 0.3, 0.8, 0.95])
def test_with_domestic_hits_the_requested_share(share):
    out = wc.with_domestic({"france": 3.0, "japan": 1.0}, share)
    assert out["us"] == pytest.approx(1.0 - share)
    assert out["france"] == pytest.approx(0.75 * share)


def test_an_empty_international_mix_is_all_domestic():
    """No international regions configured must mean 100% US, not a divide by zero."""
    assert wc.with_domestic({}, 0.5) == {"us": 1.0}
    assert wc.with_domestic({"france": 0.0}, 0.5)["us"] == 1.0


def test_the_pro_league_generates_at_the_configured_split():
    """The regression this pins: gtt_seasonmode passed region_weights() straight to
    the picker, so every generated pro was international."""
    import collections
    import random
    from app import gtt_seasonmode
    from generators.names import make_name_picker
    pick = make_name_picker(random.Random(5), gender="mixed",
                            region_weights=gtt_seasonmode._world_weights())
    us = sum(1 for _ in range(4000) if pick()[1] == "US") / 4000
    assert us == pytest.approx(1.0 - wc.intl_share(), abs=0.05)


# --- retired region ids ---------------------------------------------------------
# A region id the table no longer has is not an error anywhere: the picker's draw
# returns nothing and simply retries, so the share is silently redistributed.

LEGACY = ["africa", "africa_cricket", "namibia", "cape_verde", "mauritius", "uganda"]


@pytest.mark.parametrize("old", LEGACY)
def test_every_retired_region_migrates_to_regions_this_build_has(old):
    from generators.names import get_name_regions
    known = get_name_regions()
    migrated, moved = wc.migrate_region_weights({old: 100.0})
    assert moved[old]
    assert set(migrated) <= set(known), migrated
    assert sum(migrated.values()) == pytest.approx(100.0)


def test_migration_preserves_total_weight_in_a_mixed_map():
    """A save keeps the share it authored — the fold must not lose or invent any."""
    legacy = {"france": 100, "africa_cricket": 90, "africa": 60, "uganda": 20}
    migrated, moved = wc.migrate_region_weights(legacy)
    assert sum(migrated.values()) == pytest.approx(sum(legacy.values()))
    assert migrated["france"] == 100
    assert set(moved) == {"africa_cricket", "africa", "uganda"}


def test_a_persisted_legacy_mix_is_migrated_on_read():
    wc.set("region_w", json.dumps({"france": 100, "africa_cricket": 90}))
    wc._cache.pop("region_w", None)
    got = wc.region_weights_custom()
    assert "africa_cricket" not in got
    assert got["southern_africa"] == pytest.approx(79.2)
    assert got["east_africa"] == pytest.approx(10.8)
    assert sum(got.values()) == pytest.approx(190.0)


def test_an_unresolvable_region_is_dropped_rather_than_left_undrawable():
    """A weight the picker cannot draw is a hole in the mix, not a weight."""
    wc.set("region_w", json.dumps({"france": 100, "atlantis": 50}))
    wc._cache.pop("region_w", None)
    assert wc.region_weights_custom() == {"france": 100.0}


def test_an_all_legacy_mix_still_generates_real_people():
    """The failure this prevents: every draw resolves to nothing, all 500 retries
    burn, and the picker emits `Player NNN` with an empty country."""
    import random
    wc.set("region_w", json.dumps({"africa_cricket": 90}))
    wc._cache.pop("region_w", None)
    from generators.names import make_name_picker
    pick = make_name_picker(random.Random(2), gender="mixed",
                            region_weights=wc.full_region_weights())
    names = [pick() for _ in range(600)]
    assert not [n for n, _c in names if n.startswith("Player ")]
    assert not [c for _n, c in names if not c]
    assert {c for _n, c in names} >= {"ZA", "US"}


def test_a_mix_file_from_an_older_build_migrates_rather_than_losing_africa():
    parsed = wc.parse_region_mix({
        "format": wc.PRESET_FORMAT, "version": 1, "name": "Old", "base_band": "global_college",
        "intl_share": 0.4, "weights": {"france": 100, "africa_cricket": 90}})
    assert parsed["unknown"] == []
    assert parsed["migrated"] == {"africa_cricket": "southern_africa, east_africa"}
    assert parsed["weights"]["southern_africa"] == pytest.approx(79.2)
