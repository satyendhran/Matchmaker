"""
Domain interfaces — ports that infrastructure must implement.

These define the contracts between the domain/application layers
and the outer infrastructure layer (Dependency Inversion Principle).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matchmaker.domain.events import DomainEvent
    from matchmaker.domain.models import MatchAggregate, TournamentPlayer, User


# ──────────────────────────────────────────────
#  Repository Interfaces (ISP — separate per aggregate)
# ──────────────────────────────────────────────


class IMatchRepository(ABC):
    """Port for match persistence."""

    @abstractmethod
    def get(self, match_id: str) -> MatchAggregate | None:
        """Load a match aggregate by ID."""
        ...

    @abstractmethod
    def save(self, match: MatchAggregate) -> None:
        """Save match (insert or update with version check)."""
        ...

    @abstractmethod
    def get_matches_for_round(self, round_id: str) -> list[MatchAggregate]:
        """Get all matches in a round."""
        ...

    @abstractmethod
    def has_active_match(self, tournament_id: str, player_id: str) -> bool:
        """Check if player has an unfinished match in the tournament."""
        ...


class IPlayerRepository(ABC):
    """Port for player persistence (separate from match — ISP)."""

    @abstractmethod
    def get_tournament_player(
        self, tournament_id: str, player_id: str
    ) -> TournamentPlayer | None:
        ...

    @abstractmethod
    def save_tournament_player(self, tp: TournamentPlayer) -> None:
        ...

    @abstractmethod
    def get_active_players(self, tournament_id: str) -> list[str]:
        """Get IDs of all active (non-withdrawn) players."""
        ...


class IUserRepository(ABC):
    """Port for user/auth persistence."""

    @abstractmethod
    def get_by_id(self, user_id: str) -> User | None:
        ...

    @abstractmethod
    def get_by_username(self, username: str) -> User | None:
        ...

    @abstractmethod
    def save(self, user: User) -> None:
        ...

    @abstractmethod
    def username_exists(self, username: str) -> bool:
        ...


# ──────────────────────────────────────────────
#  Auth Interface
# ──────────────────────────────────────────────


class IAuthProvider(ABC):
    """Port for authentication infrastructure (JWT, OAuth, etc)."""

    @abstractmethod
    def create_token(self, user_id: str, username: str, role: str) -> str:
        """Create an auth token for the given user."""
        ...

    @abstractmethod
    def validate_token(self, token: str) -> dict | None:
        """Validate token, return claims dict or None if invalid."""
        ...

    @abstractmethod
    def hash_password(self, password: str) -> str:
        ...

    @abstractmethod
    def verify_password(self, password: str, password_hash: str) -> bool:
        ...


# ──────────────────────────────────────────────
#  Event Dispatcher Interface
# ──────────────────────────────────────────────


class IEventDispatcher(ABC):
    """Port for dispatching domain events to subscribers."""

    @abstractmethod
    def dispatch(self, events: list[DomainEvent]) -> None:
        ...

    @abstractmethod
    def subscribe(self, event_type: str, handler: callable) -> None:
        ...
