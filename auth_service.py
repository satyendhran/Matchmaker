"""
Authentication and Authorization Service Implementation
======================================================
Implements authentication and authorization logic.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone


from security import PasswordPolicy, RateLimiter, SessionFingerprint, get_env

from auth_core import (
    AdminUser,
    IAuthenticationService,
    IAuthorizationService,
    IUserRepository,
    PlayerUser,
    Session,
    User,
    UserRole,
    UserStatus,
)
from tournament_core import generate_id, now_iso


class AuthenticationService(IAuthenticationService):
    """Service for handling authentication."""
    
    def __init__(self, repository: IUserRepository):
        self.repository = repository
        self.session_duration_hours = int(get_env("SESSION_DURATION_HOURS", "24"))
        self.rate_limiter = RateLimiter()
        self.password_policy = PasswordPolicy()
    
    def authenticate_admin(self, username: str, password: str, ip_address: str = "") -> AdminUser | None:
        """Authenticate admin with username/password."""
        
        rate_key = f"admin:{ip_address or username}"
        allowed, wait = self.rate_limiter.check(rate_key)
        if not allowed:
            return None

        admin = self.repository.get_admin_by_username(username)
        
        if not admin:
            self.rate_limiter.record_failure(rate_key)
            return None
        
        
        if admin.status != UserStatus.ACTIVE:
            return None
        
        
        if not self._verify_password(password, admin.password_hash):
            self.rate_limiter.record_failure(rate_key)
            return None
        
        
        self.rate_limiter.record_success(rate_key)

        
        self.repository.update_last_login(admin.id, now_iso())
        
        return admin
    
    def authenticate_player(self, name: str, date_of_birth: str) -> PlayerUser | None:
        """Authenticate player with name/DOB."""
        player = self.repository.get_player_by_name_dob(name, date_of_birth)
        
        if not player:
            return None
        
        
        if player.status not in [UserStatus.ACTIVE, UserStatus.SHADOW_BANNED]:
            return None
        
        
        self.repository.update_last_login(player.id, now_iso())
        
        return player
    
    def create_session(
        self,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Session:
        """Create a new session for authenticated user.
        
        Stores a fingerprint hash for hijacking detection.
        """
        fingerprint = ""
        if ip_address and user_agent:
            fingerprint = SessionFingerprint.create(ip_address, user_agent)

        session = Session(
            session_id=self._generate_session_id(),
            user_id=user.id,
            role=user.role,
            created_at=now_iso(),
            expires_at=self._calculate_expiry(),
            ip_address=ip_address,
        )
        
        if fingerprint:
            session = Session(
                session_id=session.session_id,
                user_id=session.user_id,
                role=session.role,
                created_at=session.created_at,
                expires_at=session.expires_at,
                ip_address=f"fp:{fingerprint}|{ip_address or ''}",
            )

        self.repository.save_session(session)
        return session
    
    def validate_session(self, session_id: str) -> Session | None:
        """Validate and retrieve session."""
        session = self.repository.get_session(session_id)
        
        if not session:
            return None
        
        
        try:
            expires_dt = datetime.fromisoformat(session.expires_at.replace('Z', '+00:00'))
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            self.repository.delete_session(session_id)
            return None

        now_dt = datetime.now(timezone.utc)
        
        if now_dt > expires_dt:
            self.repository.delete_session(session_id)
            return None
        
        
        user = self.repository.get_user_by_id(session.user_id)
        if not user or user.status == UserStatus.SUSPENDED:
            self.repository.delete_session(session_id)
            return None
        
        return session
    
    def invalidate_session(self, session_id: str) -> None:
        """Invalidate/logout a session."""
        self.repository.delete_session(session_id)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using SHA-256 with salt."""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{pwd_hash}"
    
    @staticmethod
    def _verify_password(password: str, stored_hash: str) -> bool:
        """Verify password against stored hash (constant-time comparison)."""
        try:
            salt, pwd_hash = stored_hash.split(':')
            test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return secrets.compare_digest(test_hash, pwd_hash)
        except Exception:
            return False
    
    @staticmethod
    def _generate_session_id() -> str:
        """Generate secure session ID."""
        return secrets.token_urlsafe(32)
    
    def _calculate_expiry(self) -> str:
        """Calculate session expiry time."""
        expiry = datetime.now(timezone.utc) + timedelta(hours=self.session_duration_hours)
        return expiry.isoformat()


class AuthorizationService(IAuthorizationService):
    """Service for handling authorization/permissions."""
    
    def __init__(self, repository: IUserRepository):
        self.repository = repository
    
    def can_create_tournament(self, user: User) -> bool:
        """Check if user can create tournaments."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def can_create_round(self, user: User) -> bool:
        """Check if user can create rounds."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def can_record_result(self, user: User) -> bool:
        """Check if user can record match results."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def can_manage_players(self, user: User) -> bool:
        """Check if user can add/remove players."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def can_approve_staff(self, user: User) -> bool:
        """Check if user can approve staff registrations (kept for compatibility)."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def can_suspend_users(self, user: User) -> bool:
        """Check if user can suspend other users."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def can_view_all_tournaments(self, user: User) -> bool:
        """Check if user can view all tournaments."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def can_view_player_pairings(self, user: PlayerUser, tournament_id: str) -> bool:
        """Check if player can view their pairings."""
        if user.role != UserRole.PLAYER:
            return False
        
        
        if user.status == UserStatus.SHADOW_BANNED:
            return True
        
        return user.status == UserStatus.ACTIVE
    
    def can_view_admin_panel(self, user: User) -> bool:
        """Check if user can access admin panel."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def can_edit_tournament(self, user: User) -> bool:
        """Check if user can edit tournament details."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def can_delete_tournament(self, user: User) -> bool:
        """Check if user can delete tournaments."""
        return user.role == UserRole.ADMIN and user.status == UserStatus.ACTIVE
    
    def is_shadow_banned(self, user: User) -> bool:
        """Check if user is shadow banned."""
        return user.status == UserStatus.SHADOW_BANNED


class UserManagementService:
    """Service for user management operations."""
    
    def __init__(self, repository: IUserRepository, auth_service: AuthenticationService):
        self.repository = repository
        self.auth_service = auth_service
    
    def register_admin(self, username: str, password: str, email: str = None) -> AdminUser:
        """Register a new admin (should only be done during setup)."""
        admin = AdminUser(
            id=generate_id(),
            username=username,
            password_hash=self.auth_service.hash_password(password),
            email=email,
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            created_at=now_iso()
        )
        
        self.repository.save_admin(admin)
        return admin
    
    def register_player(self, player_id: str, name: str, date_of_birth: str) -> PlayerUser:
        """Register a player user account."""
        
        if self.repository.get_player_user_by_player_id(player_id):
            raise ValueError("Player ID already registered")

        
        if self.repository.get_player_by_name_dob(name, date_of_birth):
            raise ValueError("Player with this name and date of birth already registered")
            
        player_user = PlayerUser(
            id=generate_id(),
            player_id=player_id,
            name=name,
            date_of_birth=date_of_birth,
            role=UserRole.PLAYER,
            status=UserStatus.ACTIVE,
            created_at=now_iso()
        )
        
        self.repository.save_player_user(player_user)
        return player_user
    
    def change_admin_password(
        self, admin_id: str, current_password: str, new_password: str
    ) -> None:
        """Change an admin's password after verifying the current one."""
        user = self.repository.get_user_by_id(admin_id)
        if not user or user.role != UserRole.ADMIN:
            raise ValueError("Admin not found")
        
        if not self.auth_service._verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")
        
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters long")
        
        new_hash = self.auth_service.hash_password(new_password)
        self.repository.update_admin_password(admin_id, new_hash)
        
        self.repository.log_admin_action(
            admin_id, "CHANGE_PASSWORD", admin_id, "Admin changed their own password"
        )
    
    def suspend_user(self, user_id: str, admin_id: str, reason: str = None) -> None:
        """Suspend a user account."""
        self.repository.update_user_status(user_id, UserStatus.SUSPENDED)
        self.repository.log_admin_action(
            admin_id, "SUSPEND_USER", user_id, f"Suspended: {reason or 'No reason provided'}"
        )
    
    def shadow_ban_user(self, user_id: str, admin_id: str, reason: str = None) -> None:
        """Shadow ban a user (they don't know they're banned)."""
        self.repository.update_user_status(user_id, UserStatus.SHADOW_BANNED)
        self.repository.log_admin_action(
            admin_id, "SHADOW_BAN_USER", user_id, f"Shadow banned: {reason or 'No reason provided'}"
        )
    
    def reactivate_user(self, user_id: str, admin_id: str) -> None:
        """Reactivate a suspended or banned user."""
        self.repository.update_user_status(user_id, UserStatus.ACTIVE)
        self.repository.log_admin_action(
            admin_id, "REACTIVATE_USER", user_id, "User reactivated"
        )
    
    def get_user(self, user_id: str) -> User | None:
        """Get user by ID."""
        return self.repository.get_user_by_id(user_id)