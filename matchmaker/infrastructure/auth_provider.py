"""
JWT auth provider using PyJWT + werkzeug password hashing.

Uses werkzeug.security (bundled with Flask) to avoid adding bcrypt dep.
"""

from __future__ import annotations

import datetime
import os

from matchmaker.domain.interfaces import IAuthProvider

# JWT secret — in production this comes from env; for dev, generate one
_JWT_SECRET = os.environ.get("JWT_SECRET", "nexus-tournament-engine-dev-secret-key-change-in-prod")
_JWT_ALGORITHM = "HS256"
_TOKEN_EXPIRY_HOURS = 24


class JWTAuthProvider(IAuthProvider):
    """JWT-based auth provider."""

    def __init__(self, secret: str | None = None, expiry_hours: int = _TOKEN_EXPIRY_HOURS):
        self._secret = secret or _JWT_SECRET
        self._expiry_hours = expiry_hours

    def create_token(self, user_id: str, username: str, role: str) -> str:
        import jwt

        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "exp": datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(hours=self._expiry_hours),
            "iat": datetime.datetime.now(datetime.timezone.utc),
        }
        return jwt.encode(payload, self._secret, algorithm=_JWT_ALGORITHM)

    def validate_token(self, token: str) -> dict | None:
        import jwt

        try:
            payload = jwt.decode(
                token, self._secret, algorithms=[_JWT_ALGORITHM]
            )
            return {
                "user_id": payload["user_id"],
                "username": payload["username"],
                "role": payload["role"],
            }
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def hash_password(self, password: str) -> str:
        from werkzeug.security import generate_password_hash

        return generate_password_hash(password, method="pbkdf2:sha256")

    def verify_password(self, password: str, password_hash: str) -> bool:
        from werkzeug.security import check_password_hash

        return check_password_hash(password_hash, password)
