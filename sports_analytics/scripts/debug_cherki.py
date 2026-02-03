import pandas as pd
import sys
import os

# Mock preprocess from update_data.py
def preprocess_player_stats(df_stats, df_players):
    df = df_stats.copy()
    df.columns = [c.lower() for c in df.columns]
    
    df_players['scorerId'] = df_players['scorerId'].astype(str)
    df_stats['player_id'] = df_stats['player_id'].astype(str)
    
    df = pd.merge(df, df_players[['scorerId', 'posShortNames']], left_on='player_id', right_on='scorerId', how='left')
    
    # My patch logic
    has_matchweek = 'matchweek' in df.columns
    if not has_matchweek:
        pass # Recalc logic
    
    return df

df_stats = pd.read_csv('player_data/df_player_stats_24.csv')
df_players = pd.read_csv('df_players.csv')

print("\n--- Raw CSV Stats ---")
cherki = df_stats[df_stats['player_id'] == '06v07']
print(cherki[['player_id', 'fpts', 'matchweek']].to_string())

print("\n--- After Preprocess ---")
proc = preprocess_player_stats(df_stats, df_players)
cherki_proc = proc[proc['player_id'] == '06v07']
print(cherki_proc[['player_id', 'fpts', 'matchweek']].to_string())
