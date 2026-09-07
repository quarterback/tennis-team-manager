"""Fail-closed startup guard for the canonical local JHSAA universe.

This module intentionally uses read-only SQLite inspection and does not import
``app.world``: it runs from ``dbpath.resolve_db_path`` before schema bootstrap,
world creation, cache warming, or simulation can occur.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import stat
import sys


class JHSAALabStartupError(RuntimeError):
    """The canonical lab universe cannot be opened safely."""


def known_alternate_paths(canonical: str) -> list[str]:
    candidates = [
        "/tmp/jhsaa_lab.db",
        "/private/tmp/jhsaa_lab.db",
        "/var/tmp/jhsaa_lab.db",
        os.path.abspath("jhsaa_lab.db"),
        str(Path(__file__).resolve().parents[1] / "jhsaa_lab.db"),
    ]
    return list(dict.fromkeys(p for p in candidates if p != canonical))


def _read_only(path: str) -> sqlite3.Connection:
    # URI mode=ro is essential: sqlite3.connect(path) creates a missing file.
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def inspect_database(path: str) -> dict:
    info = {"path": os.path.abspath(path), "size": os.path.getsize(path),
            "world": None, "archive": (None, None, 0), "has_schema": False}
    try:
        conn = _read_only(path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "world" not in tables:
            conn.close()
            return info
        info["has_schema"] = True
        world_columns = {r[1] for r in conn.execute("PRAGMA table_info(world)")}
        salt_expr = "salt" if "salt" in world_columns else "NULL AS salt"
        worlds = conn.execute(
            f"SELECT id, seed, year, week, {salt_expr} FROM world ORDER BY id").fetchall()
        if len(worlds) > 1:
            raise JHSAALabStartupError(
                f"{path} contains {len(worlds)} worlds; a JHSAA lab DB must contain at most one.")
        info["world"] = worlds[0] if worlds else None
        if "world_jhsaa" in tables:
            if worlds:
                foreign = conn.execute(
                    "SELECT COUNT(*) FROM world_jhsaa WHERE world_id<>?",
                    (worlds[0][0],)).fetchone()[0]
                if foreign:
                    raise JHSAALabStartupError(
                        f"{path} contains {foreign} archive rows for a different world; "
                        "the single JHSAA world/archive binding is incoherent.")
                info["archive"] = conn.execute(
                    "SELECT MIN(year), MAX(year), COUNT(DISTINCT year) "
                    "FROM world_jhsaa WHERE world_id=?", (worlds[0][0],)).fetchone()
            else:
                info["archive"] = conn.execute(
                    "SELECT MIN(year), MAX(year), COUNT(DISTINCT year) FROM world_jhsaa").fetchone()
        conn.close()
        return info
    except (sqlite3.Error, OSError) as exc:
        raise JHSAALabStartupError(f"cannot open existing JHSAA database {path}: {exc}") from exc


def _describe(info: dict) -> str:
    world = info["world"]
    mn, mx, count = info["archive"]
    if world:
        wid, seed, year, week, salt = world
    else:
        wid = seed = year = week = salt = "NONE"
    return (f"path={info['path']} size={info['size']} bytes; "
            f"world.id={wid} world.seed={seed} world.year={year} world.week={week} "
            f"salt={salt}; archive.min_year={mn if mn is not None else 'NONE'} "
            f"archive.max_year={mx if mx is not None else 'NONE'} "
            f"archive.distinct_years={count}")


def _check_consistency(info: dict) -> None:
    world = info["world"]
    mn, mx, count = info["archive"]
    if not world:
        if count:
            raise JHSAALabStartupError(
                "archive rows exist without the single JHSAA world pointer")
        return
    year = world[2]
    expected = year + 1
    if (mn, mx, count) != (0, year, expected):
        raise JHSAALabStartupError(
            "JHSAA world/archive mismatch: advance_jhsaa_lab requires contiguous "
            f"archived years 0..{year} ({expected} distinct), but found "
            f"min={mn}, max={mx}, distinct={count}. No repair was attempted.")


def _assert_writable(path: str) -> None:
    file_mode = stat.S_IMODE(os.stat(path).st_mode)
    parent_mode = stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode)
    if not file_mode & 0o222 or not parent_mode & 0o222:
        raise JHSAALabStartupError(
            f"canonical JHSAA database is not writable: {path}")
    try:
        conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True)
        conn.execute("BEGIN IMMEDIATE")
        conn.rollback()
        conn.close()
    except sqlite3.Error as exc:
        raise JHSAALabStartupError(
            f"canonical JHSAA database cannot be opened for writing: {path}: {exc}") from exc


def preflight(canonical: str) -> None:
    """Warn about alternates, then validate and announce the canonical DB."""
    canonical = os.path.abspath(os.path.expanduser(canonical))
    alternates = []
    for path in known_alternate_paths(canonical):
        if os.path.isfile(path):
            try:
                info = inspect_database(path)
            except JHSAALabStartupError as exc:
                info = {"path": os.path.abspath(path), "size": os.path.getsize(path),
                        "world": None, "archive": (None, None, 0),
                        "has_schema": False}
                print(f"WARNING: alternate JHSAA database found; {_describe(info)}; "
                      f"metadata unreadable: {exc}", file=sys.stderr, flush=True)
                alternates.append(info)
                continue
            alternates.append(info)
            print(f"WARNING: alternate JHSAA database found; {_describe(info)}",
                  file=sys.stderr, flush=True)

    if not os.path.exists(canonical):
        print((f"JHSAA LAB BOOT: path={canonical} size=0 bytes; world.id=NONE "
               "world.seed=NONE world.year=NONE world.week=NONE salt=NONE; "
               "archive.min_year=NONE archive.max_year=NONE "
               "archive.distinct_years=0"), file=sys.stderr, flush=True)
        if alternates:
            found = ", ".join(i["path"] for i in alternates)
            raise JHSAALabStartupError(
                "canonical JHSAA database is missing, but an existing JHSAA "
                f"universe was found at: {found}. Startup is closed; manually "
                "recover or migrate it. Nothing was copied, deleted, or created.")
        parent = os.path.dirname(canonical)
        os.makedirs(parent, exist_ok=True)
        if not stat.S_IMODE(os.stat(parent).st_mode) & 0o222:
            raise JHSAALabStartupError(f"canonical JHSAA directory is not writable: {parent}")
        return

    info = inspect_database(canonical)
    print(f"JHSAA LAB BOOT: {_describe(info)}", file=sys.stderr, flush=True)
    _check_consistency(info)
    _assert_writable(canonical)
