"""The style-matchup cross term (owner rule 2026-09,
docs/AAR-style-matchup-cross-term.md).

`play_style` used to be a label the engine never read as a matchup: the
attribute-shape lanes are linear, so at equal overall every style-vs-style
cell sat at 47-52%. `engine.fast.style_edge` is an antisymmetric cross term on
a 2-D style plane derived from a player's attribute clusters, so styles now
beat each other in a cycle — and it fades with the overall gap, so it decides
near-equal matches and never overrides a rating.
"""
import importlib.util
import math
import random
from pathlib import Path

import pytest

from app import development as dev, jhsaa, worldconfig
from app.player_attributes import PlayerAttributes, RICH_ATTRS
from engine import fast
from engine.match import simulate_match
from engine.state import random_player

_spec = importlib.util.spec_from_file_location(
    "style_calib", Path(__file__).resolve().parent.parent / "scripts" / "style_matchup_calibration.py")
calib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(calib)


def test_engine_clusters_mirror_the_generator_clusters():
    """The engine cannot import app/, so the cluster table is repeated; the
    plane is fitted on the generator's shifts, so the two must agree."""
    assert fast.STYLE_CLUSTERS == dev._STYLE_CLUSTERS
    assert set(fast.STYLE_AXIS_X) == set(fast.STYLE_AXIS_Y) == set(fast.STYLE_CLUSTERS)
    assert set(dev._STYLE_BIAS) < set(dev._STYLE_BIAS_V2)
    assert set(dev.STYLE_DRAW_V2) == set(dev._STYLE_BIAS_V2)
    assert set(dev.STYLES_V1) == set(dev._STYLE_BIAS)


def test_synthetic_players_sit_at_the_origin_and_play_untouched():
    """random_player carries no rich table: no vector, no edge — every
    pre-existing engine test and calibration is byte-identical."""
    rng = random.Random(3)
    a, b = random_player(rng, "A"), random_player(rng, "B")
    assert fast.style_vector(a) == (0.0, 0.0)
    on = [simulate_match(a, b, seed=s, fidelity="fast").set_scores for s in range(20)]
    off = [simulate_match(a, b, seed=s, fidelity="fast", profile={"style_k": 0.0}).set_scores
           for s in range(20)]
    assert on == off


def test_edge_is_antisymmetric_and_fades_with_the_rating_gap():
    e = fast.style_edge(0.1, 0.02, -0.05, 0.08, 0.0)
    assert e != 0.0
    assert fast.style_edge(-0.05, 0.08, 0.1, 0.02, 0.0) == pytest.approx(-e)
    # same players, growing overall gap: linear fade to zero at style_fade
    half = fast.style_edge(0.1, 0.02, -0.05, 0.08, fast.TUNE["style_fade"] / 2)
    assert half == pytest.approx(e / 2)
    assert fast.style_edge(0.1, 0.02, -0.05, 0.08, fast.TUNE["style_fade"]) == 0.0
    assert fast.style_edge(0.1, 0.02, -0.05, 0.08, -0.5) == 0.0
    # a flat player has no edge against anybody
    assert fast.style_edge(0.0, 0.0, 0.3, -0.2, 0.0) == 0.0


def test_v2_profile_preserves_the_overall_grade():
    """Bigger shifts do not make a style stronger: weight-normalised, the
    overall grade is unchanged to the clamp for every style."""
    for style in dev._STYLE_BIAS_V2:
        rng = random.Random(11)
        pot = {a: 50.0 + rng.gauss(0, 3) for a in RICH_ATTRS}
        before = PlayerAttributes(pot).overall_grade()
        dev._apply_style_profile(pot, style, random.Random(5), dev._STYLE_BIAS_V2)
        assert PlayerAttributes(pot).overall_grade() == pytest.approx(before, abs=0.02), style


def test_generated_styles_land_at_their_angles():
    """Mean vector per style points where the tournament needs it (within a
    quarter turn — per-attribute noise and the net-specialist roll scatter
    individuals, the LABEL's mean is what the fit places)."""
    pl = calib.pool(80)
    for style, target in calib.ANGLES.items():
        xs, ys = zip(*(fast.style_vector(p.engine_player()) for p in pl[style]))
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        ang = math.degrees(math.atan2(my, mx)) % 360
        diff = min(abs(ang - target), 360 - abs(ang - target))
        assert diff < 45, (style, ang, target)
        assert math.hypot(mx, my) > 0.05, style
    bx, by = zip(*(fast.style_vector(p.engine_player()) for p in pl["balanced"]))
    assert math.hypot(sum(bx) / len(bx), sum(by) / len(by)) < 0.06


@pytest.mark.parametrize("profile,fidelity", [(None, "fast"), (fast.HS_PROFILE, "fast"), (None, "full")],
                         ids=["college-fast", "hs-fast", "college-full"])
def test_the_agreed_tournament_emerges_at_equal_overall(profile, fidelity):
    """Every agreed edge clears the noise floor at equal overall, in the fast
    model under both profiles AND in the point engine the college season
    actually runs; same-style and balanced cells stay near even. ~600 matches
    a cell (CI ~±4): the strong edges are calibrated to ~58-60, the two
    added styles' edges vary with their angle, so the floor is 51."""
    pl = calib.pool(150)
    cells = calib.matrix(pl, profile, seeds=2, fidelity=fidelity)
    # The point engine prices shapes unevenly ON PURPOSE (owner rule: style
    # imbalances are realistic), so there only the owner's four cardinal edges
    # are pinned; the fast model is even enough to pin every agreed edge.
    edges = calib.CARDINAL if fidelity == "full" else calib.TOURNAMENT
    for w, l in edges:
        assert cells[(w, l)][0] >= 0.51, (w, l, cells[(w, l)])
        assert cells[(l, w)][0] <= 0.49, (l, w, cells[(l, w)])
    assert sum(cells[c][0] for c in calib.CARDINAL) / len(calib.CARDINAL) >= 0.54
    # Neutral cells: a balanced player is near the origin on AVERAGE but
    # individuals scatter, and rank-pairing correlates who meets whom, so a
    # single 600-match cell can sit 5-9 points off even (measured 54 at 1,800).
    # These bound the neutral cells loosely; the agreed edges above are the pin.
    if fidelity == "full":
        return          # the point engine's neutral cells carry the accepted imbalance
    for s in calib.STYLES:
        assert 0.42 <= cells[(s, s)][0] <= 0.58, (s, cells[(s, s)])
        assert 0.40 <= cells[("balanced", s)][0] <= 0.60, (s, cells[("balanced", s)])


def test_the_point_engine_shares_the_fade():
    """rally.py mirrors fast.TUNE's fade rather than importing it (the import
    would be circular); the two must agree or the edge fades at different
    gaps in the two fidelities."""
    from engine import rally
    assert rally._STYLE_FADE == fast.TUNE["style_fade"]


def test_doubles_reads_the_same_plane():
    """A counterpunching pair troubles a pair of baseliners at equal pair
    rating, and the reverse cell is its complement."""
    pl = calib.pool(150)
    cells = calib.doubles_matrix(pl, None, seeds=2)
    assert cells[("counterpuncher", "aggressive_baseliner")][0] >= 0.53
    assert cells[("aggressive_baseliner", "counterpuncher")][0] <= 0.47
    # (no on/off scoreline check: the fade zeroes the term for a pair-rating
    # gap over 0.15, which two hand-picked pairs can easily sit outside — the
    # rank-paired matrix above is the proof the doubles model reads it.)


# --- the JHSAA era gate ---------------------------------------------------------

@pytest.fixture
def _fresh_style_era():
    yield
    worldconfig.set("jhsaa_style_era", "")
    jhsaa.reset_schools()


def test_style_era_is_in_the_reset_list():
    assert "jhsaa_style_era" in jhsaa.ERA_SETTINGS


def test_pre_era_cohorts_keep_the_v1_shape_byte_for_byte(_fresh_style_era):
    """Era past everyone: every player is a flat-drawn v1 style with no
    trait; era at zero: the v2 draw (traits present) and different attributes;
    era mid-roster: the cohorts before it are byte-identical to the all-legacy
    build (the dev_era test's shape) and overall never moves either way."""
    s = jhsaa.load_schools("boys")[0]
    worldconfig.set("jhsaa_style_era", "9999")
    jhsaa.reset_schools()
    legacy_roster = jhsaa.build_roster(s, 2035)
    legacy = {p.pid: dict(p.current) for p in legacy_roster}
    assert {p.traits.get("style_trait", "none") for p in legacy_roster} == {"none"}
    assert {p.traits["play_style"] for p in legacy_roster} <= set(dev.STYLES_V1)
    worldconfig.set("jhsaa_style_era", "0")
    jhsaa.reset_schools()
    new_roster = jhsaa.build_roster(s, 2035)
    new = {p.pid: dict(p.current) for p in new_roster}
    assert set(new) == set(legacy)
    assert any(cur != legacy[pid] for pid, cur in new.items()), "gate never opened"
    # the v2 style/trait come off a substream, so base ability is the same draw
    # either side of the era and overall moves only by the shape clamp
    assert any(p.traits.get("style_trait", "none") != "none" for p in new_roster)
    for pid, cur in new.items():
        a = PlayerAttributes(cur).overall_grade()
        b = PlayerAttributes(legacy[pid]).overall_grade()
        assert abs(a - b) < 0.35, pid
    worldconfig.set("jhsaa_style_era", "2034")
    jhsaa.reset_schools()
    mixed = {p.pid: (dict(p.current), p.entry_year, p.traits.get("style_trait", "none"))
             for p in jhsaa.build_roster(s, 2035)}
    for pid, (cur, entry, trait) in mixed.items():
        if entry < 2034:
            assert cur == legacy[pid], "pre-era cohort re-shaped"
            assert trait == "none"


# --- compositional styles: secondary traits and engine tendencies -------------

def _forced(i, style, trait, talent=50.0):
    p = dev.generate_prospect(random.Random(i), f"p{i}", "US", talent=talent,
                              maturity_range=(0.85, 0.85))
    p.traits["play_style"] = style
    p.traits["style_trait"] = trait
    return p


def test_traits_are_drawn_weighted_in_v2_and_absent_in_v1():
    from collections import Counter
    v2 = Counter(dev.generate_prospect(random.Random(i), "x", "US", talent=50).traits["style_trait"]
                 for i in range(600))
    assert set(v2) <= set(dev.TRAIT_DRAW_V2) and len(v2) >= 8
    assert 0.30 <= v2["none"] / 600 <= 0.50
    v1 = {dev.generate_prospect(random.Random(i), "x", "US", talent=50, shape="v1").traits["style_trait"]
          for i in range(100)}
    assert v1 == {"none"}
    styles_v1 = {dev.generate_prospect(random.Random(i), "x", "US", talent=50, shape="v1").traits["play_style"]
                 for i in range(200)}
    assert styles_v1 <= set(dev.STYLES_V1)


def test_every_tendency_the_generator_emits_is_one_the_engine_reads():
    from engine import rally
    for tbl in (dev._STYLE_TENDENCY, dev._TRAIT_TENDENCY):
        for key, tend in tbl.items():
            assert set(tend) <= set(rally.TENDENCY_KEYS), key
    assert set(dev._TRAIT_BIAS) == set(dev.TRAIT_DRAW_V2) == set(dev._TRAIT_TENDENCY)
    assert set(dev._STYLE_TENDENCY) == set(dev._STYLE_BIAS_V2)
    p = _forced(1, "aggressive_baseliner", "net_rusher").engine_player()
    assert p.tend["strike"] > 0 and p.tend["approach"] > 0
    legacy = dev.generate_prospect(random.Random(1), "x", "US", talent=50, shape="v1")
    assert legacy.traits["style_v"] == "v1" and legacy.engine_player().tend is None
    assert random_player(random.Random(1), "s").tend is None


def test_traits_change_behaviour_not_just_labels():
    """A net rusher comes in more, a first-striker ends points on winners and
    errors more, a grinder less — measured through the shipped point engine
    against the same balanced opponents."""
    base = [_forced(i, "balanced", "none") for i in range(40)]

    def profile(trait, style="balanced"):
        net = pts = win = ue = 0
        for i in range(40):
            x = _forced(500 + i, style, trait).engine_player()
            for j in (0, 1):
                r = simulate_match(x, base[(i + j) % 40].engine_player(), seed=i * 3 + j)
                s = r.stats[0]
                net += s.net_points; pts += s.serve_points_total + s.return_points_total
                win += s.winners; ue += s.unforced_errors
        return net / pts, win / pts, ue / pts

    none = profile("none")
    rusher = profile("net_rusher")
    striker = profile("first_strike")
    grinder = profile("grinder")
    sv = profile("none", "serve_and_volley")
    assert rusher[0] > none[0] * 1.4, (rusher, none)
    assert sv[0] > none[0] * 1.3, (sv, none)
    assert striker[1] > none[1] and striker[2] > none[2], (striker, none)
    assert grinder[1] < none[1] and grinder[2] < none[2], (grinder, none)


def test_return_specialist_troubles_a_big_server_at_equal_grade():
    rs = [_forced(2000 + i, "balanced", "return_specialist").engine_player() for i in range(40)]
    bs = [_forced(3000 + i, "balanced", "big_server").engine_player() for i in range(40)]
    w = m = 0
    for i in range(40):
        for j in range(2):
            r = simulate_match(rs[i], bs[(i + j) % 40], seed=i * 7 + j); w += r.winner == 0; m += 1
            r = simulate_match(bs[(i + j) % 40], rs[i], seed=i * 7 + j + 99); w += r.winner == 1; m += 1
    assert w / m >= 0.52, w / m


def test_the_export_names_the_trait_column():
    import inspect
    from app import research_export
    src = inspect.getsource(research_export)
    assert '"style_trait": p.traits.get("style_trait", "none")' in src
    assert "Secondary tactical trait" in src
