"""
Configuration file for Fantasy Premier League Dashboard
All configuration is loaded from .env file
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# ============================================================================
# League Configuration
# ============================================================================

# IMPORTANT: Update CURRENT_WEEK in .env as the season progresses
# This should be the NEXT unplayed gameweek
CURRENT_WEEK = int(os.getenv('CURRENT_WEEK', '24'))

# Fantrax League ID
LEAGUE_ID = os.getenv('LEAGUE_ID', 'de19pr8smd5cytbm')

# ============================================================================
# API Keys
# ============================================================================

# Google Gemini API Key (REQUIRED for chat functionality)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not set in .env file. Chat functionality will not work.")

# ============================================================================
# Data Paths
# ============================================================================

# Data directory for storing dashboard data
DATA_DIR = os.getenv('DATA_DIR', './dashboard/data')

# ============================================================================
# Prediction Settings
# ============================================================================

# Enable/disable prediction caching
PREDICTION_CACHE_ENABLED = os.getenv('PREDICTION_CACHE_ENABLED', 'true').lower() == 'true'

# Number of trees in Random Forest models
PREDICTION_N_ESTIMATORS = int(os.getenv('PREDICTION_N_ESTIMATORS', '250'))

# ============================================================================
# Reddit API Credentials (for MCP Server)
# ============================================================================
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.environ.get("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.environ.get("REDDIT_USERNAME")
REDDIT_PASSWORD = os.environ.get("REDDIT_PASSWORD")
