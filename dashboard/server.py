
from flask import Flask, render_template, jsonify, request
import pandas as pd
import json
import os
import sys
import subprocess
from fantraxapi import FantraxAPI
from requests import Session
import pickle

# Fix for Render/Gunicorn import issues: Ensure current directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from chat_agent import MultiAgentChatSystem as ChatAgent

# Import configuration
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

import config

class NanConverterJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        import numpy as np
        if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
            return None
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

app = Flask(__name__)
app.json_encoder = NanConverterJSONEncoder

@app.route('/ping')
def ping():
    return "pong"

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'dashboard_data.json')
STATS_CACHE_FILE = os.path.join(BASE_DIR, 'data', 'stats_cache.json')
ROOT_DIR = os.path.dirname(BASE_DIR)
COOKIE_PATH = os.path.join(ROOT_DIR, "fantraxloggedin.cookie")

# Helper to load data
STATS_MAPPING = {
    5: 'CS', 6: 'GA', 7: 'Sv', 8: 'YC', 9: 'RC', 10: 'PKS',
    11: 'TkW', 12: 'DIS', 13: 'G', 14: 'KP', 15: 'AT', 16: 'Int',
    17: 'CLR', 18: 'CoS', 19: 'AER', 20: 'HCS', 21: 'Sm', 22: 'OG', 23: 'SOT'
}

# START SIMPLE IN-MEMORY CACHE
_DATA_CACHE = None
_STATS_CACHE = None
_LAST_DATA_LOAD = 0
_LAST_STATS_LOAD = 0
# Cache expiry in seconds (e.g., 60s so we don't hammer disk)
CACHE_TTL = 300 

def load_data():
    global _DATA_CACHE, _LAST_DATA_LOAD
    import time
    
    if not os.path.exists(DATA_FILE):
        return {}
        
    mtime = os.path.getmtime(DATA_FILE)
    if _DATA_CACHE is not None and mtime <= _LAST_DATA_LOAD:
        return _DATA_CACHE

    try:
        with open(DATA_FILE, 'r') as f:
            _DATA_CACHE = json.load(f)
            _LAST_DATA_LOAD = mtime # Use file mtime as load time marker
            return _DATA_CACHE
    except:
        return {}

def load_stats_cache():
    global _STATS_CACHE, _LAST_STATS_LOAD
    import time
    
    if not os.path.exists(STATS_CACHE_FILE):
        return {}

    mtime = os.path.getmtime(STATS_CACHE_FILE)
    if _STATS_CACHE is not None and mtime <= _LAST_STATS_LOAD:
        return _STATS_CACHE

    if _STATS_CACHE is not None and mtime <= _LAST_STATS_LOAD:
        return _STATS_CACHE

    try:
        with open(STATS_CACHE_FILE, 'r') as f:
            _STATS_CACHE = json.load(f)
            _LAST_STATS_LOAD = mtime
            return _STATS_CACHE
    except:
        return {}

# Helper to connect to Fantrax (for lineup fetching on demand)
def get_fantrax_api():
    session = Session()
    if os.path.exists(COOKIE_PATH):
        with open(COOKIE_PATH, "rb") as f:
            for cookie in pickle.load(f):
                session.cookies.set(cookie["name"], cookie["value"])
    return FantraxAPI(config.LEAGUE_ID, session=session)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/waivers')
def get_waivers():
    data = load_data()
    return jsonify(data.get('waivers', []))




# Manager Mapping
MANAGER_TO_TEAM = {
    "Varun": "FC VAR",
    "Zach": "Point Loma Parrots",
    "Shawn": "Smip Estonian",
    "Henry": "hdiamondpott",
    "Suda": "Cold FC",
    "Subba": "sduvuuru",
    "Nilay": "Wallalujah FC",
    "Danny": "WayneRooney10",
    "Young": "youngmoon",
    "Arnav": "Arnie-senal",
    "Joseph": "Traderjoe18",
    "Joe": "Traderjoe18",
    "Ari": "Toadenham Frogspur",
    "Isaac": "Estimated Profit",
    "Purvaansh": "FC Purulona",
    "Puru": "FC Purulona",
    "Arnie": "Arnie-senal"
}

# Champions League Schedule
CL_SCHEDULE = {
    6: [("Shawn", "Zach"), ("Suda", "Varun"), ("Nilay", "Danny")],
    11: [("Zach", "Suda"), ("Varun", "Nilay"), ("Danny", "Shawn")],
    16: [("Shawn", "Suda"), ("Zach", "Nilay"), ("Varun", "Danny")],
    21: [("Shawn", "Nilay"), ("Zach", "Varun"), ("Suda", "Danny")],
    26: [("Shawn", "Varun"), ("Zach", "Danny"), ("Suda", "Nilay")]
}

# Cup Config
CUP_ROUNDS = [9, 14, 19, 24, 29, 34]
CUP_QUALIFIERS = [("Henry", "Arnie"), ("Isaac", "Joseph")]
CUP_R1 = [(0, "Danny"), ("Puru", "Subba"), ("Ari", "Young"), (1, "Varun")] # 0/1 refer to Qual Winners
CUP_QF = [(0, "Nilay"), (1, "Shawn"), (2, "Zach"), (3, "Suda")] # Refer to R1 Winners
CUP_SF = [(0, 2), (1, 3)] # Refer to QF Winners. 2 Legs (24 & 29).

@app.route('/api/init')
def get_init_data():
    data = load_data()
    
    cl_standings = calculate_cl_standings(data)
    cup_bracket = calculate_cup_bracket(data)
    
    top_players = []
    try:
        # Load Players Map (PID -> Name)
        players_csv_path = os.path.join(ROOT_DIR, 'df_players.csv')
        player_map = {}
        if os.path.exists(players_csv_path):
             df_p = pd.read_csv(players_csv_path)
             if 'scorerId' in df_p.columns and 'name' in df_p.columns:
                 df_p['scorerId'] = df_p['scorerId'].astype(str)
                 player_map = dict(zip(df_p['scorerId'], df_p['name']))
        
        # Load Stats Cache
        stats_cache = load_stats_cache()
        
        # Aggregate FPTS by Player
        player_scores = {}
        for key, stats in stats_cache.items():
            # Key format: "pid_week" or just "pid" (check keys)
            # Keys in stats_cache are "061vq_1" (pid_week)
            try:
                parts = key.split('_')
                if len(parts) >= 2:
                    pid = parts[0]
                    fpts = stats.get('FPTS', 0.0)
                    if pd.isna(fpts): fpts = 0
                    
                    player_scores[pid] = player_scores.get(pid, 0) + fpts
            except: continue
            
        # Sort by Total Points
        sorted_pids = sorted(player_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Take Top 100 first, then filter for names, slice to 50
        count = 0
        for pid, score in sorted_pids:
            if pid in player_map:
                name = player_map[pid]
                if name and name not in top_players:
                    top_players.append(name)
                    count += 1
            if count >= 50: break
            
        if not top_players:
             # Fallback if cache/csv empty
             top_players = ["Cole Palmer", "Mohamed Salah", "Bukayo Saka", "Erling Haaland"]

    except Exception as e:
        print(f"Error filtering top players: {e}")
        top_players = ["Cole Palmer", "Mohamed Salah", "Bukayo Saka", "Erling Haaland"] # Safe Fallback

    return jsonify({
        'current_week': data.get('current_week', 22),
        'standings': data.get('standings', {}),
        'weeks': list(set(m['week'] for m in data.get('matchups', []))),
        'advanced_stats': data.get('advanced_stats', {}),
        'champions_league': cl_standings,
        'cup_bracket': cup_bracket,
        'top_players': top_players
    })


def calculate_cup_bracket(data):
    matchups = data.get('matchups', [])
    current_week = data.get('current_week', 22)
    
    # Helper to get score
    def get_score(mgr, week):
        team = MANAGER_TO_TEAM.get(mgr)
        if not team: return 0
        for m in matchups:
            if m['week'] == week:
                if m['home_team'] == team: return m['home_score']
                if m['away_team'] == team: return m['away_score']
        return 0

    # Helper to resolve match
    def resolve_match(p1, p2, week, is_aggregate=False, week2=None):
        if not p1 or not p2: return {'p1': p1, 'p2': p2, 's1': 0, 's2': 0, 'winner': None, 'status': 'Scheduled'}
        
        s1 = get_score(p1, week)
        s2 = get_score(p2, week)
        
        if is_aggregate and week2:
            s1 += get_score(p1, week2)
            s2 += get_score(p2, week2)
            final_week = week2
        else:
            final_week = week
            
        status = 'Completed' if final_week < current_week else 'Scheduled' # Simplified status
        winner = None
        if status == 'Completed' or (final_week == current_week and (s1 > 0 or s2 > 0)): # Assuming non-zero means started
            if s1 > s2: winner = p1
            elif s2 > s1: winner = p2
            else: winner = p1 # Tiebreaker? Higher seed? For now random/p1.
            
        return {'p1': p1, 'p2': p2, 's1': s1, 's2': s2, 'winner': winner, 'status': status, 'week': week}

    bracket = {'qual': [], 'r1': [], 'qf': [], 'sf': [], 'final': []}
    
    # Qualifiers (Week 9)
    qual_winners = []
    for p1, p2 in CUP_QUALIFIERS:
        res = resolve_match(p1, p2, 9)
        bracket['qual'].append(res)
        qual_winners.append(res['winner'])
        
    # R1 (Week 14)
    r1_winners = []
    for idx, (p1_source, p2_source) in enumerate(CUP_R1):
        p1 = qual_winners[p1_source] if isinstance(p1_source, int) else p1_source
        p2 = qual_winners[p2_source] if isinstance(p2_source, int) else p2_source
        res = resolve_match(p1, p2, 14)
        bracket['r1'].append(res)
        r1_winners.append(res['winner'])
        
    # QF (Week 19)
    qf_winners = []
    for idx, (p1_source, p2_source) in enumerate(CUP_QF):
        p1 = r1_winners[p1_source] if isinstance(p1_source, int) else p1_source
        p2 = r1_winners[p2_source] if isinstance(p2_source, int) else p2_source
        res = resolve_match(p1, p2, 19)
        bracket['qf'].append(res)
        qf_winners.append(res['winner'])
        
    # SF (Week 24 + 29)
    sf_winners = []
    for idx, (p1_idx, p2_idx) in enumerate(CUP_SF):
        p1 = qf_winners[p1_idx]
        p2 = qf_winners[p2_idx]
        # Aggregate
        res = resolve_match(p1, p2, 24, is_aggregate=True, week2=29)
        bracket['sf'].append(res)
        sf_winners.append(res['winner'])
        
    # Final (Week 34)
    if len(sf_winners) >= 2:
        res = resolve_match(sf_winners[0], sf_winners[1], 34)
        bracket['final'].append(res)
        
    return bracket

def calculate_cl_standings(data):
    # Participants: All managers in schedule
    participants = set()
    for w, matches in CL_SCHEDULE.items():
        for m1, m2 in matches:
            participants.add(m1)
            participants.add(m2)
            
    # Initialize
    standings = {mgr: {"team": MANAGER_TO_TEAM.get(mgr), "manager": mgr, "w": 0, "d": 0, "l": 0, "pts": 0, "fpts": 0.0} for mgr in participants}
    
    matchups = data.get('matchups', [])
    current_week = data.get('current_week', 99)
    
    for week, matches in CL_SCHEDULE.items():
        if week >= current_week: continue 
        
        # Build lookup for this week's scores
        week_data = {}
        for m in matchups:
            if m['week'] == week:
                week_data[m['home_team']] = m['home_score']
                week_data[m['away_team']] = m['away_score']
                
        for mgr1, mgr2 in matches:
            t1 = MANAGER_TO_TEAM.get(mgr1)
            t2 = MANAGER_TO_TEAM.get(mgr2)
            
            s1 = week_data.get(t1)
            s2 = week_data.get(t2)
            
            if s1 is None or s2 is None: continue
            
            # Update Stats
            standings[mgr1]['fpts'] += s1
            standings[mgr2]['fpts'] += s2
            
            if s1 > s2:
                standings[mgr1]['w'] += 1
                standings[mgr1]['pts'] += 3
                standings[mgr2]['l'] += 1
            elif s2 > s1:
                standings[mgr2]['w'] += 1
                standings[mgr2]['pts'] += 3
                standings[mgr1]['l'] += 1
            else:
                standings[mgr1]['d'] += 1
                standings[mgr1]['pts'] += 1
                standings[mgr2]['d'] += 1
                standings[mgr2]['pts'] += 1

    # Sort
    res = list(standings.values())
    res.sort(key=lambda x: (x['pts'], x['fpts']), reverse=True)
    return res


@app.route('/api/matchups/<int:week>')
def get_matchups(week):
    data = load_data()
    all_matchups = data.get('matchups', [])
    week_matchups = [m for m in all_matchups if m['week'] == week]
    
    # Build lookup for team scores and IDs this week
    team_data = {} # Name -> {id, score}
    for m in week_matchups:
        team_data[m['home_team']] = {'id': m['home_team_id'], 'score': m['home_score']}
        team_data[m['away_team']] = {'id': m['away_team_id'], 'score': m['away_score']}
    
    cl_matchups = []
    if week in CL_SCHEDULE:
        for mgr1, mgr2 in CL_SCHEDULE[week]:
            team1 = MANAGER_TO_TEAM.get(mgr1)
            team2 = MANAGER_TO_TEAM.get(mgr2)
            
            if team1 in team_data and team2 in team_data:
                t1_dat = team_data[team1]
                t2_dat = team_data[team2]
                
                cl_matchups.append({
                    "matchupId": f"CL_{week}_{t1_dat['id']}_{t2_dat['id']}",
                    "week": week,
                    "home_team": team1,
                    "home_team_id": t1_dat['id'],
                    "home_score": t1_dat['score'],
                    "away_team": team2,
                    "away_team_id": t2_dat['id'],
                    "away_score": t2_dat['score'],
                    "is_cl": True
                })

    cup_matchups = []
    # Check if this is a Cup Week (including SF 2nd leg week 29)
    if week in CUP_ROUNDS or week == 29:
        bracket = calculate_cup_bracket(data)
        # Flatten bracket
        all_cup_matches = []
        for r in bracket.values():
            all_cup_matches.extend(r)
            
        for m in all_cup_matches:
            p1 = m['p1']
            p2 = m['p2']
            if not p1 or not p2: continue 
            
            # Determine if match applies to this week
            active = False
            d_s1 = m['s1']
            d_s2 = m['s2']
            
            # Standard Rounds
            if m['week'] == week and week not in [24, 29]:
                active = True
                
            # Semi-Finals (Aggregated)
            # Leg 1 (Week 24)
            if week == 24 and m['week'] == 24:
                active = True
                # Show Leg 1 Score only
                t1 = MANAGER_TO_TEAM.get(p1)
                t2 = MANAGER_TO_TEAM.get(p2)
                if t1 in team_data: d_s1 = team_data[t1]['score']
                if t2 in team_data: d_s2 = team_data[t2]['score']
                
            # Leg 2 (Week 29) - Match defined at week 24 in bracket
            if week == 29 and m['week'] == 24:
                active = True
                # Show Aggregate Score (default in m['s1'])
                
            if active:
                t1 = MANAGER_TO_TEAM.get(p1)
                t2 = MANAGER_TO_TEAM.get(p2)
                
                if t1 in team_data and t2 in team_data:
                    mid = f"CUP_{week}_{team_data[t1]['id']}_{team_data[t2]['id']}"
                    cup_matchups.append({
                        "matchupId": mid,
                        "week": week,
                        "home_team": t1,
                        "home_team_id": team_data[t1]['id'],
                        "home_score": d_s1,
                        "away_team": t2,
                        "away_team_id": team_data[t2]['id'],
                        "away_score": d_s2,
                        "is_cup": True,
                        "manager_home": p1,
                        "manager_away": p2
                    })

    return jsonify({
        'standard': week_matchups,
        'champions_league': cl_matchups,
        'cup': cup_matchups
    })


@app.route('/api/lineup/<matchup_id>')
def get_lineup(matchup_id):
    # Format: "{week}_{home_id}_{away_id}" OR "CL_{week}_{home_id}_{away_id}"
    try:
        parts = matchup_id.split('_')
        if parts[0] in ['CL', 'CUP']:
            week = int(parts[1])
            team1_id = parts[2]
            team2_id = parts[3]
        else:
            week = int(parts[0])
            team1_id = parts[1]
            team2_id = parts[2]
            
        data = load_data()
        stats_cache = load_stats_cache()
        
        predictions = data.get('predictions', []) 
        # Filter predictions for the specific week of the matchup
        week_predictions = [p for p in predictions if p.get('week') == week]
        pred_map = {str(p['player_id']): p for p in week_predictions}
        
        print(f"DEBUG: Week {week}, Found {len(week_predictions)} predictions, pred_map has {len(pred_map)} entries")
        if len(pred_map) > 0:
            sample_ids = list(pred_map.keys())[:3]
            print(f"DEBUG: Sample player IDs in pred_map: {sample_ids}")
        
        api = get_fantrax_api()
        from fantraxapi.api import request, Method
        
        def fetch_team_roster(tid, period):
            try:
                # Fetch roster for specific period
                # roster_data = request(api, Method("getTeamRosterInfo", teamId=tid, period=period))
                roster_data = request(api, Method("getTeamRosterInfo", teamId=tid, period=period))
                
                players = []
                if 'tables' in roster_data and isinstance(roster_data['tables'], list):
                    for i, table in enumerate(roster_data['tables']):
                        rows = table.get('rows', [])
                        
                        for row in rows:
                            scorer = row.get('scorer', {})
                            pid = str(scorer.get('scorerId', ''))
                            
                            # Get stats from cache
                            cache_key = f"{pid}_{period}"
                            p_stats = stats_cache.get(cache_key, {})
                            
                            # DEBUG: Trace Rayan Cherki or specific IDs
                            if pid == '06v07' or 'Cherki' in str(scorer.get('name')):
                                print(f"DEBUG_ROSTER: Found Cherki (ID {pid}). Cache Key: {cache_key}")
                                print(f"DEBUG_ROSTER: Cache Hit? {cache_key in stats_cache}")
                                print(f"DEBUG_ROSTER: Stats Data: {p_stats}")
                                print(f"DEBUG_ROSTER: from stats_cache keys sample: {list(stats_cache.keys())[:5]}")
                            
                            # Revert to using cached FPTS (which is actual weekly score if cache is up to date)
                            # The previous attempt to use Roster Cells failed because cells[2] is PPG, not Weekly Score.
                            # Without a reliable "Weekly Score" column in the default roster view, we must trust the stats cache.
                            score = p_stats.get('FPTS', 0.0) # Use .get() explicitly just in case .pop() was risky if used multiple times? 
                            # Wait, previous code used .pop(). modifying the dict in place??
                            # stats_cache is mutable! If we POP, it is gone for the next player or next call if cache is global/shared ref!
                            # CRITICAL BUG CHECK: "p_stats.pop('FPTS', 0.0)" REMOVES it from the dictionary.
                            # If stats_cache is loaded once and shared, the first request removes it, subsequent requests get default 0.0.
                            # I MUST CHANGE .pop() to .get()! 
                            
                            # Original line: score = p_stats.pop('FPTS', 0.0)
                            # This was DESTRUCTIVE.
                            score = p_stats.get('FPTS', 0.0)
                            game_info = ""
                            is_started = False
                            if 'cells' in row and len(row['cells']) > 0:
                                try:
                                    game_info = row['cells'][0]['content']
                                    if "<br/>" in game_info or "F" in game_info or "HT" in game_info or "'" in game_info:
                                        is_started = True
                                    # Correction: If score > 0, we can assume started? No, user complained about bad values.
                                    # Let's rely strictly on game info string for is_started status.
                                except: pass
                                
                            # Sanitize score
                            if pd.isna(score): score = 0.0
                            
                            # Sanitize stats dict
                            safe_stats = {}
                            for k, v in p_stats.items():
                                try:
                                    if pd.isna(v): safe_stats[k] = 0
                                    else: safe_stats[k] = v
                                except: safe_stats[k] = 0
                                
                            # Sanitize prediction
                            pred = pred_map.get(pid, None)
                            
                            # Default to 0 values if no prediction exists (e.g. no history)
                            safe_pred = {'fpts': 0.0, 'score': 0.0}
                            
                            if pred:
                                safe_pred = {}
                                for k, v in pred.items():
                                    try:
                                        if isinstance(v, float) and pd.isna(v): safe_pred[k] = 0
                                        else: safe_pred[k] = v
                                    except: safe_pred[k] = v

                            player_obj = {
                                'name': scorer.get('name'),
                                'position': scorer.get('posShortNames'),
                                'team': scorer.get('teamShortName'),
                                'player_id': pid,
                                'status': row.get('statusId'), # 1=Active, 2=Reserve
                                'prediction': safe_pred,
                                'score': score,               # Use CACHED score
                                'stats': safe_stats,
                                'game_info': game_info,
                                'is_started': is_started
                            }
                            
                            players.append(player_obj)
                return players
            except Exception as e:
                print(f"Error fetching roster for {tid}, period {period}: {e}")
                # Log to file for debugging
                with open("server_error.log", "a") as f:
                    import traceback
                    f.write(f"Error fetching roster for {tid}, period {period}: {e}\n")
                    traceback.print_exc(file=f)
                return []

        # We use the week from the matchup ID
        home_roster = fetch_team_roster(team1_id, week)
        away_roster = fetch_team_roster(team2_id, week)
        
        # We need team names too, maybe from matchup list?
        # For now, let frontend handle names or pass generic.
        # or find in dashboard_data
        home_name = "Home Team"
        away_name = "Away Team"
        
        home_score = 0
        away_score = 0
        matchups = data.get('matchups', [])
        for m in matchups:
            if str(m['matchupId']) == str(matchup_id):
                home_name = m['home_team']
                away_name = m['away_team']
                home_score = m.get('home_score', 0)
                away_score = m.get('away_score', 0)
                break

        return jsonify({
            'home_team': {'name': home_name, 'roster': home_roster},
            'away_team': {'name': away_name, 'roster': away_roster},
            'home_score': home_score,
            'away_score': away_score
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Global Agent Instance for State Persistence
GLOBAL_CHAT_AGENT = None

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages from the AI assistant."""
    global GLOBAL_CHAT_AGENT
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Initialize chat agent if needed
        if GLOBAL_CHAT_AGENT is None:
            print("Initializing Global Chat Agent...")
            data_dir = os.path.join(BASE_DIR, 'data')
            GLOBAL_CHAT_AGENT = ChatAgent(api_key=config.GEMINI_API_KEY, data_dir=data_dir)
        
        # Process query
        response = GLOBAL_CHAT_AGENT.process_query(message)
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}',
            'type': 'error'
        }), 500


@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    """Clear the chat history."""
    global GLOBAL_CHAT_AGENT
    try:
        if GLOBAL_CHAT_AGENT:
            GLOBAL_CHAT_AGENT.clear_history()
            print("Chat history cleared.")
            
        return jsonify({'success': True, 'message': 'Chat history cleared'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500



@app.route('/api/player/<player_id>')
def get_player_api(player_id):
    print(f"API Request for {player_id}")
    try:
        # 1. Load Player Metadata
        players_csv_path = os.path.join(ROOT_DIR, 'df_players.csv')
        profile = {"name": "Unknown", "team": "-", "position": "-"}
        
        if os.path.exists(players_csv_path):
            try:
                df_p = pd.read_csv(players_csv_path)
                # Ensure ID is string
                df_p['scorerId'] = df_p['scorerId'].astype(str)
                row = df_p[df_p['scorerId'] == str(player_id)]
                if not row.empty:
                    r = row.iloc[0]
                    profile = {
                        "name": str(r.get('name', 'Unknown')),
                        "team": str(r.get('teamShortName', '-')),
                        "position": str(r.get('posShortNames', '-'))
                    }
            except Exception as e:
                print(f"Error loading player metadata: {e}")

        # 2. Get Stats from Cache & Predictions
        print("Loading stats cache...")
        stats_cache = load_stats_cache()
        print("Loading data cache...")
        data = load_data()
        predictions = data.get('predictions', [])
        print("Data loaded. processing...")
        
        # Build Pred Map & Opp Map: (player_id, week) -> fpts, opp
        pred_map = {}
        opp_map = {}
        for p in predictions:
            try:
                if str(p.get('player_id')) == str(player_id):
                    # Ensure week is int for matching
                    w_val = int(p.get('week'))
                    pred_map[w_val] = float(p.get('predicted_fpts', 0.0))
                    opp_map[w_val] = str(p.get('opp', '-'))
            except: continue

        game_log = []
        season_totals = {}
        
        # We iterate weeks 1 to 38
        for w in range(1, 39):
            key = f"{player_id}_{w}"
            has_stats = key in stats_cache
            
            week_stats = stats_cache.get(key, {})
            week_pred = pred_map.get(w, 0.0)
            week_opp = opp_map.get(w, '-')
            
            if has_stats:
                # Add to log
                log_entry = {"week": w, "projected_fpts": week_pred, "opp": week_opp, **week_stats}
                game_log.append(log_entry)

                # Add to totals
                for k, v in week_stats.items():
                    if isinstance(v, (int, float)):
                        season_totals[k] = season_totals.get(k, 0) + v
        
        # Sort log by week descending
        game_log.sort(key=lambda x: x['week'], reverse=True)
        
        return jsonify({
            "profile": profile,
            "season_stats": season_totals,
            "game_log": game_log
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

# Background Updater Code
import threading
import time
import subprocess
import sys # Import sys for sys.executable

def run_background_updates():
    """Runs data update script every 5 minutes."""
    while True:
        try:
            # Run the update script as a subprocess
            # We must include --matchups to ensure live scores update alongside stats!
            cmd = [sys.executable, os.path.join(BASE_DIR, '..', 'scripts', 'update_data.py'), '--stats', '--matchups']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"[Background] Update successful at {time.strftime('%H:%M:%S')}")
                # Optional: Force reload global data if we were caching it in memory
                # But currently server reads from JSON on each request or has specific caches.
                # If we rely on in-memory globals like global_df_stats, we might need a refresh mechanism here.
                # For now, simplistic approach: The subprocess updates the JSON files. 
                # The endpoints read from JSON or their own caches.
                
                # IMPORTANT: Clear internal server function caches if they exist
                # But 'get_player_api' uses 'stats_cache' which is loaded inside the function? 
                # No, 'stats_cache' in 'get_player_api' is a global or loaded?
                # Let's check 'get_player_api'.
            else:
                print(f"[Background] Update FAILED: {result.stderr}")
                
        except Exception as e:
            print(f"[Background] Exception in update thread: {e}")
            
        # Wait 5 minutes
        time.sleep(300)

if __name__ == '__main__':
    # Ensure data exists on startup using the script we just made
    if not os.path.exists(DATA_FILE):
        print("Initializing data...")
        # subprocess.run(["python3", os.path.join(ROOT_DIR, "scripts", "update_data.py")])
        print("Skipping auto-update to prevent blocking. Verify data exists manually.")
    
    # Start background thread
    updater_thread = threading.Thread(target=run_background_updates, daemon=True)
    updater_thread.start()
    
    PORT = 8000
    print(f"Starting server on port {PORT} with Live Updates enabled...")
    app.run(host='0.0.0.0', port=PORT, threaded=True, use_reloader=False)
