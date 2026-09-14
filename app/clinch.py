"""The Clinch Report, hosted INSIDE the game (owner request 2026-09: "integrate the
analytics app into the UI so that I don't have to load a separate app").

The sidecar (`analytics/`) stays exactly what it is — a static site rendered from
research exports, never reading the game's database. This module is the bridge:
it exports a season in-process (the same bytes `/research/export` downloads),
hands them to the sidecar's own ingester, renders with the sidecar's own
`build_site`, and the game serves `analytics/site/` under `/clinch/`. One
process, one tab, one origin (which is also what makes the sidecar's
localStorage features — My Teams, the shortlist — work; see its README).

‼️ A build is MINUTES of CPU and the app has ONE request thread — it runs only
through the deferred-job idiom (`server._jh_deferred`), never inline.

‼️ SIZE. The owner's working shape (2026-09): the LATEST season, NO player
pages, one to three seasons when a comparison needs a prior year. That is the
default here; the almanac stays in the sidecar's cache whatever is rendered.
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import time
from pathlib import Path

ANALYTICS = Path(__file__).resolve().parent.parent / "analytics"
SITE = ANALYTICS / "site"
DATA = ANALYTICS / "data"
BUILD_INFO = SITE / ".build.json"

MAX_SEASONS = 3          # 1-3, per the owner's working shape
GENDERS = ("girls", "boys")


def _sidecar():
    """The sidecar's own modules, imported from its directory (it is not a
    package of the app, and must not become one — it reads exports only)."""
    if str(ANALYTICS) not in sys.path:
        sys.path.insert(0, str(ANALYTICS))
    from ptc_analytics import ingest, render          # noqa: WPS433
    return ingest, render


def cached_seasons() -> list[dict]:
    """What the sidecar's cache holds, from the manifests ALONE — never
    `all_bundles()`, which parses every CSV of every season."""
    out = []
    if not DATA.exists():
        return out
    for d in sorted(DATA.iterdir()):
        m = d / "manifest.json"
        if d.is_dir() and m.exists():
            try:
                scope = json.loads(m.read_text())["scope"]
            except (ValueError, KeyError):
                continue
            out.append({"key": d.name, "year": int(scope.get("year", 0)),
                        "gender": scope.get("gender", ""),
                        "classification": scope.get("classification", "all")})
    return out


def build_info() -> dict | None:
    if BUILD_INFO.exists():
        try:
            return json.loads(BUILD_INFO.read_text())
        except ValueError:
            return None
    return None


def site_ready() -> bool:
    return (SITE / "index.html").exists()


def build(year: int, seasons: int = 1, genders: tuple = GENDERS,
          player_pages: bool = False, classification: str = "all",
          refresh: bool = False) -> dict:
    """Export → ingest → render, for `seasons` years ending at `year`.

    A season already in the cache is NOT re-exported unless `refresh` — an
    archived JHSAA season is immutable, and the export is the slow half. The
    render is scoped to exactly the requested window (the sidecar's `--years`),
    so the site never grows past what was asked for."""
    from app.research_export import ExportError, export_zip
    ingest, render = _sidecar()
    seasons = max(1, min(MAX_SEASONS, int(seasons)))
    years = list(range(year - seasons + 1, year + 1))
    have = {(c["year"], c["gender"], c["classification"]) for c in cached_seasons()}
    t0 = time.time()
    exported, missing = [], []
    for y in years:
        for g in genders:
            if not refresh and (y, g, classification) in have:
                continue
            try:
                buf = export_zip("jhsaa", year=y, gender=g, classification=classification)
            except ExportError as exc:
                missing.append(f"{y} {g}: {exc}")
                continue
            DATA.mkdir(parents=True, exist_ok=True)
            tmp = DATA / f".export-{y}-{g}.zip"
            tmp.write_bytes(buf.getvalue())
            try:
                ingest.ingest_zip(tmp)
            finally:
                tmp.unlink(missing_ok=True)
            exported.append(f"{y} {g}")
    bundles = [b for b in ingest.all_bundles()
               if int(b["scope"]["year"]) in years
               and b["scope"].get("gender") in genders
               and b["scope"].get("classification", "all") == classification]
    if not bundles:
        raise RuntimeError("Nothing to render: no season in that window has been "
                           "played. " + "; ".join(missing))
    render.build_site(bundles, player_pages=player_pages)
    info = {"built_at": time.strftime("%Y-%m-%d %H:%M"),
            "years": years, "genders": list(genders), "player_pages": player_pages,
            "classification": classification,
            "rendered": sorted(f"{b['scope']['year']} {b['scope']['gender']}" for b in bundles),
            "exported": exported, "missing": missing,
            "seconds": round(time.time() - t0, 1), "size": _size(SITE)}
    BUILD_INFO.write_text(json.dumps(info, indent=2))
    return info


def _size(path: Path) -> str:
    total = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024 or unit == "GB":
            return f"{total:.0f} {unit}" if unit == "B" else f"{total:.1f} {unit}"
        total /= 1024
    return ""


def clear_site() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
