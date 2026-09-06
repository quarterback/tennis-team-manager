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


def test_concurrent_probes_never_flip_to_the_fallback(tmp_path, monkeypatch):
    """‼️ THE PROBE RACE THAT FORKED A SAVE. The probe file had one fixed name
    and the resolver re-probed on every call, so two threads probing at once
    deleted each other's probe, read the FileNotFoundError as 'not writable',
    and silently resolved that one call onto the fallback DB — the app then ran
    split across two saves. Unique probe names + a memoised decision make every
    concurrent resolution land on the same, configured file."""
    import concurrent.futures as cf

    import app.dbpath as dbpath

    target = tmp_path / "race" / "tennis.db"
    monkeypatch.setenv("TENNIS_DB_PATH", str(target))
    dbpath._resolved.clear()
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        got = {f.result() for f in
               [ex.submit(dbpath.resolve_db_path) for _ in range(200)]}
    assert got == {str(target)}


def test_an_existing_save_is_never_abandoned(tmp_path, monkeypatch):
    """An existing save file IS the save, whatever a probe says: one lost probe
    used to quietly fork a 47-season universe onto a shadow DB. SQLite failing
    loudly on a truly unwritable directory beats plausible wrong data."""
    import app.dbpath as dbpath

    target = tmp_path / "save" / "tennis.db"
    target.parent.mkdir()
    sqlite3.connect(str(target)).close()
    monkeypatch.setenv("TENNIS_DB_PATH", str(target))
    dbpath._resolved.clear()
    monkeypatch.setattr(dbpath, "_writable_dir", lambda p: False)
    assert resolve_db_path() == str(target)
    dbpath._resolved.clear()
