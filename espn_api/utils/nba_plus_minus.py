"""Utilities for retrieving live NBA plus/minus information.

The tkinter watchlist example relies on this helper to augment box score
information with a live plus/minus value when it is not yet available from the
fantasy API response.  The function defined here intentionally degrades
gracefully when network access is unavailable or when ESPN's public scoreboard
schema changes.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional

import requests

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


def get_live_plus_minus(player_name: str, *, session: Optional[requests.Session] = None) -> Optional[float]:
    """Attempt to fetch the live plus/minus value for ``player_name``.

    The function queries ESPN's public scoreboard endpoint for games scheduled
    on the current day.  If a box score is available, the payload is searched
    for a plus/minus statistic that belongs to the requested player.  When the
    data cannot be located or a network error occurs ``None`` is returned.

    Parameters
    ----------
    player_name:
        Display name for the player.  A case insensitive match is used when the
        scoreboard payload contains accented characters.
    session:
        Optional :class:`requests.Session` instance.  Passing a session is
        useful for testing where the HTTP requests are mocked.
    """

    if not player_name:
        return None

    http = session or requests.Session()
    today = datetime.utcnow().strftime("%Y%m%d")

    try:
        response = http.get(SCOREBOARD_URL, params={"dates": today}, timeout=5)
        response.raise_for_status()
        scoreboard = response.json()
    except (requests.RequestException, ValueError):
        return None

    events = scoreboard.get("events", []) if isinstance(scoreboard, dict) else []
    for event in events:
        competitions = event.get("competitions", []) if isinstance(event, dict) else []
        for competition in competitions:
            boxscore_ref = _extract_boxscore_ref(competition)
            if not boxscore_ref:
                continue
            try:
                box_response = http.get(boxscore_ref, timeout=5)
                box_response.raise_for_status()
                box_data = box_response.json()
            except (requests.RequestException, ValueError):
                continue

            value = _extract_plus_minus(box_data, player_name)
            if value is not None:
                return value

    return None


def _extract_boxscore_ref(competition: Dict[str, Any]) -> Optional[str]:
    if not isinstance(competition, dict):
        return None

    boxscore = competition.get("boxscore")
    if isinstance(boxscore, dict):
        ref = boxscore.get("$ref")
        if isinstance(ref, str):
            return ref
    return None


def _extract_plus_minus(boxscore: Dict[str, Any], player_name: str) -> Optional[float]:
    if not isinstance(boxscore, dict):
        return None

    target = player_name.casefold()
    queue = deque([boxscore])
    visited = set()

    while queue:
        item = queue.popleft()
        obj_id = id(item)
        if obj_id in visited:
            continue
        visited.add(obj_id)

        if isinstance(item, dict):
            athlete = item.get("athlete")
            if isinstance(athlete, dict):
                name = athlete.get("displayName") or athlete.get("fullName")
                if isinstance(name, str) and name.casefold() == target:
                    stats = item.get("stats")
                    value = _search_plus_minus(stats)
                    if value is not None:
                        return value
            for value in item.values():
                queue.append(value)
        elif isinstance(item, list):
            queue.extend(item)

    return None


def _search_plus_minus(stats: Any) -> Optional[float]:
    if stats is None:
        return None
    if isinstance(stats, (int, float)):
        return float(stats)
    if isinstance(stats, str):
        return _parse_plus_minus_string(stats)
    if isinstance(stats, dict):
        for key, value in stats.items():
            if isinstance(key, str) and _is_plus_minus_key(key):
                parsed = _coerce_float(value)
                if parsed is not None:
                    return parsed
            nested = _search_plus_minus(value)
            if nested is not None:
                return nested
        return None
    if isinstance(stats, list):
        for value in stats:
            nested = _search_plus_minus(value)
            if nested is not None:
                return nested
    return None


def _parse_plus_minus_string(value: str) -> Optional[float]:
    stripped = value.strip()
    if not stripped:
        return None

    lowered = stripped.casefold()
    if lowered.startswith("+/-") or "plus" in lowered:
        try:
            tokens = [token for token in stripped.replace("+", " +").split() if token]
            for token in reversed(tokens):
                parsed = _coerce_float(token)
                if parsed is not None:
                    return parsed
        except ValueError:
            return None
    return _coerce_float(stripped)


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace("+", "").strip())
        except ValueError:
            return None
    return None


def _is_plus_minus_key(key: str) -> bool:
    normalized = key.casefold()
    return any(token in normalized for token in {"plus", "pm", "+/", "plusminus"})

