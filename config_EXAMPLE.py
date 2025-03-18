import os

# Version information
VERSION = "1.0.0"

# Application settings
POLLING_INTERVAL = 1  # seconds

# OpenAI API configuration
OPENAI_API_KEY = "ENTER-YOUR-KEY-HERE"
ASSISTANT_ID = "ASSISTANT-ID-HERE"

# Google Custom Search API Key and Search Engine ID
GOOGLE_API_KEY = "ENTER-YOUR-KEY-HERE"
GOOGLE_CSE_ID = "ENTER-YOUR-ID-HERE"
MAX_SEARCH_RESULTS = 5  # Number of search results to retrieve from Google

# Path configurations
CHAT_DB_PATH = os.path.expanduser("~/Library/Messages/chat.db")
ATTACHMENTS_DIR = os.path.expanduser("~/Library/Messages/Attachments")
PICTURES_DIR = os.path.expanduser("~/Pictures/aibuddy/Images")
MEMORY_FILE = os.path.expanduser("~/Pictures/aibuddy/memory.json")
LOG_FILE = os.path.expanduser("~/Pictures/aibuddy/imessage_ai.log")

# Token usage configuration
TOKEN_USAGE_DIR = os.path.expanduser("~/Pictures/aibuddy")
TOKEN_USAGE_FILENAME = "token_usage.csv"
TOKEN_USAGE_FILE = os.path.join(TOKEN_USAGE_DIR, TOKEN_USAGE_FILENAME)

# Feature flags
WEB_SEARCH_ENABLED = True
USE_AI_FOR_SEARCH_DETECTION = True

# AI model configuration
"""Assistant MODEL Setup through OpenAI API"""
DEFAULT_MODEL = "gpt-4o-mini"

# Thread message limit
THREAD_MESSAGE_LIMIT = 10  # Number of most recent messages to keep in thread context (reduces token usage)

# Rate limiting
MAX_REQUESTS_PER_MINUTE = 50
REQUEST_INTERVAL = 60 / MAX_REQUESTS_PER_MINUTE

# Web search configuration
SEARCH_CACHE_EXPIRY = 3600  # Cache search results for 1 hour
MAX_SEARCH_RESULTS = 5

# Create necessary directories if they don't exist
def ensure_directories_exist():
    """Create all necessary directories if they don't exist."""
    directories = [
        PICTURES_DIR,
        TOKEN_USAGE_DIR,
        os.path.dirname(LOG_FILE),
        os.path.dirname(MEMORY_FILE)
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"Created directory: {directory}")

# Call this function when the module is imported
ensure_directories_exist() 