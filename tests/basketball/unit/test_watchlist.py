import json
from unittest import TestCase

from espn_api.basketball import League


class FakeRequest:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def league_get(self, params=None, headers=None):
        if not self.responses:
            raise AssertionError("No more responses configured for FakeRequest")

        self.calls.append((params, headers))
        return self.responses.pop(0)


class LeagueWatchlistTest(TestCase):
    def test_team_watchlist_returns_players(self):
        league = League(league_id=123456, year=2024, fetch_league=False)
        league.pro_schedule = {}

        watchlist_response = {
            "playerWatchList": {
                "watchlists": [
                    {
                        "teamId": 7,
                        "entries": [
                            {
                                "player": {
                                    "id": 101,
                                    "fullName": "Test Guard",
                                    "defaultPositionId": 1,
                                    "eligibleSlots": [0, 1],
                                    "proTeamId": 1,
                                    "injuryStatus": "ACTIVE",
                                    "stats": [],
                                },
                                "playerId": 101,
                                "lineupSlotId": 0,
                                "teamId": 7,
                            }
                        ],
                    },
                    {
                        "teamId": 4,
                        "entries": [
                            {
                                "player": {
                                    "id": 202,
                                    "fullName": "Other Player",
                                    "defaultPositionId": 4,
                                    "eligibleSlots": [4],
                                    "proTeamId": 10,
                                    "injuryStatus": "INJURY_RESERVE",
                                    "stats": [],
                                },
                                "playerId": 202,
                                "lineupSlotId": 0,
                                "teamId": 4,
                            }
                        ],
                    },
                ]
            }
        }

        fake_request = FakeRequest([watchlist_response])
        league.espn_request = fake_request

        players = league.team_watchlist(team_id=7, size=25)

        self.assertEqual(len(players), 1)
        self.assertEqual(players[0].name, "Test Guard")
        self.assertEqual(players[0].position, "PG")

        self.assertEqual(len(fake_request.calls), 1)
        params, headers = fake_request.calls[0]
        self.assertEqual(params, {'view': 'player_wl'})
        self.assertIsNone(headers)

    def test_team_watchlist_legacy_fallback(self):
        league = League(league_id=123456, year=2024, fetch_league=False)
        league.pro_schedule = {}

        legacy_response = {
            "players": [
                {
                    "player": {
                        "id": 303,
                        "fullName": "Legacy Player",
                        "defaultPositionId": 5,
                        "eligibleSlots": [5],
                        "proTeamId": 14,
                        "injuryStatus": "ACTIVE",
                        "stats": [],
                    },
                    "playerId": 303,
                    "lineupSlotId": 0,
                }
            ]
        }

        fake_request = FakeRequest([{}, legacy_response])
        league.espn_request = fake_request

        players = league.team_watchlist(team_id=9, size=10)

        self.assertEqual(len(players), 1)
        self.assertEqual(players[0].name, "Legacy Player")

        self.assertEqual(len(fake_request.calls), 2)
        first_params, first_headers = fake_request.calls[0]
        self.assertEqual(first_params, {'view': 'player_wl'})
        self.assertIsNone(first_headers)

        second_params, second_headers = fake_request.calls[1]
        self.assertEqual(second_params, {'view': 'mWatchlist'})
        filters = json.loads(second_headers['x-fantasy-filter'])
        self.assertEqual(filters['players']['filterTeamIds']['value'], [9])
        self.assertEqual(filters['players']['limit'], 10)

    def test_team_watchlist_handles_player_pool_entry(self):
        league = League(league_id=789012, year=2024, fetch_league=False)
        league.pro_schedule = {}

        watchlist_response = {
            "playerWatchList": {
                "watchlists": [
                    {
                        "teamId": 3,
                        "entries": [
                            {
                                "lineupSlotId": 0,
                                "playerPoolEntry": {
                                    "player": {
                                        "id": 401,
                                        "fullName": "Pool Entry Guard",
                                        "defaultPositionId": 1,
                                        "eligibleSlots": [0, 1],
                                        "proTeamId": 5,
                                        "injuryStatus": "ACTIVE",
                                        "stats": [],
                                    }
                                },
                            },
                            {
                                "lineupSlotId": 0,
                                "playerPoolEntry": {
                                    "player": {
                                        "id": 402,
                                        "fullName": "Pool Entry Forward",
                                        "defaultPositionId": 4,
                                        "eligibleSlots": [4, 6],
                                        "proTeamId": 12,
                                        "injuryStatus": "INJURY_RESERVE",
                                        "stats": [],
                                    }
                                },
                            },
                        ],
                    }
                ]
            }
        }

        fake_request = FakeRequest([watchlist_response])
        league.espn_request = fake_request

        players = league.team_watchlist(team_id=3, size=10)

        self.assertEqual(len(players), 2)
        player_names = [player.name for player in players]
        self.assertIn("Pool Entry Guard", player_names)
        self.assertIn("Pool Entry Forward", player_names)

        positions = {player.name: player.position for player in players}
        self.assertEqual(positions["Pool Entry Guard"], "PG")
        self.assertEqual(positions["Pool Entry Forward"], "PF")

        self.assertEqual(len(fake_request.calls), 1)
        params, headers = fake_request.calls[0]
        self.assertEqual(params, {'view': 'player_wl'})
        self.assertIsNone(headers)
