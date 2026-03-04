"""
Application use cases — orchestrate domain logic.

Each use case is a single, focused operation. Authorization
happens HERE, not in controllers or repositories.
"""

from __future__ import annotations

from matchmaker.domain.errors import (
    AuthorizationError,
    InvalidMatchResultError,
    MatchNotFoundError,
    WithdrawalNotAllowedError,
)
from matchmaker.domain.events import MatchForfeited, PlayerWithdrawn
from matchmaker.domain.interfaces import (
    IEventDispatcher,
    IMatchRepository,
    IPlayerRepository,
)
from matchmaker.domain.models import (
    MatchResult,
    MatchState,
    PlayerStatus,
    TournamentPlayer,
)
from matchmaker.domain.policies import (
    IResultSubmissionPolicy,
    IScoringPolicy,
    IWithdrawalPolicy,
)


class RecordMatchResultUseCase:
    """Record a match result — the FIXED version of the critical flow.

    This use case:
    1. Loads match from repository (proper JSON deserialization — fixes RC-1)
    2. Validates result against match participants (fixes RC-5)
    3. Enforces state transitions via aggregate (fixes RC-4 idempotency)
    4. Saves with optimistic locking (fixes RC-3 concurrency)
    5. Dispatches domain events
    """

    def __init__(
        self,
        match_repo: IMatchRepository,
        event_dispatcher: IEventDispatcher,
        scoring_policy: IScoringPolicy | None = None,
        result_policy: IResultSubmissionPolicy | None = None,
    ):
        self._match_repo = match_repo
        self._events = event_dispatcher
        self._scoring = scoring_policy
        self._result_policy = result_policy

    def execute(
        self,
        match_id: str,
        winner_ids: list[str],
        is_draw: bool,
        rankings: dict[str, int] | None = None,
        user_role: str = "ADMIN",
        user_player_id: str | None = None,
        calculator_name: str | None = None,
    ) -> dict:
        """Execute the use case. Returns result summary dict."""

        # 1. Load match aggregate (single source of truth)
        match = self._match_repo.get(match_id)
        if match is None:
            raise MatchNotFoundError(match_id)

        # 2. Authorization check (in use case, not controller)
        if self._result_policy:
            allowed, reason = self._result_policy.can_submit(
                user_role, user_player_id, match.player_ids
            )
            if not allowed:
                raise AuthorizationError(reason)

        # 3. Build result (validates against participants)
        result = MatchResult.create(
            winner_ids=winner_ids,
            is_draw=is_draw,
            participant_ids=match.player_ids,
            rankings=rankings,
        )

        # 4. Aggregate enforces state transition + idempotency
        match.record_result(result)

        # 5. Save with version check (optimistic locking)
        self._match_repo.save(match)

        # 6. Dispatch domain events
        events = match.collect_events()
        self._events.dispatch(events)

        return {
            "match_id": match_id,
            "state": match.state.value,
            "is_draw": is_draw,
            "winner_ids": winner_ids,
        }


class WithdrawPlayerUseCase:
    """Withdraw a player from a tournament per FIDE rules.

    FIDE C.04 Article 6:
    - Must have completed minimum rounds
    - Cannot withdraw during an active match
    - Past results are preserved
    - Future opponents receive bye points
    """

    def __init__(
        self,
        player_repo: IPlayerRepository,
        match_repo: IMatchRepository,
        event_dispatcher: IEventDispatcher,
        withdrawal_policy: IWithdrawalPolicy,
    ):
        self._player_repo = player_repo
        self._match_repo = match_repo
        self._events = event_dispatcher
        self._policy = withdrawal_policy

    def execute(
        self,
        tournament_id: str,
        player_id: str,
        current_round: int,
        min_rounds: int = 0,
        user_role: str = "ADMIN",
        user_player_id: str | None = None,
        reason: str = "",
    ) -> dict:
        # Authorization: only the player themselves, admin, or arbiter
        if user_role == "PLAYER" and user_player_id != player_id:
            raise AuthorizationError("Players can only withdraw themselves")

        # Load player tournament record
        tp = self._player_repo.get_tournament_player(tournament_id, player_id)
        if tp is None:
            tp = TournamentPlayer(
                player_id=player_id, tournament_id=tournament_id
            )

        # Check for active matches
        has_active = self._match_repo.has_active_match(tournament_id, player_id)

        # Apply withdrawal policy
        allowed, denial_reason = self._policy.can_withdraw(
            rounds_played=tp.rounds_played,
            current_round=current_round,
            has_active_match=has_active,
            min_rounds=min_rounds,
        )
        if not allowed:
            raise WithdrawalNotAllowedError(denial_reason)

        # Withdraw
        tp.withdraw(current_round, min_rounds=0)  # Policy already validated
        self._player_repo.save_tournament_player(tp)

        # Emit event
        self._events.dispatch(
            [
                PlayerWithdrawn(
                    player_id=player_id,
                    tournament_id=tournament_id,
                    withdrawal_round=current_round,
                    reason=reason,
                )
            ]
        )

        return {
            "player_id": player_id,
            "tournament_id": tournament_id,
            "status": "withdrawn",
            "withdrawal_round": current_round,
        }


class ForfeitMatchUseCase:
    """Player forfeits an active match."""

    def __init__(
        self,
        match_repo: IMatchRepository,
        event_dispatcher: IEventDispatcher,
    ):
        self._match_repo = match_repo
        self._events = event_dispatcher

    def execute(
        self,
        match_id: str,
        forfeiting_player_id: str,
        user_role: str = "ADMIN",
        user_player_id: str | None = None,
    ) -> dict:
        match = self._match_repo.get(match_id)
        if match is None:
            raise MatchNotFoundError(match_id)

        # Authorization
        if user_role == "PLAYER" and user_player_id != forfeiting_player_id:
            raise AuthorizationError("Players can only forfeit their own matches")

        match.forfeit(forfeiting_player_id)
        self._match_repo.save(match)

        winners = [p for p in match.player_ids if p != forfeiting_player_id]
        self._events.dispatch(
            [
                MatchForfeited(
                    match_id=match_id,
                    forfeiting_player_id=forfeiting_player_id,
                    winning_player_id=winners[0] if winners else "",
                )
            ]
        )

        return {
            "match_id": match_id,
            "state": "forfeited",
            "forfeiting_player": forfeiting_player_id,
            "winners": winners,
        }
