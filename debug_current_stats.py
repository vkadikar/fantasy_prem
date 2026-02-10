
import os
import pickle
import json
from fantraxapi import FantraxAPI
from requests import Session
from config import LEAGUE_ID, CURRENT_WEEK

# Setup API
session = Session()
cookie_path = "fantraxloggedin.cookie"
if os.path.exists(cookie_path):
    with open(cookie_path, "rb") as f:
        for cookie in pickle.load(f):
            session.cookies.set(cookie["name"], cookie["value"])

api = FantraxAPI(LEAGUE_ID, session=session)

tid = "p7p53wgimdj1ldb3" 
period = 25

try:
    print("Attempting getPlayerStats with timeframeType='BY_PERIOD'...")
    try:
        data = api._request(
            "getPlayerStats", 
            statusOrTeamFilter='ALL', 
            pageNumber=1, 
            period=period, 
            view='STATS',
            timeframeType='BY_PERIOD' 
        )
        print("Success! (getPlayerStats BY_PERIOD)")
        if 'statsTable' in data:
            rows = data['statsTable']
            print(f"Rows: {len(rows)}")
            for row in rows[:2]:
                 print(f"Scorer: {row.get('scorer', {}).get('name')}")
                 print(f"Cells: {[c.get('content') for c in row.get('cells', [])][:5]}")
    except Exception as e:
        print(f"Failed getPlayerStats BY_PERIOD: {e}")

    print("\nAttempting getTeamRosterInfo with view='GAMELOG'...")
    try:
        data = api._request("getTeamRosterInfo", teamId=tid, period=period, view='GAMELOG')
        print("Success! (getTeamRosterInfo GAMELOG)")
        if 'tables' in data:
            for table in data['tables']:
                print(f"Table: {table.get('name')}")
    except Exception as e:
        print(f"Failed getTeamRosterInfo GAMELOG: {e}")

    print("\nAttempting getTeamRosterInfo with view='SCORE'...")
    try:
         data = api._request("getTeamRosterInfo", teamId=tid, period=period, view='SCORE')
         print("Success! (getTeamRosterInfo SCORE)")
         if 'tables' in data:
             for table in data['tables']:
                 print(f"Table Name: {table.get('name', 'Unnamed')}")
                 headers = [h.get('shortName') for h in table.get('header', {}).get('cells', [])]
                 print("Headers:", headers)
                 for row in table.get('rows', [])[:2]:
                      cells = [c.get('content') for c in row.get('cells', [])]
                      print(f"Cells for {row.get('scorer', {}).get('name')}: {cells}")
    except Exception as e:
         print(f"Failed getTeamRosterInfo SCORE: {e}")




except Exception as e:
    print(f"Error: {e}")
