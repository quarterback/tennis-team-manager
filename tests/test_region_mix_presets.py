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
    doc = _mix(weights={"france": 160, "africa_cricket": 90, "not_a_place": 12})
    parsed = wc.parse_region_mix(doc)
    assert parsed["unknown"] == ["africa_cricket", "not_a_place"]
    assert "africa_cricket" not in parsed["weights"]
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
