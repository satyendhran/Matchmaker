# Tournament Matchmaking System

A feature-rich desktop application for chess-style tournament management with support for Round-Robin and Knockout.

---

## Features

### Tournament Management
- **Multiple Tournament Types:** Round-Robin and Single-Elimination Knockout tournament support
- **Player Database:** Unified player administration across all tournaments
- **Match Scheduling:** Automatic pairing generation depending on tournament type
- **Live Rankings:** Live point calculation and leader board display
- **Match Results:** Record wins, losses, draws with automatic stats update

### Round-Robin Tournaments
- Circle method scheduling for equitable round-robin play
- Automatic handling of BYE for odd numbers of players
- Avoidance of duplicate pairings
- Real-time scheduling for multiple rounds

### Knockout Tournaments
- Generation of single-elimination brackets
- Automatic advancing of winners
- Waiting list management for odd numbers of players
- Auto-advancement of unpaired players once all matches are finished

### User Interface
- **Player Panel:** Add and manage players
- **Tournament Panel:** Create tournaments and assign players
- **Round Management:** Create and navigate between rounds
- **Match Display:** List all matches with results
- **Rankings Table:** List standings with points, wins, draws, losses

---

## Database Schema

The app employs SQLite with the following tables:

- `players`: Information about players
- `tournaments`: Data about tournaments
- `tournament_players`: Player-tournament relationships with elimination status
- `rounds`: Round metadata (type, ordinal)
- `matches`: Match pairings and outcomes
- `stats`: Player stats per tournament
- `waiting_list`: Unpaired player buffer for knockout rounds

---

## Scoring System
- **Win:** 1 point
- **Draw:** 0.5 points per player
- **Loss:** 0 points
- **Auto-BYE:** 1 point (automatic pass)

---

## Advanced Features

### Waiting List (Knockout)
When a knockout round contains an odd number of players, the system:
1. Pairs as many players as possible
2. Placed remaining player(s) in waiting list
3. Automatically pairs waiting players when earlier matches are over
4. Auto-BYES one player if there is only one unpaired player

### Match Validation
- Disallows generating new rounds when matches are in progress
- Disallows repeat pairings in round-robin
- Automatically eliminates knockout round losers
- Disallows knockout creation when just one active player is left

---

## File Structure
- `tournament.py`: Main program file
- `tournament.db`: SQLite database (automatically generated)

---

## Tips
- Finish all matches in a round before generating the next round
- Use Round-Robin for league-style competition where everyone plays everyone
- Use Knockout for tournament brackets and elimination
- Rankings automatically update after every match result
- Player elimination status indicated as `[active]` or `[eliminated]`

---

## Limitations
- Single-elimination knockout only, no double-elimination
- No tiebreaker rules beyond points and wins
- No scheduling/calendar features of matches
- No undo of match results

---

## Troubleshooting
- **Issue:** Cannot create new round
**Solution:** Make sure all previous round matches have results input

- **Issue:** Player showing up twice
  **Solution:** Put each player only once into the database

- **Issue:** Rankings not reflecting
  **Solution:** Press "Show Rankings" to update stats

---

Developed with **Python**, **tkinter**, and **SQLite** for local tournament management.
