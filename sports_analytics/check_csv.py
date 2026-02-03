import pandas as pd
import os

def check():
    path = "df_player_stats.csv"
    print(f"Reading {path}...")
    try:
        df = pd.read_csv(path)
        print("Columns:", list(df.columns))
        print("First Row:", df.iloc[0].to_dict())
        
        # Check normalization
        norm_cols = [c.lower() for c in df.columns]
        if 'date' not in norm_cols:
            print("CRITICAL: 'date' column missing after lowercasing!")
        if 'team' not in norm_cols:
             print("CRITICAL: 'team' column missing!")
             
    except Exception as e:
        print(f"Error reading CSV: {e}")

if __name__ == "__main__":
    check()
