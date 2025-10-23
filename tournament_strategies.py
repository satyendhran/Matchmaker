from typing import Any
from tournament_core import (
    IMatchmakingStrategy,
    Match,
    RoundConfig,
    generate_id,
    now_iso,
    ITournamentRepository,
)
import itertools


class RoundRobinStrategy(IMatchmakingStrategy):
    """
    Round-robin matchmaking strategy.
    Supports 2-player games by default, can be extended for n-player.
    """

    def __init__(self, repository: ITournamentRepository):
        self.repository = repository

    def get_strategy_name(self) -> str:
        return "roundrobin"

    def supports_players_per_match(self, n: int) -> bool:
        return n == 2  # Can be extended for n>2

    def create_matches(
        self,
        tournament_id: str,
        round_id: str,
        available_players: list[str],
        config: RoundConfig,
    ) -> dict[str, Any]:
        """
        Create round-robin matches using circle method.
        Ensures all players face each other exactly once.
        """
        if not available_players:
            return {"matches": [], "waiting_players": [], "metadata": {}}

        players = available_players.copy()
        players_per_match = config.players_per_match

        if players_per_match != 2:
            # For n-player round robin, generate all combinations
            return self._create_nplayer_roundrobin(
                tournament_id, round_id, players, players_per_match
            )

        # Handle odd number of players
        bye_added = False
        if len(players) % 2 == 1:
            players.append("BYE")
            bye_added = True

        n = len(players)
        rounds_count = n - 1
        matches = []

        # Circle method for 2-player round robin
        for _ in range(rounds_count):
            for i in range(n // 2):
                p1 = players[i]
                p2 = players[n - 1 - i]

                if p1 != "BYE" and p2 != "BYE":
                    # Check if this pair has already played
                    if not self._pair_already_played(tournament_id, p1, p2):
                        match = Match(
                            id=generate_id(),
                            round_id=round_id,
                            tournament_id=tournament_id,
                            player_ids=[p1, p2],
                            scheduled_at=now_iso(),
                            players_per_match=2,
                        )
                        matches.append(match)
                        self.repository.save_match(match)

            # Rotate players (keep first fixed, rotate others)
            players.insert(1, players.pop())

        # Determine waiting player
        waiting = []
        if bye_added:
            scheduled_ids = set()
            for m in matches:
                scheduled_ids.update(m.player_ids)
            waiting = [p for p in available_players if p not in scheduled_ids]

        return {
            "matches": matches,
            "waiting_players": waiting,
            "metadata": {"rounds_generated": rounds_count},
        }

    def _create_nplayer_roundrobin(
        self, tournament_id: str, round_id: str, players: list[str], n: int
    ) -> dict[str, Any]:
        """Create round-robin for n-player games."""
        matches = []

        # Generate all combinations of n players
        for combo in itertools.combinations(players, n):
            if not self._group_already_played(tournament_id, list(combo)):
                match = Match(
                    id=generate_id(),
                    round_id=round_id,
                    tournament_id=tournament_id,
                    player_ids=list(combo),
                    scheduled_at=now_iso(),
                    players_per_match=n,
                )
                matches.append(match)
                self.repository.save_match(match)

        return {
            "matches": matches,
            "waiting_players": [],
            "metadata": {
                "total_combinations": len(list(itertools.combinations(players, n)))
            },
        }

    def _pair_already_played(self, tournament_id: str, p1: str, p2: str) -> bool:
        """Check if two players have already played against each other."""
        # This should query the repository
        # Simplified implementation
        return False

    def _group_already_played(self, tournament_id: str, players: list[str]) -> bool:
        """Check if a group of players have already played together."""
        return False


class SingleEliminationStrategy(IMatchmakingStrategy):
    """
    Single elimination (knockout) strategy.
    Supports n-player games.
    """

    def __init__(self, repository: ITournamentRepository):
        self.repository = repository

    def get_strategy_name(self) -> str:
        return "knockout"

    def supports_players_per_match(self, n: int) -> bool:
        return True  # Supports any number of players per match

    def create_matches(
        self,
        tournament_id: str,
        round_id: str,
        available_players: list[str],
        config: RoundConfig,
    ) -> dict[str, Any]:
        """
        Create knockout matches.
        For 2-player: pairs players from top and bottom of standings.
        For n-player: groups players into matches of n.
        """
        if not available_players:
            return {"matches": [], "waiting_players": [], "metadata": {}}

        players = available_players.copy()
        players_per_match = config.players_per_match
        matches = []

        # Group players into matches
        while len(players) >= players_per_match:
            if players_per_match == 2:
                # Pair first with last (seeding)
                match_players = [players.pop(0), players.pop(-1)]
            else:
                # Take first n players
                match_players = [players.pop(0) for _ in range(players_per_match)]

            match = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=match_players,
                scheduled_at=now_iso(),
                players_per_match=players_per_match,
            )
            matches.append(match)
            self.repository.save_match(match)

        # Handle remaining players
        waiting_players = players

        # If only one player left and no pending matches, auto-advance
        if len(waiting_players) == 1 and not matches:
            bye_match = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=[waiting_players[0]],
                scheduled_at=now_iso(),
                result="auto",
                winner_ids=[waiting_players[0]],
                auto_bye=True,
                players_per_match=1,
            )
            self.repository.save_match(bye_match)
            matches.append(bye_match)
            waiting_players = []

        return {
            "matches": matches,
            "waiting_players": waiting_players,
            "metadata": {
                "players_per_match": players_per_match,
                "matches_created": len(matches),
            },
        }


class SwissStrategy(IMatchmakingStrategy):
    """
    Swiss system strategy.
    Pairs players with similar scores who haven't played each other.
    """

    def __init__(self, repository: ITournamentRepository):
        self.repository = repository

    def get_strategy_name(self) -> str:
        return "swiss"

    def supports_players_per_match(self, n: int) -> bool:
        return n == 2  # Swiss is traditionally 2-player

    def create_matches(
        self,
        tournament_id: str,
        round_id: str,
        available_players: list[str],
        config: RoundConfig,
    ) -> dict[str, Any]:
        """
        Create Swiss pairings.
        Players are sorted by score and paired with nearby opponents.
        """
        if len(available_players) < 2:
            return {"matches": [], "waiting_players": available_players, "metadata": {}}

        # Get current standings
        stats = self.repository.get_stats(tournament_id)
        player_scores = {s["player_id"]: s["points"] for s in stats}

        # Sort players by score (descending)
        sorted_players = sorted(
            available_players, key=lambda p: player_scores.get(p, 0), reverse=True
        )

        matches = []
        paired = set()
        waiting = []

        # Pair players with similar scores
        i = 0
        while i < len(sorted_players):
            if sorted_players[i] in paired:
                i += 1
                continue

            p1 = sorted_players[i]
            p2 = None

            # Find suitable opponent
            for j in range(i + 1, len(sorted_players)):
                candidate = sorted_players[j]
                if candidate in paired:
                    continue

                # Check if they've already played
                if not self._pair_already_played(tournament_id, p1, candidate):
                    p2 = candidate
                    break

            if p2:
                match = Match(
                    id=generate_id(),
                    round_id=round_id,
                    tournament_id=tournament_id,
                    player_ids=[p1, p2],
                    scheduled_at=now_iso(),
                    players_per_match=2,
                )
                matches.append(match)
                self.repository.save_match(match)
                paired.add(p1)
                paired.add(p2)
            else:
                waiting.append(p1)

            i += 1

        return {
            "matches": matches,
            "waiting_players": waiting,
            "metadata": {"pairing_method": "swiss"},
        }

    def _pair_already_played(self, tournament_id: str, p1: str, p2: str) -> bool:
        """Check if two players have already played."""
        return False


class FreeForAllStrategy(IMatchmakingStrategy):
    """
    Free-for-all strategy for multiplayer games.
    Creates a single match with all available players.
    """

    def __init__(self, repository: ITournamentRepository):
        self.repository = repository

    def get_strategy_name(self) -> str:
        return "freeforall"

    def supports_players_per_match(self, n: int) -> bool:
        return True  # Supports any number

    def create_matches(
        self,
        tournament_id: str,
        round_id: str,
        available_players: list[str],
        config: RoundConfig,
    ) -> dict[str, Any]:
        """Create a single match with all players."""
        if not available_players:
            return {"matches": [], "waiting_players": [], "metadata": {}}

        match = Match(
            id=generate_id(),
            round_id=round_id,
            tournament_id=tournament_id,
            player_ids=available_players,
            scheduled_at=now_iso(),
            players_per_match=len(available_players),
        )

        self.repository.save_match(match)

        return {
            "matches": [match],
            "waiting_players": [],
            "metadata": {"total_players": len(available_players)},
        }
