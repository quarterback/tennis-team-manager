"""Ingest a Play to Clinch research-export zip into the local raw data cache.

Read-only relative to the game repo: this only ever reads a zip the owner
downloaded from /research/export and dropped in. It never touches the game's
database or app code.
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import zipfile
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_csv(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def scope_key(manifest: dict) -> str:
    fam = manifest["dataset_family"]
    scope = manifest["scope"]
    if fam == "jhsaa":
        # classification ("all", "9A", ...) is part of the exporter's own scope
        # (research_export.build_jhsaa) — two exports for the same year/gender
        # but different classifications are DIFFERENT datasets and must not
        # collide on one cache directory.
        return f"jhsaa__{scope['year']}__{scope['gender']}__{scope.get('classification', 'all')}"
    return f"college__{scope['year']}__{scope['division']}__{scope['gender']}"


def _ingest_scope(zf: zipfile.ZipFile, manifest: dict, prefix: str = "") -> str:
    """Extract the members of ONE scope (an ordinary single export, or one
    ``<year>/<gender>/`` folder inside a bulk archive — ``prefix`` is that
    folder, empty for a plain export) into analytics/data/<scope_key>/."""
    key = scope_key(manifest)
    dest = DATA_DIR / key
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    plen = len(prefix)
    for name in zf.namelist():
        if not name.startswith(prefix) or name == prefix:
            continue
        rel = name[plen:]
        if not rel or rel.endswith("/"):
            continue                       # a bulk zip's own subfolder entries
        (dest / rel).write_bytes(zf.read(name))
    return key


def ingest_zip(path: str | Path) -> list[str]:
    """Extract a research-export zip into analytics/data/<scope_key>/, storing
    every member as-is (csv text, json text) for the aggregator to read later.
    Re-ingesting the same scope overwrites it (a season can be re-exported after
    more of the world has been played).

    Handles both shapes /research/export can hand back: an ordinary single-scope
    zip (a root ``manifest.json``) and a bulk zip (a root ``bulk_manifest.json``
    plus one ``<year>/<gender>/`` folder — each with its own ``manifest.json`` —
    per included scope). Returns the list of scope keys ingested; a plain export
    always returns exactly one."""
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if "bulk_manifest.json" in names:
            bulk = json.loads(zf.read("bulk_manifest.json"))
            keys = []
            for scope in bulk["included"]:
                prefix = f"{scope['year']}/{scope['gender']}/"
                if f"{prefix}manifest.json" not in names:
                    continue                # e.g. underplayed exports from before it had one
                manifest = json.loads(zf.read(f"{prefix}manifest.json"))
                keys.append(_ingest_scope(zf, manifest, prefix))
            return keys
        manifest = json.loads(zf.read("manifest.json"))
        return [_ingest_scope(zf, manifest)]


def load_bundle(dest: Path) -> dict:
    """Load one ingested scope directory back into python objects."""
    manifest = json.loads((dest / "manifest.json").read_text())
    fam = manifest["dataset_family"]
    tables = {}
    for name, meta in manifest["files"].items():
        if name in ("manifest.json", "README.md"):
            continue
        p = dest / name
        if not p.exists():
            continue
        if name.endswith(".csv"):
            tables[name[:-4]] = _read_csv(p.read_bytes())
        else:
            tables[name[:-5]] = json.loads(p.read_text())
    return {"family": fam, "scope": manifest["scope"], "manifest": manifest, "tables": tables}


def all_bundles() -> list[dict]:
    if not DATA_DIR.exists():
        return []
    bundles = []
    for d in sorted(DATA_DIR.iterdir()):
        if d.is_dir() and (d / "manifest.json").exists():
            bundles.append(load_bundle(d))
    return bundles
