"""
Service layer implementing business logic.
Orchestrates strategies, calculators, and repository.
"""

from typing import Any
from tournament_core import (
    Player,
    Match,
    MatchResult,
    RoundConfig,
    ITournamentRepository,
    MatchmakingStrategyRegistry,
    PointsCalculatorRegistry,
    IPointsCalculator,
    generate_id,
    now_iso,
)


class TournamentService:
    """
    Main service orchestrating tournament operations.
    Follows Dependency Inversion and Single Responsibility principles.
    """

    def __init__(
        self,
        repository: ITournamentRepository,
        strategy_registry: MatchmakingStrategyRegistry,
        calculator_registry: PointsCalculatorRegistry,
    ):
        self.repository = repository
        self.strategy_registry = strategy_registry
        self.calculator_registry = calculator_registry
        self.default_calculator = "standard"

    def create_player(self, name: str) -> str:
        """Create a new player."""
        player = Player(id=generate_id(), name=name, created_at=now_iso())
        self.repository.save_player(player)
        return player.id

    def list_players(self) -> list[Player]:
        """list all players."""
        return self.repository.list_players()

    def create_tournament(self, name: str) -> str:
        """Create a new tournament."""
        tournament_id = generate_id()
        self.repository.save_tournament(tournament_id, name, now_iso())
        return tournament_id

    def add_player_to_tournament(self, tournament_id: str, player_id: str) -> None:
        """Add a player to a tournament."""
        self.repository.add_player_to_tournament(tournament_id, player_id)

    def create_round(self, config: RoundConfig) -> dict[str, Any]:
        """
        Create a new round with specified strategy.

        Args:
            config: Round configuration including strategy type and parameters

        Returns:
            dict with round_id and matchmaking results
        """
        # Get the strategy
        strategy = self.strategy_registry.get_strategy(config.round_type)
        if not strategy:
            raise ValueError(f"Unknown strategy: {config.round_type}")

        # Check if strategy supports the player count
        if not strategy.supports_players_per_match(config.players_per_match):
            raise ValueError(
                f"Strategy '{config.round_type}' doesn't support "
                f"{config.players_per_match}-player matches"
            )

        # Get available players
        tournament_players = self.repository.get_tournament_players(
            config.tournament_id
        )
        available_players = [
            p["player_id"] for p in tournament_players if p.get("able_to_play", 1) == 1
        ]

        if not available_players:
            raise ValueError("No available players for this round")

        # Check for pending matches
        if self._has_pending_matches(config.tournament_id):
            raise ValueError("Previous round has pending matches")

        # Create the round
        round_id = generate_id()
        ordinal = self._get_next_round_ordinal(config.tournament_id)
        self.repository.save_round(
            round_id, config.tournament_id, config.round_type, ordinal, now_iso()
        )

        # Create matches using strategy
        result = strategy.create_matches(
            config.tournament_id, round_id, available_players, config
        )

        return {
            "round_id": round_id,
            "ordinal": ordinal,
            "matches": result["matches"],
            "waiting_players": result.get("waiting_players", []),
            "metadata": result.get("metadata", {}),
        }

    def record_match_result(
        self, match_id: str, result: MatchResult, calculator_name: str | None = None
    ) -> None:
        """
        Record the result of a match and update statistics.

        Args:
            match_id: ID of the match
            result: Match result with winners and rankings
            calculator_name: Name of points calculator to use (optional)
        """
        # Get match details first
        match = self.repository.get_match(match_id)
        if not match:
            raise ValueError(f"Match not found: {match_id}")

        # Check if this is a knockout match
        round_type = self.repository.get_round_type(match.round_id)
        is_knockout = round_type == "knockout"

        # Update match result in database
        self.repository.update_match_result(match_id, result)

        # Get calculator
        calc_name = calculator_name or self.default_calculator
        calculator = self.calculator_registry.get_calculator(calc_name)
        if not calculator:
            calculator = self.calculator_registry.get_calculator(
                self.default_calculator
            )

        # Calculate and update stats for each player
        self._update_player_statistics(match, result, calculator)

        # Handle elimination for knockout tournaments
        if is_knockout and not result.is_draw:
            self._handle_knockout_elimination(match, result)

    def get_standings(self, tournament_id: str) -> list[dict[str, Any]]:
        """Get current tournament standings."""
        return self.repository.get_stats(tournament_id)

    def list_available_strategies(self) -> list[str]:
        """list all available matchmaking strategies."""
        return self.strategy_registry.list_strategies()

    def list_available_calculators(self) -> list[str]:
        """list all available points calculators."""
        return self.calculator_registry.list_calculators()

    def get_strategies_for_player_count(self, n: int) -> list[str]:
        """Get strategies that support n-player matches."""
        return self.strategy_registry.get_strategies_for_player_count(n)

    def set_default_calculator(self, calculator_name: str) -> None:
        """Set the default points calculator for the tournament."""
        if calculator_name not in self.calculator_registry.list_calculators():
            raise ValueError(f"Unknown calculator: {calculator_name}")
        self.default_calculator = calculator_name

    # Private helper methods

    def _has_pending_matches(self, tournament_id: str) -> bool:
        """Check if there are any pending matches in the tournament."""
        # This should be implemented in repository
        return False

    def _get_next_round_ordinal(self, tournament_id: str) -> int:
        """Get the ordinal number for the next round."""
        # This should query the repository for existing rounds
        return 1

    def _update_player_statistics(
        self, match: Match, result: MatchResult, calculator: IPointsCalculator
    ) -> None:
        """Update statistics for all players in a match."""
        for player_id in match.player_ids:
            points = calculator.calculate_points(player_id, match, result)

            # Determine win/draw/loss
            stats_update = {"matches_played": 1}

            if result.is_draw:
                stats_update["draws"] = 1
                stats_update["points"] = points
            elif player_id in result.winner_ids:
                stats_update["wins"] = 1
                stats_update["points"] = points
            else:
                stats_update["losses"] = 1
                stats_update["points"] = points

            # Get current stats and add increments
            current_stats = self._get_player_stats(match.tournament_id, player_id)
            for key, value in stats_update.items():
                current_stats[key] = current_stats.get(key, 0) + value

            self.repository.update_player_stats(
                match.tournament_id, player_id, current_stats
            )

    def _get_player_stats(self, tournament_id: str, player_id: str) -> dict[str, float]:
        """Get current stats for a player."""
        all_stats = self.repository.get_stats(tournament_id)
        for stat in all_stats:
            if stat["player_id"] == player_id:
                return stat
        return {"wins": 0, "draws": 0, "losses": 0, "matches_played": 0, "points": 0}

    def _handle_knockout_elimination(self, match: Match, result: MatchResult) -> None:
        """Handle player elimination in knockout matches."""
        # Eliminate all non-winners
        for player_id in match.player_ids:
            if player_id not in result.winner_ids:
                # Mark player as eliminated
                self.repository.eliminate_player(match.tournament_id, player_id)

        # Ensure winners remain active
        for winner_id in result.winner_ids:
            self.repository.activate_player(match.tournament_id, winner_id)


class RoundFactory:
    """
    Factory for creating rounds with different configurations.
    Simplifies round creation with preset configurations.
    """

    @staticmethod
    def create_standard_roundrobin(tournament_id: str) -> RoundConfig:
        """Create configuration for standard 2-player round-robin."""
        return RoundConfig(
            tournament_id=tournament_id, round_type="roundrobin", players_per_match=2
        )

    @staticmethod
    def create_knockout(tournament_id: str, players_per_match: int = 2) -> RoundConfig:
        """Create configuration for knockout round."""
        return RoundConfig(
            tournament_id=tournament_id,
            round_type="knockout",
            players_per_match=players_per_match,
        )

    @staticmethod
    def create_swiss(tournament_id: str) -> RoundConfig:
        """Create configuration for Swiss system round."""
        return RoundConfig(
            tournament_id=tournament_id, round_type="swiss", players_per_match=2
        )

    @staticmethod
    def create_freeforall(tournament_id: str) -> RoundConfig:
        """Create configuration for free-for-all round."""
        return RoundConfig(
            tournament_id=tournament_id,
            round_type="freeforall",
            players_per_match=0,  # Will use all players
        )

    @staticmethod
    def create_custom(
        tournament_id: str,
        round_type: str,
        players_per_match: int,
        additional_params: dict[str, Any] | None = None,
    ) -> RoundConfig:
        """Create custom round configuration."""
        return RoundConfig(
            tournament_id=tournament_id,
            round_type=round_type,
            players_per_match=players_per_match,
            additional_params=additional_params or {},
        )
