import sqlite3
import logging
import os
import sys
import time
import traceback
import re

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CHAT_DB_PATH, ATTACHMENTS_DIR

# Global variable to track the last processed message ID
# Will be initialized to the most recent message ID when the script starts
LAST_PROCESSED_ID = None

# Time windows for grouping messages (in seconds)
IMESSAGE_GROUP_WINDOW = 120  # 2 minutes for iMessage
SMS_GROUP_WINDOW = 300      # 5 minutes for SMS

# Cache for attachment paths to avoid redundant lookups
ATTACHMENT_PATH_CACHE = {}

# Connection pool for database connections
DB_CONNECTION = None

def initialize_last_processed_id():
    """
    Initialize LAST_PROCESSED_ID to the most recent message ID in the database
    """
    global LAST_PROCESSED_ID
    
    try:
        conn = get_db_connection()
        if conn is None:
            logging.error("❌ Failed to get database connection")
            return
            
        cursor = conn.cursor()
        
        # Get the most recent message ID
        cursor.execute("SELECT MAX(ROWID) FROM message")
        max_id = cursor.fetchone()[0]
        
        if max_id:
            LAST_PROCESSED_ID = max_id
            logging.info(f"🔍 Initialized LAST_PROCESSED_ID to {LAST_PROCESSED_ID}")
        else:
            LAST_PROCESSED_ID = 0
            logging.info("🔍 No messages found in database, initialized LAST_PROCESSED_ID to 0")
    except Exception as e:
        logging.error(f"❌ Error initializing LAST_PROCESSED_ID: {e}")
        LAST_PROCESSED_ID = 0
        logging.info("🔍 Error occurred, initialized LAST_PROCESSED_ID to 0")

def extract_text_from_attributed_body(attributed_body):
    """
    Extract text from attributedBody binary data by directly parsing the binary structure.
    This function is designed to handle various message formats including those with apostrophes.
    """
    if not attributed_body:
        return None
    
    # Convert to string for inspection
    text_data = attributed_body.decode('utf-8', errors='ignore')
    
    # PRIMARY METHOD: Extract text between NSString+ and iI
    # This is the most reliable method based on observed message patterns
    nsstring_match = re.search(r'NSString[^+]*\+', text_data)
    ii_match = re.search(r'iI', text_data)
    
    if nsstring_match and ii_match and nsstring_match.end() < ii_match.start():
        start_idx = nsstring_match.end()
        end_idx = ii_match.start()
        extracted_text = text_data[start_idx:end_idx]
        
        # Clean up the extracted text
        # Remove leading special characters, numbers, or single letters that might be part of the binary format
        extracted_text = re.sub(r'^[%#@*&^!0-9]+', '', extracted_text)
        
        # Remove a single leading character if it's followed by a capital letter
        # This handles cases like "FCreate" or "HGenerate"
        extracted_text = re.sub(r'^[a-zA-Z](?=[A-Z])', '', extracted_text)
        
        # Handle apostrophe cases
        if extracted_text.startswith("hat's "):
            extracted_text = "W" + extracted_text
        elif extracted_text.startswith("t's "):
            extracted_text = "I" + extracted_text
        
        # If the text is substantial, return it
        if len(extracted_text.strip()) > 2:
            return extracted_text.strip()
    
    # BACKUP METHOD: If NSString+/iI method fails, try to find the longest meaningful text sequence
    sequences = []
    current_sequence = ""
    for byte in attributed_body:
        if 32 <= byte <= 126:  # Printable ASCII
            current_sequence += chr(byte)
        elif current_sequence:
            if len(current_sequence) >= 5:  # Only consider sequences of at least 5 characters
                sequences.append(current_sequence)
            current_sequence = ""
    
    if current_sequence and len(current_sequence) >= 5:
        sequences.append(current_sequence)
    
    # Filter out system strings
    system_strings = [
        'nsstring', 'nsobject', 'nsattributed', 'nsdictionary', 'nsarray', 
        'nsnumber', 'nsvalue', 'nsdata', 'nsmutable', 'streamtyped', '__k'
    ]
    
    filtered_sequences = [s for s in sequences 
                         if not any(x in s.lower() for x in system_strings)]
    
    # Find potential message text (longer sequences that look like natural language)
    potential_text = [s for s in filtered_sequences if len(s) > 5 and re.search(r'[A-Za-z]', s)]
    
    # Look for sequences that start with common command or question words
    for seq in sequences:
        # Clean up the sequence first
        cleaned_seq = re.sub(r'^[^a-zA-Z]+', '', seq)  # Remove leading non-alphabetic characters
        cleaned_seq = re.sub(r'^[a-zA-Z](?=[A-Z])', '', cleaned_seq)  # Remove single leading character before capital
        
        # Check for command patterns (create, generate, etc.)
        if re.match(r'^(create|make|generate|show|tell|find|search|look|get|give|send|write|draw|calculate|compute|analyze|explain|describe)\s', cleaned_seq.lower()):
            if len(cleaned_seq) > 10:  # Make sure it's a substantial command
                return cleaned_seq
        
        # Check for question patterns (how, what, when, etc.)
        if re.match(r'^(how|what|when|where|why|who|which|whose|whom|can|could|would|should|is|are|do|does|did|has|have|had)\s', cleaned_seq.lower()):
            if len(cleaned_seq) > 10:  # Make sure it's a substantial question
                return cleaned_seq
    
    if potential_text:
        # Get the longest potential text
        longest_text = max(potential_text, key=len)
        
        # Clean up the longest text
        longest_text = re.sub(r'^[^a-zA-Z]+', '', longest_text)  # Remove leading non-alphabetic characters
        longest_text = re.sub(r'^[a-zA-Z](?=[A-Z])', '', longest_text)  # Remove single leading character before capital
        
        # Fix common issues with extracted text
        if longest_text.startswith("s "):
            return "What'" + longest_text
        
        return longest_text
    
    return None

def get_db_connection():
    """
    Get a connection to the iMessage database
    
    Returns:
        sqlite3.Connection: Database connection
    """
    global DB_CONNECTION
    
    if DB_CONNECTION is None:
        try:
            # Create a new connection
            DB_CONNECTION = sqlite3.connect(CHAT_DB_PATH)
            # Enable foreign keys
            DB_CONNECTION.execute("PRAGMA foreign_keys = ON")
            # Set timeout to avoid database locked errors
            DB_CONNECTION.execute("PRAGMA busy_timeout = 5000")
            logging.info(f"🔌 Connected to database: {CHAT_DB_PATH}")
        except sqlite3.Error as e:
            logging.error(f"❌ Database connection error: {e}")
            return None
    
    return DB_CONNECTION

def debug_attributed_body(rowid, attributed_body):
    """
    Debug function to log the raw attributedBody data for a message
    
    Args:
        rowid (int): The message ID
        attributed_body (bytes): The attributedBody binary data
    """
    if not attributed_body:
        logging.debug(f"No attributedBody for message {rowid}")
        return
    
    try:
        # Convert to string and log the first 200 characters
        text_data = attributed_body.decode('utf-8', errors='ignore')
        logging.debug(f"Raw attributedBody for message {rowid} (first 200 chars): {text_data[:200]}")
        
        # Log the hex representation of the first 100 bytes
        hex_data = ' '.join(f'{b:02x}' for b in attributed_body[:100])
        logging.debug(f"Hex attributedBody for message {rowid} (first 100 bytes): {hex_data}")
        
        # Try to find NSString patterns
        nsstring_matches = re.findall(r'NSString[^"]*"([^"]*)"', text_data)
        if nsstring_matches:
            logging.debug(f"NSString matches for message {rowid}: {nsstring_matches}")
        
        # Try to find text after NSString
        nsstring_match = re.search(r'NSString[^A-Za-z0-9]*\+?([A-Za-z0-9\s.,!?\'"-_@#$%^&*()+=<>{}[\]|\\:;]+)', text_data)
        if nsstring_match:
            raw_text = nsstring_match.group(1)
            logging.debug(f"Raw text after NSString for message {rowid}: '{raw_text}'")
            
            # Show the cleaned text
            cleaned_text = re.sub(r'^[+%#@*&^!]+', '', raw_text).strip()
            logging.debug(f"Cleaned text after NSString for message {rowid}: '{cleaned_text}'")
        
        # Extract text using our main function
        extracted_text = extract_text_from_attributed_body(attributed_body)
        logging.debug(f"Final extracted text for message {rowid}: '{extracted_text}'")
    except Exception as e:
        logging.error(f"Error debugging attributedBody for message {rowid}: {e}")
        logging.error(traceback.format_exc())

def get_latest_imessages():
    """
    Retrieve the latest unprocessed messages from the iMessage database
    
    Returns:
        list: List of new message tuples
    """
    global LAST_PROCESSED_ID
    
    # Initialize LAST_PROCESSED_ID if it's None
    if LAST_PROCESSED_ID is None:
        initialize_last_processed_id()
        # Return empty list on first run to avoid processing old messages
        return []
    
    start_time = time.time()
    
    try:
        conn = get_db_connection()
        if conn is None:
            logging.error("❌ Failed to get database connection")
            return []
            
        cursor = conn.cursor()

        # Query to get all messages with their details
        # Modified to include messages with either text OR attributedBody
        query = """
        SELECT 
            message.ROWID,
            handle.id AS sender,
            message.text,
            attachment.filename,
            handle.service,
            message.date,
            attachment.mime_type,
            message_attachment_join.message_id,
            chat.guid as chat_guid,
            message.date,
            message.attributedBody
        FROM message 
        LEFT JOIN handle ON message.handle_id = handle.ROWID
        LEFT JOIN message_attachment_join ON message.ROWID = message_attachment_join.message_id
        LEFT JOIN attachment ON message_attachment_join.attachment_id = attachment.ROWID
        LEFT JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        LEFT JOIN chat ON chat_message_join.chat_id = chat.ROWID
        WHERE message.is_from_me = 0 
        AND (
            message.text IS NOT NULL 
            OR message.attributedBody IS NOT NULL
            OR attachment.mime_type LIKE 'image/%'
            OR attachment.mime_type LIKE 'audio/%'
            OR attachment.filename LIKE '%.pdf'
            OR attachment.filename LIKE '%.docx'
            OR attachment.filename LIKE '%.xlsx'
            OR attachment.filename LIKE '%.rtf'
            OR attachment.filename LIKE '%.txt'
        )
        AND message.ROWID > ?
        ORDER BY message.date ASC;
        """
        
        cursor.execute(query, (LAST_PROCESSED_ID,))
        messages = cursor.fetchall()
        
        # Process the messages to extract text from attributedBody if text is NULL
        processed_messages = []
        for message in messages:
            # Unpack the message tuple
            rowid, sender, text, filename, service, date, mime_type, message_id, chat_guid, date_again, attributed_body = message
            
            # If text is NULL but attributedBody is not, extract text from attributedBody
            if text is None and attributed_body is not None:
                # Debug the attributedBody data
                debug_attributed_body(rowid, attributed_body)
                
                extracted_text = extract_text_from_attributed_body(attributed_body)
                if extracted_text:
                    logging.info(f"📝 Extracted text from attributedBody for message {rowid}: {extracted_text}")
                    # Create a new message tuple with the extracted text
                    message = (rowid, sender, extracted_text, filename, service, date, mime_type, message_id, chat_guid, date_again)
                else:
                    # If we couldn't extract text, keep the original message
                    message = message[:-1]  # Remove the attributedBody field
            else:
                # If text is not NULL, keep the original message without attributedBody
                message = message[:-1]  # Remove the attributedBody field
            
            processed_messages.append(message)
        
        if not processed_messages:
            logging.debug("No new messages found")
            return []
            
        logging.info(f"📥 Found {len(processed_messages)} new messages")
        
        if processed_messages:
            LAST_PROCESSED_ID = processed_messages[-1][0]
            logging.info(f"🔍 Updated LAST_PROCESSED_ID to {LAST_PROCESSED_ID}")
            
        end_time = time.time()
        logging.debug(f"get_latest_imessages took {end_time - start_time:.2f} seconds")
        
        return processed_messages
        
    except sqlite3.Error as e:
        logging.error(f"❌ Database error in get_latest_imessages: {e}")
        traceback.print_exc()
        return []
    except Exception as e:
        logging.error(f"❌ Unexpected error in get_latest_imessages: {e}")
        traceback.print_exc()
        return []

def group_related_messages(messages, time_window_seconds=None):
    """
    Group messages from the same sender that arrive within a short time window
    
    Args:
        messages (list): List of message tuples
        time_window_seconds (int, optional): Time window in seconds
        
    Returns:
        list: List of grouped message lists
    """
    if not messages:
        return []
    
    start_time = time.time()
    
    # Use the default time windows if time_window_seconds is not provided
    if time_window_seconds is None:
        time_window_seconds = IMESSAGE_GROUP_WINDOW
        
    grouped_messages = []
    current_group = [messages[0]]
    
    for i in range(1, len(messages)):
        current_message = messages[i]
        previous_message = messages[i-1]
        
        # Extract sender, service, and timestamp
        current_sender = current_message[1]  # sender
        previous_sender = previous_message[1]  # sender
        current_service = current_message[4]  # service
        previous_service = previous_message[4]  # service
        current_time = current_message[9]  # date
        previous_time = previous_message[9]  # date
        
        # Convert iMessage timestamps to seconds
        # iMessage timestamps are in nanoseconds since 2001-01-01
        current_time_seconds = current_time / 1000000000 + 978307200
        previous_time_seconds = previous_time / 1000000000 + 978307200
        time_diff = current_time_seconds - previous_time_seconds
        
        # Use a longer time window for SMS messages
        adjusted_time_window = SMS_GROUP_WINDOW if current_service == 'SMS' or previous_service == 'SMS' else IMESSAGE_GROUP_WINDOW
        
        # If from same sender and within time window, add to current group
        if current_sender == previous_sender and time_diff <= adjusted_time_window:
            current_group.append(current_message)
        else:
            # Start a new group
            grouped_messages.append(current_group)
            current_group = [current_message]
    
    # Add the last group
    if current_group:
        grouped_messages.append(current_group)
    
    end_time = time.time()
    logging.info(f"🔄 Grouped {len(messages)} messages into {len(grouped_messages)} groups in {end_time - start_time:.2f} seconds")
    
    return grouped_messages

def resolve_attachment_path(attachment_filename):
    """
    Resolve the full path to an attachment file
    
    Args:
        attachment_filename (str): Relative path to the attachment
        
    Returns:
        str: Full path to the attachment
    """
    if not attachment_filename:
        return None
    
    # Check cache first
    if attachment_filename in ATTACHMENT_PATH_CACHE:
        return ATTACHMENT_PATH_CACHE[attachment_filename]
        
    try:
        # Extract the relative path components
        path_components = attachment_filename.split('/')
        
        # The last 4 components form the path within the Attachments directory
        if len(path_components) >= 4:
            relative_path = '/'.join(path_components[-4:])
            full_path = os.path.join(ATTACHMENTS_DIR, relative_path)
            
            if os.path.exists(full_path):
                ATTACHMENT_PATH_CACHE[attachment_filename] = full_path
                return full_path
                
        # Try a direct join as fallback
        direct_path = os.path.join(ATTACHMENTS_DIR, attachment_filename)
        if os.path.exists(direct_path):
            ATTACHMENT_PATH_CACHE[attachment_filename] = direct_path
            return direct_path
            
        # Search for the file in the Attachments directory
        for root, dirs, files in os.walk(ATTACHMENTS_DIR):
            filename = os.path.basename(attachment_filename)
            if filename in files:
                full_path = os.path.join(root, filename)
                ATTACHMENT_PATH_CACHE[attachment_filename] = full_path
                return full_path
                
        logging.warning(f"⚠️ Could not find attachment: {attachment_filename}")
        return None
        
    except Exception as e:
        logging.error(f"❌ Error resolving attachment path: {e}")
        return None

def cleanup_db_connection():
    """
    Close the database connection
    """
    global DB_CONNECTION
    
    if DB_CONNECTION is not None:
        try:
            DB_CONNECTION.close()
            DB_CONNECTION = None
            logging.info("🔌 Closed database connection")
        except sqlite3.Error as e:
            logging.error(f"❌ Error closing database connection: {e}")

def clear_attachment_cache():
    """
    Clear the attachment path cache
    """
    global ATTACHMENT_PATH_CACHE
    
    cache_size = len(ATTACHMENT_PATH_CACHE)
    ATTACHMENT_PATH_CACHE.clear()
    logging.info(f"🧹 Cleared attachment path cache ({cache_size} entries)") 