
import os
import sys
import pandas as pd

# Add current directory to path
sys.path.append(os.getcwd())

from dashboard.chat_agent import MultiAgentChatSystem
import config

# Setup paths
BASE_DIR = os.path.join(os.getcwd(), 'dashboard')
DATA_DIR = os.path.join(BASE_DIR, 'data')

print(f"DEBUG: Initializing ChatAgent with data_dir={DATA_DIR}")

try:
    agent = MultiAgentChatSystem(api_key="dummy_key", data_dir=DATA_DIR)
    
    players = agent.data.get('players', {})
    print(f"DEBUG: Players Dict Size: {len(players)}")
    
    if players:
        print(f"DEBUG: Sample Player: {list(players.items())[0]}")
    
    # Check stats for Haaland (ID: 061vq)
    stats_cache = agent.data.get('stats_cache', {})
    print(f"DEBUG: Stats Cache Size: {len(stats_cache)}")
    
    
    # Check if we have ANY data for Week 24
    w24_count = 0
    sample_w24 = None
    for k in stats_cache.keys():
        if k.endswith('_24'):
            w24_count += 1
            if not sample_w24: sample_w24 = k
            
    print(f"DEBUG: Entries for Week 24: {w24_count}")
    if sample_w24:
        print(f"DEBUG: Sample Week 24 entry: {sample_w24} -> {stats_cache[sample_w24]}")
    else:
        print("DEBUG: NO DATA FOR WEEK 24 FOUND.")
        
    # Check max week found
    max_week = 0
    for k in stats_cache.keys():
        try:
             _, w = k.rsplit('_', 1)
             w = int(w)
             if w > max_week: max_week = w
        except: continue
    print(f"DEBUG: Max Week found in stats_cache: {max_week}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
