
import sys
import os
import json
import pandas as pd

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dashboard.chat_agent import MultiAgentChatSystem
import config

# Mock Config if needed
config.API_KEY = os.environ.get("GEMINI_API_KEY")

def test_waiver_logic():
    print("Initializing Chat Agent...")
    # Initialize with real data dir, but we will override
    agent = MultiAgentChatSystem(api_key=config.API_KEY)
    
    # Mock Waivers Data
    # 1. Good player, Available
    # 2. Great player, OUT
    # 3. Decent player, GTD
    mock_waivers = [
        {'player_id': 'p1', 'player_name': 'Healthy Star', 'team': 'ARS', 'position': 'M', 'fpts': 200, 'gp': 20, 'minutes': 1800, 'injured': 'Available', 'fpts_per_game': 10.0},
        {'player_id': 'p2', 'player_name': 'Injured Legend', 'team': 'MCI', 'position': 'F', 'fpts': 300, 'gp': 20, 'minutes': 1800, 'injured': 'Out', 'fpts_per_game': 15.0},
        {'player_id': 'p3', 'player_name': 'Maybe Good', 'team': 'LIV', 'position': 'D', 'fpts': 150, 'gp': 20, 'minutes': 1800, 'injured': 'GTD', 'fpts_per_game': 7.5},
        {'player_id': 'p4', 'player_name': 'Average Joe', 'team': 'CHE', 'position': 'M', 'fpts': 100, 'gp': 20, 'minutes': 1800, 'injured': 'Available', 'fpts_per_game': 5.0}
    ]
    
    # Override agent data
    agent.data['waivers'] = mock_waivers
    
    query = "Who are the best waiver pickups right now?"
    print(f"\nQuery: {query}")
    
    response = agent.process_query(query)
    
    print("\n--- Response ---")
    print(response.get('message', 'No message'))
    
    # Validation Logic
    msg = response.get('message', '').lower()
    
    # Expected: "Healthy Star" recommended. "Injured Legend" excluded or warned.
    if 'healthy star' in msg:
        print("\n[PASS] Recommended Healthy Star")
    else:
        print("\n[FAIL] Did not recommend Healthy Star")
        
    if 'injured legend' not in msg or 'out' in msg:
        print("[PASS] Handled Injured Legend correctly (excluded or warned)")
    else:
        print("[FAIL] Recommended Injured Legend without warning!")

if __name__ == "__main__":
    test_waiver_logic()
