"""
Database migrations — safely evolve the schema.

Uses ALTER TABLE for backward-compatible changes to the existing
tournament.db. Tracks applied migrations to avoid duplicate runs.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def run_migrations(db_path: str) -> None:
    """Run all pending migrations against the database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Migration tracking table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            applied_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()

    applied = {
        row["name"]
        for row in conn.execute("SELECT name FROM _migrations").fetchall()
    }

    migrations = [
        ("001_add_version_to_matches", _migrate_001_version_column),
        ("002_create_users_table", _migrate_002_users_table),
        ("003_add_player_status", _migrate_003_player_status),
    ]

    for name, func in migrations:
        if name not in applied:
            logger.info("Applying migration: %s", name)
            try:
                func(conn)
                conn.execute(
                    "INSERT INTO _migrations (name) VALUES (?)", (name,)
                )
                conn.commit()
                logger.info("Migration applied: %s", name)
            except Exception as e:
                conn.rollback()
                logger.error("Migration failed: %s — %s", name, e)
                raise

    conn.close()


def _migrate_001_version_column(conn: sqlite3.Connection) -> None:
    """Add version column to matches for optimistic locking."""
    try:
        conn.execute("ALTER TABLE matches ADD COLUMN version INTEGER DEFAULT 0")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
        logger.info("Column 'version' already exists in matches table")


def _migrate_002_users_table(conn: sqlite3.Connection) -> None:
    """Create users table for authentication."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'PLAYER',
            player_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )


def _migrate_003_player_status(conn: sqlite3.Connection) -> None:
    """Add withdrawal tracking columns to tournament_players."""
    try:
        conn.execute(
            "ALTER TABLE tournament_players ADD COLUMN status TEXT DEFAULT 'active'"
        )
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise

    try:
        conn.execute(
            "ALTER TABLE tournament_players ADD COLUMN withdrawal_round INTEGER"
        )
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
