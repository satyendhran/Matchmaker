"""
Flask Authentication Middleware
================================
Provides decorators for protecting Flask routes.
Supports both session-based and JWT Bearer token authentication.
"""

from collections.abc import Callable
from functools import wraps

from flask import g, jsonify, request

from auth_core import Session, User, UserRole, UserStatus
from auth_service import AuthenticationService, AuthorizationService
from security import CSRFProtection, JWTProvider


class AuthMiddleware:
    """Middleware for handling authentication in Flask.

    Supports:
    - Session-based auth (cookie or header)
    - JWT Bearer token auth (if JWTProvider provided)
    - CSRF protection (if CSRFProtection provided)
    """

    def __init__(
        self,
        auth_service: AuthenticationService,
        authz_service: AuthorizationService,
        jwt_provider: JWTProvider | None = None,
        csrf_protection: CSRFProtection | None = None,
    ):
        self.auth_service = auth_service
        self.authz_service = authz_service
        self.jwt_provider = jwt_provider or JWTProvider()
        self.csrf_protection = csrf_protection or CSRFProtection()

    def get_current_session(self) -> Session | None:
        """Get current session from request.

        Auth resolution order:
        1. JWT Bearer token in Authorization header → validate via JWTProvider
        2. Session ID in Authorization header (legacy) → validate via session store
        3. Session ID in cookie → validate via session store
        """
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

            claims = self.jwt_provider.validate_token(token)
            if claims:
                return Session(
                    session_id=token[:32],
                    user_id=claims.get("sub", ""),
                    role=UserRole(claims.get("role", "PLAYER")),
                    created_at=str(claims.get("iat", "")),
                    expires_at=str(claims.get("exp", "")),
                    ip_address=request.remote_addr,
                )

            return self.auth_service.validate_session(token)

        session_id = request.cookies.get("session_id")
        if session_id:
            return self.auth_service.validate_session(session_id)

        return None

    def get_current_user(self) -> User | None:
        """Get current authenticated user."""
        session = self.get_current_session()
        if not session:
            return None
        return self.auth_service.repository.get_user_by_id(session.user_id)

    def require_auth(self, func: Callable) -> Callable:
        """Decorator to require authentication."""

        @wraps(func)
        def wrapper(*args, **kwargs):
            session = self.get_current_session()
            if not session:
                return jsonify({"error": "Authentication required"}), 401
            g.current_session = session
            return func(*args, **kwargs)

        return wrapper

    def require_role(self, *allowed_roles: UserRole) -> Callable:
        """Decorator to require specific roles."""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                session = self.get_current_session()
                if not session:
                    return jsonify({"error": "Authentication required"}), 401

                if session.role not in allowed_roles:
                    return jsonify({"error": "Insufficient permissions"}), 403

                user = self.get_current_user()
                if not user or user.status != UserStatus.ACTIVE:
                    return jsonify({"error": "Account not active"}), 403

                g.current_session = session
                g.current_user = user
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def require_admin(self, func: Callable) -> Callable:
        """Decorator to require admin role."""
        return self.require_role(UserRole.ADMIN)(func)

    def require_staff_or_admin(self, func: Callable) -> Callable:
        """Decorator to require staff or admin role."""
        return self.require_role(UserRole.ADMIN)(func)

    def require_permission(self, permission_check: Callable[[User], bool]) -> Callable:
        """Decorator to check custom permission."""

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                user = self.get_current_user()
                if not user:
                    return jsonify({"error": "Authentication required"}), 401

                if not permission_check(user):
                    return jsonify({"error": "Insufficient permissions"}), 403

                g.current_user = user
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def require_csrf(self, func: Callable) -> Callable:
        """Decorator to enforce CSRF token on mutating requests."""

        @wraps(func)
        def wrapper(*args, **kwargs):
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                token = request.headers.get("X-CSRF-Token") or request.form.get(
                    "_csrf_token"
                )
                session_id = request.cookies.get("session_id", "")
                if not token or not self.csrf_protection.validate_token(
                    token, session_id
                ):
                    return jsonify({"error": "CSRF validation failed"}), 403
            return func(*args, **kwargs)

        return wrapper


def create_auth_middleware(
    auth_service: AuthenticationService,
    authz_service: AuthorizationService,
    jwt_provider: JWTProvider | None = None,
    csrf_protection: CSRFProtection | None = None,
) -> AuthMiddleware:
    """Factory function to create auth middleware."""
    return AuthMiddleware(auth_service, authz_service, jwt_provider, csrf_protection)
