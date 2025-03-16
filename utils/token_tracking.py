import os
import csv
import logging
import hashlib
import threading
import time as time_module
from datetime import datetime
from collections import Counter

# Import configuration
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TOKEN_USAGE_DIR, TOKEN_USAGE_FILE

# Initialize token usage counters
token_usage_counter = Counter()
last_usage_save = datetime.now()
total_tokens_since_last_save = 0
periodic_save_active = False

# Global flag for saving on each request
SAVE_ON_EACH_REQUEST = False
last_save_time = datetime.now()  # To prevent excessive saves

# Check if token usage file exists and create it if not
if not os.path.exists(TOKEN_USAGE_DIR):
    os.makedirs(TOKEN_USAGE_DIR, exist_ok=True)
    logging.info(f"📊 Created token usage directory: {TOKEN_USAGE_DIR}")

if not os.path.exists(TOKEN_USAGE_FILE):
    # Create the file with headers
    with open(TOKEN_USAGE_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Timestamp", 
            "Date", 
            "Time", 
            "Session_ID", 
            "Model", 
            "Purpose",
            "Prompt_Tokens", 
            "Completion_Tokens", 
            "Total_Tokens", 
            "Cost_USD"
        ])
    logging.info(f"📊 Created token usage file with headers: {TOKEN_USAGE_FILE}")
else:
    logging.info(f"📊 Token usage file exists: {TOKEN_USAGE_FILE}")

def track_token_usage(model, prompt_tokens, completion_tokens, purpose):
    """
    Track token usage for monitoring costs
    """
    global token_usage_counter, last_usage_save, total_tokens_since_last_save, last_save_time
    
    # Update counters
    token_usage_counter[f"{model}_prompt"] += prompt_tokens
    token_usage_counter[f"{model}_completion"] += completion_tokens
    token_usage_counter[f"{model}_total"] += (prompt_tokens + completion_tokens)
    token_usage_counter[f"{purpose}_calls"] += 1
    
    # Update total tokens since last save
    total_tokens_since_last_save += (prompt_tokens + completion_tokens)
    
    # Log usage
    logging.info(f"📊 Token usage: {prompt_tokens} prompt + {completion_tokens} completion = {prompt_tokens + completion_tokens} total ({model}, {purpose})")
    
    # Save on each request if enabled (with a small delay to prevent excessive writes)
    current_time = datetime.now()
    if SAVE_ON_EACH_REQUEST and (current_time - last_save_time).total_seconds() > 1.0:  # At most once per second
        save_token_usage()
        last_save_time = current_time
        last_usage_save = current_time
        total_tokens_since_last_save = 0
        return
    
    # Save more frequently (every 5 minutes instead of 10)
    if (current_time - last_usage_save).total_seconds() > 300:  # 5 minutes
        save_token_usage()
        last_usage_save = current_time
        total_tokens_since_last_save = 0
        
    # Also save after smaller usage (more than 5,000 tokens)
    if total_tokens_since_last_save > 5000:
        save_token_usage()
        last_usage_save = current_time
        total_tokens_since_last_save = 0
        
    # Save after each expensive model call (gpt-4, gpt-4o, dall-e-3)
    expensive_models = ["gpt-4", "gpt-4o", "dall-e-3"]
    if model in expensive_models and (prompt_tokens + completion_tokens) > 1000:
        save_token_usage()
        last_usage_save = current_time
        total_tokens_since_last_save = 0

def save_token_usage():
    """
    Save token usage statistics to CSV file with improved categorization by model and purpose
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(TOKEN_USAGE_DIR, exist_ok=True)
        logging.info(f"📊 Ensuring token usage directory exists: {TOKEN_USAGE_DIR}")
        
        # Define a fixed set of columns for the CSV file to ensure consistency
        fixed_columns = [
            "Timestamp", 
            "Date", 
            "Time", 
            "Session_ID", 
            "Model", 
            "Purpose",
            "Prompt_Tokens", 
            "Completion_Tokens", 
            "Total_Tokens", 
            "Cost_USD"
        ]
        
        # Check if file exists to determine if we need headers
        file_exists = os.path.isfile(TOKEN_USAGE_FILE)
        if not file_exists:
            logging.info(f"📊 Creating new token usage file: {TOKEN_USAGE_FILE}")
        else:
            logging.info(f"📊 Appending to existing token usage file: {TOKEN_USAGE_FILE}")
        
        # Prepare timestamp information
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date = datetime.now().strftime("%Y-%m-%d")
        time_of_day = datetime.now().strftime("%H:%M:%S")
        session_id = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        
        # Define model pricing (per million tokens)
        model_pricing = {
            "gpt-4o": {"input": 5.00, "output": 15.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4": {"input": 10.00, "output": 30.00},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
            "whisper-1": {"input": 0.006, "output": 0.00},  # $0.006 per minute
            "dall-e-3": {"input": 0.04, "output": 0.00}     # $0.04 per 1024x1024 image
        }
        
        # Extract unique models and purposes from the counter
        models = set()
        purposes = set()
        
        for key in token_usage_counter.keys():
            if key.endswith("_prompt") or key.endswith("_completion") or key.endswith("_total"):
                model = key.rsplit("_", 1)[0]
                models.add(model)
            elif key.endswith("_calls"):
                purpose = key.rsplit("_", 1)[0]
                purposes.add(purpose)
        
        # Log what we're about to write
        logging.info(f"📊 Writing token usage for {len(models)} models and {len(purposes)} purposes")
        
        # Open the file in append mode
        with open(TOKEN_USAGE_FILE, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fixed_columns)
            
            # Write header if file is new
            if not file_exists:
                writer.writeheader()
                logging.info(f"📊 Wrote CSV header to {TOKEN_USAGE_FILE}")
            
            # Write a row for each model and purpose combination
            rows_written = 0
            for model in models:
                for purpose in purposes:
                    # Skip if no tokens were used for this combination
                    if token_usage_counter.get(f"{purpose}_calls", 0) == 0:
                        continue
                    
                    prompt_tokens = token_usage_counter.get(f"{model}_prompt", 0)
                    completion_tokens = token_usage_counter.get(f"{model}_completion", 0)
                    total_tokens = prompt_tokens + completion_tokens
                    
                    # Skip if no tokens were used for this model
                    if total_tokens == 0:
                        continue
                    
                    # Calculate cost
                    cost = 0
                    if model in model_pricing:
                        input_cost = (prompt_tokens / 1000000) * model_pricing[model]["input"]
                        output_cost = (completion_tokens / 1000000) * model_pricing[model]["output"]
                        cost = input_cost + output_cost
                    
                    # Write the row
                    writer.writerow({
                        "Timestamp": timestamp,
                        "Date": date,
                        "Time": time_of_day,
                        "Session_ID": session_id,
                        "Model": model,
                        "Purpose": purpose,
                        "Prompt_Tokens": prompt_tokens,
                        "Completion_Tokens": completion_tokens,
                        "Total_Tokens": total_tokens,
                        "Cost_USD": f"{cost:.6f}"
                    })
                    rows_written += 1
            
            logging.info(f"📊 Wrote {rows_written} rows of token usage data to {TOKEN_USAGE_FILE}")
        
        # Reset counters after saving
        token_usage_counter.clear()
        logging.info(f"📊 Token usage counters reset after saving")
        
        logging.info(f"📊 Token usage saved to {TOKEN_USAGE_FILE}")
    except Exception as e:
        logging.error(f"❌ Error saving token usage: {e}")
        import traceback
        logging.error(traceback.format_exc()) 

def force_save_token_usage():
    """
    Force saving token usage statistics immediately
    This is useful for debugging or when you want to ensure the data is saved
    """
    logging.info("📊 Forcing token usage save...")
    save_token_usage()
    return True 

# Function to periodically save token usage
def periodic_save_thread():
    """
    Thread function to periodically save token usage
    """
    global periodic_save_active
    
    while periodic_save_active:
        # Sleep for 5 minutes
        time_module.sleep(300)
        
        # Save token usage if there's anything to save
        if sum(token_usage_counter.values()) > 0:
            logging.info("📊 Periodic token usage save triggered")
            save_token_usage()
        
        # Check if we should exit
        if not periodic_save_active:
            break

# Start the periodic save thread
def start_periodic_save():
    """
    Start the periodic save thread
    """
    global periodic_save_active
    
    if not periodic_save_active:
        periodic_save_active = True
        save_thread = threading.Thread(target=periodic_save_thread, daemon=True)
        save_thread.start()
        logging.info("📊 Started periodic token usage save thread")
        return True
    return False

# Stop the periodic save thread
def stop_periodic_save():
    """
    Stop the periodic save thread
    """
    global periodic_save_active
    
    if periodic_save_active:
        periodic_save_active = False
        logging.info("📊 Stopped periodic token usage save thread")
        return True
    return False 

def set_save_on_each_request(enabled):
    """
    Enable or disable saving token usage on each request
    
    Args:
        enabled (bool): Whether to save on each request
        
    Returns:
        bool: The new setting
    """
    global SAVE_ON_EACH_REQUEST
    SAVE_ON_EACH_REQUEST = enabled
    logging.info(f"📊 Save token usage on each request: {'Enabled' if enabled else 'Disabled'}")
    return SAVE_ON_EACH_REQUEST 