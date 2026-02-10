
import os
import sys
import requests
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GEMINI_API_KEY

def test_simple_preview():
    print("Testing 'gemini-3-flash-preview' model endpoint directly...")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    data = {
        "contents": [{
            "parts": [{"text": "Hello! Please confirm if you are the Gemini 3 Flash Preview model."}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Response Body:")
            print(json.dumps(response.json(), indent=2))
            print("\nSUCCESS: Model endpoint is reachable and responding.")
        else:
            print(f"FAILURE: HTTP {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"\nFAILURE: Exception during request: {e}")

if __name__ == "__main__":
    test_simple_preview()
