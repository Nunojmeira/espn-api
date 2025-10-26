"""Interactive NBA fantasy watchlist application built on top of espn-api.

This module exposes a simple command line application that allows fantasy
basketball managers to track a personal watchlist of players using live data
from their ESPN league.  The application demonstrates how to combine several
helpers that ship with the ``espn_api`` package to surface common pieces of
information that managers care about during the season:

* Current-day box score production for any player in the watchlist.
* Fantasy schedule context for the current and upcoming matchup periods.
* Rolling averages for the previous three and seven scoring periods.

Because the underlying package communicates with the live ESPN fantasy service,
the script expects valid league information (and, for private leagues,
authentication cookies).  The data that is retrieved mirrors the information on
the ESPN website, making the module a practical starting point for building
richer dashboards or automation on top of the API.

The module can be executed directly.  Example::

    python -m examples.nba_watchlist_app --league-id 12345 --year 2024

"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from textwrap import dedent
from typing import Dict, List, Optional, Sequence, Tuple

from espn_api.basketball import League
from espn_api.basketball.player import Player
from espn_api.utils.utils import json_parsing


@dataclass
class WatchlistEntry:
    """Container that keeps minimal player context in the watchlist."""

    player_id: int
    display_name: str


@dataclass
class LeagueCredentials:
    """Grouping of the parameters that are required to build a league."""

    league_id: int
    year: int
    espn_s2: Optional[str] = None
    swid: Optional[str] = None


def _format_dt(value: Optional[datetime]) -> str:
    """Format ``datetime`` values consistently for CLI output."""

    if not value:
        return "-"
    return value.strftime("%Y-%m-%d %I:%M %p")


def _stat_lookup(stats: Dict[str, float], keys: Sequence[str]) -> Optional[float]:
    """Return the first present stat value for any key in ``keys``."""

    for key in keys:
        if key in stats:
            return stats[key]
    return None


class NBAWatchlistApp:
    """Small interactive helper for managing an NBA fantasy watchlist."""

    METRIC_LABELS = {
        "1": "Current day game information",
        "2": "Schedule for current and next matchup periods",
        "3": "Past three scoring periods average",
        "4": "Past seven scoring periods average",
    }

    PLUS_MINUS_KEYS = ("PLUS_MINUS", "plusMinus", "+/-", "PM")

    def __init__(self, league: League):
        self.league = league
        self.watchlist: Dict[int, WatchlistEntry] = {}

    # ------------------------------------------------------------------
    # Interactive helpers
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Entrypoint for the interactive loop."""

        actions = {
            "1": ("View watchlist metrics", self._interactive_show_watchlist),
            "2": ("Add player to watchlist", self._interactive_add_player),
            "3": ("Remove player from watchlist", self._interactive_remove_player),
            "4": ("Refresh league data", self.refresh_league),
            "5": ("Find my fantasy team", self._interactive_find_team),
            "6": ("Import entire team roster into watchlist", self._interactive_import_team),
            "q": ("Quit", None),
        }

        print("Welcome to the NBA Fantasy Watchlist!\n")
        self._print_league_summary()
        while True:
            print("\nWhat would you like to do?")
            for key, (label, _) in actions.items():
                print(f"  {key}) {label}")
            choice = input("Select an option: ").strip().lower()
            if choice == "q":
                print("Good luck with your matchups!")
                return
            action = actions.get(choice)
            if not action:
                print("Unknown option. Please choose from the menu.")
                continue
            handler = action[1]
            if handler:
                handler()

    def _interactive_show_watchlist(self) -> None:
        if not self.watchlist:
            print("\nYour watchlist is currently empty. Add a player first.")
            return
        print("\nSelect a metric to display:")
        for key, label in self.METRIC_LABELS.items():
            print(f"  {key}) {label}")
        metric = input("Metric: ").strip()
        if metric not in self.METRIC_LABELS:
            print("Invalid metric choice.")
            return
        print(f"\n{self.METRIC_LABELS[metric]}\n{'-' * 60}")
        if metric == "1":
            self._display_current_day_box_scores()
        elif metric == "2":
            self._display_schedule_context()
        elif metric == "3":
            self._display_recent_average(count=3)
        elif metric == "4":
            self._display_recent_average(count=7)

    def _interactive_add_player(self) -> None:
        query = input("Enter player name or ID: ").strip()
        if not query:
            print("You must provide a player identifier.")
            return
        player = self._lookup_player(query)
        if not player:
            print("Player could not be located. Make sure the name or ID is valid.")
            return
        if player.playerId in self.watchlist:
            print(f"{player.name} is already on the watchlist.")
            return
        self.watchlist[player.playerId] = WatchlistEntry(player.playerId, player.name)
        print(f"Added {player.name} to the watchlist.")

    def _interactive_remove_player(self) -> None:
        if not self.watchlist:
            print("Your watchlist is already empty.")
            return
        print("Players on the watchlist:")
        for idx, entry in enumerate(self.watchlist.values(), start=1):
            print(f"  {idx}) {entry.display_name}")
        selection = input("Remove which player? (number): ").strip()
        if not selection.isdigit():
            print("Please choose a valid numeric entry from the list.")
            return
        idx = int(selection) - 1
        if idx < 0 or idx >= len(self.watchlist):
            print("Selection is outside of the watchlist range.")
            return
        player_id = list(self.watchlist.keys())[idx]
        removed = self.watchlist.pop(player_id)
        print(f"Removed {removed.display_name} from the watchlist.")

    def _interactive_find_team(self) -> None:
        print("\nTeams in this league:")
        for team in self.league.teams:
            owners = ", ".join(json_parsing(owner, "displayName") for owner in team.owners) or "Unknown"
            print(f"  ID {team.team_id:>2} | {team.team_name} | Owners: {owners}")

    def _interactive_import_team(self) -> None:
        team_id = input("Enter the team ID to import: ").strip()
        if not team_id.isdigit():
            print("Team ID must be numeric.")
            return
        team = self.league.get_team_data(int(team_id))
        if not team:
            print("Unable to find a team with that ID.")
            return
        imported = 0
        for player in team.roster:
            if player.playerId not in self.watchlist:
                self.watchlist[player.playerId] = WatchlistEntry(player.playerId, player.name)
                imported += 1
        print(f"Imported {imported} players from {team.team_name} into the watchlist.")

    # ------------------------------------------------------------------
    # Data fetching & presentation helpers
    # ------------------------------------------------------------------
    def refresh_league(self) -> None:
        """Pull updated data from ESPN for the current league."""

        self.league.fetch_league()
        print("League information refreshed.")

    def _print_league_summary(self) -> None:
        summary = dedent(
            f"""
            League ID: {self.league.league_id}  Season: {self.league.year}
            Current matchup period: {self.league.currentMatchupPeriod}
            Current scoring period: {self.league.scoringPeriodId}
            Teams: {len(self.league.teams)}
            """
        ).strip()
        print(summary)

    def _lookup_player(self, query: str) -> Optional[Player]:
        """Resolve a player by ID or name using ``league.player_info``."""

        # Attempt ID lookup first.
        if query.isdigit():
            result = self.league.player_info(playerId=int(query))
            if isinstance(result, Player):
                return result

        # Fallback to a name search.  ESPN returns partial matches, so prompt
        # the user if multiple players are present.
        result = self.league.player_info(name=query)
        if isinstance(result, list):
            return self._disambiguate_player(result)
        return result

    def _disambiguate_player(self, players: Sequence[Player]) -> Optional[Player]:
        print("Multiple players match that query:")
        for idx, player in enumerate(players, start=1):
            print(f"  {idx}) {player.name} — {player.proTeam} ({player.position})")
        choice = input("Select the correct player (number): ").strip()
        if not choice.isdigit():
            print("Invalid selection; aborting.")
            return None
        idx = int(choice) - 1
        if idx < 0 or idx >= len(players):
            print("Selection out of range; aborting.")
            return None
        return players[idx]

    # ------------------------------------------------------------------
    # Metric presentation
    # ------------------------------------------------------------------
    def _display_current_day_box_scores(self) -> None:
        box_scores = self.league.box_scores(scoring_period=self.league.scoringPeriodId, matchup_total=False)
        player_map: Dict[int, Tuple[str, str, Dict[str, float], float]] = {}
        for box in box_scores:
            for player in getattr(box, "home_lineup", []):
                player_map[player.playerId] = (
                    player.proTeam,
                    player.pro_opponent,
                    player.points_breakdown,
                    player.points,
                )
            for player in getattr(box, "away_lineup", []):
                player_map[player.playerId] = (
                    player.proTeam,
                    player.pro_opponent,
                    player.points_breakdown,
                    player.points,
                )

        for entry in self.watchlist.values():
            if entry.player_id not in player_map:
                print(f"{entry.display_name:25} | No active NBA game today")
                continue
            pro_team, opponent, breakdown, points = player_map[entry.player_id]
            minutes = _stat_lookup(breakdown, ("MIN", "Minutes", "MINUTES"))
            fouls = _stat_lookup(breakdown, ("PF", "Fouls"))
            plus_minus = _stat_lookup(breakdown, self.PLUS_MINUS_KEYS)
            print(
                f"{entry.display_name:25} | {points:5.1f} fantasy pts | "
                f"MIN: {minutes if minutes is not None else 'N/A'} | "
                f"PF: {fouls if fouls is not None else 'N/A'} | "
                f"+/-: {plus_minus if plus_minus is not None else 'N/A'} | "
                f"Opp: {opponent or pro_team or '-'}"
            )

    def _display_schedule_context(self) -> None:
        current_period = self.league.currentMatchupPeriod
        next_period = current_period + 1
        for entry in self.watchlist.values():
            player = self.league.player_info(playerId=entry.player_id)
            print(f"\n{entry.display_name}")
            for period, label in ((current_period, "Current week"), (next_period, "Next week")):
                scoring_periods = self.league.matchup_ids.get(period)
                if not scoring_periods:
                    print(f"  {label}: schedule unavailable.")
                    continue
                print(f"  {label}:")
                for scoring_period in scoring_periods:
                    game = player.schedule.get(str(scoring_period))
                    if not game:
                        print(f"    - {scoring_period}: No game scheduled")
                        continue
                    date = _format_dt(game.get("date"))
                    opponent = game.get("team") or "TBD"
                    print(f"    - {scoring_period}: {date} vs {opponent}")

    def _display_recent_average(self, count: int) -> None:
        label = "scoring periods" if count > 1 else "scoring period"
        for entry in self.watchlist.values():
            player = self.league.player_info(playerId=entry.player_id)
            recent_points = self._collect_recent_points(player)
            if not recent_points:
                print(f"{entry.display_name:25} | No scoring data available")
                continue
            slice_points = recent_points[:count]
            average = sum(slice_points) / len(slice_points)
            print(f"{entry.display_name:25} | Avg ({len(slice_points)} {label}): {average:.2f}")

    @staticmethod
    def _collect_recent_points(player: Player) -> List[float]:
        """Extract daily fantasy totals in reverse chronological order."""

        scoring_totals: List[Tuple[int, float]] = []
        for key, payload in player.stats.items():
            if not key.isdigit():
                continue
            applied_total = payload.get("applied_total")
            if applied_total is None:
                continue
            scoring_totals.append((int(key), float(applied_total)))
        scoring_totals.sort(key=lambda item: item[0], reverse=True)
        return [value for _, value in scoring_totals]


def _build_league(creds: LeagueCredentials) -> League:
    """Factory wrapper that instantiates :class:`League` with validation."""

    kwargs = dict(league_id=creds.league_id, year=creds.year)
    if creds.espn_s2 and creds.swid:
        kwargs.update(espn_s2=creds.espn_s2, swid=creds.swid)
    return League(**kwargs)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive NBA fantasy watchlist app")
    parser.add_argument("--league-id", type=int, required=True, help="ESPN league identifier")
    parser.add_argument("--year", type=int, required=True, help="Fantasy season year")
    parser.add_argument("--espn-s2", help="ESPN_s2 cookie for private leagues")
    parser.add_argument("--swid", help="SWID cookie for private leagues")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    creds = LeagueCredentials(
        league_id=args.league_id,
        year=args.year,
        espn_s2=args.espn_s2,
        swid=args.swid,
    )
    league = _build_league(creds)
    app = NBAWatchlistApp(league)
    app.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user.")
        sys.exit(0)
