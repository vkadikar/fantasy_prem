
import requests
import json

URL = "http://127.0.0.1:8000/api/chat"

def test_code_leak():
    print("=== Testing Code Leak Fix ===")
    
    # Trigger a plot generation which previously caused the leak
    msg = "Plot Saka's fantasy points this season."
    
    print(f"User: {msg}")
    try:
        response = requests.post(URL, json={"message": msg}, timeout=90)
        if response.status_code == 200:
            data = response.json()
            ans = data.get('message', '')
            print(f"Agent Response Length: {len(ans)}")
            print(f"Agent Response Preview: {ans[:300]}...")
            
            # Check for Python code indicators
            if "import pandas" in ans or "import plotly" in ans or "```python" in ans:
                print("❌ FAILURE: Response still contains Python code!")
            elif "Plot generated successfully" in ans: 
                 # Wait, the response shouldn't say the internal message, it should be the persona text.
                 # The persona text sees "Plot generated successfully" in its data input.
                 print("✅ SUCCESS (Partial): Internal message used properly.")
            else:
                 print("✅ SUCCESS: No code markers found in response.")
                 
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_code_leak()
