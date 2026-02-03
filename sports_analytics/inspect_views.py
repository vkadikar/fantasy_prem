
import os
import pickle
import json
from fantraxapi import FantraxAPI
from requests import Session
from config import LEAGUE_ID, CURRENT_WEEK

def connect_fantrax():
    session = Session()
    cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fantraxloggedin.cookie")
    if os.path.exists(cookie_path):
        with open(cookie_path, "rb") as f:
            for cookie in pickle.load(f):
                session.cookies.set(cookie["name"], cookie["value"])
    
    api = FantraxAPI(LEAGUE_ID, session=session)
    return api

def inspect_views():
    api = connect_fantrax()
    print(f"Inspecting Views for Week {CURRENT_WEEK}...")
    team_id = "mqmbxwrtmdg6mr2l" # Arnie-senal (from previous outputs)

    # 1. Check default response for view metadata
    try:
        data = api._request("getTeamRosterInfo", teamId=team_id, period=CURRENT_WEEK)
        if 'availableActiveViewType' in data:
            print("Available Active View Types:", data['availableActiveViewType'])
        if 'rosterDisplayMap' in data:
            print("Roster Display Map keys:", data['rosterDisplayMap'].keys())
    except Exception as e:
        print("Default call failed:", e)

    # 2. Try specific views
    # Common fantrax views: 'STATS', 'PERIOD', '1', '2'? 
    # Usually 'view' param logic exists.
    views_to_test = ['STATS', 'PERIOD', 'LIVE', 'GAMETRACKER', 'MATCHUP', 'start']
    
    for v in views_to_test:
        print(f"\n--- Testing View: {v} ---")
        try:
            # Try 'scoringPeriodId' instead of 'period'?
            data = api._request("getTeamRosterInfo", teamId=team_id, scoringPeriodId=CURRENT_WEEK, view=v)
            if 'tables' in data and data['tables']:
                row = data['tables'][0]['rows'][0]
                cells = [c.get('content') for c in row.get('cells', [])]
                print(f"Cells (first 5): {cells[:5]}")
        except Exception as e:
            print(f"View {v} failed: {e}")
            
    print("\n--- Testing getBoxscore ---")
    try:
        # getBoxscore usually takes a specific matchup or team/period.
        # Let's try passing leagueId (implicit), teamId, period.
        # Or maybe it requires 'matchupId'?
        # I'll try generic params first.
        data = api._request("getBoxscore", teamId=team_id, period=CURRENT_WEEK)
        print("getBoxscore keys:", data.keys())
    except Exception as e:
        print("getBoxscore failed:", e)
        
    print("\n--- Testing getLiveStats ---")
    try:
         data = api._request("getLiveStats", teamId=team_id, period=CURRENT_WEEK)
         print("getLiveStats keys:", data.keys())
    except Exception as e:
         print("getLiveStats failed:", e)

if __name__ == "__main__":
    inspect_views()
