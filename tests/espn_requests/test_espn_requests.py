from unittest import mock, TestCase
import requests_mock
import io
import json
from espn_api.requests.espn_requests import EspnFantasyRequests, ESPNAccessDenied

class EspnRequestsTest(TestCase):

    @requests_mock.Mocker()
    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_stub(self, mock_request, mock_stdout):
        url_api_key = 'https://registerdisney.go.com/jgc/v5/client/ESPN-FANTASYLM-PROD/api-key?langPref=en-US'
        mock_request.post(url_api_key, status_code=400)

    @requests_mock.Mocker()
    def test_get_watchlist_players(self, mock_request):
        cookies = {'espn_s2': 'token', 'SWID': '{1234-5678}'}
        request = EspnFantasyRequests(sport='nba', league_id=987654, year=2024, cookies=cookies)

        url = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/2024/segments/0/leagues/987654/players'
        payload = {
            'players': [
                {
                    'player': {'id': 1, 'fullName': 'Watchlist Player'},
                    'playerId': 1,
                }
            ]
        }

        mock_request.get(url, status_code=200, json=payload)

        entries = request.get_watchlist_players(season_id=2024, limit=25, offset=10)

        self.assertEqual(entries, payload['players'])
        last_request = mock_request.last_request
        self.assertIsNotNone(last_request)
        self.assertEqual(last_request.qs.get('view'), ['kona_player_info'])

        filters = json.loads(last_request.headers['x-fantasy-filter'])
        self.assertEqual(filters['players']['limit'], 25)
        self.assertEqual(filters['players']['offset'], 10)
        self.assertTrue(filters['players']['filterWatchList']['value'])

    def test_get_watchlist_players_requires_cookies(self):
        request = EspnFantasyRequests(sport='nba', league_id=123456, year=2024)

        with self.assertRaises(ESPNAccessDenied):
            request.get_watchlist_players()

    # @requests_mock.Mocker()
    # @mock.patch('sys.stdout', new_callable=io.StringIO)
    # def test_authentication_api_fail(self, mock_request, mock_stdout):
    #     url_api_key = 'https://registerdisney.go.com/jgc/v5/client/ESPN-FANTASYLM-PROD/api-key?langPref=en-US'
    #     mock_request.post(url_api_key, status_code=400)
    #     request = EspnFantasyRequests(sport='nfl', league_id=1234, year=2019)
    #     request.authentication(username='user', password='pass')
    #     self.assertEqual(mock_stdout.getvalue(), 'Unable to access API-Key\nRetry the authentication or continuing without private league access\n')
    
    # @requests_mock.Mocker()
    # @mock.patch('sys.stdout', new_callable=io.StringIO)
    # def test_authentication_login_fail(self, mock_request, mock_stdout):
    #     url_api_key = 'https://registerdisney.go.com/jgc/v5/client/ESPN-FANTASYLM-PROD/api-key?langPref=en-US'
    #     url_login = 'https://ha.registerdisney.go.com/jgc/v5/client/ESPN-FANTASYLM-PROD/guest/login?langPref=en-US'
    #     mock_request.post(url_api_key,  headers={'api-key':'None'}, status_code=200)
    #     mock_request.post(url_login, status_code=400, json={'eror': 'error'})

    #     request = EspnFantasyRequests(sport='nfl', league_id=1234, year=2019)
    #     request.authentication(username='user', password='pass')
    #     self.assertEqual(mock_stdout.getvalue(), 'Authentication unsuccessful - check username and password input\nRetry the authentication or continuing without private league access\n')
    
    # @requests_mock.Mocker()
    # @mock.patch('sys.stdout', new_callable=io.StringIO)
    # def test_authentication_login_error(self, mock_request, mock_stdout):
    #     url_api_key = 'https://registerdisney.go.com/jgc/v5/client/ESPN-FANTASYLM-PROD/api-key?langPref=en-US'
    #     url_login = 'https://ha.registerdisney.go.com/jgc/v5/client/ESPN-FANTASYLM-PROD/guest/login?langPref=en-US'
    #     mock_request.post(url_api_key,  headers={'api-key':'None'}, status_code=200)
    #     mock_request.post(url_login, status_code=200, json={'error': {}})

    #     request = EspnFantasyRequests(sport='nfl', league_id=1234, year=2019)
    #     request.authentication(username='user', password='pass')
    #     self.assertEqual(mock_stdout.getvalue(), 'Authentication unsuccessful - error:{}\nRetry the authentication or continuing without private league access\n')
    
    # @requests_mock.Mocker()
    # def test_authentication_pass(self, mock_request):
    #     url_api_key = 'https://registerdisney.go.com/jgc/v5/client/ESPN-FANTASYLM-PROD/api-key?langPref=en-US'
    #     url_login = 'https://ha.registerdisney.go.com/jgc/v5/client/ESPN-FANTASYLM-PROD/guest/login?langPref=en-US'
    #     mock_request.post(url_api_key,  headers={'api-key':'None'}, status_code=200)
    #     mock_request.post(url_login, status_code=200, json={'error': None,'data': {'s2': 'cookie1', 'profile': {'swid': 'cookie2'}}})

    #     request = EspnFantasyRequests(sport='nfl', league_id=1234, year=2019)
    #     request.authentication(username='user', password='pass')
    #     self.assertEqual(request.cookies['espn_s2'], 'cookie1')
    #     self.assertEqual(request.cookies['swid'], 'cookie2')