"""
Immutable domain events.

Events are produced by aggregates during state transitions and
dispatched after the transaction commits. They are the extension
point for audit logging, analytics, side-effects, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events. Immutable after creation."""

    event_type: str
    occurred_at: str = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchResultRecorded(DomainEvent):
    """Emitted when a match result is successfully recorded."""

    event_type: str = "MATCH_RESULT_RECORDED"
    match_id: str = ""
    tournament_id: str = ""
    round_id: str = ""
    winner_ids: tuple[str, ...] = ()
    is_draw: bool = False
    rankings: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PlayerWithdrawn(DomainEvent):
    """Emitted when a player withdraws from a tournament."""

    event_type: str = "PLAYER_WITHDRAWN"
    player_id: str = ""
    tournament_id: str = ""
    withdrawal_round: int = 0
    reason: str = ""


@dataclass(frozen=True)
class MatchForfeited(DomainEvent):
    """Emitted when a player forfeits a match."""

    event_type: str = "MATCH_FORFEITED"
    match_id: str = ""
    forfeiting_player_id: str = ""
    winning_player_id: str = ""


@dataclass(frozen=True)
class UserRegistered(DomainEvent):
    """Emitted when a new user account is created."""

    event_type: str = "USER_REGISTERED"
    user_id: str = ""
    username: str = ""
    role: str = ""


@dataclass(frozen=True)
class UserLoggedIn(DomainEvent):
    """Emitted on successful login."""

    event_type: str = "USER_LOGGED_IN"
    user_id: str = ""
    username: str = ""
