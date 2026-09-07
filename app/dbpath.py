"""
Resilient DB-path resolver — the app's last line of defence for persistence.

The season DB normally lives on the Fly volume at $TENNIS_DB_PATH (/data/...).
But `fly launch` periodically regenerates fly.toml and can drop the [[mounts]]
block, which would leave /data unwritable. Rather than crash, we detect an
unwritable target and fall back to a local writable path so the app always
boots — losing persistence, never availability. A one-time warning is logged so
the regression is visible in the Fly logs.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import tempfile

log = logging.getLogger("baseline.dbpath")

_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tennis.db")
_warned = False
#: The resolved answer per configured path — decided ONCE per process. See
#: `resolve_db_path`: re-probing per call is what let a single flaky probe flip
#: one connection onto the fallback save mid-run.
_resolved: dict[str, str] = {}

JHSAA_LAB_CANONICAL_DB = os.path.abspath(os.path.expanduser(
    "~/.tennis-team-manager/jhsaa_lab.db"))
JHSAA_LAB_DEV_OVERRIDE = "JHSAA_LAB_DEV_OVERRIDE"
_jhsaa_lab_checked = False


def _jhsaa_lab_path_invariant(configured: str) -> str:
    """Enforce the one-file rule before any app module can open a lab DB.

    Alternate paths remain available only when the deliberately named developer
    override is set.  The ordinary launcher never sets that override.
    """
    global _jhsaa_lab_checked
    configured = os.path.abspath(os.path.expanduser(configured))
    if configured != JHSAA_LAB_CANONICAL_DB:
        if not os.environ.get(JHSAA_LAB_DEV_OVERRIDE):
            raise RuntimeError(
                "JHSAA lab startup refused: TENNIS_DB_PATH resolves to "
                f"{configured}, not the canonical database {JHSAA_LAB_CANONICAL_DB}. "
                f"Scratch/test runs must explicitly set {JHSAA_LAB_DEV_OVERRIDE}=1.")
        return configured        # a deliberate scratch/test universe — not ours to check
    # ‼️ THE CANONICAL DATABASE IS ALWAYS PREFLIGHTED, OVERRIDE OR NOT. The
    # override used to short-circuit this whole function, so an inherited
    # `JHSAA_LAB_DEV_OVERRIDE=1` left in a developer's shell silently disabled the
    # consistency, writability and stale-alternate checks on the REAL save — and a
    # missing canonical file then resolved happily, ready to be created fresh while
    # a stale universe sat elsewhere, which is precisely the fork this module
    # exists to prevent. The override's job is to permit an ALTERNATE PATH (above);
    # it was never meant to buy an unchecked canonical open, and there is no
    # scratch-run reason to want one, since a scratch run is non-canonical by
    # definition. `scripts/jhsaa_lab_server.sh` also clears an inherited override,
    # but the guarantee must not depend on which launcher was used.
    if not _jhsaa_lab_checked:
        # Import lazily: startup owns SQLite inspection, while this leaf module
        # remains usable by the rest of the application without an import cycle.
        from .jhsaa_lab_startup import preflight
        preflight(configured)
        _jhsaa_lab_checked = True
    return configured


def _writable_dir(path: str) -> bool:
    """Can we actually create/write the parent directory of `path`?

    ‼️ THE PROBE FILENAME MUST BE UNIQUE PER PROBE. It was a fixed
    `.write_probe`, and this function used to run on EVERY connection: two
    threads (or spawn workers) probing the same directory at once would each
    create the file, the first `os.remove` won, the second raised
    FileNotFoundError — an OSError — and that caller concluded "not writable"
    and silently resolved to the FALLBACK save. A per-process/per-call name
    cannot collide, and a lost delete-race is tolerated outright: someone
    removing our file proves the directory writable, not broken. This race
    forked a real 47-season save onto a shadow DB in `~/.tennis-team-manager/`
    before it was found."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    probe = os.path.join(d, f".write_probe.{os.getpid()}.{id(object()):x}")
    try:
        os.makedirs(d, exist_ok=True)
        with open(probe, "w") as fh:
            fh.write("ok")
        try:
            os.remove(probe)
        except FileNotFoundError:
            pass
        return True
    except OSError:
        return False


def connect(path: str, *, row: bool = True, timeout: float = 5.0) -> sqlite3.Connection:
    """Open a SQLite connection tuned for this app's many short-lived, nested
    connections to the SAME file.

    The web app opens a fresh connection per helper call, and a sim holds one
    open (mid-write) while read helpers like `overrides.any_overrides()` open
    their own. Default SQLite errors that second connection out instantly with
    "database is locked". WAL lets readers run alongside a writer, and a busy
    timeout makes any genuine write contention WAIT rather than 500.
    """
    conn = sqlite3.connect(path, timeout=timeout)
    if row:
        conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass            # e.g. a filesystem that can't do WAL — degrade, don't crash
    return conn


def resolve_db_path() -> str:
    """The configured DB path if its directory is writable, else a fallback.

    Fallback order: a PERSISTENT per-user dir (`~/.tennis-team-manager/`) first —
    so a local run whose repo folder isn't writable (e.g. macOS blocks writes under
    ~/Documents) still keeps its saves — and only a temp dir as the last resort.
    Memo-warns once, naming the path actually used and whether it persists."""
    global _warned
    configured = os.environ.get("TENNIS_DB_PATH", _DEFAULT)
    if os.environ.get("JHSAA_LAB_MODE"):
        configured = _jhsaa_lab_path_invariant(configured)
    got = _resolved.get(configured)
    if got is not None:
        return got
    # ‼️ AN EXISTING SAVE IS NEVER ABANDONED ON A PROBE. This resolver used to
    # re-probe the directory on every call, and one lost probe race (see
    # `_writable_dir`) silently moved that ONE call onto the fallback file —
    # the app then ran with its subsystems split across two saves: the pages
    # read the real archive while the era settings resolved against a shadow
    # DB, every roster regenerated under the wrong inputs (all records 0-0),
    # and a boot that lost the race at import came up in the shadow universe
    # entirely. The repo's own world-resolution doctrine applies here too:
    # a graceful fallback turns a should-be-crash into plausible-looking wrong
    # data. If the configured FILE exists, it is the save, full stop — SQLite
    # will fail loudly if the directory truly cannot take its journal, which
    # is strictly better than quietly forking the universe. The fallback
    # remains only for a path that does not exist yet AND cannot be created
    # (a fresh install on a read-only volume). And the answer is memoised per
    # configured path, so one decision holds for the whole process.
    if os.path.exists(configured):
        _resolved[configured] = configured
        return configured
    if _writable_dir(configured):
        _resolved[configured] = configured
        return configured
    home = os.path.join(os.path.expanduser("~"), ".tennis-team-manager", "tennis.db")
    if _writable_dir(home):
        fallback, persists = home, True
    else:
        fallback, persists = os.path.join(tempfile.gettempdir(), "baseline-tennis.db"), False
    if not _warned:
        note = ("Saves WILL persist there." if persists
                else "Saves will NOT persist across restarts (temp dir).")
        hint = (" On Fly, check the [[mounts]] block in fly.toml."
                if str(configured).startswith("/data") else
                " Set TENNIS_DB_PATH to choose the location.")
        log.warning("TENNIS_DB_PATH=%r is not writable; using %r instead. %s%s",
                    configured, fallback, note, hint)
        _warned = True
    _resolved[configured] = fallback
    return fallback
