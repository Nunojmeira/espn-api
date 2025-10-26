import json
from unittest import TestCase

from espn_api.basketball import League


class FakeRequest:
    def __init__(self, response):
        self.response = response
        self.last_params = None
        self.last_headers = None

    def league_get(self, params=None, headers=None):
        self.last_params = params
        self.last_headers = headers
        return self.response


class LeagueWatchlistTest(TestCase):
    def test_team_watchlist_returns_players(self):
        league = League(league_id=123456, year=2024, fetch_league=False)
        league.pro_schedule = {}

        watchlist_response = {
            "players": [
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
                }
            ]
        }

        fake_request = FakeRequest(watchlist_response)
        league.espn_request = fake_request

        players = league.team_watchlist(team_id=7, size=25)

        self.assertEqual(len(players), 1)
        self.assertEqual(players[0].name, "Test Guard")
        self.assertEqual(players[0].position, "PG")

        self.assertEqual(fake_request.last_params, {'view': 'mWatchlist'})
        filters = json.loads(fake_request.last_headers['x-fantasy-filter'])
        self.assertEqual(filters['players']['filterTeamIds']['value'], [7])
        self.assertEqual(filters['players']['limit'], 25)
