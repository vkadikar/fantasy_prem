
import os
import pickle
import json
import pandas as pd
from requests import Session
from config import LEAGUE_ID

# Constants
FANTRAX_URL = "https://www.fantrax.com/fxpa/req"
USER_AGENT = "Mozilla/5.0"

# Setup Session
session = Session()
cookie_path = "fantraxloggedin.cookie"
if os.path.exists(cookie_path):
    with open(cookie_path, "rb") as f:
        for cookie in pickle.load(f):
            session.cookies.set(cookie["name"], cookie["value"])

pid = "06znb" # Robin Roefs
json_data = {
    "msgs": [
        {
            "method": "getPlayerProfile",
            "data": {
                "playerId": pid,
                "tab": "GAME_LOG_FANTASY",
                "seasonId": "925" # From ingest_data.py
            }
        }
    ],
    "v": "179.0.1"
}

headers = {'User-Agent': USER_AGENT}

try:
    print(f"Fetching Game Log for {pid}...")
    r = session.post(f"{FANTRAX_URL}?leagueId={LEAGUE_ID}", json=json_data, headers=headers)
    resp_data = r.json()['responses'][0]['data']
    
    content = resp_data.get('sectionContent', {}).get('GAME_LOG_FANTASY', {})
    if content:
        table_header = content['tables'][0]['header']['cells']
        columns = [cell['shortName'] for cell in table_header]
        print(f"Columns: {columns}")
        
        rows = content['tables'][0]['rows']
        
        print(f"Found {len(rows)} game log entries.")
        # Print top 5 rows
        for row in rows[:5]:
             row_data = {col: cell.get('content') for col, cell in zip(columns, row['cells'])}
             print(row_data)
             
    else:
        print("No content in GAME_LOG_FANTASY")

except Exception as e:
    print(f"Error: {e}")
