"""
Extended Tournament Repository — SOLID Extension Layer
=======================================================
Applies Open/Closed Principle (OCP) + Interface Segregation Principle (ISP)
+ Dependency Inversion Principle (DIP).

This module **extends** the existing repository without modifying it:
- IExtendedTournamentRepository: segregated interface for convenience methods
- ExtendedSQLiteTournamentRepository: adapter that inherits from the concrete
  repository and bridges the convenience API to the underlying save_* methods.

Usage:
    repo = ExtendedSQLiteTournamentRepository()
    repo.create_tournament(tid, "My Tournament")   
    repo.save_tournament(tid, name, created_at)     
"""

from abc import ABC, abstractmethod

from tournament_core import Player, now_iso
from tournament_repository import SQLiteTournamentRepository







class IExtendedTournamentRepository(ABC):
    """
    Extended repository interface with FIDE-friendly convenience methods.

    Segregated from ITournamentRepository so consumers that don't need
    these methods are never forced to depend on them (ISP).
    """

    @abstractmethod
    def create_tournament(self, tournament_id: str, name: str) -> None:
        """Create a tournament with auto-generated timestamp."""
        pass

    @abstractmethod
    def create_player(self, player_id: str, name: str) -> None:
        """Create and persist a player from raw id + name."""
        pass







class ExtendedSQLiteTournamentRepository(
    SQLiteTournamentRepository, IExtendedTournamentRepository
):
    """
    Extends SQLiteTournamentRepository **without modifying** it.

    Adds convenience façade methods that the FIDE routes expect,
    delegating to the inherited save_* methods from the parent class.

    Follows:
      - OCP: existing code is closed for modification, open for extension
      - LSP: can be used anywhere a SQLiteTournamentRepository is expected
      - DIP: FIDE routes depend on the IExtendedTournamentRepository abstraction
    """

    def __init__(self, db_path: str = "tournament.db") -> None:
        super().__init__(db_path)

    

    def create_tournament(self, tournament_id: str, name: str) -> None:
        """Delegate to parent save_tournament with an auto-generated timestamp."""
        self.save_tournament(tournament_id, name, now_iso())

    def create_player(self, player_id: str, name: str) -> None:
        """Construct a Player value-object and delegate to parent save_player."""
        player = Player(
            id=player_id,
            name=name,
            created_at=now_iso(),
            date_of_birth=None,
            category=None,
        )
        self.save_player(player)