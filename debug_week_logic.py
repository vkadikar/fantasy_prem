import pandas as pd
import datetime

# Mocking the preprocessing logic from update_data.py
def debug_matchweek_logic():
    print("Loading df_player_stats.csv...")
    try:
        df = pd.read_csv("df_player_stats.csv")
    except Exception as e:
        print(f"Error: {e}")
        return

    # Normalize cols
    df.columns = [c.lower() for c in df.columns]
    
    # Date parsing (Using the robust ISO support I added)
    def parse_date(date_str):
        if not isinstance(date_str, str): return None
        try:
            return datetime.datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            pass
        try:
            d = datetime.datetime.strptime(date_str, '%b %d')
            year = 2025 if d.month >= 8 else 2026
            return d.replace(year=year)
        except:
            return None

    df['date_obj'] = df['date'].apply(parse_date)
    
    # Team Games Logic (Mirroring update_data.py)
    # We drop duplicates on TEAM and DATE only to find unique matchdays
    team_games = (
        df[['team', 'date_obj']]
        .drop_duplicates()
        .sort_values(['team', 'date_obj'])
        .reset_index(drop=True)
    )
    
    # Renaming for clarity in debug output
    team_games = team_games.rename(columns={'date_obj': 'game_date'})
    
    # Calculate matchweek
    team_games['calculated_week'] = (
        team_games
            .groupby('team')
            .cumcount()
            .add(1)
    )
    
    # Inspect ARS (Arsenal)
    print("\n--- Arsenal (ARS) Match Schedule Verification ---")
    ars_games = team_games[team_games['team'] == 'ARS'].copy()
    print(ars_games)
    
    # Check Timber
    print("\n--- Jurrien Timber Rows ---")
    timber = df[df['player_name'].str.contains("Timber", na=False)]
    print(timber[['date', 'team', 'opp', 'fpts', 'matchweek']].head(10))
    
    if not timber.empty:
        # Check current week assignment
        week_23_timber = timber[timber['matchweek'] == 23]
        if not week_23_timber.empty:
            print(f"Timber found in Week 23: {week_23_timber.iloc[0].to_dict()}")
        else:
            print("Timber NOT found in Week 23.")

if __name__ == "__main__":
    debug_matchweek_logic()
