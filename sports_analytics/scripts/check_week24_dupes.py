
import pandas as pd
import os

def check_duplicates():
    file_path = "player_data/df_player_stats_24.csv"
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    print(f"Reading {file_path}...")
    df = pd.read_csv(file_path, low_memory=False)
    
    # Filter for Sunderland (SUN) and Burnley (BUR)
    # Ensure team column checks are case insensitive just in case, though usually uppercase
    target_teams = ['SUN', 'BUR']
    df_teams = df[df['team'].isin(target_teams)]
    
    if df_teams.empty:
        print("No players found for SUN or BUR.")
        return

    print(f"Found {len(df_teams)} rows for SUN/BUR.")
    
    # Check for duplicates by player_id
    # We want to see if any player_id appears more than once
    
    # Group by player_id
    counts = df_teams.groupby('player_id').size()
    duplicates = counts[counts > 1]
    
    if duplicates.empty:
        print("No duplicates found for SUN or BUR players.")
    else:
        print(f"Found {len(duplicates)} players with duplicate entries:")
        for pid in duplicates.index:
            player_rows = df_teams[df_teams['player_id'] == pid]
            name = player_rows['player_name'].iloc[0] if 'player_name' in player_rows.columns else "Unknown"
            print(f"\nPlayer: {name} (ID: {pid})")
            print(player_rows[['date', 'opp', 'fpts', 'min']].to_string(index=False))
            # game_info might not exist, let's use what we saw in head: date, team, opp, score, fpts, min
            
    # Also just list all players found to confirm coverage
    print("\n--- Summary of players checked ---")
    print(df_teams[['player_name', 'team', 'fpts']].groupby(['team', 'player_name']).sum())

if __name__ == "__main__":
    check_duplicates()
