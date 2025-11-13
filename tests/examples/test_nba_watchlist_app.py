from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.nba_watchlist_app import NBAWatchlistApp


class DummyLeague:
    scoringPeriodId = 3


def _build_app() -> NBAWatchlistApp:
    app = NBAWatchlistApp.__new__(NBAWatchlistApp)
    app.league = DummyLeague()
    app._live_plus_minus_cache = {}
    return app


def test_get_today_metrics_without_box_score() -> None:
    app = _build_app()
    player = SimpleNamespace(
        stats={
            "3": {
                "applied_total": 25.4,
                "applied_avg": 25.4,
            }
        },
        schedule={
            "3": {
                "team": "BOS",
                "date": datetime(2024, 1, 15, 19, 0),
            }
        },
        playerId=1,
    )

    metrics = app._get_today_metrics(player)

    assert metrics["points"] is None
    assert metrics["minutes"] == "-"
    assert metrics["fouls"] == "-"
    assert metrics["plus_minus"] == "-"


def test_get_today_metrics_with_box_score() -> None:
    app = _build_app()
    fetched = []

    def _fail_fetch(_player: SimpleNamespace) -> str:
        fetched.append(True)
        return "n/a"

    app._fetch_live_plus_minus = _fail_fetch  # type: ignore[attr-defined]

    player = SimpleNamespace(
        stats={
            "3": {
                "applied_total": 30.0,
                "applied_avg": 20.0,
                "total": {"PF": 2, "MIN": 34, "+/-": 5},
            }
        },
        schedule={
            "3": {
                "team": "NYK",
                "date": datetime(2024, 1, 15, 19, 30),
            }
        },
        playerId=2,
    )

    metrics = app._get_today_metrics(player)

    assert metrics["points"] == pytest.approx(30.0)
    assert metrics["minutes"] == "34.0"
    assert metrics["fouls"] == "2.0"
    assert metrics["plus_minus"] == "+5.0"
    assert not fetched


class _FakeTree:
    def __init__(self) -> None:
        self._columns = ("col_a", "col_b")
        self._widths = {
            "col_a": {"width": 120},
            "col_b": {"width": 80},
        }
        self.updated = False

    def __getitem__(self, key: str):
        if key == "columns":
            return self._columns
        raise KeyError(key)

    def column(self, column_id: str):
        return self._widths[column_id]

    def update_idletasks(self) -> None:
        self.updated = True


class _FakePane:
    def __init__(self, sash_x: int) -> None:
        self._sash_x = sash_x
        self.updated = False

    def update_idletasks(self) -> None:
        self.updated = True

    def panes(self):
        return ["pane_a", "pane_b"]

    def sash_coord(self, index: int):
        if index != 0:
            raise IndexError(index)
        return (self._sash_x, 0)


def test_capture_tree_widths_updates_geometry() -> None:
    app = _build_app()
    tree = _FakeTree()

    widths = app._capture_tree_widths(tree)  # type: ignore[arg-type]

    assert tree.updated is True
    assert widths == {"col_a": 120, "col_b": 80}


def test_capture_paned_positions_updates_geometry() -> None:
    app = _build_app()
    pane = _FakePane(240)
    app._content_pane = pane  # type: ignore[attr-defined]

    positions = app._capture_paned_positions()

    assert pane.updated is True
    assert positions == [240]
