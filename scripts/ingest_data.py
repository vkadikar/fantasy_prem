
import pandas as pd
import numpy as np
import os
import requests
import pickle
import time
import json
from datetime import datetime
from requests import Session
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LEAGUE_ID, CURRENT_WEEK
from fantraxapi import FantraxAPI

# Constants
FANTRAX_URL = "https://www.fantrax.com/fxpa/req"
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "df_player_stats.csv")

def connect_fantrax():
    session = Session()
    cookie_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fantraxloggedin.cookie")
    if os.path.exists(cookie_path):
        with open(cookie_path, "rb") as f:
            for cookie in pickle.load(f):
                session.cookies.set(cookie["name"], cookie["value"])
    return session

def get_all_players(session):
    """Fetches the list of all players in the league."""
    print("Fetching player list...")
    df_players = pd.DataFrame()
    
    # Initialize API wrapper
    # from fantraxapi.api import request, Method
    api = FantraxAPI(LEAGUE_ID, session=session)
    
    # Initial request to see total pages
    try:
        # Use api._request instead of global request/Method
        response = api._request("getPlayerStats", statusOrTeamFilter='ALL', pageNumber=1, period=CURRENT_WEEK, view='STATS')
        data_resp = response
        total_pages = data_resp['paginatedResultSet']['totalNumPages']
        print(f"Total pages to fetch: {total_pages}")
        
        # Iterate all pages
        for i in range(1, total_pages + 1):
            try:
                # User logic casts to str
                response = api._request("getPlayerStats", statusOrTeamFilter='ALL', pageNumber=str(i), period=CURRENT_WEEK, view='STATS')

                
                rows = response.get('statsTable', [])
                if not rows:
                     print(f"Warning: No rows on page {i}")
                     continue
                
                # Processing per notebook logic
                page_data = []
                for player_data in rows:
                    data = player_data['scorer']
                    data.pop('icons', None)
                    cells = player_data['cells']
                    
                    # Extract cell data mapped by notebook
                    # Notebook: cells[2] -> next_match, cells[3] -> fpts, cells[4] -> fpts_per_game
                    # We should be careful about index bounds, but assuming consistent response structure
                    if len(cells) > 4:
                        data['next_match'] = cells[2]['content']
                        data['fpts'] = cells[3]['content']
                        data['fpts_per_game'] = cells[4]['content']
                    
                    page_data.append(data)
                
                if page_data:
                    tmp_df = pd.DataFrame(page_data)
                    df_players = pd.concat([df_players, tmp_df], ignore_index=True)
                
                print(f"Fetched page {i}/{total_pages}")
                time.sleep(0.2)
                
            except Exception as e:
                print(f"Error on page {i}: {e}")
                
    except Exception as e:
        print(f"Error initializing player fetch: {e}")
            
    return df_players

def add_season_year(date_str, start_year=2025): # Defaulting to current season start
    try:
        parsed_date = datetime.strptime(date_str, '%b %d')
        # Logic: August-Dec = start_year, Jan-May = start_year + 1
        if parsed_date.month >= 8:
            year = start_year
        else:
            year = start_year + 1
        return datetime(year, parsed_date.month, parsed_date.day)
    except:
        return None

def get_player_game_log(session, player_id, player_name, team_short_name, url_name, team_map, next_match_str):
    """Scrapes the Fantasy Game Log for a single player."""
    # Based on notebook logic
    json_data = {
        "msgs": [
            {
                "method": "getPlayerProfile",
                "data": {
                    "playerId": player_id,
                    "tab": "GAME_LOG_FANTASY",
                    "seasonId": "925"
                }
            }
        ],
        "v": "179.0.1"
    }
    
    headers = {'User-Agent': USER_AGENT}
    
    df_history = pd.DataFrame()
    
    try:
        r = session.post(f"{FANTRAX_URL}?leagueId={LEAGUE_ID}", json=json_data, headers=headers)
        resp_data = r.json()['responses'][0]['data']
        
        # 1. Historical Logs
        content = resp_data.get('sectionContent', {}).get('GAME_LOG_FANTASY', {})
        if content:
            table_header = content['tables'][0]['header']['cells']
            columns = [cell['shortName'] for cell in table_header]
            rows = content['tables'][0]['rows']
            
            data_rows = []
            for row in rows:
                row_data = {col: cell.get('content') for col, cell in zip(columns, row['cells'])}
                # Debug Check Cherki
                if player_id == '06v07':
                    print(f"DEBUG CHERKI ROW: {row_data.get('Date')} - {row_data.get('Score')}")
                data_rows.append(row_data)

                
            df_history = pd.DataFrame(data_rows)
            if not df_history.empty:
                df_history['player_id'] = player_id
                df_history['player_name'] = player_name
                df_history['Date'] = df_history['Date'].apply(lambda x: add_season_year(x, 2025))
                
        # 2. Current Week / Injury Status
        # We perform the specific profile request mainly for INJURY info now
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
        
        r_inj = session.post(f"{FANTRAX_URL}?leagueId={LEAGUE_ID}", json=injury_json, headers=headers)
        overview = r_inj.json()['responses'][0]['data']['sectionContent']['OVERVIEW']
        
        # Parse Next Match from the passed string (more robust)
        # Format: "@TOT<br/>Sun 11:30AM" or similar
        current_data = {}
        if next_match_str and isinstance(next_match_str, str):
             try:
                 clean_str = next_match_str.replace('<br/>', ' ').replace('<br>', ' ')
                 parts = clean_str.split(' ')
                 opponent_raw = parts[0]
                 
                 opp_short = opponent_raw.replace('@', '')
                 # Map check
                 for t_name, t_short in team_map.items():
                     if opp_short in t_name: 
                         opp_short = t_short
                         break
                 
                 if opponent_raw.startswith('@'):
                     opp_short = '@' + opp_short
                 
                 # Date: We don't have exact date from this string, but we need A valid date for the row.
                 # Let's use datetime.now() for placeholder logic or future date?
                 # Actually, update_data.py sorting relies on date.
                 # Let's use a dummy future date if we can't parse perfectly, or just Today?
                 # Better: Use the LAST date in history and add 7 days? 
                 # Or just use datetime.now() as it is 'Current'
                 
                 current_data = {
                     'Date': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
                     'Team': team_short_name,
                     'Opp': opp_short,
                     'Score': 'TBD',
                     'player_id': player_id,
                     'player_name': player_name
                 }
             except Exception as e:
                 if 'Gvardiol' in player_name:
                     print(f"DEBUG: Error parsing next match for Gvardiol: {e}")
                     print(f"DEBUG: next_match_str was: '{next_match_str}'")
                 pass

        # Parse Injury Info
        injury_status = 'Available'
        if 'injuryInfo' in overview:
            # Handle list of strings or list of dicts
            msgs = overview['injuryInfo'].get('injuryMsgs', [])
            if msgs:
                first_msg = msgs[0]
                if isinstance(first_msg, dict):
                    curr_inj_text = first_msg.get('comment', '')
                else:
                    curr_inj_text = str(first_msg)
            
                if 'out for next game' in curr_inj_text.lower():
                    injury_status = 'Out'
                elif 'game-time decision' in curr_inj_text.lower():
                    injury_status = 'GTD'
                elif 'out indefinitely' in curr_inj_text.lower() or 'reserved' in curr_inj_text.lower():
                    injury_status = 'Out'
        
        if current_data:
            current_data['injured'] = injury_status
            df_current = pd.DataFrame([current_data])
            df_combined = pd.concat([df_history, df_current], ignore_index=True)
            return df_combined
            
        return df_history

    except Exception as e:
        # print(f"Failed to fetch log for {player_name}: {e}")
        return df_history

def ingest_data(full_refresh=False):
    session = connect_fantrax()
    
    # 1. Get List of all players
    df_players = get_all_players(session)
    print(f"Found {len(df_players)} players.")
    
    # Save the fresh player list to ensure downstream scripts use correct IDs
    players_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "df_players.csv")
    df_players.to_csv(players_file, index=False)
    print(f"Saved player list to {players_file}")
    
    # Create Team Map
    team_map = dict(zip(df_players['teamName'].astype(str), df_players['teamShortName'].astype(str)))
    
    # Threaded fetching
    print("Starting threaded fetch of game logs...")
    all_stats_dfs = []
    skipped_players = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_player = {
            executor.submit(
                get_player_game_log, 
                session, 
                row['scorerId'], 
                row['name'],
                row.get('teamShortName', ''), 
                row.get('urlName', ''),       
                team_map,
                row.get('next_match', '') # Pass next_match
            ): row 
            for _, row in df_players.iterrows()
        }
        
        count = 0
        total = len(df_players)
        for future in as_completed(future_to_player):
            p_data = future_to_player[future]
            try:
                df_log = future.result()
                if not df_log.empty:
                    all_stats_dfs.append(df_log)
                else:
                    skipped_players.append(p_data['name'])
            except Exception as exc:
                print(f"{p_data['name']} generated an exception: {exc}")
            
            count += 1
            if count % 50 == 0:
                print(f"Processed {count}/{total} players...")

    if skipped_players:
        print(f"Skipped {len(skipped_players)} players (no logs/stats found). First 10: {skipped_players[:10]}")
        # Check if key players are skipped
        if "Djordje Petrovic" in skipped_players:
            print("WARNING: Djordje Petrovic was skipped! Check seasonId or tab name.")

    if not all_stats_dfs:
        print("No stats fetched!")
        return

    if not all_stats_dfs:
        print("No stats fetched!")
        return

    # Combine
    print("Combining data...")
    combined_df = pd.concat(all_stats_dfs, ignore_index=True)
    
    # Post-processing matches notebook
    # 1. Fill NAs
    # 2. Ensure columns match simplified internal format
    # columns are ShortName based e.g. 'G', 'A', 'KP'
    # We want to match what update_data.py expects in df_player_stats.csv
    # Based on notebook check: 'Date', 'Team', 'Opp', 'Score', 'FPts', 'Min', 'G', 'KP', ...
    
    
    # Save
    print(f"Saving {len(combined_df)} rows to {DATA_FILE}...")
    combined_df.to_csv(DATA_FILE, index=False)
    print("Ingestion complete.")
    
    return combined_df

if __name__ == "__main__":
    ingest_data(full_refresh=True)
