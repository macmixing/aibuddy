import subprocess
import logging
import os
import time
import sys
import traceback
import re
import json
import sqlite3
import openai
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.message_db import get_latest_imessages, group_related_messages, resolve_attachment_path, get_db_connection
from config import PICTURES_DIR, OPENAI_API_KEY, ASSISTANT_ID, POLLING_INTERVAL
from utils.file_handling import cleanup_temp_files, get_file_type, download_attachment_to_directory, add_temp_file
from ai.document_analysis import extract_text_from_file
from ai.image_analysis import transcribe_audio, is_image_request
from ai.assistant import get_ai_assistant_response, get_ai_assistant_image_response, get_ai_assistant_document_response
from utils.token_tracking import track_token_usage
from web.search import is_web_search_request, search_web, summarize_search_results, LAST_SEARCH, update_conversation_context, CONVERSATION_CONTEXT

# Set polling interval (in seconds)
DEFAULT_POLLING_INTERVAL = 1.0
# Set a minimum interval between message processing to avoid overloading
MIN_PROCESSING_INTERVAL = 0.1

# Track the last time we processed messages
last_processing_time = 0

# Dictionary to track recently processed message groups to avoid duplicates
RECENTLY_PROCESSED_GROUPS = {}

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

def send_message(recipient, message, service):
    """
    Send message via AppleScript
    
    Args:
        recipient (str): Phone number or email
        message (str): Message text
        service (str): Service type (iMessage or SMS)
        
    Returns:
        bool: Success status
    """
    logging.info(f"📤 Sending message to {recipient} via {service}: {message}")

    service_type = "iMessage" if service and service.lower() == "imessage" else "SMS"
    
    # Escape double quotes in the message
    message = message.replace('"', '\\"')

    script = f'''
    tell application "Messages"
        set targetService to first service whose service type is {service_type}
        set targetBuddy to buddy "{recipient}" of targetService
        send "{message}" to targetBuddy
    end tell
    '''

    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    
    if result.returncode != 0:
        logging.error(f"❌ AppleScript Error: {result.stderr}")
        return False
    return True

def send_image(recipient, image_path, service):
    """
    Send image via AppleScript
    
    Args:
        recipient (str): Recipient phone number or email
        image_path (str): Path to image file
        service (str): Service type (iMessage or SMS)
        
    Returns:
        bool: True if successful, False otherwise
    """
    start_time = time.time()
    logging.info(f"📤 Sending image to {recipient} via {service}: {image_path}")
    
    # Check if file exists
    if not os.path.exists(image_path):
        logging.error(f"❌ Image file not found: {image_path}")
        return False
    
    # Normalize service name to handle different formats
    service_lower = service.lower() if service else ""
    
    # Determine the correct service type for AppleScript
    if service_lower == "imessage" or service_lower == "ichat":
        service_type = "iMessage"
    else:
        # Default to SMS for any other service or if service is None
        service_type = "SMS"
    
    logging.info(f"🔄 Using service type: {service_type} (original: {service})")
    
    # Escape paths with spaces
    image_path = image_path.replace(" ", "\\ ")
    
    script = f'''
    tell application "Messages"
        set targetService to first service whose service type is {service_type}
        set targetBuddy to buddy "{recipient}" of targetService
        send POSIX file "{image_path}" to targetBuddy
    end tell
    '''

    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    
    end_time = time.time()
    if result.returncode != 0:
        logging.error(f"❌ AppleScript Error (Image Message): {result.stderr}")
        return False
    
    logging.info(f"📤 Image sent in {end_time - start_time:.2f} seconds")
    return True

def generate_and_send_image(recipient, prompt_text, service, chat_guid=None):
    """
    Generate an image using DALL-E and send it
    
    This function uses a simplified approach to generate images directly with the OpenAI API,
    avoiding the complexity of multiple layers of duplicate detection that were causing issues.
    It directly calls the OpenAI API, saves the image, and sends it to the recipient.
    
    Args:
        recipient (str): Recipient phone number or email
        prompt_text (str): Image generation prompt
        service (str): Service type (iMessage or SMS)
        chat_guid (str, optional): Chat GUID for conversation tracking
        
    Returns:
        bool: True if successful, False otherwise
    """
    logging.info(f"🎨 Generating image with prompt: {prompt_text}")

    try:
        # Check rate limit before making API call
        from ai.openai_client import check_rate_limit
        check_rate_limit()
        
        # Get the OpenAI API key from config
        from config import OPENAI_API_KEY
        
        # Generate the image (this can take some time)
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt_text,
            n=1,
            size="1024x1024"
        )
        image_url = response.data[0].url
        
        # Track DALL-E usage
        from utils.token_tracking import track_token_usage
        track_token_usage("dall-e-3", 1000, 0, "image_generation")
        
        # Save and send the generated image
        from config import PICTURES_DIR
        image_path = os.path.join(PICTURES_DIR, f"generated_image_{int(time.time())}.png")
        
        logging.info(f"📥 Downloading image from DALL-E to: {image_path}")
        
        img_data = requests.get(image_url).content
        with open(image_path, "wb") as handler:
            handler.write(img_data)

        if os.path.exists(image_path):
            logging.info(f"✅ Image saved successfully, sending to {recipient}")
            send_image(recipient, image_path, service)
            return True
        
        logging.error("❌ Error saving the generated image")
        return False

    except Exception as e:
        logging.error(f"❌ Error generating image: {e}")
        logging.error(traceback.format_exc())
        if isinstance(e, openai.BadRequestError) and ("content_policy_violation" in str(e) or "safety system" in str(e)):
            send_message(recipient, "I couldn't create that image due to content guidelines 🙁 Please try again with a different prompt! 🎨✨", service)
        else:
            send_message(recipient, f"I'm sorry, I encountered an error generating the image: {str(e)}", service)
        return False

def process_message_group(message_group):
    """
    Process a group of related messages
    
    Args:
        message_group (list): List of related message tuples
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    if not message_group:
        return False
        
    # Create a unique identifier for this message group to avoid duplicate processing
    group_id = f"{message_group[0][1]}_{message_group[0][5]}"
    
    # Check if we've recently processed this group
    current_time = time.time()
    if group_id in RECENTLY_PROCESSED_GROUPS:
        last_processed_time = RECENTLY_PROCESSED_GROUPS[group_id]
        if current_time - last_processed_time < 60:  # Within the last minute
            logging.warning(f"⚠️ Skipping duplicate message group from {message_group[0][1]} (processed {current_time - last_processed_time:.1f}s ago)")
            return False
    
    # Update the recently processed groups
    RECENTLY_PROCESSED_GROUPS[group_id] = current_time
    
    # Clean up old entries from the recently processed groups
    for old_group_id in list(RECENTLY_PROCESSED_GROUPS.keys()):
        if current_time - RECENTLY_PROCESSED_GROUPS[old_group_id] > 300:  # Older than 5 minutes
            del RECENTLY_PROCESSED_GROUPS[old_group_id]
    
    # Log the message group
    sender = message_group[0][1]
    logging.info(f"📩 Processing message group from {sender} with {len(message_group)} messages")
    
    # Extract chat_guid from the first message in the group
    chat_guid = message_group[0][8] if len(message_group[0]) > 8 else None
    
    # Extract service type from the first message in the group
    service = message_group[0][4] if len(message_group[0]) > 4 else None
    
    # Debug log: print details for each message in the group
    for msg in message_group:
        rowid, sender, text, filename, msg_service, date, mime_type, message_id, msg_chat_guid, date2 = msg
        logging.debug(f"  Message: ROWID={rowid}, sender={sender}, text={text}, file={filename}, service={msg_service}")
        
        # If the first message doesn't have a chat_guid, try to get it from subsequent messages
        if chat_guid is None and msg_chat_guid:
            chat_guid = msg_chat_guid
            
        # If the first message doesn't have a service, try to get it from subsequent messages
        if service is None and msg_service:
            service = msg_service
    
    # Check if any message in the group has text
    has_text = any(msg[2] for msg in message_group)
    
    # Check if any message in the group has an attachment
    has_attachment = any(msg[3] for msg in message_group)
    
    # Combine all text from the message group
    combined_text = " ".join([msg[2] for msg in message_group if msg[2]])
    
    # Log the service type
    if service:
        logging.info(f"🔄 Message service type: {service}")
    else:
        logging.warning("⚠️ No service type found in message group, defaulting to iMessage")
        service = "iMessage"
    
    # Process attachment if any
    if has_attachment:
        # Flag to track if we've processed a URL attachment in this group
        processed_url_attachment = False
        
        for msg in message_group:
            rowid, sender, text, filename, msg_service, date, mime_type, message_id, msg_chat_guid, date2 = msg
            
            if filename:
                # Skip duplicate URL attachments
                if filename.endswith('.pluginPayloadAttachment'):
                    if processed_url_attachment:
                        logging.info(f"🔗 Skipping duplicate URL attachment in message group: {filename}")
                        continue
                    else:
                        processed_url_attachment = True
                
                # Use the combined text from all messages in the group as context
                attachment_text = combined_text
                
                # If there's no combined text, we'll use an empty string
                if not attachment_text:
                    attachment_text = ""
                    logging.info(f"📎 Processing attachment without text context: {filename}")
                else:
                    logging.info(f"📎 Processing attachment with text context: {filename}")
                    logging.info(f"📝 Text context: {attachment_text}")
                
                # Process the attachment
                process_attachment(sender, filename, mime_type, attachment_text, chat_guid, service)
    
    # Process text if any and no attachment
    elif has_text:
        logging.info(f"💬 Processing text message: {combined_text}")
        
        # Update conversation context with the current message FIRST
        # This ensures the context is available for search detection
        if chat_guid:
            from web.search import update_conversation_context
            update_conversation_context(chat_guid, combined_text)
            logging.info(f"🔍 Updated conversation context with current message before processing")
        
        # Check if this is an image generation request
        if is_image_request(combined_text):
            logging.info(f"🎨 Image generation request detected: {combined_text}")
            
            # Generate and send image using the simplified approach
            generate_and_send_image(sender, combined_text, service, chat_guid)
            return True
        
        # Check if this is a web search request
        search_result = is_web_search_request(combined_text, chat_guid)
        if search_result:
            if isinstance(search_result, str):
                # Use the enhanced query for the search
                search_query = search_result
                logging.info(f"🔍 Detected web search request: {combined_text} (enhanced to: {search_query})")
            else:
                # Use the original query
                search_query = combined_text
                logging.info(f"🔍 Detected web search request: {combined_text}")
            
            # Perform web search
            search_results = search_web(search_query, chat_guid=chat_guid)
            
            # Summarize search results
            summary = summarize_search_results(search_query, search_results, chat_guid=chat_guid)
            
            # Send the summary as a response
            send_imessage(sender, summary, chat_guid=chat_guid, service=service)
            
            # Update conversation context with the search results
            # We already added the original message to context above
            from web.search import update_conversation_context
            update_conversation_context(chat_guid, summary)
            
            # Ensure the search query and results are added to the Assistant thread
            try:
                from ai.assistant import conversation_threads, check_and_wait_for_active_runs
                
                if chat_guid and chat_guid in conversation_threads:
                    thread_id = conversation_threads[chat_guid]
                    
                    # Check for active runs and wait for them to complete
                    if check_and_wait_for_active_runs(thread_id):
                        # Add the user's search query to the thread
                        openai.beta.threads.messages.create(
                            thread_id=thread_id,
                            role="user",
                            content=search_query
                        )
                        
                        # Add the search results as a system message
                        search_results_text = f"Web search results for: '{search_query}'\n\n"
                        for i, result in enumerate(search_results[:5], 1):
                            title = result.get('title', 'No title')
                            snippet = result.get('snippet', 'No snippet')
                            link = result.get('link', 'No link')
                            search_results_text += f"{i}. {title}\n{snippet}\n{link}\n\n"
                        
                        openai.beta.threads.messages.create(
                            thread_id=thread_id,
                            role="user",
                            content=search_results_text
                        )
                        
                        logging.info(f"✅ Added web search results to Assistant thread for context continuity")
                    else:
                        logging.warning(f"⚠️ Could not add web search results to Assistant thread due to active run")
            except Exception as e:
                logging.error(f"❌ Error adding web search results to Assistant thread: {e}")
                logging.error(traceback.format_exc())
            
            return True
        
        # Get AI assistant response
        response = get_ai_assistant_response(chat_guid, combined_text)
        
        # Send the response
        if response:
            send_imessage(sender, response, chat_guid=chat_guid, service=service)
            return True
    
    return True

def monitor_messages(polling_interval=POLLING_INTERVAL):
    """
    Monitor for new messages and process them
    
    Args:
        polling_interval (int): Polling interval in seconds
        
    Returns:
        None
    """
    global last_processing_time
    
    logging.info(f"👀 Starting message monitoring with polling interval of {polling_interval} seconds...")
    
    try:
        while True:
            # Get new messages
            new_messages = get_latest_imessages()
            
            if new_messages:
                logging.info(f"📥 Received {len(new_messages)} new messages")
                
                # Group related messages
                message_groups = group_related_messages(new_messages)
                
                # Process each group
                for group in message_groups:
                    process_message_group(group)
                    # Small delay between processing groups to avoid race conditions
                    time.sleep(0.1)
            
            # Sleep for the polling interval
            time.sleep(polling_interval)
            
    except KeyboardInterrupt:
        logging.info("👋 Message monitoring stopped by user")
    except Exception as e:
        logging.error(f"❌ Error in message monitoring: {e}")
        logging.error(traceback.format_exc())
        raise 

def process_attachment(sender, filename, mime_type, text_context, chat_guid, service="iMessage"):
    """
    Process an attachment file
    
    Args:
        sender (str): Sender phone number or email
        filename (str): Attachment filename
        mime_type (str): MIME type of the attachment
        text_context (str): Text context from the message
        chat_guid (str): Chat GUID for conversation tracking
        service (str, optional): Service type (iMessage or SMS), defaults to "iMessage"
        
    Returns:
        bool: True if processing was successful, False otherwise
    """
    logging.info(f"📎 Processing attachment: {filename} ({mime_type})")
    
    try:
        # Resolve the attachment path
        file_path = resolve_attachment_path(filename)
        
        if not file_path:
            logging.error(f"❌ Could not resolve attachment path: {filename}")
            return False
            
        logging.info(f"📄 Resolved attachment path: {file_path}")
        
        # Determine the file type
        file_type = get_file_type(file_path)
        logging.info(f"📄 File type: {file_type}")
        
        # Special case for Audio Message.caf files which might be detected as unknown
        if "Audio Message.caf" in filename or filename.endswith('.caf'):
            file_type = "audio"
            logging.info(f"🎵 Forcing file type to audio for: {filename}")
            
        # Special case for URL attachments which come as pluginPayloadAttachment
        elif filename.endswith('.pluginPayloadAttachment'):
            logging.info(f"🔗 Detected URL attachment: {filename}")
            
            # If we have text context with URLs, process that directly
            if text_context and ('http://' in text_context.lower() or 'https://' in text_context.lower()):
                # Deduplicate URLs in the text context
                # Split by whitespace, remove duplicates while preserving order, and rejoin
                words = text_context.split()
                unique_words = []
                for word in words:
                    if word not in unique_words:
                        unique_words.append(word)
                deduplicated_text = ' '.join(unique_words)
                
                logging.info(f"🔗 Processing URLs from text context (deduplicated): {deduplicated_text}")
                
                # Check if this is a web search request
                if is_web_search_request(deduplicated_text, chat_guid):
                    if isinstance(is_web_search_request(deduplicated_text, chat_guid), str):
                        # Use the enhanced query for the search
                        search_query = is_web_search_request(deduplicated_text, chat_guid)
                        logging.info(f"🔍 Detected web search request from URL: {deduplicated_text} (enhanced to: {search_query})")
                    else:
                        # Use the original query
                        search_query = deduplicated_text
                        logging.info(f"🔍 Detected web search request from URL: {deduplicated_text}")
                    
                    # Perform web search
                    search_results = search_web(search_query, chat_guid=chat_guid)
                    
                    # Summarize search results
                    summary = summarize_search_results(search_query, search_results, chat_guid=chat_guid)
                    
                    # Send the summary as a response
                    send_imessage(sender, summary, chat_guid=chat_guid, service=service)
                    
                    # Update conversation context with the search results
                    update_conversation_context(chat_guid, summary)
                else:
                    # If not a search request, get AI response for the URL
                    ai_response = get_ai_assistant_response(chat_guid, deduplicated_text)
                    send_imessage(sender, ai_response, chat_guid=chat_guid, service=service)
                
                return True
            else:
                # If no text context with URLs, treat as unknown
                logging.warning(f"⚠️ URL attachment without text context: {filename}")
                file_type = "unknown"
            
        # Process based on file type
        if file_type == 'image' and mime_type.startswith('image/'):
            # Process image
            logging.info(f"🖼️ Processing image: {filename}")
            
            # Download the attachment to a temporary directory
            local_file_path = download_attachment_to_directory(file_path, file_type)
            
            if not local_file_path:
                logging.error(f"❌ Failed to download attachment: {filename}")
                return False
                
            # Simple check for active runs - just import what we need
            from ai.assistant import get_ai_assistant_image_response
            
            # Get AI response for the image - the function itself handles thread management
            response = get_ai_assistant_image_response(chat_guid, local_file_path, text_context)
            
            if response:
                # Send the response - this is the only place we send a message for this image
                send_imessage(sender, response, chat_guid=chat_guid, service=service)
            else:
                send_imessage(sender, "I couldn't analyze that image. Please try again with a clearer image.", chat_guid=chat_guid, service=service)
                
            # Clean up the local file - the get_ai_assistant_image_response function already cleans up its temp files
            try:
                # Check if this was a HEIC file that was converted
                original_heic_path = None
                if local_file_path.lower().endswith('.jpg') or local_file_path.lower().endswith('.jpeg'):
                    # Check if there's a corresponding HEIC file
                    possible_heic_path = os.path.splitext(local_file_path)[0] + '.HEIC'
                    if os.path.exists(possible_heic_path):
                        original_heic_path = possible_heic_path
                        logging.info(f"🔍 Found original HEIC file: {original_heic_path}")
                
                # Remove the local file if it exists
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    logging.info(f"🧹 Cleaned up file: {local_file_path}")
                else:
                    logging.info(f"🧹 File already removed or doesn't exist: {local_file_path}")
                
                # Also remove the original HEIC file if it exists
                if original_heic_path and os.path.exists(original_heic_path):
                    os.remove(original_heic_path)
                    logging.info(f"🧹 Cleaned up original HEIC file: {original_heic_path}")
                
                # Import and call cleanup_temp_files to ensure all temporary files are removed
                from utils.file_handling import cleanup_temp_files
                cleanup_temp_files()
                
            except Exception as e:
                logging.error(f"❌ Error during file cleanup: {e}")
                logging.error(traceback.format_exc())
                
            return True
            
        elif file_type == 'audio' or (mime_type and mime_type.startswith('audio/')):
            # Process audio
            logging.info(f"🔊 Processing audio: {filename}")
            
            # Download the attachment to a temporary directory
            local_file_path = download_attachment_to_directory(file_path, file_type)
            
            if not local_file_path:
                logging.error(f"❌ Failed to download attachment: {filename}")
                return False
                
            # Transcribe the audio
            transcription_result = transcribe_audio(local_file_path)
            
            if transcription_result:
                # Handle both tuple and string return types for backward compatibility
                if isinstance(transcription_result, tuple) and len(transcription_result) == 2:
                    transcribed_text, mp3_path = transcription_result
                else:
                    # Legacy format - just the text
                    transcribed_text = transcription_result
                    mp3_path = None
                
                if transcribed_text:
                    logging.info(f"🎤 Transcribed audio: {transcribed_text}")
                    
                    # Check if this is an image generation request
                    if is_image_request(transcribed_text):
                        logging.info(f"🎨 Image generation request detected from transcription: {transcribed_text}")
                        
                        # Generate and send image using the simplified approach
                        generate_and_send_image(sender, transcribed_text, service, chat_guid)
                    
                    # Check if this is a web search request
                    elif is_web_search_request(transcribed_text, chat_guid):
                        if isinstance(is_web_search_request(transcribed_text, chat_guid), str):
                            # Use the enhanced query for the search
                            search_query = is_web_search_request(transcribed_text, chat_guid)
                            logging.info(f"🔍 Detected web search request from transcription: {transcribed_text} (enhanced to: {search_query})")
                        else:
                            # Use the original query
                            search_query = transcribed_text
                            logging.info(f"🔍 Detected web search request from transcription: {transcribed_text}")
                        
                        # Perform web search
                        search_results = search_web(search_query, chat_guid=chat_guid)
                        
                        # Summarize search results
                        summary = summarize_search_results(search_query, search_results, chat_guid=chat_guid)
                        
                        # Send the summary as a response
                        send_imessage(sender, summary, chat_guid=chat_guid, service=service)
                        
                        # Update conversation context with the search results
                        from web.search import update_conversation_context
                        update_conversation_context(chat_guid, summary)
                    
                    else:
                        # If not an image request or search request, get AI response
                        ai_response = get_ai_assistant_response(chat_guid, transcribed_text)
                        
                        # Log the transcription but don't send it to the user
                        logging.info(f"📝 Transcription (not sent to user): {transcribed_text}")
                        
                        # Send only the AI response without the transcription
                        send_imessage(sender, ai_response, chat_guid=chat_guid, service=service)
                else:
                    send_imessage(sender, "I couldn't transcribe that audio. Please try again with clearer audio.", chat_guid=chat_guid, service=service)
            else:
                send_imessage(sender, "I couldn't process that audio file. Please try again.", chat_guid=chat_guid, service=service)
                
            # Clean up the local files
            try:
                # Clean up the original audio file
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    logging.info(f"🧹 Cleaned up file: {local_file_path}")
                else:
                    logging.info(f"🧹 File already removed or doesn't exist: {local_file_path}")
                
                # Clean up the MP3 file if it exists and is different from the original
                if mp3_path and mp3_path != local_file_path and os.path.exists(mp3_path):
                    os.remove(mp3_path)
                    logging.info(f"🧹 Cleaned up MP3 file: {mp3_path}")
                elif mp3_path and mp3_path != local_file_path:
                    logging.info(f"🧹 MP3 file already removed or doesn't exist: {mp3_path}")
            except Exception as e:
                logging.error(f"❌ Error removing file: {e}")
                
            return True
            
        elif file_type == 'document' or mime_type == 'application/pdf':
            # Process document
            logging.info(f"📄 Processing document: {filename}")
            
            # Download the attachment to a temporary directory
            local_file_path = download_attachment_to_directory(file_path, file_type)
            
            if not local_file_path:
                logging.error(f"❌ Failed to download attachment: {filename}")
                return False
                
            # Extract text from the document
            extracted_text = extract_text_from_file(local_file_path)
            
            if extracted_text:
                logging.info(f"📝 Extracted text from document: {extracted_text[:100].encode('utf-8', 'replace').decode('utf-8')}...")
                
                # Analyze the document with AI using the Assistant API
                analysis = get_ai_assistant_document_response(chat_guid, local_file_path, extracted_text, text_context)
                
                # Send the analysis
                send_imessage(sender, analysis, chat_guid=chat_guid, service=service)
            else:
                send_imessage(sender, "I couldn't extract text from that document. Please try again with a different document.", chat_guid=chat_guid, service=service)
                
            # Clean up the local file
            try:
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    logging.info(f"🧹 Cleaned up file: {local_file_path}")
                else:
                    logging.info(f"🧹 File already removed or doesn't exist: {local_file_path}")
            except Exception as e:
                logging.error(f"❌ Error removing file: {e}")
                
            return True
            
        else:
            # Unsupported file type
            logging.warning(f"⚠️ Unsupported file type: {file_type} ({mime_type})")
            send_imessage(sender, f"Oops! I can't process this {file_type} file yet 🙈\n\nI can work with:\n📸 Images: JPG, PNG, GIF, HEIC, WEBP\n📄 Documents: PDF, DOCX, XLSX, RTF, TXT\n🎵 Audio: MP3, WAV, M4A, CAF, AIFF, and more\n\nWant to try sending one of these instead? ✨", chat_guid=chat_guid, service=service)
            return False
            
    except Exception as e:
        logging.error(f"❌ Error processing attachment: {e}")
        logging.error(traceback.format_exc())
        send_imessage(sender, f"I'm sorry, I encountered an error processing your attachment: {str(e)}", chat_guid=chat_guid, service=service)
        return False

def send_imessage(recipient, message, chat_guid=None, service=None):
    """
    Send a message to the specified recipient
    
    Args:
        recipient (str): The recipient's phone number or email
        message (str): The message to send
        chat_guid (str, optional): The chat GUID for context tracking
        service (str, optional): The service type (iMessage or SMS)
        
    Returns:
        bool: True if the message was sent successfully, False otherwise
    """
    try:
        # Escape double quotes in the message
        escaped_message = message.replace('"', '\\"')
        
        # Determine the service type
        service_type = "iMessage"
        if service and service.lower() == "sms":
            service_type = "SMS"
            
        logging.info(f"📤 Sending message to {recipient} via {service_type}: {message[:50]}...")
        
        # Create the AppleScript command
        applescript = f'''
        tell application "Messages"
            set targetService to first service whose service type is {service_type}
            set targetBuddy to buddy "{recipient}" of targetService
            send "{escaped_message}" to targetBuddy
        end tell
        '''
        
        # Execute the AppleScript command
        process = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)
        
        if process.returncode != 0:
            logging.error(f"❌ Error sending message: {process.stderr}")
            return False
        
        logging.info(f"✅ Message sent to {recipient} via {service_type}")
        
        # Update conversation context with the assistant's response if chat_guid is provided
        if chat_guid:
            try:
                from web.search import update_conversation_context
                # Add a prefix to distinguish assistant messages in the context
                assistant_message = f"[ASSISTANT]: {message}"
                update_conversation_context(chat_guid, assistant_message)
                logging.info(f"✅ Updated conversation context with assistant's response")
            except Exception as e:
                logging.error(f"❌ Error updating conversation context with assistant's response: {e}")
        
        return True
    except Exception as e:
        logging.error(f"❌ Error sending message: {e}")
        traceback.print_exc()
        return False 