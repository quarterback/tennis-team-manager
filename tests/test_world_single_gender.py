"""Single-gender (e.g. women-only) saves must not be dragged backward by the
dormant universes. The men's seasons in a women-only save stay frozen at week 1
in 'regular'; the World Hub's phase/stage/completion must be computed over the
ACTIVE universes only, or the stepper sticks on "Regular season" forever and the
world never reaches Awards/Offseason."""
import pytest

import app.world as world
import app.worldconfig as wc
from app.web.server import create_app
from app.web.state import world_hub


@pytest.fixture
def women_only_world():
    create_app()                       # bootstrap schemas
    if world.exists():
        world.reset()
    wc.set_active(["D1", "D2", "D3"], ["women"])
    try:
        world.get_or_create()
        yield
    finally:
        wc.set_active(["D1", "D2", "D3"], ["men", "women"])   # restore default
        if world.exists():
            world.reset()


def test_world_hub_only_counts_active_universes(women_only_world):
    hub = world_hub()
    genders = {d["u"].split("-")[-1] for d in hub["divisions"]}
    assert hub["divisions"], "expected the active women's divisions"
    assert genders == {"women"}, f"dormant men leaked into the world hub: {genders}"
    # With only week-1 women active, the stage is a real season phase — never pinned
    # by a dormant universe — and completion is driven by the active side only.
    assert hub["stage"] in {"regular", "conf_tournaments", "selection", "ncaa", "awards", "offseason"}
    assert hub["complete"] is False
