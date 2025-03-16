import os
import sys
import logging
import time
import traceback
import json
import backoff
import openai
import re
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, ASSISTANT_ID, MEMORY_FILE, THREAD_MESSAGE_LIMIT
from utils.token_tracking import track_token_usage
from ai.openai_client import check_rate_limit
from ai.image_analysis import prepare_image_for_analysis
from utils.file_handling import TEMP_FILES, cleanup_temp_files, add_temp_file

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Dictionary to store conversation threads
conversation_threads = {}

# Load existing conversation threads from memory file
try:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            conversation_threads = json.load(f)
        logging.info(f"🧠 Loaded {len(conversation_threads)} conversation threads from memory")
except Exception as e:
    logging.error(f"❌ Error loading memory file: {e}")

def create_assistant_thread(chat_guid):
    """
    Create a new thread for the OpenAI Assistant API
    
    Args:
        chat_guid (str): Chat GUID for conversation tracking
        
    Returns:
        str: Thread ID
    """
    start_time = time.time()
    
    try:
        logging.info("🧵 Creating a new thread...")
        thread = openai.beta.threads.create()
        conversation_threads[chat_guid] = thread.id
        
        end_time = time.time()
        logging.info(f"🆕 Created thread ID: {conversation_threads[chat_guid]} in {end_time - start_time:.2f} seconds")
        
        # Save to memory.json for persistence
        try:
            with open(MEMORY_FILE, 'w') as f:
                json.dump(conversation_threads, f, indent=2)
            logging.info("💾 Saved chat memory to memory.json")
        except Exception as e:
            logging.error(f"⚠️ Error saving memory file: {e}")
            
        return thread.id
    except Exception as e:
        logging.error(f"❌ Error creating thread: {e}")
        logging.error(traceback.format_exc())
        return None

def wait_for_assistant_response(thread_id, run_id):
    """
    Wait for the assistant to complete processing and return the response
    
    Args:
        thread_id (str): Thread ID
        run_id (str): Run ID
        
    Returns:
        str: Assistant response
    """
    start_time = time.time()
    
    try:
        while True:
            time.sleep(2)  # Check every 2 seconds
            
            run = openai.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            
            if run.status == "completed":
                # Get the latest messages
                messages = openai.beta.threads.messages.list(
                    thread_id=thread_id
                )
                
                # Find the assistant's response
                for message in messages.data:
                    if message.role == "assistant":
                        # Get the text content
                        for content_part in message.content:
                            if content_part.type == "text":
                                end_time = time.time()
                                logging.debug(f"⏱️ Assistant response received in {end_time - start_time:.2f} seconds")
                                return content_part.text.value
                
                end_time = time.time()
                logging.warning(f"⚠️ No response from AI after {end_time - start_time:.2f} seconds")
                return "No response from AI."
            
            elif run.status == "failed":
                end_time = time.time()
                logging.error(f"❌ Assistant run failed after {end_time - start_time:.2f} seconds: {run.last_error}")
                return "I encountered an error while processing your request."
                
            elif run.status == "requires_action":
                end_time = time.time()
                logging.warning(f"⚠️ Assistant requires action (function calling) after {end_time - start_time:.2f} seconds")
                return "I need to perform additional actions to answer your question, but this feature is not supported yet."
                
            current_time = time.time()
            if current_time - start_time > 60:  # Log every minute
                logging.info(f"⏳ Still waiting for assistant response... ({int(current_time - start_time)} seconds)")
    except Exception as e:
        end_time = time.time()
        logging.error(f"❌ Error waiting for assistant response after {end_time - start_time:.2f} seconds: {e}")
        logging.error(traceback.format_exc())
        return f"Error: {str(e)}"

@backoff.on_exception(
    backoff.expo,
    (openai.RateLimitError, openai.APIError),
    max_tries=5,
    factor=2
)
def get_ai_assistant_response(chat_guid, user_message):
    """
    Generate AI response using the Assistant API
    
    Args:
        chat_guid (str): Chat GUID for conversation tracking
        user_message (str): User message
        
    Returns:
        str: AI response
    """
    start_time = time.time()
    
    if not user_message or user_message.strip() == "":
        logging.warning("⚠️ Ignoring empty message to prevent AI errors.")
        return "I received an empty message. How can I help you?"
    
    try:
        # Check rate limit before making API call
        check_rate_limit()
        
        # Get or create thread ID for this chat
        thread_id = conversation_threads.get(chat_guid)
        if not thread_id:
            thread_id = create_assistant_thread(chat_guid)
            if not thread_id:
                return "I'm having trouble setting up our conversation. Please try again later."
        
        # Log the message limit being used
        logging.info(f"🔄 Using thread message limit: {THREAD_MESSAGE_LIMIT}")
        
        # Add user message to thread
        message = openai.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_message
        )
        
        # Run the assistant
        run = openai.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
            truncation_strategy={
                "type": "last_messages",
                "last_messages": THREAD_MESSAGE_LIMIT
            }
        )
        
        # Wait for response
        response = wait_for_assistant_response(thread_id, run.id)
        
        # Track token usage (approximate since Assistant API doesn't provide token counts)
        # We'll estimate based on message length
        prompt_tokens = len(user_message) // 4  # Rough estimate
        completion_tokens = len(response) // 4  # Rough estimate
        
        track_token_usage(
            model="gpt-4",  # Assuming the assistant uses GPT-4
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            purpose="assistant"
        )
        
        end_time = time.time()
        logging.debug(f"⏱️ Total assistant response time: {end_time - start_time:.2f} seconds")
        
        return response
        
    except Exception as e:
        end_time = time.time()
        logging.error(f"❌ Error getting AI assistant response after {end_time - start_time:.2f} seconds: {e}")
        logging.error(traceback.format_exc())
        return f"I'm sorry, I encountered an error: {str(e)}"

@backoff.on_exception(
    backoff.expo,
    (openai.RateLimitError, openai.APIError),
    max_tries=5,
    factor=2
)
def get_ai_assistant_image_response(chat_guid, image_path, text_prompt=None):
    """
    Generate AI response to an image using the Assistant API
    
    Args:
        chat_guid (str): Chat GUID for conversation tracking
        image_path (str): Path to the image file
        text_prompt (str, optional): Text prompt to accompany the image
        
    Returns:
        str: AI response
    """
    start_time = time.time()
    
    try:
        # Check rate limit before making API call
        check_rate_limit()
        
        # Debug log for text prompt
        if text_prompt:
            logging.debug(f"🔍 Image analysis text prompt: '{text_prompt}'")
        else:
            logging.debug(f"🔍 No text prompt provided for image analysis")
        
        # Prepare the image (convert HEIC to JPEG if needed)
        prepared_image_path = prepare_image_for_analysis(image_path)
        if not prepared_image_path:
            return "Failed to prepare image for analysis."
            
        # Ensure the prepared image is in the TEMP_FILES list
        if prepared_image_path != image_path:
            from utils.file_handling import add_temp_file as add_file_to_temp
            add_file_to_temp(prepared_image_path)
            logging.debug(f"📝 Added prepared image to temp files: {prepared_image_path}")
        
        # Get or create thread ID for this chat
        thread_id = conversation_threads.get(chat_guid)
        if not thread_id:
            thread_id = create_assistant_thread(chat_guid)
            if not thread_id:
                return "I'm having trouble setting up our conversation. Please try again later."
        
        # Check for active runs before proceeding
        if not check_and_wait_for_active_runs(thread_id, max_wait_seconds=5):
            logging.warning(f"⚠️ Thread {thread_id} already has active runs that didn't complete in time")
            return "I'm still processing your previous request. Please try again in a moment."
        
        # Prepare message content
        message_content = []
        
        # Add text prompt if provided
        if text_prompt and text_prompt.strip():
            # Clean up the text prompt - remove any control characters
            clean_text_prompt = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text_prompt).strip()
            
            # Use the provided text context directly without any additional instructions
            message_content.append({
                "type": "text",
                "text": clean_text_prompt
            })
            logging.info(f"🖼️ Using user-provided context for image analysis: '{clean_text_prompt}'")
        else:
            # If no context provided, just ask to analyze the image without specific instructions
            message_content.append({
                "type": "text",
                "text": "What's in this image?"
            })
            logging.info("🖼️ No user context provided, using simple prompt")
        
        # Simplify image processing: Convert any image to .jpg format for consistency
        # This eliminates separate steps for case normalization and .jpeg to .jpg conversion
        filename, extension = os.path.splitext(prepared_image_path)
        
        # Only convert if not already a lowercase .jpg file
        if extension.lower() != '.jpg':
            try:
                from PIL import Image
                from utils.file_handling import add_temp_file as add_file_to_temp
                
                # Create a new path with .jpg extension
                jpg_path = filename + '.jpg'
                
                # Convert the image to JPG format
                Image.open(prepared_image_path).convert('RGB').save(jpg_path, 'JPEG')
                
                # Add the JPG file to the temp files list for cleanup
                add_file_to_temp(jpg_path)
                
                logging.info(f"🖼️ Converted image to JPG format for consistency: {jpg_path}")
                prepared_image_path = jpg_path
            except Exception as e:
                logging.error(f"❌ Error converting image to JPG: {e}")
                # Continue with original file, will try to upload anyway
        
        # Upload the image file to OpenAI
        with open(prepared_image_path, "rb") as image_file:
            try:
                # Try with vision purpose first
                file = openai.files.create(
                    file=image_file,
                    purpose="vision"
                )
                
                logging.info(f"✅ Image uploaded to OpenAI with ID: {file.id} using 'vision' purpose")
                
                message_content.append({
                    "type": "image_file",
                    "image_file": {
                        "file_id": file.id
                    }
                })
            except Exception as upload_error:
                logging.error(f"❌ Error uploading image with purpose 'vision': {upload_error}")
                
                # Try again with 'assistants' purpose
                image_file.seek(0)  # Reset file pointer
                file = openai.files.create(
                    file=image_file,
                    purpose="assistants"
                )
                
                logging.info(f"✅ Image uploaded to OpenAI with ID: {file.id} using 'assistants' purpose")
                
                message_content.append({
                    "type": "image_file",
                    "image_file": {
                        "file_id": file.id
                    }
                })
        
        # Log the message limit being used
        logging.info(f"🔄 Using thread message limit for image analysis: {THREAD_MESSAGE_LIMIT}")
        
        try:
            # Add message to thread
            message = openai.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message_content
            )
            
            # Run the assistant
            run = openai.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=ASSISTANT_ID,
                truncation_strategy={
                    "type": "last_messages",
                    "last_messages": THREAD_MESSAGE_LIMIT
                }
            )
            
            # Wait for response
            response = wait_for_assistant_response(thread_id, run.id)
            
            # Track token usage (approximate since Assistant API doesn't provide token counts)
            prompt_tokens = 1000  # Rough estimate for image
            if text_prompt:
                prompt_tokens += len(text_prompt) // 4
            completion_tokens = len(response) // 4  # Rough estimate
            
            track_token_usage(
                model="gpt-4",  # Assuming the assistant uses GPT-4
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                purpose="assistant_image"
            )
            
            end_time = time.time()
            logging.debug(f"⏱️ Total image assistant response time: {end_time - start_time:.2f} seconds")
            
            return response
            
        except openai.BadRequestError as e:
            # Handle the specific case of "already has an active run"
            if "already has an active run" in str(e):
                logging.warning(f"⚠️ Thread {thread_id} already has an active run: {e}")
                return "I'm still processing a previous request. Please wait a moment and try again."
            else:
                # Re-raise other BadRequestError exceptions
                raise
        
    except Exception as e:
        end_time = time.time()
        logging.error(f"❌ Error getting AI assistant image response after {end_time - start_time:.2f} seconds: {e}")
        logging.error(traceback.format_exc())
        
        # Clean up temporary files
        cleanup_temp_files()
        
        # Provide a more user-friendly error message
        if "rate limit" in str(e).lower():
            return "I'm receiving too many requests right now. Please try again in a moment."
        elif "invalid_request_error" in str(e):
            return "I'm having trouble processing your image. Please try again in a moment."
        else:
            return "I'm sorry, I encountered an error processing your image. Please try again."
    
    finally:
        # Always clean up temporary files
        cleanup_temp_files()

def check_and_wait_for_active_runs(thread_id, max_wait_seconds=30):
    """
    Check if there are any active runs for a thread and wait for them to complete
    
    Args:
        thread_id (str): Thread ID
        max_wait_seconds (int, optional): Maximum wait time in seconds
        
    Returns:
        bool: True if no active runs or all runs completed, False otherwise
    """
    start_time = time.time()
    
    try:
        # List runs for the thread
        runs = openai.beta.threads.runs.list(thread_id=thread_id)
        
        # Check if there are any active runs
        active_runs = [run for run in runs.data if run.status in ["queued", "in_progress", "requires_action"]]
        
        if not active_runs:
            return True
            
        # Wait for active runs to complete
        logging.info(f"⏳ Waiting for {len(active_runs)} active runs to complete...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            # Check each active run
            all_completed = True
            for run in active_runs:
                run_status = openai.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                ).status
                
                if run_status in ["queued", "in_progress", "requires_action"]:
                    all_completed = False
                    break
            
            if all_completed:
                end_time = time.time()
                logging.info(f"✅ All runs completed in {end_time - start_time:.2f} seconds")
                return True
                
            # Wait before checking again
            time.sleep(2)
        
        end_time = time.time()
        logging.warning(f"⚠️ Timed out waiting for runs to complete after {max_wait_seconds} seconds")
        return False
        
    except Exception as e:
        end_time = time.time()
        logging.error(f"❌ Error checking active runs after {end_time - start_time:.2f} seconds: {e}")
        logging.error(traceback.format_exc())
        return False

def set_thread_message_limit(new_limit):
    """
    Change the thread message limit dynamically
    
    Args:
        new_limit (int): New message limit
        
    Returns:
        int: Previous message limit
    """
    global THREAD_MESSAGE_LIMIT
    old_limit = THREAD_MESSAGE_LIMIT
    THREAD_MESSAGE_LIMIT = new_limit
    logging.info(f"🔄 Changed thread message limit from {old_limit} to {new_limit}")
    return old_limit

def get_thread_messages(chat_guid, limit=10):
    """
    Get messages from an existing thread
    
    Args:
        chat_guid (str): Chat GUID for conversation tracking
        limit (int, optional): Maximum number of messages to retrieve
        
    Returns:
        list: List of messages
    """
    try:
        # Check if we have a thread for this chat
        if chat_guid not in conversation_threads:
            logging.warning(f"⚠️ No thread found for chat {chat_guid}")
            return []
        
        thread_id = conversation_threads[chat_guid]
        
        # Get messages from the thread
        messages = openai.beta.threads.messages.list(
            thread_id=thread_id,
            limit=limit,
            order="desc"  # Get the most recent messages first
        )
        
        # Convert to a more usable format
        result = []
        for msg in messages.data:
            content = ""
            if msg.content and len(msg.content) > 0:
                # Extract text content
                for content_part in msg.content:
                    if hasattr(content_part, 'text') and content_part.text:
                        content = content_part.text.value
                        break
            
            result.append({
                'id': msg.id,
                'role': msg.role,
                'content': content,
                'created_at': msg.created_at
            })
        
        return result
    except Exception as e:
        logging.error(f"❌ Error getting thread messages: {e}")
        logging.error(traceback.format_exc())
        return []

def get_ai_assistant_document_response(chat_guid, file_path, extracted_text, text_prompt=None):
    """
    Generate AI response to a document using the Assistant API
    
    Args:
        chat_guid (str): Chat GUID for conversation tracking
        file_path (str): Path to the document file
        extracted_text (str): Text extracted from the document
        text_prompt (str, optional): Text prompt to accompany the document
        
    Returns:
        str: AI response
    """
    start_time = time.time()
    
    try:
        # Check rate limit before making API call
        check_rate_limit()
        
        # Debug log for text prompt
        if text_prompt:
            logging.debug(f"📄 Document analysis text prompt: '{text_prompt}'")
        else:
            logging.debug(f"📄 No text prompt provided for document analysis")
        
        # Get file name and extension
        file_name = os.path.basename(file_path)
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Get or create thread ID for this chat
        thread_id = conversation_threads.get(chat_guid)
        if not thread_id:
            thread_id = create_assistant_thread(chat_guid)
            if not thread_id:
                return "I'm having trouble setting up our conversation. Please try again later."
        
        # Check for active runs before proceeding
        if not check_and_wait_for_active_runs(thread_id, max_wait_seconds=5):
            logging.warning(f"⚠️ Thread {thread_id} already has active runs that didn't complete in time")
            return "I'm still processing your previous request. Please try again in a moment."
        
        # Prepare message content
        message_content = []
        
        # Add text prompt if provided
        if text_prompt and text_prompt.strip():
            # Clean up the text prompt - remove any control characters
            clean_text_prompt = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text_prompt).strip()
            
            # Format the message with document info and user's question
            message_text = f"{clean_text_prompt}\n\nDocument: {file_name} ({file_extension[1:].upper()})\n\n{extracted_text}"
            message_content.append({
                "type": "text",
                "text": message_text
            })
            logging.info(f"📄 Using user-provided context for document analysis: '{clean_text_prompt}'")
        else:
            # If no context provided, just ask to analyze the document
            message_text = f"Please analyze this {file_extension[1:].upper()} document: {file_name}\n\n{extracted_text}"
            message_content.append({
                "type": "text",
                "text": message_text
            })
            logging.info(f"📄 No user context provided, using simple prompt for document analysis")
        
        try:
            # Add message to thread
            message = openai.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message_content
            )
            
            # Run the assistant
            run = openai.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=ASSISTANT_ID,
                truncation_strategy={
                    "type": "last_messages",
                    "last_messages": THREAD_MESSAGE_LIMIT
                }
            )
            
            # Wait for response
            response = wait_for_assistant_response(thread_id, run.id)
            
            # Track token usage (approximate since Assistant API doesn't provide token counts)
            prompt_tokens = len(extracted_text) // 4  # Rough estimate based on text length
            if text_prompt:
                prompt_tokens += len(text_prompt) // 4
            completion_tokens = len(response) // 4  # Rough estimate
            
            track_token_usage(
                model="gpt-4",  # Assuming the assistant uses GPT-4
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                purpose="assistant_document"
            )
            
            end_time = time.time()
            logging.debug(f"⏱️ Total document assistant response time: {end_time - start_time:.2f} seconds")
            
            return response
            
        except openai.BadRequestError as e:
            # Handle the specific case of "already has an active run"
            if "already has an active run" in str(e):
                logging.warning(f"⚠️ Thread {thread_id} already has an active run: {e}")
                return "I'm still processing a previous request. Please wait a moment and try again."
            else:
                # Re-raise other BadRequestError exceptions
                raise
        
    except Exception as e:
        end_time = time.time()
        logging.error(f"❌ Error getting AI assistant document response after {end_time - start_time:.2f} seconds: {e}")
        logging.error(traceback.format_exc())
        
        # Provide a more user-friendly error message
        if "rate limit" in str(e).lower():
            return "I'm receiving too many requests right now. Please try again in a moment."
        elif "invalid_request_error" in str(e):
            return "I'm having trouble processing your document. Please try again in a moment."
        elif "maximum context length" in str(e).lower() or "token limit" in str(e).lower():
            return "This document is too large for me to process in full. I can only analyze portions of very large documents."
        else:
            return "I'm sorry, I encountered an error processing your document. Please try again." 