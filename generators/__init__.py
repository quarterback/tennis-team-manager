"""Name / player generators (lifted from the O27 viperball-derived pools)."""
from .names import make_name_picker, region_preset, list_presets
from .flavor import (
    roll_hometown, roll_birthday, roll_secondary_country, roll_high_school,
    country_name, country_abbrev, flag_emoji,
)
from . import nation_talent

__all__ = [
    "make_name_picker", "region_preset", "list_presets",
    "roll_hometown", "roll_birthday", "roll_secondary_country", "roll_high_school",
    "country_name", "country_abbrev", "flag_emoji",
    "nation_talent",
]
