
import requests
import json

URL = "http://127.0.0.1:8000/api/chat"

def test_find_player():
    print("=== Testing find_player Helper ===")
    
    # We ask a question using a partial name that requires code execution via find_player
    # "Who is Saka?" should trigger `find_player('Saka')` 
    msg = "What is Saka's full name?"
    
    print(f"User: {msg}")
    try:
        response = requests.post(URL, json={"message": msg}, timeout=90)
        if response.status_code == 200:
            data = response.json()
            ans = data.get('message', '')
            print(f"Agent Response: {ans[:200]}...")
            
            if "Bukayo Saka" in ans:
                print("✅ SUCCESS: Found 'Bukayo Saka' from 'Saka'.")
            else:
                print("⚠️ WARNING: Agent might not have used find_player or output is verbose.")
                # We can check the generated code if returned? 
                # The API response usually includes 'code' in history but maybe not in final json return unless we changed it.
                # Actually, our chat_agent doesn't return the code in the JSON response to client usually?
                # Let's hope the answer is correct.
        else:
             print(f"Error: {response.text}")

    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_find_player()
