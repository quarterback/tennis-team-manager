"""The DB-path resolver returns the configured path when writable, and falls
back to a writable local path (never crashing) when it isn't — so a regenerated
fly.toml that drops the volume mount can't take the app down."""
import os
import sqlite3

from app.dbpath import resolve_db_path


def test_uses_configured_path_when_writable(tmp_path, monkeypatch):
    target = tmp_path / "sub" / "tennis.db"
    monkeypatch.setenv("TENNIS_DB_PATH", str(target))
    assert resolve_db_path() == str(target)
    sqlite3.connect(str(target)).close()           # and it's actually usable


def test_falls_back_when_target_unwritable(monkeypatch):
    # Parent is a regular file, so the directory can never be created.
    monkeypatch.setenv("TENNIS_DB_PATH", "/etc/hostname/tennis.db")
    p = resolve_db_path()
    assert p != "/etc/hostname/tennis.db"
    sqlite3.connect(p).close()                      # fallback is writable
    os.remove(p)
