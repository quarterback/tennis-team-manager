"""Deterministic tennis match engine (singles full + fast, dual-match team layer)."""
from .state import Player, PlayerStats, MatchState, MatchContext, random_player, ATTRS
from .format import MatchFormat, PRESETS, DEFAULT
from .match import simulate_match, MatchResult
from .fast import simulate_fast
from .dual import simulate_dual, Team, DualResult
from .doubles import (simulate_doubles, DoublesTeam, DoublesResult,
                      doubles_rating, serve_rating, return_rating,
                      net_rating, poach_rating)
from .tournament import (run_tournament, TournamentResult, TourMatch,
                         round_name, finish_label, seed_count)
from .render import box_score, pbp_text

__all__ = [
    "Player", "PlayerStats", "MatchState", "MatchContext", "random_player", "ATTRS",
    "MatchFormat", "PRESETS", "DEFAULT",
    "simulate_match", "MatchResult", "simulate_fast",
    "simulate_dual", "Team", "DualResult",
    "simulate_doubles", "DoublesTeam", "DoublesResult", "doubles_rating",
    "serve_rating", "return_rating", "net_rating", "poach_rating",
    "run_tournament", "TournamentResult", "TourMatch", "round_name", "finish_label",
    "seed_count",
    "box_score", "pbp_text",
]
