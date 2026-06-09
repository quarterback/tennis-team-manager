"""Shared test fixtures."""
import pytest

from app import worldconfig as wc


@pytest.fixture(autouse=True, scope="session")
def _fast_junior_season():
    """Pin a short junior season for the whole suite so the (otherwise 36-week)
    circuit builds stay cheap. Production default is unaffected; restored after."""
    prev = wc.get("jr_season_weeks")
    wc.set("jr_season_weeks", "10")
    yield
    wc.set("jr_season_weeks", prev)
