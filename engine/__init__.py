"""Deterministic tennis match engine (singles full + fast, dual-match team layer)."""
from .state import Player, PlayerStats, MatchState, MatchContext, random_player, ATTRS
from .format import MatchFormat, PRESETS, DEFAULT
from .match import simulate_match, MatchResult
from .fast import simulate_fast
from .dual import simulate_dual, Team, DualResult
from .tournament import (run_tournament, TournamentResult, TourMatch,
                         round_name, finish_label)
from .render import box_score, pbp_text

__all__ = [
    "Player", "PlayerStats", "MatchState", "MatchContext", "random_player", "ATTRS",
    "MatchFormat", "PRESETS", "DEFAULT",
    "simulate_match", "MatchResult", "simulate_fast",
    "simulate_dual", "Team", "DualResult",
    "run_tournament", "TournamentResult", "TourMatch", "round_name", "finish_label",
    "box_score", "pbp_text",
]
