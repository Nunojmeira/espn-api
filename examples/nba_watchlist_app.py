"""NBA fantasy watchlist desktop application using espn-api.

This module exposes a Tkinter based GUI that can be executed on Windows
(or any OS with a Python 3 interpreter) to monitor NBA fantasy players.

Example
-------
python examples/nba_watchlist_app.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from functools import partial
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from espn_api.basketball import League
from espn_api.basketball.player import Player
try:
    from espn_api.utils.nba_plus_minus import get_live_plus_minus
except ModuleNotFoundError:  # pragma: no cover - fallback for older installs
    def get_live_plus_minus(*_args: Any, **_kwargs: Any) -> None:
        """Fallback when the optional ``nba_plus_minus`` helper is unavailable."""

        return None


class NBAWatchlistApp:
    """Tkinter application that builds an NBA fantasy watchlist."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ESPN NBA Fantasy Watchlist")
        self.root.geometry("1280x620")

        self._saved_preferences, self._saved_column_widths = self._load_saved_preferences()
        self._saved_column_widths.setdefault("player", {})
        self._saved_column_widths.setdefault("watchlist", {})

        self.league: Optional[League] = None
        self.watchlist_ids: List[int] = []
        self.team_by_label: Dict[str, int] = {}
        self.league_players: Dict[int, Dict[str, Any]] = {}
        self._tree_sort_states: Dict[Any, bool] = {}
        self.player_columns = [
            {"id": "player", "title": "Player", "width": 210, "anchor": tk.W, "visible": True},
            {"id": "nba_team", "title": "NBA Team", "width": 110, "anchor": tk.CENTER, "visible": True},
            {"id": "position", "title": "Position", "width": 100, "anchor": tk.CENTER, "visible": True},
            {"id": "availability", "title": "Availability", "width": 190, "anchor": tk.W, "visible": True},
            {"id": "today_fpts", "title": "FPts", "width": 90, "anchor": tk.CENTER, "visible": True},
            {"id": "fpts_avg", "title": "Season Avg FPts", "width": 130, "anchor": tk.CENTER, "visible": True},
            {"id": "recent", "title": "Last 7 Avg FPts", "width": 130, "anchor": tk.CENTER, "visible": True},
            {"id": "status", "title": "Status", "width": 160, "anchor": tk.W, "visible": True},
        ]
        self.watchlist_columns = [
            {"id": "player", "title": "Player", "width": 190, "anchor": tk.W, "visible": True},
            {"id": "availability", "title": "Availability", "width": 190, "anchor": tk.W, "visible": True},
            {"id": "today_status", "title": "Today's Game", "width": 170, "anchor": tk.W, "visible": True},
            {"id": "today_fpts", "title": "FPts", "width": 90, "anchor": tk.CENTER, "visible": True},
            {"id": "today_minutes", "title": "MIN", "width": 80, "anchor": tk.CENTER, "visible": True},
            {"id": "today_fouls", "title": "PF", "width": 70, "anchor": tk.CENTER, "visible": True},
            {"id": "today_plus_minus", "title": "+/-", "width": 90, "anchor": tk.CENTER, "visible": True},
            {"id": "curr_week", "title": "Current Week", "width": 170, "anchor": tk.W, "visible": True},
            {"id": "next_week", "title": "Next Week", "width": 170, "anchor": tk.W, "visible": True},
            {"id": "last3", "title": "Past 3 Avg", "width": 90, "anchor": tk.CENTER, "visible": True},
            {"id": "last7", "title": "Past 7 Avg", "width": 90, "anchor": tk.CENTER, "visible": True},
        ]
        self.player_column_order = [column["id"] for column in self.player_columns]
        self.watchlist_column_order = [column["id"] for column in self.watchlist_columns]
        self.player_base_columns = list(self.player_column_order)
        self.watchlist_base_columns = list(self.watchlist_column_order)
        self._column_visibility_vars: Dict[str, Dict[str, tk.BooleanVar]] = {"player": {}, "watchlist": {}}
        self._column_option_widgets: Dict[str, Dict[str, Any]] = {}
        self._live_plus_minus_cache: Dict[int, str] = {}

        self._build_widgets()
        self._restore_column_widths()
        self._apply_column_settings("player")
        self._apply_column_settings("watchlist")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        connection = ttk.LabelFrame(self.root, text="League Connection")
        connection.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(connection, text="League ID:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.league_id_var = tk.StringVar(value=self._saved_preferences.get("league_id", ""))
        ttk.Entry(connection, width=12, textvariable=self.league_id_var).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(connection, text="Season Year:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        default_year = self._saved_preferences.get("year") or str(datetime.now().year)
        self.year_var = tk.StringVar(value=default_year)
        ttk.Entry(connection, width=8, textvariable=self.year_var).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(connection, text="espn_s2 (optional):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.espn_s2_var = tk.StringVar(value=self._saved_preferences.get("espn_s2", ""))
        ttk.Entry(connection, width=40, textvariable=self.espn_s2_var).grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky=tk.W)

        ttk.Label(connection, text="SWID (optional):").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.swid_var = tk.StringVar(value=self._saved_preferences.get("swid", ""))
        ttk.Entry(connection, width=40, textvariable=self.swid_var).grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky=tk.W)

        ttk.Button(connection, text="Load League", command=self.load_league).grid(row=0, column=4, rowspan=3, padx=10, pady=5, sticky=tk.N+tk.S)

        connection.columnconfigure(5, weight=1)

        # Team frame ----------------------------------------------------
        team_frame = ttk.LabelFrame(self.root, text="League Teams")
        team_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(team_frame, text="Team:").grid(row=0, column=0, padx=5, pady=5)
        self.team_var = tk.StringVar()
        self.team_combo = ttk.Combobox(team_frame, textvariable=self.team_var, state="readonly", width=45)
        self.team_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(team_frame, text="Add Team Roster", command=self.add_selected_team).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(team_frame, text="Import Team Watchlist", command=self.import_team_watchlist).grid(row=0, column=3, padx=5, pady=5)

        # Watchlist controls -------------------------------------------
        controls = ttk.LabelFrame(self.root, text="Watchlist Controls")
        controls.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(controls, text="Player name or ID:").grid(row=0, column=0, padx=5, pady=5)
        self.player_query_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.player_query_var, width=32).grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(controls, text="Add Player", command=self.add_player).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(controls, text="Remove Selected", command=self.remove_selected).grid(row=0, column=3, padx=5, pady=5)

        ttk.Button(controls, text="Refresh Watchlist", command=self.refresh_watchlist).grid(row=0, column=4, padx=5, pady=5)

        controls.columnconfigure(5, weight=1)

        # Main content -------------------------------------------------
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        dashboard = ttk.Frame(notebook)
        notebook.add(dashboard, text="Watchlist")

        options_tab = ttk.Frame(notebook)
        notebook.add(options_tab, text="Options")

        content = ttk.Frame(dashboard)
        content.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # League player directory -------------------------------------
        player_frame = ttk.LabelFrame(content, text="League Player Pool")
        player_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        filter_row = ttk.Frame(player_frame)
        filter_row.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_row, text="Search:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.player_filter_var = tk.StringVar()
        filter_entry = ttk.Entry(filter_row, textvariable=self.player_filter_var, width=28)
        filter_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        filter_entry.bind("<KeyRelease>", lambda _event: self._populate_player_directory())

        self.free_agent_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filter_row,
            text="Free agents only",
            variable=self.free_agent_only_var,
            command=self._populate_player_directory,
        ).grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)

        ttk.Button(
            filter_row,
            text="Add Selected to Watchlist",
            command=self.add_selected_players_from_directory,
        ).grid(row=0, column=3, padx=5, pady=5)
        filter_row.columnconfigure(4, weight=1)

        self.player_tree = ttk.Treeview(
            player_frame,
            columns=self.player_base_columns,
            show="headings",
            height=16,
            selectmode="extended",
        )
        for config in self.player_columns:
            column_id = config["id"]
            self.player_tree.heading(
                column_id,
                text=config["title"],
                command=partial(self._sort_tree, self.player_tree, column_id),
            )
            self.player_tree.column(
                column_id,
                anchor=config["anchor"],
                width=config["width"],
                stretch=True,
            )

        self.player_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5, pady=(0, 5))

        player_scrollbar_y = ttk.Scrollbar(player_frame, orient=tk.VERTICAL, command=self.player_tree.yview)
        player_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 5))
        player_scrollbar_x = ttk.Scrollbar(player_frame, orient=tk.HORIZONTAL, command=self.player_tree.xview)
        player_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X, padx=5)
        self.player_tree.configure(yscrollcommand=player_scrollbar_y.set, xscrollcommand=player_scrollbar_x.set)

        # Watchlist table ----------------------------------------------
        watchlist = ttk.LabelFrame(content, text="Watchlist")
        watchlist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            watchlist,
            columns=self.watchlist_base_columns,
            show="headings",
            height=16,
            selectmode="extended",
        )
        for config in self.watchlist_columns:
            column_id = config["id"]
            self.tree.heading(
                column_id,
                text=config["title"],
                command=partial(self._sort_tree, self.tree, column_id),
            )
            self.tree.column(
                column_id,
                anchor=config["anchor"],
                width=config["width"],
                stretch=True,
            )

        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.TOP, padx=5, pady=(0, 5))

        watchlist_scroll_y = ttk.Scrollbar(watchlist, orient=tk.VERTICAL, command=self.tree.yview)
        watchlist_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        watchlist_scroll_x = ttk.Scrollbar(watchlist, orient=tk.HORIZONTAL, command=self.tree.xview)
        watchlist_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.configure(yscrollcommand=watchlist_scroll_y.set, xscrollcommand=watchlist_scroll_x.set)

        self._build_options_tab(options_tab)

        # Status bar ----------------------------------------------------
        self.status_var = tk.StringVar(value="Load a league to begin.")
        status_label = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_label.pack(fill=tk.X, padx=10, pady=(0, 5))

    def _build_options_tab(self, container: ttk.Frame) -> None:
        description = ttk.Label(
            container,
            text="Customize which statistics appear in each table and the order in which they are shown.",
            wraplength=520,
            justify=tk.LEFT,
        )
        description.pack(anchor=tk.W, padx=10, pady=(10, 0))

        player_options = ttk.LabelFrame(container, text="Player Pool Columns")
        player_options.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._create_column_options_widgets(player_options, "player")

        watchlist_options = ttk.LabelFrame(container, text="Watchlist Columns")
        watchlist_options.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._create_column_options_widgets(watchlist_options, "watchlist")

    def _restore_column_widths(self) -> None:
        for key, tree in (("player", getattr(self, "player_tree", None)), ("watchlist", getattr(self, "tree", None))):
            if not tree:
                continue
            saved_widths = self._saved_column_widths.get(key, {}) if hasattr(self, "_saved_column_widths") else {}
            for config in self._get_column_configs(key):
                column_id = config["id"]
                width = saved_widths.get(column_id)
                if isinstance(width, int) and width > 0:
                    tree.column(column_id, width=width)

    def _capture_tree_widths(self, tree: ttk.Treeview) -> Dict[str, int]:
        widths: Dict[str, int] = {}
        if not tree:
            return widths
        for column_id in tree["columns"]:
            info = tree.column(column_id)
            width = info.get("width")
            if isinstance(width, int) and width > 0:
                widths[column_id] = width
        return widths

    def _on_close(self) -> None:
        player_widths: Dict[str, int] = {}
        watchlist_widths: Dict[str, int] = {}
        if hasattr(self, "player_tree"):
            player_widths = self._capture_tree_widths(self.player_tree)
        if hasattr(self, "tree"):
            watchlist_widths = self._capture_tree_widths(self.tree)

        self._saved_column_widths["player"] = player_widths
        self._saved_column_widths["watchlist"] = watchlist_widths

        league_id = self.league_id_var.get().strip() if hasattr(self, "league_id_var") else self._saved_preferences.get("league_id", "")
        year = self.year_var.get().strip() if hasattr(self, "year_var") else self._saved_preferences.get("year", "")
        espn_s2 = self.espn_s2_var.get().strip() if hasattr(self, "espn_s2_var") else self._saved_preferences.get("espn_s2", "")
        swid = self.swid_var.get().strip() if hasattr(self, "swid_var") else self._saved_preferences.get("swid", "")

        league_id = league_id or self._saved_preferences.get("league_id", "")
        year = year or self._saved_preferences.get("year", "")
        espn_s2 = espn_s2 or self._saved_preferences.get("espn_s2", "")
        swid = swid or self._saved_preferences.get("swid", "")

        watchlist_key = self._current_watchlist_key()

        self._save_preferences(
            league_id=league_id,
            year=year,
            espn_s2=espn_s2,
            swid=swid,
            watchlist_key=watchlist_key,
            watchlist_ids=self.watchlist_ids,
            column_widths=self._saved_column_widths,
        )

        self.root.destroy()

    def _create_column_options_widgets(self, frame: ttk.Frame, key: str) -> None:
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        listbox = tk.Listbox(frame, height=max(len(self._get_column_order(key)), 4), exportselection=False)
        listbox.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self._column_option_widgets.setdefault(key, {})['listbox'] = listbox
        self._refresh_column_listbox(key)
        if listbox.size():
            listbox.select_set(0)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=0, column=1, sticky=tk.N, padx=5, pady=5)
        ttk.Button(button_frame, text="Move Up", command=lambda: self._move_column(key, -1)).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Move Down", command=lambda: self._move_column(key, 1)).pack(fill=tk.X, pady=2)

        visible_frame = ttk.LabelFrame(frame, text="Visible Columns")
        visible_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=(0, 5))
        visible_frame.columnconfigure(0, weight=1)

        for config in self._get_column_configs(key):
            column_id = config["id"]
            if column_id not in self._column_visibility_vars[key]:
                self._column_visibility_vars[key][column_id] = tk.BooleanVar(value=config.get("visible", True))
            var = self._column_visibility_vars[key][column_id]
            ttk.Checkbutton(
                visible_frame,
                text=config["title"],
                variable=var,
                command=lambda c=column_id, table=key: self._toggle_column_visibility(table, c),
            ).pack(anchor=tk.W, padx=5, pady=2)

    def _get_column_configs(self, key: str) -> List[Dict[str, Any]]:
        return self.player_columns if key == "player" else self.watchlist_columns

    def _get_column_order(self, key: str) -> List[str]:
        return self.player_column_order if key == "player" else self.watchlist_column_order

    def _get_tree(self, key: str) -> Optional[ttk.Treeview]:
        if key == "player":
            return getattr(self, "player_tree", None)
        return getattr(self, "tree", None)

    def _apply_column_settings(self, key: str) -> None:
        tree = self._get_tree(key)
        if not tree:
            return

        order = self._get_column_order(key)
        visible_columns = [column_id for column_id in order if self._column_is_visible(key, column_id)]
        if not visible_columns and order:
            visible_columns = [order[0]]
        tree.configure(displaycolumns=visible_columns)

    def _column_is_visible(self, key: str, column_id: str) -> bool:
        if column_id not in self._column_visibility_vars[key]:
            config = self._find_column_config(key, column_id)
            self._column_visibility_vars[key][column_id] = tk.BooleanVar(value=config.get("visible", True))
        return bool(self._column_visibility_vars[key][column_id].get())

    def _refresh_column_listbox(self, key: str, select: Optional[int] = None) -> None:
        listbox = self._column_option_widgets.get(key, {}).get('listbox')
        if not listbox:
            return

        listbox.delete(0, tk.END)
        for column_id in self._get_column_order(key):
            config = self._find_column_config(key, column_id)
            listbox.insert(tk.END, config["title"])

        if listbox.size():
            index = 0 if select is None else max(0, min(select, listbox.size() - 1))
            listbox.select_clear(0, tk.END)
            listbox.select_set(index)

    def _move_column(self, key: str, direction: int) -> None:
        listbox = self._column_option_widgets.get(key, {}).get('listbox')
        if not listbox:
            return
        selection = listbox.curselection()
        if not selection:
            return
        index = selection[0]
        new_index = index + direction

        order = self._get_column_order(key)
        if new_index < 0 or new_index >= len(order):
            return

        order[index], order[new_index] = order[new_index], order[index]
        self._refresh_column_listbox(key, select=new_index)
        self._apply_column_settings(key)

    def _toggle_column_visibility(self, key: str, column_id: str) -> None:
        var = self._column_visibility_vars[key][column_id]
        if not var.get():
            remaining_visible = [cid for cid in self._get_column_order(key) if cid != column_id and self._column_is_visible(key, cid)]
            if not remaining_visible:
                var.set(True)
                return

        config = self._find_column_config(key, column_id)
        config["visible"] = bool(var.get())
        self._apply_column_settings(key)

    def _find_column_config(self, key: str, column_id: str) -> Dict[str, Any]:
        for config in self._get_column_configs(key):
            if config["id"] == column_id:
                return config
        raise KeyError(column_id)

    # ------------------------------------------------------------------
    # Command callbacks
    # ------------------------------------------------------------------
    def load_league(self) -> None:
        league_id = self.league_id_var.get().strip()
        year = self.year_var.get().strip()

        if not league_id or not year:
            messagebox.showerror("Missing Information", "Please provide both a league ID and season year.")
            return

        try:
            league_kwargs = dict(league_id=int(league_id), year=int(year))
        except ValueError:
            messagebox.showerror("Invalid Input", "League ID and year must be integers.")
            return

        espn_s2 = self.espn_s2_var.get().strip()
        swid = self.swid_var.get().strip()
        if espn_s2 and swid:
            league_kwargs.update(espn_s2=espn_s2, swid=swid)

        self._set_status("Connecting to league...")
        self.root.update_idletasks()
        try:
            league = League(**league_kwargs)
        except Exception as exc:  # pragma: no cover - user feedback path
            messagebox.showerror("League Error", f"Unable to load league: {exc}")
            self._set_status("Unable to load league. Check credentials and try again.")
            return

        self.league = league
        self._live_plus_minus_cache.clear()
        self._populate_teams()

        watchlist_key = self._compose_watchlist_key(league_id, year)
        saved_watchlist = self._load_watchlist_ids(watchlist_key)
        self.watchlist_ids = saved_watchlist

        self.tree.delete(*self.tree.get_children())
        self.player_tree.delete(*self.player_tree.get_children())
        self._collect_league_players()
        self._populate_player_directory()
        self.refresh_watchlist()
        self._set_status("League loaded. Add players or import a roster to begin.")
        self._save_preferences(
            league_id=league_id,
            year=year,
            espn_s2=espn_s2,
            swid=swid,
            watchlist_key=watchlist_key,
            watchlist_ids=self.watchlist_ids,
        )

    def add_selected_team(self) -> None:
        team = self._get_selected_team()
        if not team:
            return

        added = 0
        for player in team.roster:
            if player.playerId not in self.watchlist_ids:
                self.watchlist_ids.append(player.playerId)
                added += 1
        if added:
            self._persist_current_watchlist()
            self._set_status(f"Added {added} players from {team.team_name} to the watchlist.")
            self.refresh_watchlist()
        else:
            self._set_status("All players from the selected roster are already on the watchlist.")

    def import_team_watchlist(self) -> None:
        team = self._get_selected_team()
        if not team:
            return

        try:
            players = self.league.team_watchlist(team.team_id) if self.league else []
        except Exception as exc:  # pragma: no cover - user feedback path
            messagebox.showerror("Watchlist Error", f"Unable to retrieve the ESPN watchlist: {exc}")
            return

        if isinstance(players, Player):
            player_iterable = [players]
        elif isinstance(players, list):
            player_iterable = [player for player in players if isinstance(player, Player)]
        else:
            player_iterable = []

        added = 0
        for player in player_iterable:
            if player.playerId not in self.watchlist_ids:
                self.watchlist_ids.append(player.playerId)
                added += 1

        if added:
            self._persist_current_watchlist()
            self._set_status(f"Added {added} players from {team.team_name}'s watchlist.")
            self.refresh_watchlist()
        else:
            self._set_status("All players from the selected watchlist are already on the watchlist.")

    def _get_selected_team(self) -> Optional[Any]:
        if not self.league:
            messagebox.showinfo("League Required", "Load a league before selecting a team.")
            return None

        team_label = self.team_var.get()
        if team_label not in self.team_by_label:
            messagebox.showinfo("Select Team", "Please choose a team to import.")
            return None

        team_id = self.team_by_label[team_label]
        team = next((t for t in self.league.teams if t.team_id == team_id), None)
        if not team:
            messagebox.showerror("Team Missing", "Unable to locate the selected team.")
            return None
        return team

    def add_selected_players_from_directory(self) -> None:
        if not self.league:
            messagebox.showinfo("League Required", "Load a league before adding players.")
            return

        selections = self.player_tree.selection()
        if not selections:
            self._set_status("Select players in the league pool to add them to the watchlist.")
            return

        added = 0
        for item in selections:
            try:
                player_id = int(item)
            except ValueError:
                continue
            if player_id not in self.watchlist_ids:
                self.watchlist_ids.append(player_id)
                added += 1

        if added:
            self._persist_current_watchlist()
            self._set_status(f"Added {added} players to the watchlist.")
            self.refresh_watchlist()
        else:
            self._set_status("Selected players are already on the watchlist.")

    def add_player(self) -> None:
        if not self.league:
            messagebox.showinfo("League Required", "Load a league before adding players.")
            return

        query = self.player_query_var.get().strip()
        if not query:
            return

        player_id = self._resolve_player_id(query)
        if player_id is None:
            messagebox.showerror("Player Not Found", f"Unable to locate a player for '{query}'.")
            return

        if player_id not in self.watchlist_ids:
            self.watchlist_ids.append(player_id)
            self._persist_current_watchlist()
            self._set_status(f"Added player {self.league.player_map.get(player_id, query)} to watchlist.")
            self.refresh_watchlist()
        else:
            self._set_status("Player already exists on the watchlist.")

    def remove_selected(self) -> None:
        selections = self.tree.selection()
        if not selections:
            return

        removed = False
        for item in selections:
            try:
                player_id = int(item)
            except ValueError:
                continue
            if player_id in self.watchlist_ids:
                self.watchlist_ids.remove(player_id)
                removed = True
        for item in selections:
            self.tree.delete(item)

        if removed:
            self._persist_current_watchlist()
        self._set_status("Removed selected players from the watchlist.")

    def refresh_watchlist(self) -> None:
        if not self.league:
            self._set_status("Load a league to display data.")
            return

        if not self.watchlist_ids:
            self.tree.delete(*self.tree.get_children())
            self._set_status("Watchlist is empty. Add players to begin monitoring.")
            return

        try:
            players = self.league.player_info(playerId=list(self.watchlist_ids))
        except Exception as exc:  # pragma: no cover - user feedback path
            messagebox.showerror("Data Error", f"Unable to refresh player data: {exc}")
            return

        if isinstance(players, Player):
            player_list = [players]
        elif isinstance(players, list):
            player_list = [p for p in players if isinstance(p, Player)]
        else:
            player_list = []

        lookup = {player.playerId: player for player in player_list}
        if not lookup:
            self.tree.delete(*self.tree.get_children())
            self._set_status("Unable to retrieve data for watchlist players.")
            return

        self._collect_league_players()
        self._populate_player_directory()

        current_ids = set(self.watchlist_ids)
        for iid in self.tree.get_children():
            if int(iid) not in current_ids:
                self.tree.delete(iid)

        for player_id in self.watchlist_ids:
            player = lookup.get(player_id)
            if not player:
                continue
            values = self._build_watchlist_row(player)
            iid = str(player_id)
            if self.tree.exists(iid):
                self.tree.item(iid, values=values)
            else:
                self.tree.insert("", tk.END, iid=iid, values=values)

        self._set_status(f"Updated watchlist for {len(lookup)} players.")

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _preferences_path(self) -> Path:
        return Path.home() / ".espn_nba_watchlist.json"

    def _load_saved_preferences(self) -> Tuple[Dict[str, Any], Dict[str, Dict[str, int]]]:
        path = self._preferences_path()
        base_preferences: Dict[str, Any] = {"watchlists": {}}
        base_widths: Dict[str, Dict[str, int]] = {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw_data = json.load(handle)
        except FileNotFoundError:
            return base_preferences, base_widths
        except (OSError, json.JSONDecodeError):
            return base_preferences, base_widths

        if not isinstance(raw_data, dict):
            return base_preferences, base_widths

        data: Dict[str, Any] = {"watchlists": {}}
        for key in ("league_id", "year", "espn_s2", "swid"):
            if key in raw_data:
                value = raw_data.get(key)
                if value is not None:
                    data[key] = str(value)

        watchlists = raw_data.get("watchlists")
        if isinstance(watchlists, dict):
            normalized: Dict[str, List[int]] = {}
            for key, value in watchlists.items():
                if not isinstance(key, str):
                    continue
                if isinstance(value, list):
                    sanitized = self._sanitize_watchlist_ids(value)
                    if sanitized:
                        normalized[key] = sanitized
                    else:
                        normalized[key] = []
            data["watchlists"] = normalized

        column_widths = self._normalize_column_widths(raw_data.get("column_widths"))

        return data, column_widths

    def _save_preferences(
        self,
        *,
        league_id: Optional[str] = None,
        year: Optional[str] = None,
        espn_s2: Optional[str] = None,
        swid: Optional[str] = None,
        watchlist_key: Optional[str] = None,
        watchlist_ids: Optional[Iterable[Any]] = None,
        column_widths: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        data: Dict[str, Any] = dict(self._saved_preferences)
        watchlists: Dict[str, List[int]] = dict(data.get("watchlists", {}))
        saved_widths = self._normalize_column_widths(column_widths or self._saved_column_widths)

        active_key: Optional[str] = None
        if league_id is not None:
            data["league_id"] = str(league_id)
        if year is not None:
            data["year"] = str(year)
        if league_id is not None and year is not None:
            active_key = self._compose_watchlist_key(league_id, year)

        if espn_s2 is not None:
            if espn_s2:
                data["espn_s2"] = str(espn_s2)
            else:
                data.pop("espn_s2", None)
        if swid is not None:
            if swid:
                data["swid"] = str(swid)
            else:
                data.pop("swid", None)

        if watchlist_key is not None:
            sanitized_ids = self._sanitize_watchlist_ids(watchlist_ids)
            if sanitized_ids:
                watchlists[watchlist_key] = sanitized_ids
            else:
                watchlists.pop(watchlist_key, None)

        if active_key is not None:
            watchlists = {key: ids for key, ids in watchlists.items() if key == active_key}

        data["watchlists"] = watchlists
        data["column_widths"] = saved_widths
        self._saved_preferences = data
        self._saved_column_widths = saved_widths

        path = self._preferences_path()
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _normalize_column_widths(
        self, column_widths: Optional[Dict[str, Any]]
    ) -> Dict[str, Dict[str, int]]:
        """Convert stored column widths into a mapping of positive integers."""
        if not isinstance(column_widths, dict):
            return {}
        normalized: Dict[str, Dict[str, int]] = {}
        for table_key, table_widths in column_widths.items():
            if not isinstance(table_key, str) or not isinstance(table_widths, dict):
                continue
            filtered: Dict[str, int] = {}
            for column_id, width in table_widths.items():
                if not isinstance(column_id, str):
                    continue
                try:
                    width_value = int(width)
                except (TypeError, ValueError):
                    continue
                if width_value > 0:
                    filtered[column_id] = width_value
            if filtered:
                normalized[table_key] = filtered
        return normalized

    @staticmethod
    def _compose_watchlist_key(league_id: Any, year: Any) -> Optional[str]:
        league_str = str(league_id).strip() if league_id is not None else ""
        year_str = str(year).strip() if year is not None else ""
        if league_str and year_str:
            return f"{league_str}:{year_str}"
        return None

    def _current_watchlist_key(self) -> Optional[str]:
        if getattr(self, "league", None) is not None:
            league_id = getattr(self.league, "league_id", None)
            year = getattr(self.league, "year", None)
            key = self._compose_watchlist_key(league_id, year)
            if key:
                return key
        league_id = self.league_id_var.get().strip() if hasattr(self, "league_id_var") else ""
        year = self.year_var.get().strip() if hasattr(self, "year_var") else ""
        return self._compose_watchlist_key(league_id, year)

    def _sanitize_watchlist_ids(self, watchlist_ids: Optional[Iterable[Any]]) -> List[int]:
        if not watchlist_ids:
            return []
        sanitized: List[int] = []
        seen: set[int] = set()
        for value in watchlist_ids:
            try:
                player_id = int(value)
            except (TypeError, ValueError):
                continue
            if player_id in seen:
                continue
            sanitized.append(player_id)
            seen.add(player_id)
        return sanitized

    def _load_watchlist_ids(self, watchlist_key: Optional[str]) -> List[int]:
        if not watchlist_key:
            return []
        stored = self._saved_preferences.get("watchlists", {})
        if not isinstance(stored, dict):
            return []
        values = stored.get(watchlist_key)
        if not isinstance(values, list):
            return []
        return self._sanitize_watchlist_ids(values)

    def _persist_current_watchlist(self) -> None:
        watchlist_key = self._current_watchlist_key()
        if not watchlist_key:
            return
        self._save_preferences(watchlist_key=watchlist_key, watchlist_ids=self.watchlist_ids)

    def _collect_league_players(self) -> None:
        if not self.league:
            self.league_players = {}
            return

        players: Dict[int, Dict[str, Any]] = {}
        for team in self.league.teams:
            for player in team.roster:
                avg_points = getattr(player, "avg_points", None)
                recent_points = self._calculate_average(player, games=7)
                today_metrics = self._get_today_metrics(player)
                players[player.playerId] = {
                    "player_id": player.playerId,
                    "name": player.name,
                    "pro_team": player.proTeam,
                    "position": player.position,
                    "fantasy_team": team.team_name,
                    "is_free_agent": False,
                    "avg_points": avg_points,
                    "recent_points": recent_points,
                    "today_fpts": self._format_numeric(today_metrics.get("points")),
                    "status": self._format_player_status(player),
                }

        try:
            free_agents = self.league.free_agents(size=500)
        except Exception:
            free_agents = []

        for player in free_agents:
            today_metrics = self._get_today_metrics(player)
            entry = {
                "player_id": player.playerId,
                "name": player.name,
                "pro_team": player.proTeam,
                "position": player.position,
                "fantasy_team": "Free Agent",
                "is_free_agent": True,
                "avg_points": getattr(player, "avg_points", None),
                "recent_points": self._calculate_average(player, games=7),
                "today_fpts": self._format_numeric(today_metrics.get("points")),
                "status": self._format_player_status(player),
            }
            if player.playerId in players:
                players[player.playerId]["is_free_agent"] = True
                players[player.playerId]["name"] = player.name
                players[player.playerId]["pro_team"] = player.proTeam
                players[player.playerId]["position"] = player.position
                players[player.playerId]["avg_points"] = entry["avg_points"]
                players[player.playerId]["recent_points"] = entry["recent_points"]
                players[player.playerId]["today_fpts"] = entry["today_fpts"]
                players[player.playerId]["status"] = entry["status"]
            else:
                players[player.playerId] = entry

        self.league_players = players

    def _populate_player_directory(self) -> None:
        if not hasattr(self, "player_tree"):
            return

        self.player_tree.delete(*self.player_tree.get_children())
        if not self.league_players:
            return

        filter_text = self.player_filter_var.get().strip().lower() if hasattr(self, "player_filter_var") else ""
        free_only = self.free_agent_only_var.get() if hasattr(self, "free_agent_only_var") else False

        entries = sorted(self.league_players.values(), key=lambda info: info["name"].lower())
        for info in entries:
            if filter_text and filter_text not in info["name"].lower():
                continue
            if free_only and not info.get("is_free_agent"):
                continue

            availability = info.get("fantasy_team") if not info.get("is_free_agent") else "Free Agent"
            row = {
                "player": info["name"],
                "nba_team": info["pro_team"],
                "position": info["position"],
                "availability": availability,
                "today_fpts": info.get("today_fpts", "-"),
                "fpts_avg": self._format_numeric(info.get("avg_points")),
                "recent": self._format_numeric(info.get("recent_points")),
                "status": info.get("status", "Active"),
            }
            values = tuple(row.get(column_id, "-") for column_id in self.player_base_columns)
            self.player_tree.insert("", tk.END, iid=str(info["player_id"]), values=values)

    def _populate_teams(self) -> None:
        if not self.league:
            return

        self.team_by_label.clear()
        labels: List[str] = []
        for team in sorted(self.league.teams, key=lambda t: t.team_name.lower()):
            label = f"{team.team_name} (ID: {team.team_id})"
            labels.append(label)
            self.team_by_label[label] = team.team_id

        self.team_combo["values"] = labels
        if labels:
            self.team_combo.current(0)

    def _resolve_player_id(self, query: str) -> Optional[int]:
        if query.isdigit():
            return int(query)

        if not self.league:
            return None

        query_lower = query.lower()
        exact_matches = [
            info["player_id"]
            for info in self.league_players.values()
            if info["name"].lower() == query_lower
        ]
        if exact_matches:
            return exact_matches[0]

        last_name_matches = [
            info["player_id"]
            for info in self.league_players.values()
            if info["name"].split()[-1].lower() == query_lower
        ]
        if len(last_name_matches) == 1:
            return last_name_matches[0]

        substring_matches = [
            info["player_id"]
            for info in self.league_players.values()
            if query_lower in info["name"].lower()
        ]
        if len(substring_matches) == 1:
            return substring_matches[0]
        if len(substring_matches) > 1:
            suggestions = sorted(
                self.league_players[player_id]["name"] for player_id in substring_matches
            )[:5]
            messagebox.showinfo(
                "Multiple Matches",
                "Multiple players match '{query}'. Refine your search (e.g. {examples}).".format(
                    query=query,
                    examples=", ".join(suggestions),
                ),
            )
            return None

        player_id = self.league.player_map.get(query)
        if isinstance(player_id, int):
            return player_id

        for key, value in self.league.player_map.items():
            if isinstance(key, str) and key.lower() == query_lower and isinstance(value, int):
                return value
        return None

    def _build_watchlist_row(self, player: Player) -> Sequence[str]:
        info = self.league_players.get(player.playerId, {
            "fantasy_team": "Free Agent",
            "is_free_agent": True,
        })
        fantasy_team = info.get("fantasy_team", "Free Agent")
        availability = fantasy_team if fantasy_team != "Free Agent" else "Free Agent"

        today_metrics = self._get_today_metrics(player)
        current_week = self._format_schedule(
            player,
            self._get_scoring_periods(self.league.currentMatchupPeriod),
            fallback="No games remaining this week.",
        )
        next_week = self._format_schedule(
            player,
            self._get_next_week_periods(player),
            fallback="Next week's schedule unavailable.",
        )
        last3 = self._calculate_average(player, games=3)
        last7 = self._calculate_average(player, games=7)

        row = {
            "player": player.name,
            "availability": availability,
            "today_status": today_metrics["status"],
            "today_fpts": self._format_numeric(today_metrics["points"]),
            "today_minutes": today_metrics["minutes"],
            "today_fouls": today_metrics["fouls"],
            "today_plus_minus": today_metrics["plus_minus"],
            "curr_week": current_week,
            "next_week": next_week,
            "last3": self._format_numeric(last3),
            "last7": self._format_numeric(last7),
        }

        return tuple(row.get(column_id, "-") for column_id in self.watchlist_base_columns)

    def _get_scoring_periods(self, matchup_period: int) -> Sequence[int]:
        if not self.league:
            return []
        periods = self.league.matchup_ids.get(matchup_period, [])
        return [int(p) for p in periods]

    def _get_next_week_periods(self, player: Player) -> Sequence[int]:
        upcoming = self._get_upcoming_periods(player, days=7)
        if upcoming:
            return upcoming
        return self._get_scoring_periods(self.league.currentMatchupPeriod + 1)

    def _get_upcoming_periods(self, player: Player, days: int) -> Sequence[int]:
        if not self.league:
            return []

        now = datetime.now()
        limit = now + timedelta(days=days)
        upcoming: List[int] = []
        sorted_periods = sorted(
            (int(key) for key in player.schedule.keys() if str(key).isdigit())
        )

        for period in sorted_periods:
            entry = player.schedule.get(str(period), {})
            date = entry.get("date") if isinstance(entry, dict) else None

            if isinstance(date, datetime):
                if now <= date <= limit:
                    upcoming.append(period)
                elif date > limit and upcoming:
                    break
            elif period > self.league.scoringPeriodId:
                upcoming.append(period)

            if len(upcoming) >= 5:
                break

        return upcoming

    def _get_today_metrics(self, player: Player) -> Dict[str, Any]:
        if not self.league:
            return {"status": "", "points": None, "minutes": "-", "fouls": "-", "plus_minus": "-"}

        scoring_period = str(self.league.scoringPeriodId)
        stat_entry = player.stats.get(scoring_period)
        schedule_entry = player.schedule.get(scoring_period)

        if not stat_entry:
            if schedule_entry:
                opponent = schedule_entry.get("team", "TBD")
                date = schedule_entry.get("date")
                if isinstance(date, datetime):
                    status = f"Scheduled: {date.strftime('%a %m/%d')} vs {opponent}"
                else:
                    status = f"Scheduled vs {opponent}"
            else:
                status = "No game today."
            return {"status": status, "points": None, "minutes": "-", "fouls": "-", "plus_minus": "-"}

        opponent = stat_entry.get("team", schedule_entry.get("team") if schedule_entry else None)
        date = stat_entry.get("date", schedule_entry.get("date") if schedule_entry else None)
        header_parts: List[str] = []
        if opponent:
            header_parts.append(f"vs {opponent}")
        if isinstance(date, datetime):
            header_parts.append(date.strftime('%a %m/%d'))
        status = " ".join(header_parts) if header_parts else "Current game"

        points = float(stat_entry.get("applied_total", 0.0) or 0.0)
        totals = stat_entry.get("total") or {}
        minutes = self._lookup_stat(totals, ("MIN", "MPG"))
        fouls = self._lookup_stat(totals, ("PF",))
        plus_minus = self._lookup_plus_minus(totals)
        if plus_minus in {"-", ""}:
            plus_minus = self._fetch_live_plus_minus(player)
        return {"status": status, "points": points, "minutes": minutes, "fouls": fouls, "plus_minus": plus_minus}

    def _calculate_average(self, player: Player, games: int) -> Optional[float]:
        totals: List[float] = []
        numeric_keys = sorted((int(key) for key in player.stats.keys() if key.isdigit()), reverse=True)
        for scoring_period in numeric_keys:
            stat_line = player.stats.get(str(scoring_period), {})
            value = stat_line.get("applied_total")
            if value is None:
                continue
            totals.append(float(value))
            if len(totals) >= games:
                break
        if not totals:
            return None
        return sum(totals) / len(totals)

    def _format_player_status(self, player: Player) -> str:
        parts: List[str] = []
        status = getattr(player, "injuryStatus", "")
        if status:
            parts.append(status)
        expected = getattr(player, "expected_return_date", None)
        if expected:
            parts.append(expected.strftime('%b %d'))
        if not parts:
            return "Active"
        return " - ".join(parts)

    @staticmethod
    def _format_numeric(value: Optional[float]) -> str:
        if value is None:
            return "-"
        return f"{value:.2f}"

    def _format_schedule(self, player: Player, periods: Iterable[int], fallback: str) -> str:
        entries: List[str] = []
        for period in periods:
            schedule = player.schedule.get(str(period))
            if not schedule:
                continue
            opponent = schedule.get("team", "TBD")
            date = schedule.get("date")
            if isinstance(date, datetime):
                entries.append(f"{date.strftime('%a %m/%d')} vs {opponent}")
            else:
                entries.append(opponent)
        return ", ".join(entries) if entries else fallback

    @staticmethod
    def _lookup_stat(stats: Dict[str, float], keys: Sequence[str]) -> str:
        for key in keys:
            value = stats.get(key)
            if value is not None:
                return f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
        return "-"

    @staticmethod
    def _lookup_plus_minus(stats: Dict[str, float]) -> str:
        plus_keys = ("+/−", "+/-", "PLUS_MINUS", "PM", "45")
        for key in plus_keys:
            if key in stats:
                value = stats[key]
                return f"{value:+.1f}" if isinstance(value, (int, float)) else str(value)
        for key, value in stats.items():
            if "PLUS" in key.upper():
                return f"{value:+.1f}" if isinstance(value, (int, float)) else str(value)
        return "-"

    def _fetch_live_plus_minus(self, player: Player) -> str:
        cached = self._live_plus_minus_cache.get(player.playerId)
        if cached is not None:
            return cached

        display = "-"
        try:
            value = get_live_plus_minus(player.name)
        except Exception:
            value = None
        if isinstance(value, (int, float)):
            display = f"{value:+.1f}"

        self._live_plus_minus_cache[player.playerId] = display
        return display

    def _sort_tree(self, tree: ttk.Treeview, column: str) -> None:
        items = []
        for iid in tree.get_children(""):
            value = tree.set(iid, column)
            items.append((self._coerce_sort_value(value), value, iid))

        key = (tree, column)
        reverse = self._tree_sort_states.get(key, False)
        items.sort(key=lambda entry: (entry[0], entry[1]), reverse=reverse)

        for index, (_, _, iid) in enumerate(items):
            tree.move(iid, "", index)

        self._tree_sort_states[key] = not reverse

    @staticmethod
    def _coerce_sort_value(value: Any) -> Tuple[int, Any]:
        if value is None:
            return (2, "")
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped == "-":
                return (2, "")
            try:
                numeric = float(stripped.replace("+", ""))
            except ValueError:
                return (1, stripped.lower())
            return (0, numeric)
        if isinstance(value, (int, float)):
            return (0, float(value))
        return (1, str(value).lower())

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)


def main() -> None:
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    app = NBAWatchlistApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
