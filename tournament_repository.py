import sqlite3
import json
from typing import Any
from tournament_core import ITournamentRepository, Player, Match, MatchResult


class SQLiteTournamentRepository(ITournamentRepository):
    """SQLite implementation of tournament repository."""

    def __init__(self, db_path: str = "tournament.db"):
        self.db_path = db_path
        self._init_database()

    def _get_connection(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cur = conn.cursor()

            # Players table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS players (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT
                )
            """
            )

            # Tournaments table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tournaments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT,
                    default_calculator TEXT DEFAULT 'standard'
                )
            """
            )

            # Tournament players table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tournament_players (
                    tournament_id TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    added_at TEXT,
                    able_to_play INTEGER DEFAULT 1,
                    PRIMARY KEY (tournament_id, player_id)
                )
            """
            )

            # Rounds table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rounds (
                    id TEXT PRIMARY KEY,
                    tournament_id TEXT,
                    round_type TEXT,
                    ordinal INTEGER,
                    created_at TEXT
                )
            """
            )

            # Matches table (updated for n-player support)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS matches (
                    id TEXT PRIMARY KEY,
                    round_id TEXT,
                    tournament_id TEXT,
                    player_ids TEXT,  -- JSON array of player IDs
                    scheduled_at TEXT,
                    result TEXT,
                    winner_ids TEXT,  -- JSON array of winner IDs
                    rankings TEXT,    -- JSON object of player_id -> rank
                    auto_bye INTEGER DEFAULT 0,
                    players_per_match INTEGER DEFAULT 2
                )
            """
            )

            # Stats table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS stats (
                    player_id TEXT,
                    tournament_id TEXT,
                    wins REAL DEFAULT 0,
                    draws REAL DEFAULT 0,
                    losses REAL DEFAULT 0,
                    matches_played INTEGER DEFAULT 0,
                    points REAL DEFAULT 0,
                    PRIMARY KEY(player_id, tournament_id)
                )
            """
            )

            # Waiting list table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS waiting_list (
                    id TEXT PRIMARY KEY,
                    tournament_id TEXT,
                    player_id TEXT,
                    added_at TEXT
                )
            """
            )

            conn.commit()

    def save_player(self, player: Player) -> None:
        """Save a player to the database."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO players (id, name, created_at) VALUES (?, ?, ?)",
                (player.id, player.name, player.created_at),
            )
            conn.commit()

    def get_player(self, player_id: str) -> Player:
        """Get a player by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM players WHERE id = ?", (player_id,)
            ).fetchone()

            if row:
                return Player(
                    id=row["id"], name=row["name"], created_at=row["created_at"]
                )
            raise ValueError("Player Does Not Exists")

    def list_players(self) -> list[Player]:
        """list all players."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM players ORDER BY name").fetchall()

            return [
                Player(id=r["id"], name=r["name"], created_at=r["created_at"])
                for r in rows
            ]

    def save_match(self, match: Match) -> None:
        """Save a match to the database."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO matches 
                (id, round_id, tournament_id, player_ids, scheduled_at, result, 
                 winner_ids, rankings, auto_bye, players_per_match)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    match.id,
                    match.round_id,
                    match.tournament_id,
                    json.dumps(match.player_ids),
                    match.scheduled_at,
                    match.result,
                    json.dumps(match.winner_ids) if match.winner_ids else None,
                    json.dumps(match.rankings) if match.rankings else None,
                    1 if match.auto_bye else 0,
                    match.players_per_match,
                ),
            )
            conn.commit()

    def get_match(self, match_id: str) -> Match:
        """Get a match by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM matches WHERE id = ?", (match_id,)
            ).fetchone()

            if row:
                return self._row_to_match(row)
            raise ValueError("Match Does Not Exists")

    def list_matches_for_round(self, round_id: str) -> list[Match]:
        """list all matches for a round."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM matches WHERE round_id = ?", (round_id,)
            ).fetchall()

            return [self._row_to_match(r) for r in rows]

    def update_match_result(self, match_id: str, result: MatchResult) -> None:
        """Update match result."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE matches 
                SET result = ?, winner_ids = ?, rankings = ?
                WHERE id = ?
            """,
                (
                    "draw" if result.is_draw else "complete",
                    json.dumps(result.winner_ids),
                    json.dumps(result.rankings),
                    match_id,
                ),
            )
            conn.commit()

    def save_tournament(self, tournament_id: str, name: str, created_at: str) -> None:
        """Save a tournament."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO tournaments (id, name, created_at) VALUES (?, ?, ?)",
                (tournament_id, name, created_at),
            )
            conn.commit()

    def get_tournament_players(self, tournament_id: str) -> list[dict[str, Any]]:
        """Get all players in a tournament."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT p.id as player_id, p.name, tp.able_to_play
                FROM players p
                JOIN tournament_players tp ON tp.player_id = p.id
                WHERE tp.tournament_id = ?
                ORDER BY p.name
            """,
                (tournament_id,),
            ).fetchall()

            return [dict(r) for r in rows]

    def add_player_to_tournament(self, tournament_id: str, player_id: str) -> None:
        """Add a player to a tournament."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO tournament_players 
                (tournament_id, player_id, added_at, able_to_play)
                VALUES (?, ?, datetime('now'), 1)
            """,
                (tournament_id, player_id),
            )

            conn.execute(
                """
                INSERT OR IGNORE INTO stats (player_id, tournament_id)
                VALUES (?, ?)
            """,
                (player_id, tournament_id),
            )

            conn.commit()

    def save_round(
        self,
        round_id: str,
        tournament_id: str,
        round_type: str,
        ordinal: int,
        created_at: str,
    ) -> None:
        """Save a round."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO rounds (id, tournament_id, round_type, ordinal, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (round_id, tournament_id, round_type, ordinal, created_at),
            )
            conn.commit()

    def get_stats(self, tournament_id: str) -> list[dict[str, Any]]:
        """Get tournament statistics."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT s.player_id, p.name, s.wins, s.draws, s.losses, 
                       s.matches_played, s.points
                FROM stats s
                JOIN players p ON p.id = s.player_id
                WHERE s.tournament_id = ?
                ORDER BY s.points DESC, s.wins DESC
            """,
                (tournament_id,),
            ).fetchall()

            return [dict(r) for r in rows]

    def update_player_stats(
        self, tournament_id: str, player_id: str, stats: dict[str, float]
    ) -> None:
        """Update player statistics."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO stats 
                (player_id, tournament_id, wins, draws, losses, matches_played, points)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    player_id,
                    tournament_id,
                    stats.get("wins", 0),
                    stats.get("draws", 0),
                    stats.get("losses", 0),
                    stats.get("matches_played", 0),
                    stats.get("points", 0),
                ),
            )
            conn.commit()

    def _row_to_match(self, row) -> Match:
        """Convert database row to Match object."""
        return Match(
            id=row["id"],
            round_id=row["round_id"],
            tournament_id=row["tournament_id"],
            player_ids=json.loads(row["player_ids"]),
            scheduled_at=row["scheduled_at"],
            result=row["result"],
            winner_ids=json.loads(row["winner_ids"]) if row["winner_ids"] else None,
            rankings=json.loads(row["rankings"]) if row["rankings"] else None,
            auto_bye=bool(row["auto_bye"]),
            players_per_match=row["players_per_match"],
        )
