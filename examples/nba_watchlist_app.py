"""NBA fantasy watchlist desktop application using espn-api.

This module exposes a Tkinter based GUI that can be executed on Windows
(or any OS with a Python 3 interpreter) to monitor NBA fantasy players.

Example
-------
python examples/nba_watchlist_app.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Iterable, List, Optional, Sequence

from espn_api.basketball import League
from espn_api.basketball.player import Player


class NBAWatchlistApp:
    """Tkinter application that builds an NBA fantasy watchlist."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ESPN NBA Fantasy Watchlist")
        self.root.geometry("1280x620")

        self._saved_preferences = self._load_saved_preferences()

        self.league: Optional[League] = None
        self.watchlist_ids: List[int] = []
        self.team_by_label: Dict[str, int] = {}
        self.league_players: Dict[int, Dict[str, Any]] = {}
        self._tree_sort_states: Dict[Any, bool] = {}

        self._build_widgets()

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
        content = ttk.Frame(self.root)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

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

        player_columns = ("player", "nba_team", "position", "fantasy_team", "availability")
        self.player_tree = ttk.Treeview(
            player_frame,
            columns=player_columns,
            show="headings",
            height=16,
            selectmode="extended",
        )
        player_headings = {
            "player": "Player",
            "nba_team": "NBA Team",
            "position": "Position",
            "fantasy_team": "Fantasy Team",
            "availability": "Availability",
        }
        for column, title in player_headings.items():
            self.player_tree.heading(column, text=title, command=lambda c=column: self._sort_tree(self.player_tree, c))
            anchor = tk.W if column in {"player", "fantasy_team", "availability"} else tk.CENTER
            width = 200 if column == "player" else 120
            self.player_tree.column(column, anchor=anchor, width=width, stretch=False)
        self.player_tree.column("fantasy_team", width=180)

        self.player_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5, pady=(0, 5))

        player_scrollbar = ttk.Scrollbar(player_frame, orient=tk.VERTICAL, command=self.player_tree.yview)
        player_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 5))
        self.player_tree.configure(yscrollcommand=player_scrollbar.set)

        # Watchlist table ----------------------------------------------
        watchlist = ttk.LabelFrame(content, text="Watchlist")
        watchlist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        watchlist_columns = (
            "player",
            "fantasy_team",
            "availability",
            "today_status",
            "today_fpts",
            "today_minutes",
            "today_fouls",
            "today_plus_minus",
            "curr_week",
            "next_week",
            "last3",
            "last7",
        )
        self.tree = ttk.Treeview(
            watchlist,
            columns=watchlist_columns,
            show="headings",
            height=16,
            selectmode="extended",
        )
        watchlist_headings = {
            "player": "Player",
            "fantasy_team": "Fantasy Team",
            "availability": "Availability",
            "today_status": "Today's Game",
            "today_fpts": "FPts",
            "today_minutes": "MIN",
            "today_fouls": "PF",
            "today_plus_minus": "+/-",
            "curr_week": "Current Week",
            "next_week": "Next Week",
            "last3": "Past 3 Avg",
            "last7": "Past 7 Avg",
        }
        for column, title in watchlist_headings.items():
            self.tree.heading(column, text=title, command=lambda c=column: self._sort_tree(self.tree, c))
            if column == "player":
                width = 190
                anchor = tk.W
            elif column in {"fantasy_team", "availability", "today_status", "curr_week", "next_week"}:
                width = 170 if column == "today_status" else 150
                anchor = tk.W
            elif column in {"today_fpts", "last3", "last7"}:
                width = 90
                anchor = tk.CENTER
            else:
                width = 70
                anchor = tk.CENTER
            self.tree.column(column, anchor=anchor, width=width, stretch=False)

        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.TOP, padx=5, pady=(0, 5))

        watchlist_scroll_y = ttk.Scrollbar(watchlist, orient=tk.VERTICAL, command=self.tree.yview)
        watchlist_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        watchlist_scroll_x = ttk.Scrollbar(watchlist, orient=tk.HORIZONTAL, command=self.tree.xview)
        watchlist_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.configure(yscrollcommand=watchlist_scroll_y.set, xscrollcommand=watchlist_scroll_x.set)

        # Status bar ----------------------------------------------------
        self.status_var = tk.StringVar(value="Load a league to begin.")
        status_label = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_label.pack(fill=tk.X, padx=10, pady=(0, 5))

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
        self._populate_teams()
        self.watchlist_ids.clear()
        self.tree.delete(*self.tree.get_children())
        self.player_tree.delete(*self.player_tree.get_children())
        self._collect_league_players()
        self._populate_player_directory()
        self._set_status("League loaded. Add players or import a roster to begin.")
        self._save_preferences(
            league_id=league_id,
            year=year,
            espn_s2=espn_s2,
            swid=swid,
        )

    def add_selected_team(self) -> None:
        if not self.league:
            messagebox.showinfo("League Required", "Load a league before selecting a team.")
            return

        team_label = self.team_var.get()
        if team_label not in self.team_by_label:
            messagebox.showinfo("Select Team", "Please choose a team to import.")
            return

        team_id = self.team_by_label[team_label]
        team = next((t for t in self.league.teams if t.team_id == team_id), None)
        if not team:
            messagebox.showerror("Team Missing", "Unable to locate the selected team.")
            return

        added = 0
        for player in team.roster:
            if player.playerId not in self.watchlist_ids:
                self.watchlist_ids.append(player.playerId)
                added += 1
        if added:
            self._set_status(f"Added {added} players from {team.team_name} to the watchlist.")
            self.refresh_watchlist()
        else:
            self._set_status("All players from the selected roster are already on the watchlist.")

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
            self._set_status(f"Added player {self.league.player_map.get(player_id, query)} to watchlist.")
            self.refresh_watchlist()
        else:
            self._set_status("Player already exists on the watchlist.")

    def remove_selected(self) -> None:
        selections = self.tree.selection()
        if not selections:
            return

        for item in selections:
            try:
                player_id = int(item)
            except ValueError:
                continue
            if player_id in self.watchlist_ids:
                self.watchlist_ids.remove(player_id)
        for item in selections:
            self.tree.delete(item)

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

    def _load_saved_preferences(self) -> Dict[str, str]:
        path = self._preferences_path()
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return {k: str(v) for k, v in data.items() if isinstance(k, str)}
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _save_preferences(self, *, league_id: str, year: str, espn_s2: str, swid: str) -> None:
        data = {
            "league_id": league_id,
            "year": year,
        }
        if espn_s2:
            data["espn_s2"] = espn_s2
        if swid:
            data["swid"] = swid

        path = self._preferences_path()
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _collect_league_players(self) -> None:
        if not self.league:
            self.league_players = {}
            return

        players: Dict[int, Dict[str, Any]] = {}
        for team in self.league.teams:
            for player in team.roster:
                players[player.playerId] = {
                    "player_id": player.playerId,
                    "name": player.name,
                    "pro_team": player.proTeam,
                    "position": player.position,
                    "fantasy_team": team.team_name,
                    "is_free_agent": False,
                }

        try:
            free_agents = self.league.free_agents(size=500)
        except Exception:
            free_agents = []

        for player in free_agents:
            entry = {
                "player_id": player.playerId,
                "name": player.name,
                "pro_team": player.proTeam,
                "position": player.position,
                "fantasy_team": "Free Agent",
                "is_free_agent": True,
            }
            if player.playerId in players:
                players[player.playerId]["is_free_agent"] = True
                players[player.playerId]["name"] = player.name
                players[player.playerId]["pro_team"] = player.proTeam
                players[player.playerId]["position"] = player.position
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

            availability = "Free Agent" if info.get("is_free_agent") else "Rostered"
            values = (
                info["name"],
                info["pro_team"],
                info["position"],
                info["fantasy_team"],
                availability,
            )
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
        availability = "Free Agent" if info.get("is_free_agent") or fantasy_team == "Free Agent" else "Rostered"

        today_metrics = self._get_today_metrics(player)
        current_week = self._format_schedule(
            player,
            self._get_scoring_periods(self.league.currentMatchupPeriod),
            fallback="No games remaining this week.",
        )
        next_week = self._format_schedule(
            player,
            self._get_scoring_periods(self.league.currentMatchupPeriod + 1),
            fallback="Next week's schedule unavailable.",
        )
        last3 = self._calculate_average(player, games=3)
        last7 = self._calculate_average(player, games=7)

        return (
            player.name,
            fantasy_team,
            availability,
            today_metrics["status"],
            self._format_numeric(today_metrics["points"]),
            today_metrics["minutes"],
            today_metrics["fouls"],
            today_metrics["plus_minus"],
            current_week,
            next_week,
            self._format_numeric(last3),
            self._format_numeric(last7),
        )

    def _get_scoring_periods(self, matchup_period: int) -> Sequence[int]:
        if not self.league:
            return []
        periods = self.league.matchup_ids.get(matchup_period, [])
        return [int(p) for p in periods]

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
    def _coerce_sort_value(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped == "-":
                return ""
            try:
                return float(stripped.replace("+", ""))
            except ValueError:
                return stripped.lower()
        return value

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)


def main() -> None:
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    app = NBAWatchlistApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
