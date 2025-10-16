import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from rich.console import Console

import io
import datetime
import uuid


DB = "tournament.db"


def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def init_db():
    with connect() as db:
        cur = db.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT
        )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS tournaments (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT
        )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS tournament_players (
            tournament_id TEXT NOT NULL,
            player_id TEXT NOT NULL,
            added_at TEXT,
            able_to_play INTEGER DEFAULT 1,
            PRIMARY KEY (tournament_id, player_id)
        )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS rounds (
            id TEXT PRIMARY KEY, tournament_id TEXT, round_type TEXT, ordinal INTEGER, created_at TEXT
        )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS matches (
            id TEXT PRIMARY KEY, round_id TEXT, tournament_id TEXT,
            p1_id TEXT, p2_id TEXT,
            scheduled_at TEXT, result TEXT, winner_id TEXT, auto_bye INTEGER DEFAULT 0
        )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS stats (
            player_id TEXT, tournament_id TEXT,
            wins REAL DEFAULT 0, draws REAL DEFAULT 0, losses REAL DEFAULT 0,
            matches_played INTEGER DEFAULT 0, points REAL DEFAULT 0,
            PRIMARY KEY(player_id,tournament_id)
        )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS waiting_list (
            id TEXT PRIMARY KEY, tournament_id TEXT, player_id TEXT, added_at TEXT
        )"""
        )
        db.commit()


def newid():
    return uuid.uuid4().hex


def previous_round_pending_matches(tournament_id: str) -> bool:
    if not tournament_id:
        return False
    with connect() as db:
        count = db.execute(
            """
            SELECT COUNT(*) FROM matches m
            JOIN rounds r ON m.round_id=r.id
            WHERE r.tournament_id=? AND m.result IS NULL AND m.auto_bye=0
        """,
            (tournament_id,),
        ).fetchone()[0]
    return count > 0


def add_player(name: str) -> str:
    pid = newid()
    created = now_iso()
    with connect() as db:
        db.execute(
            "INSERT INTO players(id,name,created_at) VALUES(?,?,?)",
            (pid, name, created),
        )
        db.commit()
    return pid


def list_players():
    with connect() as db:
        rows = db.execute("SELECT * FROM players ORDER BY name").fetchall()
    return rows


def create_tournament(name: str) -> str:
    tid = newid()
    with connect() as db:
        db.execute(
            "INSERT INTO tournaments(id,name,created_at) VALUES(?,?,?)",
            (tid, name, now_iso()),
        )
        db.commit()
    return tid


def list_tournaments():
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM tournaments ORDER BY created_at DESC"
        ).fetchall()
    return rows


def add_player_to_tournament(tournament_id: str, player_id: str):
    added_at = now_iso()
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO tournament_players(tournament_id,player_id,added_at,able_to_play) VALUES(?,?,?,?)",
            (tournament_id, player_id, added_at, 1),
        )
        db.execute(
            "INSERT OR IGNORE INTO stats(player_id,tournament_id) VALUES(?,?)",
            (player_id, tournament_id),
        )
        db.commit()


def players_in_tournament(tournament_id: str):
    with connect() as db:
        rows = db.execute(
            """SELECT p.id,p.name,tp.able_to_play FROM players p
            JOIN tournament_players tp ON tp.player_id=p.id
            WHERE tp.tournament_id = ?
            ORDER BY p.name""",
            (tournament_id,),
        ).fetchall()
    return rows


def tournament_rounds(tournament_id: str):
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM rounds WHERE tournament_id=? ORDER BY ordinal",
            (tournament_id,),
        ).fetchall()
    return rows


def create_round(tournament_id: str, round_type: str):
    with connect() as db:
        alive = db.execute(
            "SELECT COUNT(*) FROM tournament_players WHERE tournament_id=? AND able_to_play=1",
            (tournament_id,),
        ).fetchone()[0]
        if alive <= 1 and (
            round_type == "knockout" or round_exists_of_type(tournament_id, "knockout")
        ):
            raise RuntimeError(
                "Tournament already decided; cannot create further rounds."
            )
        cur = db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM rounds WHERE tournament_id=?", (tournament_id,)
        )
        ordinal = cur.fetchone()[0] + 1
        rid = newid()
        cur.execute(
            "INSERT INTO rounds(id,tournament_id,round_type,ordinal,created_at) VALUES(?,?,?,?,?)",
            (rid, tournament_id, round_type, ordinal, now_iso()),
        )
        db.commit()
    return rid, ordinal


def round_exists_of_type(tournament_id: str, round_type: str) -> bool:
    with connect() as db:
        r = db.execute(
            "SELECT COUNT(*) FROM rounds WHERE tournament_id=? AND round_type=?",
            (tournament_id, round_type),
        ).fetchone()[0]
    return r > 0


def knockout_exists(tournament_id: str) -> bool:
    return round_exists_of_type(tournament_id, "knockout")


def any_roundrobin_exists(tournament_id: str) -> bool:
    return round_exists_of_type(tournament_id, "roundrobin")


def existing_pair_played(tournament_id: str, p1: str, p2: str) -> bool:
    with connect() as db:
        r = db.execute(
            """
            SELECT COUNT(*) FROM matches 
            WHERE tournament_id=? 
            AND p1_id IS NOT NULL AND p2_id IS NOT NULL
            AND ((p1_id=? AND p2_id=?) OR (p1_id=? AND p2_id=?))
        """,
            (tournament_id, p1, p2, p2, p1),
        ).fetchone()[0]
    return r > 0




def create_roundrobin_matches(tournament_id: str, round_id: str):
    with connect() as db:
        players = db.execute(
            "SELECT player_id FROM tournament_players WHERE tournament_id=?",
            (tournament_id,),
        ).fetchall()
    pids = [r["player_id"] for r in players]

    if not pids:
        return {"pairs": [], "waiting": None}

    # Handle odd players -> add BYE
    bye_added = False
    if len(pids) % 2 == 1:
        pids.append("BYE")
        bye_added = True

    n = len(pids)
    rounds = n - 1
    schedule = []
    rid = 0

    # Circle method, continuous matches
    for r in range(rounds):
        for i in range(n // 2):
            p1 = pids[i]
            p2 = pids[n - 1 - i]
            if p1 != "BYE" and p2 != "BYE":
                schedule.append((rid, p1, p2))
                rid += 1
        pids.insert(1, pids.pop())  # rotate

    scheduled = []
    with connect() as db:
        for rid, a, b in schedule:
            if not existing_pair_played(tournament_id, a, b):
                mid = newid()
                db.execute(
                    "INSERT INTO matches(id,round_id,tournament_id,p1_id,p2_id,scheduled_at) VALUES(?,?,?,?,?,?)",
                    (mid, round_id, tournament_id, a, b, now_iso()),
                )
                scheduled.append((mid, a, b))
        db.commit()

    # Who is waiting (if BYE was added)
    waiting = None
    if bye_added:
        used = set([x for _, a, b in scheduled for x in (a, b)])
        waiting_candidates = [p for p in pids if p not in used and p != "BYE"]
        waiting = waiting_candidates[0] if waiting_candidates else None

    return {"pairs": scheduled, "waiting": waiting}


def get_stats(tournament_id: str):
    with connect() as db:
        rows = db.execute(
            """SELECT s.player_id,p.name,s.wins,s.draws,s.losses,s.matches_played,s.points
                             FROM stats s JOIN players p ON p.id=s.player_id
                             WHERE s.tournament_id=?
                             ORDER BY s.points DESC, s.wins DESC""",
            (tournament_id,),
        ).fetchall()
    return rows


def recalc_stats_for_tournament(tournament_id: str):
    with connect() as db:
        cur = db.cursor()
        cur.execute(
            "SELECT player_id FROM tournament_players WHERE tournament_id=?",
            (tournament_id,),
        )
        pids = [r["player_id"] for r in cur.fetchall()]
        for pid in pids:
            cur.execute(
                "INSERT OR IGNORE INTO stats(player_id,tournament_id) VALUES(?,?)",
                (pid, tournament_id),
            )
        cur.execute(
            "UPDATE stats SET wins=0, draws=0, losses=0, matches_played=0, points=0 WHERE tournament_id=?",
            (tournament_id,),
        )
        matches = db.execute(
            "SELECT * FROM matches WHERE tournament_id=? AND result IS NOT NULL",
            (tournament_id,),
        ).fetchall()
        for m in matches:
            p1 = m["p1_id"]
            p2 = m["p2_id"]
            res = m["result"]
            if m["auto_bye"] == 1:
                winner = m["winner_id"]
                cur.execute(
                    "UPDATE stats SET wins=wins+1, matches_played=matches_played+1, points=points+1 WHERE player_id=? AND tournament_id=?",
                    (winner, tournament_id),
                )
                continue
            if res == "draw":
                cur.execute(
                    "UPDATE stats SET draws=draws+1, matches_played=matches_played+1, points=points+0.5 WHERE player_id=? AND tournament_id=?",
                    (p1, tournament_id),
                )
                cur.execute(
                    "UPDATE stats SET draws=draws+1, matches_played=matches_played+1, points=points+0.5 WHERE player_id=? AND tournament_id=?",
                    (p2, tournament_id),
                )
            else:
                winner = m["winner_id"]
                if winner == p1:
                    loser = p2
                elif winner == p2:
                    loser = p1
                else:
                    loser = None
                cur.execute(
                    "UPDATE stats SET wins=wins+1, matches_played=matches_played+1, points=points+1 WHERE player_id=? AND tournament_id=?",
                    (winner, tournament_id),
                )
                if loser:
                    cur.execute(
                        "UPDATE stats SET losses=losses+1, matches_played=matches_played+1 WHERE player_id=? AND tournament_id=?",
                        (loser, tournament_id),
                    )
        db.commit()


def add_to_waiting_list(tournament_id: str, player_id: str):
    with connect() as db:
        db.execute(
            "INSERT INTO waiting_list(id,tournament_id,player_id,added_at) VALUES(?,?,?,?)",
            (newid(), tournament_id, player_id, now_iso()),
        )
        db.commit()


def get_waiting_list(tournament_id: str) -> list[str]:
    with connect() as db:
        rows = db.execute(
            "SELECT player_id FROM waiting_list WHERE tournament_id=? ORDER BY added_at",
            (tournament_id,),
        ).fetchall()
    return [r["player_id"] for r in rows]


def clear_waiting_list(tournament_id: str, keep_last: list[str] | None = None):
    with connect() as db:
        if keep_last:
            placeholders = ",".join("?" * len(keep_last))
            db.execute(
                f"DELETE FROM waiting_list WHERE tournament_id=? AND player_id NOT IN ({placeholders})",
                [tournament_id] + keep_last,
            )
        else:
            db.execute(
                "DELETE FROM waiting_list WHERE tournament_id=?", (tournament_id,)
            )
        db.commit()


def mark_as_winner(player_id: str, tournament_id: str, round_id: str | None = None):
    mid = newid()
    with connect() as db:
        db.execute(
            "INSERT INTO matches(id,round_id,tournament_id,p1_id,p2_id,scheduled_at,result,winner_id,auto_bye) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                mid,
                round_id,
                tournament_id,
                player_id,
                None,
                now_iso(),
                "auto",
                player_id,
                1,
            ),
        )
        db.commit()
    recalc_stats_for_tournament(tournament_id)


def create_knockout_matches(tournament_id: str, round_id: str):
    recalc_stats_for_tournament(tournament_id)
    with connect() as db:
        rows = db.execute(
            "SELECT player_id FROM tournament_players WHERE tournament_id=? AND able_to_play=1 ORDER BY player_id",
            (tournament_id,),
        ).fetchall()
        pids = [r["player_id"] for r in rows]
        if not pids:
            rows = db.execute(
                "SELECT player_id FROM stats WHERE tournament_id=? ORDER BY points DESC, wins DESC",
                (tournament_id,),
            ).fetchall()
            pids = [r["player_id"] for r in rows]
    pairs = []
    byes = []
    if len(pids) == 0:
        return {"pairs": [], "waiting": None, "byes": []}
    if len(pids) == 1:
        mark_as_winner(pids[0], tournament_id, round_id)
        return {"pairs": [], "waiting": None, "byes": [(None, pids[0])]}
    clear_waiting_list(tournament_id)
    with connect() as db:
        while len(pids) >= 2:
            a = pids.pop(0)
            b = pids.pop(-1)
            mid = newid()
            db.execute(
                "INSERT INTO matches(id,round_id,tournament_id,p1_id,p2_id,scheduled_at) VALUES(?,?,?,?,?,?)",
                (mid, round_id, tournament_id, a, b, now_iso()),
            )
            db.commit()
            pairs.append((mid, a, b))
    waiting = None
    if pids:
        waiting = pids[0]
        add_to_waiting_list(tournament_id, waiting)
    return {"pairs": pairs, "waiting": waiting, "byes": byes}


def schedule_pairs_from_waiting(tournament_id: str, round_id: str):
    waiting_players = get_waiting_list(tournament_id)
    if not waiting_players:
        return {"pairs": [], "remaining": None}
    with connect() as db:
        pending = db.execute(
            "SELECT COUNT(*) FROM matches m JOIN rounds r ON m.round_id=r.id WHERE r.tournament_id=? AND m.result IS NULL AND m.auto_bye=0",
            (tournament_id,),
        ).fetchone()[0]
    if pending == 0 and len(waiting_players) == 1:
        with connect() as db:
            row = db.execute(
                "SELECT id FROM rounds WHERE tournament_id=? AND round_type='knockout' ORDER BY ordinal DESC LIMIT 1",
                (tournament_id,),
            ).fetchone()
        round_id_to_use = row["id"] if row else round_id
        mark_as_winner(waiting_players[0], tournament_id, round_id_to_use)
        clear_waiting_list(tournament_id)
        return {"pairs": [], "remaining": None}
    to_pair = waiting_players[:]
    new_remaining = None
    if len(to_pair) % 2 == 1:
        new_remaining = to_pair.pop(-1)
    pairs = []
    with connect() as db:
        for i in range(0, len(to_pair), 2):
            a = to_pair[i]
            b = to_pair[i + 1]
            mid = newid()
            db.execute(
                "INSERT INTO matches(id,round_id,tournament_id,p1_id,p2_id,scheduled_at) VALUES(?,?,?,?,?,?)",
                (mid, round_id, tournament_id, a, b, now_iso()),
            )
            db.commit()
            pairs.append((mid, a, b))
    clear_waiting_list(tournament_id)
    if new_remaining:
        add_to_waiting_list(tournament_id, new_remaining)
    return {"pairs": pairs, "remaining": new_remaining}


def process_waiting_list(tournament_id: str):
    with connect() as db:
        row = db.execute(
            "SELECT id FROM rounds WHERE tournament_id=? AND round_type='knockout' ORDER BY ordinal DESC LIMIT 1",
            (tournament_id,),
        ).fetchone()
    if not row:
        return
    latest_round_id = row["id"]
    with connect() as db:
        pending = db.execute(
            "SELECT COUNT(*) FROM matches WHERE round_id=? AND result IS NULL AND auto_bye=0",
            (latest_round_id,),
        ).fetchone()[0]
    if pending == 0:
        schedule_pairs_from_waiting(tournament_id, latest_round_id)


def list_matches_for_round(round_id: str):
    with connect() as db:
        rows = db.execute(
            """SELECT m.*, p1.name p1_name, p2.name p2_name FROM matches m
            LEFT JOIN players p1 ON p1.id = m.p1_id
            LEFT JOIN players p2 ON p2.id = m.p2_id
            WHERE m.round_id = ?""",
            (round_id,),
        ).fetchall()
    return rows


def set_match_result(match_id: str, result: str, winner_id: str | None = None):
    with connect() as db:
        if result == "draw":
            db.execute(
                "UPDATE matches SET result=?, winner_id=NULL WHERE id=?",
                (result, match_id),
            )
        else:
            db.execute(
                "UPDATE matches SET result=?, winner_id=? WHERE id=?",
                (result, winner_id, match_id),
            )
        db.commit()
        row = db.execute(
            "SELECT tournament_id, round_id, p1_id, p2_id FROM matches WHERE id=?",
            (match_id,),
        ).fetchone()
        if not row:
            return
        t = row["tournament_id"]
        round_row = db.execute(
            "SELECT round_type FROM rounds WHERE id=?", (row["round_id"],)
        ).fetchone()
        round_type = round_row["round_type"] if round_row else None
        if round_type == "knockout" and result != "draw" and winner_id:
            p1 = row["p1_id"]
            p2 = row["p2_id"]
            loser = p1 if winner_id == p2 else p2 if winner_id == p1 else None
            if loser:
                db.execute(
                    "UPDATE tournament_players SET able_to_play=0 WHERE tournament_id=? AND player_id=?",
                    (t, loser),
                )
                db.execute(
                    "UPDATE tournament_players SET able_to_play=1 WHERE tournament_id=? AND player_id=?",
                    (t, winner_id),
                )
                db.commit()
    recalc_stats_for_tournament(t)
    process_waiting_list(t)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Tournament Matchmaking")
        self.current_tournament: str | None = None
        self.current_round: str | None = None
        self.init_ui()
        init_db()
        self.refresh_players()
        self.refresh_tournaments()
        self.console = Console(file=io.StringIO(), force_terminal=False, width=120)

    def ui_add_selected_players_to_tourney(self):
        if not self.current_tournament:
            messagebox.showerror("Load", "Load a tournament first")
            return
        sel = self.player_list.curselection()
        if not sel:
            messagebox.showerror("Select", "Select at least one player")
            return
        for idx in sel:
            text = self.player_list.get(idx)
            pid = text.split(" - ")[0]
            add_player_to_tournament(self.current_tournament, pid)
        self.refresh_tournament_players()
        messagebox.showinfo("Added", f"{len(sel)} player(s) added to the tournament")

    def init_ui(self):
        frm = ttk.Frame(self.root)
        frm.pack(fill="both", expand=True)
        left = ttk.Frame(frm)
        left.pack(side="left", fill="y", padx=6, pady=6)
        ttk.Label(left, text="Players").pack()
        self.player_list = tk.Listbox(left, width=30, height=20, selectmode=tk.MULTIPLE)
        self.player_list.pack()
        ttk.Button(left, text="Add Player", command=self.ui_add_player).pack(pady=4)
        ttk.Button(left, text="Refresh Players", command=self.refresh_players).pack(
            pady=2
        )
        mid = ttk.Frame(frm)
        mid.pack(side="left", fill="y", padx=6, pady=6)
        ttk.Label(mid, text="Tournaments").pack()
        self.tourney_list = tk.Listbox(mid, width=40, height=10)
        self.tourney_list.pack()
        ttk.Button(mid, text="Create Tournament", command=self.ui_create_tourney).pack(
            pady=4
        )
        ttk.Button(mid, text="Load Tournament", command=self.ui_load_tourney).pack(
            pady=2
        )
        ttk.Label(mid, text="Tournament Players").pack(pady=(10, 0))
        self.t_players = tk.Listbox(mid, width=40, height=8)
        self.t_players.pack()
        ttk.Button(
            mid,
            text="Add Selected Player(s) to Tournament",
            command=self.ui_add_selected_players_to_tourney,
        ).pack(pady=4)
        right = ttk.Frame(frm)
        right.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        topr = ttk.Frame(right)
        topr.pack(fill="x")
        ttk.Label(topr, text="Rounds / Actions").pack(anchor="w")
        rr = ttk.Frame(topr)
        rr.pack(fill="x", pady=4)
        ttk.Button(
            rr,
            text="Create RoundRobin",
            command=lambda: self.ui_create_round("roundrobin"),
        ).pack(side="left")
        ttk.Button(
            rr, text="Create Knockout", command=lambda: self.ui_create_round("knockout")
        ).pack(side="left", padx=6)
        ttk.Button(rr, text="Refresh Rounds", command=self.refresh_rounds).pack(
            side="left", padx=6
        )
        ttk.Label(right, text="Rounds List").pack(anchor="w", pady=(8, 0))
        self.rounds_list = tk.Listbox(right, height=6)
        self.rounds_list.pack(fill="x")
        ttk.Button(right, text="Load Selected Round", command=self.ui_load_round).pack(
            pady=4
        )
        ttk.Label(right, text="Matches / Rankings (Rich table)").pack(
            anchor="w", pady=(8, 0)
        )
        self.console_text = tk.Text(right, height=20, width=100)
        self.console_text.pack(fill="both", expand=True)
        ctrl = ttk.Frame(right)
        ctrl.pack(fill="x", pady=6)
        ttk.Button(ctrl, text="Show Rankings", command=self.ui_show_rankings).pack(
            side="left"
        )
        ttk.Button(
            ctrl, text="Show Matches (round)", command=self.ui_show_matches
        ).pack(side="left", padx=6)
        ttk.Button(
            ctrl, text="Update Match Result", command=self.ui_update_match_result
        ).pack(side="left", padx=6)
        ttk.Button(
            ctrl,
            text="Refresh Tournament Players",
            command=self.refresh_tournament_players,
        ).pack(side="left", padx=6)

    def ui_add_player(self):
        name = simpledialog.askstring(
            "Player name", "Enter player name:", parent=self.root
        )
        if not name:
            return
        add_player(name.strip())
        self.refresh_players()

    def refresh_players(self):
        self.player_list.delete(0, tk.END)
        for r in list_players():
            self.player_list.insert(tk.END, f"{r['id']} - {r['name']}")

    def ui_create_tourney(self):
        name = simpledialog.askstring(
            "Tournament name", "Enter tournament name:", parent=self.root
        )
        if not name:
            return
        tid = create_tournament(name.strip())
        self.refresh_tournaments()
        messagebox.showinfo("Created", f"Tournament created with ID {tid}")

    def refresh_tournaments(self):
        self.tourney_list.delete(0, tk.END)
        for r in list_tournaments():
            self.tourney_list.insert(tk.END, f"{r['id']} - {r['name']}")

    def ui_load_tourney(self):
        sel = self.tourney_list.curselection()
        if not sel:
            messagebox.showerror("Select", "Select a tournament")
            return
        text = self.tourney_list.get(sel[0])
        tid = text.split(" - ")[0]
        self.current_tournament = tid
        self.refresh_tournament_players()
        self.refresh_rounds()
        messagebox.showinfo("Loaded", f"Tournament {tid} loaded")

    def refresh_tournament_players(self):
        self.t_players.delete(0, tk.END)
        if not self.current_tournament:
            return
        for r in players_in_tournament(self.current_tournament):
            status = "active" if r["able_to_play"] == 1 else "eliminated"
            self.t_players.insert(tk.END, f"{r['id']} - {r['name']} [{status}]")

    def ui_add_selected_player_to_tourney(self):
        if not self.current_tournament:
            messagebox.showerror("Load", "Load a tournament first")
            return
        sel = self.player_list.curselection()
        if not sel:
            messagebox.showerror("Select", "Select a player")
            return
        text = self.player_list.get(sel[0])
        pid = text.split(" - ")[0]
        add_player_to_tournament(self.current_tournament, pid)
        self.refresh_tournament_players()

    def ui_create_round(self, rtype: str):
        if not self.current_tournament:
            messagebox.showerror("Load", "Load a tournament first")
            return
        if previous_round_pending_matches(self.current_tournament):
            messagebox.showerror(
                "Pending matches",
                "Finish all matches of the previous round before creating a new round",
            )
            return
        try:
            rid, ordinal = create_round(self.current_tournament, rtype)
        except RuntimeError as e:
            messagebox.showerror("Cannot create round", str(e))
            return
        if rtype == "roundrobin":
            res = create_roundrobin_matches(self.current_tournament, rid)
            txt = f"RoundRobin created (round {ordinal}). {len(res['pairs'])} matches scheduled."
            if res["waiting"]:
                txt += f" Waiting player: {res['waiting']}"
        else:
            res = create_knockout_matches(self.current_tournament, rid)
            txt = f"Knockout created (round {ordinal}). {len(res['pairs'])} matches scheduled."
            if res["waiting"]:
                txt += f" Waiting player buffered: {res['waiting']}"
        self.refresh_rounds()
        messagebox.showinfo("Round created", txt)

    def refresh_rounds(self):
        self.rounds_list.delete(0, tk.END)
        if not self.current_tournament:
            return
        for r in tournament_rounds(self.current_tournament):
            self.rounds_list.insert(
                tk.END, f"{r['id']} - {r['round_type']} - #{r['ordinal']}"
            )

    def ui_load_round(self):
        sel = self.rounds_list.curselection()
        if not sel:
            messagebox.showerror("Select", "Select a round")
            return
        text = self.rounds_list.get(sel[0])
        rid = text.split(" - ")[0]
        self.current_round = rid
        messagebox.showinfo("Round loaded", f"Round {rid} loaded")

    def ui_show_rankings(self):
        if not self.current_tournament:
            messagebox.showerror("Load", "Load a tournament first")
            return
        recalc_stats_for_tournament(self.current_tournament)
        rows = get_stats(self.current_tournament)
        self.console_text.delete("1.0", tk.END)
        if not rows:
            self.console_text.insert(tk.END, "No players in this tournament.\n")
            return
        header = f"{'Rank':<5} {'Player':<20} {'Pts':<5} {'W':<3} {'D':<3} {'L':<3} {'Matches':<7}\n"
        self.console_text.insert(tk.END, header)
        self.console_text.insert(tk.END, "-" * 60 + "\n")
        for i, r in enumerate(rows, start=1):
            line = f"{i:<5} {r['name']:<20} {r['points']:<5} {r['wins']:<3} {r['draws']:<3} {r['losses']:<3} {r['matches_played']:<7}\n"
            self.console_text.insert(tk.END, line)

    def ui_show_matches(self):
        if not self.current_round:
            messagebox.showerror("Load", "Load a round first")
            return

        rows = list_matches_for_round(self.current_round)
        if not rows:
            self.console_text.delete("1.0", tk.END)
            self.console_text.insert(tk.END, "No matches scheduled for this round.\n")
            return

        headers = ["Match ID", "Player 1", "Player 2", "Result", "Winner", "AutoBye"]
        widths = [37, 15, 15, 8, 10, 8]

        def fmt_row(row):
            return "".join(str(val).ljust(w) for val, w in zip(row, widths))

        lines = []
        lines.append(fmt_row(headers))
        lines.append("-" * sum(widths))

        for r in rows:
            p1 = r["p1_name"] or r["p1_id"]
            p2 = r["p2_name"] or ("<BYE>" if r["p2_id"] is None else r["p2_id"])
            result = r["result"] or "-"
            winner = r["winner_id"] or "-"
            autobye = "Yes" if r["auto_bye"] else "No"
            short_id = str(r["id"])  # shorten to 8 chars
            lines.append(fmt_row([short_id, p1, p2, result, winner, autobye]))

        table_output = "\n".join(lines)

        self.console_text.delete("1.0", tk.END)
        self.console_text.insert(tk.END, table_output)

    def ui_update_match_result(self):
        if not self.current_round:
            messagebox.showerror("Load", "Load a round first")
            return
        rows = list_matches_for_round(self.current_round)
        pending = [
            r
            for r in rows
            if r["result"] is None and r["auto_bye"] == 0 and r["p2_id"] is not None
        ]
        if not pending:
            messagebox.showinfo("No matches", "No pending matches available for update")
            return
        sel_win = tk.Toplevel(self.root)
        sel_win.title("Select Match")
        tk.Label(sel_win, text="Select a match to update:").pack(pady=4)
        match_list = tk.Listbox(sel_win, width=80, height=10, selectmode=tk.SINGLE)
        match_list.pack(padx=4, pady=4)
        for r in pending:
            p1 = r["p1_name"] or r["p1_id"]
            p2 = r["p2_name"] or r["p2_id"]
            match_list.insert(tk.END, f"{r['id'][:6]}: {p1} vs {p2}")

        def update_result():
            sel = match_list.curselection()
            if not sel:
                messagebox.showerror("Select", "Select a match")
                return
            idx = sel[0]
            m = pending[idx]
            res_choice = simpledialog.askstring(
                "Result", "Enter result: p1 / p2 / draw", parent=self.root
            )
            if not res_choice:
                return
            res_choice = res_choice.strip().lower()
            if res_choice == "draw":
                set_match_result(m["id"], "draw", None)
                messagebox.showinfo("Updated", "Marked as draw")
            elif res_choice in ("p1", "1"):
                set_match_result(m["id"], "win", m["p1_id"])
                messagebox.showinfo("Updated", "Player 1 marked winner")
            elif res_choice in ("p2", "2"):
                set_match_result(m["id"], "win", m["p2_id"])
                messagebox.showinfo("Updated", "Player 2 marked winner")
            else:
                messagebox.showerror("Bad", "Unknown result")
                return
            sel_win.destroy()
            self.ui_show_matches()
            self.ui_show_rankings()

        tk.Button(sel_win, text="Update Result", command=update_result).pack(pady=4)


if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = App(root)
    root.mainloop()
