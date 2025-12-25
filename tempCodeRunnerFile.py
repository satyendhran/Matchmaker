import secrets

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from plugin_loader import PluginLoader
from tournament_calculators import (
    PercentagePointsCalculator,
    RankingPointsCalculator,
    StandardPointsCalculator,
    ThreePointsCalculator,
)
from tournament_core import (
    MatchmakingStrategyRegistry,
    MatchResult,
    PointsCalculatorRegistry,
    RoundConfig,
)
from tournament_repository import SQLiteTournamentRepository
from tournament_service import TournamentService
from tournament_strategies import (
    FreeForAllStrategy,
    RoundRobinStrategy,
    SingleEliminationStrategy,
    SwissStrategy,
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)


class TournamentWebApp:
    """Service layer for Flask application."""

    def __init__(self):
        self.repository = SQLiteTournamentRepository()
        self.strategy_registry = MatchmakingStrategyRegistry()
        self.calculator_registry = PointsCalculatorRegistry()

        self._register_builtin_strategies()
        self._register_builtin_calculators()

        self.plugin_loader = PluginLoader(
            self.strategy_registry, self.calculator_registry, self.repository
        )

        self.service = TournamentService(
            self.repository, self.strategy_registry, self.calculator_registry
        )

        self.plugin_loader.discover_and_load_plugins()

    def _register_builtin_strategies(self):
        self.strategy_registry.register(RoundRobinStrategy(self.repository))
        self.strategy_registry.register(SingleEliminationStrategy(self.repository))
        self.strategy_registry.register(SwissStrategy(self.repository))
        self.strategy_registry.register(FreeForAllStrategy(self.repository))

    def _register_builtin_calculators(self):
        self.calculator_registry.register(StandardPointsCalculator())
        self.calculator_registry.register(ThreePointsCalculator())
        self.calculator_registry.register(RankingPointsCalculator())
        self.calculator_registry.register(PercentagePointsCalculator())


# Initialize app service
app_service = TournamentWebApp()


@app.route("/")
def index():
    """Main page."""
    return render_template("index3.html")


@app.route("/api/players", methods=["GET"])
def get_players():
    """Get all players."""
    try:
        players = app_service.service.list_players()
        return jsonify(
            [{"id": p.id, "name": p.name, "short_id": p.id[:8]} for p in players]
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/players", methods=["POST"])
def create_player():
    """Create a new player."""
    try:
        data = request.get_json()
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "Name is required"}), 400

        player_id = app_service.service.create_player(name)
        return jsonify({"id": player_id, "name": name}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tournaments", methods=["GET"])
def get_tournaments():
    """Get all tournaments."""
    try:
        with app_service.repository._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, name, created_at FROM tournaments ORDER BY created_at DESC"
            ).fetchall()
            return jsonify(
                [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "short_id": r["id"][:8],
                        "created_at": r["created_at"],
                    }
                    for r in rows
                ]
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tournaments", methods=["POST"])
def create_tournament():
    """Create a new tournament."""
    try:
        data = request.get_json()
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "Name is required"}), 400

        tournament_id = app_service.service.create_tournament(name)
        return jsonify({"id": tournament_id, "name": name}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tournaments/<tournament_id>", methods=["GET"])
def get_tournament(tournament_id):
    """Get tournament details."""
    try:
        with app_service.repository._get_connection() as conn:
            tournament = conn.execute(
                "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
            ).fetchone()

            if not tournament:
                return jsonify({"error": "Tournament not found"}), 404

            players = app_service.repository.get_tournament_players(tournament_id)

            return jsonify(
                {
                    "id": tournament["id"],
                    "name": tournament["name"],
                    "players": [
                        {
                            "player_id": p["player_id"],
                            "name": p["name"],
                            "able_to_play": p.get("able_to_play", 1),
                            "short_id": p["player_id"][:8],
                        }
                        for p in players
                    ],
                }
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tournaments/<tournament_id>/players", methods=["POST"])
def add_players_to_tournament(tournament_id):
    """Add players to tournament."""
    try:
        data = request.get_json()
        player_ids = data.get("player_ids", [])

        for player_id in player_ids:
            app_service.service.add_player_to_tournament(tournament_id, player_id)

        return jsonify({"message": f"{len(player_ids)} player(s) added"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tournaments/<tournament_id>/calculator", methods=["POST"])
def set_tournament_calculator(tournament_id):
    """Set tournament calculator."""
    try:
        data = request.get_json()
        calculator = data.get("calculator")

        app_service.service.set_default_calculator(calculator)
        return jsonify({"message": f"Calculator set to {calculator}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tournaments/<tournament_id>/rounds", methods=["GET"])
def get_rounds(tournament_id):
    """Get tournament rounds."""
    try:
        with app_service.repository._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, round_type, ordinal FROM rounds WHERE tournament_id = ? ORDER BY ordinal",
                (tournament_id,),
            ).fetchall()

            return jsonify(
                [
                    {
                        "id": r["id"],
                        "round_type": r["round_type"],
                        "ordinal": r["ordinal"],
                        "short_id": r["id"][:8],
                    }
                    for r in rows
                ]
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tournaments/<tournament_id>/rounds", methods=["POST"])
def create_round(tournament_id):
    """Create a new round."""
    try:
        # Check for incomplete matches
        with app_service.repository._get_connection() as conn:
            unfinished = conn.execute(
                """
                SELECT COUNT(*) AS incomplete_count
                FROM matches m
                JOIN rounds r ON m.round_id = r.id
                WHERE r.tournament_id = ?
                AND m.result IS NULL
                """,
                (tournament_id,),
            ).fetchone()

            if unfinished and unfinished["incomplete_count"] > 0:
                return (
                    jsonify(
                        {
                            "error": f"There are {unfinished['incomplete_count']} unfinished matches. Complete them first."
                        }
                    ),
                    400,
                )

        data = request.get_json()
        strategy = data.get("strategy")
        players_per_match = data.get("players_per_match", 2)

        # Validate strategy support
        supported = app_service.strategy_registry.get_strategy(strategy)
        if supported and not supported.supports_players_per_match(players_per_match):
            return (
                jsonify(
                    {
                        "error": f"Strategy '{strategy}' doesn't support {players_per_match}-player matches"
                    }
                ),
                400,
            )

        config = RoundConfig(
            tournament_id=tournament_id,
            round_type=strategy,
            players_per_match=players_per_match,
        )

        result = app_service.service.create_round(config)
        return (
            jsonify(
                {
                    "message": f"Round #{result['ordinal']} created",
                    "ordinal": result["ordinal"],
                    "matches": len(result["matches"]),
                    "waiting": len(result["waiting_players"]),
                }
            ),
            201,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rounds/<round_id>/matches", methods=["GET"])
def get_matches(round_id):
    """Get matches for a round."""
    try:
        matches = app_service.repository.list_matches_for_round(round_id)
        round_type = app_service.repository.get_round_type(round_id)

        match_data = []
        for m in matches:
            player_names = []
            for pid in m.player_ids:
                player = app_service.repository.get_player(pid)
                player_names.append(player.name if player else pid[:8])

            status = "pending"
            status_text = "Pending"
            winner_names = []
            eliminated_names = []

            if m.result:
                if m.auto_bye:
                    status = "bye"
                    status_text = "BYE (Auto-advance)"
                elif m.result == "draw":
                    status = "draw"
                    status_text = "DRAW"
                else:
                    status = "completed"
                    if m.winner_ids:
                        for wid in m.winner_ids:
                            wp = app_service.repository.get_player(wid)
                            winner_names.append(wp.name if wp else wid[:8])
                        status_text = f"Winner: {', '.join(winner_names)}"

                        if round_type == "knockout":
                            losers = [
                                pid for pid in m.player_ids if pid not in m.winner_ids
                            ]
                            if losers:
                                for lid in losers:
                                    lp = app_service.repository.get_player(lid)
                                    eliminated_names.append(lp.name if lp else lid[:8])

            match_data.append(
                {
                    "id": m.id,
                    "player_ids": m.player_ids,
                    "player_names": player_names,
                    "status": status,
                    "status_text": status_text,
                    "winner_names": winner_names,
                    "eliminated_names": eliminated_names,
                    "auto_bye": m.auto_bye,
                    "players_per_match": m.players_per_match,
                }
            )

        return jsonify({"round_type": round_type, "matches": match_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/matches/<match_id>/result", methods=["POST"])
def record_match_result(match_id):
    """Record match result."""
    try:
        data = request.get_json()
        result_type = data.get("result_type")  # 'win', 'draw', 'rankings'
        winner_id = data.get("winner_id")
        rankings = data.get("rankings", {})

        # Get match details
        with app_service.repository._get_connection() as conn:
            match_row = conn.execute(
                "SELECT * FROM matches WHERE id = ?", (match_id,)
            ).fetchone()

            if not match_row:
                return jsonify({"error": "Match not found"}), 404

            player_ids = match_row["player_ids"].split(",")

        if result_type == "draw":
            result = MatchResult(
                match_id=match_id, winner_ids=[], rankings={}, is_draw=True
            )
        elif result_type == "win" and winner_id:
            loser_id = [pid for pid in player_ids if pid != winner_id][0]
            result = MatchResult(
                match_id=match_id,
                winner_ids=[winner_id],
                rankings={winner_id: 1, loser_id: 2},
            )
        elif result_type == "rankings" and rankings:
            winners = [pid for pid, rank in rankings.items() if int(rank) == 1]
            result = MatchResult(
                match_id=match_id,
                winner_ids=winners,
                rankings={pid: int(rank) for pid, rank in rankings.items()},
                is_draw=len(winners) > 1,
            )
        else:
            return jsonify({"error": "Invalid result data"}), 400

        app_service.service.record_match_result(match_id, result)
        return jsonify({"message": "Result recorded successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tournaments/<tournament_id>/standings", methods=["GET"])
def get_standings(tournament_id):
    """Get tournament standings."""
    try:
        stats = app_service.service.get_standings(tournament_id)
        return jsonify(
            [
                {
                    "rank": i + 1,
                    "name": s["name"],
                    "points": s["points"],
                    "wins": int(s["wins"]),
                    "draws": int(s["draws"]),
                    "losses": int(s["losses"]),
                    "matches_played": s["matches_played"],
                }
                for i, s in enumerate(stats)
            ]
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategies", methods=["GET"])
def get_strategies():
    """Get available strategies."""
    try:
        strategies = app_service.service.list_available_strategies()
        return jsonify(strategies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/calculators", methods=["GET"])
def get_calculators():
    """Get available calculators."""
    try:
        calculators = app_service.service.list_available_calculators()
        return jsonify(calculators)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/plugins/reload", methods=["POST"])
def reload_plugins():
    """Reload plugins."""
    try:
        app_service.plugin_loader.discover_and_load_plugins()
        return jsonify({"message": "Plugins reloaded successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
