
import requests
import json
import time

URL = "http://127.0.0.1:8000/api/chat"

def test_injury_query():
    print("=== Testing Injury Query ===")
    
    # "Is Saka injured?"
    msg = "Is Saka injured?"
    
    print(f"User: {msg}")
    try:
        response = requests.post(URL, json={"message": msg}, timeout=90)
        if response.status_code == 200:
            data = response.json()
            ans = data.get('message', '')
            print(f"Agent Response: {ans[:300]}...")
            
            if "Available" in ans or "Out" in ans or "GTD" in ans:
                print("✅ SUCCESS: Agent reported an injury status.")
            else:
                print("⚠️ WARNING: Agent response might miss the status.")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_injury_query()
