
import pandas as pd
import numpy as np
import json
import os
import requests
import pickle
import glob
from fantraxapi import FantraxAPI
from requests import Session
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
import warnings
import warnings
warnings.simplefilter('ignore')

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- CONFIG ---
from config import CURRENT_WEEK, LEAGUE_ID, DATA_DIR

# IMPORTS
import sys
import argparse
from scripts.ingest_data import ingest_data

# IMPORTANT: CURRENT_WEEK, LEAGUE_ID, and DATA_DIR are configured in config.py
# which loads from .env file


# --- SCORING RULES ---
fantasy_scoring_rules_goalkeeper = {
    "AER": 1, "AT": 7, "CS": 8, "DIS": -0.5, "GAO": -2, "G": 10,
    "HCS": 1, "Int": 1, "OG": -5, "PKS": 8, "RC": -7, "SOT": 2,
    "Sm": 1, "CoS": 1, "CLR": 0.25, "KP": 2, "Sv": 2, "TkW": 1, "YC": -2
}
fantasy_scoring_rules_defender = {
    "ACNC": 1, "AER": 1, "AT": 7, "BS": 1, "CS": 6, "DIS": -0.5,
    "GAO": -2, "G": 10, "Int": 1, "OG": -5, "PKD": 2, "PKM": -4,
    "RC": -7, "SOT": 2, "CoS": 1, "CLR": 0.25, "KP": 2, "TkW": 1, "YC": -2
}
fantasy_scoring_rules_midfield = {
    "ACNC": 1, "AER": 0.5, "AT": 6, "BS": 1, "CS": 1, "DIS": -0.5,
    "G": 9, "Int": 1, "OG": -5, "PKD": 2, "PKM": -4, "RC": -7,
    "SOT": 2, "CoS": 1, "KP": 2, "TkW": 1, "YC": -2
}
fantasy_scoring_rules_forward = {
    "ACNC": 1, "AER": 0.5, "AT": 6, "BS": 1, "DIS": -0.5, "G": 9,
    "Int": 1, "OG": -5, "PKD": 2, "PKM": -4, "RC": -7, "SOT": 2,
    "CoS": 1, "KP": 2, "TkW": 1, "YC": -2
}

fantasy_scoring_rules = pd.DataFrame({
    'G': fantasy_scoring_rules_goalkeeper, 
    'D': fantasy_scoring_rules_defender, 
    'M': fantasy_scoring_rules_midfield, 
    'F': fantasy_scoring_rules_forward
}).fillna(0).T

def get_fantasy_score(row):
    stats = fantasy_scoring_rules.columns.tolist()
    score = 0
    # Map position names if necessary, assuming 'G','D','M','F' inputs
    pos = row.get('position', 'M') # Default to M if missing
    
    # Handle potential discrepancies in position naming
    if pos not in ['G', 'D', 'M', 'F']:
        # simplistic mapping
        if 'Goalkeeper' in str(pos): pos = 'G'
        elif 'Defender' in str(pos): pos = 'D'
        elif 'Midfielder' in str(pos): pos = 'M'
        elif 'Forward' in str(pos): pos = 'F'
        else: pos = 'M' # Fallback

    if pos not in fantasy_scoring_rules.index:
        return 0

    for stat in stats:
        # Check lowercase stat in row keys
        if stat.lower() in row:
            val = row[stat.lower()]
            # Ensure value is numeric
            try:
                val = float(val)
            except:
                val = 0
            score += float(fantasy_scoring_rules.loc[pos, stat]) * val
    return score

def connect_fantrax():
    session = Session()
    cookie_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fantraxloggedin.cookie")
    if os.path.exists(cookie_path):
        with open(cookie_path, "rb") as f:
            for cookie in pickle.load(f):
                session.cookies.set(cookie["name"], cookie["value"])
    
    api = FantraxAPI(LEAGUE_ID, session=session)
    return api


# from fantraxapi.api import request, Method

def get_team_details(api):
    print("Fetching team details...")
    try:
        # Use classic view to get fantasyTeamInfo
        data = api._request("getStandings", view="Classic")
        details = {}
        if 'fantasyTeamInfo' in data:
            for tid, info in data['fantasyTeamInfo'].items():
                # User-provided manager mapping
                TEAM_TO_MANAGER = {
                    "Arnie-senal": "Arnav (Arnie)",
                    "Toadenham Frogspur": "Ari",
                    "WayneRooney10": "Danny",
                    "hdiamondpott": "Henry",
                    "Estimated Profit": "Isaac",
                    "Traderjoe18": "Joseph (Joe)",
                    "Wallalujah FC": "Nilay",
                    "FC Purulona": "Purvaansh (Puru)",
                    "Smip Estonian": "Shawn",
                    "sduvuuru": "Subba",
                    "Cold FC": "Suda",
                    "FC VAR": "Varun",
                    "youngmoon": "Young",
                    "Point Loma Parrots": "Zach"
                }
                
                team_name = info.get('name', 'Unknown')
                details[tid] = {
                    'team': team_name,
                    'manager': TEAM_TO_MANAGER.get(team_name, info.get('shortName', 'Unknown')),
                    'logo': info.get('logoUrl512', '')
                }
        return details
    except Exception as e:
        print(f"Error fetching team details: {e}")
        return {}

def get_matchups(api):
    print("Fetching matchups...")
    matchups = pd.DataFrame()
    try:
        standings_data = api._request("getStandings", view="SCHEDULE")
        
        matchup_list = []
        
        for week, data in enumerate(standings_data['tableList']):
            week_num = week + 1
            # print(f"Processing Week {week_num} with {len(data['rows'])} games")
            for matchup in data['rows']:
                matchup = matchup['cells']
                
                def safe_float(val):
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return 0.0

                home_team = matchup[0]['content']
                home_team_id = matchup[0]['teamId']
                home_score = safe_float(matchup[1]['content'])
                away_team = matchup[2]['content']
                away_team_id = matchup[2]['teamId']
                away_score = safe_float(matchup[3]['content'])
                
                matchup_obj = {
                    'matchupId': f"{week_num}_{home_team_id}_{away_team_id}",
                    'week': week_num,
                    'home_team': home_team,
                    'home_team_id': home_team_id,
                    'home_score': home_score,
                    'away_team': away_team,
                    'away_team_id': away_team_id,
                    'away_score': away_score
                }
                matchup_list.append(matchup_obj)
                
                tmp_df = pd.DataFrame({
                    'matchupId': [matchup_obj['matchupId'], matchup_obj['matchupId']],
                    'week': [week_num, week_num],
                    'team': [home_team, away_team],
                    'team_id': [home_team_id, away_team_id],
                    'score': [home_score, away_score],
                    'opponent': [away_team, home_team],
                    'opponent_score': [away_score, home_score],
                    'is_home': [1, 0]
                })
                matchups = pd.concat([matchups, tmp_df])
                
        matchups = matchups.reset_index(drop=True)
        return matchups, matchup_list
    except Exception as e:
        print(f"Error fetching matchups: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(), []

def calculate_standings(matchups):
    if matchups.empty: return pd.DataFrame()
    print("Calculating standings...")
    # Assume finished weeks are everything before current, or standard logic
    # Using specific week logic 21 from notebook context
    completed_matchups = matchups[matchups.week < CURRENT_WEEK].copy()
    
    completed_matchups['result'] = np.where(completed_matchups.score > completed_matchups.opponent_score, 'W', 
                                   np.where(completed_matchups.score < completed_matchups.opponent_score, 'L', 'D'))
    
    completed_matchups['win'] = (completed_matchups.result == 'W').astype(int)
    completed_matchups['draw'] = (completed_matchups.result == 'D').astype(int)
    completed_matchups['loss'] = (completed_matchups.result == 'L').astype(int)
    completed_matchups['points'] = completed_matchups['win'] * 3 + completed_matchups['draw'] * 1
    
    standings = completed_matchups.groupby('team').agg({
        'win': 'sum',
        'draw': 'sum',
        'loss': 'sum',
        'points': 'sum',
        'score': 'sum',
        'opponent_score': 'sum'
    }).reset_index()
    
    standings['record'] = standings.apply(lambda x: f"{int(x.win)}-{int(x.draw)}-{int(x.loss)}", axis=1)
    standings = standings.rename(columns={'score': 'fpts_for', 'opponent_score': 'fpts_against'})
    standings = standings.sort_values(['points', 'fpts_for'], ascending=False).reset_index(drop=True)
    standings['rank'] = standings.index + 1
    
    return standings

def calculate_median_standings(matchups):
    if matchups.empty: return pd.DataFrame()
    print("Calculating median standings...")
    completed_matchups = matchups[matchups.week < CURRENT_WEEK]
    
    weekly_medians = completed_matchups.groupby('week').score.median()
    completed_matchups['median_score'] = completed_matchups.week.apply(lambda x: weekly_medians.get(x, 0))
    
    # H2H Points
    completed_matchups['h2h_points'] = np.where(completed_matchups.score > completed_matchups.opponent_score, 3,
                                       np.where(completed_matchups.score == completed_matchups.opponent_score, 1, 0))
    
    # Median Points
    completed_matchups['median_points'] = np.where(completed_matchups.score > completed_matchups.median_score, 3,
                                          np.where(completed_matchups.score == completed_matchups.median_score, 1, 0))
    
    completed_matchups['total_points'] = completed_matchups['h2h_points'] + completed_matchups['median_points']
    
    standings = completed_matchups.groupby('team').agg({
        'total_points': 'sum',
        'score': 'sum'
    }).reset_index().rename(columns={'score': 'fpts_for', 'total_points': 'points'})
    
    standings = standings.sort_values(['points', 'fpts_for'], ascending=False).reset_index(drop=True)
    standings['rank'] = standings.index + 1
    
    return standings


def solve_best_lineup(players_df):
    # Logic matching notebook:
    # Base: 1 G, 3 D, 2 M, 1 F
    # Flex: 4 spots.
    # Constraints: Max 1 G, 5 D, 5 M, 3 F. Total 11.
    
    if players_df.empty: return 0
    
    # Get scores dict or list
    # Use 0 if not enough players to satisfy base?
    
    # Helper to safely get top N
    def get_top(df, pos, n):
        scores = sorted(df[df.position == pos].fpts.tolist())
        return scores[-n:] if n > 0 else []
        
    def get_remaining(df, pos, used_scores):
        # This is tricky if duplicate scores.
        # Better to work with indices or object IDs.
        # But simpler: sort all, take everything NOT in top N.
        scores = sorted(df[df.position == pos].fpts.tolist())
        # Remove used_scores from end
        for s in used_scores:
            if scores and scores[-1] == s:
                scores.pop()
        return scores

    # 1. Select Base
    g_scores = sorted(players_df[players_df.position == 'G'].fpts.tolist())
    d_scores = sorted(players_df[players_df.position == 'D'].fpts.tolist())
    m_scores = sorted(players_df[players_df.position == 'M'].fpts.tolist())
    f_scores = sorted(players_df[players_df.position == 'F'].fpts.tolist())
    
    top_g = g_scores[-1:] # Max 1
    top_d = d_scores[-3:] # Min 3
    top_m = m_scores[-2:] # Min 2
    top_f = f_scores[-1:] # Min 1
    
    # Update remaining
    g_rem = g_scores[:-1]
    d_rem = d_scores[:-3]
    m_rem = m_scores[:-2]
    f_rem = f_scores[:-1]
    
    # 2. Fill Flex (4 spots)
    for _ in range(4):
        # Check constraints
        can_add_d = len(top_d) < 5 and len(d_rem) > 0
        can_add_m = len(top_m) < 5 and len(m_rem) > 0
        can_add_f = len(top_f) < 3 and len(f_rem) > 0
        
        candidates = []
        if can_add_d: candidates.append(('D', d_rem[-1]))
        if can_add_m: candidates.append(('M', m_rem[-1]))
        if can_add_f: candidates.append(('F', f_rem[-1]))
        
        if not candidates: break
        
        # Pick max
        best_pos, best_score = max(candidates, key=lambda x: x[1])
        
        if best_pos == 'D':
            top_d.append(best_score)
            d_rem.pop()
        elif best_pos == 'M':
            top_m.append(best_score)
            m_rem.pop()
        elif best_pos == 'F':
            top_f.append(best_score)
            f_rem.pop()
            
    return sum(top_g) + sum(top_d) + sum(top_m) + sum(top_f)

def calculate_optimal_standings(api, matchups, df_stats, df_players):
    print(f"DEBUG: Entering calculate_optimal_standings. Matchups count: {len(matchups)}")
    if matchups.empty: 
        print("DEBUG: Matchups empty, returning early.")
        return pd.DataFrame(), pd.DataFrame() # Return two DFs as expected
    
    # 1. Fetch/Load Rosters for all completed weeks
    # Cache to disk to speed up
    cache_path = os.path.join(DATA_DIR, "roster_cache.json")
    print(f"DEBUG: Roster cache path: {cache_path}")
    roster_cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                roster_cache = json.load(f)
        except: pass
        
    # Stats lookup: (player_id, week) -> fpts
    # df_stats needs 'matchweek' relative to season start
    # We assume preprocess_player_stats ran? No, we need raw or preprocessed stats.
    # Let's run a quick preprocess specific for this or reuse.
    # We need actual points for past weeks.
    
    # Re-run basic preprocessing on stats to get matchweek/season correct if not passed in
    # Actually df_stats passed here is RAW from CSV usually.
    # Let's assume we do a mini-process to get matchweek/player_id/fpts
    
    # ... reused logic ...
    # Quick fix: assume df_stats has 'season', 'date' etc. and we need 'matchweek'.
    # We will trust the helper below to prepare stats for lookup.
    
    stats_df = preprocess_player_stats(df_stats.copy(), df_players.copy(), matchups)
    stats_df['player_id'] = stats_df['player_id'].astype(str)
    
    # Create lookup dict
    # Key: f"{player_id}_{matchweek}" -> fpts
    stats_lookup = {}
    for _, row in stats_df.iterrows():
        key = f"{row['player_id']}_{row['matchweek']}"
        stats_lookup[key] = stats_lookup.get(key, 0) + row['fpts']

    # Iterate weeks
    # Ensure weeks are standard python ints
    # INCLUDE CURRENT WEEK (for Roster Cache purposes, even if optimal score is 0)
    completed_weeks = [int(w) for w in sorted(matchups[matchups.week <= CURRENT_WEEK].week.unique())]
    
    optimal_results = [] # {week, team, score}
    
    team_ids = matchups[matchups.week <= CURRENT_WEEK].team_id.unique()
    
    for week in completed_weeks:
        week_str = str(week)
        if week_str not in roster_cache:
            roster_cache[week_str] = {}
            
        for tid in team_ids:
            tid_str = str(tid)
            
            # Check cache
            if tid_str in roster_cache[week_str]:
                team_roster = roster_cache[week_str][tid_str]
            else:
                # Fetch
                try:
                    # Fantrax period is usually week number
                    # Careful with period ID mapping, assume 1-to-1 for now
                    # print(f"Fetching roster for Team {tid}, Week {week}...")
                    roster_data = api._request("getTeamRosterInfo", teamId=tid, period=week)
                    # Parse simplified list of player IDs and Positions
                    parsed_roster = []
                    if 'tables' in roster_data and isinstance(roster_data['tables'], list):
                        for table in roster_data['tables']:
                            for row in table['rows']:
                                scorer = row.get('scorer', {})
                                pid = str(scorer.get('scorerId', ''))
                                pos = scorer.get('posShortNames', 'M')
                                status_id = row.get('statusId', 1) # 1=Active, 2=Reserve
                                status_str = 'Starter' if str(status_id) == '1' else 'Bench'
                                
                                if not pid: continue
                                parsed_roster.append({'id': pid, 'pos': pos, 'status': status_str})
                    


                    roster_cache[week_str][tid_str] = parsed_roster
                    team_roster = parsed_roster
                except Exception as e:
                    print(f"Error fetching roster {tid} week {week}: {e}")
                    team_roster = []
            
            # Ensure sorted (Fixes unsorted cache and enforces order)
            pos_map = {'G': 0, 'D': 1, 'M': 2, 'F': 3}
            team_roster.sort(key=lambda x: (
                0 if x.get('status') == 'Starter' else 1, 
                pos_map.get(x.get('pos'), 99)
            ))

            # Calculate Best Lineup Score for this team/week
            # Map roster to stats
            team_week_players = []
            for p in team_roster:
                pid = p['id']
                if not pid: continue
                # Lookup score
                key = f"{pid}_{week}"
                fpts = stats_lookup.get(key, 0)
                
                team_week_players.append({'player_id': pid, 'position': p['pos'], 'fpts': fpts})
            
            best_score = solve_best_lineup(pd.DataFrame(team_week_players))
            optimal_results.append({'week': week, 'team_id': tid, 'optimal_score': best_score})
            
    # Save cache
    with open(cache_path, 'w') as f:
        json.dump(roster_cache, f)
        
    # Build Optimal Matchups/Standings
    # Merge optimal scores back to matchups
    opt_df = pd.DataFrame(optimal_results)
    
    # We need to map team_id back to team name or join with matchups
    # Matchups has team_id
    
    matchups_opt = matchups[matchups.week < CURRENT_WEEK].copy()
    
    # Join home
    matchups_opt = pd.merge(matchups_opt, opt_df, left_on=['week', 'team_id'], right_on=['week', 'team_id'], how='left').rename(columns={'optimal_score': 'home_opt'})
    # Join away? Wait, the matchups df structure is long: team, opponent.
    # So for each row, 'score' is that team's score.
    
    # Simpler: just replace 'score' with 'optimal_score' in the long format DataFrame
    matchups_opt = pd.merge(matchups_opt, opt_df, left_on=['week', 'team_id'], right_on=['week', 'team_id'], how='left')
    matchups_opt['score'] = matchups_opt['optimal_score'].fillna(0) # Replace actual with optimal
    
    # Now we need opponent optimal score. 
    # Matchups df has 'opponent' name but not ID directly in row easily unless we look it up.
    # Actually invalid approach for opponent.
    # Better: Re-calculate standings from scratch using the new 'score' column.
    
    # We need 'opponent_score' to also update.
    # Since matchups is 2 rows per game (A vs B, B vs A), 
    # if we update 'score' for A and 'score' for B, we need to refresh 'opponent_score'.
    
    # Self-join to get opp score
    # matchups_opt has 'week', 'matchupId', 'team', 'score' (updated)
    # We can group by matchupId and propagate?
    # Or just use the fact it's symmetric?
    
    # Let's re-build opponent_score
    # matchups df has 'opponent' column (team name).
    # We have 'team' + 'week' -> 'score'.
    # We need 'opponent' + 'week' -> 'score'.
    
    # Create lookup map (team, week) -> opt_score
    score_map = matchups_opt.set_index(['team', 'week'])['score'].to_dict()
    
    matchups_opt['opponent_score'] = matchups_opt.apply(lambda row: score_map.get((row['opponent'], row['week']), 0), axis=1)
    
    # Now Calculate Standard Standings on this new data
    opt_standings = calculate_standings(matchups_opt)
    
    # Return:
    # 1. Standings DF (for Current Standings display)
    # 2. Raw Optimal Results DF (for merging into matchups history)
    return opt_standings, opt_df

def calculate_median_scores_history(matchups):
    """Calculates median thresholds and results for all historical weeks."""
    if matchups.empty: return {}
    
    print("Calculating median history...")
    completed_matchups = matchups[matchups.week < CURRENT_WEEK].copy()
    
    # Dict to return: { (team_id, week) : { 'median_score': float, 'beat_median': bool, 'median_win': int } }
    
    weekly_medians = completed_matchups.groupby('week').score.median()
    results = {}
    
    # Iterate all rows (2 rows per game in completed_matchups usually?)
    # completed_matchups comes from get_matchups which returns A vs B and B vs A?
    # No, get_matchups returns standard list of dicts. We converted to DF.
    # The DF likely has 1 row per game if raw, or 2 if expanded.
    # Let's assume standard 'long' format (Team, Score, Week).
    
    for _, row in completed_matchups.iterrows():
        week = row['week']
        team_id = str(row['team_id']) # Ensure string ID
        score = row['score']
        
        median_val = weekly_medians.get(week, 0)
        beat_median = score > median_val
        median_win = 1 if beat_median else (0.5 if score == median_val else 0) # Assumes 1pt for win, 0.5 for draw vs median? Or just W/L?
        # Standard Median Scoring usually: Top half gets a Win.
        
        results[(team_id, week)] = {
            'median_value': median_val,
            'beat_median': beat_median,
            'median_points': 1 if beat_median else 0 # Simple addition to standard points
        }
        
    return results

def calculate_median_standings(matchups):
    """Calculates current median standings table."""
    if matchups.empty: return pd.DataFrame()
    print("Calculating median standings...")
    completed_matchups = matchups[matchups.week < CURRENT_WEEK].copy()
    
    weekly_medians = completed_matchups.groupby('week').score.median()
    completed_matchups['median_score'] = completed_matchups.week.apply(lambda x: weekly_medians.get(x, 0))
    
    completed_matchups['result_med'] = np.where(completed_matchups.score > completed_matchups.median_score, 'W',
                                         np.where(completed_matchups.score == completed_matchups.median_score, 'D', 'L'))
    
    completed_matchups['win'] = (completed_matchups.result_med == 'W').astype(int)
    completed_matchups['draw'] = (completed_matchups.result_med == 'D').astype(int)
    completed_matchups['loss'] = (completed_matchups.result_med == 'L').astype(int)
    
    # PURE POINTS
    completed_matchups['points'] = completed_matchups['win'] * 3 + completed_matchups['draw'] * 1
    
    standings = completed_matchups.groupby('team').agg({
        'win': 'sum',
        'draw': 'sum',
        'loss': 'sum',
        'points': 'sum',
        'score': 'sum'
    }).reset_index().rename(columns={'score': 'fpts_for'})
    
    standings['record'] = standings.apply(lambda x: f"{int(x.win)}-{int(x.draw)}-{int(x.loss)}", axis=1)
    standings = standings.sort_values(['points', 'fpts_for'], ascending=False).reset_index(drop=True)
    standings['rank'] = standings.index + 1
    
    return standings

def preprocess_player_stats(df_stats, df_players, df_matchups=None):
    if df_stats.empty: return pd.DataFrame()
    print("Pre-processing player stats (Strict Notebook Logic)...")
    
    # Copy to avoid SettingWithCopy
    df = df_stats.copy()
    
    # 1. Lowercase cols
    df.columns = [c.lower() for c in df.columns]
    
    # 2. Basic Clean
    if 'position' in df.columns:
        df = df.drop(columns=['position'])
        
    df_players['scorerId'] = df_players['scorerId'].astype(str)
    df_stats['player_id'] = df_stats['player_id'].astype(str)
    
    # 3. Merge position
    # Use 'df' (which has lowercased columns) instead of 'df_stats'
    df = pd.merge(df, df_players[['scorerId', 'posShortNames']], left_on='player_id', right_on='scorerId', how='left')
    df = df.rename(columns={'posShortNames': 'position'})
    
    # DROP existing calculated columns to avoid merge conflicts (matchweek_x, matchweek_y)
    # MODIFIED: Trust API's matchweek if present!
    has_matchweek = 'matchweek' in df.columns
    
    for col in ['season']:
        if col in df.columns:
            df = df.drop(columns=[col])
            
    # If matchweek is NOT present, drop it (unlikely) or calculate it
    if not has_matchweek:
        # 4. Date & Matchweek (The User's Snippet)
        df['date'] = pd.to_datetime(df['date'])
        
        # Calculate matchweek from team schedule sequence
        # "team_games = df_player_stats[['team', 'date']].drop_duplicates()..."
        team_games = (
            df[['team', 'date']]
            .drop_duplicates()
            .sort_values(['team', 'date'])
            .reset_index(drop=True)
        )
        
        team_games['matchweek'] = (
            team_games
                .groupby('team')
                .cumcount()
                .add(1)
        )
        
        # Merge matchweek back
        df = pd.merge(df, team_games, on=['team', 'date'], how='left')
    else:
        # Just ensure date is datetime
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
    
    # --- DENSIFICATION START ---
    # Ensure every player has a row for every week (1 to max_week or CURRENT_WEEK)
    # This prevents shift(1) from jumping over missing weeks (e.g. Week 1 -> Week 20)
    
    if not df.empty and 'matchweek' in df.columns:
        print("Densifying data to include non-playing weeks...")
        # 1. Determine Week Range
        max_wk = int(df['matchweek'].max()) if not df['matchweek'].isnull().all() else 38
        all_weeks = pd.DataFrame({'matchweek': range(1, max_wk + 1)})
        
        # 2. Get All Players (with team/pos context from df_players)
        # We use df_players to get the "Current/Default" team for filling gaps
        base_players = df_players[['scorerId', 'teamShortName', 'posShortNames']].rename(
            columns={'scorerId': 'player_id', 'teamShortName': 'default_team', 'posShortNames': 'default_pos'}
        ).drop_duplicates('player_id')
        
        # 3. Create Skeleton (Cross Join)
        # use 'cross' join available in newer pandas, or generic key
        all_weeks['key'] = 1
        base_players['key'] = 1
        skeleton = pd.merge(base_players, all_weeks, on='key').drop('key', axis=1)
        
        # Enforce types for valid merge
        skeleton['matchweek'] = skeleton['matchweek'].astype(int)
        skeleton['player_id'] = skeleton['player_id'].astype(str)
        
        df['matchweek'] = df['matchweek'].fillna(-1).astype(int)
        df['player_id'] = df['player_id'].astype(str)
        
        # DEBUG: Check stats before merge
        print(f"Stats rows before densify: {len(df)}")
        print(f"Skeleton rows: {len(skeleton)}")

        # 4. Merge Existing Stats onto Skeleton
        # We merge on player_id and matchweek
        # Existing df might have specific 'team' and 'position' for that week (e.g. before transfer) -> Trust df
        
        df = pd.merge(skeleton, df, on=['player_id', 'matchweek'], how='left', suffixes=('', '_actual'))
        
        # DEBUG: Check stats after merge
        matches_found = df['min'].notna().sum()
        print(f"Stats rows after densify: {len(df)} (Matches found with stats: {matches_found})")
        if matches_found == 0:
            print("CRITICAL WARNING: Densification wiped out all stats! Check merge keys.")
        
        # 5. Coalesce metadata columns
        # If actual data exists, use it. If not, use defaults from df_players.
        df['team'] = df['team'].fillna(df['default_team'])
        
        # Handle position: df might have 'position', skeleton has 'default_pos'
        # Previous logic (lines 511-512) merged 'posShortNames' -> 'position'
        # In the merge above, if df had 'position', it's kept.
        # If df was missing (NaN), we use 'default_pos'
        if 'position' in df.columns:
             df['position'] = df['position'].fillna(df['default_pos'])
        else:
             df['position'] = df['default_pos']
             
        # Cleanup temp cols
        df = df.drop(columns=['default_team', 'default_pos', 'scorerId', 'posShortNames'], errors='ignore')
        
        # 6. Fill Opponent for inserted rows
        # We need 'opp' to calculate home_ind and merge position_avg
        # df_matchups has (week, home_team, away_team)
        if df_matchups is not None and not df_matchups.empty:
            # Create a lookup from the FLATTENED df_matchups
            # It already has 'week', 'team', 'opponent', 'is_home'
            # We just need to merge this onto our dense df
            
            # Key: (week, team) -> (opponent, is_home)
            schedule_lookup = df_matchups[['week', 'team', 'opponent', 'is_home']].copy()
            
            # Merge schedule onto dense df
            # Left join on matchweek/team to find the opponent for that week
            df = pd.merge(df, schedule_lookup, left_on=['matchweek', 'team'], right_on=['week', 'team'], how='left')
            
            # Fill 'opp' from 'opponent' lookup
            if 'opp' in df.columns:
                 df['opp'] = df['opp'].fillna(df['opponent'])
            else:
                 df['opp'] = df['opponent']
                 
            # Fill 'home_ind' (is_home)
            # If 'home_ind' exists, fill it. Else create it.
            if 'home_ind' in df.columns:
                 df['home_ind'] = df['home_ind'].fillna(df['is_home'])
            else:
                 df['home_ind'] = df['is_home']

            # If still missing (e.g. bye week), fill defaults
            df['opp'] = df['opp'].fillna('-')
            df['home_ind'] = df['home_ind'].fillna(0).astype(int)
            
            # Cleanup
            df = df.drop(columns=['opponent', 'week', 'is_home'], errors='ignore')

    # --- DENSIFICATION END ---
    
    # SAFETY: Deduplicate columns to prevent "Grouper not 1-dimensional" error
    df = df.loc[:, ~df.columns.duplicated()]
    
    # 5. Season (Notebook uses 'season' column, assumes current context is 2025/2026? 
    # Actually checking notebook: "season = year" locally. Global "season" column in df.
    # We'll just ensure it's present.
    if 'season' not in df.columns:
        df['season'] = 2025
        
    # 6. Cleaning Stats (Zero fill)
    if 'fpts' in df.columns:
        df['fpts'] = df['fpts'].fillna(0).astype(float)
        
    calc_stats = ['g', 'kp', 'at', 'sot', 'tkw', 'dis', 'yc', 'rc', 'acnc', 'int', 'clr', 'cos', 'bs', 'aer', 'pkm', 'pkd', 'og', 'gao', 'cs', 'ga', 'sv', 'pks', 'hcs', 'sm']
    
    # Ensure minutes is float
    if 'min' in df.columns:
        df['min'] = df['min'].fillna(0).astype(float)
        
    df['last_minutes'] = df.groupby(['season', 'player_id'])['min'].shift(1).fillna(0)
    df['season_minutes'] = df.groupby(['season', 'player_id'])['last_minutes'].cumsum()
    
    for stat in calc_stats:
        if stat in df.columns:
            df[stat] = df[stat].fillna(0).astype(float)
            df[f'last_{stat}'] = df.groupby(['season', 'player_id'])[stat].shift(1).fillna(0)
            df[f'season_{stat}'] = df.groupby(['season', 'player_id'])[f'last_{stat}'].cumsum()
            
            # Avoid div by zero
            df[f'{stat}_per_min_gameweek'] = np.where(df.last_minutes > 0, df[f'last_{stat}'] / df.last_minutes, 0)
            df[f'{stat}_per_min_season'] = np.where(df.season_minutes > 0, df[f'season_{stat}'] / df.season_minutes, 0)
            
            df[f'{stat}_per_90_gameweek'] = df[f'{stat}_per_min_gameweek'] * 90
            df[f'{stat}_per_90_season'] = df[f'{stat}_per_min_season'] * 90
            
    # 7. Helper columns
    # home_ind not in snippet but used downstream? 
    # Notebook code: "df_player_stats['home_ind'] = df_player_stats.opp.str.contains('@')"
    df['home_ind'] = df['opp'].astype(str).str.contains('@').astype(int)
    # Robust clean
    df['opp_clean'] = df['opp'].apply(lambda x: str(x).replace('@', '') if pd.notnull(x) else '')
    
    # 8. Positional Averages (Notebook Logic)
    per90_cols = [c for c in df.columns if 'per_90_season' in c]
    pos_avg = df.groupby(['opp_clean', 'position'])[per90_cols].mean().reset_index()
    rename_dict = {c: f'positional_avg_{c}' for c in per90_cols}
    pos_avg = pos_avg.rename(columns=rename_dict)
    df = pd.merge(df, pos_avg, on=['opp_clean', 'position'], how='left')
    
    # Dummy Standings (Simplified)
    df['team_week_standing'] = 5
    df['team_week_standing_opp'] = 5
    
    return df

def train_position_models(train_encode, target_stats):
    """
    Train position-specific RandomForest models for all stats.
    Returns a dict of models: {(stat, position): model}
    This allows training once and reusing for multiple future weeks.
    """
    models = {}
    positions = ['G', 'D', 'M', 'F']
    
    for stat in target_stats:
        # Construct feature list for this stat
        stat_feats = [
            'player_id_code', 'team_code', 'opp_clean_code', 'position_code', 'home_ind',
            f'{stat}_per_min_gameweek', f'{stat}_per_min_season',
            f'{stat}_per_90_gameweek', f'{stat}_per_90_season',
            f'positional_avg_{stat}_per_90_season' # Consider also calculating a positional average against the specific opponent
        ]
        
        # Check availability
        valid_feats = [f for f in stat_feats if f in train_encode.columns]
        if not valid_feats:
            print(f"No valid features found for stat {stat}")
            continue
        
        # Train separate model for each position
        for pos in positions:
            train_pos = train_encode[train_encode['position'] == pos]
            if train_pos.empty:
                continue
            
            X_train = train_pos[valid_feats].fillna(0)
            y_train = train_pos[stat].fillna(0)
            
            # Train model
            model = RandomForestRegressor(n_estimators=10, random_state=42, n_jobs=1)
            model.fit(X_train, y_train)
            
            # Store with (stat, position, valid_feats) as key
            models[(stat, pos)] = (model, valid_feats)
    
    return models

def predict_with_models(models, predict_encode, target_stats):
    """
    Use pre-trained models to make predictions.
    Returns predictions DataFrame with player info and predicted stats.
    """
    predictions = pd.DataFrame()
    predictions['player_id'] = predict_encode['player_id']
    predictions['player_name'] = predict_encode['player_name']
    predictions['team'] = predict_encode['team']
    predictions['opp'] = predict_encode['opp_clean']
    predictions['position'] = predict_encode['position']
    
    positions = ['G', 'D', 'M', 'F']
    
    for stat in target_stats:
        for pos in positions:
            # Get the trained model for this stat/position
            if (stat, pos) not in models:
                continue
            
            model, valid_feats = models[(stat, pos)]
            predict_pos = predict_encode[predict_encode['position'] == pos]
            
            if predict_pos.empty:
                continue
            
            # Predict
            X_test = predict_pos[valid_feats].fillna(0)
            pred_vals = model.predict(X_test)
            
            # Store predictions
            pos_mask = predictions['position'] == pos
            predictions.loc[pos_mask, stat] = pred_vals
    
    return predictions

def make_predictions(df, target_week, matchups_df=None, pretrained_models=None):
    """
    Train on data < target_week.
    Predict on data == target_week.
    If target_week data is missing (future), construct it using matchups + latest features.
    """
    print(f"Generating predictions for Week {target_week}...")
    
    # Filter stats
    target_stats = ['g', 'kp', 'at', 'sot', 'tkw', 'dis', 'yc', 'rc', 'acnc', 'int', 'clr', 'cos', 'bs', 'aer', 'pkm', 'pkd', 'og', 'gao', 'cs', 'ga', 'sv', 'pks', 'hcs', 'sm']
    
    try:
        if df.empty:
            return []
            
        train_encode = df[df.matchweek < target_week]
        
        # Determine Prediction Set
        predict_encode = df[df.matchweek == target_week]
        
        # Future Week Handling (Predictive)
        if predict_encode.empty:
            if matchups_df is not None and not matchups_df.empty:
                # Construct rows for this future week
                week_games = matchups_df[matchups_df.week == target_week]
                if not week_games.empty:
                    # Use stats from last COMPLETED week (minutes > 0) not scheduled week (minutes = 0)
                    # This ensures we use real performance data for predictions
                    completed_weeks = df[df['min'] > 0]
                    if not completed_weeks.empty:
                        # Get each player's most recent completed game
                        latest_completed = completed_weeks.sort_values(['matchweek']).groupby('player_id').tail(1).copy()
                        
                        # Use these stats as basis for future prediction
                        # Note: We keep the opponent ('opp') from their last game
                        # This is a limitation - ideally we'd have future fixture data
                        # But the rolling stats (form) are the dominant predictors
                        future_df = latest_completed.copy()
                        
                        if not future_df.empty:
                            predict_encode = future_df
        
        if predict_encode.empty:
            return []
        
        if train_encode.empty:
             return []

        predictions = pd.DataFrame()
        predictions['player_id'] = predict_encode['player_id'] # Store IDs
        predictions['player_name'] = predict_encode['player_name']
        predictions['team'] = predict_encode['team']
        predictions['opp'] = predict_encode['opp_clean']
        predictions['position'] = predict_encode['position']  # Add position for position-specific models
        
        # Check if we have pretrained models to use (for future weeks optimization)
        if pretrained_models is not None:
            # Use pretrained models - much faster!
            predictions = predict_with_models(pretrained_models, predict_encode, target_stats)
        else:
            # Train models from scratch (for historical weeks)
            # Train & Predict loop
            for stat in target_stats:
                # Construct feature list for this stat
                stat_feats = [
                    'player_id_code', 'team_code', 'opp_clean_code', 'position_code', 'home_ind',
                    f'{stat}_per_min_gameweek', f'{stat}_per_min_season',
                    f'{stat}_per_90_gameweek', f'{stat}_per_90_season',
                    f'positional_avg_{stat}_per_90_season' 
                ]
                
                # Check availability
                valid_feats = [f for f in stat_feats if f in train_encode.columns]
                
                if not valid_feats:
                    continue
                
                # Train SEPARATE models for each position (G, D, M, F)
                # This improves accuracy since positions have very different stat profiles
                positions = ['G', 'D', 'M', 'F']
                
                for pos in positions:
                    # Filter training and prediction data for this position
                    train_pos = train_encode[train_encode['position'] == pos]
                    predict_pos = predict_encode[predict_encode['position'] == pos]
                    
                    if train_pos.empty or predict_pos.empty:
                        continue
                    
                    # Prepare data
                    X_train = train_pos[valid_feats].fillna(0)
                    y_train = train_pos[stat].fillna(0)
                    X_test = predict_pos[valid_feats].fillna(0)
                    
                    # Train position-specific model
                    model = RandomForestRegressor(n_estimators=10, random_state=42, n_jobs=1)
                    model.fit(X_train, y_train)
                    
                    # Predict for this position
                    pred_vals = model.predict(X_test)
                    
                    # Store predictions back into main dataframe
                    pos_mask = predictions['position'] == pos
                    predictions.loc[pos_mask, stat] = pred_vals
            
        # Calculate predicted FPts
        # Calculate predicted FPts
        predictions['predicted_fpts'] = predictions.apply(get_fantasy_score, axis=1).round(2)
        
        # Add week info
        predictions['week'] = target_week
        
        # Return list of dicts with position included
        return predictions[['player_id', 'player_name', 'position', 'team', 'predicted_fpts', 'opp', 'week']].to_dict(orient='records')
        
    except Exception as e:
        print(f"Prediction failed for Week {target_week}: {e}")
        # import traceback
        # traceback.print_exc()
        return []

def enrich_matchups_with_projections(api, matchups_list, all_predictions, start_week, actual_score_map=None):
    """
    Enrich matchups with projected scores using rolled predictions.
    and ACTUAL scores if available.
    """
    print("Enriching matchups with rolling predictions and actuals...")
    if actual_score_map is None: actual_score_map = {}
    
    # Create nested lookup: week -> player_id -> score
    pred_map = {}
    for p in all_predictions:
        w = p['week']
        pid = str(p['player_id'])
        score = float(p.get('predicted_fpts', 0))
        
        if w not in pred_map: pred_map[w] = {}
        pred_map[w][pid] = score
    
    # Cache roster calls to avoid re-fetching for same team/week
    roster_cache = {}

    def get_starters_proj_cached(tid, week):
        key = f"{tid}_{week}"
        if key in roster_cache: return roster_cache[key]
        
        total_proj = 0.0
        try:
             # roster_data = api._request("getTeamRosterInfo", teamId=tid, period=week)
             roster_data = api._request("getTeamRosterInfo", teamId=tid, period=week)
             
             # Collect all players for potential optimal calculation
             all_roster_players = []
             starter_points = 0.0
             starters_found = 0
             
             week_preds = pred_map.get(week, {})
             week_actuals = actual_score_map.get(week, {}) # Lookup actuals for this week
             
             if 'tables' in roster_data and isinstance(roster_data['tables'], list):
                for table in roster_data['tables']:
                    for row in table['rows']:
                        # Get ID
                        scorer = row.get('scorer', {})
                        pid = str(scorer.get('scorerId', ''))
                        pos = scorer.get('posShortNames', 'M')
                        status = row.get('statusId', '0')
                        
                        # --- KEY CHANGE: Projections vs Actuals ---
                        pred_score = week_preds.get(pid, 0.0) # Model Projection
                        
                        # Actual Score:
                        # If pid in week_actuals, use it (even if negative)
                        # If NOT in week_actuals, default to 0.0 (didn't play)
                        # BUT we want to ensure we don't overwrite if actuals is 0?
                        # No, if actual is 0, it's 0.
                        actual_score = week_actuals.get(pid, 0.0)
                        
                        # Inject into row for Dashboard
                        # Dashboard expects 'score' (Actual) and 'projected' (Model) likely?
                        # Or maybe we need to set specific keys?
                        # Looking at dashboard.json structure, 'starters' list usually has 'score'.
                        # The dashboard code (not visible, but typical) reads 'score'.
                        # We can't modify 'row' in place persistently unless we return it?
                        # Wait, 'roster_data' is local.
                        # BUT 'enrich_matchups' modifies 'matchups_list'.
                        # This function only returns total_proj.
                        
                        # Wait, we need to inject this into MATCHUP_LIST for the dashboard to see it.
                        # 'get_starters_proj_cached' is just a helper calculation?
                        # Ah, lines 868 assign:
                        # m['home_projected'] = round(get_starters_proj_cached(...), 2)
                        
                        # Where is the ROSTER OBJECT populated?
                        # If 'enrich' doesn't population roster, then who does?
                        # 'get_matchups' returns skeleton.
                        # 'rostered_ids' fetches current.
                        # Ah! The dashboard likely fetches roster in REAL TIME or uses 'team_details'?
                        # No, 'dashboard_data.json' has 'matchups' list.
                        # Does 'matchups' list contain rosters?
                        # Line 1188: df_matchups, matchup_list = get_matchups(api)
                        # 'matchup_list' is what is saved.
                        # Does 'get_matchups' fetch rosters?
                        # If not, the dashboard has NO ROSTERS.
                        # Checking user request output JSON earlier... 
                        # "starters": [...] implies rosters ARE inside.
                        # If 'get_matchups' fetches them, then 'enrich_matchups' needs to ITERATE them.
                        # BUT 'enrich_matchups' calls 'get_starters_proj_cached' which CALLS 'getTeamRosterInfo'.
                        # It fetches roster locally but DOES NOT SAVE IT into the matchup object?!
                        # If 'get_matchups' provides rosters, why fetch again?
                        # If 'get_matchups' DOES NOT provide rosters, where do they come from?
                        
                        # HYPOTHESIS: 'get_matchups' logic (view_file needed?)
                        # If 'matchup_list' strictly has team/score, how does dashboard show players?
                        # Maybe 'matchup_details_modal' fetches on demand?
                        # USER SAID: "Matchweek 23 is showing real values...".
                        # This means dashboard HAS the values.
                        # If I modified update_data.py to return actuals, and dashboard shows it.
                        # Then 'enrich_matchups' MUST be modifying the structure OR 'get_matchups' does it.
                        
                        # Wait, 'enrich_matchups' implementation:
                        # It loops m in matchups_list.
                        # It calls 'get_starters_proj_cached'.
                        # That function FETCHES roster.
                        # But it returns a FLOAT (total).
                        # It DOES NOT attach the roster back to 'm'.
                        
                        # THIS IMPLIES: 'matchup_list' ALREADY HAS ROSTERS?
                        # OR dashboard fetches them?
                        # If dashboard fetches them, it hits Fantrax API directly? No, it hits 'server.py'.
                        # 'server.py' reads 'dashboard_data.json'.
                        # So 'matchup_list' MUST have rosters.
                        # Let me check 'get_matchups' to be sure.
                        
                        if status == '1': # Starter
                            starter_points += pred_score
                            starters_found += 1
                            
                        # Add to potential list
                        all_roster_players.append({
                            'player_id': pid,
                            'position': pos,
                            'fpts': pred_score
                        })
            
             # Decision: Use Actual Starters OR Optimal?
             # If future week (e.g. starters_found == 0), use Optimal Lineup from Predictions
             # Using threshold < 11 to be safe (if someone set incomplete lineup, we might still want their actual, but usually 0 means unset)
             # Let's say if < 9 starters, assume invalid/future and auto-fill.
             if starters_found < 9:
                 # Calculate best possible lineup from roster
                 roster_df = pd.DataFrame(all_roster_players)
                 if not roster_df.empty:
                     total_proj = solve_best_lineup(roster_df)
                 else:
                     total_proj = 0.0
             else:
                 total_proj = starter_points
                            
        except Exception as e:
            print(f"Error fetching starters for {tid}: {e}")
            
        roster_cache[key] = total_proj
        return total_proj

    for m in matchups_list:
        # Enrich all historic matchups if we have predictions
        # (Or filtering start_week if needed, but we likely want all available)
        if m['week'] in pred_map:
            try:
                m['home_projected'] = round(get_starters_proj_cached(m['home_team_id'], m['week']), 2)
                m['away_projected'] = round(get_starters_proj_cached(m['away_team_id'], m['week']), 2)
            except Exception as e:
                print(f"Error projecting matchup {m['matchupId']}: {e}")


def calculate_advanced_stats(matchups, opt_df=None):
    print("Calculating advanced stats...")
    import numpy as np
    if matchups.empty: return {}

    # If opt_df is empty/None (didn't run rosters), TRY TO RECONSTRUCT IT from matchups
    if opt_df is None or opt_df.empty:
        print("Detailed optimal stats (opt_df) not provided. Attempting to reconstruct from matchups data...")
        # Check if matchups has optimal score columns
        if 'home_optimal_score' in matchups.columns and 'away_optimal_score' in matchups.columns:
            # Reconstruct opt_df: We need [week, team_id, optimal_score]
            
            # Reconstruct opt_df: We need [week, team_id, optimal_score]
            # df_matchups is long, so we use 'is_home' to pick the right column
            
            # Ensure we have is_home
            if 'is_home' in matchups.columns:
                matchups['optimal_score'] = np.where(matchups['is_home'] == 1,
                                                     matchups['home_optimal_score'],
                                                     matchups['away_optimal_score'])
                
                opt_df = matchups[['week', 'team_id', 'optimal_score']].copy()
                
                # Filter out NaNs
                opt_df = opt_df.dropna(subset=['optimal_score'])
                
                # Ensure types
                opt_df['team_id'] = opt_df['team_id'].astype(str)
                opt_df['week'] = opt_df['week'].astype(int)
                opt_df['optimal_score'] = opt_df['optimal_score'].astype(float)
                
                print(f"Reconstructed opt_df with {len(opt_df)} records.")
            else:
                print("Warning: is_home column missing in matchups, cannot reconstruct optimal scores.")
        else:
            print("Warning: Matchups data does not contain preserved optimal scores. Efficiency cannot be calculated.")

    
    # Filter for completed weeks
    completed_matchups = matchups[matchups.week < CURRENT_WEEK].copy()
    
    # helper for result
    def get_result(row):
        if row['score'] > row['opponent_score']: return 'W'
        elif row['score'] < row['opponent_score']: return 'L'
        else: return 'D'
    
    completed_matchups['result'] = completed_matchups.apply(get_result, axis=1)
    
    # Weekly Extremes
    weekly_extremes = []
    sorted_weeks = sorted(completed_matchups.week.unique())
    for w in sorted_weeks:
        week_games = completed_matchups[completed_matchups.week == w]
        if week_games.empty: continue
        
        high_idx = week_games['score'].idxmax()
        high_row = week_games.loc[high_idx]
        
        low_idx = week_games['score'].idxmin()
        low_row = week_games.loc[low_idx]
        
        # Efficiency
        best_eff = {'team': '-', 'score': 0, 'opt': 0, 'pct': 0}
        worst_eff = {'team': '-', 'score': 0, 'opt': 0, 'pct': 100}
        
        if opt_df is not None and not opt_df.empty:
            week_opt = opt_df[opt_df.week == w]
            if not week_opt.empty:
                # Merge week_games (has team_id) with week_opt (has team_id, optimal_score)
                # Ensure team_id types match (str vs int)
                week_games['team_id'] = week_games['team_id'].astype(str)
                week_opt['team_id'] = week_opt['team_id'].astype(str)
                
                merged = pd.merge(week_games, week_opt, on=['team_id'], suffixes=('', '_opt'))
                if not merged.empty:
                    merged['efficiency'] = (merged['score'] / merged['optimal_score'].replace(0, 1)) * 100
                    
                    valid_eff = merged['efficiency'].dropna()
                    
                    if not valid_eff.empty:
                        # Best Efficiency
                        best_idx = valid_eff.idxmax()
                        best_row = merged.loc[best_idx]
                        best_eff = {
                            'team': best_row['team'],
                            'score': round(float(best_row['score']), 2),
                            'opt': round(float(best_row['optimal_score']), 2),
                            'pct': round(float(best_row['efficiency']), 1)
                        }
                        
                        # Worst Efficiency
                        worst_idx = valid_eff.idxmin()
                        worst_row = merged.loc[worst_idx]
                        worst_eff = {
                            'team': worst_row['team'],
                            'score': round(float(worst_row['score']), 2),
                            'opt': round(float(worst_row['optimal_score']), 2),
                            'pct': round(float(worst_row['efficiency']), 1)
                        }

        weekly_extremes.append({
            'week': int(w),
            'high_team': high_row['team'],
            'high_score': round(float(high_row['score']), 2),
            'low_team': low_row['team'],
            'low_score': round(float(low_row['score']), 2),
            'best_eff': best_eff,
            'worst_eff': worst_eff
        })

    teams = completed_matchups.team.unique()
    
    summary = []
    
    for team in teams:
        team_games = completed_matchups[completed_matchups.team == team].sort_values('week')
        
        scores = team_games.score.values
        opp_scores = team_games.opponent_score.values
        results = team_games.result.values
        
        # 1. Consistency (Std Dev)
        import numpy as np
        std_dev = float(np.std(scores))
        
        # 2. Luck (Total Points Against)
        total_pa = float(np.sum(opp_scores))
        
        # 3. Form (Last 5)
        last_5_games = team_games.tail(5)
        last_5_avg = float(last_5_games.score.mean()) if not last_5_games.empty else 0.0
        last_5_record = "".join(last_5_games.result.values) # e.g. "WWLDL"
        
        # 4. Extremes
        max_score = float(np.max(scores)) if len(scores) > 0 else 0.0
        min_score = float(np.min(scores)) if len(scores) > 0 else 0.0
        
        # 5. Weekly trend
        weekly_trend = []
        cumulative_points = 0
        for w, s, r in zip(team_games.week.values, scores, results):
            pts = 3 if r == 'W' else 1 if r == 'D' else 0
            cumulative_points += pts
            weekly_trend.append({
                'week': int(w),
                'score': float(s),
                'table_points': int(cumulative_points)
            })
        
        summary.append({
            'team': team,
            'std_dev': round(std_dev, 2),
            'total_pa': round(total_pa, 2),
            'last_5_avg': round(last_5_avg, 2),
            'form': last_5_record,
            'max_score': round(max_score, 2),
            'min_score': round(min_score, 2),
            'weekly_trend': weekly_trend
        })
        
    # Superlatives
    df_sum = pd.DataFrame(summary)
    
    superlatives = {}
    if not df_sum.empty:
        most_consistent = df_sum.loc[df_sum['std_dev'].idxmin()]
        least_consistent = df_sum.loc[df_sum['std_dev'].idxmax()]
        luckiest = df_sum.loc[df_sum['total_pa'].idxmin()] # Lowest PA
        unluckiest = df_sum.loc[df_sum['total_pa'].idxmax()] # Highest PA
        best_form_team = df_sum.loc[df_sum['last_5_avg'].idxmax()]
        
        superlatives = {
            'most_consistent': {'team': most_consistent['team'], 'val': most_consistent['std_dev'], 'desc': 'Lowest Std Dev in Scores'},
            'wildcard': {'team': least_consistent['team'], 'val': least_consistent['std_dev'], 'desc': 'Highest Std Dev in Scores'}, 
            'luckiest': {'team': luckiest['team'], 'val': luckiest['total_pa'], 'desc': 'Fewest Points Against'},
            'unluckiest': {'team': unluckiest['team'], 'val': unluckiest['total_pa'], 'desc': 'Most Points Against'},
            'form_king': {'team': best_form_team['team'], 'val': best_form_team['last_5_avg'], 'desc': 'Highest Avg Score (Last 5)'}
        }
    
    return {
        'team_stats': summary,
        'superlatives': superlatives,
        'weekly_extremes': weekly_extremes
    }



def fetch_current_rosters(api, team_ids=None):
    """
    Fetch rosters for the current week to identify which players are NOT available.
    Returns a set of rostered player IDs.
    """
    print(f"Fetching current rosters for Week {CURRENT_WEEK}...")
    rostered_ids = set()
    
    try:
        # Get team IDs from API if not provided
        if not team_ids:
            # Try fetching from SCHEDULE view which lists all matchups/teams
            print("Attempting to fetch Team IDs from SCHEDULE view...")
            standings_data = api._request("getStandings", view="SCHEDULE")
            team_ids = []
            if 'tableList' in standings_data:
                 for table in standings_data['tableList']:
                     for row in table['rows']:
                         # Schedule rows contain cells with team info
                         if 'cells' in row:
                             for cell in row['cells']:
                                 if 'teamId' in cell:
                                     team_ids.append(cell['teamId'])
            
            # Unique IDs
            team_ids = list(set(team_ids))
                         
        if not team_ids:
             print("Warning: Could not fetch team IDs. Rosters might be incomplete.")
        
        print(f"Found {len(team_ids)} teams.")
        
        for i, tid in enumerate(team_ids):
            try:
                # Fetch roster for CURRENT_WEEK
                roster_data = api._request("getTeamRosterInfo", teamId=tid, period=CURRENT_WEEK)
                
                if 'tables' in roster_data and isinstance(roster_data['tables'], list):
                    for table in roster_data['tables']:
                         for row in table['rows']:
                             # Try to find player ID in row
                             if 'fixedId' in row:
                                 rostered_ids.add(str(row['fixedId']))
                             elif 'id' in row:
                                 rostered_ids.add(str(row['id']))
                             elif 'responseId' in row:
                                 rostered_ids.add(str(row['responseId']))
                             # Handling for scorer object
                             elif 'scorer' in row and 'scorerId' in row['scorer']:
                                 rostered_ids.add(str(row['scorer']['scorerId']))
                             # Sometimes it is in cells
                             elif 'cells' in row:
                                # This is fragile without knowing index, but usually first hidden or similar
                                # For now let's hope top-level id fields work as they did in other calls
                                pass

            except Exception as e:
                print(f"Failed to fetch roster for team {tid}: {e}")

    
        # Print sample IDs for debugging
        if len(rostered_ids) > 0:
            print(f"DEBUG: Sample Rostered IDs: {list(rostered_ids)[:5]}")
        else:
            print("DEBUG: No rostered IDs found!")


    except Exception as e:
        print(f"Error checking rosters: {e}")
        
    return rostered_ids

def get_waivers(processed_stats, rostered_ids):
    """
    Filter processed stats for non-rostered players and aggregate.
    Returns sorted list of waiver players.
    """
    print("Calculating waiver stats...")
    
    # rostered_ids needs to be string set
    rostered_ids = set(str(x) for x in rostered_ids)
    
    # Unique players in stats
    stats_players = processed_stats.player_id.astype(str).unique()
    waiver_players = [p for p in stats_players if p not in rostered_ids]
    
    # Filter dataframe
    df = processed_stats[processed_stats.player_id.astype(str).isin(waiver_players)].copy()
    
    if df.empty:
        return []

    # Aggregations
    # Handle numeric columns
    # Aggregations
    # Handle numeric columns
    # Full list of stats requested by user
    numeric_cols = ['fpts', 'minutes', 'g', 'kp', 'at', 'sot', 'tkw', 'dis', 'yc', 'rc', 'acnc', 'int', 'clr', 'cos', 'bs', 'aer', 'pkm', 'pkd', 'og', 'gao', 'cs', 'ga', 'sv', 'pks', 'hcs', 'sm']
    
    # Check which cols exist
    existing_num_cols = [c for c in numeric_cols if c in df.columns]
    
    # Add matches played col (approx)
    if 'minutes' in df.columns:
        df['gp'] = (df['minutes'] > 0).astype(int)
    else:
        df['gp'] = 1
    
    agg_rules = {col: 'sum' for col in existing_num_cols}
    agg_rules['gp'] = 'sum'
    # Ensure minutes is summed
    if 'minutes' in existing_num_cols:
        agg_rules['minutes'] = 'sum'
    
    # Non-numeric: take last (most recent)
    if 'player_name' in df.columns: agg_rules['player_name'] = 'last'
    if 'team' in df.columns: agg_rules['team'] = 'last'
    if 'position' in df.columns: agg_rules['position'] = 'last'
    if 'injured' in df.columns: agg_rules['injured'] = 'last'
    # NEW: Capture last played date
    if 'date' in df.columns: agg_rules['date'] = 'max'
    
    try:
        grouped = df.sort_values('matchweek').groupby('player_id').agg(agg_rules).reset_index()
        
        # Rename date to last_played for clarity
        if 'date' in grouped.columns:
            grouped = grouped.rename(columns={'date': 'last_played'})
            # Convert to string YYYY-MM-DD for JSON serialization
            grouped['last_played'] = grouped['last_played'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else None)
        
        # Calculate per 90s and per game
        if 'gp' in grouped.columns:
            grouped['fpts_per_game'] = (grouped['fpts'] / grouped['gp']).fillna(0).round(2)
            
            # Calculate per game for all numeric cols except metadata
            for col in existing_num_cols:
                if col not in ['minutes']:
                    grouped[f'{col}_per_game'] = (grouped[col] / grouped['gp']).fillna(0).round(2)
        
        if 'minutes' in grouped.columns:
            # Avoid div by zero
            mins = grouped['minutes'].replace(0, 1)
            grouped['fpts_per_90'] = ((grouped['fpts'] / mins) * 90).fillna(0).round(2)
            
            # Calculate per 90 for all numeric cols except metadata
            for col in existing_num_cols:
                if col not in ['minutes']:
                     grouped[f'{col}_per_90'] = ((grouped[col] / mins) * 90).fillna(0).round(2)

            # Filter out junk (e.g. 0 minutes)
            grouped = grouped[grouped['minutes'] > 0]
        
        # Sort by Total FPTS descending
        if 'fpts' in grouped.columns:
            grouped = grouped.sort_values('fpts', ascending=False)
        
        return grouped.to_dict(orient='records')
        
    except Exception as e:
        print(f"Error calculating waivers: {e}")
        import traceback
        traceback.print_exc()
        return []

def load_aggregated_stats(base_dir):
    """
    Loads player stats. Prioritizes the monolithic df_player_stats.csv
    generated by ingest_data.py. Fallback to weekly files for legacy support.
    """
    # 1. Try Loading Monolithic File (Preferred)
    mono_path = os.path.join(base_dir, "df_player_stats.csv")
    if os.path.exists(mono_path):
        print(f"Loading aggregated stats from {mono_path}...")
        try:
             return pd.read_csv(mono_path, low_memory=False)
        except Exception as e:
             print(f"Error loading {mono_path}: {e}")

    # 2. Fallback to Weekly Files
    player_data_dir = os.path.join(base_dir, "player_data")
    if not os.path.exists(player_data_dir):
        os.makedirs(player_data_dir)
        return pd.DataFrame()
        
    all_files = glob.glob(os.path.join(player_data_dir, "df_player_stats_*.csv"))
    if not all_files:
        print("No weekly player stat files found.")
        return pd.DataFrame()

    
    print(f"Found {len(all_files)} weekly stat files. Aggregating...")
    df_list = []
    for filename in all_files:
        try:
            # Read each file
            df = pd.read_csv(filename, low_memory=False)
            df_list.append(df)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            
    if not df_list:
        return pd.DataFrame()
        
    # Concatenate all week files
    aggregated_df = pd.concat(df_list, ignore_index=True)
    
    # Deduplicate in case of overlaps (trusting matchweek/player_id)
    # Actually, trusting the files are partitioned by week is better, 
    # but dropping exact duplicates is safe.
    aggregated_df = aggregated_df.drop_duplicates()
    
    return aggregated_df

def main():
    parser = argparse.ArgumentParser(description='Update Dashboard Data')
    parser.add_argument('--all', action='store_true', help='Update ALL data (default if no other flags provided)')
    parser.add_argument('--stats', action='store_true', help='Run data ingestion (Slow)')
    parser.add_argument('--matchups', action='store_true', help='Update matchups and standings')
    parser.add_argument('--rosters', action='store_true', help='Update rosters and optimal lineups')
    parser.add_argument('--predictions', action='store_true', help='Generate ML predictions')
    parser.add_argument('--waivers', action='store_true', help='Process waivers')
    args = parser.parse_args()

    # Default to ALL if no specific flags
    if not any([args.stats, args.matchups, args.rosters, args.predictions, args.waivers]):
        args.all = True

    if args.all:
        args.stats = True
        args.matchups = True
        args.rosters = True
        args.predictions = True
        args.waivers = True
        
    # Dependencies
    if args.rosters or args.predictions or args.waivers:
        args.matchups = True # Need current matchups context for everything else
        
    print(f"Update Configuration:")
    print(f"  Stats: {args.stats}")
    print(f"  Matchups: {args.matchups}")
    print(f"  Rosters: {args.rosters}")
    print(f"  Predictions: {args.predictions}")
    print(f"  Waivers: {args.waivers}")

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Load existing data to preserve what isn't updated
    data = {}
    data_path = os.path.join(DATA_DIR, 'dashboard_data.json')
    if os.path.exists(data_path):
        try:
            with open(data_path, 'r') as f:
                data = json.load(f)
            print("Loaded existing dashboard_data.json.")
        except Exception as e:
            print(f"Error loading existing data: {e}")

    # 1. Run Data Ingestion (Smart Refresh)
    df_fresh = pd.DataFrame()
    if args.stats:
        print("Running data ingestion (smart refresh)...")
        try:
            df_fresh = ingest_data(full_refresh=False)
        except Exception as e:
            print(f"Ingestion failed: {e}")
    
    # Connect to Fantrax
    api = connect_fantrax()
    
    # 2. Get Matchups
    df_matchups = pd.DataFrame()
    matchup_list = data.get('matchups', [])
    
    if args.matchups:
        df_matchups, matchup_list = get_matchups(api)

        # --- FIX: PRESERVE OPTIMAL SCORES ---
        # If we are NOT calculating fresh optimal scores (args.rosters is False),
        # we MUST preserve the existing ones from 'data' to keep efficiency rankings alive.
        if not args.rosters:
            print("Preserving existing optimal scores from previous data...")
            prev_opt_map = {} # matchupId -> {home_opt: X, away_opt: Y}
            
            prev_matchups = data.get('matchups', [])
            for m in prev_matchups:
                mid = m.get('matchupId')
                if mid:
                    entry = {}
                    if 'home_optimal_score' in m: entry['home_optimal_score'] = m['home_optimal_score']
                    if 'away_optimal_score' in m: entry['away_optimal_score'] = m['away_optimal_score']
                    if entry:
                        prev_opt_map[mid] = entry
            
            # Inject into new matchup_list
            preserved_count = 0
            for m in matchup_list:
                mid = m.get('matchupId')
                if mid in prev_opt_map:
                    # Only inject if NOT present (shouldn't be, since it's fresh specific fetch)
                    # But safest to just set if missing
                    curr_home = m.get('home_optimal_score')
                    curr_away = m.get('away_optimal_score')
                    
                    if curr_home is None and 'home_optimal_score' in prev_opt_map[mid]:
                        m['home_optimal_score'] = prev_opt_map[mid]['home_optimal_score']
                        preserved_count += 1
                        
                    if curr_away is None and 'away_optimal_score' in prev_opt_map[mid]:
                        m['away_optimal_score'] = prev_opt_map[mid]['away_optimal_score']
                        
            print(f"Preserved optimal scores for {preserved_count} matchups.")
            
            # We also need to update df_matchups because calculate_advanced_stats uses the DF, not the list.
            # Convert enrich list back to DF or merge?
            # Easier to just merge the preserved values onto df_matchups
            if preserved_count > 0:
                 # Create a temp DF from the enriched list
                 enriched_df = pd.DataFrame(matchup_list)
                 # We only care about the optimal columns and matchupId
                 cols_to_merge = ['matchupId']
                 if 'home_optimal_score' in enriched_df.columns: cols_to_merge.append('home_optimal_score')
                 if 'away_optimal_score' in enriched_df.columns: cols_to_merge.append('away_optimal_score')
                 
                 valid_cols = [c for c in cols_to_merge if c in enriched_df.columns]
                 if len(valid_cols) > 1: # at least ID + one score
                     mini_df = enriched_df[valid_cols]
                     # Merge onto df_matchups
                     # df_matchups has 'matchupId'
                     df_matchups = pd.merge(df_matchups, mini_df, on='matchupId', how='left', suffixes=('', '_new'))
                     
                     # Coalesce
                     if 'home_optimal_score_new' in df_matchups.columns:
                         df_matchups['home_optimal_score'] = df_matchups['home_optimal_score_new'].combine_first(df_matchups.get('home_optimal_score', pd.Series(dtype='float64')))
                         df_matchups = df_matchups.drop(columns=['home_optimal_score_new'])
                         
                     if 'away_optimal_score_new' in df_matchups.columns:
                         df_matchups['away_optimal_score'] = df_matchups['away_optimal_score_new'].combine_first(df_matchups.get('away_optimal_score', pd.Series(dtype='float64')))
                         df_matchups = df_matchups.drop(columns=['away_optimal_score_new'])
        
        data['matchups'] = matchup_list # Update data object
    else:
        # Construct df_matchups from loaded JSON to support dependent tasks?
        # It's Complex. But if dependent tasks requested matchups, args.matchups is True.
        # So we only reach here if NO dependent tasks run.
        pass

    # 3. Team Details (Always Fast, update if matchups run)
    if args.matchups:
        team_details = get_team_details(api)
        data['team_details'] = team_details

    # 4. Fetch Rosters (for Waivers) & Rostered IDs
    rostered_ids = set()
    if args.waivers or args.rosters: # Waivers need rostered_ids
        team_ids = list(set([m['home_team_id'] for m in matchup_list] + [m['away_team_id'] for m in matchup_list]))
        rostered_ids = fetch_current_rosters(api, team_ids=team_ids)
    
    # 5. Standings (Standard & Median) & Historical Merge Preparation
    median_history = {} # Lookup for merging
    
    if args.matchups:
        std_standings = calculate_standings(df_matchups)
        med_standings = calculate_median_standings(df_matchups)
        median_history = calculate_median_scores_history(df_matchups) # Get historical data
        
        # Initialize dictionary if missing
        if 'standings' not in data: data['standings'] = {}
        
        data['standings']['standard'] = std_standings.to_dict(orient='records') if not std_standings.empty else []
        data['standings']['median'] = med_standings.to_dict(orient='records') if not med_standings.empty else []
    
    # 6. Load Players (Saved by ingest_data)
    try:
        df_players = pd.read_csv(os.path.join(base_dir, "df_players.csv"))
    except Exception as e:
        print(f"Error loading players: {e}")
        df_players = pd.DataFrame()

    # 7. Process Fresh Data & Archive Current Week
    if not df_fresh.empty:
        try:
            print("Processing fresh data to isolate current week...")
            # We must use preprocess to calculate 'matchweek' correctly based on the full sequence in df_fresh
            # Assuming df_matchups is available or can be None for basic preprocessing
            df_fresh_proc = preprocess_player_stats(df_fresh, df_players, df_matchups)
            
            # Filter for CURRENT_WEEK
            df_current_week = df_fresh_proc[df_fresh_proc['matchweek'] == CURRENT_WEEK]
            
            if not df_current_week.empty:
                week_file = os.path.join(base_dir, "player_data", f"df_player_stats_{CURRENT_WEEK}.csv")
                # Create dir if not exists
                os.makedirs(os.path.dirname(week_file), exist_ok=True)
                
                print(f"Saving {len(df_current_week)} rows for Week {CURRENT_WEEK} to {week_file}")
                # Save just this week's data
                df_current_week.to_csv(week_file, index=False)
            else:
                print(f"Warning: No stats found for Week {CURRENT_WEEK} in fresh data.")
        except Exception as e:
            print(f"Error processing fresh data: {e}")
            import traceback
            traceback.print_exc()

    # 8. Load Aggregated Historical Data (Source of Truth)
    # Needed for Rosters, Predictions, Waivers
    df_stats = pd.DataFrame()
    if args.rosters or args.predictions or args.waivers or args.stats:
        print("Loading aggregated historical data from weekly files...")
        df_stats = load_aggregated_stats(base_dir)
        
        if df_stats.empty:
            print("CRITICAL WARNING: No aggregated stats loaded.")
            if not df_fresh.empty:
                print("Falling back to fresh data...")
                df_stats = df_fresh

    # 9. Optimal Standings & Processing
    opt_df = pd.DataFrame()
    optimal_lookup = {} # (team_id, week) -> score
    
    if args.rosters:
        try:
            opt_standings, opt_df = calculate_optimal_standings(api, df_matchups, df_stats, df_players)
            if 'standings' not in data: data['standings'] = {}
            data['standings']['optimal'] = opt_standings.to_dict(orient='records') if not opt_standings.empty else []
            
            # Create lookup for merging
            # opt_df has columns: week, team_id, optimal_score
            for _, row in opt_df.iterrows():
                try:
                    # team_id might be int or str, normalize to str
                    optimal_lookup[(str(row['team_id']), row['week'])] = float(row['optimal_score'])
                except: pass
                
        except Exception as e:
            print(f"Optimal standings failed: {e}")
            import traceback
            traceback.print_exc()

    # --- MERGE HISTORICAL DATA INTO MATCHUPS ---
    # We do this here (after Rosters/Optimal runs) to ensure we have the data
    if args.matchups and (not opt_df.empty or median_history):
        print("Merging historical Optimal/Median scores into Matchups...")
        # Iterating the list of dicts directly
        for m in data['matchups']:
            wk = m['week']
            # Only processing past/current weeks 
            if wk <= CURRENT_WEEK:
                h_tm_id = str(m['home_team_id'])
                a_tm_id = str(m['away_team_id'])
                
                # 1. OPTIMAL SCORES
                if optimal_lookup:
                    m['home_optimal_score'] = optimal_lookup.get((h_tm_id, wk), 0.0)
                    m['away_optimal_score'] = optimal_lookup.get((a_tm_id, wk), 0.0)
                    
                # 2. MEDIAN DATA
                if median_history:
                    # Home
                    h_med = median_history.get((h_tm_id, wk), {})
                    m['home_median_score'] = h_med.get('median_value', 0.0) # The median threshold itself? or the team's score? 
                    # Actually standard practice: "Median Score" usually refers to the threshold you tried to beat.
                    # BUT for consistency with "Optimal Score" (which is YOUR score), maybe we just need 'beat_median' flag?
                    # Let's save the threshold as 'median_threshold' and boolean result.
                    m['median_threshold'] = h_med.get('median_value', 0.0) # Same for both teams in a week
                    m['home_beat_median'] = h_med.get('beat_median', False)
                    m['away_beat_median'] = median_history.get((a_tm_id, wk), {}).get('beat_median', False)

    # 10. Process Stats & Calculate Waivers & Predictions
    waivers_data = [] 
    player_predictions = data.get('predictions', [])

    if args.waivers or args.predictions:
        try:
            processed_stats = preprocess_player_stats(df_stats, df_players, df_matchups)
            
            # Waivers
            if args.waivers:
                waivers_data = get_waivers(processed_stats, rostered_ids)
                data['waivers'] = waivers_data
            
            # Predictions
            if args.predictions:
                # Encode once globally
                for col in ['player_id', 'team', 'opp_clean', 'position']:
                    if col in processed_stats.columns:
                         processed_stats[col + '_code'] = processed_stats[col].astype('category').cat.codes

                all_predictions = []
                
                # Load prediction cache
                cache_path = os.path.join(DATA_DIR, "predictions_cache.json")
                predictions_cache = {}
                if os.path.exists(cache_path):
                    try:
                        with open(cache_path, 'r') as f:
                            cache_data = json.load(f)
                            # Convert to dict keyed by week
                            for pred in cache_data:
                                week = pred.get('week')
                                if week not in predictions_cache:
                                    predictions_cache[week] = []
                                predictions_cache[week].append(pred)
                        print(f"Loaded cached predictions for {len(predictions_cache)} weeks")
                    except Exception as e:
                        print(f"Failed to load prediction cache: {e}")
                
                # Loop from Week 2 to 38 (Full Season)
                start_pred_week = 2 
                end_pred_week = CURRENT_WEEK # Limit to current week (Active data only)
                
                newly_cached_weeks = []
                
                # FORCE REFRESH for the week immediately prior to current week to ensure latest data is used
                force_refresh_week = CURRENT_WEEK - 1
                
                for w in range(start_pred_week, CURRENT_WEEK):
                    # Check if this week is already cached (and not the force refresh week)
                    if w in predictions_cache and w != force_refresh_week:
                        print(f"Using cached predictions for Week {w}")
                        all_predictions.extend(predictions_cache[w])
                    else:
                        # Generate predictions for this historical week
                        print(f"Regenerating predictions for Week {w} (Cache override or miss)...")
                        preds = make_predictions(processed_stats, w, df_matchups)
                        if preds:
                            all_predictions.extend(preds)
                            predictions_cache[w] = preds
                            newly_cached_weeks.append(w)
                
                # OPTIMIZATION: Train models once for all future weeks
                if CURRENT_WEEK <= end_pred_week:
                    print(f"Training models once for future weeks {CURRENT_WEEK}-{end_pred_week}...")
                    
                    # Define target stats
                    target_stats = ['g', 'kp', 'at', 'sot', 'tkw', 'dis', 'yc', 'rc', 'acnc', 'int', 'clr', 'cos', 'bs', 'aer', 'pkm', 'pkd', 'og', 'gao', 'cs', 'ga', 'sv', 'pks', 'hcs', 'sm']
                    
                    # Train on all data < CURRENT_WEEK
                    train_data = processed_stats[processed_stats.matchweek < CURRENT_WEEK]
                    if not train_data.empty:
                        future_models = train_position_models(train_data, target_stats)
                        print(f"Trained {len(future_models)} position-specific models")
                        
                        # Now predict for each future week using the same models
                        for w in range(CURRENT_WEEK, end_pred_week + 1):
                            preds = make_predictions(processed_stats, w, df_matchups, pretrained_models=future_models)
                            if preds:
                                all_predictions.extend(preds)
                    else:
                        print("Warning: No training data available for future predictions")
                
                # Save updated cache
                if newly_cached_weeks:
                    try:
                        # Flatten cache for JSON storage
                        cache_list = []
                        for week_preds in predictions_cache.values():
                            cache_list.extend(week_preds)
                        
                        with open(cache_path, 'w') as f:
                            json.dump(cache_list, f)
                        print(f"Cached predictions for weeks: {newly_cached_weeks}")
                    except Exception as e:
                        print(f"Failed to save prediction cache: {e}")
                        
                player_predictions = all_predictions
                data['predictions'] = player_predictions
            
        except Exception as e:
            print(f"Stats Processing/Predictions failed: {e}")
            import traceback
            traceback.print_exc()

    # 4 (Continued). Enrich Matchups with Projections (All Historic)
    # We run this if we ran predictions OR rosters OR matchups, basically if any data changed
    if args.predictions or args.rosters or args.matchups:
        print("Enriching matchups with projections (this may take a while)...")
        enrich_matchups_with_projections(api, matchup_list, player_predictions, start_week=2)


    
    # 5. Advanced Stats
    if args.matchups or args.rosters: # Needs opt_df which comes from rosters
        advanced_stats = calculate_advanced_stats(df_matchups, opt_df)
        data['advanced_stats'] = advanced_stats
    
    # Save Data
    data['last_updated'] = datetime.now().isoformat()
    data['current_week'] = CURRENT_WEEK
    
    def clean_nans(obj):
        """Recursively replace NaN with None for valid JSON serialization"""
        if isinstance(obj, float):
            return None if pd.isna(obj) else obj
        if isinstance(obj, (np.floating, np.integer)):
            return None if pd.isna(obj) else obj.item()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, dict):
            return {k: clean_nans(v) for k, v in obj.items()}
        if isinstance(obj, list) or isinstance(obj, np.ndarray):
            return [clean_nans(v) for v in obj]
        return obj

    # Sanitize data for JSON
    data = clean_nans(data)
    
    with open(os.path.join(DATA_DIR, 'dashboard_data.json'), 'w') as f:
        json.dump(data, f, indent=4)
        
    # NEW: Export stats cache for detailed lineup views
    # Run only if we have stats
    if (args.rosters or args.stats or args.predictions) and not df_stats.empty:
        try:
            # Re-use processed_stats if available, otherwise regenerate
            # Start from clean aggregation to ensure accuracy
            processed_stats_for_cache = preprocess_player_stats(df_stats, df_players, df_matchups)
            processed_stats = processed_stats_for_cache
            
            # CRITICAL FIX: Sort by FPTS ascending so duplicates (e.g. 0.0 and 16.5) result in MAX score winning
            if 'fpts' in processed_stats.columns:
                 processed_stats.sort_values(by=['player_id', 'matchweek', 'fpts'], ascending=[True, True, True], inplace=True)
            
            # Build cache: { "player_id+week": { "G": 1, "A": 0 ... } }
            stats_cache = {}
            target_display_stats = ['fpts', 'g', 'kp', 'at', 'sot', 'tkw', 'dis', 'acnc', 'int', 'clr', 'cos', 'bs', 'aer', 'gao', 'cs', 'sv', 'pks', 'hcs', 'sm', 'yc', 'rc', 'min']
            
            for _, row in processed_stats.iterrows():
                pid = str(row['player_id'])
                wk = int(row['matchweek'])
                key = f"{pid}_{wk}"
                
                # Extract non-zero stats (allow negatives!)
                p_stats = {}
                for s in target_display_stats:
                    if s in row and row[s] != 0:
                        p_stats[s.upper()] = float(row[s]) # Convert to standard float
                
                # Capture Injury Status (if present)
                if 'injured' in row and pd.notna(row['injured']):
                    p_stats['INJURED'] = str(row['injured'])
                        
                stats_cache[key] = p_stats
                
            with open(os.path.join(DATA_DIR, 'stats_cache.json'), 'w') as f:
                json.dump(stats_cache, f, indent=4)
                
        except Exception as e:
            print(f"Stats caching failed: {e}")

    print("Dashboard data updated successfully.")

if __name__ == "__main__":
    main()
