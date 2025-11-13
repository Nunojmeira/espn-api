from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from espn_api.utils.nba_plus_minus import get_live_plus_minus


class DummyResponse:
    def __init__(self, json_data: Dict[str, Any]) -> None:
        self.status_code = 200
        self._json_data = json_data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return self._json_data


class DummySession:
    def __init__(self, responses: Dict[str, Dict[str, Any]]) -> None:
        self.responses = responses
        self.requested_urls: List[str] = []

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> DummyResponse:
        self.requested_urls = list(self.requested_urls) + [url]
        payload = self.responses.get(url)
        if payload is None:
            raise RuntimeError(f"Unexpected URL: {url}")
        return DummyResponse(payload)


def build_scoreboard(boxscore_url: str, player_name: str, plus_minus: Any) -> Dict[str, Any]:
    return {
        "events": [
            {
                "competitions": [
                    {
                        "boxscore": {"$ref": boxscore_url},
                    }
                ]
            }
        ]
    }


def build_boxscore(player_name: str, plus_minus: Any) -> Dict[str, Any]:
    return {
        "teams": [
            {
                "statistics": [
                    {
                        "athletes": [
                            {
                                "athlete": {"displayName": player_name},
                                "stats": {"plusMinus": plus_minus},
                            }
                        ]
                    }
                ]
            }
        ]
    }


def test_get_live_plus_minus_extracts_numeric_value() -> None:
    player_name = "Sample Player"
    boxscore_url = "http://example.com/boxscore/1"
    responses = {
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard": build_scoreboard(boxscore_url, player_name, 5),
        boxscore_url: build_boxscore(player_name, 5),
    }
    session = DummySession(responses)

    result = get_live_plus_minus(player_name, session=session)

    assert result == pytest.approx(5.0)


def test_get_live_plus_minus_parses_string_payload() -> None:
    player_name = "Sample Player"
    boxscore_url = "http://example.com/boxscore/2"
    responses = {
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard": build_scoreboard(boxscore_url, player_name, "+/-: -3"),
        boxscore_url: build_boxscore(player_name, "+/-: -3"),
    }
    session = DummySession(responses)

    result = get_live_plus_minus(player_name, session=session)

    assert result == pytest.approx(-3.0)


def test_get_live_plus_minus_returns_none_on_missing_data() -> None:
    player_name = "Missing Player"
    responses = {
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard": {"events": []},
    }
    session = DummySession(responses)

    result = get_live_plus_minus(player_name, session=session)

    assert result is None
