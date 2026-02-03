
import os
import pickle
import json
from fantraxapi import FantraxAPI
from requests import Session
from config import LEAGUE_ID

def connect_fantrax():
    session = Session()
    cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fantraxloggedin.cookie")
    if os.path.exists(cookie_path):
        with open(cookie_path, "rb") as f:
            for cookie in pickle.load(f):
                session.cookies.set(cookie["name"], cookie["value"])
    
    api = FantraxAPI(LEAGUE_ID, session=session)
    return api

def inspect_teams():
    api = connect_fantrax()
    print("Fetching league info...")
    
    # Try different views/endpoints
    try:
        data = api._request("getStandings", view="SCHEDULE")
        if 'tableList' in data:
            row = data['tableList'][0]['rows'][0]
            print("Sample Schedule Row:", json.dumps(row, indent=2))
    except Exception as e:
        print("getStandings error:", e)

    try:
        # Often manager info is in getLeagueStandings or similar
        data = api._request("getStandings", view="Classic")
        print("Sample Classic Standings Data (Truncated):")
        # Just look for team/manager keys
        print(json.dumps(data, indent=2)[:2000])
    except Exception as e:
        print("Classic view error:", e)

if __name__ == "__main__":
    inspect_teams()
