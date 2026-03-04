"""
Domain policies — pluggable business rules.

Policies are the Open/Closed extension point: add new scoring rules,
withdrawal logic, or result validation without modifying existing code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from matchmaker.domain.models import MatchAggregate, MatchResult


# ──────────────────────────────────────────────
#  Scoring Policies
# ──────────────────────────────────────────────


class IScoringPolicy(ABC):
    """Strategy for calculating points from a match result."""

    @abstractmethod
    def get_name(self) -> str:
        ...

    @abstractmethod
    def calculate_points(
        self, player_id: str, match: MatchAggregate, result: MatchResult
    ) -> float:
        ...


class StandardScoringPolicy(IScoringPolicy):
    """Win=1, Draw=0.5, Loss=0 (FIDE standard)."""

    def get_name(self) -> str:
        return "fide_standard"

    def calculate_points(
        self, player_id: str, match: MatchAggregate, result: MatchResult
    ) -> float:
        if match.auto_bye:
            return 1.0
        if result.is_draw:
            return 0.5
        if player_id in result.winner_ids:
            return 1.0
        return 0.0


class ThreePointScoringPolicy(IScoringPolicy):
    """Win=3, Draw=1, Loss=0 (Football/Soccer style)."""

    def get_name(self) -> str:
        return "three_point"

    def calculate_points(
        self, player_id: str, match: MatchAggregate, result: MatchResult
    ) -> float:
        if result.is_draw:
            return 1.0
        if player_id in result.winner_ids:
            return 3.0
        return 0.0


# ──────────────────────────────────────────────
#  Withdrawal Policies
# ──────────────────────────────────────────────


class IWithdrawalPolicy(ABC):
    """Policy for determining if a player can withdraw."""

    @abstractmethod
    def get_name(self) -> str:
        ...

    @abstractmethod
    def can_withdraw(
        self,
        rounds_played: int,
        current_round: int,
        has_active_match: bool,
        min_rounds: int,
    ) -> tuple[bool, str]:
        """Returns (allowed, reason_if_denied)."""
        ...


class FideWithdrawalPolicy(IWithdrawalPolicy):
    """FIDE C.04 Article 6 withdrawal rules.

    - Cannot withdraw during an active match
    - Must have completed minimum rounds (configurable per tournament)
    - Past results preserved for tiebreak calculations
    """

    def get_name(self) -> str:
        return "fide_standard"

    def can_withdraw(
        self,
        rounds_played: int,
        current_round: int,
        has_active_match: bool,
        min_rounds: int,
    ) -> tuple[bool, str]:
        if has_active_match:
            return False, "Cannot withdraw during an active match. Finish or forfeit first."

        if rounds_played < min_rounds:
            return (
                False,
                f"Must complete at least {min_rounds} rounds (played {rounds_played})",
            )

        return True, ""


class OpenWithdrawalPolicy(IWithdrawalPolicy):
    """Liberal withdrawal — anytime, no restrictions."""

    def get_name(self) -> str:
        return "open"

    def can_withdraw(
        self,
        rounds_played: int,
        current_round: int,
        has_active_match: bool,
        min_rounds: int,
    ) -> tuple[bool, str]:
        return True, ""


# ──────────────────────────────────────────────
#  Result Submission Policies
# ──────────────────────────────────────────────


class IResultSubmissionPolicy(ABC):
    """Policy for who can submit a result."""

    @abstractmethod
    def can_submit(
        self, user_role: str, user_player_id: str | None, match_player_ids: list[str]
    ) -> tuple[bool, str]:
        ...


class StandardResultSubmissionPolicy(IResultSubmissionPolicy):
    """Admins and arbiters can submit any result.
    Players can only submit results for their own matches.
    """

    def can_submit(
        self, user_role: str, user_player_id: str | None, match_player_ids: list[str]
    ) -> tuple[bool, str]:
        if user_role in ("ADMIN", "ARBITER"):
            return True, ""

        if user_role == "PLAYER" and user_player_id in match_player_ids:
            return True, ""

        return False, "You are not authorized to submit results for this match"
