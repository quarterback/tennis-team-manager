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
import tempfile

log = logging.getLogger("baseline.dbpath")

_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tennis.db")
_warned = False


def _writable_dir(path: str) -> bool:
    """Can we actually create/write the parent directory of `path`?"""
    d = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".write_probe")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False


def resolve_db_path() -> str:
    """The configured DB path if its directory is writable, else a local
    fallback. Memo-warns once if it has to fall back."""
    global _warned
    configured = os.environ.get("TENNIS_DB_PATH", _DEFAULT)
    if _writable_dir(configured):
        return configured
    fallback = os.path.join(tempfile.gettempdir(), "baseline-tennis.db")
    if not _warned:
        log.warning(
            "TENNIS_DB_PATH=%r is not writable (volume not mounted?); falling back "
            "to %r — saved seasons will NOT persist across restarts. Check the "
            "[[mounts]] block in fly.toml.", configured, fallback)
        _warned = True
    return fallback
