"""
Domain models — Entities, Value Objects, Aggregates, State Machine.

This module is PURE: zero framework imports, zero infrastructure deps.
All business invariants are enforced here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from matchmaker.domain.errors import (
    InvalidMatchResultError,
    MatchAlreadyCompletedError,
)
from matchmaker.domain.events import DomainEvent, MatchResultRecorded


# ──────────────────────────────────────────────
#  Enums / State Machine
# ──────────────────────────────────────────────


class MatchState(str, Enum):
    """Explicit match lifecycle state machine.

    SCHEDULED → IN_PROGRESS → COMPLETED
                             ↘ FORFEITED
    """

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FORFEITED = "forfeited"

    @property
    def is_terminal(self) -> bool:
        return self in (MatchState.COMPLETED, MatchState.FORFEITED)


class PlayerStatus(str, Enum):
    """Player status within a tournament."""

    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    FORFEITED = "forfeited"


class Role(str, Enum):
    """User roles for authorization."""

    ADMIN = "ADMIN"
    ARBITER = "ARBITER"
    PLAYER = "PLAYER"


# ──────────────────────────────────────────────
#  Value Objects (immutable, identity-less)
# ──────────────────────────────────────────────


@dataclass(frozen=True)
class MatchId:
    value: str

    def __post_init__(self):
        if not self.value or not isinstance(self.value, str):
            raise ValueError("MatchId must be a non-empty string")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PlayerId:
    value: str

    def __post_init__(self):
        if not self.value or not isinstance(self.value, str):
            raise ValueError("PlayerId must be a non-empty string")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class TournamentId:
    value: str

    def __post_init__(self):
        if not self.value or not isinstance(self.value, str):
            raise ValueError("TournamentId must be a non-empty string")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class RoundId:
    value: str

    def __post_init__(self):
        if not self.value or not isinstance(self.value, str):
            raise ValueError("RoundId must be a non-empty string")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class MatchResult:
    """Validated match result value object.

    Invariants enforced at construction:
    - winner_ids must be a subset of participant_ids
    - rankings keys must be a subset of participant_ids
    - A draw has no winner_ids
    """

    winner_ids: list[str]
    is_draw: bool
    rankings: dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        winner_ids: list[str],
        is_draw: bool,
        participant_ids: list[str],
        rankings: dict[str, int] | None = None,
    ) -> MatchResult:
        """Factory that validates against match participants."""
        rankings = rankings or {}

        # Validate winner IDs are actual participants
        non_participants = set(winner_ids) - set(participant_ids)
        if non_participants:
            raise InvalidMatchResultError(
                f"Winner IDs {non_participants} are not match participants"
            )

        # Validate rankings keys
        non_participant_ranks = set(rankings.keys()) - set(participant_ids)
        if non_participant_ranks:
            raise InvalidMatchResultError(
                f"Ranking IDs {non_participant_ranks} are not match participants"
            )

        # Draw cannot have winners
        if is_draw and winner_ids:
            raise InvalidMatchResultError(
                "A draw cannot have winner IDs"
            )

        # Non-draw must have winners
        if not is_draw and not winner_ids:
            raise InvalidMatchResultError(
                "A non-draw result must have at least one winner"
            )

        return cls(winner_ids=winner_ids, is_draw=is_draw, rankings=rankings)

    def equals(self, other: MatchResult) -> bool:
        """Check if two results are semantically equal (for idempotency)."""
        return (
            sorted(self.winner_ids) == sorted(other.winner_ids)
            and self.is_draw == other.is_draw
            and self.rankings == other.rankings
        )


# ──────────────────────────────────────────────
#  Aggregates
# ──────────────────────────────────────────────


@dataclass
class MatchAggregate:
    """Match aggregate root — enforces all match invariants.

    State transitions happen ONLY through domain methods.
    Domain events are collected and dispatched after save.
    """

    id: str
    round_id: str
    tournament_id: str
    player_ids: list[str]
    state: MatchState = MatchState.SCHEDULED
    result: MatchResult | None = None
    auto_bye: bool = False
    scheduled_at: str = ""
    players_per_match: int = 2
    version: int = 0  # Optimistic locking
    _pending_events: list[DomainEvent] = field(
        default_factory=list, repr=False
    )

    def record_result(self, result: MatchResult) -> None:
        """Record a match result with full invariant enforcement.

        - Validates state transition (must be SCHEDULED or IN_PROGRESS)
        - Idempotent: re-recording the same result is a no-op
        - Produces MatchResultRecorded event
        """
        # Idempotency: if already completed with same result, no-op
        if self.state == MatchState.COMPLETED and self.result is not None:
            if self.result.equals(result):
                return  # Idempotent — same result already recorded
            raise MatchAlreadyCompletedError(self.id)

        # State guard
        if self.state.is_terminal:
            raise MatchAlreadyCompletedError(self.id)

        # Validate result against participants
        validated = MatchResult.create(
            winner_ids=result.winner_ids,
            is_draw=result.is_draw,
            participant_ids=self.player_ids,
            rankings=result.rankings,
        )

        # State transition
        self.state = MatchState.COMPLETED
        self.result = validated

        # Emit event
        self._pending_events.append(
            MatchResultRecorded(
                match_id=self.id,
                tournament_id=self.tournament_id,
                round_id=self.round_id,
                winner_ids=tuple(validated.winner_ids),
                is_draw=validated.is_draw,
                rankings=validated.rankings,
            )
        )

    def forfeit(self, forfeiting_player_id: str) -> None:
        """Player forfeits the match. Other player(s) win."""
        if self.state.is_terminal:
            raise MatchAlreadyCompletedError(self.id)

        if forfeiting_player_id not in self.player_ids:
            raise InvalidMatchResultError(
                f"Player {forfeiting_player_id} is not in this match"
            )

        winners = [p for p in self.player_ids if p != forfeiting_player_id]
        rankings = {p: 1 for p in winners}
        rankings[forfeiting_player_id] = len(self.player_ids)

        self.state = MatchState.FORFEITED
        self.result = MatchResult(
            winner_ids=winners, is_draw=False, rankings=rankings
        )

    def collect_events(self) -> list[DomainEvent]:
        """Drain pending events (call after successful save)."""
        events = list(self._pending_events)
        self._pending_events.clear()
        return events


@dataclass
class TournamentPlayer:
    """Tracks a player's status within a tournament."""

    player_id: str
    tournament_id: str
    status: PlayerStatus = PlayerStatus.ACTIVE
    withdrawal_round: int | None = None
    rounds_played: int = 0

    @property
    def is_active(self) -> bool:
        return self.status == PlayerStatus.ACTIVE

    def withdraw(self, current_round: int, min_rounds: int = 0) -> None:
        """Withdraw from the tournament with FIDE rule enforcement.

        FIDE C.04 Article 6:
        - Players can withdraw after completing the current round
        - Must have played at least `min_rounds` rounds
        """
        from matchmaker.domain.errors import WithdrawalNotAllowedError

        if not self.is_active:
            raise WithdrawalNotAllowedError(
                f"Player is already {self.status.value}"
            )

        if self.rounds_played < min_rounds:
            raise WithdrawalNotAllowedError(
                f"Must complete at least {min_rounds} rounds "
                f"(played {self.rounds_played})"
            )

        self.status = PlayerStatus.WITHDRAWN
        self.withdrawal_round = current_round


@dataclass
class User:
    """User entity for authentication."""

    id: str
    username: str
    password_hash: str
    role: Role
    player_id: str | None = None
    created_at: str = ""

    @staticmethod
    def generate_id() -> str:
        return uuid.uuid4().hex
