"""
Authentication and Authorization Core Module
============================================
Defines interfaces and models for the authentication system.
Follows SOLID principles with clear separation of concerns.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class UserRole(Enum):
    """User roles with hierarchical permissions."""

    ADMIN = "admin"
    PLAYER = "player"


class UserStatus(Enum):
    """User account status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    SHADOW_BANNED = "shadow_banned"


@dataclass(kw_only=True)
class User:
    """Base user model."""

    id: str
    role: UserRole
    status: UserStatus
    created_at: str
    last_login: str | None = None


@dataclass(kw_only=True)
class AdminUser(User):
    """Admin user with username/password authentication."""

    username: str
    password_hash: str
    email: str | None = None


@dataclass(kw_only=True)
class PlayerUser(User):
    """Player user with name/DOB authentication."""

    player_id: str
    name: str
    date_of_birth: str


@dataclass
class Session:
    """User session information."""

    session_id: str
    user_id: str
    role: UserRole
    created_at: str
    expires_at: str
    ip_address: str | None = None


class IAuthenticationService(ABC):
    """Interface for authentication operations."""

    @abstractmethod
    def authenticate_admin(self, username: str, password: str) -> AdminUser | None:
        """Authenticate admin with username/password."""
        pass

    @abstractmethod
    def authenticate_player(self, name: str, date_of_birth: str) -> PlayerUser | None:
        """Authenticate player with name/DOB."""
        pass

    @abstractmethod
    def create_session(self, user: User, ip_address: str | None = None) -> Session:
        """Create a new session for authenticated user."""
        pass

    @abstractmethod
    def validate_session(self, session_id: str) -> Session | None:
        """Validate and retrieve session."""
        pass

    @abstractmethod
    def invalidate_session(self, session_id: str) -> None:
        """Invalidate/logout a session."""
        pass


class IAuthorizationService(ABC):
    """Interface for authorization/permission checks."""

    @abstractmethod
    def can_create_tournament(self, user: User) -> bool:
        """Check if user can create tournaments."""
        pass

    @abstractmethod
    def can_create_round(self, user: User) -> bool:
        """Check if user can create rounds."""
        pass

    @abstractmethod
    def can_record_result(self, user: User) -> bool:
        """Check if user can record match results."""
        pass

    @abstractmethod
    def can_manage_players(self, user: User) -> bool:
        """Check if user can add/remove players."""
        pass

    @abstractmethod
    def can_suspend_users(self, user: User) -> bool:
        """Check if user can suspend other users."""
        pass

    @abstractmethod
    def can_view_all_tournaments(self, user: User) -> bool:
        """Check if user can view all tournaments."""
        pass

    @abstractmethod
    def can_view_player_pairings(self, user: PlayerUser, tournament_id: str) -> bool:
        """Check if player can view their pairings."""
        pass


class IUserRepository(ABC):
    """Interface for user data persistence."""

    @abstractmethod
    def save_admin(self, admin: AdminUser) -> None:
        """Save admin user."""
        pass

    @abstractmethod
    def save_player_user(self, player: PlayerUser) -> None:
        """Save player user."""
        pass

    @abstractmethod
    def get_admin_by_username(self, username: str) -> AdminUser | None:
        """Get admin by username."""
        pass

    @abstractmethod
    def get_player_by_name_dob(self, name: str, dob: str) -> PlayerUser | None:
        """Get player by name and date of birth."""
        pass

    @abstractmethod
    def get_player_user_by_player_id(self, player_id: str) -> PlayerUser | None:
        """Get player user by their linked player_id."""
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> User | None:
        """Get any user by ID."""
        pass

    @abstractmethod
    def update_user_status(self, user_id: str, status: UserStatus) -> None:
        """Update user account status."""
        pass

    @abstractmethod
    def update_admin_password(self, admin_id: str, new_password_hash: str) -> None:
        """Update admin password hash."""
        pass

    @abstractmethod
    def save_session(self, session: Session) -> None:
        """Save session."""
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Delete session."""
        pass

    @abstractmethod
    def update_last_login(self, user_id: str, timestamp: str) -> None:
        """Update last login timestamp."""
        pass

    @abstractmethod
    def log_admin_action(
        self,
        admin_id: str,
        action: str,
        target_user_id: str | None = None,
        details: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log an admin action for audit trail."""
        pass
