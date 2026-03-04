"""
Chess FIDE Swiss Plugin
=======================
Full Chess-Result.com / Swiss-Manager feature parity.
FIDE Dutch Swiss pairing, auto age-categories, tiebreaks,
crosstables, player cards, title norms.

All chess-specific data stored in isolated 'chess_fide.db'.
"""

import json
import math
import sqlite3
from datetime import date
from typing import Any

from tournament_core import (
    IMatchmakingStrategy,
    IPointsCalculator,
    ITournamentRepository,
    Match,
    MatchResult,
    RoundConfig,
    generate_id,
    now_iso,
)

# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────

FIDE_CATEGORIES = ["U7", "U9", "U11", "U13", "U15", "U17", "U19", "Open"]
FIDE_TITLES = ["GM", "IM", "FM", "CM", "WGM", "WIM", "WFM", "WCM", ""]

# Title norm thresholds (performance rating)
TITLE_NORM_THRESHOLDS = {
    "GM": 2600,
    "IM": 2450,
    "FM": 2300,
    "WGM": 2300,
    "WIM": 2150,
    "WFM": 2000,
    "CM": 2200,
    "WCM": 2000,
}


# ──────────────────────────────────────────────
#  ChessFideDB — Isolated temp database
# ──────────────────────────────────────────────


class ChessFideDB:
    """Manages all FIDE-specific data in a separate chess_fide.db."""

    def __init__(self, db_path: str = "chess_fide.db"):
        self.db_path = db_path
        self._init_database()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_database(self):
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS fide_tournaments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tournament_date TEXT NOT NULL,
                max_rounds INTEGER NOT NULL DEFAULT 7,
                venue TEXT DEFAULT '',
                arbiter TEXT DEFAULT '',
                chief_arbiter TEXT DEFAULT '',
                time_control TEXT DEFAULT 'Standard',
                categories TEXT DEFAULT '[]',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS fide_players (
                player_id TEXT PRIMARY KEY,
                fide_id TEXT DEFAULT '',
                name TEXT NOT NULL,
                rating INTEGER DEFAULT 0,
                dob TEXT DEFAULT '',
                federation TEXT DEFAULT '',
                title TEXT DEFAULT '',
                club TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS fide_tournament_players (
                tournament_id TEXT NOT NULL,
                player_id TEXT NOT NULL,
                category TEXT DEFAULT 'Open',
                starting_rank INTEGER DEFAULT 0,
                initial_rating INTEGER DEFAULT 0,
                PRIMARY KEY (tournament_id, player_id)
            );

            CREATE TABLE IF NOT EXISTS fide_colors (
                tournament_id TEXT NOT NULL,
                round_ordinal INTEGER NOT NULL,
                player_id TEXT NOT NULL,
                color TEXT NOT NULL,
                opponent_id TEXT DEFAULT '',
                board_number INTEGER DEFAULT 0,
                result TEXT DEFAULT '',
                PRIMARY KEY (tournament_id, round_ordinal, player_id)
            );

            CREATE TABLE IF NOT EXISTS fide_byes (
                tournament_id TEXT NOT NULL,
                player_id TEXT NOT NULL,
                round_ordinal INTEGER NOT NULL,
                bye_type TEXT DEFAULT 'full',
                PRIMARY KEY (tournament_id, player_id, round_ordinal)
            );

            CREATE TABLE IF NOT EXISTS fide_rounds (
                tournament_id TEXT NOT NULL,
                round_ordinal INTEGER NOT NULL,
                round_id TEXT NOT NULL,
                created_at TEXT,
                PRIMARY KEY (tournament_id, round_ordinal)
            );
            """)

    # ── Tournament CRUD ──

    def create_tournament(
        self,
        tid: str,
        name: str,
        tournament_date: str,
        max_rounds: int,
        venue: str = "",
        arbiter: str = "",
        chief_arbiter: str = "",
        time_control: str = "Standard",
        categories: list[str] | None = None,
    ) -> dict:
        cats = categories or ["Open"]
        with self._conn() as c:
            c.execute(
                """INSERT INTO fide_tournaments
                   (id, name, tournament_date, max_rounds, venue, arbiter,
                    chief_arbiter, time_control, categories, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    tid,
                    name,
                    tournament_date,
                    max_rounds,
                    venue,
                    arbiter,
                    chief_arbiter,
                    time_control,
                    json.dumps(cats),
                    now_iso(),
                ),
            )
        return {"id": tid, "name": name}

    def get_tournament(self, tid: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM fide_tournaments WHERE id = ?", (tid,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["categories"] = json.loads(d["categories"])
            return d

    def list_tournaments(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM fide_tournaments ORDER BY created_at DESC"
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["categories"] = json.loads(d["categories"])
                result.append(d)
            return result

    def get_current_round_count(self, tid: str) -> int:
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) as cnt FROM fide_rounds WHERE tournament_id = ?",
                (tid,),
            ).fetchone()
            return row["cnt"] if row else 0

    # ── Player CRUD ──

    def register_player(
        self,
        player_id: str,
        name: str,
        rating: int = 0,
        dob: str = "",
        federation: str = "",
        title: str = "",
        club: str = "",
        fide_id: str = "",
    ) -> dict:
        with self._conn() as c:
            if fide_id:
                row = c.execute(
                    "SELECT player_id FROM fide_players WHERE fide_id = ?",
                    (fide_id,),
                ).fetchone()
                if row and row["player_id"] != player_id:
                    raise ValueError("FIDE ID already assigned to another player")
            c.execute(
                """INSERT OR REPLACE INTO fide_players
                   (player_id, fide_id, name, rating, dob, federation, title, club)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (player_id, fide_id, name, rating, dob, federation, title, club),
            )
        return {"player_id": player_id, "name": name}

    def get_player(self, player_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM fide_players WHERE player_id = ?", (player_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_player_by_fide_id(self, fide_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM fide_players WHERE fide_id = ?", (fide_id,)
            ).fetchone()
            return dict(row) if row else None

    # ── Tournament Player Registration ──

    def add_player_to_tournament(
        self, tid: str, player_id: str, category: str = "Open"
    ) -> None:
        player = self.get_player(player_id)
        rating = player["rating"] if player else 0
        with self._conn() as c:
            c.execute(
                """INSERT OR REPLACE INTO fide_tournament_players
                   (tournament_id, player_id, category, initial_rating)
                   VALUES (?,?,?,?)""",
                (tid, player_id, category, rating),
            )
            self._recalculate_starting_ranks(tid, c)

    def remove_player_from_tournament(self, tid: str, player_id: str) -> None:
        with self._conn() as c:
            c.execute(
                "DELETE FROM fide_tournament_players WHERE tournament_id=? AND player_id=?",
                (tid, player_id),
            )
            self._recalculate_starting_ranks(tid, c)

    def _recalculate_starting_ranks(self, tid: str, conn) -> None:
        rows = conn.execute(
            """SELECT tp.player_id, COALESCE(p.rating,0) as rating
               FROM fide_tournament_players tp
               LEFT JOIN fide_players p ON p.player_id = tp.player_id
               WHERE tp.tournament_id = ?
               ORDER BY rating DESC, p.name ASC""",
            (tid,),
        ).fetchall()
        for i, row in enumerate(rows, 1):
            conn.execute(
                "UPDATE fide_tournament_players SET starting_rank=? WHERE tournament_id=? AND player_id=?",
                (i, tid, row["player_id"]),
            )

    def get_tournament_players(self, tid: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT tp.*, p.name, p.rating, p.dob, p.federation, p.title,
                          p.club, p.fide_id
                   FROM fide_tournament_players tp
                   JOIN fide_players p ON p.player_id = tp.player_id
                   WHERE tp.tournament_id = ?
                   ORDER BY tp.starting_rank ASC""",
                (tid,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Category Engine ──

    @staticmethod
    def calculate_age(dob_str: str, ref_date_str: str) -> int | None:
        """Calculate age on a reference date."""
        try:
            dob = date.fromisoformat(dob_str)
            ref = date.fromisoformat(ref_date_str)
            age = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
            return age
        except (ValueError, TypeError):
            return None

    @staticmethod
    def auto_assign_category(
        dob_str: str, tournament_date_str: str, categories: list[str]
    ) -> str:
        """Auto-assign age category based on DOB and tournament date."""
        age = ChessFideDB.calculate_age(dob_str, tournament_date_str)
        if age is None:
            return "Open"

        # Sort categories by age limit (numerically)
        age_cats = []
        for cat in categories:
            if cat.startswith("U") and cat[1:].isdigit():
                age_cats.append((int(cat[1:]), cat))
        age_cats.sort(key=lambda x: x[0])

        for limit, cat_name in age_cats:
            if age < limit:
                return cat_name

        return "Open"

    # ── Color History ──

    def record_color(
        self,
        tid: str,
        round_ordinal: int,
        player_id: str,
        color: str,
        opponent_id: str,
        board_number: int,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT OR REPLACE INTO fide_colors
                   (tournament_id, round_ordinal, player_id, color, opponent_id, board_number)
                   VALUES (?,?,?,?,?,?)""",
                (tid, round_ordinal, player_id, color, opponent_id, board_number),
            )

    def update_color_result(
        self, tid: str, round_ordinal: int, player_id: str, result: str
    ) -> None:
        with self._conn() as c:
            c.execute(
                """UPDATE fide_colors SET result=?
                   WHERE tournament_id=? AND round_ordinal=? AND player_id=?""",
                (result, tid, round_ordinal, player_id),
            )

    def get_player_color_history(self, tid: str, player_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT * FROM fide_colors
                   WHERE tournament_id=? AND player_id=?
                   ORDER BY round_ordinal""",
                (tid, player_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_round_colors(self, tid: str, round_ordinal: int) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT * FROM fide_colors
                   WHERE tournament_id=? AND round_ordinal=?
                   ORDER BY board_number""",
                (tid, round_ordinal),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_colors(self, tid: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT * FROM fide_colors
                   WHERE tournament_id=?
                   ORDER BY round_ordinal, board_number""",
                (tid,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Bye tracking ──

    def record_bye(
        self, tid: str, player_id: str, round_ordinal: int, bye_type: str = "full"
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO fide_byes VALUES (?,?,?,?)",
                (tid, player_id, round_ordinal, bye_type),
            )

    def player_had_bye(self, tid: str, player_id: str) -> bool:
        with self._conn() as c:
            row = c.execute(
                "SELECT COUNT(*) as cnt FROM fide_byes WHERE tournament_id=? AND player_id=?",
                (tid, player_id),
            ).fetchone()
            return row["cnt"] > 0 if row else False

    # ── Round tracking ──

    def save_fide_round(self, tid: str, round_ordinal: int, round_id: str) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO fide_rounds VALUES (?,?,?,?)",
                (tid, round_ordinal, round_id, now_iso()),
            )

    def get_fide_rounds(self, tid: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM fide_rounds WHERE tournament_id=? ORDER BY round_ordinal",
                (tid,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Opponent history ──

    def get_opponents(self, tid: str, player_id: str) -> list[str]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT opponent_id FROM fide_colors
                   WHERE tournament_id=? AND player_id=? AND opponent_id != ''""",
                (tid, player_id),
            ).fetchall()
            return [r["opponent_id"] for r in rows]

    def have_played(self, tid: str, p1: str, p2: str) -> bool:
        opponents = self.get_opponents(tid, p1)
        return p2 in opponents


# ──────────────────────────────────────────────
#  Tiebreak Engine
# ──────────────────────────────────────────────


class TiebreakEngine:
    """FIDE tiebreak calculations."""

    def __init__(self, fide_db: ChessFideDB, repository: ITournamentRepository):
        self.fide_db = fide_db
        self.repository = repository

    def _get_player_results(self, tid: str) -> dict[str, list[dict]]:
        """Get all results per player: [{opponent_id, result, color, round}]."""
        colors = self.fide_db.get_all_colors(tid)
        results: dict[str, list[dict]] = {}
        for c in colors:
            pid = c["player_id"]
            if pid not in results:
                results[pid] = []
            results[pid].append(
                {
                    "opponent_id": c["opponent_id"],
                    "result": c.get("result", ""),
                    "color": c["color"],
                    "round": c["round_ordinal"],
                }
            )
        return results

    def _get_scores(self, tid: str) -> dict[str, float]:
        """Get current scores for all players."""
        stats = self.repository.get_stats(tid)
        return {s["player_id"]: s["points"] for s in stats}

    def buchholz(self, tid: str, player_id: str) -> float:
        """Sum of opponents' scores."""
        scores = self._get_scores(tid)
        opponents = self.fide_db.get_opponents(tid, player_id)
        return sum(scores.get(opp, 0) for opp in opponents)

    def buchholz_cut1(self, tid: str, player_id: str) -> float:
        """Buchholz minus lowest opponent score."""
        scores = self._get_scores(tid)
        opponents = self.fide_db.get_opponents(tid, player_id)
        opp_scores = [scores.get(opp, 0) for opp in opponents]
        if not opp_scores:
            return 0.0
        return sum(opp_scores) - min(opp_scores)

    def sonneborn_berger(self, tid: str, player_id: str) -> float:
        """Sum of beaten opponents' scores + 0.5 * drawn opponents' scores."""
        scores = self._get_scores(tid)
        results = self._get_player_results(tid)
        player_results = results.get(player_id, [])
        sb = 0.0
        for r in player_results:
            opp_score = scores.get(r["opponent_id"], 0)
            if r["result"] == "1":
                sb += opp_score
            elif r["result"] == "0.5":
                sb += 0.5 * opp_score
        return sb

    def direct_encounter(
        self, tid: str, player_id: str, tied_players: list[str]
    ) -> float:
        """Score against other tied players."""
        results = self._get_player_results(tid)
        player_results = results.get(player_id, [])
        score = 0.0
        for r in player_results:
            if r["opponent_id"] in tied_players:
                try:
                    score += float(r["result"])
                except (ValueError, TypeError):
                    pass
        return score

    def num_wins(self, tid: str, player_id: str) -> int:
        """Number of wins."""
        results = self._get_player_results(tid)
        player_results = results.get(player_id, [])
        return sum(1 for r in player_results if r["result"] == "1")

    def num_black_games(self, tid: str, player_id: str) -> int:
        """Number of games with black pieces."""
        results = self._get_player_results(tid)
        player_results = results.get(player_id, [])
        return sum(1 for r in player_results if r["color"] == "B")

    def performance_rating(self, tid: str, player_id: str) -> float:
        """Performance rating = avg opponent rating + dp from score percentage."""
        players = {p["player_id"]: p for p in self.fide_db.get_tournament_players(tid)}
        opponents = self.fide_db.get_opponents(tid, player_id)
        if not opponents:
            return 0.0

        opp_ratings = [players[opp]["rating"] for opp in opponents if opp in players]
        if not opp_ratings:
            return 0.0

        avg_opp = sum(opp_ratings) / len(opp_ratings)

        scores = self._get_scores(tid)
        player_score = scores.get(player_id, 0)
        games = len(opponents)
        if games == 0:
            return 0.0

        percentage = player_score / games

        # FIDE dp table approximation
        if percentage >= 1.0:
            dp = 800
        elif percentage <= 0.0:
            dp = -800
        else:
            dp = -400 * math.log10(1 / percentage - 1)

        return round(avg_opp + dp, 1)

    def compute_all_tiebreaks(self, tid: str, player_id: str) -> dict[str, float]:
        """Compute all tiebreaks for a player."""
        return {
            "buchholz": round(self.buchholz(tid, player_id), 1),
            "buchholz_cut1": round(self.buchholz_cut1(tid, player_id), 1),
            "sonneborn_berger": round(self.sonneborn_berger(tid, player_id), 1),
            "num_wins": self.num_wins(tid, player_id),
            "num_black": self.num_black_games(tid, player_id),
            "performance_rating": self.performance_rating(tid, player_id),
        }


# ──────────────────────────────────────────────
#  ChessFidePointsCalculator
# ──────────────────────────────────────────────


class ChessFidePointsCalculator(IPointsCalculator):
    """FIDE standard scoring: Win=1, Draw=0.5, Loss=0."""

    def get_calculator_name(self) -> str:
        return "fide_standard"

    def calculate_points(
        self, player_id: str, match: Match, result: MatchResult
    ) -> float:
        if match.auto_bye:
            return 1.0
        if result.is_draw:
            return 0.5
        if player_id in result.winner_ids:
            return 1.0
        return 0.0


# ──────────────────────────────────────────────
#  Title Norm Detection
# ──────────────────────────────────────────────


class TitleNormChecker:
    """Check if players achieved FIDE title norms."""

    def __init__(self, fide_db: ChessFideDB, tiebreak: TiebreakEngine):
        self.fide_db = fide_db
        self.tiebreak = tiebreak

    def check_norms(self, tid: str) -> list[dict]:
        """Check all players for title norms."""
        players = self.fide_db.get_tournament_players(tid)
        norms = []
        for p in players:
            perf = self.tiebreak.performance_rating(tid, p["player_id"])
            opponents = self.fide_db.get_opponents(tid, p["player_id"])
            num_games = len(opponents)

            if num_games < 5:
                continue  # Minimum games for norm

            achieved = []
            for title, threshold in TITLE_NORM_THRESHOLDS.items():
                if perf >= threshold and (
                    not p.get("title")
                    or FIDE_TITLES.index(p.get("title", "")) > FIDE_TITLES.index(title)
                ):
                    achieved.append(title)

            if achieved:
                norms.append(
                    {
                        "player_id": p["player_id"],
                        "name": p["name"],
                        "rating": p["rating"],
                        "performance_rating": perf,
                        "games_played": num_games,
                        "norms_achieved": achieved,
                        "current_title": p.get("title", ""),
                    }
                )
        return norms


# ──────────────────────────────────────────────
#  Report Generators
# ──────────────────────────────────────────────


class FideReports:
    """Generate Chess-Result.com style reports."""

    def __init__(
        self,
        fide_db: ChessFideDB,
        tiebreak: TiebreakEngine,
        repository: ITournamentRepository,
    ):
        self.fide_db = fide_db
        self.tiebreak = tiebreak
        self.repository = repository

    def starting_rank_list(self, tid: str) -> list[dict]:
        """Chess-Result style starting rank list."""
        players = self.fide_db.get_tournament_players(tid)
        result = []
        for p in players:
            result.append(
                {
                    "sno": p["starting_rank"],
                    "title": p.get("title", ""),
                    "name": p["name"],
                    "rating": p["rating"],
                    "fide_id": p.get("fide_id", ""),
                    "federation": p.get("federation", ""),
                    "club": p.get("club", ""),
                    "dob": p.get("dob", ""),
                    "category": p["category"],
                    "player_id": p["player_id"],
                }
            )
        return result

    def round_pairings(self, tid: str, round_ordinal: int) -> list[dict]:
        """Board-by-board pairings for a round."""
        colors = self.fide_db.get_round_colors(tid, round_ordinal)
        players = {p["player_id"]: p for p in self.fide_db.get_tournament_players(tid)}

        # Resolve round_id for this ordinal to look up match IDs from the main DB
        fide_rounds = self.fide_db.get_fide_rounds(tid)
        round_id = None
        for fr in fide_rounds:
            if fr["round_ordinal"] == round_ordinal:
                round_id = fr["round_id"]
                break

        # Build frozenset({white_id, black_id}) -> match_id lookup
        match_id_lookup: dict = {}
        if round_id:
            matches = self.repository.list_matches_for_round(round_id)
            for m in matches:
                if len(m.player_ids) == 2:
                    match_id_lookup[frozenset(m.player_ids)] = m.id

        # Group by board number — each board has two entries (W and B)
        boards: dict[int, dict] = {}
        for c in colors:
            brd = c["board_number"]
            if brd not in boards:
                boards[brd] = {"board": brd}
            if c["color"] == "W":
                p = players.get(c["player_id"], {})
                boards[brd]["white_id"] = c["player_id"]
                boards[brd]["white_name"] = p.get("name", "")
                boards[brd]["white_rating"] = p.get("rating", 0)
                boards[brd]["white_title"] = p.get("title", "")
                boards[brd]["white_result"] = c.get("result", "")
                boards[brd]["white_sno"] = p.get("starting_rank", 0)
            elif c["color"] == "B":
                p = players.get(c["player_id"], {})
                boards[brd]["black_id"] = c["player_id"]
                boards[brd]["black_name"] = p.get("name", "")
                boards[brd]["black_rating"] = p.get("rating", 0)
                boards[brd]["black_title"] = p.get("title", "")
                boards[brd]["black_result"] = c.get("result", "")
                boards[brd]["black_sno"] = p.get("starting_rank", 0)

        # Attach match_id to each board entry
        for brd_data in boards.values():
            wid = brd_data.get("white_id")
            bid = brd_data.get("black_id")
            brd_data["match_id"] = (
                match_id_lookup.get(frozenset([wid, bid])) if wid and bid else None
            )

        return [boards[b] for b in sorted(boards.keys())]

    def standings(self, tid: str, category_filter: str | None = None) -> list[dict]:
        """Full standings with tiebreaks and round-by-round results."""
        stats = self.repository.get_stats(tid)
        players = {p["player_id"]: p for p in self.fide_db.get_tournament_players(tid)}

        standing_data = []
        for s in stats:
            pid = s["player_id"]
            p = players.get(pid)
            if not p:
                continue

            if category_filter and p["category"] != category_filter:
                continue

            tiebreaks = self.tiebreak.compute_all_tiebreaks(tid, pid)

            # Round-by-round results
            color_history = self.fide_db.get_player_color_history(tid, pid)
            round_results = []
            for ch in color_history:
                opp = players.get(ch["opponent_id"], {})
                round_results.append(
                    {
                        "round": ch["round_ordinal"],
                        "color": ch["color"],
                        "opponent_sno": opp.get("starting_rank", 0),
                        "opponent_name": opp.get("name", ""),
                        "result": ch.get("result", ""),
                    }
                )

            standing_data.append(
                {
                    "player_id": pid,
                    "sno": p["starting_rank"],
                    "title": p.get("title", ""),
                    "name": p["name"],
                    "rating": p["rating"],
                    "federation": p.get("federation", ""),
                    "club": p.get("club", ""),
                    "category": p["category"],
                    "points": s["points"],
                    "wins": int(s["wins"]),
                    "draws": int(s["draws"]),
                    "losses": int(s["losses"]),
                    "matches_played": s["matches_played"],
                    **tiebreaks,
                    "round_results": round_results,
                }
            )

        # Sort: points DESC, buchholz DESC, sonneborn_berger DESC
        standing_data.sort(
            key=lambda x: (
                x["points"],
                x["buchholz"],
                x["sonneborn_berger"],
                x["num_wins"],
                x["performance_rating"],
            ),
            reverse=True,
        )

        # Assign ranks
        for i, s in enumerate(standing_data, 1):
            s["rank"] = i

        return standing_data

    def crosstable(self, tid: str) -> dict:
        """N×N crosstable showing all head-to-head results."""
        players = self.fide_db.get_tournament_players(tid)
        player_map = {p["player_id"]: p for p in players}
        stats = self.repository.get_stats(tid)
        scores = {s["player_id"]: s["points"] for s in stats}

        # Sort by score then starting rank
        sorted_players = sorted(
            players,
            key=lambda p: (-scores.get(p["player_id"], 0), p["starting_rank"]),
        )

        # Build result matrix
        all_colors = self.fide_db.get_all_colors(tid)
        result_matrix: dict[str, dict[str, str]] = {}
        for c in all_colors:
            pid = c["player_id"]
            opp = c["opponent_id"]
            if pid not in result_matrix:
                result_matrix[pid] = {}
            res = c.get("result", "")
            color_indicator = "w" if c["color"] == "W" else "b"
            result_matrix[pid][opp] = f"{res}{color_indicator}" if res else ""

        table = []
        for i, p in enumerate(sorted_players, 1):
            pid = p["player_id"]
            row = {
                "ct_rank": i,
                "sno": p["starting_rank"],
                "name": p["name"],
                "rating": p["rating"],
                "title": p.get("title", ""),
                "points": scores.get(pid, 0),
                "results": {},
            }
            for j, opp in enumerate(sorted_players, 1):
                if pid == opp["player_id"]:
                    row["results"][str(j)] = "X"
                else:
                    row["results"][str(j)] = result_matrix.get(pid, {}).get(
                        opp["player_id"], ""
                    )
            table.append(row)

        return {
            "headers": [
                {"ct_rank": i + 1, "name": p["name"], "sno": p["starting_rank"]}
                for i, p in enumerate(sorted_players)
            ],
            "rows": table,
        }

    def player_card(self, tid: str, player_id: str) -> dict:
        """Individual player card with all round details."""
        p = self.fide_db.get_player(player_id)
        if not p:
            return {}

        players = {
            pl["player_id"]: pl for pl in self.fide_db.get_tournament_players(tid)
        }
        tp = players.get(player_id, {})
        stats_list = self.repository.get_stats(tid)
        score = 0.0
        for s in stats_list:
            if s["player_id"] == player_id:
                score = s["points"]
                break

        color_history = self.fide_db.get_player_color_history(tid, player_id)
        rounds = []
        for ch in color_history:
            opp = players.get(ch["opponent_id"], {})
            rounds.append(
                {
                    "round": ch["round_ordinal"],
                    "board": ch["board_number"],
                    "color": ch["color"],
                    "opponent_sno": opp.get("starting_rank", 0),
                    "opponent_name": opp.get("name", ""),
                    "opponent_rating": opp.get("rating", 0),
                    "result": ch.get("result", ""),
                }
            )

        tiebreaks = self.tiebreak.compute_all_tiebreaks(tid, player_id)

        return {
            "player_id": player_id,
            "name": p["name"],
            "rating": p["rating"],
            "fide_id": p.get("fide_id", ""),
            "federation": p.get("federation", ""),
            "title": p.get("title", ""),
            "club": p.get("club", ""),
            "category": tp.get("category", "Open"),
            "starting_rank": tp.get("starting_rank", 0),
            "points": score,
            **tiebreaks,
            "rounds": rounds,
        }


# ──────────────────────────────────────────────
#  ChessFideSwissStrategy — FIDE Dutch Pairing
# ──────────────────────────────────────────────


class ChessFideSwissStrategy(IMatchmakingStrategy):
    """
    FIDE Dutch Swiss System pairing.
    Implements core C.04 rules: score groups, S1/S2 split,
    color alternation, no-repeat, bye assignment, float handling.
    """

    def __init__(self, repository: ITournamentRepository, fide_db: ChessFideDB):
        self.repository = repository
        self.fide_db = fide_db

    def get_strategy_name(self) -> str:
        return "fide_swiss"

    def supports_players_per_match(self, n: int) -> bool:
        return n == 2

    def create_matches(
        self,
        tournament_id: str,
        round_id: str,
        available_players: list[str],
        config: RoundConfig,
    ) -> dict[str, Any]:
        if len(available_players) < 2:
            return {
                "matches": [],
                "waiting_players": available_players,
                "metadata": {},
            }

        # Check max rounds
        tourn = self.fide_db.get_tournament(tournament_id)
        if tourn:
            current = self.fide_db.get_current_round_count(tournament_id)
            if current >= tourn["max_rounds"]:
                return {
                    "matches": [],
                    "waiting_players": available_players,
                    "metadata": {
                        "error": f"Maximum rounds ({tourn['max_rounds']}) reached"
                    },
                }

        # Current round ordinal
        round_ordinal = self.fide_db.get_current_round_count(tournament_id) + 1

        # Get current standings
        stats = self.repository.get_stats(tournament_id)
        player_scores = {s["player_id"]: s["points"] for s in stats}

        # Player data for starting rank tiebreak
        tournament_players = {
            p["player_id"]: p
            for p in self.fide_db.get_tournament_players(tournament_id)
        }

        # Sort by score DESC, then starting_rank ASC
        sorted_players = sorted(
            available_players,
            key=lambda p: (
                -player_scores.get(p, 0),
                tournament_players.get(p, {}).get("starting_rank", 9999),
            ),
        )

        # Handle bye if odd number
        bye_player = None
        if len(sorted_players) % 2 == 1:
            bye_player = self._select_bye_player(tournament_id, sorted_players)
            sorted_players.remove(bye_player)

        # Group by score
        score_groups = self._create_score_groups(sorted_players, player_scores)

        # Pair within score groups
        matches = []
        unpaired: list[str] = []
        board_number = 1

        for group_score, group_players in score_groups:
            # Add any unpaired from previous group (floaters)
            all_in_group = unpaired + group_players
            unpaired = []

            paired_in_group, leftover = self._pair_score_group(
                tournament_id,
                round_id,
                round_ordinal,
                all_in_group,
                player_scores,
                tournament_players,
                board_number,
            )
            matches.extend(paired_in_group)
            board_number += len(paired_in_group)
            unpaired = leftover

        # Any remaining unpaired float further
        while len(unpaired) >= 2:
            p1 = unpaired.pop(0)
            p2 = None
            for i, candidate in enumerate(unpaired):
                if not self.fide_db.have_played(tournament_id, p1, candidate):
                    p2 = unpaired.pop(i)
                    break
            if p2 is None and unpaired:
                p2 = unpaired.pop(0)  # Force pair if no other option

            if p2:
                white, black = self._assign_colors(
                    tournament_id, p1, p2, tournament_players
                )
                match = Match(
                    id=generate_id(),
                    round_id=round_id,
                    tournament_id=tournament_id,
                    player_ids=[white, black],
                    scheduled_at=now_iso(),
                    players_per_match=2,
                )
                matches.append(match)
                self.repository.save_match(match)
                self._record_pairing_colors(
                    tournament_id, round_ordinal, white, black, board_number
                )
                board_number += 1

        # Handle bye
        waiting = list(unpaired)
        if bye_player:
            bye_match = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=[bye_player],
                scheduled_at=now_iso(),
                auto_bye=True,
                players_per_match=2,
                result="complete",
                winner_ids=[bye_player],
                rankings={bye_player: 1},
            )
            matches.append(bye_match)
            self.repository.save_match(bye_match)
            self.fide_db.record_bye(tournament_id, bye_player, round_ordinal, "full")

        # Save round in fide DB
        self.fide_db.save_fide_round(tournament_id, round_ordinal, round_id)

        return {
            "matches": matches,
            "waiting_players": waiting,
            "metadata": {
                "pairing_method": "fide_dutch_swiss",
                "round_ordinal": round_ordinal,
                "boards": board_number - 1,
            },
        }

    def _select_bye_player(self, tournament_id: str, players: list[str]) -> str:
        """Select bye player: lowest ranked who hasn't had a bye."""
        for p in reversed(players):
            if not self.fide_db.player_had_bye(tournament_id, p):
                return p
        # All have had byes, give to lowest ranked
        return players[-1]

    def _create_score_groups(
        self, players: list[str], scores: dict[str, float]
    ) -> list[tuple[float, list[str]]]:
        """Group players by their score."""
        groups: dict[float, list[str]] = {}
        for p in players:
            s = scores.get(p, 0)
            if s not in groups:
                groups[s] = []
            groups[s].append(p)

        return sorted(groups.items(), key=lambda x: -x[0])

    def _pair_score_group(
        self,
        tournament_id: str,
        round_id: str,
        round_ordinal: int,
        players: list[str],
        scores: dict[str, float],
        tournament_players: dict,
        board_start: int,
    ) -> tuple[list[Match], list[str]]:
        """Pair players within a score group using S1/S2 split."""
        if len(players) < 2:
            return [], players

        n = len(players)
        half = n // 2

        s1 = players[:half]  # Top half (higher ranked)
        s2 = players[half:]  # Bottom half

        matches = []
        paired = set()
        board = board_start

        for i, p1 in enumerate(s1):
            if p1 in paired:
                continue

            best_opponent = None
            best_idx = -1

            # Try to pair with corresponding S2 player first
            for j, p2 in enumerate(s2):
                if p2 in paired:
                    continue
                if not self.fide_db.have_played(tournament_id, p1, p2):
                    best_opponent = p2
                    best_idx = j
                    break

            # If no valid opponent in corresponding position, try others
            if best_opponent is None:
                for j, p2 in enumerate(s2):
                    if p2 in paired:
                        continue
                    if not self.fide_db.have_played(tournament_id, p1, p2):
                        best_opponent = p2
                        best_idx = j
                        break

            # Last resort: pair even if already played
            if best_opponent is None:
                for j, p2 in enumerate(s2):
                    if p2 in paired:
                        continue
                    best_opponent = p2
                    best_idx = j
                    break

            if best_opponent:
                white, black = self._assign_colors(
                    tournament_id, p1, best_opponent, tournament_players
                )
                match = Match(
                    id=generate_id(),
                    round_id=round_id,
                    tournament_id=tournament_id,
                    player_ids=[white, black],
                    scheduled_at=now_iso(),
                    players_per_match=2,
                )
                matches.append(match)
                self.repository.save_match(match)
                self._record_pairing_colors(
                    tournament_id, round_ordinal, white, black, board
                )
                paired.add(p1)
                paired.add(best_opponent)
                board += 1

        unpaired = [p for p in players if p not in paired]
        return matches, unpaired

    def _assign_colors(
        self,
        tournament_id: str,
        p1: str,
        p2: str,
        tournament_players: dict,
    ) -> tuple[str, str]:
        """
        Assign White/Black per FIDE color allocation rules:
        1. Alternate from last game
        2. Balance W/B counts (diff ≤ 1)
        3. Higher-ranked gets preference
        """
        h1 = self.fide_db.get_player_color_history(tournament_id, p1)
        h2 = self.fide_db.get_player_color_history(tournament_id, p2)

        last1 = h1[-1]["color"] if h1 else None
        last2 = h2[-1]["color"] if h2 else None

        w_count1 = sum(1 for h in h1 if h["color"] == "W")
        b_count1 = sum(1 for h in h1 if h["color"] == "B")
        w_count2 = sum(1 for h in h2 if h["color"] == "W")
        b_count2 = sum(1 for h in h2 if h["color"] == "B")

        # Due color: opposite of last played
        due1 = "B" if last1 == "W" else "W"
        due2 = "B" if last2 == "W" else "W"

        # If both want same color, give to higher ranked (lower starting_rank)
        if due1 != due2:
            # Compatible — p1 gets due1, p2 gets due2
            if due1 == "W":
                return p1, p2
            else:
                return p2, p1
        else:
            # Both want same color — resolve by:
            # 1) Give to the one with fewer games of that color
            # 2) Higher ranked (lower starting_rank) gets preference
            r1 = tournament_players.get(p1, {}).get("starting_rank", 9999)
            r2 = tournament_players.get(p2, {}).get("starting_rank", 9999)

            if due1 == "W":
                # Both want white
                if w_count1 <= w_count2:
                    return p1, p2  # p1 gets white
                elif w_count2 < w_count1:
                    return p2, p1  # p2 gets white
                else:
                    return (p1, p2) if r1 < r2 else (p2, p1)
            else:
                # Both want black
                if b_count1 <= b_count2:
                    return p2, p1  # p1 gets black
                elif b_count2 < b_count1:
                    return p1, p2  # p2 gets black
                else:
                    return (p2, p1) if r1 < r2 else (p1, p2)

    def _record_pairing_colors(
        self,
        tournament_id: str,
        round_ordinal: int,
        white: str,
        black: str,
        board: int,
    ) -> None:
        """Record color assignments for the pairing."""
        self.fide_db.record_color(
            tournament_id, round_ordinal, white, "W", black, board
        )
        self.fide_db.record_color(
            tournament_id, round_ordinal, black, "B", white, board
        )
