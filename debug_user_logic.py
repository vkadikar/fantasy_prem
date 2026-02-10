
import sys
import os
import json
import pandas as pd
import plotly.express as px

# Mock Agent Environment
class MockAgent:
    def __init__(self):
        self.data = {}
        # Load Stats Cache
        with open('dashboard/data/stats_cache.json', 'r') as f:
            self.data['stats_cache'] = json.load(f)
        
        # Load Players
        try:
            df_p = pd.read_csv('df_players.csv')
            df_p['scorerId'] = df_p['scorerId'].astype(str)
            self.data['players'] = dict(zip(df_p['scorerId'], df_p['name']))
        except:
            self.data['players'] = {}
            
        # Load Dashboard Data for Current Week
        with open('dashboard/data/dashboard_data.json', 'r') as f:
            dash = json.load(f)
            self.data['current_week'] = dash.get('current_week', 22)

def run_debug():
    agent = MockAgent()
    stats_cache = agent.data['stats_cache']
    players = agent.data['players']
    CURRENT_WEEK = agent.data['current_week']
    
    print(f"DEBUG: CURRENT_WEEK = {CURRENT_WEEK}")
    print(f"DEBUG: stats_cache items = {len(stats_cache)}")
    
    # --- USER PROVIDED CODE START ---
    player_cumulative_goals = {}
    plot_data = []
    top_n_players = 10 

    for week in range(1, CURRENT_WEEK):
        # print(f"Processing Week {week}...")
        for key, stats in stats_cache.items():
            try:
                # FIX: Handle potential unpack errors if key format is wrong
                if '_' not in key: continue
                
                parts = key.rsplit('_', 1)
                if len(parts) != 2: continue
                
                player_id, stat_week_str = parts
                stat_week = int(stat_week_str)

                if stat_week == week:
                    goals = stats.get('G', 0)
                    player_cumulative_goals[player_id] = player_cumulative_goals.get(player_id, 0) + goals
            except ValueError:
                continue

        current_top_scorers = sorted(
            player_cumulative_goals.items(),
            key=lambda item: item[1],
            reverse=True
        )[:top_n_players]

        for player_id, cumulative_goals in current_top_scorers:
            player_name = players.get(player_id, player_id)
            plot_data.append({
                'Week': week,
                'Player': player_name,
                'Cumulative Goals': cumulative_goals
            })
    
    # --- USER PROVIDED CODE END ---
    
    df = pd.DataFrame(plot_data)
    print("DEBUG: DataFrame Info:")
    print(df.info())
    print("DEBUG: DataFrame Head:")
    print(df.head(20))
    print("DEBUG: Unique Weeks in DF:", df['Week'].unique())
    
    if df.empty:
        print("RESULT: Empty DataFrame")
    else:
        # Check Haaland
        haaland = df[df['Player'] == 'Erling Haaland']
        print("DEBUG: Haaland Data rows:", len(haaland))
        print(haaland.head())

if __name__ == "__main__":
    run_debug()
