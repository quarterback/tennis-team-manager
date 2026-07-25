"""A new save must not inherit the PRIOR save's off-season / cross-system state.

Two stores used to survive `world.reset()` (the "Start new league" action) and
resurface under the fresh save with stale players:

  * `world_cups` — the Davis Cup / BJK Cup snapshots, keyed by `world_id`. The
    `world` table's id is a plain INTEGER PRIMARY KEY, so SQLite REUSES id=1 after
    the reset drops the world row and get_or_create re-inserts it — the leftover
    cup rows then match the new world_id.
  * GTT pro leagues — the pro tour, which binds to the active world's SEED (always
    2026). `world.reset()` never touched the gtt_* tables at all.

Regression for the owner report: "davis cup / bjk cup and pro games do not
naturally restart on a new save — they just have stale players."
"""
from app import world
import app.gtt_seasonmode as gs
from app.web.server import create_app


def _seed_prior_save():
    """Leave the DB as a completed prior save would: one world row, a stored cup
    for it, and a GTT pro league bound to its seed."""
    conn = world._db()
    wid = conn.execute("INSERT INTO world (seed, year, week, salt) VALUES (?,0,0,?)",
                       (world.DEFAULT_SEED, "prior")).lastrowid
    conn.execute("INSERT INTO world_cups VALUES (?,?,?,?)",
                 (wid, 0, "men", '{"event": "Davis Cup", "champion": null}'))
    conn.commit()
    conn.close()
    gs.create_league("Prior Tour", n_teams=4)         # binds to the world seed
    return wid


def test_new_save_clears_cups_and_pro_leagues():
    create_app()                                       # ensure every schema exists
    world.reset()                                      # clean slate to start from
    try:
        old_wid = _seed_prior_save()
        # Pre-reset: both stores are populated and readable.
        assert world.latest_world_cup(world.DEFAULT_SEED, "men") is not None
        assert gs.list_leagues(), "prior GTT league should exist before the reset"

        # The new-save action.
        world.reset()

        # The cup and the pro leagues are gone.
        assert gs.list_leagues() == []
        conn = world._db()
        assert conn.execute("SELECT COUNT(*) c FROM world_cups").fetchone()["c"] == 0
        conn.close()

        # And the crux: a fresh world REUSES the same rowid, yet finds no stale
        # cup under it (the bug was latest_world_cup serving the prior squad here).
        # Insert the world row directly rather than get_or_create() so the test
        # stays light — the heavy year-0 roster build isn't what's under test.
        conn = world._db()
        new_wid = conn.execute("INSERT INTO world (seed, year, week, salt) VALUES (?,0,0,?)",
                               (world.DEFAULT_SEED, "fresh")).lastrowid
        conn.commit()
        conn.close()
        assert new_wid == old_wid, "SQLite reuses world_id=1 after reset"
        assert world.latest_world_cup(world.DEFAULT_SEED, "men") is None
    finally:
        world.reset()                                  # leave a clean DB for siblings
