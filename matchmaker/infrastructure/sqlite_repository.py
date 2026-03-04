"""
SQLite repository implementations.

Implements domain repository interfaces using the EXISTING SQLite database.
Adds optimistic locking via version column, proper JSON serialization,
and consistent connection management.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from matchmaker.domain.errors import ConcurrencyConflictError
from matchmaker.domain.interfaces import (
    IMatchRepository,
    IPlayerRepository,
    IUserRepository,
)
from matchmaker.domain.models import (
    MatchAggregate,
    MatchResult,
    MatchState,
    PlayerStatus,
    Role,
    TournamentPlayer,
    User,
)

if TYPE_CHECKING:
    pass


class SQLiteMatchRepository(IMatchRepository):
    """Match repository using the existing SQLite `matches` table.

    Key differences from the old repository:
    - Always uses json.loads() for player_ids (fixes RC-1)
    - Optimistic locking via version column (fixes RC-3)
    - Single connection per operation (fixes RC-2)
    """

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def get(self, match_id: str) -> MatchAggregate | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM matches WHERE id = ?", (match_id,)
            ).fetchone()

            if not row:
                return None

            return self._row_to_aggregate(row)

    def save(self, match: MatchAggregate) -> None:
        with self._conn() as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT version FROM matches WHERE id = ?", (match.id,)
            ).fetchone()

            if existing is not None:
                # UPDATE with optimistic locking
                expected_version = match.version
                new_version = expected_version + 1

                result_str = None
                winner_ids_str = "[]"
                rankings_str = "{}"

                if match.result:
                    result_str = "draw" if match.result.is_draw else "complete"
                    winner_ids_str = json.dumps(match.result.winner_ids)
                    rankings_str = json.dumps(match.result.rankings)

                cursor = conn.execute(
                    """
                    UPDATE matches
                    SET result = ?, winner_ids = ?, rankings = ?, version = ?
                    WHERE id = ? AND version = ?
                    """,
                    (
                        result_str,
                        winner_ids_str,
                        rankings_str,
                        new_version,
                        match.id,
                        expected_version,
                    ),
                )

                if cursor.rowcount == 0:
                    raise ConcurrencyConflictError("match")

                match.version = new_version
                conn.commit()
            else:
                # INSERT — new match
                result_str = None
                winner_ids_str = "[]"
                rankings_str = "{}"

                if match.result:
                    result_str = "draw" if match.result.is_draw else "complete"
                    winner_ids_str = json.dumps(match.result.winner_ids)
                    rankings_str = json.dumps(match.result.rankings)

                conn.execute(
                    """
                    INSERT INTO matches
                        (id, round_id, tournament_id, player_ids, scheduled_at,
                         players_per_match, auto_bye, result, winner_ids,
                         rankings, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match.id,
                        match.round_id,
                        match.tournament_id,
                        json.dumps(match.player_ids),
                        match.scheduled_at,
                        match.players_per_match,
                        1 if match.auto_bye else 0,
                        result_str,
                        winner_ids_str,
                        rankings_str,
                        0,
                    ),
                )
                conn.commit()

    def get_matches_for_round(self, round_id: str) -> list[MatchAggregate]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM matches WHERE round_id = ?", (round_id,)
            ).fetchall()
            return [self._row_to_aggregate(r) for r in rows]

    def has_active_match(self, tournament_id: str, player_id: str) -> bool:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, player_ids, result FROM matches
                WHERE tournament_id = ? AND result IS NULL
                """,
                (tournament_id,),
            ).fetchall()

            for row in rows:
                pids = json.loads(row["player_ids"])
                if player_id in pids:
                    return True
            return False

    def _row_to_aggregate(self, row: sqlite3.Row) -> MatchAggregate:
        """Convert DB row to MatchAggregate with proper JSON deserialization."""
        player_ids = json.loads(row["player_ids"])
        winner_ids = json.loads(row["winner_ids"]) if row["winner_ids"] else []
        rankings = json.loads(row["rankings"]) if row["rankings"] else {}

        # Determine state from result column
        result_col = row["result"]
        if result_col is None:
            state = MatchState.SCHEDULED
            match_result = None
        elif result_col == "draw":
            state = MatchState.COMPLETED
            match_result = MatchResult(winner_ids=[], is_draw=True, rankings=rankings)
        elif result_col in ("complete", "forfeited"):
            state = (
                MatchState.FORFEITED
                if result_col == "forfeited"
                else MatchState.COMPLETED
            )
            match_result = MatchResult(
                winner_ids=winner_ids,
                is_draw=False,
                rankings=rankings,
            )
        else:
            state = MatchState.SCHEDULED
            match_result = None

        # Get version, defaulting to 0 for rows created before migration
        try:
            version = row["version"] if row["version"] is not None else 0
        except (IndexError, KeyError):
            version = 0

        return MatchAggregate(
            id=row["id"],
            round_id=row["round_id"],
            tournament_id=row["tournament_id"],
            player_ids=player_ids,
            state=state,
            result=match_result,
            auto_bye=bool(row["auto_bye"]) if "auto_bye" in row.keys() else False,
            scheduled_at=row["scheduled_at"] if "scheduled_at" in row.keys() else "",
            players_per_match=(
                row["players_per_match"] if "players_per_match" in row.keys() else 2
            ),
            version=version,
        )


class SQLitePlayerRepository(IPlayerRepository):
    """Player tournament status repository."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_tournament_player(
        self, tournament_id: str, player_id: str
    ) -> TournamentPlayer | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT tp.*, s.matches_played
                FROM tournament_players tp
                LEFT JOIN stats s ON s.tournament_id = tp.tournament_id
                    AND s.player_id = tp.player_id
                WHERE tp.tournament_id = ? AND tp.player_id = ?
                """,
                (tournament_id, player_id),
            ).fetchone()

            if not row:
                return None

            status_str = "active"
            withdrawal_round = None
            try:
                status_str = row["status"] or "active"
                withdrawal_round = row["withdrawal_round"]
            except (IndexError, KeyError):
                pass

            return TournamentPlayer(
                player_id=row["player_id"],
                tournament_id=row["tournament_id"],
                status=PlayerStatus(status_str),
                withdrawal_round=withdrawal_round,
                rounds_played=row["matches_played"] if row["matches_played"] else 0,
            )

    def save_tournament_player(self, tp: TournamentPlayer) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE tournament_players
                SET status = ?, withdrawal_round = ?
                WHERE tournament_id = ? AND player_id = ?
                """,
                (
                    tp.status.value,
                    tp.withdrawal_round,
                    tp.tournament_id,
                    tp.player_id,
                ),
            )
            conn.commit()

    def get_active_players(self, tournament_id: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT player_id FROM tournament_players
                WHERE tournament_id = ?
                AND (status IS NULL OR status = 'active')
                """,
                (tournament_id,),
            ).fetchall()
            return [r["player_id"] for r in rows]


class SQLiteUserRepository(IUserRepository):
    """User persistence for auth."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, user_id: str) -> User | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return self._row_to_user(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return self._row_to_user(row) if row else None

    def save(self, user: User) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO users
                    (id, username, password_hash, role, player_id, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    user.id,
                    user.username,
                    user.password_hash,
                    user.role.value,
                    user.player_id,
                ),
            )
            conn.commit()

    def username_exists(self, username: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone()
            return row is not None

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            role=Role(row["role"]),
            player_id=row["player_id"],
            created_at=row["created_at"] if "created_at" in row.keys() else "",
        )
