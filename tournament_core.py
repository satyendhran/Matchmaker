"""
Core interfaces and base classes for the tournament system.
Following SOLID principles for extensibility.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import datetime
import uuid


@dataclass
class Player:
    """Value object representing a player."""

    id: str
    name: str
    created_at: str


@dataclass
class Match:
    """Value object representing a match between players."""

    id: str
    round_id: str
    tournament_id: str
    player_ids: list[str]  # Changed from p1_id, p2_id to support n-player games
    scheduled_at: str
    result: str | None = None
    winner_ids: list[str] | None = None  # Support multiple winners/ties
    rankings: dict[str, int] | None = (
        None  # player_id -> rank (1=winner, 2=second, etc)
    )
    auto_bye: bool = False
    players_per_match: int = 2  # Default to 2-player games


@dataclass
class MatchResult:
    """Value object for match results."""

    match_id: str
    winner_ids: list[str]
    rankings: dict[str, int]  # player_id -> rank
    is_draw: bool = False


@dataclass
class RoundConfig:
    """Configuration for creating a round."""

    tournament_id: str
    round_type: str
    players_per_match: int = 2
    additional_params: dict[str, Any] | None = None


class IMatchmakingStrategy(ABC):
    """
    Strategy interface for different matchmaking algorithms.
    Follows Strategy Pattern and Open/Closed Principle.
    """

    @abstractmethod
    def create_matches(
        self,
        tournament_id: str,
        round_id: str,
        available_players: list[str],
        config: RoundConfig,
    ) -> dict[str, Any]:
        """
        Create matches for a round.

        Returns:
            dict with keys:
            - matches: list[Match]
            - waiting_players: list[str]
            - metadata: dict[str, Any]
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return the name of this strategy."""
        pass

    @abstractmethod
    def supports_players_per_match(self, n: int) -> bool:
        """Check if this strategy supports n-player matches."""
        pass


class IPointsCalculator(ABC):
    """
    Interface for calculating points from match results.
    Follows Single Responsibility Principle.
    """

    @abstractmethod
    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        """Calculate points earned by a player in a match."""
        pass

    @abstractmethod
    def get_calculator_name(self) -> str:
        """Return the name of this calculator."""
        pass


class ITournamentRepository(ABC):
    """
    Repository interface for data persistence.
    Follows Dependency Inversion Principle.
    """

    @abstractmethod
    def save_player(self, player: Player) -> None:
        pass

    @abstractmethod
    def get_player(self, player_id: str) -> Player | None:
        pass

    @abstractmethod
    def list_players(self) -> list[Player]:
        pass

    @abstractmethod
    def save_match(self, match: Match) -> None:
        pass

    @abstractmethod
    def get_match(self, match_id: str) -> Match | None:
        pass

    @abstractmethod
    def list_matches_for_round(self, round_id: str) -> list[Match]:
        pass

    @abstractmethod
    def update_match_result(self, match_id: str, result: MatchResult) -> None:
        pass

    @abstractmethod
    def save_tournament(self, tournament_id: str, name: str, created_at: str) -> None:
        pass

    @abstractmethod
    def get_tournament_players(self, tournament_id: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def add_player_to_tournament(self, tournament_id: str, player_id: str) -> None:
        pass

    @abstractmethod
    def save_round(
        self,
        round_id: str,
        tournament_id: str,
        round_type: str,
        ordinal: int,
        created_at: str,
    ) -> None:
        pass

    @abstractmethod
    def get_stats(self, tournament_id: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def update_player_stats(
        self, tournament_id: str, player_id: str, stats: dict[str, float]
    ) -> None:
        pass

    @abstractmethod
    def eliminate_player(self, tournament_id: str, player_id: str) -> None:
        """Mark a player as eliminated from tournament."""
        pass

    @abstractmethod
    def activate_player(self, tournament_id: str, player_id: str) -> None:
        """Mark a player as active in tournament."""
        pass

    @abstractmethod
    def get_round_type(self, round_id: str) -> str:
        """Get the type of a round."""
        pass


class MatchmakingStrategyRegistry:
    """
    Registry for matchmaking strategies.
    Allows dynamic loading of strategies at runtime.
    """

    def __init__(self):
        self._strategies: dict[str, IMatchmakingStrategy] = {}

    def register(self, strategy: IMatchmakingStrategy) -> None:
        """Register a new matchmaking strategy."""
        name = strategy.get_strategy_name()
        self._strategies[name] = strategy

    def get_strategy(self, name: str) -> IMatchmakingStrategy | None:
        """Get a strategy by name."""
        return self._strategies.get(name)

    def list_strategies(self) -> list[str]:
        """list all registered strategy names."""
        return list(self._strategies.keys())

    def get_strategies_for_player_count(self, n: int) -> list[str]:
        """Get strategies that support n-player matches."""
        return [
            name
            for name, strategy in self._strategies.items()
            if strategy.supports_players_per_match(n)
        ]


class PointsCalculatorRegistry:
    """Registry for points calculators."""

    def __init__(self):
        self._calculators: dict[str, IPointsCalculator] = {}

    def register(self, calculator: IPointsCalculator) -> None:
        """Register a new points calculator."""
        name = calculator.get_calculator_name()
        self._calculators[name] = calculator

    def get_calculator(self, name: str) -> IPointsCalculator | None:
        """Get a calculator by name."""
        return self._calculators.get(name)

    def list_calculators(self) -> list[str]:
        """list all registered calculator names."""
        return list(self._calculators.keys())


def generate_id() -> str:
    """Generate a unique ID."""
    return uuid.uuid4().hex


def now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
