"""Shared test fixtures."""
import pytest

from app import worldconfig as wc
from app import injuries


@pytest.fixture(autouse=True)
def _injuries_off():
    """Injuries are the one deliberately non-deterministic system (real entropy),
    which would break the suite's determinism/replay assertions. Disable them by
    default for every test; the injury tests opt back in (seeded). Production is
    unaffected — the module ships enabled."""
    injuries.set_enabled(False)
    yield
    injuries.set_enabled(True)


@pytest.fixture(autouse=True, scope="session")
def _fast_junior_season():
    """Pin a short junior season for the whole suite so the (otherwise 36-week)
    circuit builds stay cheap. Production default is unaffected; restored after."""
    prev = wc.get("jr_season_weeks")
    wc.set("jr_season_weeks", "10")
    yield
    wc.set("jr_season_weeks", prev)


@pytest.fixture(autouse=True, scope="session")
def _sixteen_state_pilot_off():
    """Keep every suite on the association's standing postseason unless it opts
    into the 16-team State pilot (JHSAA rule 2099).

    `jhsaa.sixteen_state_era()` self-configures like every era: a database with no
    archived season resolves it to 0, i.e. the pilot from the first season — which
    is right for a fresh save and wrong for this suite, whose ladder, TOC, awards
    and committee tests all assert the full 4A/3A/2A/1A/Group 3 ladder on a
    season-2027 fixture. The resolver is REPLACED rather than pinned in
    worldconfig because `world.reset()` (the `played_season` fixture) clears every
    era setting mid-run. `tests/test_jhsaa_sixteen_state.py` opts in by swapping
    it back, and tests the real resolver directly."""
    from app import jhsaa as jh
    real = jh.sixteen_state_era
    jh.sixteen_state_era = lambda: 10 ** 6
    yield
    jh.sixteen_state_era = real


@pytest.fixture
def legacy_talent_draw():
    """Pin the CLASSIFICATION talent draw (pre-`jhsaa.band_era()` cohorts) for a
    test that describes that model. From the program-tier change (owner rule
    2026-09) a fresh save draws every cohort from its school's tier and the
    class sets roster size only — but cohorts entering before the era still
    generate on `_TALENT`, so its shape is still worth pinning; this makes the
    test measure that path rather than the tiered one."""
    from app import jhsaa
    prev = wc.get("jhsaa_band_era")
    wc.set("jhsaa_band_era", "9999")
    jhsaa.reset_schools()
    yield
    wc.set("jhsaa_band_era", prev if prev is not None else "")
    jhsaa.reset_schools()
