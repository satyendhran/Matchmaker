# Tournament Matchmaking System

A modular tournament management system developed according to SOLID principles, accommodating n-player games, dynamic plugin loading, and various matchmaking strategies.

## Features

- **N-Player Game Support** - Accommodates matches with 2, 3, 4, or more players in parallel
- **Dynamic Plugin System** - Load user-defined matchmaking strategies and scoring calculators at runtime
- **SOLID Architecture** - Clean, readable codebase adhering to industry best practices
- **Multiple Tournament Formats** - Round-robin, single elimination, Swiss system, and free-for-all
- **Flexible Scoring Systems** - Standard, three-point, ranking-based, percentage, and custom calculators
- **Persistent Storage** - SQLite database with clean repository pattern implementation
- **GUI Interface** - Tkinter-based interface for complete tournament management
- **Real-time Statistics** - Comprehensive tracking of wins, losses, draws, points, and rankings

## Prerequisites

- Python 3.8 or later
- Standard library only (no dependencies)

## Installation

```bash
git clone https://github.com/yourusername/tournament-matchmaking-system.git
cd tournament-matchmaking-system
```
python tournament_app.py


## Project Structure

```
tournament-matchmaking-system/
├── tournament_core.py              # Core interfaces and abstract base classes
├── tournament_strategies.py        # Built-in matchmaking strategy implementations
├── tournament_calculators.py       # Built-in points calculator implementations
├── tournament_repository.py        # SQLite repository implementation
├── tournament_service.py           # Business logic service layer
├── plugin_loader.py                # Dynamic plugin loading system
├── tournament_app.py    # GUI application entry point
├── plugins/                        # Custom plugin directory
│   ├── example_strategy.py
│   └── example_calculator.py
├── tournament.db                   # SQLite database (auto-generated)
└── README.md
```

## Quick Start Guide

### Basic Workflow

1. **Player Management** - Add players to the system
2. **Tournament Creation** - Initialize a new tournament
3. **Player Assignment** - Add players to the tournament roster
4. **Round Creation** - Choose matchmaking strategy and set parameters
5. **Result Recording** - Input match results as they finish
6. **Statistics Review** - Review current standings and player statistics

### Command Line Usage

```bash
python tournament_app.py
```

## Matchmaking Strategies

### Round Robin Strategy

Guarantees each player plays against every other player a single time. Appropriate for league tournaments where detailed matchups are necessary.

**Configuration:**
```python
strategy = "roundrobin"
players_per_match = 2  # or n for combinations
```

**Optimal Use Cases:**
- League tournaments
- Fair play mandates
- Small to medium-sized player pools

### Single Elimination Strategy

Classic bracket-style knockout competition. Winners proceed; losers are removed from competition.

**Configuration:**
```python
strategy = "knockout"
players_per_match = 2  # supports n-player eliminations
```

**Optimal Use Cases:**
- Championship brackets
- Time-limited tournaments
- Unambiguous winner determination

### Swiss System Strategy

Matches players with the same performance history who have not faced each other before. Typically applied to chess tournaments.

**Configuration:**
```python
strategy = "swiss"
players_per_match = 2
```

**Optimal Use Cases:**
- Chess competitions
- Competitive esports leagues
- Big player bases

### Free-for-All Strategy

One match involving all participants at once. Applicable to battle royale or multiplayer celebration games.

**Configuration:**
```python
strategy = "freeforall"
players_per_match = all_available_players
```

**Optimal Use Cases:**
- Battle royale games
- Party game events
- Multiplayer board games

## Scoring Systems

| Calculator | Win Points | Draw Points | Loss Points | Primary Application |
|-----------|-----------|-------------|-------------|-------------------|
| Standard | 1.0 | 0.5 | 0.0 | Chess, general competitions |
| Three-Point | 3.0 | 1.0 | 0.0 | Soccer/football leagues |
| Ranking | n-(rank-1) | N/A | N/A | Multi-player positional games |
| Percentage | (defeated/total)×100 | N/A | N/A | Battle royale formats |
| Custom | Configurable | Configurable | Configurable | Specialized requirements |

## Plugin Development

### Defining a Custom Matchmaking Strategy

Define `plugins/custom_strategy.py`:

```python
from tournament_core import IMatchmakingStrategy, Match, RoundConfig
from tournament_core import generate_id, now_iso
from typing import List, Dict, Any

class SkillBasedStrategy(IMatchmakingStrategy):
    """Pairs players by skill ratings."""
    
    def __init__(self, repository):
        self.repository = repository

    def get_strategy_name(self) -> str:
        return "skill_based"

    def supports_players_per_match(self, n: int) -> bool:
        return n == 2

    def create_matches(self,
                      tournament_id: str, 
                      round_id: str,
                      available_players: List[str],
                      config: RoundConfig) -> Dict[str, Any]:
        
        # Get player statistics
        stats = self.repository.get_stats(tournament_id)
        player_scores = {s['player_id']: s['points'] for s in stats}
        
        # Sort by performance
        sorted_players = sorted(
            available_players,
        key=lambda p: player_scores.get(p, 0),
            reverse=True
        )
        
        matches = []
        while len(sorted_players) >= 2:
            p1 = sorted_players.pop(0)
            p2 = sorted_players.pop(0)
            
            match = Match(
                id=generate_id(),
                round_id=round_id,
                tournament_id=tournament_id,
                player_ids=[p1, p2],
                scheduled_at=now_iso(),
                players_per_match=2
            )
            matches.append(match)
            self.repository.save_match(match)
        return {
            "matches": matches,
            "waiting_players": sorted_players,
            "metadata": {"pairing_method": "skill_based"}
        }
```
### Building a Custom Points Calculator

Make `plugins/custom_calculator.py`:

```python
from tournament_core import IPointsCalculator, Match, MatchResult

class WeightedPointsCalculator(IPointsCalculator):
    """Uses weighted scoring according to match complexity."""
    
    def __init__(self, weight_factor: float = 1.5):
        self.weight_factor = weight_factor
    
    def get_calculator_name(self) -> str:
        return "weighted"

    def calculate_points(self, 
                        player_id: str, 
                        match: Match,
                        result: MatchResult) -> float:
        
        base_points = 0.0
        
        if result.is_draw:
            base_points = 0.5
        elif player_id in result.winner_ids:
            base_points = 1.0
        
        # Apply weight based on match complexity
        complexity_factor = len(match.player_ids) / 2.0
        weighted_points = base_points * complexity_factor * self.weight_factor
        
        return weighted_points
```

### Loading Plugins

Plugins are automatically discovered when placed in the `plugins/` directory. Click "Load Plugins" in the GUI or restart the application to activate new plugins.

## Architecture Design

### Implementation of SOLID Principles

#### Single Responsibility Principle
Every component possesses a single, well-defined responsibility:
- `TournamentService`: Orchestration of business logic
- `SQLiteTournamentRepository`: Operations of data persistence
- `RoundRobinStrategy`: Round-robin matchmaking logic implementation
- `StandardPointsCalculator`: Points calculation logic implementation

#### Open/Closed Principle
The system is closed to modification of core behavior but open to extension via plugins.

#### Liskov Substitution Principle
Every strategy implementation is substitutable via the `IMatchmakingStrategy` interface. Every calculator is substitutable via the `IPointsCalculator` interface.

#### Interface Segregation Principle
Interfaces are narrow and single-purpose:
- `IMatchmakingStrategy`: Matchmaking actions only
- `IPointsCalculator`: Points calculation only
- `ITournamentRepository`: Data actions only

#### Dependency Inversion Principle
High-level modules rely on abstractions instead of concrete implementations. Dependencies are injected via constructors.

### Component Architecture

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│       (Tkinter GUI Application)         │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│          Service Layer                  │
│      (TournamentService)                │
│   Business Logic Orchestration          │
└──┬──────────────┬──────────────┬────────┘
   │              │              │
   ▼              ▼              ▼
┌────────┐  ┌──────────┐  ┌────────────┐
│Strategy│  │Calculator│  │ Repository │
│Registry│  │ Registry │  │  (SQLite)  │
└────┬───┘  └─────┬────┘  └──────┬─────┘
     │            │              │
     ▼            ▼              ▼
┌─────────────────────────────────────────┐
│          Plugin System                  │
│      Dynamic Module Loading             │
└─────────────────────────────────────────┘

```

## Database Schema

### Players Table
```sql
CREATE TABLE players (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT
);
```

### Tournaments Table
```sql
CREATE TABLE tournaments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT,
    default_calculator TEXT DEFAULT 'standard'
);
```

### Matches Table (N-Player Support)
```sql
CREATE TABLE matches (
    id TEXT PRIMARY KEY,
    round_id TEXT,
    tournament_id TEXT,
    player_ids TEXT,       
    scheduled_at TEXT,
    result TEXT,
    winner_ids TEXT,       
    rankings TEXT,       
    auto_bye INTEGER DEFAULT 0,
    players_per_match INTEGER DEFAULT 2
);
```

### Statistics Table
```sql
CREATE TABLE stats (
    player_id TEXT,
    tournament_id TEXT,
    wins REAL DEFAULT 0,
    draws REAL DEFAULT 0,
    losses REAL DEFAULT 0,
    matches_played INTEGER DEFAULT 0,
    points REAL DEFAULT 0,
    PRIMARY KEY(player_id, tournament_id)
);
```
## API Reference

### Core Interfaces

#### IMatchmakingStrategy Interface

```python
from abc import ABC, abstractmethod

class IMatchmakingStrategy(ABC):
    @abstractmethod
    def get_strategy_name(self) -> str:
    """"Returns whether this strategy supports n-players per match.""""
        pass

    @abstractmethod
    def supports_players_per_match(self, n: int) -> bool:
        """"Determines if strategy supports n-player matches.""".    
        pass

    @abstractmethod
    def create_matches(self,
                    tournament_id: str,
                    round_id: str,
available_players: List[str],
                      config: RoundConfig) -> Dict[str, Any]:
        """
        Constructs matches for a tournament round.

        Returns:
            Dictionary with:
            - matches: List[Match]
            - waiting_players: List[str]
            - metadata: Dict[str, Any]
        """
    pass
```

#### IPointsCalculator Interface

```python
from abc import ABC, abstractmethod

class IPointsCalculator(ABC):
    """
    Points calculator abstract interface
    """
    @abstractmethod
    def get_calculator_name(self) -> str:

    """Returns unique identifier for this calculator."""
        pass
    
    @abstractmethod
    def calculate_points(self, 
                        player_id: str,
                        match: Match,
                        result: MatchResult) -> float:
        """Calculates points earned by player in given match."""
        pass
```
### Service Layer Methods

#### TournamentService

```python
# Player Operations
def create_player(name: str) -> str
def list_players() -> List[Player]

# Tournament Operations
def create_tournament(name: str) -> str
def add_player_to_tournament(tournament_id: str, player_id: str) -> None
def get_standings(tournament_id: str) -> List[Dict[str, Any]]

# Round Operations
def create_round(config: RoundConfig) -> Dict[str, Any]
def record_match_result(match_id: str, result: MatchResult) -> None

# Plugin Operations
def list_available_strategies() -> List[str]
def list_available_calculators() -> List[str]
def get_strategies_for_player_count(n: int) -> List[str]
def set_default_calculator(calculator_name: str) -> None
```

## Use Case Examples

### Chess Tournament Configuration
```
Strategy: Swiss System
Players per Match: 2
Calculator: Standard (1 point per win, 0.5 per draw)
Number of Rounds: 7-9 rounds
```

### Board Game Tournament (4-player games)
```
Strategy: Round Robin
Players per Match: 4
Calculator: Ranking (1st=4pts, 2nd=3pts, 3rd=2pts, 4th=1pt)
Number of Rounds: All combinations
```

### Esports Single Elimination
```
Strategy: Knockout
Players per Match: 2 (or team size)
Calculator: Three-Point
Number of Rounds: Log2(n) rounds to finals
```

### Battle Royale Tournament
```
Strategy: Free-for-All
Number of Players: Multiple qualification rounds
Players per Match: All participants or large groups
Calculator: Percentage-based placement scoring
```

## Troubleshooting

### Plugin Loading Issues

**Symptom:** Custom plugin does not show up in strategy/calculator dropdown

**Resolution:**
1. Check file is present in `plugins/` directory
2. Check class is subclassing correct interface
3. Check constructor signature is correct
4. Press "Load Plugins" button or restart app
5. Look for error messages in console output

### Match Creation Failures

**Symptom:** Cannot create new tournament round

**Resolution:**
1. Confirm chosen strategy accommodates configured number of players
2. Confirm adequate number of active players
3. Finish all outstanding matches from last rounds
4. Confirm tournament state is valid for new rounds

### Statistics Calculation Mistakes

**Symptom:** Standings show inexact point counts

**Resolution:**
1. Confirm correct calculator used for tournament
2. Confirm all match results contain necessary fields
3. In n-player matches, confirm rankings dictionary contains all players
4. Recalculate statistics manually if needed

## Performance Considerations

- **Player Capacity:** Handles 1000+ players efficiently
- **Database Operations:** Proper indexes optimized
- **Plugin Loading:** Lazy loading with cache
- **Statistics Calculation:** Incremental updates to reduce overhead

## Testing

Run test suite:

```bash
# Unit tests
python -m pytest tests/

# Integration tests
python -m pytest tests/integration/

# Coverage report
python -m pytest --cov=. tests/
```

## Contributing

Pull requests are accepted using these steps:

1. Fork repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Commit with good messages: `git commit -m 'Add new feature'`
4. Push to branch: `git push origin feature/new-feature`
5. Create Pull Request with full description

### Areas to Contribute

- New matchmaking approaches
- New scoring calculator implementations
- Developing web-based user interface
- Creating mobile application wrapper
- Documentation enhancements
- Increasing test coverage
- Performance improvements

## License

This project is under the MIT License.

```
MIT License

Copyright (c) SATYENDHRAN 2024

Permission is absolutely granted, at no charge, to any individual obtaining a copy
of this software and the accompanying documentation files (the "Software") to
deal in the Software without limitation, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to allow persons to whom the Software is
provided to do so, on the condition that:

The following copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
## Contact and Support

- **Issue Tracking:** [GitHub Issues](https://github.com/satyendhran/Matchmaker/issues)
- **Discussion Forum:** [GitHub Discussions](https://github.com/satyendhran/Matchmaker/discussions)
- **Email Contact:** satyendhran74@gmail.com

## Educational Value

This project shows examples of professional software engineering practices:

- **Design Patterns:** Strategy, Factory, Repository, Registry patterns
- **SOLID Principles:** All five principles in everyday use
- **Clean Architecture:** Layered design with proper separation of concerns
- **Dependency Injection:** Constructor-based dependency management
- **Plugin Systems:** Dynamic module registration and loading
- **Database Design:** Normalized schema with JSON flexibility
- **GUI Development:** Event-driven programming using Tkinter

Ideal for academic research, portfolio work, and learning modern software architecture concepts.

## Acknowledgments

This project has been designed as per industry best practices and modern software engineering concepts. It is as much a functional tournament management system as it is an educational guide to clean code architecture.