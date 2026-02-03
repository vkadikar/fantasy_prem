
import sys
import os
import pickle
import json
import requests
from requests import Session

# Mock FantraxAPI if not importable
# But better to try importing it if it exists in a file.
# The user's code uses `from fantraxapi import FantraxAPI`? 
# or just `connect_fantrax` helper.
# I'll replicate connect_fantrax logic.

LEAGUE_ID = "de19pr8smd5cytbm" # From .env inspection

def connect_and_debug():
    session = Session()
    cookie_path = os.path.join(os.getcwd(), "fantraxloggedin.cookie")
    print(f"Loading cookie from: {cookie_path}")
    
    if os.path.exists(cookie_path):
        with open(cookie_path, "rb") as f:
            cookies = pickle.load(f)
            # print(f"Cookies found: {len(cookies)}")
            for cookie in cookies:
                session.cookies.set(cookie["name"], cookie["value"])
    else:
        print("Cookie file not found!")
        return

    # Manual request mimicking api._request("getStandings", view="SCHEDULE")
    url = "https://www.fantrax.com/fxpa/req"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
    }
    
    payload = {
        "msgs": [
            {
                "method": "getStandings",
                "data": {
                    "leagueId": LEAGUE_ID,
                    "view": "SCHEDULE"
                }
            }
        ],
        "v": "179.0.1"
    }
    
    print(f"Sending request to {url}...")
    try:
        r = session.post(f"{url}?leagueId={LEAGUE_ID}", json=payload, headers=headers)
        print(f"Response Status: {r.status_code}")
        
        if r.status_code == 200:
            resp_json = r.json()
            # print(json.dumps(resp_json, indent=2)) 
            
            # Navigate to data
            if 'responses' in resp_json and len(resp_json['responses']) > 0:
                data = resp_json['responses'][0]['data']
                print("Keys in data:", data.keys())
                
                if 'tableList' in data:
                    print(f"tableList found with length: {len(data['tableList'])}")
                    if len(data['tableList']) > 0:
                        print("First week sample keys:", data['tableList'][0].keys())
                        print("Rows in first week:", len(data['tableList'][0].get('rows', [])))
                else:
                    print("'tableList' NOT found in data. Response might differ from expectation.")
                    print("Data dump (partial):", str(data)[:500])
            else:
                print("Invalid response structure (no 'responses')")
                print(resp_json)
        else:
            print("Request failed.")
            print(r.text)
            
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    connect_and_debug()
