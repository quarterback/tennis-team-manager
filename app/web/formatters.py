"""Presentation helpers exposed to Jinja as template filters.

Country/flag rendering for the player & recruit cards, ported from o27
baseball's formatters: real ISO 3166-1 alpha-2 codes render as a
regional-indicator emoji; fictional countries with custom art (e.g. ZR)
render as an inline <img> from /static/flags/. Dual-nationality players
show both flags. The code -> "Spain" / "ESP" name lookups come from
generators.flavor so the web and the engine agree on display names.
"""
from __future__ import annotations

from markupsafe import Markup, escape

from generators.flavor import country_name as _country_name
from generators.flavor import country_abbrev as _country_abbrev
from generators.flavor import flag_emoji as _flag_emoji

# Fictional countries with custom flag art under app/web/static/flags/.
_CUSTOM_FLAGS: dict[str, str] = {
    "ZR": "zr.png",   # Zaryanovia — alt-history Far East
}


def flag(country_code) -> Markup:
    """A single flag for a country code: emoji for real codes, <img> for
    custom-art codes, '' for blanks/unknowns."""
    if not country_code:
        return Markup("")
    s = str(country_code).strip().upper()
    if s in _CUSTOM_FLAGS:
        return Markup(
            f'<img src="/static/flags/{_CUSTOM_FLAGS[s]}" alt="{escape(s)}" '
            f'class="player-flag-img" style="height:1em;vertical-align:-0.15em;width:auto" />'
        )
    return Markup(_flag_emoji(s))


def flags(primary, secondary="") -> Markup:
    """One or two flags. Dual-nationality (dual citizen) players show both,
    primary first — pure flavor, ~a few % of the population."""
    out = str(flag(primary))
    sec = (str(secondary) or "").strip().upper()
    if sec and sec != str(primary or "").strip().upper():
        out = f"{out} {flag(sec)}"
    return Markup(out)


def country_name(country_code) -> str:
    return _country_name(country_code)


def country_abbrev(country_code) -> str:
    return _country_abbrev(country_code)
