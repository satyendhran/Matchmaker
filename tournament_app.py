import tkinter as tk
from tkinter import Toplevel, messagebox, simpledialog, ttk

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


class Style:
    """Apple-inspired color palette and styling constants."""

    # Colors - Apple Design Language
    BG_PRIMARY = "#F5F5F7"  # Light gray background
    BG_SECONDARY = "#FFFFFF"  # White cards
    BG_SIDEBAR = "#FAFAFA"  # Sidebar background

    ACCENT_BLUE = "#007AFF"  # iOS blue
    ACCENT_BLUE_HOVER = "#0051D5"
    ACCENT_GREEN = "#34C759"  # Success green
    ACCENT_RED = "#FF3B30"  # Destructive red
    ACCENT_ORANGE = "#FF9500"  # Warning orange

    TEXT_PRIMARY = "#1D1D1F"  # Almost black
    TEXT_SECONDARY = "#86868B"  # Gray text
    TEXT_TERTIARY = "#B0B0B5"  # Light gray text

    BORDER_COLOR = "#D2D2D7"
    SHADOW_COLOR = "#00000015"

    # Typography - SF Pro inspired
    FONT_LARGE = ("SF Pro Display", 28, "bold")
    FONT_TITLE = ("SF Pro Display", 20, "bold")
    FONT_HEADLINE = ("SF Pro Display", 17, "bold")
    FONT_BODY = ("SF Pro Text", 15)
    FONT_CAPTION = ("SF Pro Text", 13)
    FONT_SMALL = ("SF Pro Text", 11)

    # Spacing
    PADDING_LARGE = 24
    PADDING_MEDIUM = 16
    PADDING_SMALL = 8
    RADIUS = 12


class ModernButton(tk.Canvas):
    """Custom Apple-style button with hover effects."""

    def __init__(
        self,
        parent,
        text,
        command=None,
        style="primary",
        width=120,
        height=36,
        **kwargs,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bg=Style.BG_PRIMARY,
            **kwargs,
        )

        self.command = command
        self.style = style
        self.text = text
        self.width = width
        self.height = height
        self.is_hovered = False

        self._draw_button()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _draw_button(self):
        self.delete("all")

        # Determine colors based on style
        if self.style == "primary":
            bg = Style.ACCENT_BLUE_HOVER if self.is_hovered else Style.ACCENT_BLUE
            fg = "#FFFFFF"
        elif self.style == "secondary":
            bg = "#E5E5EA" if self.is_hovered else "#F2F2F7"
            fg = Style.TEXT_PRIMARY
        elif self.style == "success":
            bg = "#2DA44E" if self.is_hovered else Style.ACCENT_GREEN
            fg = "#FFFFFF"
        else:
            bg = "#E5E5EA" if self.is_hovered else "#F2F2F7"
            fg = Style.TEXT_PRIMARY

        # Draw rounded rectangle
        radius = 8
        self.create_rounded_rect(
            2, 2, self.width - 2, self.height - 2, radius, fill=bg, outline=""
        )

        # Draw text
        self.create_text(
            self.width / 2,
            self.height / 2,
            text=self.text,
            fill=fg,
            font=Style.FONT_BODY,
        )

    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_enter(self, e):
        self.is_hovered = True
        self._draw_button()

    def _on_leave(self, e):
        self.is_hovered = False
        self._draw_button()

    def _on_click(self, e):
        if self.command:
            self.command()


class CardFrame(tk.Frame):
    """Apple-style card with shadow effect."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=Style.BG_SECONDARY, relief=tk.FLAT, **kwargs)
        self.configure(highlightbackground=Style.BORDER_COLOR, highlightthickness=1)


class TournamentApp:
    """Main GUI application with Apple-inspired design."""

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Tournament Manager")
        root.geometry("1400x900")
        root.configure(bg=Style.BG_PRIMARY)

        # Try to use SF Pro font, fallback to system fonts
        self._setup_fonts()

        # Initialize components
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

        # State
        self.current_tournament: str | None = None
        self.current_round: str | None = None

        # Build UI
        self.init_ui()

        # Load initial data
        self.refresh_players()
        self.refresh_tournaments()

        # Load plugins
        self.plugin_loader.discover_and_load_plugins()

    def _setup_fonts(self):
        """Setup fonts with fallbacks."""
        import platform

        system = platform.system()

        if system == "Darwin":  # macOS
            Style.FONT_LARGE = ("SF Pro Display", 28, "bold")
            Style.FONT_TITLE = ("SF Pro Display", 20, "bold")
            Style.FONT_HEADLINE = ("SF Pro Display", 17, "bold")
            Style.FONT_BODY = ("SF Pro Text", 15)
            Style.FONT_CAPTION = ("SF Pro Text", 13)
        else:  # Windows/Linux
            Style.FONT_LARGE = ("Segoe UI", 28, "bold")
            Style.FONT_TITLE = ("Segoe UI", 20, "bold")
            Style.FONT_HEADLINE = ("Segoe UI", 17, "bold")
            Style.FONT_BODY = ("Segoe UI", 13)
            Style.FONT_CAPTION = ("Segoe UI", 11)

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

    def init_ui(self):
        """Initialize the Apple-inspired user interface."""
        # Main container with padding
        main_container = tk.Frame(self.root, bg=Style.BG_PRIMARY)
        main_container.pack(
            fill="both",
            expand=True,
            padx=Style.PADDING_LARGE,
            pady=Style.PADDING_LARGE,
        )

        # Header
        self._create_header(main_container)

        # Content area with three columns
        content_frame = tk.Frame(main_container, bg=Style.BG_PRIMARY)
        content_frame.pack(fill="both", expand=True, pady=(Style.PADDING_MEDIUM, 0))

        self._create_sidebar(content_frame)
        self._create_tournament_section(content_frame)
        self._create_rounds_section(content_frame)

    def _create_header(self, parent):
        """Create the app header."""
        header = tk.Frame(parent, bg=Style.BG_PRIMARY, height=60)
        header.pack(fill="x", pady=(0, Style.PADDING_LARGE))
        header.pack_propagate(False)

        title_label = tk.Label(
            header,
            text="Tournament Manager",
            font=Style.FONT_LARGE,
            bg=Style.BG_PRIMARY,
            fg=Style.TEXT_PRIMARY,
        )
        title_label.pack(side="left", pady=10)

        # Plugin reload button in header
        reload_btn = ModernButton(
            header,
            "↻ Reload Plugins",
            command=self.reload_plugins,
            style="secondary",
            width=140,
            height=36,
        )
        reload_btn.pack(side="right", padx=5, pady=10)

    def _create_sidebar(self, parent):
        """Create the players sidebar."""
        sidebar = CardFrame(parent, width=320)
        sidebar.pack(side="left", fill="y", padx=(0, Style.PADDING_MEDIUM))
        sidebar.pack_propagate(False)

        # Sidebar header
        header = tk.Frame(sidebar, bg=Style.BG_SECONDARY, height=60)
        header.pack(
            fill="x",
            padx=Style.PADDING_MEDIUM,
            pady=(Style.PADDING_MEDIUM, 0),
        )
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Players",
            font=Style.FONT_TITLE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(side="left", pady=10)

        # Add button
        add_frame = tk.Frame(header, bg=Style.BG_SECONDARY)
        add_frame.pack(side="right", pady=10)

        add_btn = ModernButton(
            add_frame,
            "+ Add",
            command=self.add_player,
            style="primary",
            width=80,
            height=32,
        )
        add_btn.pack()

        # Players list with custom styling
        list_container = tk.Frame(sidebar, bg=Style.BG_SECONDARY)
        list_container.pack(
            fill="both",
            expand=True,
            padx=Style.PADDING_MEDIUM,
            pady=Style.PADDING_SMALL,
        )

        scrollbar = tk.Scrollbar(list_container)
        scrollbar.pack(side="right", fill="y")

        self.player_list = tk.Listbox(
            list_container,
            selectmode=tk.MULTIPLE,
            font=Style.FONT_BODY,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
            selectbackground=Style.ACCENT_BLUE,
            selectforeground="#FFFFFF",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        self.player_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.player_list.yview)

        # Refresh button
        refresh_btn = ModernButton(
            sidebar,
            "↻ Refresh",
            command=self.refresh_players,
            style="secondary",
            width=280,
            height=36,
        )
        refresh_btn.pack(pady=Style.PADDING_MEDIUM)

    def _create_tournament_section(self, parent):
        """Create the tournament management section."""
        section = CardFrame(parent, width=420)
        section.pack(
            side="left", fill="both", expand=True, padx=(0, Style.PADDING_MEDIUM)
        )
        section.pack_propagate(False)

        # Header
        header = tk.Frame(section, bg=Style.BG_SECONDARY, height=60)
        header.pack(
            fill="x",
            padx=Style.PADDING_MEDIUM,
            pady=(Style.PADDING_MEDIUM, 0),
        )
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Tournaments",
            font=Style.FONT_TITLE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(side="left", pady=10)

        btn_frame = tk.Frame(header, bg=Style.BG_SECONDARY)
        btn_frame.pack(side="right", pady=10)

        create_btn = ModernButton(
            btn_frame,
            "Create",
            command=self.create_tournament,
            style="primary",
            width=80,
            height=32,
        )
        create_btn.pack(side="left", padx=2)

        load_btn = ModernButton(
            btn_frame,
            "Load",
            command=self.load_tournament,
            style="secondary",
            width=80,
            height=32,
        )
        load_btn.pack(side="left", padx=2)

        # Tournament list
        list_frame = tk.Frame(section, bg=Style.BG_SECONDARY)
        list_frame.pack(fill="x", padx=Style.PADDING_MEDIUM, pady=Style.PADDING_SMALL)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.tournament_list = tk.Listbox(
            list_frame,
            height=6,
            font=Style.FONT_BODY,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
            selectbackground=Style.ACCENT_BLUE,
            selectforeground="#FFFFFF",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        self.tournament_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.tournament_list.yview)

        # Divider
        tk.Frame(section, bg=Style.BORDER_COLOR, height=1).pack(
            fill="x", padx=Style.PADDING_MEDIUM, pady=Style.PADDING_MEDIUM
        )

        # Tournament players section
        tk.Label(
            section,
            text="Tournament Players",
            font=Style.FONT_HEADLINE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(anchor="w", padx=Style.PADDING_MEDIUM, pady=(0, 8))

        players_frame = tk.Frame(section, bg=Style.BG_SECONDARY)
        players_frame.pack(
            fill="both",
            expand=True,
            padx=Style.PADDING_MEDIUM,
            pady=(0, Style.PADDING_SMALL),
        )

        scrollbar2 = tk.Scrollbar(players_frame)
        scrollbar2.pack(side="right", fill="y")

        self.tournament_players = tk.Listbox(
            players_frame,
            font=Style.FONT_CAPTION,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
            selectbackground=Style.ACCENT_BLUE,
            selectforeground="#FFFFFF",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=scrollbar2.set,
        )
        self.tournament_players.pack(side="left", fill="both", expand=True)
        scrollbar2.config(command=self.tournament_players.yview)

        # Add players button
        add_players_btn = ModernButton(
            section,
            "+ Add Selected Players",
            command=self.add_players_to_tournament,
            style="success",
            width=380,
            height=36,
        )
        add_players_btn.pack(pady=(8, Style.PADDING_MEDIUM))

        # Settings section
        tk.Frame(section, bg=Style.BORDER_COLOR, height=1).pack(
            fill="x", padx=Style.PADDING_MEDIUM, pady=Style.PADDING_SMALL
        )

        tk.Label(
            section,
            text="Settings",
            font=Style.FONT_HEADLINE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(anchor="w", padx=Style.PADDING_MEDIUM, pady=(8, 8))

        # Calculator selection
        calc_frame = tk.Frame(section, bg=Style.BG_SECONDARY)
        calc_frame.pack(fill="x", padx=Style.PADDING_MEDIUM, pady=4)

        tk.Label(
            calc_frame,
            text="Points Calculator:",
            font=Style.FONT_CAPTION,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_SECONDARY,
        ).pack(side="left")

        self.calculator_var = tk.StringVar(value="standard")
        self.calculator_combo = ttk.Combobox(
            calc_frame,
            textvariable=self.calculator_var,
            state="readonly",
            width=18,
            font=Style.FONT_CAPTION,
        )
        self.calculator_combo.pack(side="right")
        self.refresh_calculator_list()

        set_calc_btn = ModernButton(
            section,
            "Set Calculator",
            command=self.set_calculator,
            style="secondary",
            width=380,
            height=36,
        )
        set_calc_btn.pack(pady=(8, Style.PADDING_MEDIUM))

    def _create_rounds_section(self, parent):
        section = CardFrame(parent)
        section.pack(side="left", fill="both", expand=True)
        section.grid_columnconfigure(0, weight=1)

        # Configure row weights
        section.grid_rowconfigure(0, weight=0)  # header
        section.grid_rowconfigure(1, weight=0)  # create_frame
        section.grid_rowconfigure(2, weight=0)  # rounds label
        section.grid_rowconfigure(3, weight=1)  # rounds list
        section.grid_rowconfigure(4, weight=0)  # load button
        section.grid_rowconfigure(5, weight=0)  # details label
        section.grid_rowconfigure(6, weight=2)  # matches text
        section.grid_rowconfigure(7, weight=0)  # control buttons

        header = tk.Frame(section, bg=Style.BG_SECONDARY, height=50)
        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=Style.PADDING_MEDIUM,
            pady=(Style.PADDING_MEDIUM, 0),
        )
        header.grid_propagate(False)
        tk.Label(
            header,
            text="Rounds & Matches",
            font=Style.FONT_TITLE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(side="left", pady=10)

        create_frame = tk.LabelFrame(
            section,
            text=" Create Round ",
            font=Style.FONT_HEADLINE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
            relief=tk.FLAT,
            borderwidth=1,
            highlightbackground=Style.BORDER_COLOR,
        )
        create_frame.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=Style.PADDING_MEDIUM,
            pady=Style.PADDING_SMALL,
        )

        strat_frame = tk.Frame(create_frame, bg=Style.BG_SECONDARY)
        strat_frame.pack(fill="x", padx=Style.PADDING_SMALL, pady=Style.PADDING_SMALL)
        tk.Label(
            strat_frame,
            text="Strategy:",
            font=Style.FONT_CAPTION,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))
        self.strategy_var = tk.StringVar(value="roundrobin")
        self.strategy_combo = ttk.Combobox(
            strat_frame,
            textvariable=self.strategy_var,
            state="readonly",
            width=20,
            font=Style.FONT_CAPTION,
        )
        self.strategy_combo.pack(side="left")
        self.refresh_strategy_list()

        players_frame = tk.Frame(create_frame, bg=Style.BG_SECONDARY)
        players_frame.pack(fill="x", padx=Style.PADDING_SMALL, pady=Style.PADDING_SMALL)
        tk.Label(
            players_frame,
            text="Players/Match:",
            font=Style.FONT_CAPTION,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))
        self.players_per_match = tk.IntVar(value=2)
        spinbox = tk.Spinbox(
            players_frame,
            from_=2,
            to=10,
            textvariable=self.players_per_match,
            width=8,
            font=Style.FONT_CAPTION,
            relief=tk.FLAT,
            borderwidth=1,
            highlightbackground=Style.BORDER_COLOR,
        )
        spinbox.pack(side="left")

        create_btn = ModernButton(
            create_frame,
            "Create Round",
            command=self.create_round,
            style="primary",
            width=200,
            height=36,
        )
        create_btn.pack(pady=Style.PADDING_SMALL)

        tk.Label(
            section,
            text="Rounds",
            font=Style.FONT_HEADLINE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=Style.PADDING_MEDIUM,
            pady=(Style.PADDING_MEDIUM, 8),
        )

        rounds_frame = tk.Frame(section, bg=Style.BG_SECONDARY)
        rounds_frame.grid(
            row=3,
            column=0,
            sticky="nsew",
            padx=Style.PADDING_MEDIUM,
            pady=(0, Style.PADDING_SMALL),
        )
        scrollbar = tk.Scrollbar(rounds_frame)
        scrollbar.pack(side="right", fill="y")
        self.rounds_list = tk.Listbox(
            rounds_frame,
            height=4,
            font=Style.FONT_CAPTION,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
            selectbackground=Style.ACCENT_BLUE,
            selectforeground="#FFFFFF",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        self.rounds_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.rounds_list.yview)

        load_round_btn = ModernButton(
            section,
            "Load Selected Round",
            command=self.load_round,
            style="secondary",
            width=200,
            height=32,
        )
        load_round_btn.grid(row=4, column=0, pady=(4, Style.PADDING_SMALL))

        tk.Label(
            section,
            text="Details",
            font=Style.FONT_HEADLINE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).grid(
            row=5,
            column=0,
            sticky="w",
            padx=Style.PADDING_MEDIUM,
            pady=(Style.PADDING_MEDIUM, 8),
        )

        text_frame = tk.Frame(section, bg=Style.BG_SECONDARY)
        text_frame.grid(
            row=6, column=0, sticky="nsew", padx=Style.PADDING_MEDIUM, pady=(0, 0)
        )
        scrollbar2 = tk.Scrollbar(text_frame)
        scrollbar2.pack(side="right", fill="y")
        self.matches_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=Style.FONT_CAPTION,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=scrollbar2.set,
        )
        self.matches_text.pack(side="left", fill="both", expand=True)
        scrollbar2.config(command=self.matches_text.yview)

        ctrl_frame = tk.Frame(section, bg=Style.BG_SECONDARY)
        ctrl_frame.grid(
            row=7,
            column=0,
            sticky="ew",
            padx=Style.PADDING_MEDIUM,
            pady=(Style.PADDING_SMALL, Style.PADDING_MEDIUM),
        )
        standings_btn = ModernButton(
            ctrl_frame,
            "Standings",
            command=self.show_standings,
            style="secondary",
            width=130,
            height=36,
        )
        standings_btn.pack(side="left", padx=2)
        matches_btn = ModernButton(
            ctrl_frame,
            "Matches",
            command=self.show_matches,
            style="secondary",
            width=130,
            height=36,
        )
        matches_btn.pack(side="left", padx=2)
        record_btn = ModernButton(
            ctrl_frame,
            "Record Result",
            command=self.record_match_result,
            style="success",
            width=140,
            height=36,
        )
        record_btn.pack(side="left", padx=2)

    # Player Management

    def add_player(self):
        name = simpledialog.askstring(
            "Add Player", "Enter player name:", parent=self.root
        )
        if name:
            try:
                player_id = self.service.create_player(name.strip())
                self.refresh_players()
                messagebox.showinfo("Success", f"Player '{name}' added successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add player: {e}")

    def refresh_players(self):
        self.player_list.delete(0, tk.END)
        players = self.service.list_players()
        for p in players:
            self.player_list.insert(tk.END, f"  {p.name}")

    # Tournament Management

    def create_tournament(self):
        name = simpledialog.askstring(
            "Create Tournament", "Enter tournament name:", parent=self.root
        )
        if name:
            try:
                tournament_id = self.service.create_tournament(name.strip())
                self.refresh_tournaments()
                messagebox.showinfo(
                    "Success", f"Tournament '{name}' created successfully!"
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create tournament: {e}")

    def refresh_tournaments(self):
        self.tournament_list.delete(0, tk.END)
        with self.repository._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, name FROM tournaments ORDER BY created_at DESC"
            ).fetchall()
            for r in rows:
                self.tournament_list.insert(tk.END, f"  {r['name']}")

    def load_tournament(self):
        sel = self.tournament_list.curselection()
        if not sel:
            messagebox.showerror("Error", "Please select a tournament")
            return

        text = self.tournament_list.get(sel[0]).strip()

        with self.repository._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM tournaments WHERE name = ?", (text,)
            ).fetchone()

            if row:
                self.current_tournament = row["id"]
                self.refresh_tournament_players()
                self.refresh_rounds()
                messagebox.showinfo("Success", "Tournament loaded!")

    def refresh_tournament_players(self):
        self.tournament_players.delete(0, tk.END)
        if not self.current_tournament:
            return

        players = self.repository.get_tournament_players(self.current_tournament)
        for p in players:
            status_symbol = "✓" if p.get("able_to_play", 1) == 1 else "✗"
            self.tournament_players.insert(tk.END, f"  {status_symbol} {p['name']}")

    def add_players_to_tournament(self):
        if not self.current_tournament:
            messagebox.showerror("Error", "Please load a tournament first")
            return

        sel = self.player_list.curselection()
        if not sel:
            messagebox.showerror("Error", "Please select at least one player")
            return

        for idx in sel:
            name = self.player_list.get(idx).strip()
            players = self.service.list_players()
            for p in players:
                if p.name == name:
                    self.service.add_player_to_tournament(self.current_tournament, p.id)
                    break

        self.refresh_tournament_players()
        messagebox.showinfo("Success", f"{len(sel)} player(s) added!")

    # Calculator Management

    def refresh_calculator_list(self):
        calculators = self.service.list_available_calculators()
        self.calculator_combo["values"] = calculators

    def set_calculator(self):
        calc = self.calculator_var.get()
        try:
            self.service.set_default_calculator(calc)
            messagebox.showinfo("Success", f"Calculator set to: {calc}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set calculator: {e}")

    # Round Management

    def refresh_strategy_list(self):
        strategies = self.service.list_available_strategies()
        self.strategy_combo["values"] = strategies

    def create_round(self):
        if not self.current_tournament:
            messagebox.showerror("Error", "Please load a tournament first")
            return

        try:
            # Check if previous rounds are complete
            with self.repository._get_connection() as conn:
                unfinished = conn.execute(
                    """
                    SELECT COUNT(*) AS incomplete_count
                    FROM matches m
                    JOIN rounds r ON m.round_id = r.id
                    WHERE r.tournament_id = ?
                    AND m.result IS NULL
                    """,
                    (self.current_tournament,),
                ).fetchone()

                if unfinished and unfinished["incomplete_count"] > 0:
                    messagebox.showwarning(
                        "Round Not Complete",
                        f"There are still {unfinished['incomplete_count']} unfinished matches.\n\n"
                        "Please record all results before creating a new round.",
                    )
                    return

            strategy = self.strategy_var.get()
            players_per_match = self.players_per_match.get()

            supported = self.strategy_registry.get_strategy(strategy)
            if supported and not supported.supports_players_per_match(
                players_per_match
            ):
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
                f"Round #{result['ordinal']} created successfully!\n\n"
                f"Strategy: {strategy}\n"
                f"Matches: {len(result['matches'])}\n"
                f"Waiting players: {len(result['waiting_players'])}"
            )

            messagebox.showinfo("Success", msg)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create round: {e}")

    def refresh_rounds(self):
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
                    tk.END, f"  #{r['ordinal']} • {r['round_type'].title()}"
                )

    def load_round(self):
        sel = self.rounds_list.curselection()
        if not sel:
            messagebox.showerror("Error", "Please select a round")
            return

        text = self.rounds_list.get(sel[0]).strip()
        ordinal = int(text.split("#")[1].split("•")[0].strip())

        with self.repository._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM rounds WHERE tournament_id = ? AND ordinal = ?",
                (self.current_tournament, ordinal),
            ).fetchone()

            if row:
                self.current_round = row["id"]
                self.show_matches()
                messagebox.showinfo("Success", "Round loaded!")

    # Display Functions

    def show_standings(self):
        if not self.current_tournament:
            messagebox.showerror("Error", "Please load a tournament first")
            return

        stats = self.service.get_standings(self.current_tournament)

        self.matches_text.delete("1.0", tk.END)

        if not stats:
            self.matches_text.insert(tk.END, "No statistics available yet.\n")
            return

        # Header with styling
        self.matches_text.insert(tk.END, "TOURNAMENT STANDINGS\n", "header")
        self.matches_text.insert(tk.END, "=" * 70 + "\n\n", "separator")

        # Table header
        header = f"{'#':<5}{'Player':<30}{'Points':<12}{'W':<6}{'D':<6}{'L':<6}{'Played':<8}\n"
        self.matches_text.insert(tk.END, header, "table_header")
        self.matches_text.insert(tk.END, "-" * 90 + "\n", "separator")

        # Stats rows
        for i, s in enumerate(stats, 1):
            line = (
                f"{i:<5}{s['name']:<30}{s['points']:<12.1f}"
                f"{int(s['wins']):<6}{int(s['draws']):<6}{int(s['losses']):<6}"
                f"{s['matches_played']:<8}\n"
            )
            tag = "top_player" if i <= 3 else "normal"
            self.matches_text.insert(tk.END, line, tag)

        # Configure tags for styling
        self.matches_text.tag_config(
            "header",
            font=Style.FONT_HEADLINE,
            foreground=Style.TEXT_PRIMARY,
        )
        self.matches_text.tag_config(
            "table_header",
            font=Style.FONT_CAPTION,
            foreground=Style.TEXT_SECONDARY,
        )
        self.matches_text.tag_config("separator", foreground=Style.BORDER_COLOR)
        self.matches_text.tag_config("top_player", foreground=Style.ACCENT_BLUE)
        self.matches_text.tag_config("normal", foreground=Style.TEXT_PRIMARY)

    def show_matches(self):
        if not self.current_round:
            messagebox.showerror("Error", "Please load a round first")
            return

        matches = self.repository.list_matches_for_round(self.current_round)

        self.matches_text.delete("1.0", tk.END)

        if not matches:
            self.matches_text.insert(tk.END, "No matches in this round.\n")
            return

        round_type = self.repository.get_round_type(self.current_round)

        # Header
        self.matches_text.insert(tk.END, f"MATCHES • {round_type.upper()}\n", "header")
        self.matches_text.insert(tk.END, "=" * 90 + "\n\n", "separator")

        if round_type == "knockout":
            self.matches_text.insert(
                tk.END,
                "⚠️  WARNING: Losers will be eliminated from this tournament\n\n",
                "warning",
            )

        for i, m in enumerate(matches, 1):
            # Get player names
            player_names = []
            for pid in m.player_ids:
                player = self.repository.get_player(pid)
                player_names.append(player.name if player else pid[:8])

            players_str = " vs ".join(player_names)

            # Match header
            self.matches_text.insert(tk.END, f"Match {i}\n", "match_num")
            self.matches_text.insert(tk.END, f"{players_str}\n", "players")

            # Status
            status = ""
            status_tag = "pending"

            if m.result:
                if m.auto_bye:
                    status = "✓ BYE (Auto-advance)"
                    status_tag = "bye"
                elif m.result == "draw":
                    status = "⚖️  DRAW"
                    status_tag = "draw"
                else:
                    winners = []
                    if m.winner_ids:
                        for wid in m.winner_ids:
                            wp = self.repository.get_player(wid)
                            winners.append(wp.name if wp else wid[:8])
                    status = f"🏆 Winner: {', '.join(winners)}"
                    status_tag = "winner"

                    if round_type == "knockout":
                        losers = [
                            pid for pid in m.player_ids if pid not in m.winner_ids
                        ]
                        if losers:
                            loser_names = []
                            for lid in losers:
                                lp = self.repository.get_player(lid)
                                loser_names.append(lp.name if lp else lid[:8])
                            status += f"\n   ✗ Eliminated: {', '.join(loser_names)}"
            else:
                status = "⏳ Pending"
                status_tag = "pending"

            self.matches_text.insert(tk.END, f"   {status}\n", status_tag)
            self.matches_text.insert(tk.END, "\n")

        # Configure tags
        self.matches_text.tag_config(
            "header",
            font=Style.FONT_HEADLINE,
            foreground=Style.TEXT_PRIMARY,
        )
        self.matches_text.tag_config(
            "match_num",
            font=Style.FONT_BODY,
            foreground=Style.TEXT_SECONDARY,
        )
        self.matches_text.tag_config(
            "players", font=Style.FONT_BODY, foreground=Style.TEXT_PRIMARY
        )
        self.matches_text.tag_config("pending", foreground=Style.ACCENT_ORANGE)
        self.matches_text.tag_config("winner", foreground=Style.ACCENT_GREEN)
        self.matches_text.tag_config("draw", foreground=Style.ACCENT_BLUE)
        self.matches_text.tag_config("bye", foreground=Style.TEXT_SECONDARY)
        self.matches_text.tag_config("warning", foreground=Style.ACCENT_RED)
        self.matches_text.tag_config("separator", foreground=Style.BORDER_COLOR)

    def record_match_result(self):
        if not self.current_round:
            messagebox.showerror("Error", "Please load a round first")
            return

        matches = self.repository.list_matches_for_round(self.current_round)
        pending = [m for m in matches if not m.result and not m.auto_bye]

        if not pending:
            messagebox.showinfo("Info", "No pending matches in this round")
            return

        self._show_match_result_dialog(pending)

    def _show_match_result_dialog(self, matches):
        """Show Apple-styled dialog for recording match results."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Record Match Result")
        dialog.geometry("700x600")
        dialog.configure(bg=Style.BG_PRIMARY)
        dialog.resizable(False, False)

        # Header
        header = tk.Frame(dialog, bg=Style.BG_PRIMARY, height=60)
        header.pack(
            fill="x",
            padx=Style.PADDING_LARGE,
            pady=(Style.PADDING_LARGE, 0),
        )
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Record Match Result",
            font=Style.FONT_TITLE,
            bg=Style.BG_PRIMARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(side="left", pady=10)

        # Card for match selection
        card = CardFrame(dialog)
        card.pack(
            fill="both",
            expand=True,
            padx=Style.PADDING_LARGE,
            pady=Style.PADDING_MEDIUM,
        )

        tk.Label(
            card,
            text="Select a match:",
            font=Style.FONT_HEADLINE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(
            anchor="w",
            padx=Style.PADDING_MEDIUM,
            pady=(Style.PADDING_MEDIUM, 8),
        )

        list_frame = tk.Frame(card, bg=Style.BG_SECONDARY)
        list_frame.pack(
            fill="both",
            expand=True,
            padx=Style.PADDING_MEDIUM,
            pady=(0, Style.PADDING_MEDIUM),
        )

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        match_list = tk.Listbox(
            list_frame,
            font=Style.FONT_BODY,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
            selectbackground=Style.ACCENT_BLUE,
            selectforeground="#FFFFFF",
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        match_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=match_list.yview)

        for m in matches:
            player_names = []
            for pid in m.player_ids:
                player = self.repository.get_player(pid)
                player_names.append(player.name if player else pid[:8])
            match_list.insert(tk.END, f"  {' vs '.join(player_names)}")

        def submit_result():
            sel = match_list.curselection()
            if not sel:
                messagebox.showerror("Error", "Please select a match", parent=dialog)
                return

            match = matches[sel[0]]

            if match.players_per_match == 2:
                self._record_2player_result(match, dialog)
            else:
                self._record_nplayer_result(match, dialog)

        # Buttons
        btn_frame = tk.Frame(dialog, bg=Style.BG_PRIMARY)
        btn_frame.pack(
            fill="x",
            padx=Style.PADDING_LARGE,
            pady=(0, Style.PADDING_LARGE),
        )

        submit_btn = ModernButton(
            btn_frame,
            "Continue →",
            command=submit_result,
            style="primary",
            width=200,
            height=44,
        )
        submit_btn.pack(side="right")

        cancel_btn = ModernButton(
            btn_frame,
            "Cancel",
            command=dialog.destroy,
            style="secondary",
            width=100,
            height=44,
        )
        cancel_btn.pack(side="right", padx=8)

    def _record_2player_result(self, match, parent_dialog):
        """Apple-styled 2-player result dialog."""
        player1 = self.repository.get_player(match.player_ids[0])
        player2 = self.repository.get_player(match.player_ids[1])

        dialog = Toplevel(parent_dialog)
        dialog.title("Match Result")
        dialog.geometry("500x400")
        dialog.configure(bg=Style.BG_PRIMARY)
        dialog.resizable(False, False)
        dialog.grab_set()

        # Header
        header = tk.Frame(dialog, bg=Style.BG_PRIMARY)
        header.pack(
            fill="x",
            padx=Style.PADDING_LARGE,
            pady=(Style.PADDING_LARGE, 0),
        )

        tk.Label(
            header,
            text=f"{player1.name} vs {player2.name}",
            font=Style.FONT_TITLE,
            bg=Style.BG_PRIMARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(pady=10)

        # Card for options
        card = CardFrame(dialog)
        card.pack(
            fill="both",
            expand=True,
            padx=Style.PADDING_LARGE,
            pady=Style.PADDING_MEDIUM,
        )

        tk.Label(
            card,
            text="Who won?",
            font=Style.FONT_HEADLINE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(pady=Style.PADDING_MEDIUM)

        result_var = tk.StringVar(value="")

        # Custom radio button style
        options_frame = tk.Frame(card, bg=Style.BG_SECONDARY)
        options_frame.pack(fill="both", expand=True, padx=Style.PADDING_LARGE)

        for value, text in [("1", player1.name), ("2", player2.name), ("draw", "Draw")]:
            rb = tk.Radiobutton(
                options_frame,
                text=f"  {text}",
                variable=result_var,
                value=value,
                font=Style.FONT_BODY,
                bg=Style.BG_SECONDARY,
                fg=Style.TEXT_PRIMARY,
                selectcolor=Style.ACCENT_BLUE,
                activebackground=Style.BG_SECONDARY,
                activeforeground=Style.TEXT_PRIMARY,
                relief=tk.FLAT,
                borderwidth=0,
                highlightthickness=0,
            )
            rb.pack(anchor="w", pady=8)

        def submit():
            choice = result_var.get().strip().lower()
            if not choice:
                messagebox.showwarning(
                    "Warning", "Please select a result.", parent=dialog
                )
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

                messagebox.showinfo("Success", "Match result recorded successfully!")
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to record result: {e}", parent=dialog
                )

        # Buttons
        btn_frame = tk.Frame(dialog, bg=Style.BG_PRIMARY)
        btn_frame.pack(
            fill="x",
            padx=Style.PADDING_LARGE,
            pady=(0, Style.PADDING_LARGE),
        )

        submit_btn = ModernButton(
            btn_frame, "Submit", command=submit, style="primary", width=150, height=44
        )
        submit_btn.pack(side="right")

        cancel_btn = ModernButton(
            btn_frame,
            "Cancel",
            command=dialog.destroy,
            style="secondary",
            width=100,
            height=44,
        )
        cancel_btn.pack(side="right", padx=8)

    def _record_nplayer_result(self, match, parent_dialog):
        """Apple-styled n-player result dialog."""
        rank_dialog = tk.Toplevel(parent_dialog)
        rank_dialog.title("Enter Rankings")
        rank_dialog.geometry("600x650")
        rank_dialog.configure(bg=Style.BG_PRIMARY)
        rank_dialog.resizable(False, False)
        rank_dialog.grab_set()

        # Header
        header = tk.Frame(rank_dialog, bg=Style.BG_PRIMARY)
        header.pack(
            fill="x",
            padx=Style.PADDING_LARGE,
            pady=(Style.PADDING_LARGE, 0),
        )

        tk.Label(
            header,
            text="Enter Rankings",
            font=Style.FONT_TITLE,
            bg=Style.BG_PRIMARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(pady=10)

        # Card
        card = CardFrame(rank_dialog)
        card.pack(
            fill="both",
            expand=True,
            padx=Style.PADDING_LARGE,
            pady=Style.PADDING_MEDIUM,
        )

        tk.Label(
            card,
            text="Assign finishing position to each player:",
            font=Style.FONT_HEADLINE,
            bg=Style.BG_SECONDARY,
            fg=Style.TEXT_PRIMARY,
        ).pack(pady=Style.PADDING_MEDIUM)

        # Scrollable content
        canvas = tk.Canvas(card, bg=Style.BG_SECONDARY, highlightthickness=0)
        scrollbar = tk.Scrollbar(card, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=Style.BG_SECONDARY)

        scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=Style.PADDING_MEDIUM)
        scrollbar.pack(side="right", fill="y")

        rank_vars = {}
        num_players = len(match.player_ids)

        for i, pid in enumerate(match.player_ids):
            player = self.repository.get_player(pid)

            row_frame = tk.Frame(scroll_frame, bg=Style.BG_SECONDARY)
            row_frame.pack(fill="x", pady=6)

            tk.Label(
                row_frame,
                text=f"{player.name}:",
                font=Style.FONT_BODY,
                bg=Style.BG_SECONDARY,
                fg=Style.TEXT_PRIMARY,
                width=25,
                anchor="w",
            ).pack(side="left", padx=(0, 12))

            var = tk.StringVar(value=str(i + 1))
            combo = ttk.Combobox(
                row_frame,
                textvariable=var,
                values=[str(j) for j in range(1, num_players + 1)],
                state="readonly",
                width=8,
                font=Style.FONT_BODY,
            )
            combo.pack(side="left")
            rank_vars[pid] = var

        def submit_rankings():
            try:
                rankings = {pid: int(var.get()) for pid, var in rank_vars.items()}

                if len(set(rankings.values())) != len(rankings):
                    messagebox.showwarning(
                        "Invalid Rankings",
                        "Each player must have a unique finishing position.",
                        parent=rank_dialog,
                    )
                    return

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

                messagebox.showinfo("Success", "Match result recorded successfully!")

            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to record result: {e}", parent=rank_dialog
                )

        # Buttons
        btn_frame = tk.Frame(rank_dialog, bg=Style.BG_PRIMARY)
        btn_frame.pack(
            fill="x",
            padx=Style.PADDING_LARGE,
            pady=(0, Style.PADDING_LARGE),
        )

        submit_btn = ModernButton(
            btn_frame,
            "Submit Rankings",
            command=submit_rankings,
            style="primary",
            width=180,
            height=44,
        )
        submit_btn.pack(side="right")

        cancel_btn = ModernButton(
            btn_frame,
            "Cancel",
            command=rank_dialog.destroy,
            style="secondary",
            width=100,
            height=44,
        )
        cancel_btn.pack(side="right", padx=8)

    def reload_plugins(self):
        """Reload plugins from plugins directory."""
        try:
            self.plugin_loader.discover_and_load_plugins()
            self.refresh_strategy_list()
            self.refresh_calculator_list()
            messagebox.showinfo("Success", "Plugins reloaded successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reload plugins: {e}")


def main():
    """Main entry point."""
    root = tk.Tk()
    root.geometry("1400x900")
    root.configure(bg=Style.BG_PRIMARY)
    TournamentApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
