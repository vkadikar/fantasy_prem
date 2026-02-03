
from datetime import datetime
import pandas as pd

def test_logic():
    next_match_str = "@TOT<br/>Sun 11:30AM"
    team_map = {'Tottenham': 'TOT', 'Manchester City': 'MCI'}
    team_short_name = 'MCI'
    player_id = '06ex4'
    player_name = 'Josko Gvardiol'
    
    print(f"Testing with: {next_match_str}")
    
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
             
             print(f"Opponent: {opp_short}")
             
             current_data = {
                 'Date': datetime.now(),
                 'Team': team_short_name,
                 'Opp': opp_short,
                 'Score': 'TBD',
                 'player_id': player_id,
                 'player_name': player_name
             }
         except Exception as e:
             print(f"Exception: {e}")
             pass

    print(f"Current Data: {current_data}")
    
    # Simulate Date check
    if current_data.get('Date'):
        print("Success: Date found.")
    else:
        print("Fail: No Date.")

if __name__ == "__main__":
    test_logic()
