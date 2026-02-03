
import sys
import os
import json

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dashboard.chat_agent import MultiAgentChatSystem
import config

# Mock Config if needed
config.API_KEY = os.environ.get("GEMINI_API_KEY")

def test_mcp_logic():
    print("Initializing Chat Agent (with MCP)...")
    try:
        agent = MultiAgentChatSystem(api_key=config.API_KEY)
        
        # Test Query that SHOULD trigger reddit search
        query = "Search reddit for Bukayo Saka"
        print(f"\nQuery: {query}")
        
        # We process query - this will attempt to run real code
        # Since CREDENTIALS are likely default, it might fail/return error string from tool
        # But we want to see if it TRIES to call search_reddit
        
        response = agent.process_query(query)
        
        print("\n--- Response ---")
        msg = response.get('message', 'No message')
        print(msg)
        
        # Check history to see if code called search_reddit
        history = agent.conversation_history
        found_tool_call = False
        for entry in history:
            if 'code' in entry and 'search_reddit' in entry['code']:
                found_tool_call = True
                print("\n[PASS] Agent generated code to call `search_reddit`.")
                break
                
        if not found_tool_call:
            print("\n[FAIL] Agent did NOT generate `search_reddit` call.")
            
    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    test_mcp_logic()
