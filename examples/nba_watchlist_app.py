"""NBA fantasy watchlist desktop application using espn-api.

This module exposes a Tkinter based GUI that can be executed on Windows
(or any OS with a Python 3 interpreter) to monitor NBA fantasy players.

Example
-------
python examples/nba_watchlist_app.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from espn_api.basketball import League
from espn_api.basketball.player import Player


class NBAWatchlistApp:
    """Tkinter application that builds an NBA fantasy watchlist."""

    METRIC_TODAY = "Today's Game"
    METRIC_CURR_WEEK = "Current Week Schedule"
    METRIC_NEXT_WEEK = "Next Week Schedule"
    METRIC_LAST3 = "Past 3 Games Avg"
    METRIC_LAST7 = "Past 7 Games Avg"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ESPN NBA Fantasy Watchlist")
        self.root.geometry("940x520")

        self.league: Optional[League] = None
        self.watchlist_ids: List[int] = []
        self.team_by_label: Dict[str, int] = {}

        self._build_widgets()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        connection = ttk.LabelFrame(self.root, text="League Connection")
        connection.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(connection, text="League ID:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.league_id_var = tk.StringVar()
        ttk.Entry(connection, width=12, textvariable=self.league_id_var).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(connection, text="Season Year:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(connection, width=8, textvariable=self.year_var).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(connection, text="espn_s2 (optional):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.espn_s2_var = tk.StringVar()
        ttk.Entry(connection, width=40, textvariable=self.espn_s2_var).grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky=tk.W)

        ttk.Label(connection, text="SWID (optional):").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.swid_var = tk.StringVar()
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

        ttk.Label(controls, text="Metric:").grid(row=0, column=4, padx=5, pady=5)
        self.metric_var = tk.StringVar(value=self.METRIC_TODAY)
        metric_choices = (
            self.METRIC_TODAY,
            self.METRIC_CURR_WEEK,
            self.METRIC_NEXT_WEEK,
            self.METRIC_LAST3,
            self.METRIC_LAST7,
        )
        metric_combo = ttk.Combobox(controls, textvariable=self.metric_var, state="readonly", values=metric_choices, width=24)
        metric_combo.grid(row=0, column=5, padx=5, pady=5)
        metric_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_watchlist())

        ttk.Button(controls, text="Refresh", command=self.refresh_watchlist).grid(row=0, column=6, padx=5, pady=5)

        controls.columnconfigure(7, weight=1)

        # Watchlist table ----------------------------------------------
        watchlist = ttk.LabelFrame(self.root, text="Watchlist")
        watchlist.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("player", "details")
        self.tree = ttk.Treeview(watchlist, columns=columns, show="headings", height=12)
        self.tree.heading("player", text="Player")
        self.tree.heading("details", text="Details")
        self.tree.column("player", width=190, anchor=tk.W)
        self.tree.column("details", anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(watchlist, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

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
        self._set_status("League loaded. Add players or import a roster to begin.")

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
        for iid in self.tree.get_children():
            if int(iid) not in self.watchlist_ids:
                self.tree.delete(iid)

        metric = self.metric_var.get()
        for player_id in self.watchlist_ids:
            player = lookup.get(player_id)
            if not player:
                continue
            detail = self._format_metric(player, metric)
            player_name = player.name
            iid = str(player_id)
            if self.tree.exists(iid):
                self.tree.item(iid, values=(player_name, detail))
            else:
                self.tree.insert("", tk.END, iid=iid, values=(player_name, detail))

        self._set_status(f"Updated watchlist for {len(lookup)} players.")

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
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

        player_id = self.league.player_map.get(query)
        if isinstance(player_id, int):
            return player_id

        query_lower = query.lower()
        for key, value in self.league.player_map.items():
            if isinstance(key, str) and key.lower() == query_lower and isinstance(value, int):
                return value
        return None

    def _format_metric(self, player: Player, metric: str) -> str:
        if metric == self.METRIC_CURR_WEEK:
            periods = self._get_scoring_periods(self.league.currentMatchupPeriod)
            return self._format_schedule(player, periods, fallback="No games remaining this week.")
        if metric == self.METRIC_NEXT_WEEK:
            periods = self._get_scoring_periods(self.league.currentMatchupPeriod + 1)
            return self._format_schedule(player, periods, fallback="Next week's schedule unavailable.")
        if metric == self.METRIC_LAST3:
            return self._format_average(player, games=3)
        if metric == self.METRIC_LAST7:
            return self._format_average(player, games=7)
        return self._format_today(player)

    def _get_scoring_periods(self, matchup_period: int) -> Sequence[int]:
        if not self.league:
            return []
        periods = self.league.matchup_ids.get(matchup_period, [])
        return [int(p) for p in periods]

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

    def _format_average(self, player: Player, games: int) -> str:
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
            return "Fantasy points unavailable for recent games."
        average = sum(totals) / len(totals)
        return f"{average:.2f} FPts avg over last {len(totals)} games"

    def _format_today(self, player: Player) -> str:
        if not self.league:
            return ""
        scoring_period = str(self.league.scoringPeriodId)
        stat_entry = player.stats.get(scoring_period)
        schedule_entry = player.schedule.get(scoring_period)

        if not stat_entry:
            if schedule_entry:
                opponent = schedule_entry.get("team", "TBD")
                date = schedule_entry.get("date")
                if isinstance(date, datetime):
                    return f"Scheduled: {date.strftime('%a %m/%d')} vs {opponent}"
                return f"Scheduled vs {opponent}"
            return "No game today."

        opponent = stat_entry.get("team", schedule_entry.get("team") if schedule_entry else None)
        date = stat_entry.get("date", schedule_entry.get("date") if schedule_entry else None)
        header_parts: List[str] = []
        if opponent:
            header_parts.append(f"vs {opponent}")
        if isinstance(date, datetime):
            header_parts.append(date.strftime('%a %m/%d'))
        header = " ".join(header_parts) if header_parts else "Current game"

        points = stat_entry.get("applied_total", 0.0) or 0.0
        totals = stat_entry.get("total") or {}
        minutes = self._lookup_stat(totals, ("MIN", "MPG"))
        fouls = self._lookup_stat(totals, ("PF",))
        plus_minus = self._lookup_plus_minus(totals)
        return f"{header} | FPts: {points:.2f} | MIN: {minutes} | PF: {fouls} | +/-: {plus_minus}"

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

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)


def main() -> None:
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    app = NBAWatchlistApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
