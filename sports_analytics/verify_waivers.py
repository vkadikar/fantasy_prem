
import sys
import os
import time
import json
import pandas as pd
from datetime import datetime

# Add verified path
sys.path.insert(0, '/Users/varunkadikar/Desktop/personal_projects/Antigravity/sports_analytics')

# Mock config
import config
from scripts.update_data import fetch_current_rosters, connect_fantrax, get_waivers

def test_waiver_logic():
    print("Connecting to API...")
    api = connect_fantrax()
    
    print(f"Fetching rosters for Week {config.CURRENT_WEEK}...")
    rostered_ids = fetch_current_rosters(api)
    print(f"Found {len(rostered_ids)} rostered player IDs.")
    
    # Load stats to simulate get_waivers
    try:
        base_dir = '/Users/varunkadikar/Desktop/personal_projects/Antigravity/sports_analytics'
        df_stats = pd.read_csv(os.path.join(base_dir, "df_player_stats.csv"))
        # We need a dummy processed stats df or just mock it to test filtering
        # Let's just test if specific known owned players are in rostered_ids
        
        # Example: Haaland (usually owned). We don't know his ID easily without looking it up, but let's check count.
        # If len is 0, it's broken.
        if len(rostered_ids) == 0:
            print("ERROR: No rostered players found. Logic is broken.")
        else:
            print("SUCCESS: Rosters fetched.")
            
        print("Done.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_waiver_logic()
