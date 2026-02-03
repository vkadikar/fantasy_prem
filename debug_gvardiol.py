
import requests
import json
import os
import sys
from requests import Session
import pickle

# Setup paths (hacky copy from ingest_data)
LEAGUE_ID = "4e70q9ull5621415" # Hardcoded from config check
FANTRAX_URL = "https://www.fantrax.com/fxpa/req"
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'

def connect_fantrax():
    session = Session()
    cookie_path = "fantraxloggedin.cookie"
    if os.path.exists(cookie_path):
        with open(cookie_path, "rb") as f:
            for cookie in pickle.load(f):
                session.cookies.set(cookie["name"], cookie["value"])
    return session

def debug_player(player_id, url_name):
    session = connect_fantrax()
    
    injury_json = {
        "msgs": [
            {
                "method": "getPlayerProfile",
                "data": {
                    "playerId": player_id,
                }
            }
        ],
        "refUrl": f"https://www.fantrax.com/player/{player_id}/{LEAGUE_ID}/{url_name}",
        "v": "179.0.1"
    }
    
    headers = {'User-Agent': USER_AGENT}
    
    print(f"Fetching profile for {player_id} ({url_name})...")
    r = session.post(f"{FANTRAX_URL}?leagueId={LEAGUE_ID}", json=injury_json, headers=headers)
    
    try:
        data = r.json()
        overview = data['responses'][0]['data']['sectionContent']['OVERVIEW']
        
        print("\n=== RAW INJURY INFO ===")
        if 'injuryInfo' in overview:
            print(json.dumps(overview['injuryInfo'], indent=2))
        else:
            print("No 'injuryInfo' key found in OVERVIEW.")
            
        print("\n=== RAW NEXT MATCH INFO ===")
        if 'tables' in overview and len(overview['tables']) > 3:
             print(json.dumps(overview['tables'][3], indent=2))
             
    except Exception as e:
        print(f"Error: {e}")
        print(r.text[:500])

if __name__ == "__main__":
    debug_player("06ex4", "josko-gvardiol")
