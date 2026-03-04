"""
Security Module — Consolidated security enhancements.
=====================================================
Contains: PasswordPolicy, InputValidator, RateLimiter,
SessionFingerprint, CSRFProtection, JWTProvider, AuditLogger.
"""

import hashlib
import json
import os
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

# ---------------------------------------------------------------------------
#  Environment helpers
# ---------------------------------------------------------------------------


def _load_env():
    """Load .env file into os.environ if python-dotenv is available."""
    try:
        from dotenv import load_dotenv

        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        load_dotenv(env_path)
    except ImportError:
        pass


_load_env()


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with fallback."""
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
#  Password Policy
# ---------------------------------------------------------------------------


class PasswordPolicy:
    """Enforces password strength requirements.

    Configurable via .env or constructor params.
    """

    def __init__(
        self,
        min_length: int = 0,
        require_uppercase: bool = False,
        require_lowercase: bool = False,
        require_digit: bool = False,
        require_special: bool = False,
    ):
        self.min_length = min_length or int(get_env("PASSWORD_MIN_LENGTH", "8"))
        self.require_uppercase = (
            require_uppercase
            or get_env("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
        )
        self.require_lowercase = (
            require_lowercase
            or get_env("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
        )
        self.require_digit = (
            require_digit or get_env("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
        )
        self.require_special = require_special

    def validate(self, password: str) -> tuple[bool, list[str]]:
        """Validate password against policy.

        Returns:
            (is_valid, list_of_violations)
        """
        violations = []

        if len(password) < self.min_length:
            violations.append(f"Password must be at least {self.min_length} characters")

        if self.require_uppercase and not re.search(r"[A-Z]", password):
            violations.append("Password must contain at least one uppercase letter")

        if self.require_lowercase and not re.search(r"[a-z]", password):
            violations.append("Password must contain at least one lowercase letter")

        if self.require_digit and not re.search(r"\d", password):
            violations.append("Password must contain at least one digit")

        if self.require_special and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            violations.append("Password must contain at least one special character")

        return (len(violations) == 0, violations)


# ---------------------------------------------------------------------------
#  Input Validator
# ---------------------------------------------------------------------------

_UUID_HEX_RE = re.compile(r"^[0-9a-f]{32}$")
_UUID_CANONICAL_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_SAFE_STRING_RE = re.compile(r"^[a-zA-Z0-9 _.\-@]+$")


class InputValidator:
    """Validates and sanitizes user inputs before they reach SQL."""

    @staticmethod
    def is_valid_uuid(value: str) -> bool:
        """Check if string is a valid UUID (hex or canonical format)."""
        if not isinstance(value, str):
            return False
        v = value.strip().lower()
        return bool(_UUID_HEX_RE.match(v) or _UUID_CANONICAL_RE.match(v))

    @staticmethod
    def is_safe_string(value: str, max_length: int = 255) -> bool:
        """Check if string is safe (no SQL injection vectors)."""
        if not isinstance(value, str):
            return False
        if len(value) > max_length:
            return False
        return bool(_SAFE_STRING_RE.match(value))

    @staticmethod
    def sanitize_string(value: str, max_length: int = 255) -> str:
        """Strip dangerous characters from a string."""
        if not isinstance(value, str):
            return ""
        cleaned = value.strip()[:max_length]
        # Remove null bytes and control characters
        cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)
        return cleaned

    @staticmethod
    def validate_id(value: str, name: str = "ID") -> str:
        """Validate and return a clean UUID, or raise ValueError."""
        if not InputValidator.is_valid_uuid(value):
            raise ValueError(f"Invalid {name}: must be a valid UUID hex string")
        return value.strip().lower()

    @staticmethod
    def validate_date(value: str) -> str:
        """Validate YYYY-MM-DD date format."""
        try:
            datetime.strptime(value.strip(), "%Y-%m-%d")
            return value.strip()
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid date format: '{value}'. Expected YYYY-MM-DD")


# ---------------------------------------------------------------------------
#  Rate Limiter
# ---------------------------------------------------------------------------


@dataclass
class _LoginAttempt:
    count: int = 0
    first_attempt: float = 0.0
    locked_until: float = 0.0


class RateLimiter:
    """In-memory rate limiter for brute-force protection.

    Tracks failed attempts per key (usually IP address).
    After max_attempts within window, locks out for lockout_seconds.
    """

    def __init__(
        self,
        max_attempts: int = 0,
        lockout_seconds: int = 0,
    ):
        self.max_attempts = max_attempts or int(get_env("MAX_LOGIN_ATTEMPTS", "5"))
        self.lockout_seconds = lockout_seconds or int(
            get_env("LOGIN_LOCKOUT_SECONDS", "300")
        )
        self._attempts: dict[str, _LoginAttempt] = {}

    def check(self, key: str) -> tuple[bool, int]:
        """Check if a key is allowed to attempt login.

        Returns:
            (is_allowed, seconds_until_unlock)
        """
        now = time.time()
        attempt = self._attempts.get(key)

        if attempt is None:
            return (True, 0)

        # Currently locked out?
        if attempt.locked_until > now:
            remaining = int(attempt.locked_until - now)
            return (False, remaining)

        # Lock expired — reset if needed
        if attempt.locked_until > 0 and attempt.locked_until <= now:
            self._attempts.pop(key, None)
            return (True, 0)

        return (True, 0)

    def record_failure(self, key: str) -> tuple[bool, int]:
        """Record a failed login attempt.

        Returns:
            (is_now_locked, lockout_seconds_remaining)
        """
        now = time.time()
        attempt = self._attempts.get(key)

        if attempt is None:
            attempt = _LoginAttempt(count=1, first_attempt=now)
            self._attempts[key] = attempt
        else:
            attempt.count += 1

        if attempt.count >= self.max_attempts:
            attempt.locked_until = now + self.lockout_seconds
            return (True, self.lockout_seconds)

        return (False, 0)

    def record_success(self, key: str) -> None:
        """Clear attempts on successful login."""
        self._attempts.pop(key, None)

    def reset(self, key: str) -> None:
        """Manually reset a key (admin action)."""
        self._attempts.pop(key, None)


# ---------------------------------------------------------------------------
#  Session Fingerprint
# ---------------------------------------------------------------------------


class SessionFingerprint:
    """Binds sessions to a (ip, user_agent) fingerprint to detect hijacking."""

    @staticmethod
    def create(ip_address: str, user_agent: str) -> str:
        """Create a fingerprint hash from IP and User-Agent."""
        raw = f"{ip_address}|{user_agent}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def verify(stored_fingerprint: str, ip_address: str, user_agent: str) -> bool:
        """Verify that current request matches stored fingerprint."""
        current = SessionFingerprint.create(ip_address, user_agent)
        return secrets.compare_digest(stored_fingerprint, current)


# ---------------------------------------------------------------------------
#  CSRF Protection
# ---------------------------------------------------------------------------


class CSRFProtection:
    """CSRF token generation and validation for Flask."""

    def __init__(self, secret_key: str = ""):
        self.secret_key = secret_key or get_env("SECRET_KEY", "default-csrf-key")

    def generate_token(self, session_id: str) -> str:
        """Generate a CSRF token tied to a session."""
        raw = f"{self.secret_key}:{session_id}:{int(time.time()) // 3600}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate CSRF token. Accepts current hour and previous hour."""
        current_hour = int(time.time()) // 3600
        for hour_offset in (0, -1):
            raw = f"{self.secret_key}:{session_id}:{current_hour + hour_offset}"
            expected = hashlib.sha256(raw.encode()).hexdigest()
            if secrets.compare_digest(token, expected):
                return True
        return False

    def flask_protect(self) -> Callable:
        """Flask decorator to enforce CSRF on POST/PUT/DELETE."""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                from flask import jsonify, request

                if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                    token = request.headers.get("X-CSRF-Token") or request.form.get(
                        "_csrf_token"
                    )
                    session_id = request.cookies.get("session_id", "")

                    if not token or not self.validate_token(token, session_id):
                        return jsonify({"error": "CSRF validation failed"}), 403

                return func(*args, **kwargs)

            return wrapper

        return decorator


# ---------------------------------------------------------------------------
#  JWT Provider
# ---------------------------------------------------------------------------


class JWTProvider:
    """JWT token creation and validation.

    Uses PyJWT if available, otherwise falls back to a simple HMAC token.
    Implements the IAuthProvider interface from matchmaker.domain.interfaces.
    """

    def __init__(self, secret: str = "", algorithm: str = "", expiry_hours: int = 0):
        self.secret = secret or get_env("JWT_SECRET", "default-jwt-secret")
        self.algorithm = algorithm or get_env("JWT_ALGORITHM", "HS256")
        self.expiry_hours = expiry_hours or int(get_env("JWT_EXPIRY_HOURS", "24"))
        self._has_pyjwt = self._check_pyjwt()

    @staticmethod
    def _check_pyjwt() -> bool:
        try:
            import jwt  # noqa: F401

            return True
        except ImportError:
            return False

    def create_token(self, user_id: str, username: str, role: str) -> str:
        """Create a JWT token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=self.expiry_hours)).timestamp()),
        }

        if self._has_pyjwt:
            import jwt

            return jwt.encode(payload, self.secret, algorithm=self.algorithm)

        # Fallback: HMAC-based simple token
        return self._simple_encode(payload)

    def validate_token(self, token: str) -> dict | None:
        """Validate a JWT token and return claims, or None if invalid."""
        if self._has_pyjwt:
            try:
                import jwt

                payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
                return payload
            except Exception:
                return None

        # Fallback: HMAC validation
        return self._simple_decode(token)

    def _simple_encode(self, payload: dict) -> str:
        """Fallback encoder using HMAC (no PyJWT dependency)."""
        import base64

        payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
        sig = hashlib.sha256(f"{payload_b64}.{self.secret}".encode()).hexdigest()
        return f"{payload_b64}.{sig}"

    def _simple_decode(self, token: str) -> dict | None:
        """Fallback decoder."""
        import base64

        try:
            parts = token.rsplit(".", 1)
            if len(parts) != 2:
                return None
            payload_b64, sig = parts
            expected_sig = hashlib.sha256(
                f"{payload_b64}.{self.secret}".encode()
            ).hexdigest()
            if not secrets.compare_digest(sig, expected_sig):
                return None
            # Pad base64
            padding = 4 - len(payload_b64) % 4
            payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            # Check expiry
            if payload.get("exp", 0) < time.time():
                return None
            return payload
        except Exception:
            return None

    # IAuthProvider interface compatibility
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt (matches existing auth_service pattern)."""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{pwd_hash}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against stored hash."""
        try:
            salt, pwd_hash = password_hash.split(":")
            test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return secrets.compare_digest(test_hash, pwd_hash)
        except Exception:
            return False


# ---------------------------------------------------------------------------
#  Audit Logger (enhanced with diffs)
# ---------------------------------------------------------------------------


class AuditLogger:
    """Enhanced audit logger that captures before/after diffs."""

    @staticmethod
    def create_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        """Create a diff between two states.

        Returns dict like:
        {
            "field_name": {"before": old_value, "after": new_value},
            ...
        }
        """
        diff = {}
        all_keys = set(list(before.keys()) + list(after.keys()))
        for key in all_keys:
            old_val = before.get(key)
            new_val = after.get(key)
            if old_val != new_val:
                diff[key] = {"before": old_val, "after": new_val}
        return diff

    @staticmethod
    def format_action(
        admin_id: str,
        action: str,
        target_id: str | None = None,
        details: str | None = None,
        diff: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Format an audit log entry with optional diff."""
        entry = {
            "admin_id": admin_id,
            "action": action,
            "target_id": target_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip_address": ip_address,
        }
        if diff:
            entry["diff"] = diff
        return entry
