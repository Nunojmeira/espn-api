from importlib import util
from pathlib import Path
from unittest import TestCase

MODULE_PATH = Path(__file__).resolve().parents[3] / "examples" / "nba_watchlist_app.py"
spec = util.spec_from_file_location("nba_watchlist_app", MODULE_PATH)
module = util.module_from_spec(spec)
assert spec and spec.loader  # keep mypy/pyright happy when available
spec.loader.exec_module(module)  # type: ignore[union-attr]
NBAWatchlistApp = module.NBAWatchlistApp


class StubBoxScore:
    def __init__(self, home, away):
        self.home_lineup = home
        self.away_lineup = away


class StubLeague:
    def __init__(self, box_scores):
        self._box_scores = box_scores
        self.currentMatchupPeriod = 3
        self.scoringPeriodId = 42
        self.calls = []

    def box_scores(self, matchup_period=None, scoring_period=None, matchup_total=None):
        self.calls.append((matchup_period, scoring_period, matchup_total))
        return self._box_scores


class StubPlayer:
    def __init__(self, player_id, points):
        self.playerId = player_id
        self.points = points


class WatchlistAppHelperTests(TestCase):
    def test_coerce_positive_int_accepts_numeric_strings(self):
        self.assertEqual(NBAWatchlistApp._coerce_positive_int("128"), 128)
        self.assertEqual(NBAWatchlistApp._coerce_positive_int("72.5"), 72)
        self.assertEqual(NBAWatchlistApp._coerce_positive_int(96), 96)
        self.assertIsNone(NBAWatchlistApp._coerce_positive_int("invalid"))
        self.assertIsNone(NBAWatchlistApp._coerce_positive_int(-5))

    def test_apply_box_score_points_overrides_live_totals(self):
        players = {
            1: {"today_fpts": None},
            2: {"today_fpts": 4.0},
        }
        league = StubLeague([
            StubBoxScore(
                [StubPlayer(1, 12.5)],
                [StubPlayer(2, "7.0"), StubPlayer(999, 30)],
            )
        ])

        app = object.__new__(NBAWatchlistApp)
        app.league = league

        app._apply_box_score_points(players)

        self.assertEqual(players[1]["today_fpts"], 12.5)
        self.assertEqual(players[2]["today_fpts"], 7.0)
        self.assertEqual(league.calls, [(league.currentMatchupPeriod, league.scoringPeriodId, False)])
