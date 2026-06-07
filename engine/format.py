"""
Match format — the optional, toggleable scoring rules.

Each field is an independent switch (a "checkbox feature"): no-ad scoring,
whether sets use a tiebreak at 6-6 (vs an advantage set), the tiebreak
target, and how the deciding set is played (full set / advantage set /
match-tiebreak). Presets bundle common real-world configurations.

These are pure data — the engine reads them; nothing here has side effects,
so a format is safe to serialise (e.g. straight from UI checkbox state).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class MatchFormat:
    best_of: int = 3                     # 3 or 5 sets (ignored when pro_set)

    # Per-set scoring
    no_ad: bool = False                  # sudden-death deciding point at deuce
    set_games: int = 6                   # games to win a normal set (win by 2)
    set_tiebreak: bool = True            # tiebreak at games-all (False ⇒ advantage set)
    set_tiebreak_target: int = 7         # points to win a set tiebreak (win by 2)

    # Deciding-set scoring (independent of the rules above)
    final_set_tiebreak: bool = True      # deciding set is a match tiebreak…
    final_set_tiebreak_target: int = 10  # …to this many points (win by 2)
    # If final_set_tiebreak is False, the deciding set is a normal set, using
    # `set_tiebreak`/`set_tiebreak_target` (advantage set when set_tiebreak False).

    # Single-set alternatives (override best_of when on)
    pro_set: bool = False                # whole match is ONE long set…
    pro_set_games: int = 8               # …to this many games (win by 2), tiebreak at games-all

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MatchFormat":
        fields = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in fields})


# --- Named presets (real-world configurations) ---------------------------

PRESETS: dict[str, MatchFormat] = {
    # NCAA dual singles: best-of-3, no-ad, tiebreak sets, deciding set is a
    # full third set (no match tiebreak).
    "ncaa_dual": MatchFormat(
        best_of=3, no_ad=True, set_tiebreak=True,
        final_set_tiebreak=False,
    ),
    # ITF/ATP-style best-of-3 with a 10-point match tiebreak third set.
    "best_of_3_mtb": MatchFormat(
        best_of=3, no_ad=False, set_tiebreak=True,
        final_set_tiebreak=True, final_set_tiebreak_target=10,
    ),
    # Grand-slam-ish best-of-5, ad scoring, 10-point final-set tiebreak.
    "grand_slam": MatchFormat(
        best_of=5, no_ad=False, set_tiebreak=True,
        final_set_tiebreak=True, final_set_tiebreak_target=10,
    ),
    # Classic advantage-set everywhere (no tiebreaks at all).
    "advantage": MatchFormat(
        best_of=3, no_ad=False, set_tiebreak=False,
        final_set_tiebreak=False,
    ),
    # 8-game pro set: one set to 8 games, win by 2, 7-point tiebreak at 8-8.
    "pro_set_8": MatchFormat(
        no_ad=True, pro_set=True, pro_set_games=8,
        set_tiebreak=True, set_tiebreak_target=7,
    ),
}

DEFAULT = PRESETS["best_of_3_mtb"]
