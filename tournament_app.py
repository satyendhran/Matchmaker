"""
Refactored GUI application using SOLID principles.
Now supports dynamic plugin loading and n-player games.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, Toplevel, Label, Button, StringVar, Radiobutton,ttk

from tournament_core import (
    MatchmakingStrategyRegistry,
    PointsCalculatorRegistry,
    MatchResult,
    RoundConfig,
)
from tournament_strategies import (
    RoundRobinStrategy,
    SingleEliminationStrategy,
    SwissStrategy,
    FreeForAllStrategy,
)
from tournament_calculators import (
    StandardPointsCalculator,
    ThreePointsCalculator,
    RankingPointsCalculator,
    PercentagePointsCalculator,
)
from tournament_repository import SQLiteTournamentRepository
from tournament_service import TournamentService
from plugin_loader import PluginLoader


class TournamentApp:
    """
    Main GUI application following SOLID principles.
    Uses dependency injection for all services.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Tournament Matchmaking System")

        # Initialize components
        self.repository = SQLiteTournamentRepository()
        self.strategy_registry = MatchmakingStrategyRegistry()
        self.calculator_registry = PointsCalculatorRegistry()

        # Register built-in strategies
        self._register_builtin_strategies()

        # Register built-in calculators
        self._register_builtin_calculators()

        # Initialize plugin loader
        self.plugin_loader = PluginLoader(
            self.strategy_registry, self.calculator_registry, self.repository
        )

        # Initialize service
        self.service = TournamentService(
            self.repository, self.strategy_registry, self.calculator_registry
        )

        # State
        self.current_tournament: str | None = None
        self.current_round: str | None = None

        # Build UI
        self.init_ui()

        # Load initial data
        self.refresh_players()
        self.refresh_tournaments()

        # Try to load plugins
        self.plugin_loader.discover_and_load_plugins()

    def _register_builtin_strategies(self):
        """Register built-in matchmaking strategies."""
        self.strategy_registry.register(RoundRobinStrategy(self.repository))
        self.strategy_registry.register(SingleEliminationStrategy(self.repository))
        self.strategy_registry.register(SwissStrategy(self.repository))
        self.strategy_registry.register(FreeForAllStrategy(self.repository))

    def _register_builtin_calculators(self):
        """Register built-in points calculators."""
        self.calculator_registry.register(StandardPointsCalculator())
        self.calculator_registry.register(ThreePointsCalculator())
        self.calculator_registry.register(RankingPointsCalculator())
        self.calculator_registry.register(PercentagePointsCalculator())

    def init_ui(self):
        """Initialize the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Create three columns
        self._create_players_column(main_frame)
        self._create_tournaments_column(main_frame)
        self._create_rounds_column(main_frame)

    def _create_players_column(self, parent):
        """Create the players management column."""
        frame = ttk.Frame(parent)
        frame.pack(side="left", fill="y", padx=5)

        ttk.Label(frame, text="Players", font=("Arial", 12, "bold")).pack(pady=5)

        self.player_list = tk.Listbox(
            frame, width=30, height=20, selectmode=tk.MULTIPLE
        )
        self.player_list.pack(pady=5)

        ttk.Button(frame, text="Add Player", command=self.add_player).pack(pady=5)
        ttk.Button(frame, text="Refresh", command=self.refresh_players).pack(pady=5)

    def _create_tournaments_column(self, parent):
        """Create the tournaments management column."""
        frame = ttk.Frame(parent)
        frame.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(frame, text="Tournaments", font=("Arial", 12, "bold")).pack(pady=5)

        self.tournament_list = tk.Listbox(frame, width=40, height=10)
        self.tournament_list.pack(pady=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Create", command=self.create_tournament).pack(
            side="left", padx=2
        )
        ttk.Button(btn_frame, text="Load", command=self.load_tournament).pack(
            side="left", padx=2
        )

        ttk.Label(frame, text="Tournament Players", font=("Arial", 10, "bold")).pack(
            pady=(10, 5)
        )

        self.tournament_players = tk.Listbox(frame, width=40, height=8)
        self.tournament_players.pack(pady=5)

        ttk.Button(
            frame, text="Add Selected Players", command=self.add_players_to_tournament
        ).pack(pady=2)

        ttk.Label(frame, text="Settings", font=("Arial", 10, "bold")).pack(pady=(10, 5))

        # Calculator selection
        calc_frame = ttk.Frame(frame)
        calc_frame.pack(fill="x", pady=2)
        ttk.Label(calc_frame, text="Points Calculator:").pack(side="left")
        self.calculator_var = tk.StringVar(value="standard")
        self.calculator_combo = ttk.Combobox(
            calc_frame, textvariable=self.calculator_var, state="readonly", width=15
        )
        self.calculator_combo.pack(side="left", padx=5)
        self.refresh_calculator_list()

        ttk.Button(frame, text="Set Calculator", command=self.set_calculator).pack(
            pady=2
        )

    def _create_rounds_column(self, parent):
        """Create the rounds and matches column."""
        frame = ttk.Frame(parent)
        frame.pack(side="left", fill="both", expand=True, padx=5)

        ttk.Label(frame, text="Rounds & Matches", font=("Arial", 12, "bold")).pack(
            pady=5
        )

        # Round creation controls
        create_frame = ttk.LabelFrame(frame, text="Create Round")
        create_frame.pack(fill="x", pady=5)

        # Strategy selection
        strat_frame = ttk.Frame(create_frame)
        strat_frame.pack(fill="x", pady=2)
        ttk.Label(strat_frame, text="Strategy:").pack(side="left")
        self.strategy_var = tk.StringVar(value="roundrobin")
        self.strategy_combo = ttk.Combobox(
            strat_frame, textvariable=self.strategy_var, state="readonly", width=15
        )
        self.strategy_combo.pack(side="left", padx=5)
        self.refresh_strategy_list()

        # Players per match
        players_frame = ttk.Frame(create_frame)
        players_frame.pack(fill="x", pady=2)
        ttk.Label(players_frame, text="Players/Match:").pack(side="left")
        self.players_per_match = tk.IntVar(value=2)
        ttk.Spinbox(
            players_frame, from_=2, to=10, textvariable=self.players_per_match, width=10
        ).pack(side="left", padx=5)

        ttk.Button(create_frame, text="Create Round", command=self.create_round).pack(
            pady=5
        )
        
        # Rounds list
        ttk.Label(frame, text="Rounds", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        self.rounds_list = tk.Listbox(frame, height=6)
        self.rounds_list.pack(fill="x", pady=5)

        ttk.Button(frame, text="Load Selected Round", command=self.load_round).pack(
            pady=2
        )

        # Matches display
        ttk.Label(frame, text="Matches & Standings", font=("Arial", 10, "bold")).pack(
            pady=(10, 5)
        )

        self.matches_text = tk.Text(frame, height=15, width=80, wrap=tk.NONE)
        scrollbar = ttk.Scrollbar(frame, command=self.matches_text.yview)
        self.matches_text.configure(yscrollcommand=scrollbar.set)
        self.matches_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Control buttons
        ctrl_frame = ttk.Frame(frame)
        ctrl_frame.pack(fill="x", pady=5)

        ttk.Button(ctrl_frame, text="Show Standings", command=self.show_standings).pack(
            side="left", padx=2
        )
        ttk.Button(ctrl_frame, text="Show Matches", command=self.show_matches).pack(
            side="left", padx=2
        )
        ttk.Button(
            ctrl_frame, text="Record Result", command=self.record_match_result
        ).pack(side="left", padx=2)
        ttk.Button(ctrl_frame, text="Load Plugins", command=self.reload_plugins).pack(
            side="left", padx=2
        )

    # Player Management

    def add_player(self):
        """Add a new player."""
        name = simpledialog.askstring(
            "Add Player", "Enter player name:", parent=self.root
        )
        if name:
            try:
                player_id = self.service.create_player(name.strip())
                self.refresh_players()
                messagebox.showinfo(
                    "Success", f"Player '{name}' added (ID: {player_id[:8]})"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add player: {e}")

    def refresh_players(self):
        """Refresh the players list."""
        self.player_list.delete(0, tk.END)
        players = self.service.list_players()
        for p in players:
            self.player_list.insert(tk.END, f"{p.id[:8]}... - {p.name}")

    # Tournament Management

    def create_tournament(self):
        """Create a new tournament."""
        name = simpledialog.askstring(
            "Create Tournament", "Enter tournament name:", parent=self.root
        )
        if name:
            try:
                tournament_id = self.service.create_tournament(name.strip())
                self.refresh_tournaments()
                messagebox.showinfo(
                    "Success", f"Tournament '{name}' created (ID: {tournament_id[:8]})"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create tournament: {e}")

    def refresh_tournaments(self):
        """Refresh the tournaments list."""
        self.tournament_list.delete(0, tk.END)
        with self.repository._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, name FROM tournaments ORDER BY created_at DESC"
            ).fetchall()
            for r in rows:
                self.tournament_list.insert(tk.END, f"{r['id'][:8]}... - {r['name']}")

    def load_tournament(self):
        """Load a selected tournament."""
        sel = self.tournament_list.curselection()
        if not sel:
            messagebox.showerror("Error", "Please select a tournament")
            return

        text = self.tournament_list.get(sel[0])
        # Extract ID (first 8 chars before ...)
        short_id = text.split("...")[0]

        # Find full ID
        with self.repository._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM tournaments WHERE id LIKE ?", (f"{short_id}%",)
            ).fetchone()

            if row:
                self.current_tournament = row["id"]
                self.refresh_tournament_players()
                self.refresh_rounds()
                messagebox.showinfo("Success", "Tournament loaded")

    def refresh_tournament_players(self):
        """Refresh the tournament players list."""
        self.tournament_players.delete(0, tk.END)
        if not self.current_tournament:
            return

        players = self.repository.get_tournament_players(self.current_tournament)
        for p in players:
            status = "ACTIVE" if p.get("able_to_play", 1) == 1 else "ELIMINATED"
            status_symbol = "[✓]" if p.get("able_to_play", 1) == 1 else "[✗]"
            self.tournament_players.insert(
                tk.END,
                f"{status_symbol} {p['player_id'][:8]}... - {p['name']} ({status})",
            )

    def add_players_to_tournament(self):
        """Add selected players to the current tournament."""
        if not self.current_tournament:
            messagebox.showerror("Error", "Please load a tournament first")
            return

        sel = self.player_list.curselection()
        if not sel:
            messagebox.showerror("Error", "Please select at least one player")
            return

        for idx in sel:
            text = self.player_list.get(idx)
            short_id = text.split("...")[0]

            # Find full player ID
            with self.repository._get_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM players WHERE id LIKE ?", (f"{short_id}%",)
                ).fetchone()

                if row:
                    self.service.add_player_to_tournament(
                        self.current_tournament, row["id"]
                    )

        self.refresh_tournament_players()
        messagebox.showinfo("Success", f"{len(sel)} player(s) added to tournament")

    # Calculator Management

    def refresh_calculator_list(self):
        """Refresh available calculators."""
        calculators = self.service.list_available_calculators()
        self.calculator_combo["values"] = calculators

    def set_calculator(self):
        """Set the default calculator for the tournament."""
        calc = self.calculator_var.get()
        try:
            self.service.set_default_calculator(calc)
            messagebox.showinfo("Success", f"Calculator set to: {calc}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set calculator: {e}")

    # Round Management

    def refresh_strategy_list(self):
        """Refresh available strategies."""
        strategies = self.service.list_available_strategies()
        self.strategy_combo["values"] = strategies

    def create_round(self):
        """Create a new round only if all previous rounds are completed."""
        if not self.current_tournament:
            messagebox.showerror("Error", "Please load a tournament first")
            return

        try:
            # --- Check if previous rounds are complete ---
            with self.repository._get_connection() as conn:
                unfinished = conn.execute(
                    """
                    SELECT COUNT(*) AS incomplete_count
                    FROM matches m
                    JOIN rounds r ON m.round_id = r.id
                    WHERE r.tournament_id = ?
                    AND m.result_id IS NULL
                    """,
                    (self.current_tournament,),
                ).fetchone()

                if unfinished and unfinished["incomplete_count"] > 0:
                    messagebox.showwarning(
                        "Round Not Complete",
                        f"There are still {unfinished['incomplete_count']} unfinished matches "
                        "in the current round.\n\nPlease record all results before creating a new round.",
                    )
                    return

            # --- Proceed with round creation if all matches complete ---
            strategy = self.strategy_var.get()
            players_per_match = self.players_per_match.get()

            # Validate player count compatibility
            supported = self.strategy_registry.get_strategy(strategy)
            if supported and not supported.supports_players_per_match(players_per_match):
                messagebox.showerror(
                    "Error",
                    f"Strategy '{strategy}' doesn't support {players_per_match}-player matches",
                )
                return

            config = RoundConfig(
                tournament_id=self.current_tournament,
                round_type=strategy,
                players_per_match=players_per_match,
            )

            result = self.service.create_round(config)
            self.refresh_rounds()

            msg = (
                f" Round #{result['ordinal']} created using '{strategy}' strategy.\n\n"
                f"Matches created: {len(result['matches'])}\n"
                f"Waiting players: {len(result['waiting_players'])}"
            )

            messagebox.showinfo("Success", msg)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create round: {e}")


    def refresh_rounds(self):
        """Refresh the rounds list."""
        self.rounds_list.delete(0, tk.END)
        if not self.current_tournament:
            return

        with self.repository._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, round_type, ordinal FROM rounds WHERE tournament_id = ? ORDER BY ordinal",
                (self.current_tournament,),
            ).fetchall()

            for r in rows:
                self.rounds_list.insert(
                    tk.END, f"#{r['ordinal']} - {r['round_type']} - {r['id'][:8]}..."
                )

    def load_round(self):
        """Load a selected round."""
        sel = self.rounds_list.curselection()
        if not sel:
            messagebox.showerror("Error", "Please select a round")
            return

        text = self.rounds_list.get(sel[0])
        short_id = text.split(" - ")[-1].replace("...", "")

        # Find full round ID
        with self.repository._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM rounds WHERE id LIKE ?", (f"{short_id}%",)
            ).fetchone()

            if row:
                self.current_round = row["id"]
                self.show_matches()
                messagebox.showinfo("Success", "Round loaded")

    # Display Functions

    def show_standings(self):
        """Display tournament standings."""
        if not self.current_tournament:
            messagebox.showerror("Error", "Please load a tournament first")
            return

        stats = self.service.get_standings(self.current_tournament)

        self.matches_text.delete("1.0", tk.END)

        if not stats:
            self.matches_text.insert(tk.END, "No statistics available yet.\n")
            return

        # Header
        header = f"{'Rank':<6}{'Player':<25}{'Points':<8}{'W':<5}{'D':<5}{'L':<5}{'Matches':<8}\n"
        self.matches_text.insert(tk.END, header)
        self.matches_text.insert(tk.END, "=" * 80 + "\n")

        # Stats
        for i, s in enumerate(stats, 1):
            line = (
                f"{i:<6}{s['name']:<25}{s['points']:<8.1f}"
                f"{int(s['wins']):<5}{int(s['draws']):<5}{int(s['losses']):<5}"
                f"{s['matches_played']:<8}\n"
            )
            self.matches_text.insert(tk.END, line)

    def show_matches(self):
        """Display matches for the current round."""
        if not self.current_round:
            messagebox.showerror("Error", "Please load a round first")
            return

        matches = self.repository.list_matches_for_round(self.current_round)

        self.matches_text.delete("1.0", tk.END)

        if not matches:
            self.matches_text.insert(tk.END, "No matches in this round.\n")
            return

        # Get round type
        round_type = self.repository.get_round_type(self.current_round)

        # Header
        self.matches_text.insert(tk.END, f"Matches for Round ({round_type.upper()})\n")
        self.matches_text.insert(tk.END, "=" * 80 + "\n")

        if round_type == "knockout":
            self.matches_text.insert(
                tk.END, "NOTE: Losers will be ELIMINATED from this tournament\n"
            )
            self.matches_text.insert(tk.END, "=" * 80 + "\n")

        self.matches_text.insert(tk.END, "\n")

        for i, m in enumerate(matches, 1):
            # Get player names
            player_names = []
            for pid in m.player_ids:
                player = self.repository.get_player(pid)
                player_names.append(player.name if player else pid[:8])

            players_str = " vs ".join(player_names)

            status = "Pending"
            if m.result:
                if m.auto_bye:
                    status = "BYE (Auto-advance)"
                elif m.result == "draw":
                    status = "DRAW"
                else:
                    winners = []
                    if m.winner_ids:
                        for wid in m.winner_ids:
                            wp = self.repository.get_player(wid)
                            winners.append(wp.name if wp else wid[:8])
                    status = f"Winner: {', '.join(winners)}"

                    if round_type == "knockout":
                        # Show eliminated players
                        losers = [
                            pid for pid in m.player_ids if pid not in m.winner_ids
                        ]
                        if losers:
                            loser_names = []
                            for lid in losers:
                                lp = self.repository.get_player(lid)
                                loser_names.append(lp.name if lp else lid[:8])
                            status += f" | ELIMINATED: {', '.join(loser_names)}"

            self.matches_text.insert(tk.END, f"Match {i}: {players_str}\n")
            self.matches_text.insert(tk.END, f"  Status: {status}\n")
            self.matches_text.insert(tk.END, f"  ID: {m.id[:16]}...\n\n")

    def record_match_result(self):
        """Record the result of a match."""
        if not self.current_round:
            messagebox.showerror("Error", "Please load a round first")
            return

        matches = self.repository.list_matches_for_round(self.current_round)
        pending = [m for m in matches if not m.result and not m.auto_bye]

        if not pending:
            messagebox.showinfo("Info", "No pending matches in this round")
            return

        # Create dialog for match selection
        self._show_match_result_dialog(pending)

    def _show_match_result_dialog(self, matches):
        """Show dialog for recording match results."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Match Result")
        dialog.geometry("600x500")

        ttk.Label(dialog, text="Select a match:", font=("Arial", 10, "bold")).pack(
            pady=10
        )

        match_list = tk.Listbox(dialog, width=70, height=10)
        match_list.pack(pady=5, padx=10)

        for m in matches:
            player_names = []
            for pid in m.player_ids:
                player = self.repository.get_player(pid)
                player_names.append(player.name if player else pid[:8])
            match_list.insert(tk.END, " vs ".join(player_names))

        result_frame = ttk.LabelFrame(dialog, text="Result")
        result_frame.pack(fill="both", expand=True, pady=10, padx=10)

        def submit_result():
            sel = match_list.curselection()
            if not sel:
                messagebox.showerror("Error", "Please select a match")
                return

            match = matches[sel[0]]

            if match.players_per_match == 2:
                self._record_2player_result(match, dialog)
            else:
                self._record_nplayer_result(match, dialog)

        ttk.Button(dialog, text="Record Result", command=submit_result).pack(pady=10)

    def _record_2player_result(self, match, parent_dialog):
        """Record result for 2-player match using a radio button dialog."""
        player1 = self.repository.get_player(match.player_ids[0])
        player2 = self.repository.get_player(match.player_ids[1])

        # Create a new dialog window
        dialog = Toplevel(parent_dialog)
        dialog.title("Match Result")
        dialog.geometry("300x200")
        dialog.resizable(False, False)
        dialog.grab_set()  # Make it modal

        Label(dialog, text=f"{player1.name} vs {player2.name}", font=("Arial", 12, "bold")).pack(pady=10)

        result_var = StringVar(value="")  # Holds the selected option

        # Radio buttons for choices
        Radiobutton(dialog, text=f"{player1.name} wins", variable=result_var, value="1").pack(anchor="w", padx=30)
        Radiobutton(dialog, text=f"{player2.name} wins", variable=result_var, value="2").pack(anchor="w", padx=30)
        Radiobutton(dialog, text="Draw", variable=result_var, value="draw").pack(anchor="w", padx=30)

        def submit():
            choice = result_var.get().strip().lower()
            if not choice:
                messagebox.showwarning("Warning", "Please select a result.", parent=dialog)
                return

            try:
                if choice == "draw":
                    result = MatchResult(
                        match_id=match.id, winner_ids=[], rankings={}, is_draw=True
                    )
                elif choice == "1":
                    result = MatchResult(
                        match_id=match.id,
                        winner_ids=[match.player_ids[0]],
                        rankings={match.player_ids[0]: 1, match.player_ids[1]: 2},
                    )
                elif choice == "2":
                    result = MatchResult(
                        match_id=match.id,
                        winner_ids=[match.player_ids[1]],
                        rankings={match.player_ids[1]: 1, match.player_ids[0]: 2},
                    )

                self.service.record_match_result(match.id, result)
                dialog.destroy()
                parent_dialog.destroy()
                self.show_matches()
                self.show_standings()
                self.refresh_tournament_players()

                messagebox.showinfo(
                    "Success",
                    "Match result recorded. Losers have been eliminated from knockout tournament.",
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to record result: {e}", parent=dialog)

        # Buttons
        Button(dialog, text="Submit", command=submit, width=10).pack(pady=10)
        Button(dialog, text="Cancel", command=dialog.destroy, width=10).pack()

        dialog.wait_window(dialog)

    def _record_nplayer_result(self, match, parent_dialog):
        """Record result for n-player match with improved layout and validation."""
        rank_dialog = tk.Toplevel(parent_dialog)
        rank_dialog.title("Enter Rankings")
        rank_dialog.geometry("400x400")
        rank_dialog.resizable(False, False)
        rank_dialog.grab_set()  # Modal dialog

        ttk.Label(
            rank_dialog,
            text=f"Enter finishing position for each player:",
            font=("Arial", 11, "bold"),
        ).pack(pady=10)

        container = ttk.Frame(rank_dialog)
        container.pack(fill="both", expand=True, padx=15)

        # Scrollable area (in case of many players)
        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        rank_vars = {}
        num_players = len(match.player_ids)

        # Dropdown for ranking positions
        for i, pid in enumerate(match.player_ids):
            player = self.repository.get_player(pid)
            frame = ttk.Frame(scroll_frame)
            frame.pack(fill="x", pady=4)

            ttk.Label(frame, text=f"{player.name}:", width=20, anchor="w").pack(side="left")

            var = tk.StringVar(value=str(i + 1))
            combo = ttk.Combobox(
                frame,
                textvariable=var,
                values=[str(i) for i in range(1, num_players + 1)],
                state="readonly",
                width=5,
            )
            combo.pack(side="left", padx=10)
            rank_vars[pid] = var

        def submit_rankings():
            try:
                # Collect and validate ranks
                rankings = {pid: int(var.get()) for pid, var in rank_vars.items()}

                # Check for duplicate ranks
                if len(set(rankings.values())) != len(rankings):
                    messagebox.showwarning(
                        "Invalid Rankings",
                        "Each player must have a unique finishing position.",
                        parent=rank_dialog,
                    )
                    return

                # Find winners (rank 1)
                winners = [pid for pid, rank in rankings.items() if rank == 1]

                result = MatchResult(
                    match_id=match.id,
                    winner_ids=winners,
                    rankings=rankings,
                    is_draw=len(winners) > 1,
                )

                self.service.record_match_result(match.id, result)

                rank_dialog.destroy()
                parent_dialog.destroy()
                self.show_matches()
                self.show_standings()
                self.refresh_tournament_players()

                messagebox.showinfo(
                    "Success",
                    "Match result recorded. Non-winners have been eliminated from knockout tournament.",
                )

            except Exception as e:
                messagebox.showerror("Error", f"Failed to record result: {e}", parent=rank_dialog)

        ttk.Button(rank_dialog, text="Submit Rankings", command=submit_rankings).pack(pady=15)


    def reload_plugins(self):
            """Reload plugins from plugins directory."""
            try:
                self.plugin_loader.discover_and_load_plugins()
                self.refresh_strategy_list()
                self.refresh_calculator_list()
                messagebox.showinfo("Success", "Plugins reloaded")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reload plugins: {e}")


def main():
    """Main entry point."""
    root = tk.Tk()
    root.geometry("1200x700")
    TournamentApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
