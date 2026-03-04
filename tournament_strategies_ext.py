"""
Extended Matchmaking Strategies
================================
New strategies: Double Elimination, Color-Balanced Swiss.
"""

import random
from dataclasses import dataclass
from typing import Any

from tournament_core import (
    IMatchmakingStrategy,
    ITournamentRepository,
    Match,
    RoundConfig,
    generate_id,
    now_iso,
)


@dataclass
class _BracketState:
    """Internal tracker for a single player's bracket position."""

    player_id: str
    losses: int = 0
    bracket: str = "winners"


class DoubleEliminationStrategy(IMatchmakingStrategy):
    """Double-elimination bracket: lose once → losers bracket, lose twice → out.

    Bracket state is persisted via `additional_params["bracket_state"]` on each
    RoundConfig so the caller can reload it across rounds.

    Grand final: the winners-bracket champion faces the losers-bracket champion.
    If the losers-bracket champion wins the first grand-final match, a second
    "true final" is played (because the winners-bracket champion has only one loss).
    """

    def get_strategy_name(self) -> str:
        return "double_elimination"

    def can_create_round(
        self, tournament_id: str, repository: ITournamentRepository, config: RoundConfig
    ) -> tuple[bool, str]:
        players = self._get_active_players(repository, tournament_id)
        if len(players) < 2:
            return False, "Need at least 2 active players"
        return True, ""

    def create_matches(
        self,
        tournament_id: str,
        round_id: str,
        available_players: list[dict[str, Any]],
        config: RoundConfig,
    ) -> dict[str, Any]:
        params = config.additional_params or {}
        bracket_state: dict[str, dict] = params.get("bracket_state", {})

        if not bracket_state:
            for p in available_players:
                pid = p["player_id"]
                bracket_state[pid] = {"losses": 0, "bracket": "winners"}

        winners = [pid for pid, s in bracket_state.items() if s["bracket"] == "winners"]
        losers = [pid for pid, s in bracket_state.items() if s["bracket"] == "losers"]

        matches: list[Match] = []

        random.shuffle(winners)
        matches.extend(self._pair_bracket(winners, tournament_id, round_id, "winners"))

        random.shuffle(losers)
        matches.extend(self._pair_bracket(losers, tournament_id, round_id, "losers"))

        if len(winners) == 1 and len(losers) == 1:
            gf = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=[winners[0], losers[0]],
                scheduled_at=now_iso(),
                players_per_match=2,
            )
            matches = [gf]

        for m in matches:
            config.additional_params = config.additional_params or {}
            config.additional_params["bracket_state"] = bracket_state

        return {
            "matches": matches,
            "bracket_state": bracket_state,
        }

    @staticmethod
    def _pair_bracket(
        player_ids: list[str], tournament_id: str, round_id: str, bracket: str
    ) -> list[Match]:
        """Pair players in a bracket; give bye to odd player out."""
        matches: list[Match] = []
        i = 0
        while i + 1 < len(player_ids):
            m = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=[player_ids[i], player_ids[i + 1]],
                scheduled_at=now_iso(),
                players_per_match=2,
            )
            matches.append(m)
            i += 2

        if i < len(player_ids):
            bye = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=[player_ids[i]],
                scheduled_at=now_iso(),
                auto_bye=True,
                players_per_match=2,
            )
            matches.append(bye)

        return matches

    @staticmethod
    def update_bracket_state(
        bracket_state: dict[str, dict], match: Match, result: Any
    ) -> dict[str, dict]:
        """Call after recording a result to advance/eliminate players.

        Returns updated bracket_state dict for storage.
        """
        if match.auto_bye or not result:
            return bracket_state

        for pid in match.player_ids:
            state = bracket_state.get(pid)
            if not state:
                continue
            if pid not in (result.winner_ids or []):
                state["losses"] += 1
                if state["losses"] >= 2:
                    state["bracket"] = "eliminated"
                elif state["bracket"] == "winners":
                    state["bracket"] = "losers"
        return bracket_state

    @staticmethod
    def _get_active_players(
        repository: ITournamentRepository, tournament_id: str
    ) -> list[dict]:
        players = repository.get_tournament_players(tournament_id)
        return [p for p in players if p.get("able_to_play", 1)]


class ColorBalancedSwissStrategy(IMatchmakingStrategy):
    """Swiss pairing with FIDE-style color balance tracking.

    Ensures that no player gets the same color three times in a row and
    that colour assignments are as balanced as possible.

    Color history is tracked via `additional_params["color_history"]`:
        { "player_id": ["white", "black", "white", ...] }
    """

    def get_strategy_name(self) -> str:
        return "color_balanced_swiss"

    def can_create_round(
        self, tournament_id: str, repository: ITournamentRepository, config: RoundConfig
    ) -> tuple[bool, str]:
        players = repository.get_tournament_players(tournament_id)
        active = [p for p in players if p.get("able_to_play", 1)]
        if len(active) < 2:
            return False, "Need at least 2 active players"
        return True, ""

    def create_matches(
        self,
        tournament_id: str,
        round_id: str,
        available_players: list[dict[str, Any]],
        config: RoundConfig,
    ) -> dict[str, Any]:
        params = config.additional_params or {}
        color_history: dict[str, list[str]] = params.get("color_history", {})

        stats = params.get("stats", [])

        sorted_players = sorted(
            available_players,
            key=lambda p: (-self._get_points(p["player_id"], stats), p.get("name", "")),
        )

        matches: list[Match] = []
        paired: set[str] = set()

        if len(sorted_players) % 2 == 1:
            bye_player = sorted_players[-1]
            sorted_players = sorted_players[:-1]
            bye = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=[bye_player["player_id"]],
                scheduled_at=now_iso(),
                auto_bye=True,
                players_per_match=2,
            )
            matches.append(bye)

        board = 1
        for i in range(0, len(sorted_players) - 1, 2):
            p1 = sorted_players[i]["player_id"]
            p2 = sorted_players[i + 1]["player_id"]

            c1, c2 = self._assign_colors(p1, p2, color_history)

            color_history.setdefault(p1, []).append(c1)
            color_history.setdefault(p2, []).append(c2)

            m = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=[p1, p2],
                scheduled_at=now_iso(),
                players_per_match=2,
                board_no=board,
                colors=[c1, c2],
            )
            matches.append(m)
            board += 1

        return {
            "matches": matches,
            "color_history": color_history,
        }

    @staticmethod
    def _get_points(player_id: str, stats: list[dict]) -> float:
        for s in stats:
            if s.get("player_id") == player_id:
                return s.get("points", 0)
        return 0.0

    @staticmethod
    def _assign_colors(
        p1: str, p2: str, history: dict[str, list[str]]
    ) -> tuple[str, str]:
        """Assign white/black respecting the FIDE balance rules.

        Rules:
        1. No player may have the same colour three times in a row.
        2. The player with the stronger colour preference (more games
           as one colour) gets the opposite colour.
        3. If equal, the higher-seeded player (p1) gets white.
        """
        h1 = history.get(p1, [])
        h2 = history.get(p2, [])

        def _needs_opposite(h: list[str]) -> str | None:
            if len(h) >= 2 and h[-1] == h[-2]:
                return "black" if h[-1] == "white" else "white"
            return None

        forced_1 = _needs_opposite(h1)
        forced_2 = _needs_opposite(h2)

        if forced_1 and not forced_2:
            return forced_1, ("black" if forced_1 == "white" else "white")
        if forced_2 and not forced_1:
            c2 = forced_2
            return ("black" if c2 == "white" else "white"), c2
        if forced_1 and forced_2:
            return forced_1, forced_2

        whites_1 = h1.count("white")
        whites_2 = h2.count("white")

        if whites_1 > whites_2:
            return "black", "white"
        elif whites_2 > whites_1:
            return "white", "black"

        return "white", "black"
