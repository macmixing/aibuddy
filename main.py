#!/usr/bin/env python3
"""
AI Buddy
A modular AI assistant for iMessage that can respond to messages, analyze images,
process documents, search the web, and more.
"""

import os
import sys
import signal
import json
import logging
import time
import traceback
import argparse
import platform

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up signal handlers for graceful shutdown
def signal_handler(sig, frame):
    print("👋 Received shutdown signal, saving token usage...")
    try:
        from utils.token_tracking import force_save_token_usage
        force_save_token_usage()
    except Exception as e:
        print(f"❌ Error saving token usage on shutdown: {e}")
    print("👋 Shutting down iMessage AI Assistant...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print("Starting iMessage AI Assistant...")
print("Importing configuration...")

# Import configuration
from config import (
    OPENAI_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID, 
    ASSISTANT_ID, PICTURES_DIR, LOG_FILE, TOKEN_USAGE_DIR, TOKEN_USAGE_FILE,
    THREAD_MESSAGE_LIMIT, ensure_directories_exist, VERSION, POLLING_INTERVAL
)

print("Importing utility modules...")

# Import utility modules
from utils.logging_setup import setup_logging
from utils.file_handling import cleanup_temp_files
from utils.token_tracking import track_token_usage, save_token_usage, set_save_on_each_request

print("Importing AI modules...")

# Import AI modules
try:
    from ai.assistant import create_assistant_thread, get_ai_assistant_response
except ImportError:
    # Fallback if the module doesn't exist
    def create_assistant_thread(chat_guid):
        pass
    def get_ai_assistant_response(chat_guid, message):
        return "I'm sorry, I'm having trouble connecting to my AI backend. Please try again later."
    print("Warning: ai.assistant module not found, using fallback")

print("Importing messaging module...")

# Import messaging module
try:
    from messaging.imessage import monitor_messages, process_message_group
except ImportError:
    def monitor_messages():
        print("❌ Error: messaging module not found")
    def process_message_group(message_group):
        pass
    print("Warning: messaging.imessage module not found, using fallback")

print("Importing web module...")

# Import web module
try:
    from web.search import search_web, clean_search_cache
except ImportError:
    def search_web(query, num_results=5):
        return f"I'm sorry, I can't search the web right now. Query: {query}"
    def clean_search_cache():
        pass
    print("Warning: web.search module not found, using fallback")

# Configure logging
setup_logging()

# Log startup information
logging.info("🚀 Starting iMessage AI Assistant...")
logging.info(f"🔧 System: {sys.platform} {os.uname().release}")
logging.info(f"🐍 Python: {sys.version}")

# Check for required API keys
if not OPENAI_API_KEY:
    logging.error("❌ OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    sys.exit(1)

# Log configuration
logging.info(f"📁 Images directory: {PICTURES_DIR}")
logging.info(f"📁 Logs directory: {os.path.dirname(LOG_FILE)}")
logging.info(f"📁 Token usage directory: {TOKEN_USAGE_DIR}")
logging.info(f"📄 Token usage file: {TOKEN_USAGE_FILE}")
logging.info(f"🔄 Thread message limit: {THREAD_MESSAGE_LIMIT}")

# Log feature enhancements
logging.info("📝 Context-aware image analysis: using user context when provided, detailed instructions otherwise")
logging.info("🔄 Improved image format handling with automatic PNG to JPG conversion")
logging.info("🔄 Prioritizing Assistant API for image follow-up questions to maintain context")
logging.info("🔗 Improved URL handling: URLs are now properly grouped with messages and processed as shared links")
logging.info("🛡️ Enhanced duplicate message prevention to avoid processing the same message multiple times")
logging.info("🔄 Improved product correction handling: detecting and prioritizing corrected product information")

# Ensure directories exist
ensure_directories_exist()

def main():
    """Main function to start the iMessage AI Assistant."""
    print("Starting iMessage AI Assistant...")
    print("Importing configuration...")
    
    # Ensure required directories exist
    ensure_directories_exist()
    
    # Set up logging
    setup_logging()
    
    # Initialize token usage tracking
    try:
        from utils.token_tracking import start_periodic_save, set_save_on_each_request, force_save_token_usage
        start_periodic_save()
        logging.info("✅ Started periodic token usage saving")
        
        # Optionally enable saving on each request
        set_save_on_each_request(True)
        logging.info("✅ Enabled token usage saving on each request")
        
        # Register shutdown hook
        import atexit
        atexit.register(force_save_token_usage)
        logging.info("✅ Registered token usage saving on shutdown")
    except Exception as e:
        logging.error(f"❌ Error initializing token tracking: {e}")
        print(f"❌ Error initializing token tracking: {e}")
    
    # Set thread message limit
    try:
        from ai.assistant import set_thread_message_limit
        set_thread_message_limit(THREAD_MESSAGE_LIMIT)
        logging.info(f"✅ Set thread message limit to {THREAD_MESSAGE_LIMIT}")
    except Exception as e:
        print(f"❌ Error setting thread message limit: {e}")
    
    # Print startup message
    logging.info("=" * 80)
    logging.info(f"🤖 iMessage AI Assistant v{VERSION} starting up")
    logging.info(f"💻 System: {platform.system()} {platform.release()}")
    logging.info(f"📂 Working directory: {os.getcwd()}")
    logging.info(f"📝 Log file: {LOG_FILE}")
    logging.info(f"🔄 Polling interval: {POLLING_INTERVAL} seconds")
    logging.info("=" * 80)
    
    # Initialize the last processed message ID
    try:
        from database.message_db import initialize_last_processed_id
        initialize_last_processed_id()
        logging.info("✅ Initialized last processed message ID")
    except Exception as e:
        logging.error(f"❌ Error initializing last processed message ID: {e}")
        print(f"❌ Error initializing last processed message ID: {e}")
    
    # Start monitoring messages
    try:
        monitor_messages()
    except KeyboardInterrupt:
        logging.info("👋 Shutting down iMessage AI Assistant...")
        print("👋 Shutting down iMessage AI Assistant...")
        # Save token usage before exiting
        try:
            from utils.token_tracking import force_save_token_usage
            force_save_token_usage()
            logging.info("💾 Saved token usage data before shutdown")
        except Exception as e:
            logging.error(f"❌ Error saving token usage on shutdown: {e}")
    except Exception as e:
        logging.error(f"❌ Error in main function: {e}")
        logging.error(traceback.format_exc())
        print(f"❌ Error: {e}")
        # Save token usage even on error
        try:
            from utils.token_tracking import force_save_token_usage
            force_save_token_usage()
            logging.info("💾 Saved token usage data before shutdown")
        except Exception as save_error:
            logging.error(f"❌ Error saving token usage on shutdown: {save_error}")

def load_api_keys_from_config():
    """Check and validate API keys from config.py."""
    global OPENAI_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID, ASSISTANT_ID
    
    # Validate API keys
    if not OPENAI_API_KEY:
        logging.error("❌ OPENAI_API_KEY is not set in config.py")
        print("❌ OPENAI_API_KEY is not set in config.py")
        
    if not GOOGLE_API_KEY:
        logging.warning("⚠️ GOOGLE_API_KEY is not set in config.py, web search will not work")
        
    if not GOOGLE_CSE_ID:
        logging.warning("⚠️ GOOGLE_CSE_ID is not set in config.py, web search will not work")
        
    if not ASSISTANT_ID:
        logging.warning("⚠️ ASSISTANT_ID is not set in config.py, will create a new assistant")

if __name__ == "__main__":
    import subprocess
    main() 