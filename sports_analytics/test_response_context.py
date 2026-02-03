
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
            ans = data.get('message', 'No message')
            print(f"Agent: {ans[:400]}...") 
            return ans
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None

def test_context_continuity():
    print("=== Testing Context Continuity ===")
    
    # Turn 1: Establish context
    send_message("Who is the top scorer for Newcastle?")
    
    # Turn 2: Ambiguous query
    # "his" should refer to the player found in Turn 1 (likely Isak or Gordon or similar)
    ans = send_message("How many goals does he have?")
    
    if ans:
        # Check if agent asks "Who is he?" (Failure) or answers with a number/name (Success)
        if "who" in ans.lower() and "he" in ans.lower() and "?" in ans:
             print("❌ FAILURE: Agent seems confused about who 'he' is.")
        else:
             print("✅ SUCCESS: Agent likely understood the reference.")

if __name__ == "__main__":
    test_context_continuity()
