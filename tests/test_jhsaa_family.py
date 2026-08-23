"""Family ties — the owner-authored metadata linking two pids.

Two faults, both reported from the page rather than caught here, because nothing
covered this feature at all:

  * the relation read BACKWARDS. `_relation_from` correctly derived seniority from
    entry years (an earlier entry year is the older player), and the template then
    wrapped it in "older sibling of Jane" — a sentence whose subject is the OTHER
    end of the tie, so the label described the wrong person. Seniority is gone
    entirely now (owner rule) and the relation is rendered as a label ON the member
    it describes, which has no perspective left to invert.
  * a family could not grow past TWO. `family_add` has always joined a third member
    to an existing family; the player page hid the picker the moment a tie existed,
    so three siblings could only be associated by starting from the untied one.
  * and the relation was stored ONCE ON THE HOUSEHOLD, so a family begun as cousins
    made every later member a cousin of everyone — "it doesn't let you connect
    siblings if the cousin relationship was started". A relation is a fact about two
    people; it now lives on the LINK.
"""
import pytest

from app import jhsaa as jh


# --- what a member IS, from the other end ------------------------------------------

def _m(pid, entry):
    return {"pid": pid, "name": pid.title(), "school": "Somewhere", "entry": entry}


def _fam(relation, *pairs):
    """A family whose stated ties are exactly `pairs`."""
    return {"relation": relation,
            "links": [{"a": a, "b": b, "relation": relation} for a, b in pairs]}


@pytest.mark.parametrize("mine,theirs", [(2030, 2027), (2027, 2030), (2029, 2029)])
def test_a_sibling_is_just_a_sibling(mine, theirs):
    """‼️ NO older/younger/twin (owner rule 2026-08): "it says younger when it means
    older and vice versa … it can just say sibling". The derivation was right and the
    sentence around it inverted the meaning, so the words are gone rather than
    re-pointed — seniority is not worth a label whose truth depends on which page you
    are standing on. Whichever way round the entry years fall, the answer is one word.
    """
    fam = _fam("sibling", ("me", "them"))
    assert jh._relation_from(fam, _m("me", mine), _m("them", theirs)) == "sibling"


def test_a_cousin_is_never_given_a_direction():
    fam = _fam("cousin", ("me", "them"))
    assert jh._relation_from(fam, _m("me", 2030), _m("them", 2027)) == "cousin"


def test_a_parent_keeps_its_direction():
    """The one asymmetry that survives, because it IS the content of the tie: the
    earlier cohort is the parent. Rendered as a label on that member ("Jane Doe ·
    parent"), never as an "X of Y" sentence — the shape that inverted the siblings."""
    fam = _fam("parent", ("mum", "kid"))
    older, younger = _m("mum", 2004), _m("kid", 2030)
    assert jh._relation_from(fam, younger, older) == "parent"
    assert jh._relation_from(fam, older, younger) == "child"


def test_a_missing_entry_year_falls_back_to_the_plain_relation():
    """A member need not be enrolled — a parent from twenty seasons back may carry no
    entry year at all — and a tie has to render anyway rather than raising."""
    fam = _fam("parent", ("me", "x"))
    assert jh._relation_from(fam, _m("me", 2030), {"pid": "x"}) == "parent"
    assert jh._relation_from(fam, None, _m("them", 2027)) == ""


def test_a_relation_is_claimed_only_where_one_was_stated():
    """‼️ A SIBLING'S COUSIN IS NOT YOUR COUSIN. With one relation per household the
    page asserted a word for every pair; only the pairs the owner actually named have
    one, and the rest are family and nothing more."""
    fam = _fam("sibling", ("a", "b"))
    assert jh._relation_from(fam, _m("a", 2030), _m("c", 2030)) == ""


def test_a_family_written_before_links_still_reads():
    """Legacy rows carry `relation` and no `links` — which is exactly the complete
    graph at that relation, since that is what they displayed. Derived on read, never
    migrated."""
    legacy = {"relation": "cousin",
              "members": [{"pid": "a"}, {"pid": "b"}, {"pid": "c"}]}
    links = jh.family_links(legacy)
    assert len(links) == 3                       # every pair
    assert all(l["relation"] == "cousin" for l in links)
    assert jh._relation_from(legacy, _m("a", 2030), _m("c", 2029)) == "cousin"


# --- a family is not a pair --------------------------------------------------------

@pytest.fixture
def three_siblings(monkeypatch):
    """Three resolvable players, without building a single roster: `family_add`'s
    only use for the world is `_resolve_member`, and what this exercises is the
    JOIN."""
    from app import overrides as ov
    people = {"pid-a": _m("pid-a", 2029), "pid-b": _m("pid-b", 2030),
              "pid-c": _m("pid-c", 2031)}
    for p, rec in people.items():
        rec["gender"] = "girls"
    monkeypatch.setattr(jh, "_resolve_member",
                        lambda pid, **kw: dict(people[pid]) if pid in people else None)
    for fid in list(ov.get_jhsaa_families()):
        jh.family_remove(fid)
    jh._family_cache.clear()
    yield people
    for fid in list(ov.get_jhsaa_families()):
        jh.family_remove(fid)
    jh._family_cache.clear()


def test_a_third_member_joins_the_family_that_already_exists(three_siblings):
    """‼️ THE MODEL WAS ALWAYS N-ARY; the PAGE was the limit. Tying A-B then B-C must
    leave ONE family of three, not two families of two — otherwise `families()` maps a
    pid to whichever family it met last and the third sibling silently splits the
    household in half."""
    first = jh.family_add("pid-a", "pid-b", "sibling")
    assert first["ok"], first
    joined = jh.family_add("pid-b", "pid-c", "sibling")
    assert joined["ok"], joined
    assert joined["family_id"] == first["family_id"]
    fam = jh.family_for("pid-c")
    assert fam and fam["family_id"] == first["family_id"]
    assert {m["pid"] for m in fam["members"]} == {"pid-a", "pid-b", "pid-c"}
    # B was tied to both, so B states two relations; A and C were never tied to each
    # other, so each states one and sees the third as household. That asymmetry is
    # the model working — the old one asserted "sibling" for a pair nobody named.
    b = jh.family_for("pid-b")
    assert {o["pid"] for o in b["others"]} == {"pid-a", "pid-c"}
    assert all(o["relation"] == "sibling" for o in b["others"])
    a = jh.family_for("pid-a")
    assert [o["pid"] for o in a["others"]] == ["pid-b"]
    assert [o["pid"] for o in a["kin"]] == ["pid-c"]


def test_a_cousin_household_can_still_take_a_pair_of_siblings(three_siblings):
    """‼️ THE REPORTED FAULT. The relation was stored on the FAMILY, so once a
    household was begun as cousins every later tie was a cousin tie — "it doesn't let
    you connect siblings if the cousin relationship was started". A real family holds
    both at once."""
    jh.family_add("pid-a", "pid-b", "cousin")
    joined = jh.family_add("pid-b", "pid-c", "sibling")
    assert joined["ok"], joined
    rel = {o["pid"]: o["relation"] for o in jh.family_for("pid-b")["others"]}
    assert rel == {"pid-a": "cousin", "pid-c": "sibling"}


def test_a_second_tie_inside_one_family_is_recorded(three_siblings):
    """‼️ "THERE'S NO WAY TO ASSOCIATE SOMEONE MORE THAN ONCE." Two people already in
    the same household used to be refused outright, so the tie between them could
    never be stated — even though it is a different fact from the ones already there.
    """
    jh.family_add("pid-a", "pid-b", "sibling")
    jh.family_add("pid-b", "pid-c", "sibling")
    assert jh.family_for("pid-a")["kin"], "c should start as household-only"
    again = jh.family_add("pid-a", "pid-c", "cousin")
    assert again["ok"], again
    rel = {o["pid"]: o["relation"] for o in jh.family_for("pid-a")["others"]}
    assert rel == {"pid-b": "sibling", "pid-c": "cousin"}
    assert not jh.family_for("pid-a")["kin"]
    # and no member is added twice by stating a tie between two who are already in
    assert len(jh.family_for("pid-a")["members"]) == 3


def test_the_same_pair_is_not_tied_twice(three_siblings):
    jh.family_add("pid-a", "pid-b", "sibling")
    dup = jh.family_add("pid-a", "pid-b", "cousin")
    assert not dup["ok"] and "already tied" in dup["msg"]
    assert len(jh.family_for("pid-a")["links"]) == 1


def test_joining_from_the_new_members_own_page_works_the_same_way(three_siblings):
    """The argument order is whichever page you started from, so it cannot matter."""
    first = jh.family_add("pid-a", "pid-b", "sibling")
    joined = jh.family_add("pid-c", "pid-a", "sibling")
    assert joined["ok"] and joined["family_id"] == first["family_id"]
    assert len(jh.family_for("pid-a")["members"]) == 3


def test_two_households_discovered_to_be_one_are_merged(three_siblings, monkeypatch):
    """Two people who each already have a family used to be refused, which left the
    owner with no way to state a tie they had just decided on. Discovering one is a
    MERGE — and a pid must still resolve to exactly ONE family afterwards, or
    `families()` picks whichever row it met last and half the household vanishes."""
    from app import overrides as ov
    people = three_siblings
    people["pid-d"] = {**_m("pid-d", 2028), "gender": "girls"}
    monkeypatch.setattr(jh, "_resolve_member",
                        lambda pid, **kw: dict(people[pid]) if pid in people else None)
    one = jh.family_add("pid-a", "pid-b", "sibling")
    two = jh.family_add("pid-c", "pid-d", "sibling")
    assert one["family_id"] != two["family_id"]
    merged = jh.family_add("pid-b", "pid-c", "cousin")
    assert merged["ok"], merged
    ids = {jh.family_for(p)["family_id"] for p in ("pid-a", "pid-b", "pid-c", "pid-d")}
    assert len(ids) == 1, ids
    assert len(ov.get_jhsaa_families()) == 1        # the absorbed row is gone
    assert len(jh.family_for("pid-a")["members"]) == 4
    # every stated tie survives the merge, including the one that caused it
    rel = {frozenset((l["a"], l["b"])): l["relation"]
           for l in jh.family_for("pid-a")["links"]}
    assert rel == {frozenset(("pid-a", "pid-b")): "sibling",
                   frozenset(("pid-c", "pid-d")): "sibling",
                   frozenset(("pid-b", "pid-c")): "cousin"}


def test_removing_a_member_takes_their_ties_with_them(three_siblings):
    """A link naming a pid that is no longer a member is a tie to nobody — and a
    re-added member would silently inherit the old relation."""
    jh.family_add("pid-a", "pid-b", "sibling")
    jh.family_add("pid-b", "pid-c", "cousin")
    fid = jh.family_for("pid-a")["family_id"]
    assert jh.family_remove(fid, "pid-c")["ok"]
    links = jh.family_for("pid-a")["links"]
    assert all("pid-c" not in (l["a"], l["b"]) for l in links), links


def test_an_empty_link_list_is_explicit_not_legacy():
    """‼️ THE LEGACY TEST IS AN ABSENT KEY, NEVER AN EMPTY LIST. A new-format family
    can hold no stated ties at all — remove the middle of A-B-C and the two left were
    never tied to each other — and a truthiness check read that as a legacy row,
    synthesised a tie nobody stated, and then refused the real one as a duplicate."""
    fam = {"relation": "cousin", "links": [],
           "members": [{"pid": "a"}, {"pid": "b"}]}
    assert jh.family_links(fam) == []
    assert jh._relation_from(fam, _m("a", 2030), _m("b", 2029)) == ""


def test_removing_a_bridge_splits_the_family(three_siblings, monkeypatch):
    """‼️ A FAMILY IS A CONNECTED COMPONENT, so removing a BRIDGE splits it. With
    A-B, B-C, C-D and B gone, only C-D still holds anything together — but the row
    kept all three, so A went on being presented as D's family and shared a family id
    with them, which is the only thing the doubles nudge ever looked at."""
    from app import overrides as ov
    people = three_siblings
    people["pid-d"] = {**_m("pid-d", 2028), "gender": "girls"}
    monkeypatch.setattr(jh, "_resolve_member",
                        lambda pid, **kw: dict(people[pid]) if pid in people else None)
    jh.family_add("pid-a", "pid-b", "sibling")
    jh.family_add("pid-b", "pid-c", "cousin")
    jh.family_add("pid-c", "pid-d", "sibling")
    fid = jh.family_for("pid-a")["family_id"]
    assert jh.family_remove(fid, "pid-b")["ok"]
    # A had only the one tie, through B: they are out, not a household of one.
    assert jh.family_for("pid-a") is None
    # C-D survive as their own family, and nobody else is in it.
    cd = jh.family_for("pid-c")
    assert {m["pid"] for m in cd["members"]} == {"pid-c", "pid-d"}
    assert jh.family_for("pid-d")["family_id"] == cd["family_id"]
    assert len(ov.get_jhsaa_families()) == 1


def test_two_surviving_components_each_become_a_family(three_siblings, monkeypatch):
    """A bridge between two real pairs leaves TWO families, not one row holding four
    people who are no longer all related."""
    from app import overrides as ov
    people = three_siblings
    for extra, entry in (("pid-d", 2028), ("pid-e", 2027)):
        people[extra] = {**_m(extra, entry), "gender": "girls"}
    monkeypatch.setattr(jh, "_resolve_member",
                        lambda pid, **kw: dict(people[pid]) if pid in people else None)
    jh.family_add("pid-a", "pid-b", "sibling")     # A-B
    jh.family_add("pid-b", "pid-c", "cousin")      # bridge
    jh.family_add("pid-c", "pid-d", "sibling")     # C-D
    jh.family_add("pid-d", "pid-e", "sibling")     # C-D-E
    fid = jh.family_for("pid-a")["family_id"]
    jh.family_remove(fid, "pid-c")                 # drop the OTHER end of the bridge
    assert len(ov.get_jhsaa_families()) == 2
    assert {m["pid"] for m in jh.family_for("pid-a")["members"]} == {"pid-a", "pid-b"}
    assert {m["pid"] for m in jh.family_for("pid-d")["members"]} == {"pid-d", "pid-e"}
    assert jh.family_for("pid-a")["family_id"] != jh.family_for("pid-d")["family_id"]


def test_a_severed_pair_can_then_be_tied_for_real(three_siblings):
    """The empty-list bug's real cost: after a split the survivors could not be tied,
    because the synthesised legacy tie made the genuine one look like a duplicate."""
    jh.family_add("pid-a", "pid-b", "sibling")
    jh.family_add("pid-b", "pid-c", "sibling")
    fid = jh.family_for("pid-a")["family_id"]
    jh.family_remove(fid, "pid-b")
    assert jh.family_for("pid-a") is None and jh.family_for("pid-c") is None
    again = jh.family_add("pid-a", "pid-c", "sibling")
    assert again["ok"], again


# --- the doubles nudge is SIBLINGS ONLY --------------------------------------------

def test_only_siblings_draw_the_doubles_bonus(three_siblings):
    """‼️ Owner rule 2026-08: "only siblings get the bonus NOT family connections at
    all". It asked whether two pids shared a family ID, so cousins — and anyone merely
    reachable through a third member's tie — partnered with a thumb on the scale."""
    jh.family_add("pid-a", "pid-b", "sibling")
    jh.family_add("pid-b", "pid-c", "cousin")
    m = jh.families()
    assert jh._family_pairs("pid-a", "pid-b", m)          # stated siblings
    assert not jh._family_pairs("pid-b", "pid-c", m)      # stated cousins
    assert not jh._family_pairs("pid-a", "pid-c", m)      # same household, no tie


def test_a_legacy_sibling_family_still_draws_it(three_siblings):
    """A row written before links carries one relation for every pair, which is what
    it always meant — so a legacy SIBLING family keeps its nudge and a legacy cousin
    family never had one to lose."""
    from app import overrides as ov
    ov.set_jhsaa_family("legacy-sib", {"label": "L", "relation": "sibling",
                                       "members": [{"pid": "x"}, {"pid": "y"}]})
    ov.set_jhsaa_family("legacy-cuz", {"label": "M", "relation": "cousin",
                                       "members": [{"pid": "p"}, {"pid": "q"}]})
    jh._family_cache.clear()
    m = jh.families()
    assert jh._family_pairs("x", "y", m)
    assert not jh._family_pairs("p", "q", m)
