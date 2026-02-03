
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

def inspect_roster():
    api = connect_fantrax()
    print(f"Fetching roster for Week {CURRENT_WEEK}...")
    
    # Get a team ID first (e.g. from standings)
    standings = api._request("getStandings", view="SCHEDULE")
    team_id = "u5523KHKJ" # Dummy default
    if 'tableList' in standings:
        rows = standings['tableList'][0]['rows']
        if rows:
             # Try to get a valid team ID
             row = rows[0]['cells']
             team_id = row[0]['teamId']
             print(f"Using Team ID: {team_id}")
    
    try:
        data = api._request("getTeamRosterInfo", teamId=team_id, period=CURRENT_WEEK)
        print("Roster Data Keys:", data.keys())
        
        # Check scoring categories mapping
        if 'scoringCategoryTypes' in data:
            print("\n--- SCORING CATEGORIES ---")
            for cat in data['scoringCategoryTypes']:
                print(f"ID: {cat.get('id')} Name: {cat.get('name')} Abbr: {cat.get('shortName')}")
        
        # Check if row mapping exists
        if 'rosterDisplayMap' in data:
             print("\n--- ROSTER DISPLAY MAP ---")
             print(json.dumps(data['rosterDisplayMap'], indent=2))
        
        if 'tables' in data:
            table = data['tables'][0]
            print("\n--- HEADERS ---")
            # Headers might be under 'headers' list
            if 'headers' in table:
                for img_idx, h in enumerate(table['headers']):
                     print(f"Index {img_idx}: ID={h.get('id')} Name='{h.get('name')}' Type={h.get('type')}")
            else:
                print("No 'headers' key found in table.")

            # Print first few rows to compare
            print("\n--- ROWS (First 2) ---")
            for i, row in enumerate(table['rows'][:2]):
                print(f"\nRow {i}:")
                if 'scorer' in row:
                    print(f"  Name: {row['scorer'].get('name')}")
                if 'cells' in row:
                    for c_idx, cell in enumerate(row['cells']):
                        print(f"  Cell {c_idx}: {cell.get('content')}")
                        
    except Exception as e:
        print("Error:", e)

def search_keys(obj, key_part, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}"
            if key_part.lower() in k.lower():
                print(f"Found match at {new_path}")
            search_keys(v, key_part, new_path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            search_keys(item, key_part, f"{path}[{i}]")

def inspect_roster_deep():
    api = connect_fantrax()
    print("Fetching roster keys...")
    team_id = "mqmbxwrtmdg6mr2l"
    data = api._request("getTeamRosterInfo", teamId=team_id, period=CURRENT_WEEK)
    
    print("\n--- Header Content ---")
    if 'tables' in data and len(data['tables']) > 0:
        table = data['tables'][0]
        headers = table.get('header') or table.get('scGroupScorerHeader')
        if headers:
            print("Raw Headers List:", headers)
            # Check if headers are just IDs
            print("\n--- Mapping Headers ---")
            
            # Build Category Map
            cat_map = {}
            if 'scoringCategoryTypes' in data:
                for cat in data['scoringCategoryTypes']:
                    cat_map[str(cat.get('id'))] = cat.get('name')
            
            for i, h in enumerate(headers):
                if isinstance(h, str):
                   # Try to lookup ID
                   name = cat_map.get(h, "Unknown")
                   print(f"Col {i}: ID={h} Name='{name}'")
                elif isinstance(h, dict):
                   print(f"Col {i}: {h.get('name')} ({h.get('shortName')})")


def inspect_live_scoring():
    api = connect_fantrax()
    print("Fetching Live Scoring...")
    
    # Try getLiveScores or getStandings('LIVE')
    try:
        # Fantrax often uses getLiveScores with leagueId and period
        data = api._request("getLiveScores", period=CURRENT_WEEK)
        print("Live Scoring Keys:", data.keys())
        if 'tableList' in data:
            print("Found tableList!")
            rows = data['tableList'][0]['rows']
            if rows:
                print("First Row:", json.dumps(rows[0], indent=2))
        elif 'fantasyTeams' in data:
             print("Found fantasyTeams list")
    except Exception as e:
        print("getLiveScores error:", e)

if __name__ == "__main__":
    inspect_live_scoring()
