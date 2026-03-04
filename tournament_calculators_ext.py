"""
Extended Points Calculators
============================
New calculators: Buchholz, Sonneborn-Berger, Direct Encounter,
Bye points, and Glicko-2 rating.
"""

import math
from typing import Any

from tournament_core import IPointsCalculator, ITournamentRepository, Match, MatchResult







class BuchholzCalculator(IPointsCalculator):
    """Buchholz score: sum of opponents' points.

    Used as a tiebreak in Swiss tournaments.
    Requires access to the repository to look up opponent scores.
    """

    def __init__(self, repository: ITournamentRepository | None = None):
        self._repository = repository

    def get_calculator_name(self) -> str:
        return "buchholz"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """Return Buchholz score for the player based on this single match.

        For a full Buchholz calculation across all rounds, use
        `calculate_full_buchholz()` instead.
        """
        if not self._repository:
            return 0.0

        opponent_ids = [pid for pid in match.player_ids if pid != player_id]
        total = 0.0
        for opp_id in opponent_ids:
            stats = self._get_player_stats(match.tournament_id, opp_id)
            total += stats.get("points", 0.0)
        return total

    def calculate_full_buchholz(
        self, tournament_id: str, player_id: str, all_matches: list[Match]
    ) -> float:
        """Sum of ALL opponents' current scores across a tournament."""
        if not self._repository:
            return 0.0

        opponent_ids: set[str] = set()
        for m in all_matches:
            if player_id in m.player_ids and not m.auto_bye:
                opponent_ids.update(p for p in m.player_ids if p != player_id)

        total = 0.0
        for opp_id in opponent_ids:
            stats = self._get_player_stats(tournament_id, opp_id)
            total += stats.get("points", 0.0)
        return total

    def _get_player_stats(self, tournament_id: str, player_id: str) -> dict:
        if not self._repository:
            return {}
        all_stats = self._repository.get_stats(tournament_id)
        for s in all_stats:
            if s.get("player_id") == player_id:
                return s
        return {}







class SonnebornBergerCalculator(IPointsCalculator):
    """Sonneborn-Berger score: sum of (score against opponent × opponent's total).

    For each opponent:
      SB += (points_earned_vs_opponent) * (opponent_total_points)
    """

    def __init__(self, repository: ITournamentRepository | None = None):
        self._repository = repository

    def get_calculator_name(self) -> str:
        return "sonneborn_berger"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """Per-match SB contribution."""
        if not self._repository:
            return 0.0

        opponent_ids = [pid for pid in match.player_ids if pid != player_id]
        sb_total = 0.0

        
        if result.is_draw:
            earned = 0.5
        elif player_id in result.winner_ids:
            earned = 1.0
        else:
            earned = 0.0

        for opp_id in opponent_ids:
            opp_stats = self._get_player_stats(match.tournament_id, opp_id)
            opp_total = opp_stats.get("points", 0.0)
            sb_total += earned * opp_total

        return sb_total

    def _get_player_stats(self, tournament_id: str, player_id: str) -> dict:
        if not self._repository:
            return {}
        all_stats = self._repository.get_stats(tournament_id)
        for s in all_stats:
            if s.get("player_id") == player_id:
                return s
        return {}







class DirectEncounterCalculator(IPointsCalculator):
    """Head-to-head tiebreak: returns 1 if player beat opponent in this
    match, 0.5 for draw, 0 for loss. Sum across all encounters for full
    tiebreak.
    """

    def get_calculator_name(self) -> str:
        return "direct_encounter"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        if result.is_draw:
            return 0.5
        if player_id in result.winner_ids:
            return 1.0
        return 0.0







class ByeCalculator(IPointsCalculator):
    """Awards configurable bye points (default ½ — FIDE-compliant).

    Only applies to auto-bye matches; for regular matches returns 0.
    """

    def __init__(self, bye_points: float = 0.5):
        self.bye_points = bye_points

    def get_calculator_name(self) -> str:
        return "bye"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        if match.auto_bye and player_id in match.player_ids:
            return self.bye_points
        return 0.0







class GlickoRatingCalculator(IPointsCalculator):
    """Glicko-2 rating change calculation.

    This calculator computes the rating change for a single match.
    For a full Glicko-2 update across a rating period (multiple games),
    use `calculate_rating_period()`.

    Reference: Mark Glickman, "Example of the Glicko-2 system"
    """

    TAU = 0.5  

    def get_calculator_name(self) -> str:
        return "glicko"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """Simplified: returns expected score adjustment (not full Glicko).

        For actual Glicko-2 rating updates, use `calculate_rating_change()`.
        This method is compatible with the standard IPointsCalculator interface.
        """
        if result.is_draw:
            return 0.5
        if player_id in result.winner_ids:
            return 1.0
        return 0.0

    @staticmethod
    def calculate_rating_change(
        player_rating: float,
        player_rd: float,
        player_volatility: float,
        opponent_rating: float,
        opponent_rd: float,
        score: float,  
    ) -> tuple[float, float, float]:
        """Compute new (rating, RD, volatility) after a single game.

        Returns:
            (new_rating, new_rd, new_volatility)
        """
        
        mu = (player_rating - 1500) / 173.7178
        phi = player_rd / 173.7178
        sigma = player_volatility

        mu_j = (opponent_rating - 1500) / 173.7178
        phi_j = opponent_rd / 173.7178

        
        g_phi_j = 1.0 / math.sqrt(1 + 3 * phi_j**2 / math.pi**2)

        
        E = 1.0 / (1 + math.exp(-g_phi_j * (mu - mu_j)))

        
        v = 1.0 / (g_phi_j**2 * E * (1 - E))

        
        delta = v * g_phi_j * (score - E)

        
        new_sigma = GlickoRatingCalculator._compute_new_volatility(
            sigma, phi, v, delta
        )

        
        phi_star = math.sqrt(phi**2 + new_sigma**2)

        
        new_phi = 1.0 / math.sqrt(1.0 / phi_star**2 + 1.0 / v)
        new_mu = mu + new_phi**2 * g_phi_j * (score - E)

        
        new_rating = 173.7178 * new_mu + 1500
        new_rd = 173.7178 * new_phi

        return (new_rating, new_rd, new_sigma)

    @staticmethod
    def _compute_new_volatility(
        sigma: float, phi: float, v: float, delta: float
    ) -> float:
        """Iterative algorithm to compute new volatility (Step 5 of Glicko-2)."""
        tau = GlickoRatingCalculator.TAU
        a = math.log(sigma**2)
        epsilon = 0.000001

        def f(x: float) -> float:
            ex = math.exp(x)
            d2 = delta**2
            p2 = phi**2
            return (
                ex * (d2 - p2 - v - ex) / (2 * (p2 + v + ex) ** 2)
                - (x - a) / tau**2
            )

        
        A = a
        if delta**2 > phi**2 + v:
            B = math.log(delta**2 - phi**2 - v)
        else:
            k = 1
            while f(a - k * tau) < 0:
                k += 1
            B = a - k * tau

        
        fa = f(A)
        fb = f(B)
        while abs(B - A) > epsilon:
            C = A + (A - B) * fa / (fb - fa)
            fc = f(C)
            if fc * fb <= 0:
                A = B
                fa = fb
            else:
                fa /= 2
            B = C
            fb = fc

        return math.exp(A / 2)
