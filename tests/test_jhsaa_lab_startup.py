"""Regression coverage for the canonical, fail-closed JHSAA lab database."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

from app import dbpath
from app.jhsaa_lab_startup import JHSAALabStartupError, inspect_database, preflight


def _lab_db(path: Path, *, year: int = 0, archived: list[int] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE world (id INTEGER PRIMARY KEY, seed INTEGER, year INTEGER,
                            week INTEGER, salt TEXT);
        CREATE TABLE world_jhsaa (world_id INTEGER, year INTEGER,
                                  gender TEXT, data TEXT);
    """)
    conn.execute("INSERT INTO world VALUES (1, 2026, ?, 0, 'stable-salt')", (year,))
    for value in archived if archived is not None else range(year + 1):
        conn.execute("INSERT INTO world_jhsaa VALUES (1, ?, 'boys', '{}')", (value,))
    conn.commit()
    conn.close()
    return path


def test_canonical_existing_database_is_announced_and_opened(tmp_path, monkeypatch, capsys):
    canonical = str(_lab_db(tmp_path / "home" / "jhsaa_lab.db", year=2))
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [])
    preflight(canonical)
    output = capsys.readouterr().err
    assert f"path={canonical}" in output
    assert "world.id=1 world.seed=2026 world.year=2 world.week=0" in output
    assert "salt=stable-salt" in output
    assert "archive.min_year=0 archive.max_year=2 archive.distinct_years=3" in output
    assert inspect_database(canonical)["world"][2] == 2


@pytest.mark.parametrize("alternate", ["/tmp/jhsaa_lab.db", "/private/tmp/jhsaa_lab.db"])
def test_stale_alternate_warns_but_is_never_selected(tmp_path, monkeypatch, capsys, alternate):
    canonical = str(_lab_db(tmp_path / "canonical.db"))
    stale = str(_lab_db(tmp_path / Path(alternate).name / "stale.db", year=4))
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [stale])
    preflight(canonical)
    warning = capsys.readouterr().err
    assert f"WARNING: alternate JHSAA database found; path={stale}" in warning
    assert "size=" in warning and "world.year=4" in warning
    assert "archive.max_year=4" in warning
    assert os.path.exists(canonical)


def test_missing_canonical_with_stale_database_fails_without_creating(tmp_path, monkeypatch):
    canonical = str(tmp_path / "home" / "jhsaa_lab.db")
    stale = str(_lab_db(tmp_path / "tmp" / "jhsaa_lab.db", year=1))
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [stale])
    with pytest.raises(JHSAALabStartupError, match="manually recover or migrate"):
        preflight(canonical)
    assert not os.path.exists(canonical)


def test_missing_canonical_without_alternate_only_prepares_canonical_directory(tmp_path, monkeypatch):
    canonical = str(tmp_path / "home" / "jhsaa_lab.db")
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [])
    preflight(canonical)
    assert os.path.isdir(os.path.dirname(canonical))
    assert not os.path.exists(canonical)  # preflight itself never opens/creates SQLite


def test_accidental_env_path_is_rejected_and_developer_override_is_explicit(tmp_path, monkeypatch):
    canonical = str(tmp_path / "canonical.db")
    scratch = str(tmp_path / "scratch.db")
    monkeypatch.setattr(dbpath, "JHSAA_LAB_CANONICAL_DB", canonical)
    monkeypatch.setenv("JHSAA_LAB_MODE", "1")
    monkeypatch.setenv("TENNIS_DB_PATH", scratch)
    monkeypatch.delenv(dbpath.JHSAA_LAB_DEV_OVERRIDE, raising=False)
    dbpath._resolved.clear()
    with pytest.raises(RuntimeError, match="startup refused"):
        dbpath.resolve_db_path()
    assert not os.path.exists(scratch)

    monkeypatch.setenv(dbpath.JHSAA_LAB_DEV_OVERRIDE, "1")
    dbpath._resolved.clear()
    assert dbpath.resolve_db_path() == scratch


def test_existing_canonical_that_is_not_writable_is_fatal(tmp_path, monkeypatch):
    canonical = _lab_db(tmp_path / "canonical.db")
    canonical.chmod(0o444)
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [])
    with pytest.raises(JHSAALabStartupError, match="not writable"):
        preflight(str(canonical))


def test_archive_pointer_mismatch_fails_without_repair(tmp_path, monkeypatch):
    canonical = str(_lab_db(tmp_path / "canonical.db", year=3, archived=[0, 1, 3]))
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [])
    with pytest.raises(JHSAALabStartupError, match="world/archive mismatch"):
        preflight(canonical)
    assert inspect_database(canonical)["archive"] == (0, 3, 3)


def test_archive_rows_cannot_belong_to_a_different_world(tmp_path, monkeypatch):
    canonical = _lab_db(tmp_path / "canonical.db")
    conn = sqlite3.connect(canonical)
    conn.execute("INSERT INTO world_jhsaa VALUES (99, 0, 'girls', '{}')")
    conn.commit()
    conn.close()
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [])
    with pytest.raises(JHSAALabStartupError, match="different world"):
        preflight(str(canonical))


def test_launcher_is_cwd_independent_and_always_exports_canonical(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    capture = tmp_path / "capture"
    fake_python = fake_bin / "python3"
    fake_python.write_text("#!/bin/sh\nprintf '%s\\n%s\\n%s\\n' \"$PWD\" \"$TENNIS_DB_PATH\" \"$*\" > \"$CAPTURE\"\n")
    fake_python.chmod(0o755)
    home = tmp_path / "home"
    outside = tmp_path / "outside"
    outside.mkdir()
    env = {**os.environ, "HOME": str(home), "PATH": f"{fake_bin}:{os.environ['PATH']}",
           "CAPTURE": str(capture)}
    env.pop("TENNIS_DB_PATH", None)
    script = Path(__file__).resolve().parents[1] / "scripts" / "jhsaa_lab_server.sh"
    subprocess.run([str(script), "5099"], cwd=outside, env=env, check=True,
                   text=True, capture_output=True)
    pwd, selected, args = capture.read_text().splitlines()
    assert pwd == str(Path(__file__).resolve().parents[1])
    assert selected == str(home / ".tennis-team-manager" / "jhsaa_lab.db")
    assert args == "-m app.web.server"
    assert not (outside / "jhsaa_lab.db").exists()


def test_launcher_rejects_inherited_alternate_and_old_path_argument(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "jhsaa_lab_server.sh"
    env = {**os.environ, "HOME": str(tmp_path / "home"),
           "TENNIS_DB_PATH": str(tmp_path / "accidental.db")}
    bad_env = subprocess.run([str(script)], env=env, text=True, capture_output=True)
    assert bad_env.returncode == 2
    assert "inherited TENNIS_DB_PATH" in bad_env.stderr
    assert not (tmp_path / "accidental.db").exists()

    env.pop("TENNIS_DB_PATH")
    old = subprocess.run([str(script), str(tmp_path / "old.db")], env=env,
                         text=True, capture_output=True)
    assert old.returncode == 2
    assert "arbitrary paths are not accepted" in old.stderr
    assert not (tmp_path / "old.db").exists()


def test_a_crashed_advance_is_recoverable_not_fatal(tmp_path, monkeypatch, capsys):
    """‼️ PR #425 BRICKED THE SAVE ON ITS OWN DESIGNED CRASH STATE.
    `world.advance_jhsaa_lab` commits the season's archive FIRST and only then
    moves `world.year`, so that a crash mid-simulation leaves the year
    REPLAYABLE (the next advance recomputes the same year). That leaves the
    archive exactly one year ahead of the pointer — which the original
    `max == world.year` check made fatal, so a sim that died mid-advance also
    locked the owner out of the save it died in."""
    canonical = str(_lab_db(tmp_path / "canonical.db", year=4, archived=[0, 1, 2, 3, 4, 5]))
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [])
    preflight(canonical)                      # must NOT raise
    err = capsys.readouterr().err
    assert "archive is ahead of the world pointer" in err
    assert "replays year 5" in err


def test_a_hole_in_the_archive_is_still_fatal(tmp_path, monkeypatch):
    """The carve-out above must not swallow genuine incoherence."""
    canonical = str(_lab_db(tmp_path / "canonical.db", year=3, archived=[0, 1, 3]))
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [])
    with pytest.raises(JHSAALabStartupError, match="CONTIGUOUS"):
        preflight(canonical)


def test_a_world_claiming_unsimulated_seasons_is_still_fatal(tmp_path, monkeypatch):
    """The pointer ahead of the archive is the direction that must never happen:
    it means a season the world claims was never played."""
    canonical = str(_lab_db(tmp_path / "canonical.db", year=6, archived=[0, 1, 2]))
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [])
    with pytest.raises(JHSAALabStartupError, match="never simulated"):
        preflight(canonical)


def test_a_clean_save_still_passes_silently(tmp_path, monkeypatch, capsys):
    canonical = str(_lab_db(tmp_path / "canonical.db", year=47))
    monkeypatch.setattr("app.jhsaa_lab_startup.known_alternate_paths", lambda _: [])
    preflight(canonical)
    assert "ahead of the world pointer" not in capsys.readouterr().err


# --- the advisory that covers the launch the path invariant cannot reach -----

def test_a_plain_launch_is_told_which_universe_it_is_not_opening(tmp_path):
    """`dbpath` only enforces the canonical path under JHSAA_LAB_MODE, so it is
    inert on the college-route launch that caused the incident. This names the
    lab universe the process is NOT using."""
    from app.jhsaa_lab_startup import canonical_universe_elsewhere

    canonical = str(_lab_db(tmp_path / "lab.db", year=49))
    line = canonical_universe_elsewhere(canonical, str(tmp_path / "tennis.db"))
    assert line is not None
    assert canonical in line and "world year 49" in line and "50 archived seasons" in line


def test_the_advisory_is_silent_when_there_is_nothing_to_warn_about(tmp_path):
    from app.jhsaa_lab_startup import canonical_universe_elsewhere

    canonical = str(_lab_db(tmp_path / "lab.db", year=2))
    # Already opening it — nothing to say.
    assert canonical_universe_elsewhere(canonical, canonical) is None
    # No lab database at all.
    assert canonical_universe_elsewhere(str(tmp_path / "absent.db"),
                                        str(tmp_path / "tennis.db")) is None


def test_the_advisory_never_raises_on_an_unreadable_lab_database(tmp_path):
    """A college boot must not die because a lab file it is not using is broken."""
    from app.jhsaa_lab_startup import canonical_universe_elsewhere

    broken = tmp_path / "lab.db"
    broken.write_bytes(b"this is not a sqlite database")
    line = canonical_universe_elsewhere(str(broken), str(tmp_path / "tennis.db"))
    assert line is None or "unreadable" in line
