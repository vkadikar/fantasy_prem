import os
import json
import subprocess
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
import traceback
from typing import Dict, Any, List, Optional
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def calculate_historical_standings(matchups: List[Dict], target_week: int, scoring_type: str = 'standard') -> pd.DataFrame:
    """
    Calculate standings up to a specific week with optional scoring type.
    scoring_type: 'standard', 'optimal', 'median'
    """
    if not matchups:
        return pd.DataFrame()

    # Filter matchups up to target week
    relevant = [m for m in matchups if m['week'] <= target_week]
    
    teams = {}
    
    for m in relevant:
        h_team = m['home_team']
        a_team = m['away_team']
        
        # Standard Stats
        h_score = m['home_score']
        a_score = m['away_score']
        
        # Determine Points Calculation based on Type
        h_pts = 0
        a_pts = 0
        h_w, h_d, h_l = 0, 0, 0
        a_w, a_d, a_l = 0, 0, 0
        
        # --- SCORING TYPE LOGIC ---
        if scoring_type == 'optimal':
            # Use computed optimal scores if available, else 0
            # Note: requires 'home_optimal_score' in matchups (populated by update_data.py)
            h_score_active = m.get('home_optimal_score', 0)
            a_score_active = m.get('away_optimal_score', 0)
            
            # Recalculate result based on optimal scores
            if h_score_active > a_score_active:
                h_pts, h_w, a_l = 3, 1, 1
            elif a_score_active > h_score_active:
                a_pts, a_w, h_l = 3, 1, 1
            else:
                h_pts, a_pts, h_d, a_d = 1, 1, 1, 1
                
            # Override for display
            h_score_display = h_score_active
            a_score_display = a_score_active
            
        elif scoring_type == 'median':
            # Median Standings: Points purely from beating median? 
            # Or Standard + Median Bonus? "League Median Standings" usually implies Top Half = Win.
            # We stored 'home_beat_median' in update_data.py
            
            # The logic usually is 1 point for beating median? Or 3pts?
            # Standard "Vs Median" leagues often assign 3pts for H2H Win + 3pts for Median Win (Total 6).
            # BUT the user asked for "Optimal Standings" and "Median Standings" as separate tables.
            # "Median Standings" in the dashboard typically means: Wins vs Median check only.
            
            h_beat = m.get('home_beat_median', False)
            a_beat = m.get('away_beat_median', False)
            h_thresh = m.get('median_threshold', 0)
            
            # Assign 3 pts for "Win" vs Median? Or 1? 
            # In update_data.py median_standings, we did (Win vs Median)*3 + (Draw)*1.
            # So if you beat median, you get a "Win" (3pts).
            
            if h_beat: 
                h_pts, h_w = 3, 1
            elif h_score == h_thresh and h_thresh > 0:
                h_pts, h_d = 1, 1
            else:
                h_l = 1
                
            if a_beat:
                a_pts, a_w = 3, 1
            elif a_score == h_thresh and h_thresh > 0:
                a_pts, a_d = 1, 1
            else:
                a_l = 1
            
            h_score_display = h_score
            a_score_display = a_score
            
        else:
            # STANDARD
            if h_score > a_score:
                h_pts, h_w, a_l = 3, 1, 1
            elif a_score > h_score:
                a_pts, a_w, h_l = 3, 1, 1
            else:
                h_pts, a_pts, h_d, a_d = 1, 1, 1, 1
                
            h_score_display = h_score
            a_score_display = a_score
            
            
        # Init if needed
        if h_team not in teams: teams[h_team] = {'team': h_team, 'points': 0, 'w': 0, 'd': 0, 'l': 0, 'fpts_for': 0.0, 'fpts_against': 0.0}
        if a_team not in teams: teams[a_team] = {'team': a_team, 'points': 0, 'w': 0, 'd': 0, 'l': 0, 'fpts_for': 0.0, 'fpts_against': 0.0}
        
        # Update
        teams[h_team]['points'] += h_pts
        teams[h_team]['w'] += h_w
        teams[h_team]['d'] += h_d
        teams[h_team]['l'] += h_l
        teams[h_team]['fpts_for'] += h_score_display
        teams[h_team]['fpts_against'] += a_score_display # In median, this is kinda meaningless or just opponent score
        
        teams[a_team]['points'] += a_pts
        teams[a_team]['w'] += a_w
        teams[a_team]['d'] += a_d
        teams[a_team]['l'] += a_l
        teams[a_team]['fpts_for'] += a_score_display
        teams[a_team]['fpts_against'] += h_score_display

    df = pd.DataFrame(list(teams.values()))
    if not df.empty:
        df['record'] = df.apply(lambda x: f"{int(x['w'])}-{int(x['d'])}-{int(x['l'])}", axis=1)
        df = df.sort_values(by=['points', 'fpts_for'], ascending=[False, False])
        df['rank'] = range(1, len(df) + 1)
        
    return df


class MCPManager:
    """Manages connection to the MCP Server."""
    def __init__(self, script_path):
        self.script_path = script_path
        
    def call_tool(self, tool_name, **kwargs):
        """
        Executes a tool on the MCP server via subprocess.
        To avoid complex async/IPC in this simple script, we'll run a one-off command.
        """
        # Simplified JSON-RPC Request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": f"tools/call",
            "params": {
                "name": tool_name,
                "arguments": kwargs
            }
        }
        
        try:
            # Start the server process active
            proc = subprocess.Popen(
                [sys.executable, self.script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Send Initialization (Required by MCP protocol)
            init_req = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "AntigravityClient", "version": "1.0"}
                }
            }
            
            # Send Init
            proc.stdin.write(json.dumps(init_req) + "\n")
            proc.stdin.flush()
            
            # Read Init Response
            while True:
                line = proc.stdout.readline()
                if not line: break
                try:
                    resp = json.loads(line)
                    if resp.get('id') == 0:
                        break # Init done
                except:
                    continue
                    
            # Send Initialized Notification
            proc.stdin.write(json.dumps({
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }) + "\n")
            proc.stdin.flush()
            
            # Send Tool Call
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
            
            # Read Tool Response
            result = None
            while True:
                line = proc.stdout.readline()
                if not line: break
                try:
                    resp = json.loads(line)
                    if resp.get('id') == 1:
                        if 'error' in resp:
                            return f"MCP Error: {resp['error']['message']}"
                        result = resp.get('result', {})
                        break
                except:
                   continue
            
            proc.terminate()
            
            # Extract content from result
            if result and 'content' in result:
                # FastMCP returns content list
                text_content = [c['text'] for c in result['content'] if c['type'] == 'text']
                return "\n".join(text_content)
                
            return "No content returned."
            
        except Exception as e:
            return f"Failed to call MCP tool: {str(e)}"


class MultiAgentChatSystem:
    """Multi-agent chat system with Planner, Code Writer, and Error Corrector agents."""
    
    # Comprehensive data schema based on actual data inspection
    DATA_SCHEMA = f"""
CURRENT CONTEXT:
- CURRENT_WEEK: {config.CURRENT_WEEK} (the next unplayed gameweek)
- Historical weeks: 1 through {config.CURRENT_WEEK - 1} (completed)
- Future weeks: {config.CURRENT_WEEK} through 38 (upcoming/predicted)
- When users ask about "this week" or "current week", they mean week {config.CURRENT_WEEK}
- Actual stats (stats_cache) only available for weeks 1-{config.CURRENT_WEEK - 1}
- ROSTERS (lineups) ARE AVAILABLE for the Current Week ({config.CURRENT_WEEK})!
- Predictions available for all weeks 2-38

Here are the teams in the fantasy league and their managers:
| Manager | Team Name |
| :--- | :--- |
| Arnav (Arnie) | Arnie-senal |
| Ari | Toadenham Frogspur |
| Danny | WayneRooney10 |
| Henry | hdiamondpott |
| Isaac | Estimated Profit |
| Joseph (Joe) | Traderjoe18 |
| Nilay | Wallalujah FC |
| Purvaansh (Puru) | FC Purulona |
| Shawn | Smip Estonian |
| Subba | sduvuuru |
| Suda | Cold FC |
| Varun | FC VAR |
| Young | youngmoon |
| Zach | Point Loma Parrots |

AVAILABLE DATA:

1. team_details: dict of team metadata
   Key: team_id (str)
   Value: {{ 'team': 'Team Name', 'manager': 'Manager Name', 'logo': 'url' }}
   Access: Use this to map managers (e.g. "Ari", "Suda") to their teams.


2. standings: dict with keys ['standard', 'median', 'optimal']

   Each value is a LIST of team dicts with structure:
   {{
     'team': str,           # Team name
     'rank': int,           # Current rank
     'points': int,         # League points (3 per win, 1 per draw)
     'win': int, 'draw': int, 'loss': int,
     'record': str,         # Format: "W-D-L" (e.g. "15-0-7")
     'fpts_for': float,     # Total fantasy points scored
     'fpts_against': float  # Total fantasy points conceded
   }}
    Access: standings['standard'] returns LIST
    Example: max(standings['standard'], key=lambda x: x['fpts_for'])
    
    CRITICAL: 'standings' ONLY contains CURRENT week data!
    To look up HISTORICAL standings, you MUST use the PRE-LOADED function `calculate_historical_standings(matchups, target_week, scoring_type)`.
    
    Arguments:
    - target_week: int (e.g. 10)
    - scoring_type: str ('standard', 'optimal', 'median') [Default: 'standard']
    
    IMPORTANT: Historical 'optimal' and 'median' data IS AVAILABLE. Use the flag to access it.
    
    ```python
    # Example 1: Standard Standings Week 10
    df = calculate_historical_standings(matchups, 10)
    
    # Example 2: Optimal Standings Week 21 (Hypothetical: if EVERY team played their perfect lineup)
    df_opt = calculate_historical_standings(matchups, 21, scoring_type='optimal')
    
    # Example 3: Median Standings Week 5 (Wins vs League Median)
    df_med = calculate_historical_standings(matchups, 5, scoring_type='median')
    ```

3. matchups: list of matchup dicts
   Structure:
   {{
     'week': int,                    # Week number (1 through {config.CURRENT_WEEK-1})
     'matchupId': str,
     'home_team': str, 'away_team': str,
     'home_team_id': str, 'away_team_id': str,
     'home_score': float, 'away_score': float
   }}
   Example: [m for m in matchups if m['week'] == 15]

4. predictions: list of player prediction dicts
   Structure:
   {{
     'player_id': str,
     'player_name': str,
     'position': str,          # Player position: 'G' (Goalkeeper), 'D' (Defender), 'M' (Midfielder), 'F' (Forward)
     'team': str,              # 3-letter team code (e.g. 'ARS', 'MCI')
     'predicted_fpts': float,  # AI-predicted fantasy points
     'week': int,              # Week number for this prediction
     'opp': str                # Opponent team code
   }}
   Example: sorted(predictions, key=lambda x: x['predicted_fpts'], reverse=True)[:10]
   Example by position: [p for p in predictions if p['position'] == 'F']  # All forwards
   
   PREDICTION ERROR ANALYSIS:
   To compare predictions vs actual performance, join with stats_cache:
   ```python
   # 1. Get predictions for a specific week
   week_preds = [p for p in predictions if p['week'] == 15]
   
   # 2. Join with actual stats from stats_cache
   errors = []
   for pred in week_preds:
       key = f"{{pred['player_id']}}_{{pred['week']}}"
       actual_stats = stats_cache.get(key, {{}})
       actual_fpts = actual_stats.get('FPTS', 0)
       
       errors.append({{
           'player_name': pred['player_name'],
           'predicted': pred['predicted_fpts'],
           'actual': actual_fpts,
           'error': actual_fpts - pred['predicted_fpts'],  # Positive = underestimated
           'abs_error': abs(actual_fpts - pred['predicted_fpts'])
       }})
   
   # 3. Calculate metrics
   df = pd.DataFrame(errors)
   mae = df['abs_error'].mean()  # Mean Absolute Error
   rmse = (df['error'] ** 2).mean() ** 0.5  # Root Mean Square Error
   ```
   Access: predictions returns LIST with ~500 entries per week


5. advanced_stats: dict with keys ['team_stats', 'superlatives', 'weekly_extremes']
   
   team_stats: list of dicts
   {{
     'team': str,
     'form': str,              # Last 5 results: "WLLWL" format
     'last_5_avg': float,      # Average score in last 5 weeks
     'std_dev': float,         # Standard deviation (consistency)
     'min_score': float, 'max_score': float,
     'total_pa': float,        # Total points against
     'weekly_trend': [         # List of all weekly scores
       {{'week': int, 'score': float}},
       ...
     }}
   
   weekly_extremes: list of dicts
   {{
     'week': int,
     'high_team': str, 'high_score': float,
     'low_team': str, 'low_score': float
   }}
    
6. waivers: list of dicts (available free agents)
    Structure:
    {{
        'player_id': str,
        'player_name': str,
        'team': str,
        'position': str,
        'fpts': float,            # Total fantasy points
        'fpts_per_game': float,
        'fpts_per_90': float,
        'fpts_per_90': float,
        'minutes': int,
        'gp': int,                # Games played
        'injured': str,           # Injury Status: 'Out', 'GTD', 'Available' (Crucial for Waiver decisions)
        # Plus all stats per 90 and per game:
        # g, kp, at (assists), sot, tkw, dis, int, clr, aer, etc.
        # e.g. 'g_per_90', 'tkw_per_game'
    }}
    Example: sorted(waivers, key=lambda x: x['fpts'], reverse=True)[:5]

7. stats_cache: dict of player weekly stats
   Key format: 'player_id_week' (e.g. '04ge7_15')
   Value: dict with player stats for that week
   {{
     'FPTS': float,    # Fantasy points
     'G': int,         # Goals scored
     'AT': int,        # Assists
     'SOT': int,       # Shots on target
     'KP': int,        # Key passes (assist to a shot)
     'TKW': int,       # Tackles won
     'INT': int,       # Interceptions
     'CLR': int,       # Clearances
     'BS': int,        # Blocked shots
     'AER': int,       # Aerials won
     'CS': int,        # Clean sheet (0 or 1)
     'SV': int,        # Saves (only relevant for goalkeepers)
     'GAO': int,       # Goals against (only relevant for goalkeepers and defenders)
     'YC': int,        # Yellow cards
     'RC': int,        # Red cards
     'MIN': int,       # Minutes played (0-90)
     'INJURED': str,   # Injury Status: 'Out', 'GTD', 'Available' (Current Week Only)
     'ACNC': int,      # Accurate crosses (non corners)
     'COS': int,       # Successful dribbles
     'DIS': int,       # Dispossessed
     'HCS': int,       # High contests succeeded
     'PKS': int,       # Penalty kicks saved (only relevant for goalkeepers)
     'SM': int,        # Smothers (only relevant for goalkeepers)
   }}   
   
   IMPORTANT - Getting Player Names:
   stats_cache only has player_id, NOT player names.
   To get player names, use predictions data which has player_id and player_name.
   
   Example - Top goal scorers with names:
   ```python
   # 1. Aggregate goals by player_id
   player_goals = {{}}
   for key, stats in stats_cache.items():
       # Use rsplit to handle IDs safely (just in case)
       try:
           player_id = key.rsplit('_', 1)[0]
           goals = stats.get('G', 0)
           player_goals[player_id] = player_goals.get(player_id, 0) + goals
       except: continue
   
   # 2. Use global 'players' dict for names (COMPLETE list)
   # (predictions only has active players)
   
   # 3. Combine into DataFrame
   data = []
   for player_id, total_goals in player_goals.items():
       name = players.get(player_id, player_id) # Safe lookup
       data.append({{
           'player_name': name,
           'total_goals': total_goals
       }})
   
   df = pd.DataFrame(data)
   if not df.empty:
       result = df.nlargest(10, 'total_goals')
   else:
       result = "No goal data found."
   ```

8. players: dict of all player ids to names
   Key: player_id (str)
   Value: player_name (str)
   Access: players.get('04ge7') -> 'Bukayo Saka'
   
   HELPER FUNCTION: `find_player(name_str)` returns `player_id` (or None).
   Use this instead of iterating manually!
   Example: `pid = find_player("Saka")` -> Returns ID for Bukayo Saka.

9. roster_data: dict of weekly rosters (who played for who)
   Key format: String(Week) -> String(TeamID) -> List of Dicts
   Structure:
   {{
     '12': {{
       '805xxx': [{{'id': '04ge7', 'pos': 'M', 'status': 'Starter'}}, {{'id': '99abc', 'pos': 'F', 'status': 'Bench'}}, ...],
       ...
     }},
     ...
   }}
   
   Example - Who played for 'Varun' in Week 12?
   ```python
   # 1. Find Varun's team ID
   varun_team_id = next((t['id'] for t in team_details.values() if 'Varun' in t['manager']), None)
   
   # 2. Get Roster for Week 12
   roster = roster_data.get('12', {{}}).get(varun_team_id, [])
   
   # 3. Join with Names (from players dict) and Stats (from stats_cache)
   
   rows = []
   for p in roster:
       pid = p['id']
       name = players.get(pid, 'Unknown Player')
       
       # Get stats for that specific week
       stats_key = f"{{pid}}_12"
       stats = stats_cache.get(stats_key, {{}})
       fpts = stats.get('FPTS', 0)
       
       rows.append({{'Name': name, 'Pos': p['pos'], 'Status': p.get('status', 'Starter'), 'FPTS': fpts}})
       
   result = pd.DataFrame(rows)
   ```

CRITICAL RULES:
- standings['standard'] is a LIST, not dict - use list operations
- For DataFrames: NEVER 'if df:' - use 'if not df.empty:'
- For visualizations: create plotly.express figure, store in 'result'
- DO NOT call .to_html() or .show() - just return the figure object
- Example: result = px.bar(df, x='team', y='score')
- EMPTY DATA CHECK: If your DataFrame is empty, DO NOT return a figure. Return a string explaining why.
  - Correct: `if df.empty: result = "No data found."`
  - Wrong: `result = px.line(df, ...)` (Produces empty shell)

10. EXTERNAL TOOLS:
    `search_reddit(query: str, limit: int = 5)` -> str
    - Searches Reddit (r/FantasyPL, r/PremierLeague) for recent discussions.
    - Use this for QUALITATIVE analysis: "What are fans saying about Saka?", "Is Isak essential?"
    - Returns a string payload of thread titles and comments.
    - Example: `info = search_reddit("Saka injury")`
"""

    def __init__(self, api_key: str, data_dir: str = None):
        """Initialize the multi-agent system."""
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), 'data')
        
        self.data_dir = data_dir
        self.api_key = api_key
        self.flash_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        self.pro_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
        
        # Memory
        self.conversation_history = []  # List of {'role': 'user'|'model', 'content': str}
        
        # Load data
        self.data = self._load_data()
        
        # Initialize MCP Manager (point to mcp_server.py)
        root_dir = os.path.dirname(os.path.dirname(self.data_dir))
        mcp_script = os.path.join(root_dir, 'mcp_server.py')
        self.mcp = MCPManager(mcp_script)
    
    def _load_data(self) -> Dict[str, Any]:
        """Load all available data."""
        data = {}
        
        # Load dashboard data
        dashboard_file = os.path.join(self.data_dir, 'dashboard_data.json')
        if os.path.exists(dashboard_file):
            with open(dashboard_file, 'r') as f:
                dashboard = json.load(f)
                data['matchups'] = dashboard.get('matchups', [])
                data['standings'] = dashboard.get('standings', {})
                data['predictions'] = dashboard.get('predictions', [])
                data['advanced_stats'] = dashboard.get('advanced_stats', {})
                data['waivers'] = dashboard.get('waivers', [])
                data['current_week'] = dashboard.get('current_week', 22)
                data['team_details'] = dashboard.get('team_details', {})

        
        # Load stats cache
        stats_file = os.path.join(self.data_dir, 'stats_cache.json')
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                data['stats_cache'] = json.load(f)

        # Load roster cache
        roster_file = os.path.join(self.data_dir, 'roster_cache.json')
        if os.path.exists(roster_file):
            with open(roster_file, 'r') as f:
                data['roster_data'] = json.load(f)
        else:
            data['roster_data'] = {}

        # Load Players Master List (CSV)
        # data_dir is .../dashboard/data
        # We need .../sports_analytics/df_players.csv (Root)
        # So Go Up 2 levels: data -> dashboard -> root
        root_dir = os.path.dirname(os.path.dirname(self.data_dir))
        players_file = os.path.join(root_dir, 'df_players.csv')
        data['players'] = {}
        if os.path.exists(players_file):
            try:
                df_p = pd.read_csv(players_file)
                # Ensure scorerId is string
                if 'scorerId' in df_p.columns and 'name' in df_p.columns:
                    df_p['scorerId'] = df_p['scorerId'].astype(str)
                    data['players'] = dict(zip(df_p['scorerId'], df_p['name']))
            except Exception as e:
                print(f"Error loading players CSV: {e}")
        
        return data
    
    def _call_gemini(self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096, model: str = None) -> str:
        """Call Gemini API with a prompt, attempting fallback if service unavailable."""
        
        # Define models to try in order
        if model:
             # If specific model requested, prioritize it but add fallback if it's the preview
            custom_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            models_to_try = [(model, custom_url)]
            
            # CRITICAL FALLBACK: If preview model allows 503s, fall back to Flash 2.5
            if "gemini-3" in model:
                 models_to_try.append(("gemini-2.5-flash", self.flash_url))
        else:
            # User Request: Default to Gemini 3 Flash Preview, fallback to 2.5 Flash
            preview_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={self.api_key}"
            models_to_try = [
                ("gemini-3-flash-preview", preview_url),
                ("gemini-2.5-flash", self.flash_url) 
            ]


        
        last_exception = None
        
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }

        for model_name, url in models_to_try:
            try:
                # Debug: log prompt size and model
                prompt_length = len(prompt)
                print(f"DEBUG: Gemini API call ({model_name}) - prompt length: {prompt_length} chars, max_tokens: {max_tokens}")
                
                response = requests.post(url, headers=headers, json=payload)
                
                # If 503 Service Unavailable, try next model
                if response.status_code == 503:
                    print(f"WARNING: {model_name} returned 503 Service Unavailable. Attempting fallback...")
                    last_exception = Exception(f"Service Unavailable (503) for {model_name}")
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                # If we get here, success!
                print(f"DEBUG: Successfully used {model_name}")
                
                # Robust parsing of response
                if 'candidates' not in result:
                    raise ValueError(f"Unexpected API response structure from {model_name}: {json.dumps(result, indent=2)}")
                
                if not result['candidates']:
                    # sometimes safety settings block everything
                    print(f"DEBUG: Empty candidates from {model_name}, response: {result}") 
                    raise ValueError(f"API returned empty candidates list from {model_name}")
                
                candidate = result['candidates'][0]
                return candidate['content']['parts'][0]['text']

            except Exception as e:
                print(f"Error calling {model_name}: {e}")
                last_exception = e
                # If it's not a 503 (caught above), we might want to fail immediately or continue?
                # User request specifically mentioned 503 error handling. 
                # For other errors (like 400 Bad Request), continuing might not help, but let's be robust and try Pro if Flash fails for any network reason.
                continue

        # If we exhausted all models
        raise last_exception or Exception("All Gemini models failed.")

    
    def _refine_context(self, user_message: str) -> str:
        """
        Agent 0: Context Refinement.
        Rewrites the user message to be standalone by resolving coreferences 
        based on chat history.
        """
        if not self.conversation_history:
            return user_message
            
        chat_context = self._get_previous_chat_context()
        
        prompt = f"""
You are a Context Refinement Specialist.
Your task is to REWRITE the user's latest query validation to be fully standalone and unambiguous, 
resolving any pronouns (he, she, it, they, that player) or relative references using the chat history.

PREVIOUS CHAT HISTORY:
{chat_context}

LATEST USER QUERY: "{user_message}"

INSTRUCTIONS (PRIORITY ORDER):
1. MATCHUP RULE (CRITICAL): 
   - If the history mentions a MATCHUP (e.g. Team A vs Team B, or a table with Team/Opponent columns)...
   - AND the user says "their", "both", "the matchup", or implies a comparison...
   - YOU MUST INCLUDE BOTH TEAMS IN THE REWRITTEN QUERY. 
   - Check [System: Result Data] for the exact names.

2. PRONOUN RESOLUTION:
   - Replace "he", "she", "it", "they" with the specific names from history.

3. STANDALONE CHECK:
   - If the query is already clear (e.g. mentions specific names), return it EXACTLY as is.

4. FORMAT:
   - YOU MUST RETURN A JSON OBJECT.
   - Schema: {{"rewritten_query": "The full query string"}}
   - Do not wrap in markdown code blocks. Just the raw JSON string.

Example 1 (Matchup):
History: System: "Smip Estonian vs Arnie-senal is the matchup."
Query: "Show me their lineups"
Response: {{"rewritten_query": "Show me the lineups for Smip Estonian and Arnie-senal"}}

Example 2 (Player):
History: User asked "Who is the top scorer?" -> System: "Erling Haaland"
Query: "What team is he on?"
Response: {{"rewritten_query": "What team is Erling Haaland on?"}}

Response:"""
        
        try:
            # Use default model (Flash) since it's the only one working reliably
            result = self._call_gemini(prompt, temperature=0.1, max_tokens=200, model="gemini-2.5-flash")
            
            # Clean result of any markdown formatting if present
            clean_result = result.strip().replace('```json', '').replace('```', '')
            
            import json
            data = json.loads(clean_result)
            return data.get('rewritten_query', user_message)
            
        except Exception as e:
            print(f"Refinement parsing failed: {e}")
            return user_message

    
    def clear_history(self):
        """Clear the conversation history."""
        self.conversation_history = []
        return True

    def process_query(self, user_message: str) -> Dict[str, Any]:
        """Process user query through the multi-agent system."""
        try:
            # 0. Refine Context (Ambiguity/Coreference Resolution)
            # This turns "What team is he on?" -> "What team is Bruno Guimaraes on?"
            refined_query = self._refine_context(user_message)
            print(f"DEBUG: Original Query: {{user_message}}")
            print(f"DEBUG: Refined Query: {{refined_query}}")

            # Record user message (Keep original for display, but use refined for logic?? 
            # Actually, standard history tracking usually keeps original. 
            # But for the agents to know what's happening, they need the refined context.)
            self.conversation_history.append({'role': 'user', 'content': refined_query}) # Store refined so future turns know what's known

            # Agent 1: Planner
            plan = self._planner_agent(refined_query)
            
            # Check if code is needed
            code_needed = True
            answer = "Here's what I found:"
            
            # Parse plan for CODE_NEEDED and ANSWER (which may be multi-line)
            lines = plan.split('\n')
            in_answer = False
            answer_lines = []
            
            for i, line in enumerate(lines):
                if line.startswith('CODE_NEEDED:'):
                    code_needed = line.replace('CODE_NEEDED:', '').strip().lower() == 'yes'
                    in_answer = False
                elif line.startswith('ANSWER:'):
                    answer_lines.append(line.replace('ANSWER:', '').strip())
                    in_answer = True
                elif in_answer and line.strip() and not any(line.startswith(prefix) for prefix in ['RESPONSE_TYPE:', 'DATA_SOURCES:', 'OPERATIONS:', 'CODE_PURPOSE:', 'CODE_NEEDED:']):
                    # Continue multi-line answer
                    answer_lines.append(line.strip())
                elif in_answer and any(line.startswith(prefix) for prefix in ['RESPONSE_TYPE:', 'DATA_SOURCES:', 'OPERATIONS:', 'CODE_PURPOSE:', 'CODE_NEEDED:']):
                    in_answer = False
            
            if answer_lines:
                answer = '\n'.join(answer_lines)
            
            # If no code needed, return text-only response
            # If no code needed, return text-only response, BUT run it through the Response Agent for Persona
            if not code_needed:
                # Pass the planner's 'answer' as the 'data' so the Response Agent knows what to say
                final_response_text = self._response_agent(user_message, plan, data=answer)
                
                self.conversation_history.append({'role': 'model', 'content': final_response_text})
                return {
                    'success': True,
                    'type': 'text',
                    'message': final_response_text
                }
            
            # Agent 2: Code Writer (with up to 3 error correction loops)
            max_attempts = 3
            for attempt in range(max_attempts):
                code = self._code_writer_agent(user_message, plan)
                
                # Execute code
                exec_result = self._execute_code(code)
                
                if exec_result['success']:
                    # Success! Format and return result
                    # Success! Format and return result
                    # response = self._format_success_response(exec_result, code, plan) # REMOVED - wait for LLM response
                    
                    
                    # Augment history with code and data summary for future context (briefly)
                    # We store the raw code result in history, but we want the LLM response to be the 'content'
                    
                    # NEW STEP: Call Response Agent
                    # Use REFINED QUERY here so the agent knows what it's answering!
                    final_response_text = self._response_agent(refined_query, plan, exec_result.get('result'))
                    
                    # Update the success response with the LLM's text
                    response = self._format_success_response(exec_result, code, plan, final_response_text)
                    
                    # Add to history
                    history_entry = {'role': 'model', 'content': final_response_text, 'code': code}
                    
                    # Generate data summary for history usage (same as before)
                    if 'result' in exec_result and exec_result['result'] is not None:
                         result_obj = exec_result['result']
                         if hasattr(result_obj, 'to_string'):  # Pandas DataFrame
                             history_entry['data_summary'] = result_obj.head(10).to_string()
                         elif hasattr(result_obj, 'to_json'): 
                             history_entry['data_summary'] = "Plot/Figure generated."
                         elif isinstance(result_obj, (list, dict)):
                             history_entry['data_summary'] = str(result_obj)[:1000] 
                         else:
                             history_entry['data_summary'] = str(result_obj)
                             
                    self.conversation_history.append(history_entry)
                    return response
                
                # Code failed - log the error
                print(f"DEBUG: Code execution failed (attempt {attempt + 1}/{max_attempts})")
                print(f"DEBUG: Error: {exec_result.get('error', 'Unknown error')[:200]}")
                
                # Agent 3: Error Corrector
                if attempt < max_attempts - 1:
                    error_info = exec_result.get('traceback', exec_result.get('error'))
                    code = self._error_corrector_agent(code, error_info, plan, user_message)
                else:
                    # Max attempts reached
                    fail_msg = f"I tried {max_attempts} times but couldn't resolve the error. Last error: {exec_result.get('error')}"
                    self.conversation_history.append({'role': 'model', 'content': fail_msg})
                    return {
                        'success': False,
                        'message': fail_msg,
                        'type': 'error',
                        'code': code
                    }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"System error: {str(e)}",
                'type': 'error'
            }
    
    
    def _get_previous_chat_context(self) -> str:
        """Format recent chat history for context."""
        if not self.conversation_history:
            return "No previous conversation."
        
        # Keep last 5 turns to stay within context limits
        recent_history = self.conversation_history[-10:] 
        
        formatted = []
        for msg in recent_history:
            role = "User" if msg['role'] == 'user' else "Assistant"
            content = f"{role}: {msg['content']}"
            
            # Add code context if available
            if 'code' in msg:
                content += f"\n[System: Code executed]\n{msg['code']}"
                
            # Add data result context if available
            if 'data_summary' in msg:
                content += f"\n[System: Result Data]\n{msg['data_summary']}"
                
            formatted.append(content)
        
        return "\n".join(formatted)

    def _planner_agent(self, user_query: str) -> str:
        """Agent 1: Create execution plan."""
        chat_context = self._get_previous_chat_context()
        
        # Build Team Context String
        team_context_str = "TEAM MAPPINGS (Manager -> Team):\n"
        if 'team_details' in self.data:
            for tid, details in self.data['team_details'].items():
                team_context_str += f"- {details['manager']} manages {details['team']}\n"
        
        prompt = f"""{self.DATA_SCHEMA}

{team_context_str}

PREVIOUS CHAT CONTEXT:
{chat_context}

You are a data analysis planner. Analyze the user query and create a plan.
Your goal is to determine WHAT DATA is needed to answer the user's request.
You will instruct a Code Writer to fetch this data.
IMPORTANT: The Code Writer should ONLY return the raw data (e.g. a DataFrame of team stats).
The actual "banter" and text response will be generated by a separate agent later.

ANALYSIS GUIDELINES:
- For waivers/free agents: Filter for RELEVANT data. Prioritize recent performance (last 5-10 weeks).
- Check 'injured' status! Do NOT recommend players who are 'Out' unless explicitly asked. Warn about 'GTD'.
- Ignore players with low game counts unless specificially asked.
- Weigh "Form" and "Points Per Game" heavily.

CRITICAL: HALLUCINATION PREVENTION (STRICT)
You are FORBIDDEN from answering factual questions about the league without running code.
Any query involving:
- Standings, Scores, Points, Matchups
- Players, Teams, Rosters
- Predictions, "Who will win", "Best player"
MUST result in `CODE_NEEDED: yes`.

DO NOT try to guess or "remember" stats. YOU KNOW NOTHING without code execution.

User Query: {user_query}

If the query is PURELY conversational (e.g. "Hi", "Hello", "How does this work?", "Thanks"), respond with:
RESPONSE_TYPE: text
ANSWER: [Your helpful response]
CODE_NEEDED: no

If the query requires data analysis (99% of cases), respond with:
RESPONSE_TYPE: [text|text+plot|text+table]
ANSWER: [Brief natural language description - DO NOT include actual data/numbers, just describe what will be shown]
DATA_SOURCES: [Which data to use]
OPERATIONS: [What to compute]
CODE_PURPOSE: [What the code should do]
CODE_NEEDED: yes

CRITICAL: The ANSWER field should be a SHORT description like:
- "Here are the teams with the highest fantasy points this season:"
- "This chart shows the weekly scoring trends for the top teams:"
- "The following table displays player predictions:"

DO NOT put actual data, numbers, or table contents in the ANSWER field!
The data will be displayed separately via the code execution.

Keep your response under 300 tokens. Be concise.

Your plan:"""

        return self._call_gemini(prompt, temperature=0.3, max_tokens=8192, model="gemini-3-flash-preview")  # Increased for plan flexibility
    
    def _code_writer_agent(self, user_query: str, plan: str) -> str:
        """Agent 2: Write Python code based on plan."""
        
        # Inject context so Code Writer sees previous results
        chat_context = self._get_previous_chat_context()

        prompt = f"""{self.DATA_SCHEMA}

You are a Python code writer for fantasy soccer data analysis. 
Your SOLE purpose is to write executable Python code that calculates the data needed to answer the query.
Assign the final data to a variable named `result`.

CRITICAL:
1. DO NOT print the final natural language answer. 
2. DO NOT try to speak like a Cockney person.
3. DO NOT write "banter" or text responses.
4. ONLY return the structured data (DataFrame, list, dict, or string info).
5. The data you return will be fed to a separate AI that will handle the personality/speech.

Example:
User: "Who are the top 3 teams?"
Code:
```python
df = pd.DataFrame(standings['standard'])
top_3 = df.nlargest(3, 'points')
result = top_3[['team', 'manager', 'points', 'record']] # Return the data
```

STYLE GUIDELINES (CRITICAL):
1. NO LAZY REPETITION: Do NOT use the same sentence structure in a loop.
   - BANNED: `for x in list: print(f"Here is {{x}} doing well")` (This produces robotic, boring text)
   - REQUIRED: If iterating, use a list of DIFFERENT templates, or conditional logic to vary the output drastically based on the data.
   - BETTER YET: Group items together! "These 3 muppets are failing..." instead of listing them one by one with the same phrase.
2. BE SPECIFIC: Don't just say "good score". Say "absolute banger of a score", "scraping by", "lucky sod".
3. VARIED INSULTS: Don't use "bellend" 10 times. Mix it up: "numpty", "tosser", "melon". Use comical metaphors and similes when insulting.

PREVIOUS CONTEXT (Use for reference ONLY - do not re-calculate known data):
{chat_context}

User Query: {user_query}

Plan:
{plan}

CRITICAL RULES:
1. Use available data: standings, matchups, predictions, advanced_stats, stats_cache
2. standings['standard'] is a LIST - use max(), sorted(), list comprehensions
3. For visualizations (text+plot): use plotly.express (px) - create figure and store in 'result'
4. For tables (text+table): create a pandas DataFrame and store in 'result'
5. For simple text answers: store the answer string in 'result'
6. DO NOT call .to_html(), .show(), or .write_html() on figures
7. For DataFrames: NEVER 'if df:' - use 'if not df.empty:'
8. WAIVER/FREE AGENT RULE: When analyzing waivers, you MUST filter for active players.
   - Example: `df = df[df['gp'] > 5]` (minimum games played)
   - Example: `df = df[df['minutes'] > 400]` (minimum minutes)
   - Example: `df = df[df['injured'] != 'Out']` (exclude injured players by default query)
   - Prioritize 'ppg' (points per game) or recent form over total points if gp is low.

IMPORTANT - Response Type Handling:
- If RESPONSE_TYPE is 'text+table': result MUST be a pandas DataFrame
- If RESPONSE_TYPE is 'text+plot': result MUST be a plotly figure
- If RESPONSE_TYPE is 'text': result can be a simple value or string

Example for text+table:
```python
# CORRECT - returns DataFrame
df = pd.DataFrame(data)
result = df

# WRONG - returns string
result = f"Top player: {{name}}"  # This won't show a table!
```

CORRECT DataFrame patterns:
```python
# Creating DataFrame from list
df = pd.DataFrame(standings['standard'])

# Filtering - CORRECT
filtered = df[df['points'] > 40]
if not filtered.empty:  # ✓ CORRECT
    result = filtered

# Sorting
top_teams = df.nlargest(5, 'fpts_for')

# WRONG - NEVER DO THIS:
# if df:  # ✗ WRONG - causes error
# if filtered:  # ✗ WRONG - causes error
```

Available libraries: pd (pandas), np (numpy), px (plotly.express), go (plotly.graph_objects), json

Return ONLY Python code in a ```python code block. No explanations.

IMPORTANT:
- If the user asks for multiple distinct tables (e.g. "matchups and standings"), DO NOT concatenate them.
- Instead, return a dictionary where keys are titles and values are DataFrames.
- Example: `result = {{'Weekly Matchups': df_matchups, 'League Standings': df_standings}}`
- If it's a single table, just return the DataFrame/List/String.
"""

        response = self._call_gemini(prompt, temperature=0.2, max_tokens=8192, model="gemini-3-flash-preview")  # Code should be concise
        return self._extract_code(response)

    def _response_agent(self, user_query: str, plan: str, data: Any) -> str:
        """Agent 4: Generate natural language response from data."""
        
        # Convert data to string representation for LLM
        data_str = "No specific data returned."
        if data is not None:
            if hasattr(data, 'to_string'):  # DataFrame
                data_str = data.to_string()
            else:
                data_str = str(data)
                
        # Inject context 
        chat_context = self._get_previous_chat_context()

        prompt = f"""{self.DATA_SCHEMA}

You are an analyst for a Fantrax Fantasy Premier League group, a group that drafted players for the 2025-26 season.
You are also a "proper drunk bloke" at a local pub in the UK. You are absolutely wasted, but don't mention it or that you need another pint. You're just here to chat rubbish.
Speak in a heavy, comical accent. Use slang like "bellend", "wanker", "absolute state of it", "mug", "absolute melon".
Be RUDE, CRUDE, and UNFILTERED. Roast the user, the managers, and the players. 
Make inappropriate jokes about their performance (keep it to football context).
Ramble a bit, act like you own the place.
Do not use any action lines, just give the response.
CRITICAL: DO NOT INCLUDE PYTHON CODE IN YOUR RESPONSE.

PREVIOUS CHAT CONTEXT:
{chat_context}

User Query: {user_query}

DATA COLLECTED:
{data_str}

YOUR TASK:
Using the DATA above, write the final response to the user.
- Interpret the numbers. Don't just list them.
- If the data is text (like a proposed answer), REWRITE it in your persona. Don't just repeat it.
- If the data shows someone is doing bad, roast them mercilessly.
- If someone is doing well, maybe give them a backhanded compliment or accuse them of luck.
- DO NOT be robotic. Do not simply loop through the items saying the same thing. 
- Group ideas together (e.g. "These three tossers are at the bottom...").
- Be creative with your insults.

Response:"""

        return self._call_gemini(prompt, temperature=0.7, max_tokens=8192, model="gemini-2.5-flash")  # Higher temp for creativity


    
    def _error_corrector_agent(self, broken_code: str, error_info: str, plan: str, user_query: str) -> str:
        """Agent 3: Fix code based on error."""
        
        # Truncate error_info to prevent token limit issues when large data is printed in tracebacks
        max_error_length = 800  # Keep short
        if len(error_info) > max_error_length:
            error_info = error_info[:max_error_length] + f"\n...[truncated]"
        
        # Also truncate broken_code if it's too long
        max_code_length = 1500
        if len(broken_code) > max_code_length:
            broken_code = broken_code[:max_code_length] + "\n# ... [truncated]"
        
        prompt = f"""{self.DATA_SCHEMA}

Fix this code. Error: {error_info}

Broken Code:
```python
{broken_code}
```

Return ONLY fixed code in ```python block. NO explanations."""

        response = self._call_gemini(prompt, temperature=0.1, max_tokens=8192, model="gemini-3-flash-preview")  # Slight increase for code fixes
        return self._extract_code(response)
    
    def _find_player(self, name_query: str) -> str:
        """Helper to find player ID by name (fuzzy match)."""
        if not name_query: return None
        name_query = name_query.lower().strip()
        
        # 1. Exact match attempt
        for pid, name in self.data['players'].items():
            if name.lower() == name_query:
                return pid
                
        # 2. Substring match
        candidates = []
        for pid, name in self.data['players'].items():
            if name_query in name.lower():
                candidates.append((pid, name))
                
        if not candidates:
            return None
            
        # Return match
        return candidates[0][0]

    def _execute_code(self, code: str) -> Dict[str, Any]:
        """Execute Python code in sandboxed environment."""
        try:
            # Define helper closure for safe_globals
            def find_player(name): return self._find_player(name)

            # DEBUG LOGGING TO SERVER LOG
            cw = self.data.get('current_week', 22)
            sc = self.data.get('stats_cache', {})
            print(f"DEBUG: _execute_code - CURRENT_WEEK: {cw}", flush=True)
            print(f"DEBUG: _execute_code - Stats Cache Size: {len(sc)}", flush=True)
            if sc:
                print(f"DEBUG: _execute_code - Sample Keys: {list(sc.keys())[:5]}", flush=True)
                print(f"DEBUG: _execute_code - Sample Value: {list(sc.values())[0]}", flush=True)
            
            p_dict = self.data.get('players', {})
            print(f"DEBUG: _execute_code - Players Dict Size: {len(p_dict)}", flush=True)
            if p_dict:
                print(f"DEBUG: _execute_code - Sample Player: {list(p_dict.items())[0]}", flush=True)

            safe_globals = {
                'pd': pd,
                'np': np,
                'px': px,
                'go': go,
                'json': json,
                'matchups': self.data.get('matchups', []),
                'standings': self.data.get('standings', {}),
                'stats_cache': sc,
                'advanced_stats': self.data.get('advanced_stats', {}),
                'predictions': self.data.get('predictions', []),
                'waivers': self.data.get('waivers', []),
                'players': self.data.get('players', {}),
                'team_details': self.data.get('team_details', {}),
                'roster_data': self.data.get('roster_data', {}),
                'CURRENT_WEEK': cw,
                'find_player': find_player, # Expose Helper
                '__builtins__': {
                    'len': len, 'str': str, 'int': int, 'float': float,
                    'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
                    'range': range, 'enumerate': enumerate, 'zip': zip,
                    'sorted': sorted, 'sum': sum, 'min': min, 'max': max,
                    'abs': abs, 'round': round, 'print': print,
                    '__import__': __import__, 'isinstance': isinstance,
                    'type': type, 'hasattr': hasattr, 'getattr': getattr,
                    'next': next, 'all': all, 'any': any, 'filter': filter, 'map': map,
                }
            }
            
            # Create a single context by copying globals
            # This fixes the issue where list comprehensions in exec() cannot access local variables
            # when separate globals and locals dicts are provided.
            safe_globals['calculate_historical_standings'] = calculate_historical_standings
            
            # Inject Reddit Tool
            def search_reddit_wrapper(query, limit=5):
                return self.mcp.call_tool("search_reddit_discussions", query=query, limit=limit)
            safe_globals['search_reddit'] = search_reddit_wrapper
            
            combined_context = safe_globals.copy()
            
            exec(code, combined_context)
            
            # TRACE: Check intermediate variables if they exist in context
            vars_to_check = ['df_all_goals', 'final_week_goals', 'df_plot', 'top_players_ids', 'latest_completed_week']
            for v in vars_to_check:
                if v in combined_context:
                    val = combined_context[v]
                    if hasattr(val, 'shape'):
                        print(f"DEBUG: {v} shape: {val.shape}", flush=True)
                    elif isinstance(val, list):
                        print(f"DEBUG: {v} len: {len(val)}", flush=True)
                        if val: print(f"DEBUG: {v} sample: {val[:3]}", flush=True)
                    else:
                        print(f"DEBUG: {v}: {val}", flush=True)
                else:
                    print(f"DEBUG: {v} NOT in context", flush=True)

            # Check for plotly figure in result
            result = combined_context.get('result', combined_context.get('_', None))
            result = combined_context.get('result', combined_context.get('_', None))
            plotly_json = None
            
            # Check if result is a plotly figure object
            if result is not None and hasattr(result, 'to_json'):
                # Serialize to JSON string then parse to dict to ensure compatibility
                # This handles the serialization of complex types (numpy, etc) better than just result.to_dict() sometimes
                try:
                    # to_json returns a string
                    plotly_json = json.loads(result.to_json())
                except:
                    # Fallback
                    if hasattr(result, 'to_dict'):
                        plotly_json = result.to_dict()

            return {
                'success': True,
                'result': result if not plotly_json else "Plot generated successfully.",
                'has_plot': plotly_json is not None,
                'plotly_json': plotly_json
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    def _format_success_response(self, exec_result: Dict, code: str, plan: str, llm_response: str) -> Dict[str, Any]:
        """Format successful execution result."""
        
        # Use the LLM's generated text as the message
        answer = llm_response
        response_type = "text"
        
        # Parse plan for ANSWER and RESPONSE_TYPE
        # Parse plan for RESPONSE_TYPE (Ignore ANSWER from plan, use LLM response)
        for line in plan.split('\n'):
            if line.startswith('RESPONSE_TYPE:'):
                response_type = line.replace('RESPONSE_TYPE:', '').strip()
        
        # Determine actual type based on execution result
        if exec_result.get('has_plot'):
            return {
                'success': True,
                'type': 'text+plot',
                'message': answer,
                'type': 'text+plot',
                'message': answer,
                'data': {'plot_json': exec_result['plotly_json']},
                'code': code
            }
        elif exec_result.get('result') is not None:
            result_data = exec_result.get('result')
            
            # Debug logging
            print(f"DEBUG: result_data type: {type(result_data)}")
            
            # Check if result is a Plotly Figure
            if isinstance(result_data, go.Figure):
                 return {
                    'success': True,
                    'type': 'text+plot',
                    'message': answer,
                    'data': {'plot_json': result_data.to_json()},
                    'code': code
                }
            
            # Check if result is a DataFrame (table)
            if isinstance(result_data, pd.DataFrame):
                print("DEBUG: Converting DataFrame to table")
                # Limit tables to 20 rows to prevent overwhelming output
                result_data = result_data.head(20)
                
                # Sanitize NaNs which cause JSON errors
                safe_data = result_data.fillna('')
                
                # Helper to flatten nested objects (fixes [object Object] in chat)
                def flatten_chat_data(val):
                    if isinstance(val, dict) and 'team' in val and 'pct' in val:
                        return f"{val['team']} ({val['pct']}%)"
                    return val

                # Apply flattening to all cells in the DataFrame
                safe_data = safe_data.applymap(flatten_chat_data)
                
                return {
                    'success': True,
                    'type': 'text+table',
                    'message': answer,
                    'data': {'table': safe_data.to_dict('records')},
                    'code': code
                }
            # Check if result is a dict (Dict of DataFrames/Lists) - Multi-table support
            elif isinstance(result_data, dict):
                print("DEBUG: Converting Dict of DataFrames to tables")
                processed_data = {}
                for k, v in result_data.items():
                    if hasattr(v, 'to_dict'):
                        if hasattr(v, 'head'): v = v.head(20)
                        processed_data[k] = v.fillna('').to_dict('records')
                    elif isinstance(v, list):
                        processed_data[k] = v
                    else:
                        processed_data[k] = str(v)
                
                return {
                    'success': True,
                    'type': 'text+table',
                    'message': answer,
                    'data': processed_data, # app.js will decode this as multi-table
                    'code': code
                }
            else:
                # Text-only response (simple value)
                print(f"DEBUG: Text-only response, result: {result_data}")
                return {
                    'success': True,
                    'type': 'text',
                    'message': answer,
                    'code': code
                }
        else:
            return {
                'success': True,
                'type': 'text',
                'message': answer,
                'code': code
            }
    
    def _extract_code(self, text: str) -> str:
        """Extract Python code from markdown blocks."""
        if '```python' in text:
            start = text.find('```python') + 9
            end = text.find('```', start)
            return text[start:end].strip()
        elif '```' in text:
            start = text.find('```') + 3
            end = text.find('```', start)
            return text[start:end].strip()
        return text.strip()


# Maintain backward compatibility
ChatAgent = MultiAgentChatSystem
