
import requests
import json
import time

URL = "http://127.0.0.1:8000/api/chat"

def send_message(msg):
    print(f"\nUser: {msg}")
    try:
        start_time = time.time()
        response = requests.post(URL, json={"message": msg}, timeout=90)
        duration = time.time() - start_time
        
        print(f"Status: {response.status_code} ({duration:.2f}s)")
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('message', 'No message')
            print(f"Agent: {answer[:300]}...") # Truncate for readability
            
            # Check for specific success indicators in the response
            return answer
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None

def test_refinement():
    print("=== Testing Context Refinement Agent ===")
    
    # 1. Establish Contex
    q1 = "Who is the best player on Shawn's team?"
    ans1 = send_message(q1)
    
    if ans1 and "Bruno Guimaraes" in ans1 or "251" in ans1: 
        print("✅ SUCCESS: Found best player (Bruno Guimaraes)")
    else:
        print("❌ FAILURE: Did not find best player or context is wrong.")
    
    # 2. Test Refinement (Ambiguous Query)
    # The agent should refine "he" -> "Bruno Guimaraes" and answer "Newcastle"
    q2 = "What team is he on?"
    ans2 = send_message(q2)
    
    if ans2:
        if "Newcastle" in ans2 or "newcastle" in ans2.lower():
             print("✅ SUCCESS: Refined 'he' to Bruno and identified Newcastle.")
        else:
             print("❌ FAILURE: Did not identify Newcastle. Refinement might have failed.")
             
if __name__ == "__main__":
    test_refinement()
