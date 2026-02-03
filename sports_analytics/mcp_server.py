
import os
import sys
import json
from typing import List, Dict, Any

# Ensure we can import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

try:
    from mcp.server.fastmcp import FastMCP
    import praw
except ImportError as e:
    print(f"Error: Missing dependencies for MCP server. Please install 'mcp' and 'praw'.\nDetails: {e}", file=sys.stderr)
    sys.exit(1)

# Initialize MCP Server
mcp = FastMCP("Reddit Analytics Server")

# Initialize Reddit Client
def get_reddit():
    return praw.Reddit(
        client_id=config.REDDIT_CLIENT_ID,
        client_secret=config.REDDIT_CLIENT_SECRET,
        user_agent=config.REDDIT_USER_AGENT,
        username=config.REDDIT_USERNAME,
        password=config.REDDIT_PASSWORD
    )

@mcp.tool()
def search_reddit_discussions(query: str, limit: int = 5, subreddits: List[str] = ["FantasyPL", "PremierLeague", "soccer"]) -> str:
    """
    Search Reddit for discussions about a player, team, or topic.
    Returns a formatted string of recent thread titles and top comments/summaries.
    
    Args:
        query: The search term (e.g. "Bukayo Saka", "Arsenal defence")
        limit: Number of threads to return (default 5)
        subreddits: List of subreddits to search (default ["FantasyPL", "PremierLeague", "soccer"])
    """
    try:
        reddit = get_reddit()
        
        # Combine subreddits for multi-sub search: "FantasyPL+PremierLeague"
        sub_query = "+".join(subreddits)
        print(f"Searching r/{sub_query} for '{query}'...", file=sys.stderr)
        
        results = []
        
        # Search specifically in these subreddits
        # sort='top' (best content) with time_filter='week' (recent)
        # Limit to 10 initially, then filter down to TOP 3 matching criteria
        search_limit = 10 
        valid_results = []
        
        for submission in reddit.subreddit(sub_query).search(query, sort='top', time_filter='week', limit=search_limit):
            # FILTER: Exclude EAFC / FIFA video game content
            title_body = (submission.title + " " + (submission.selftext or "")).lower()
            if "eafc" in title_body or "ea fc" in title_body or "fifa" in title_body:
                continue
                
            # FILTER: Simple English heuristic (optional, these subs are mostly english)
            # We skip this for now to avoid installing `langdetect`, assuming user query drives english results.
            
            # Format: Text-focused with context explanation
            thread_data = f"--- Context: Recent discussion from r/{submission.subreddit.display_name} (Score: {submission.score}) ---\n"
            thread_data += f"Title: {submission.title}\n"
            if submission.selftext:
                # Truncate long selftext
                text_body = submission.selftext.replace('\n', ' ')
                if len(text_body) > 500: text_body = text_body[:500] + "..."
                thread_data += f"Post Text: {text_body}\n"
            
            # Get TOP 3 Comments
            submission.comments.replace_more(limit=0)
            top_comments = []
            for comment in submission.comments[:3]:
                # Filter EAFC in comments too? Maybe overkill, just show them.
                body = comment.body.replace('\n', ' ')
                if len(body) > 300: body = body[:300] + "..."
                top_comments.append(f"- \"{body}\"")
            
            if top_comments:
                thread_data += "Relevant Comments:\n" + "\n".join(top_comments) + "\n"
            
            valid_results.append(thread_data)
            
            if len(valid_results) >= 3:
                break
            
        if not valid_results:
            return f"No recent (past week) Reddit discussions found for '{query}' in r/{sub_query} (filtered EAFC content)."
            
        return "\n".join(valid_results)
        
    except Exception as e:
        return f"Error searching Reddit: {str(e)}"

if __name__ == "__main__":
    try:
        mcp.run()
    except Exception as e:
        print(f"MCP Server Error: {e}", file=sys.stderr)
        sys.exit(1)
