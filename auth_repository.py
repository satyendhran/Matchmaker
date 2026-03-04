"""
SQLite User Repository Implementation
=====================================
Implements user data persistence using SQLite.
"""

import sqlite3

from auth_core import (
    AdminUser,
    IUserRepository,
    PlayerUser,
    Session,
    User,
    UserRole,
    UserStatus,
)


class SQLiteUserRepository(IUserRepository):
    """SQLite implementation of user repository."""

    def __init__(self, db_path: str = "tournament.db"):
        self.db_path = db_path
        self._init_database()

    def _get_connection(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize authentication tables."""
        with self._get_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    last_login TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS player_users (
                    id TEXT PRIMARY KEY,
                    player_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    date_of_birth TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    FOREIGN KEY (player_id) REFERENCES players(id)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    ip_address TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_user_id TEXT,
                    details TEXT,
                    timestamp TEXT NOT NULL,
                    ip_address TEXT
                )
            """)

            conn.commit()

    def save_admin(self, admin: AdminUser) -> None:
        """Save admin user."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO admin_users 
                (id, username, password_hash, email, status, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    admin.id,
                    admin.username,
                    admin.password_hash,
                    admin.email,
                    admin.status.value,
                    admin.created_at,
                    admin.last_login,
                ),
            )
            conn.commit()

    def save_player_user(self, player: PlayerUser) -> None:
        """Save player user."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO player_users 
                (id, player_id, name, date_of_birth, status, created_at, last_login)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    player.id,
                    player.player_id,
                    player.name,
                    player.date_of_birth,
                    player.status.value,
                    player.created_at,
                    player.last_login,
                ),
            )
            conn.commit()

    def get_admin_by_username(self, username: str) -> AdminUser | None:
        """Get admin by username."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM admin_users WHERE username = ?", (username,)
            ).fetchone()

            if row:
                return AdminUser(
                    id=row["id"],
                    username=row["username"],
                    password_hash=row["password_hash"],
                    email=row["email"],
                    role=UserRole.ADMIN,
                    status=UserStatus(row["status"]),
                    created_at=row["created_at"],
                    last_login=row["last_login"],
                )
            return None

    def get_player_by_name_dob(self, name: str, dob: str) -> PlayerUser | None:
        """Get player by name and date of birth."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM player_users WHERE name = ? AND date_of_birth = ?",
                (name, dob),
            ).fetchone()

            if row:
                return PlayerUser(
                    id=row["id"],
                    player_id=row["player_id"],
                    name=row["name"],
                    date_of_birth=row["date_of_birth"],
                    role=UserRole.PLAYER,
                    status=UserStatus(row["status"]),
                    created_at=row["created_at"],
                    last_login=row["last_login"],
                )
            return None

    def get_player_user_by_player_id(self, player_id: str) -> PlayerUser | None:
        """Get player user by player ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM player_users WHERE player_id = ?", (player_id,)
            ).fetchone()

            if row:
                return PlayerUser(
                    id=row["id"],
                    player_id=row["player_id"],
                    name=row["name"],
                    date_of_birth=row["date_of_birth"],
                    role=UserRole.PLAYER,
                    status=UserStatus(row["status"]),
                    created_at=row["created_at"],
                    last_login=row["last_login"],
                )
            return None

    def get_user_by_id(self, user_id: str) -> User | None:
        """Get any user by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM admin_users WHERE id = ?", (user_id,)
            ).fetchone()
            if row:
                return AdminUser(
                    id=row["id"],
                    username=row["username"],
                    password_hash=row["password_hash"],
                    email=row["email"],
                    role=UserRole.ADMIN,
                    status=UserStatus(row["status"]),
                    created_at=row["created_at"],
                    last_login=row["last_login"],
                )

            row = conn.execute(
                "SELECT * FROM player_users WHERE id = ?", (user_id,)
            ).fetchone()
            if row:
                return PlayerUser(
                    id=row["id"],
                    player_id=row["player_id"],
                    name=row["name"],
                    date_of_birth=row["date_of_birth"],
                    role=UserRole.PLAYER,
                    status=UserStatus(row["status"]),
                    created_at=row["created_at"],
                    last_login=row["last_login"],
                )

            return None

    def update_user_status(self, user_id: str, status: UserStatus) -> None:
        """Update user account status."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE admin_users SET status = ? WHERE id = ?",
                (status.value, user_id),
            )
            conn.execute(
                "UPDATE player_users SET status = ? WHERE id = ?",
                (status.value, user_id),
            )
            conn.commit()

    def update_admin_password(self, admin_id: str, new_password_hash: str) -> None:
        """Update admin password hash."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE admin_users SET password_hash = ? WHERE id = ?",
                (new_password_hash, admin_id),
            )
            conn.commit()

    def save_session(self, session: Session) -> None:
        """Save session."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions 
                (session_id, user_id, role, ip_address, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    session.session_id,
                    session.user_id,
                    session.role.value,
                    session.ip_address,
                    session.created_at,
                    session.expires_at,
                ),
            )
            conn.commit()

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()

            if row:
                return Session(
                    session_id=row["session_id"],
                    user_id=row["user_id"],
                    role=UserRole(row["role"]),
                    ip_address=row["ip_address"],
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                )
            return None

    def delete_session(self, session_id: str) -> None:
        """Delete session."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()

    def update_last_login(self, user_id: str, timestamp: str) -> None:
        """Update last login timestamp."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE admin_users SET last_login = ? WHERE id = ?",
                (timestamp, user_id),
            )
            conn.execute(
                "UPDATE player_users SET last_login = ? WHERE id = ?",
                (timestamp, user_id),
            )
            conn.commit()

    def log_admin_action(
        self,
        admin_id: str,
        action: str,
        target_user_id: str = None,
        details: str = None,
        ip_address: str = None,
    ) -> None:
        """Log an admin action for audit trail."""
        from tournament_core import now_iso

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_log 
                (admin_id, action, target_user_id, details, timestamp, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (admin_id, action, target_user_id, details, now_iso(), ip_address),
            )
            conn.commit()
