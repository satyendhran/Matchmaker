import gzip
import json
from typing import Any

from tournament_core import (
    IPointsCalculator,
    ITournamentRepository,
    Match,
    MatchmakingStrategyRegistry,
    MatchResult,
    Player,
    PointsCalculatorRegistry,
    RoundCompletionPolicy,
    RoundConfig,
    TournamentConfig,
    TournamentPhase,
    TournamentTemplate,
    generate_id,
    now_iso,
)


class TournamentService:
    """
    Main service orchestrating tournament operations.
    Follows Dependency Inversion and Single Responsibility principles.
    """

    def __init__(
        self,
        repository: ITournamentRepository,
        strategy_registry: MatchmakingStrategyRegistry,
        calculator_registry: PointsCalculatorRegistry,
    ):
        self.repository = repository
        self.strategy_registry = strategy_registry
        self.calculator_registry = calculator_registry
        self.default_calculator = "standard"

        self._tournament_configs: dict[str, TournamentConfig] = {}

    def create_player(
        self, name: str, date_of_birth: str | None = None, category: str | None = None
    ) -> str:
        """Create a new player."""

        existing = self.repository.get_player_by_name(name)
        if existing:
            raise ValueError(f"Player '{name}' already exists")

        player = Player(
            id=generate_id(),
            name=name,
            created_at=now_iso(),
            date_of_birth=date_of_birth,
            category=category,
        )
        self.repository.save_player(player)
        return player.id

    def list_players(self) -> list[Player]:
        """list all players."""
        return self.repository.list_players()

    def create_tournament(self, name: str) -> str:
        """Create a new tournament."""
        tournament_id = generate_id()
        self.repository.save_tournament(tournament_id, name, now_iso())
        return tournament_id

    def add_player_to_tournament(self, tournament_id: str, player_id: str) -> None:
        """Add a player to a tournament."""
        self.repository.add_player_to_tournament(tournament_id, player_id)

    def create_round(self, config: RoundConfig) -> dict[str, Any]:
        """
        Create a new round with specified strategy.

        Args:
            config: Round configuration including strategy type and parameters

        Returns:
            dict with round_id and matchmaking results
        """

        strategy = self.strategy_registry.get_strategy(config.round_type)
        if not strategy:
            raise ValueError(f"Unknown strategy: {config.round_type}")

        if not strategy.supports_players_per_match(config.players_per_match):
            raise ValueError(
                f"Strategy '{config.round_type}' doesn't support "
                f"{config.players_per_match}-player matches"
            )

        tournament_players = self.repository.get_tournament_players(
            config.tournament_id
        )
        available_players = [
            p["player_id"] for p in tournament_players if p.get("able_to_play", 1) == 1
        ]
        print(f"DEBUG: Service - Available players: {len(available_players)}")
        print(f"DEBUG: Service - Strategy: {config.round_type}")

        if not available_players:
            raise ValueError("No available players for this round")

        if not config.force_create:
            policy = self._get_completion_policy(config.tournament_id)
            if policy == RoundCompletionPolicy.STRICT:
                if self._has_pending_matches(config.tournament_id):
                    raise ValueError(
                        "Previous round has pending matches. "
                        "Set force_create=True or change the tournament's round "
                        "completion policy to FLEXIBLE."
                    )

        round_id = generate_id()
        ordinal = self._get_next_round_ordinal(config.tournament_id)
        self.repository.save_round(
            round_id, config.tournament_id, config.round_type, ordinal, now_iso()
        )

        result = strategy.create_matches(
            config.tournament_id, round_id, available_players, config
        )
        print(f"DEBUG: Service - Matches created: {len(result.get('matches', []))}")

        return {
            "round_id": round_id,
            "ordinal": ordinal,
            "matches": result["matches"],
            "waiting_players": result.get("waiting_players", []),
            "metadata": result.get("metadata", {}),
        }

    def record_match_result(
        self, match_id: str, result: MatchResult, calculator_name: str | None = None
    ) -> None:
        """
        Record the result of a match and update statistics.

        Args:
            match_id: ID of the match
            result: Match result with winners and rankings
            calculator_name: Name of points calculator to use (optional)
        """

        match = self.repository.get_match(match_id)
        if not match:
            raise ValueError(f"Match not found: {match_id}")

        round_type = self.repository.get_round_type(match.round_id)
        is_knockout = round_type == "knockout"

        self.repository.update_match_result(match_id, result)

        calc_name = calculator_name or self.default_calculator
        calculator = self.calculator_registry.get_calculator(calc_name)
        if not calculator:
            calculator = self.calculator_registry.get_calculator(
                self.default_calculator
            )

        self._update_player_statistics(match, result, calculator)

        if is_knockout and not result.is_draw:
            self._handle_knockout_elimination(match, result)

    def get_standings(self, tournament_id: str) -> list[dict[str, Any]]:
        """Get current tournament standings."""
        return self.repository.get_stats(tournament_id)

    def list_available_strategies(self) -> list[str]:
        """list all available matchmaking strategies."""
        return self.strategy_registry.list_strategies()

    def list_available_calculators(self) -> list[str]:
        """list all available points calculators."""
        return self.calculator_registry.list_calculators()

    def get_strategies_for_player_count(self, n: int) -> list[str]:
        """Get strategies that support n-player matches."""
        return self.strategy_registry.get_strategies_for_player_count(n)

    def set_default_calculator(self, calculator_name: str) -> None:
        """Set the default points calculator for the tournament."""
        if calculator_name not in self.calculator_registry.list_calculators():
            raise ValueError(f"Unknown calculator: {calculator_name}")
        self.default_calculator = calculator_name

    def _has_pending_matches(self, tournament_id: str) -> bool:
        """Check if there are any pending matches in the tournament."""
        try:
            with self.repository._get_connection() as conn:
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

                return bool(unfinished and unfinished["incomplete_count"] > 0)
        except AttributeError:
            return False

    def _get_next_round_ordinal(self, tournament_id: str) -> int:
        """Get the ordinal number for the next round."""
        try:
            with self.repository._get_connection() as conn:
                max_ordinal = conn.execute(
                    """
                    SELECT MAX(ordinal) as max_ordinal
                    FROM rounds
                    WHERE tournament_id = ?
                    """,
                    (tournament_id,),
                ).fetchone()

                if max_ordinal and max_ordinal["max_ordinal"] is not None:
                    return max_ordinal["max_ordinal"] + 1
                return 1
        except AttributeError:
            return 1

    def _update_player_statistics(
        self, match: Match, result: MatchResult, calculator: IPointsCalculator
    ) -> None:
        """Update statistics for all players in a match."""
        for player_id in match.player_ids:
            points = calculator.calculate_points(player_id, match, result)

            stats_update = {"matches_played": 1}

            if result.is_draw:
                stats_update["draws"] = 1
                stats_update["points"] = points
            elif player_id in result.winner_ids:
                stats_update["wins"] = 1
                stats_update["points"] = points
            else:
                stats_update["losses"] = 1
                stats_update["points"] = points

            current_stats = self._get_player_stats(match.tournament_id, player_id)
            for key, value in stats_update.items():
                current_stats[key] = current_stats.get(key, 0) + value

            self.repository.update_player_stats(
                match.tournament_id, player_id, current_stats
            )

    def _get_player_stats(self, tournament_id: str, player_id: str) -> dict[str, float]:
        """Get current stats for a player."""
        all_stats = self.repository.get_stats(tournament_id)
        for stat in all_stats:
            if stat["player_id"] == player_id:
                return stat
        return {"wins": 0, "draws": 0, "losses": 0, "matches_played": 0, "points": 0}

    def _handle_knockout_elimination(self, match: Match, result: MatchResult) -> None:
        """Handle player elimination in knockout matches."""

        for player_id in match.player_ids:
            if player_id not in result.winner_ids:
                self.repository.eliminate_player(match.tournament_id, player_id)

        for winner_id in result.winner_ids:
            self.repository.activate_player(match.tournament_id, winner_id)

    def _get_completion_policy(self, tournament_id: str) -> RoundCompletionPolicy:
        """Get the round-completion policy for a tournament.

        Returns STRICT by default unless overridden via
        `set_tournament_config()`.
        """
        tc = self._tournament_configs.get(tournament_id)
        if tc:
            return tc.round_completion_policy

        try:
            tc_data = self.repository.get_tournament_config(tournament_id)
            if tc_data:
                policy = RoundCompletionPolicy(
                    tc_data.get("round_completion_policy", "strict")
                )
                return policy
        except (AttributeError, TypeError):
            pass

        return RoundCompletionPolicy.STRICT

    def set_tournament_config(self, config: TournamentConfig) -> None:
        """Set per-tournament configuration (round completion policy, etc.).

        Example:
            svc.set_tournament_config(TournamentConfig(
                tournament_id="abc",
                round_completion_policy=RoundCompletionPolicy.FLEXIBLE,
            ))
        """
        self._tournament_configs[config.tournament_id] = config

        try:
            self.repository.save_tournament_config(
                config.tournament_id,
                {
                    "round_completion_policy": config.round_completion_policy.value,
                    "min_rounds_before_withdrawal": config.min_rounds_before_withdrawal,
                    "default_calculator": config.default_calculator,
                    "default_strategy": config.default_strategy,
                },
            )
        except AttributeError:
            pass

    def get_tournament_config(self, tournament_id: str) -> TournamentConfig:
        """Get tournament configuration."""
        tc = self._tournament_configs.get(tournament_id)
        if tc:
            return tc
        return TournamentConfig(tournament_id=tournament_id)

    def withdraw_player(
        self,
        tournament_id: str,
        player_id: str,
        reason: str = "",
        current_round: int = 0,
    ) -> None:
        """Withdraw a player from the tournament.

        Respects `min_rounds_before_withdrawal` from tournament config.
        """
        tc = self.get_tournament_config(tournament_id)
        stats = self._get_player_stats(tournament_id, player_id)
        played = int(stats.get("matches_played", 0))

        if played < tc.min_rounds_before_withdrawal:
            raise ValueError(
                f"Player must complete at least {tc.min_rounds_before_withdrawal} "
                f"rounds before withdrawal (played {played})"
            )

        self.repository.eliminate_player(tournament_id, player_id)

    def appeal_match_result(self, match_id: str, reason: str) -> None:
        """File an appeal for a match result."""
        match = self.repository.get_match(match_id)
        if not match:
            raise ValueError(f"Match not found: {match_id}")
        if match.result is None:
            raise ValueError("Cannot appeal a match without a result")

        try:
            self.repository.update_match_appeal(match_id, "pending", reason)
        except AttributeError:
            match.appeal_status = "pending"
            match.appeal_reason = reason

    def resolve_appeal(
        self,
        match_id: str,
        decision: str,
        new_result: MatchResult | None = None,
    ) -> None:
        """Resolve a match appeal (admin action).

        Args:
            match_id: The match to resolve
            decision: "approved" or "rejected"
            new_result: If approved, the corrected result
        """
        if decision not in ("approved", "rejected"):
            raise ValueError("Decision must be 'approved' or 'rejected'")

        try:
            self.repository.update_match_appeal(match_id, decision, None)
        except AttributeError:
            pass

        if decision == "approved" and new_result:
            self.record_match_result(match_id, new_result)

    def auto_adjudicate_round(self, round_id: str) -> list[str]:
        """Forfeit all unfinished matches past round end_time.

        Returns list of forfeited match IDs.
        """
        forfeited: list[str] = []
        try:
            with self.repository._get_connection() as conn:
                rows = conn.execute(
                    "SELECT id FROM matches WHERE round_id = ? AND result IS NULL",
                    (round_id,),
                ).fetchall()
                for row in rows:
                    mid = row["id"]
                    match = self.repository.get_match(mid)
                    if match:
                        forfeit_result = MatchResult(
                            match_id=mid,
                            winner_ids=[],
                            rankings={},
                            is_draw=True,
                        )
                        self.record_match_result(mid, forfeit_result)
                        forfeited.append(mid)
        except AttributeError:
            pass
        return forfeited

    def create_phased_tournament(
        self, name: str, phases: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Create a multi-stage tournament.

        Args:
            name: Tournament name
            phases: List of phase configs, e.g.
                [{"type": "group", "strategy": "swiss", "qualification_count": 8},
                 {"type": "knockout", "strategy": "knockout"}]
        """
        parent_id = self.create_tournament(f"{name} - Main")
        phase_ids: list[str] = []

        for i, phase in enumerate(phases):
            child_id = self.create_tournament(
                f"{name} - Phase {i + 1} ({phase.get('type', 'unknown')})"
            )
            phase_ids.append(child_id)

            tp = TournamentPhase(
                parent_tournament_id=parent_id,
                child_tournament_id=child_id,
                phase_type=phase.get("type", "unknown"),
                qualification_count=phase.get("qualification_count", 0),
            )

            try:
                self.repository.save_phase(tp)
            except AttributeError:
                pass

        return {
            "parent_id": parent_id,
            "phase_ids": phase_ids,
        }

    def advance_to_next_phase(
        self, from_tournament_id: str, to_tournament_id: str, count: int
    ) -> list[str]:
        """Qualify top-N players from one phase to the next.

        Returns list of qualified player IDs.
        """
        standings = self.get_standings(from_tournament_id)
        qualified = [s["player_id"] for s in standings[:count]]

        for pid in qualified:
            self.add_player_to_tournament(to_tournament_id, pid)

        return qualified

    def save_template(self, template: TournamentTemplate) -> None:
        """Save a reusable tournament template."""
        try:
            self.repository.save_template(template)
        except AttributeError:
            if not hasattr(self, "_templates"):
                self._templates: dict[str, TournamentTemplate] = {}
            self._templates[template.name] = template

    def create_from_template(self, template_name: str, tournament_name: str) -> str:
        """Create a tournament from a saved template."""
        template: TournamentTemplate | None = None
        try:
            template = self.repository.get_template(template_name)
        except AttributeError:
            if hasattr(self, "_templates"):
                template = self._templates.get(template_name)

        if not template:
            raise ValueError(f"Template not found: {template_name}")

        tid = self.create_tournament(tournament_name)
        tc = TournamentConfig(
            tournament_id=tid,
            round_completion_policy=template.round_completion_policy,
            default_calculator=template.calculator,
            default_strategy=template.round_type,
        )
        self.set_tournament_config(tc)
        return tid

    def archive_tournament(self, tournament_id: str) -> bytes:
        """Export full tournament state as gzip-compressed JSON."""
        data: dict[str, Any] = {
            "tournament_id": tournament_id,
            "exported_at": now_iso(),
            "standings": self.get_standings(tournament_id),
            "players": [
                p.__dict__
                for p in self.repository.list_players()
                if any(
                    tp["player_id"] == p.id
                    for tp in self.repository.get_tournament_players(tournament_id)
                )
            ],
        }

        rounds_data: list[dict] = []
        try:
            with self.repository._get_connection() as conn:
                rounds = conn.execute(
                    "SELECT * FROM rounds WHERE tournament_id = ? ORDER BY ordinal",
                    (tournament_id,),
                ).fetchall()
                for r in rounds:
                    r_dict = dict(r)
                    matches = self.repository.list_matches_for_round(r["id"])
                    r_dict["matches"] = [m.__dict__ for m in matches]
                    rounds_data.append(r_dict)
        except AttributeError:
            pass
        data["rounds"] = rounds_data

        payload = json.dumps(data, default=str).encode()
        return gzip.compress(payload)


class RoundFactory:
    """
    Factory for creating rounds with different configurations.
    Simplifies round creation with preset configurations.
    """

    @staticmethod
    def create_standard_roundrobin(tournament_id: str) -> RoundConfig:
        """Create configuration for standard 2-player round-robin."""
        return RoundConfig(
            tournament_id=tournament_id, round_type="roundrobin", players_per_match=2
        )

    @staticmethod
    def create_knockout(tournament_id: str, players_per_match: int = 2) -> RoundConfig:
        """Create configuration for knockout round."""
        return RoundConfig(
            tournament_id=tournament_id,
            round_type="knockout",
            players_per_match=players_per_match,
        )

    @staticmethod
    def create_swiss(tournament_id: str) -> RoundConfig:
        """Create configuration for Swiss system round."""
        return RoundConfig(
            tournament_id=tournament_id, round_type="swiss", players_per_match=2
        )

    @staticmethod
    def create_freeforall(tournament_id: str) -> RoundConfig:
        """Create configuration for free-for-all round."""
        return RoundConfig(
            tournament_id=tournament_id,
            round_type="freeforall",
            players_per_match=0,
        )

    @staticmethod
    def create_custom(
        tournament_id: str,
        round_type: str,
        players_per_match: int,
        additional_params: dict[str, Any] | None = None,
    ) -> RoundConfig:
        """Create custom round configuration."""
        return RoundConfig(
            tournament_id=tournament_id,
            round_type=round_type,
            players_per_match=players_per_match,
            additional_params=additional_params or {},
        )
