
import pandas as pd
import json
import os

def debug_lookup():
    print("--- Debugging Player ID Lookup ---")
    
    # 1. Load Players CSV (Agent Logic)
    players_file = 'df_players.csv'
    players = {}
    if os.path.exists(players_file):
        try:
            df_p = pd.read_csv(players_file)
            print(f"Loaded {len(df_p)} rows from df_players.csv")
            
            # Check column names
            print(f"Columns: {df_p.columns.tolist()}")
            
            if 'scorerId' in df_p.columns and 'name' in df_p.columns:
                df_p['scorerId'] = df_p['scorerId'].astype(str)
                players = dict(zip(df_p['scorerId'], df_p['name']))
                print(f"Created players dict with {len(players)} entries.")
                
                # Sample some keys
                print(f"Sample keys: {list(players.keys())[:5]}")
            else:
                print("MISSING COLUMNS 'scorerId' or 'name'")
        except Exception as e:
            print(f"Error loading players CSV: {e}")
    else:
        print(f"File not found: {players_file}")
        
    # 2. Load Roster Data
    roster_file = 'dashboard/data/roster_cache.json'
    if os.path.exists(roster_file):
        with open(roster_file, 'r') as f:
            roster_data = json.load(f)
            
        print(f"Loaded roster_data. Weeks available: {list(roster_data.keys())}")
        
        target_week = "24"
        shawn_team_id = "pmzfm9z8mdg3f44o"
        
        week_data = roster_data.get(target_week, {})
        if not week_data:
            print(f"WARNING: No data for Week {target_week}")
            # Try finding latest week
            weeks = sorted([int(k) for k in roster_data.keys()])
            if weeks:
                target_week = str(weeks[-1])
                print(f"Falling back to latest week: {target_week}")
                week_data = roster_data.get(target_week, {})

        team_roster = week_data.get(shawn_team_id, [])
        print(f"Found {len(team_roster)} players for Shawn's Team (Week {target_week})")
        
        for p in team_roster:
            pid = p['id']
            name = players.get(pid, "UNKNOWN")
            print(f"ID: {pid} -> Name: {name}")
            
    else:
        print(f"File not found: {roster_file}")

if __name__ == "__main__":
    debug_lookup()
