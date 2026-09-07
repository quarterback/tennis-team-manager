"""Regression coverage for archived JHSAA injury roster badges."""

from flask import Flask, render_template_string

from app import world
from app.web.state import _jh_injury_badges


def test_school_injuries_include_archived_program_names(tmp_path, monkeypatch):
    db = tmp_path / "injuries.db"
    monkeypatch.setattr(world, "WORLD_DB", str(db))
    monkeypatch.setattr(world, "_schema_ready_for", None)
    monkeypatch.setattr("app.jhsaa.known_names",
                        lambda school, gender: ["Current Academy", "Former High"])

    conn = world._db()
    conn.executemany(
        "INSERT INTO world_jhsaa_injury"
        " (world_id, year, gender, school, pid, name, dual_index, duals_out, season_ending)"
        " VALUES (1, 4, 'girls', ?, ?, ?, ?, ?, ?)",
        [("Former High", "stable-pid", "A Player", 3, 2, 0),
         ("Different School", "other-pid", "Other Player", 2, 1, 0)],
    )
    conn.commit()
    conn.close()

    rows = world.jhsaa_school_injuries(1, 4, "girls", "Current Academy")
    assert [r["pid"] for r in rows] == ["stable-pid"]


def test_badge_tooltips_use_stored_ordinal_and_scheduled_duration():
    badges = _jh_injury_badges([
        {"pid": "ended", "dual_index": 1, "duals_out": 0, "season_ending": 1},
        {"pid": "short", "dual_index": 18, "duals_out": 3, "season_ending": 0},
    ])

    with Flask(__name__).app_context():
        html = render_template_string(
            "{% for badge in badges.values() %}"
            '<span class="jh-chip inj" title="{{ badge.detail }}">{{ badge.label }}</span>'
            "{% endfor %}", badges=badges)

    assert 'title="Season-ending injury (dual 1)"' in html
    assert 'title="Scheduled out for 3 duals"' in html
    assert "dual 2" not in html
    assert "Missed 3 duals" not in html
