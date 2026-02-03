import sys
import os
import pandas as pd

# Add the current directory to path to import scripts
sys.path.append(os.getcwd())

from scripts.update_data import preprocess_player_stats

def validate():
    print("Loading data...")
    try:
        df_stats = pd.read_csv("df_player_stats.csv")
        df_players = pd.read_csv("df_players.csv")
        matchups = pd.DataFrame() # preprocess doesn't strictly need matchups for the main logic if just checking stats
        
        # Preprocess
        processed = preprocess_player_stats(df_stats, df_players, matchups)
        
        # Find Timber
        print("\n--- Jurrien Timber (Processed) ---")
        timber = processed[processed['player_name'].str.contains("Timber", na=False)]
        
        # Sort by matchweek desc
        timber = timber.sort_values('matchweek', ascending=False).head(5)
        
        # Print columns of interest
        cols = ['date', 'team', 'opp', 'fpts', 'matchweek', 'min', 'g', 'player_id'] 
        print(timber[cols])
        
        # Check specific week 23
        t23 = timber[timber['matchweek'] == 23]
        if not t23.empty:
            print(f"\nWeek 23 Found! ID: {t23.iloc[0]['player_id']} FPTS: {t23.iloc[0]['fpts']}")
        else:
            print("\nWeek 23 MISSING in processed dataframe.")
            
        # Check Saka too
        print("\n--- Bukayo Saka (Processed) ---")
        saka = processed[processed['player_name'].str.contains("Saka", na=False)]
        saka = saka.sort_values('matchweek', ascending=False).head(5)
        print(saka[cols])

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    validate()
