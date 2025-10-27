![](https://github.com/cwendt94/espn-api/workflows/Espn%20API/badge.svg)
![](https://github.com/cwendt94/espn-api/workflows/Espn%20API%20Integration%20Test/badge.svg) [![codecov](https://codecov.io/gh/cwendt94/espn-api/branch/master/graphs/badge.svg)](https://codecov.io/gh/cwendt94/espn-api) [![Join the chat at https://gitter.im/ff-espn-api/community](https://badges.gitter.im/ff-espn-api/community.svg)](https://gitter.im/ff-espn-api/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge) [![PyPI version](https://badge.fury.io/py/espn-api.svg)](https://badge.fury.io/py/espn-api)<a target="_blank" href="https://www.python.org/downloads/" title="Python version"><img src="https://img.shields.io/badge/python-%3E=_3.8-teal.svg"></a>


## ESPN API
This package uses ESPN's Fantasy API to extract data from any public or private league for **Fantasy Football and Basketball (NHL, MLB, and WNBA are in development)**.  
Please feel free to make suggestions, bug reports, and pull request for features or fixes!

This package was inspired and based off of [rbarton65/espnff](https://github.com/rbarton65/espnff).

## Installing
### Note
The difference in setup.py and requirements is in the test packages. If you are in python version >=3.9 then please use the requirements and pytest as nosetests is deprecated.

With Git & Setup.py (Not recommended for Python >=3.9):
```
git clone https://github.com/cwendt94/espn-api
cd espn-api
python3 setup.py install
```

with Git and Requirements.txt (Recommended for python >=3.9)
```
git clone https://github.com/cwendt94/espn-api
cd espn-api
python -m venv myenv
myenv\Scripts\activate.bat
pip install -r requirementsV2.txt
```

With pip:
```
pip install espn_api
```


### Run Tests
with nosetests (Not recommended for Python >=3.9):
```
python3 setup.py nosetests
```

with pytest (Recommended for Python >=3.9)
```
pytest
```




## Usage
### [For Getting Started and API details head over to the Wiki!](https://github.com/cwendt94/espn-api/wiki)
```python
# Football API
from espn_api.football import League
# Basketball API
from espn_api.basketball import League
# Hockey API
from espn_api.hockey import League
# Baseball API
from espn_api.baseball import League
# Init
league = League(league_id=222, year=2019)
```

### Windows NBA Watchlist App

The repository includes an example Tkinter desktop application that can be
run on Windows (or any OS with Python 3) to track NBA fantasy player stats,
view schedules, and maintain a customizable watchlist.

```bash
python examples/nba_watchlist_app.py
```

The app supports authenticated private leagues by providing `espn_s2` and
`SWID` cookies within the UI and offers quick roster imports for any team in
the league.

### Syncing an ESPN Watchlist

Private watchlists require the authenticated user's ESPN cookies. Follow these
steps to mirror your online watchlist inside the desktop application:

1. **Capture your ESPN cookies.** Sign in to fantasy.espn.com, open your
   browser's developer tools, and copy the values of the `SWID` (including the
   braces) and `espn_s2` cookies. Keep them secret—they grant access to your
   private league data.
2. **Launch the watchlist app.** From this repository, run
   `python examples/nba_watchlist_app.py` (or double-click the file on Windows)
   to open the Tkinter UI.
3. **Enter your league credentials.** In the **League Connection** panel,
   provide the league ID and season year for the league you want to sync, then
   paste your `espn_s2` and `SWID` cookie values into the optional fields.
4. **Load the league.** Click **Load League**. If the cookies are valid the
   app will fetch private data such as team rosters and your saved watchlist.
5. **Sync the watchlist.** Choose your fantasy team from the **League Teams**
   drop-down and click **Import Team Watchlist**. You can refresh the data at
   any time via the **Refresh Watchlist** button in the **Watchlist Controls**
   section.

For custom scripts you can access the same data directly through the API.
Instantiate a `League` with your cookies and call `watchlist_players()`:

```python
from espn_api.basketball import League

league = League(
    league_id=58624887,
    year=2024,
    espn_s2='YOUR_ESPNS2_TOKEN',
    swid='{YOUR-SWID}',
)

players = league.watchlist_players()
```

For NBA and WNBA leagues the API sometimes publishes the watchlist under the
following calendar year. The `watchlist_players` helper automatically checks the
next season when necessary, or you can pass explicit `season_ids` if you prefer
to control the lookup manually.


## [Discussions](https://github.com/cwendt94/espn-api/discussions) (new)
If you have any questions about the package, ESPN API data, or want to talk about a feature please start a [discussion](https://github.com/cwendt94/espn-api/discussions)! 


## Issue Reporting
If you find a bug follow the steps below for reporting.

1. Open a [new issue](https://github.com/cwendt94/espn-api/issues) with a brief description of the bug for the title. In the title also add which sport (Football or Basketball)

2. Run the application in debug mode to view ESPN API request's and response's
    ```python
    # ... import statement above
    league = League(league_id=1245, year=2019, debug=True)
    ```
    The application will print all requests and the response from ESPN's API in the console. I would suggest piping the console output to a text file as it will be a lot of data.

3. Find the last log before the crash and copy it in the issue descrption with the line number of the crash or possible bug.

4. Submit the new issue!

I will try to comment on the issue as soon as possible with my thoughts and possible fix!
