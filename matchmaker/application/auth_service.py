"""
Authentication service — login, register, session validation.

This is an application service (not domain) because it coordinates
between the domain User model and the infrastructure auth provider.
"""

from __future__ import annotations

from matchmaker.domain.errors import AuthenticationError
from matchmaker.domain.events import UserLoggedIn, UserRegistered
from matchmaker.domain.interfaces import (
    IAuthProvider,
    IEventDispatcher,
    IUserRepository,
)
from matchmaker.domain.models import Role, User


class AuthService:
    """Application-level auth service."""

    def __init__(
        self,
        user_repo: IUserRepository,
        auth_provider: IAuthProvider,
        event_dispatcher: IEventDispatcher,
    ):
        self._users = user_repo
        self._auth = auth_provider
        self._events = event_dispatcher

    def register(
        self,
        username: str,
        password: str,
        role: str = "PLAYER",
        player_id: str | None = None,
    ) -> dict:
        """Register a new user account."""
        if not username or len(username) < 3:
            raise AuthenticationError("Username must be at least 3 characters")
        if not password or len(password) < 6:
            raise AuthenticationError("Password must be at least 6 characters")

        if self._users.username_exists(username):
            raise AuthenticationError(f"Username '{username}' is already taken")

        # Only admins can create admin/arbiter accounts — but for bootstrap,
        # the first user can be admin
        try:
            role_enum = Role(role)
        except ValueError:
            raise AuthenticationError(f"Invalid role: {role}")

        user = User(
            id=User.generate_id(),
            username=username,
            password_hash=self._auth.hash_password(password),
            role=role_enum,
            player_id=player_id,
        )

        self._users.save(user)

        self._events.dispatch(
            [
                UserRegistered(
                    user_id=user.id, username=user.username, role=user.role.value
                )
            ]
        )

        token = self._auth.create_token(user.id, user.username, user.role.value)

        return {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
            "token": token,
        }

    def login(self, username: str, password: str) -> dict:
        """Authenticate and return JWT token."""
        user = self._users.get_by_username(username)
        if user is None:
            raise AuthenticationError("Invalid credentials")

        if not self._auth.verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid credentials")

        token = self._auth.create_token(user.id, user.username, user.role.value)

        self._events.dispatch([UserLoggedIn(user_id=user.id, username=user.username)])

        return {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
            "token": token,
            "player_id": user.player_id,
        }

    def validate_session(self, token: str) -> dict | None:
        """Validate a JWT token and return user info."""
        claims = self._auth.validate_token(token)
        if claims is None:
            return None

        user = self._users.get_by_id(claims.get("user_id", ""))
        if user is None:
            return None

        return {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
            "player_id": user.player_id,
        }

    def get_user_info(self, user_id: str) -> dict | None:
        """Get user profile info."""
        user = self._users.get_by_id(user_id)
        if user is None:
            return None
        return {
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
            "player_id": user.player_id,
        }
