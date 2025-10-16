# Tournament Matchmaking System

A comprehensive desktop application for managing chess-style tournaments with support for both Round-Robin and Knockout formats.

---

## Features

### Tournament Management
- **Multiple Tournament Types:** Support for Round-Robin and Single-Elimination Knockout tournaments
- **Player Database:** Centralized player management across all tournaments
- **Match Scheduling:** Automatic pairing generation based on tournament format
- **Live Rankings:** Real-time point calculation and leaderboard display
- **Match Results:** Track wins, losses, draws with automatic stat updates

### Round-Robin Tournaments
- Circle method scheduling for fair round-robin play
- Automatic BYE handling for odd player counts
- Prevention of duplicate pairings
- Continuous scheduling across multiple rounds

### Knockout Tournaments
- Single-elimination bracket generation
- Automatic winner progression
- Waiting list management for odd player counts
- Auto-advancement for unpaired players when all matches complete

### User Interface
- **Player Panel:** Add and manage players
- **Tournament Panel:** Create tournaments and assign players
- **Round Management:** Create and navigate between rounds
- **Match Display:** View all matches with results
- **Rankings Table:** See standings with points, wins, draws, losses

---

## Database Schema

The application uses SQLite with the following tables:

- `players`: Player information
- `tournaments`: Tournament details
- `tournament_players`: Player-tournament associations with elimination status
- `rounds`: Round metadata (type, ordinal)
- `matches`: Match pairings and results
- `stats`: Player statistics per tournament
- `waiting_list`: Buffer for unpaired players in knockout rounds

---

## Scoring System
- **Win:** 1 point  
- **Draw:** 0.5 points each player  
- **Loss:** 0 points  
- **Auto-BYE:** 1 point (automatic advancement)

---

## Advanced Features

### Waiting List (Knockout)
When a knockout round has an odd number of players, the system:  
1. Pairs as many players as possible  
2. Places remaining player(s) in waiting list  
3. Automatically pairs waiting players when previous matches complete  
4. Awards auto-BYE if only one player remains unpaired

### Match Validation
- Prevents creating new rounds while matches are pending
- Prevents duplicate pairings in round-robin
- Automatically eliminates losers in knockout rounds
- Stops knockout creation when only one active player remains

---

## File Structure
- `tournament.py`: Main application file  
- `tournament.db`: SQLite database (created automatically)

---

## Tips
- Complete all matches in a round before creating the next round
- Use Round-Robin for league-style play where everyone faces everyone
- Use Knockout for tournament brackets with elimination
- Rankings update automatically after each match result
- Player elimination status shown as `[active]` or `[eliminated]`

---

## Limitations
- Single-elimination knockout only (no double-elimination)
- No tiebreaker rules beyond points and wins
- No match scheduling/calendar features
- No undo functionality for match results

---

## Troubleshooting
- **Issue:** Cannot create new round  
  **Solution:** Ensure all matches from previous round have results entered

- **Issue:** Player appears twice  
  **Solution:** Each player should only be added once to the database

- **Issue:** Rankings not updating  
  **Solution:** Click "Show Rankings" to recalculate stats

---

Built with **Python**, **tkinter**, and **SQLite** for local tournament management.
