"""Presentation helpers exposed to Jinja as template filters.

Country/flag rendering for the player & recruit cards: real ISO 3166-1
alpha-2 codes render as a self-hosted flag-icons SVG (`<span class="fi
fi-xx">`), which displays identically on every platform — unlike the old
regional-indicator emoji, which Windows/Chrome render as bare letters.
Fictional countries with custom art (e.g. ZR) keep their inline <img> from
/static/flags/. Dual-nationality players show both flags. The code ->
"Spain" / "ESP" name lookups come from generators.flavor so the web and the
engine agree on display names.
"""
from __future__ import annotations

import json
from pathlib import Path

from markupsafe import Markup, escape

from generators.flavor import country_name as _country_name
from generators.flavor import country_abbrev as _country_abbrev

# Fictional countries with custom flag art under app/web/static/flags/.
_CUSTOM_FLAGS: dict[str, str] = {
    "ZR": "zr.png",   # Zaryanovia — alt-history Far East
}

# Real alpha-2 codes we ship a flag-icons SVG for (4x3 set under
# static/vendor/flag-icons/flags/4x3/). Built once at import so an unknown
# code degrades to no mark instead of an empty box.
_FLAG_ICON_DIR = (
    Path(__file__).resolve().parent / "static" / "vendor" / "flag-icons"
    / "flags" / "4x3"
)


def _load_flag_codes() -> set[str]:
    try:
        return {p.stem.upper() for p in _FLAG_ICON_DIR.glob("*.svg")}
    except OSError:
        return set()


_FLAG_CODES: set[str] = _load_flag_codes()

# School name -> {"slug", "espn_id"} mapping built by
# scripts/fetch_team_logos.py; logo PNGs live under app/web/static/logos/.
# Schools without a known logo (e.g. some D2/D3 ESPN doesn't track) are absent
# and render with no mark, exactly like an unknown flag.
_LOGO_MAP_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "ncaa" / "logos.json"
)


def _load_logo_map() -> dict[str, dict]:
    try:
        return json.loads(_LOGO_MAP_PATH.read_text())
    except (FileNotFoundError, ValueError):
        return {}


_LOGOS: dict[str, dict] = _load_logo_map()


def flag(country_code) -> Markup:
    """A single flag for a country code: a flag-icons SVG span for real
    codes, <img> for custom-art codes, '' for blanks/unknowns."""
    if not country_code:
        return Markup("")
    s = str(country_code).strip().upper()
    if s in _CUSTOM_FLAGS:
        return Markup(
            f'<img src="/static/flags/{_CUSTOM_FLAGS[s]}" alt="{escape(s)}" '
            f'class="player-flag-img" style="height:1em;vertical-align:-0.15em;width:auto" />'
        )
    if s in _FLAG_CODES:
        return Markup(
            f'<span class="fi fi-{s.lower()}" '
            f'style="vertical-align:-0.1em"></span>'
        )
    return Markup("")


def flags(primary, secondary="") -> Markup:
    """One or two flags. Dual-nationality (dual citizen) players show both,
    primary first — pure flavor, ~a few % of the population."""
    out = str(flag(primary))
    sec = (str(secondary) or "").strip().upper()
    if sec and sec != str(primary or "").strip().upper():
        out = f"{out} {flag(sec)}"
    return Markup(out)


def team_logo(school, cls: str = "team-logo-img") -> Markup:
    """Inline <img> of a school's logo, or '' if we have no art for it.

    Mirrors flag(): a small mark the template scales to ~1em, rendered just
    before the school name in rankings/standings/schedule rows.
    """
    if not school:
        return Markup("")
    info = _LOGOS.get(str(school).strip())
    if not info:
        return Markup("")
    return Markup(
        f'<img src="/static/logos/{escape(info["slug"])}.png" '
        f'alt="{escape(str(school))}" class="{escape(cls)}" '
        f'style="height:1.4em;width:auto;vertical-align:-0.35em" '
        f'loading="lazy" />'
    )


def has_team_logo(school) -> bool:
    return bool(school) and str(school).strip() in _LOGOS


def team_logo_src(school) -> str:
    """Bare URL of a school's logo PNG, or '' if we have no art for it.
    For templates that place the mark inside their own element (e.g. the
    team-crest box) rather than using the ready-made <img> from team_logo()."""
    info = _LOGOS.get(str(school).strip()) if school else None
    return f"/static/logos/{info['slug']}.png" if info else ""


def state_abbrev(state_name) -> str:
    """Full US state name -> postal abbreviation (e.g. 'California' -> 'CA').
    Falls back to the input when it's already an abbr or unknown."""
    from app.juniors import _STATE_ABBR
    if not state_name:
        return ""
    return _STATE_ABBR.get(str(state_name), str(state_name))


def country_name(country_code) -> str:
    return _country_name(country_code)


def country_abbrev(country_code) -> str:
    return _country_abbrev(country_code)
