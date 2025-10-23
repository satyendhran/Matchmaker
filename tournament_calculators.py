from tournament_core import IPointsCalculator, Match, MatchResult


class StandardPointsCalculator(IPointsCalculator):
    """
    Standard points calculator.
    Win = 1 point, Draw = 0.5 points, Loss = 0 points.
    """

    def get_calculator_name(self) -> str:
        return "standard"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """Calculate points for standard scoring."""
        if result.is_draw:
            # Equal points for all players in a draw
            return 1.0 / len(match.player_ids)

        if player_id in result.winner_ids:
            return 1.0

        return 0.0


class ThreePointsCalculator(IPointsCalculator):
    """
    Three-points-for-win calculator (like soccer).
    Win = 3 points, Draw = 1 point, Loss = 0 points.
    """

    def get_calculator_name(self) -> str:
        return "three_point"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """Calculate points for three-point scoring."""
        if result.is_draw:
            return 1.0

        if player_id in result.winner_ids:
            return 3.0

        return 0.0


class RankingPointsCalculator(IPointsCalculator):
    """
    Ranking-based points calculator for n-player games.
    Points awarded based on finishing position.
    1st place = n points, 2nd = n-1 points, etc.
    """

    def get_calculator_name(self) -> str:
        return "ranking"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """Calculate points based on ranking."""
        if not result.rankings or player_id not in result.rankings:
            return 0.0

        rank = result.rankings[player_id]
        total_players = len(match.player_ids)

        # Award points: 1st place = total_players points, 2nd = total_players-1, etc.
        points = max(0, total_players - rank + 1)

        return float(points)


class EloCalculator(IPointsCalculator):
    """
    Elo-style rating calculator.
    Points based on expected vs actual performance.
    """

    def __init__(self, k_factor: float = 32):
        self.k_factor = k_factor

    def get_calculator_name(self) -> str:
        return "elo"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """
        Calculate Elo rating change.
        Note: This is a simplified implementation.
        Full Elo requires opponent ratings.
        """
        if result.is_draw:
            actual_score = 0.5
        elif player_id in result.winner_ids:
            actual_score = 1.0
        else:
            actual_score = 0.0

        # Simplified: assume expected score is 0.5 (equal opponents)
        expected_score = 0.5

        rating_change = self.k_factor * (actual_score - expected_score)

        return rating_change


class PercentagePointsCalculator(IPointsCalculator):
    """
    Percentage-based calculator for n-player games.
    Points distributed based on how many players you beat.
    """

    def get_calculator_name(self) -> str:
        return "percentage"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """Calculate points as percentage of players beaten."""
        if not result.rankings or player_id not in result.rankings:
            return 0.0

        rank = result.rankings[player_id]
        total_players = len(match.player_ids)

        # Points = (players beaten / total players) * 100
        players_beaten = total_players - rank
        percentage = (
            (players_beaten / (total_players - 1)) * 100 if total_players > 1 else 0
        )

        return percentage


class CustomWeightedCalculator(IPointsCalculator):
    """
    Custom weighted calculator allowing different point values.
    Useful for different game types or tournament formats.
    """

    def __init__(self, weights: dict[int, float]):
        """
        Initialize with custom weights.

        Args:
            weights: dict mapping rank to points (e.g., {1: 10, 2: 5, 3: 2, 4: 1})
        """
        self.weights = weights

    def get_calculator_name(self) -> str:
        return "custom_weighted"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """Calculate points using custom weights."""
        if result.is_draw:
            # Average points for all players in draw
            total_points = sum(self.weights.values())
            return total_points / len(match.player_ids)

        if not result.rankings or player_id not in result.rankings:
            return 0.0

        rank = result.rankings[player_id]
        return self.weights.get(rank, 0.0)
