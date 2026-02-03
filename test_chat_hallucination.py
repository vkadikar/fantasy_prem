
import requests
import json
import time

URL = "http://127.0.0.1:8000/api/chat"

def send_message(msg):
    print(f"\nUser: {msg}")
    try:
        response = requests.post(URL, json={"message": msg}, timeout=90)
        if response.status_code == 200:
            data = response.json()
            answer = data.get('message', 'No message')
            print(f"Agent: {answer[:300]}...") 
            return data
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None

def test_hallucination_fix():
    print("=== Testing Hallucination Fix ===")
    
    # This query previously might have triggered a "conversational" response with fake data
    q1 = "Who is winning the league?"
    data = send_message(q1)
    
    if data:
        # Check if code was executed
        if data.get('type') == 'text+table' or data.get('type') == 'text+plot' or (data.get('type') == 'text' and 'CODE_NEEDED: no' not in str(data)):
             # In our current schema, the API returns the final response. 
             # We can check if the response contains specific true data or structure.
             # Ideally we'd peep the internal logs, but checking for known data works too.
             # "Estimated Profit" is a known team name from server.py (Lines 104)
             ans = data.get('message', '')
             if "Estimated Profit" in ans or "FC Purulona" in ans or "Cold FC" in ans:
                 print("✅ SUCCESS: Agent likely fetched real data (Found known team names).")
             else:
                 print("⚠️ WARNING: Agent answer might be generic. Check content manually.")
        else:
            print("❌ FAILURE: Agent might have treated this as pure text without code.")

if __name__ == "__main__":
    test_hallucination_fix()
