"""
Domain error hierarchy.

Explicit, typed errors replace generic ValueError/RuntimeError.
No existence leaks: unauthorized lookups get MatchNotFoundError too.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base for all domain-level errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        super().__init__(message)
        self.code = code


# ── Match Errors ──


class MatchNotFoundError(DomainError):
    """Match does not exist OR caller is not authorized to see it."""

    def __init__(self, match_id: str = ""):
        detail = f": {match_id}" if match_id else ""
        super().__init__(f"Match not found{detail}", "MATCH_NOT_FOUND")


class MatchAlreadyCompletedError(DomainError):
    """Attempted to record a result on a match that is already completed."""

    def __init__(self, match_id: str = ""):
        detail = f": {match_id}" if match_id else ""
        super().__init__(
            f"Match already completed{detail}", "MATCH_ALREADY_COMPLETED"
        )


class InvalidMatchResultError(DomainError):
    """Result data violates domain invariants."""

    def __init__(self, reason: str):
        super().__init__(f"Invalid match result: {reason}", "INVALID_MATCH_RESULT")


# ── Concurrency ──


class ConcurrencyConflictError(DomainError):
    """Optimistic locking failure — another write beat us."""

    def __init__(self, entity: str = "entity"):
        super().__init__(
            f"Concurrent modification detected on {entity}. Please retry.",
            "CONCURRENCY_CONFLICT",
        )


# ── Withdrawal ──


class WithdrawalNotAllowedError(DomainError):
    """Player cannot withdraw under current tournament rules."""

    def __init__(self, reason: str):
        super().__init__(
            f"Withdrawal not allowed: {reason}", "WITHDRAWAL_NOT_ALLOWED"
        )


# ── Auth ──


class AuthenticationError(DomainError):
    """Invalid credentials."""

    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message, "AUTHENTICATION_FAILED")


class AuthorizationError(DomainError):
    """Caller lacks required permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, "AUTHORIZATION_FAILED")


# ── Tournament ──


class TournamentNotFoundError(DomainError):
    def __init__(self, tournament_id: str = ""):
        detail = f": {tournament_id}" if tournament_id else ""
        super().__init__(f"Tournament not found{detail}", "TOURNAMENT_NOT_FOUND")


class PlayerNotFoundError(DomainError):
    def __init__(self, player_id: str = ""):
        detail = f": {player_id}" if player_id else ""
        super().__init__(f"Player not found{detail}", "PLAYER_NOT_FOUND")
