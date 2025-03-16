import logging
import os
import sys

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_FILE

def setup_logging():
    """
    Configure logging for the application
    """
    # Create directory for log file if it doesn't exist
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Remove any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create a formatter for detailed output
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Create a file handler for the log file
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Create a console handler for stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Set to INFO to show important messages only
    console_handler.setFormatter(formatter)
    
    # Configure the root logger
    root_logger.setLevel(logging.INFO)  # Set to INFO for less verbose logging
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log startup message
    logging.info("🚀 Logging initialized")
    
    return logging.getLogger()

def log_startup_info(version="1.0.0"):
    """
    Log startup information
    """
    logging.info("=" * 50)
    logging.info(f"📱 iMessage AI Assistant v{version}")
    logging.info("=" * 50)
    logging.info(f"📝 Log file: {LOG_FILE}")
    
    # Log system information
    import platform
    logging.info(f"💻 System: {platform.system()} {platform.release()} ({platform.machine()})")
    logging.info(f"🐍 Python: {platform.python_version()}")
    
    # Log OpenAI package version
    try:
        import openai
        logging.info(f"🤖 OpenAI SDK: {openai.__version__}")
    except (ImportError, AttributeError):
        logging.warning("⚠️ OpenAI SDK version could not be determined")
        
    # Log additional package versions
    try:
        import requests
        logging.info(f"🌐 Requests: {requests.__version__}")
    except (ImportError, AttributeError):
        pass
        
    try:
        import backoff
        logging.info(f"🔄 Backoff: {backoff.__version__}")
    except (ImportError, AttributeError):
        pass
        
    try:
        from PIL import __version__ as pil_version
        logging.info(f"🖼️ Pillow: {pil_version}")
    except (ImportError, AttributeError):
        pass
        
    logging.info("=" * 50)
    logging.info("📋 Logging configuration complete - all activity will be logged")
    logging.info("=" * 50) 