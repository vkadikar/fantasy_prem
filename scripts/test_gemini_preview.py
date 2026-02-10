
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.chat_agent import ChatAgent
from config import GEMINI_API_KEY

def test_preview_model():
    print("Initializing ChatAgent...")
    agent = ChatAgent(api_key=GEMINI_API_KEY)
    
    print("\nTesting 'gemini-3-flash-preview' model...")
    try:
        response = agent._call_gemini(
            prompt="Hello! Are you the Gemini 3 Flash Preview model? Please confirm.",
            model="gemini-3-flash-preview"
        )
        print("\n--- RESPONSE START ---")
        print(response)
        print("--- RESPONSE END ---")
        print("\nSUCCESS: Model endpoint is working.")
    except Exception as e:
        print(f"\nFAILURE: Error calling model: {e}")

if __name__ == "__main__":
    test_preview_model()
