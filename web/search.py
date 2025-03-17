import requests
import logging
import json
import re
import html
import backoff
import openai
import os
import sys
from datetime import datetime, timedelta
import time
import traceback
from typing import Union
import hashlib

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID, SEARCH_CACHE_EXPIRY, DEFAULT_MODEL
from utils.token_tracking import track_token_usage
from ai.openai_client import check_rate_limit
from prompts_config import (
    SEARCH_SUMMARIZATION_PROMPT, 
    FOLLOW_UP_QUESTION_PROMPT, 
    get_query_enhancement_prompt_1,
    get_query_enhancement_prompt_2,
    get_web_search_determination_prompt,
    get_current_date_formatted
)

# Google Search API URL
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# Cache for search results
SEARCH_CACHE = {}

# Conversation context tracker
CONVERSATION_CONTEXT = {}

# Direct context tracking for recent searches (chat_guid -> {query, summary})
LAST_SEARCH = {}

# Cache for search detection results
SEARCH_DETECTION_CACHE = {}

def update_conversation_context(chat_guid, message):
    """
    Update conversation context with the current message
    
    Args:
        chat_guid (str): Chat GUID
        message (str): Message text
        
    Returns:
        None
    """
    if not chat_guid or not message:
        return
    
    try:
        # Initialize conversation context if it doesn't exist
        if not hasattr(sys.modules[__name__], 'CONVERSATION_CONTEXT'):
            global CONVERSATION_CONTEXT
            CONVERSATION_CONTEXT = {}
        
        # Initialize context for this chat if it doesn't exist
        if chat_guid not in CONVERSATION_CONTEXT:
            CONVERSATION_CONTEXT[chat_guid] = {
                'recent_messages': [],
                'topics': set(),
                'entities': set(),
                'last_updated': time.time()
            }
        
        # Clean the message before adding it to context
        # Remove any control characters that might cause issues
        clean_message = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', message)
        
        # Add message to recent messages
        recent_messages = CONVERSATION_CONTEXT[chat_guid]['recent_messages']
        
        # Log the message history before update
        logging.info(f"🔍 Message history before update: {recent_messages}")
        
        # Keep only the last 10 messages (increased from 5 for better context)
        if len(recent_messages) >= 10:
            removed_message = recent_messages.pop(0)
            logging.info(f"🔍 Removed oldest message from history: '{removed_message}'")
        
        # Add the current message
        recent_messages.append(clean_message)
        
        # Log the message history after update
        logging.info(f"🔍 Message history after update: {recent_messages}")
        
        # Extract topics from the message
        try:
            topics = extract_topics_from_message(chat_guid, clean_message)
            # Update topics
            CONVERSATION_CONTEXT[chat_guid]['topics'].update(topics)
        except Exception as e:
            logging.error(f"❌ Error extracting topics: {e}")
            logging.error(traceback.format_exc())
        
        # Update last updated timestamp
        CONVERSATION_CONTEXT[chat_guid]['last_updated'] = time.time()
        
        # Log context tracking information
        logging.info(f"🔍 Context tracking - Recent messages: {recent_messages}")
        logging.info(f"🔍 Context tracking - Detected entities: {CONVERSATION_CONTEXT[chat_guid]['entities']}")
        logging.info(f"🔍 Context tracking - Topics: {CONVERSATION_CONTEXT[chat_guid]['topics']}")
    
    except Exception as e:
        logging.error(f"❌ Error updating conversation context: {e}")
        logging.error(traceback.format_exc())

def extract_topics_from_message(chat_guid, message):
    """
    Extract topics from a message and add them to the conversation context
    
    Args:
        chat_guid (str): Chat GUID
        message (str): Message text
    """
    # Simple extraction of nouns and named entities
    # This is a basic implementation - could be improved with NLP
    words = message.split()
    topics = set()
    for word in words:
        # Only add words that are likely nouns (capitalized or longer than 4 chars)
        if len(word) > 4 or (len(word) > 1 and word[0].isupper()):
            # Clean up the word (remove punctuation)
            clean_word = re.sub(r'[^\w\s]', '', word).strip()
            if clean_word and len(clean_word) > 2:
                topics.add(clean_word.lower())
    return topics

def get_context_for_search(chat_guid, query):
    """
    Get context-enhanced search query based on conversation history
    
    Args:
        chat_guid (str): Chat GUID
        query (str): Original search query
        
    Returns:
        str: Enhanced search query with context
    """
    if not chat_guid or chat_guid not in CONVERSATION_CONTEXT:
        return query
    
    # Get recent messages
    recent_messages = CONVERSATION_CONTEXT[chat_guid]['recent_messages']
    
    # If this is the first message, no context to add
    if len(recent_messages) <= 1:
        return query
    
    # Get the previous message for context
    previous_message = recent_messages[-2] if len(recent_messages) > 1 else None
    
    # If no previous message or it's the same as the current query, return original query
    if not previous_message or previous_message == query:
        return query
    
    # Check if the query is likely a follow-up question
    is_followup = is_followup_question(query)
    is_short_query = len(query.split()) <= 5
    has_pronouns = any(pronoun in query.lower() for pronoun in ["it", "they", "them", "their", "its", "this", "that", "these", "those"])
    
    # Log detection results for debugging
    if is_followup:
        logging.info(f"🔍 Detected follow-up question pattern in: '{query}'")
    if is_short_query:
        logging.info(f"🔍 Detected short query that may need context: '{query}'")
    if has_pronouns:
        logging.info(f"🔍 Detected pronouns in query that may refer to previous context: '{query}'")
    
    # If query is likely a follow-up or contains pronouns, enhance it with context
    if is_followup or is_short_query or has_pronouns:
        # Get entities from context
        entities = CONVERSATION_CONTEXT[chat_guid]['entities']
        entity_str = " ".join(entities) if entities else ""
        
        # Create different enhanced queries based on the situation
        if entities and (has_pronouns or is_short_query):
            # If we have entities and pronouns/short query, replace pronouns with entities
            enhanced_query = f"{query} about {entity_str}"
            logging.info(f"🔍 Enhanced query with entities: '{enhanced_query}' (original: '{query}')")
            return enhanced_query
        else:
            # Otherwise, include the full previous message as context
            enhanced_query = f"{query} in context of previous question about {previous_message}"
            logging.info(f"🔍 Enhanced query with previous message: '{enhanced_query}' (original: '{query}')")
            return enhanced_query
    
    return query

def is_followup_question(query):
    """
    Determine if a query is likely a follow-up question
    
    Args:
        query (str): Query text
        
    Returns:
        bool: True if likely a follow-up question
    """
    # Patterns that indicate follow-up questions
    followup_patterns = [
        r"^(how|what|when|where|why|who|which)",  # Questions starting with wh-words
        r"^(is|are|was|were|do|does|did|can|could|would|should|will)",  # Questions starting with auxiliary verbs
        r"^(and|but|so|then)",  # Questions starting with conjunctions
        r"^(how much|how many)",  # Specific question phrases
        r"(they|them|those|these|that|this|it|he|she|his|her|their|its)"  # Pronouns indicating reference to previous context
    ]
    
    # Check if the query matches any follow-up patterns
    for pattern in followup_patterns:
        if re.search(pattern, query.lower()):
            return True
    
    # Additional patterns for vague questions that likely refer to previous context
    vague_followup_patterns = [
        r"(your|my) (pick|choice|recommendation|suggestion|opinion|thought)",  # "What is your pick?"
        r"(which|what) (one|should|would|do you) (i|you) (choose|pick|select|recommend|suggest)",  # "Which should I choose?"
        r"(best|better|preferred|recommended) (option|choice|pick|selection)",  # "What's the best option?"
        r"(any|have) (preference|recommendation|suggestion)",  # "Do you have any preference?"
        r"(what|how) about",  # "What about...?"
        r"(tell|give) me more",  # "Tell me more"
        r"(anything|something) else",  # "Anything else?"
        r"^(yes|no|maybe|sure|okay|fine|alright|great|perfect)",  # Short responses that likely refer to previous context
        r"^(i|we) (like|prefer|want|need|choose|pick|select)",  # "I prefer..."
        r"^(can|could) you",  # "Can you..."
    ]
    
    # Check if the query matches any vague follow-up patterns
    for pattern in vague_followup_patterns:
        if re.search(pattern, query.lower()):
            logging.info(f"🔍 Detected vague follow-up question: '{query}' (matched pattern: {pattern})")
            return True
    
    # Check if the query is very short (likely a follow-up)
    if len(query.split()) <= 5:
        logging.info(f"🔍 Detected short query that might be a follow-up: '{query}'")
        return True
    
    return False

def is_web_search_request(text, chat_guid=None):
    """
    Determine if a message is requesting web search
    
    Args:
        text (str): Message text
        chat_guid (str, optional): Chat GUID
        
    Returns:
        Union[bool, str]: True/False if web search is needed, or the enhanced query string
    """
    if not text:
        return False
    
    # Log the full text being analyzed for debugging
    logging.debug(f"🔍 Analyzing for web search request: {text[:100]}..." if len(text) > 100 else f"🔍 Analyzing for web search request: {text}")
    
    # Log the chat_guid for debugging
    logging.info(f"🔍 is_web_search_request received chat_guid: {chat_guid}")
    
    # Check for weather queries first - always treat as web search requests
    if is_weather_query(text):
        logging.info(f"🌤️ Detected weather query: '{text}' - treating as search request")
        if chat_guid:
            update_conversation_context(chat_guid, text)
        return True
    
    # Check if the text is just a URL or multiple URLs
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    
    # If the text contains a lot of URLs, it's likely URL sharing, not a search request
    url_matches = re.findall(url_pattern, text)
    if len(url_matches) > 0:
        # If more than 50% of the text is URLs, it's likely URL sharing
        url_text_length = sum(len(url) for url in url_matches)
        if url_text_length > len(text) * 0.5:
            logging.info(f"🔗 Detected URL sharing (URLs make up >50% of text), not treating as search request: {text[:100]}...")
            return False
    
    # Split by newlines to handle multiple URLs
    lines = text.strip().split('\n')
    # Check if all lines are URLs
    all_lines_are_urls = all(re.match(f'^{url_pattern}$', line.strip()) for line in lines if line.strip())
    
    # If the text is just one or more URLs, it's not a search request
    if all_lines_are_urls and len(lines) >= 1:
        logging.info(f"🔗 Detected URL sharing, not treating as search request: {text[:100]}...")
        return False
    
    # Check if this is a message about a URL (e.g., "This is the url...")
    if len(lines) <= 3:  # Short message
        url_count = sum(1 for line in lines if re.search(url_pattern, line))
        if url_count > 0 and url_count == len(lines):
            logging.info(f"🔗 Detected URL sharing (all lines are URLs), not treating as search request: {text[:100]}...")
            return False
    
    # Use AI to determine if this is a search request
    try:
        # First check if we have a cached result
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in SEARCH_DETECTION_CACHE:
            result = SEARCH_DETECTION_CACHE[cache_key]
            logging.info(f"🔍 Using cached search detection result: {result}")
            return result
        
        # If we have chat_guid, use conversation context for better detection
        if chat_guid and chat_guid in CONVERSATION_CONTEXT:
            logging.info(f"🔍 Using recent messages for search detection context from chat_guid: {chat_guid}")
            result = _ai_search_detection(text, chat_guid)
        else:
            if chat_guid:
                logging.info(f"🔍 Chat GUID {chat_guid} not found in CONVERSATION_CONTEXT")
                # Initialize context for this chat if it doesn't exist
                update_conversation_context(chat_guid, text)
                # Try again with the newly initialized context
                if chat_guid in CONVERSATION_CONTEXT:
                    logging.info(f"🔍 Successfully initialized context for chat_guid: {chat_guid}")
                    result = _ai_search_detection(text, chat_guid)
                else:
                    logging.info(f"🔍 Failed to initialize context for chat_guid: {chat_guid}")
                    result = _ai_search_detection(text)
            else:
                logging.info(f"🔍 No chat_guid provided, using default search detection")
                result = _ai_search_detection(text)
        
        # Cache the result
        SEARCH_DETECTION_CACHE[cache_key] = result
        
        if result:
            logging.info(f"🔍 AI determined this is a search request")
        else:
            logging.info(f"🔍 AI determined this is NOT a search request")
        
        return result
    except Exception as e:
        logging.error(f"❌ Error in search detection: {e}")
        logging.error(traceback.format_exc())
        return False

def is_realtime_information_query(text):
    """
    Determine if a query requires realtime information
    
    Args:
        text (str): Query text
        
    Returns:
        bool: True if realtime information is needed
    """
    if not text:
        return False
        
    # Check for time-sensitive keywords
    time_patterns = [
        r"(?i)(current|latest|recent|today'?s|tonight'?s|tomorrow'?s|upcoming|live|now|right now)\s+.+",
        r"(?i)what'?s\s+happening\s+(now|today|tonight|this\s+week|this\s+month)",
        r"(?i)(news|weather|forecast|stock|price|score|event|update)\s+.+",
        r"(?i)when\s+(is|will|does|do)\s+.+",
        r"(?i)how\s+(is|are|much|many)\s+.+\s+(now|today|currently|at\s+the\s+moment)",
        r"(?i)(2023|2024|2025)\s+.+",  # Current year references
        r"(?i)what\s+is\s+the\s+(current|latest|today'?s)\s+.+",
        r"(?i)who\s+is\s+(currently|now|presently)\s+.+"
    ]
    
    for pattern in time_patterns:
        if re.search(pattern, text):
            return True
    
    # Check for specific realtime topics
    realtime_topics = [
        r"(?i)(weather|temperature|forecast|rain|snow|storm)",
        r"(?i)(stock|market|price|trading|nasdaq|dow|s&p|bitcoin|crypto)",
        r"(?i)(game|match|score|playing|tournament|championship)",
        r"(?i)(news|headline|breaking|announced|released|launched)",
        r"(?i)(traffic|delay|accident|road|flight|status)",
        r"(?i)(election|poll|vote|campaign|president|candidate)",
        r"(?i)(movie|show|concert|event|ticket|playing|streaming)",
        r"(?i)(open|closed|hours|schedule|time)",
        r"(?i)(covid|pandemic|virus|outbreak|cases)"
    ]
    
    for pattern in realtime_topics:
        if re.search(pattern, text):
            return True
            
    # Check for explicit time references
    time_references = ["today", "tonight", "tomorrow", "this week", "this month", "this year", 
                      "now", "currently", "at the moment", "right now", "present"]
    
    for reference in time_references:
        if reference in text.lower():
            return True
    
    return False

def _keyword_search_detection(text):
    """
    Detect search requests using keyword matching
    
    Args:
        text (str): Message text
        
    Returns:
        bool: True if search is needed
    """
    # Keywords that suggest a search query
    search_keywords = [
        "search", "google", "look up", "find", "information", "data", 
        "statistics", "facts", "details", "research", "learn about",
        "tell me about", "what is", "who is", "where is", "when did",
        "why does", "how to", "latest", "current", "recent", "news"
    ]
    
    # Check for question marks
    if "?" in text:
        # Questions are likely search queries
        return True
    
    # Check for search keywords
    for keyword in search_keywords:
        if keyword.lower() in text.lower():
            return True
    
    return False

def _ai_search_detection(text, chat_guid=None):
    """
    Use AI to determine if a message requires web search and enhance the query with context
    
    Args:
        text (str): Message text
        chat_guid (str, optional): Chat GUID for conversation context
        
    Returns:
        Union[bool, str]: True if search is needed, or enhanced query string
    """
    try:
        # Get current date for time-sensitive queries
        current_date = get_current_date_formatted()
        
        # Check rate limit before making API call
        check_rate_limit()
        
        # Clean the input text before processing
        # Remove any leading "Nope." or similar responses and any odd characters
        clean_text = re.sub(r'^(nope|no|yes|yeah|yep|sure|oh|wow|nice)\.?\s*', '', text, flags=re.IGNORECASE)
        clean_text = re.sub(r'[\'"]', '', clean_text)  # Remove quotes
        clean_text = clean_text.strip()
        
        # Prepare context from recent conversation if available
        context = ""
        recent_context = []
        
        if chat_guid and chat_guid in CONVERSATION_CONTEXT:
            recent_messages = CONVERSATION_CONTEXT[chat_guid]['recent_messages']
            logging.info(f"🔍 Available context messages: {recent_messages}")
            
            # We need at least 2 messages for context (including the current one)
            if recent_messages and len(recent_messages) >= 2:
                # Get all messages except the current one
                # The current message should be the last one in the list
                previous_messages = recent_messages[:-1]
                
                if previous_messages:
                    logging.info(f"🔍 Using previous messages for context: {previous_messages}")
                    # Clean the messages before including them
                    for msg in previous_messages:
                        # Remove any odd characters and clean up the message
                        clean_msg = re.sub(r'[\'"]', '', msg)  # Remove quotes
                        clean_msg = re.sub(r'^\s*[a-z]\s+', '', clean_msg, flags=re.IGNORECASE)  # Remove single letter prefixes
                        # Remove any trailing control characters
                        clean_msg = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', clean_msg)
                        
                        # Check if this is an assistant message (prefixed with [ASSISTANT]:)
                        if clean_msg.startswith('[ASSISTANT]:'):
                            # Format assistant messages differently
                            clean_msg = clean_msg[12:].strip()  # Remove the [ASSISTANT]: prefix
                            if clean_msg:
                                recent_context.append(f"Assistant: {clean_msg}")
                        else:
                            # Format user messages
                            if clean_msg:
                                recent_context.append(f"User: {clean_msg}")
                    
                    if recent_context:
                        messages_context = "\n".join([f"- {msg}" for msg in recent_context])
                        context = f"""Recent conversation context:
{messages_context}

"""
                        logging.info(f"🔍 Using recent messages for search detection context: {context}")
                    else:
                        logging.info("🔍 No valid context messages after cleaning")
                else:
                    logging.info("🔍 No previous messages found for context")
            else:
                logging.info("🔍 Not enough messages in conversation context")
        else:
            logging.info(f"🔍 No conversation context available for chat_guid: {chat_guid}")
        
        # Check if this is likely a follow-up question with pronouns or short query
        pronouns = ["it", "this", "that", "these", "those", "they", "them", "their", "there"]
        has_pronouns = any(pronoun in clean_text.lower().split() for pronoun in pronouns)
        is_short_query = len(clean_text.split()) <= 5
        
        # Check for instruction language patterns
        instruction_patterns = ["send me", "find me", "get me", "show me", "give me", "can you find", "can you send", "can you get", "can you show", "can you give"]
        has_instruction_pattern = any(pattern in clean_text.lower() for pattern in instruction_patterns)
        
        # Check for link request patterns
        link_request_patterns = ["link to", "link for", "where to buy", "where to find", "where can i buy", "where can i find", "where to get", "where can i get"]
        has_link_request = any(pattern in clean_text.lower() for pattern in link_request_patterns)
        
        # If this has pronouns, is a short query, contains question words, has instruction patterns, or is a link request and we have context, ask the model to enhance the query
        if (has_pronouns or is_short_query or has_instruction_pattern or has_link_request or "what" in clean_text.lower() or "where" in clean_text.lower() or "when" in clean_text.lower() or "how" in clean_text.lower()) and context:
            logging.info(f"🔍 Attempting to enhance query with context. Has pronouns: {has_pronouns}, Is short query: {is_short_query}, Has instruction pattern: {has_instruction_pattern}, Has link request: {has_link_request}")
            
            # Use DEFAULT_MODEL for consistency
            logging.info(f"🔍 Using Query Enhancement Prompt 1 to evaluate search need and enhance query")
            response = openai.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": get_query_enhancement_prompt_1(current_date)
                    },
                    {
                        "role": "user",
                        "content": f"{context}Current message: {clean_text}\n\nDoes this message require a web search to provide an accurate response? If yes, enhance the query with relevant context. Answer with 'Yes: [enhanced query]' or just 'No'."
                    }
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            # Track token usage
            if hasattr(response, 'usage'):
                track_token_usage(
                    model=DEFAULT_MODEL,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    purpose="search_detection"
                )
            
            result = response.choices[0].message.content.strip()
            logging.info(f"🔍 AI response for query enhancement: {result}")
            
            if result.lower().startswith("yes:"):
                # Extract the enhanced query
                enhanced_query = result[4:].strip()
                
                # Clean up the enhanced query
                enhanced_query = re.sub(r'^(nope|no|yes|yeah|yep|sure|oh|wow|nice)\.?\s*', '', enhanced_query, flags=re.IGNORECASE)
                enhanced_query = re.sub(r'[\'"]', '', enhanced_query)  # Remove quotes
                enhanced_query = enhanced_query.strip()
                
                # Ensure the enhanced query is not malformed
                if enhanced_query and len(enhanced_query) > 3:
                    logging.info(f"🔍 AI enhanced search query: '{enhanced_query}' (original: '{text}')")
                    return enhanced_query
                else:
                    # If the enhanced query is too short or empty, fall back to the original
                    logging.info(f"🔍 Enhanced query was too short, using original: '{text}'")
                    return True
            elif result.lower() == "yes":
                logging.info(f"🔍 AI determined this is a search request but did not provide an enhanced query")
                return True
            else:
                # Removed duplicate log message
                return False
        else:
            if not context:
                logging.info(f"🔍 No context available for query enhancement")
                
                # Even without context, we should still enhance instruction-style queries and link requests
                if has_instruction_pattern or has_link_request:
                    logging.info(f"🔍 Enhancing instruction-style query or link request without context")
                    # Use DEFAULT_MODEL for consistency
                    logging.info(f"🔍 Using Query Enhancement Prompt 2 to enhance instruction-style query")
                    response = openai.chat.completions.create(
                        model=DEFAULT_MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": get_query_enhancement_prompt_2(current_date)
                            },
                            {
                                "role": "user",
                                "content": f"Enhance this search query by removing instruction language and focusing on the core search intent: {clean_text}"
                            }
                        ],
                        temperature=0.1,
                        max_tokens=50
                    )
                    
                    # Track token usage
                    if hasattr(response, 'usage'):
                        track_token_usage(
                            model=DEFAULT_MODEL,
                            prompt_tokens=response.usage.prompt_tokens,
                            completion_tokens=response.usage.completion_tokens,
                            purpose="search_enhancement"
                        )
                    
                    enhanced_query = response.choices[0].message.content.strip()
                    
                    # Clean up the enhanced query
                    enhanced_query = re.sub(r'^(nope|no|yes|yeah|yep|sure|oh|wow|nice)\.?\s*', '', enhanced_query, flags=re.IGNORECASE)
                    enhanced_query = re.sub(r'[\'"]', '', enhanced_query)  # Remove quotes
                    enhanced_query = enhanced_query.strip()
                    
                    # Ensure the enhanced query is not malformed
                    if enhanced_query and len(enhanced_query) > 3:
                        logging.info(f"🔍 AI enhanced instruction-style query: '{enhanced_query}' (original: '{text}')")
                        return enhanced_query
            else:
                logging.info(f"🔍 Query doesn't meet criteria for enhancement. Has pronouns: {has_pronouns}, Is short query: {is_short_query}, Has instruction pattern: {has_instruction_pattern}")
            
            # Use DEFAULT_MODEL for consistency
            logging.info(f"🔍 Using Web Search Determination Prompt to evaluate search need")
            response = openai.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": get_web_search_determination_prompt(current_date)
                    },
                    {
                        "role": "user",
                        "content": f"{context}Message: {clean_text}\n\nDoes this message require a web search to provide an accurate response? Answer with just 'Yes' or 'No'."
                    }
                ],
                temperature=0.1,
                max_tokens=5
            )
            
            # Track token usage
            if hasattr(response, 'usage'):
                track_token_usage(
                    model=DEFAULT_MODEL,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    purpose="search_detection"
                )
            
            result = response.choices[0].message.content.strip().lower()
            logging.info(f"🔍 AI search detection result: {result}")
            return result == "yes"
    except Exception as e:
        logging.error(f"❌ Error in AI search detection: {e}")
        logging.error(traceback.format_exc())
        # Fall back to keyword detection
        return _keyword_search_detection(text)

def search_web(query, num_results=5, chat_guid=None):
    """
    Search the web for a query
    
    Args:
        query (str): Search query
        num_results (int, optional): Number of results to return
        chat_guid (str, optional): Chat GUID
        
    Returns:
        list: List of search results
    """
    start_time = time.time()
    logging.info(f"🔍 Starting web search for: '{query}'")
    
    # Check if we have API keys
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        logging.error("❌ Google API key or CSE ID not set")
        return []
    
    logging.info(f"🔍 Using Google API Key: {GOOGLE_API_KEY[:5]}...{GOOGLE_API_KEY[-5:]}")
    logging.info(f"🔍 Using Google CSE ID: {GOOGLE_CSE_ID}")
    
    # Check if this is a factual query about current events that might need special handling
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # Enhance query with current year for time-sensitive queries
    enhanced_query = query
    time_sensitive_keywords = ["current", "now", "today", "present", "latest"]
    entity_keywords = ["president", "prime minister", "ceo", "leader", "governor", "mayor", "secretary"]
    
    if any(keyword in query.lower() for keyword in time_sensitive_keywords) and any(entity in query.lower() for entity in entity_keywords):
        enhanced_query = f"{query} {current_year}"
        logging.info(f"🔍 Enhanced query with current year: '{enhanced_query}' (original: '{query}')")
    
    if chat_guid and chat_guid in CONVERSATION_CONTEXT:
        # Log the context for debugging
        logging.info(f"🔍 Context tracking - Recent messages: {CONVERSATION_CONTEXT[chat_guid]['recent_messages']}")
        logging.info(f"🔍 Context tracking - Detected entities: {CONVERSATION_CONTEXT[chat_guid]['entities']}")
        logging.info(f"🔍 Context tracking - Topics: {CONVERSATION_CONTEXT[chat_guid]['topics']}")
    
    # Build the search query
    search_query = {
        'q': enhanced_query,
        'key': GOOGLE_API_KEY,
        'cx': GOOGLE_CSE_ID,
        'num': num_results
    }
    
    # Send the request
    logging.info(f"🔍 Searching the web for: {enhanced_query}")
    logging.info(f"🔍 Sending request to Google API: {GOOGLE_SEARCH_URL}")
    
    try:
        response = requests.get(GOOGLE_SEARCH_URL, params=search_query)
        response.raise_for_status()
        
        logging.info(f"🔍 Google API response status code: {response.status_code}")
        
        # Parse the response
        results = response.json()
        
        # Check if we have results
        if 'items' not in results:
            logging.warning(f"⚠️ No search results found for: {enhanced_query}")
            return []
            
        # Extract the results
        search_results = []
        for item in results['items']:
            search_results.append({
                'title': item.get('title', 'No title'),
                'link': item.get('link', 'No link'),
                'snippet': item.get('snippet', 'No snippet')
            })
        
        logging.info(f"✅ Found {len(search_results)} search results")
        
        end_time = time.time()
        logging.debug(f"🔍 Web search completed in {end_time - start_time:.2f} seconds")
        
        return search_results
        
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error searching the web: {e}")
        return []

def extract_domain(url):
    """
    Extract domain name from URL for cleaner source attribution
    
    Args:
        url (str): URL
        
    Returns:
        str: Domain name
    """
    try:
        if url:
            match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if match:
                return match.group(1)
    except:
        pass
    return url

@backoff.on_exception(
    backoff.expo,
    (openai.RateLimitError, openai.APIError),
    max_tries=5,
    factor=2
)
def summarize_search_results(query, results, chat_guid=None, num_results=5):
    """
    Summarize search results using OpenAI with token optimization
    
    Args:
        query (str): Search query
        results (list): Search results
        chat_guid (str, optional): Chat GUID for context
        num_results (int, optional): Number of results to include in summary, defaults to 5
        
    Returns:
        str: Summarized results
    """
    # Initialize context variables
    context = ""
    messages_context = ""
    object_context = ""
    
    if not results:
        return "I looked that up but couldn't find relevant information. Is there something else you'd like to know?"
    
    # Get direct context from previous search if available
    if chat_guid and chat_guid in LAST_SEARCH:
        last_query = LAST_SEARCH[chat_guid].get('original_query')
        last_response = LAST_SEARCH[chat_guid].get('last_response')
        
        # Check for pronouns that might indicate a follow-up
        pronouns = ["they", "them", "their", "it", "its", "this", "that", "these", "those"]
        has_pronouns = any(pronoun in query.lower().split() for pronoun in pronouns)
        
        # Check if it's a short query (likely needs context)
        is_short = len(query.split()) <= 5
        
        if last_query and last_response and (has_pronouns or is_short) and last_query != query:
            # This is likely a follow-up question
            context = f"""CONVERSATION CONTEXT:

Previous question: "{last_query}"
Previous answer (excerpt): "{last_response[:200]}..."
Current question: "{query}"

The current question is a follow-up to the previous question. 
Make sure your response addresses the specific intent of the current question while maintaining context from the previous conversation.

"""
            logging.info(f"🔍 Using conversation context for summarization")
    # If no direct context, try conversation context
    elif chat_guid and chat_guid in CONVERSATION_CONTEXT:
        recent_messages = CONVERSATION_CONTEXT[chat_guid]['recent_messages']
        entities = CONVERSATION_CONTEXT[chat_guid]['entities']
        topics = CONVERSATION_CONTEXT[chat_guid]['topics']
        
        # Check if there was a recent image analysis - expanded to include more product types
        image_analysis_indicators = [
            # Plants
            "plant", "snake plant", "sansevieria", 
            # General identification phrases
            "looks like", "appears to be", "this is a", "that's a", "that is a",
            # Colors (often indicate product descriptions)
            "color", "purple", "blue", "red", "green", "yellow", "black", "white",
            # Food and beverages
            "can", "bottle", "drink", "soda", "flavor", "tasty", "dr pepper", "coca-cola", "pepsi"
        ]
        has_image_analysis = any(indicator in " ".join(recent_messages[-3:]).lower() for indicator in image_analysis_indicators)
        
        # Extract object name from recent image analysis if available
        object_name = None
        plant_type = None
        product_name = None
        
        if has_image_analysis:
            # First, look for specific plant types mentioned in recent messages
            plant_types = ["snake plant", "sansevieria", "orchid", "succulent", "cactus", "fern", "monstera", "pothos", "philodendron"]
            for msg in recent_messages[-3:]:
                for plant in plant_types:
                    if plant in msg.lower():
                        plant_type = plant
                        logging.info(f"🔍 Found specific plant type in messages for search context: '{plant_type}'")
                        break
                if plant_type:
                    break
            
            # Look for product names and descriptions (beverages, food items, etc.)
            product_indicators = ["dr pepper", "coca-cola", "pepsi", "sprite", "fanta", "mountain dew", "blackberry", "zero sugar"]
            for msg in recent_messages[-3:]:
                for product in product_indicators:
                    if product in msg.lower():
                        # If we find a product indicator, try to extract the full product name
                        product_match = re.search(r"(?:(?:that|this)(?:'s| is)? (?:a|an)? )?([a-zA-Z\s]+ (?:dr pepper|coca-cola|pepsi|sprite|fanta|mountain dew|zero sugar)[a-zA-Z\s]*)", msg.lower())
                        if product_match:
                            product_name = product_match.group(1).strip()
                        else:
                            # If regex fails, just use the indicator we found
                            product_name = product
                        logging.info(f"🔍 Found product name in messages for search context: '{product_name}'")
                        break
                if product_name:
                    break
            
            # If no specific plant type or product was found, try to extract the object name using patterns
            if not plant_type and not product_name:
                for msg in recent_messages[-3:]:
                    # More comprehensive pattern to catch various object descriptions
                    object_match = re.search(r"(?:that'?s|this is)(?: a| an)?(?: type of)? ([a-zA-Z\s]+?)(?:!|\.|,|\n|$| that| which| and)", msg.lower())
                    if object_match:
                        object_name = object_match.group(1).strip()
                        logging.info(f"🔍 Extracted object name from analysis for search context: '{object_name}'")
                        break
                    
                    # Try to extract color + object descriptions (e.g., "deep purple can")
                    color_object_match = re.search(r"((?:[a-zA-Z]+\s)?(?:purple|blue|red|green|yellow|black|white)\s[a-zA-Z]+)", msg.lower())
                    if color_object_match:
                        object_name = color_object_match.group(1).strip()
                        logging.info(f"🔍 Extracted color+object description from analysis: '{object_name}'")
                        break
        
        # Use the most specific information available
        final_object = product_name if product_name else (plant_type if plant_type else object_name)
        
        if recent_messages and len(recent_messages) > 1:
            # Format recent messages for context
            messages_context = "\n".join([f"- {msg}" for msg in recent_messages[-3:]])
            
            # Add specific context about the object if available
            if final_object:
                object_context = f"\nThe user recently asked about a {final_object} they shared in an image. The current query is likely related to this {final_object}."
        
            context = f"""CONVERSATION CONTEXT:

Recent messages:
{messages_context}{object_context}

Current question: "{query}"

The current question may be related to the recent conversation.
Make sure your response addresses the specific intent of the current question while maintaining context from the previous conversation.

"""
            logging.info(f"🔍 Using recent messages for context")
    
    # If no context was set, use a default context
    if not context:
        context = f"""SEARCH CONTEXT:

The user has asked: "{query}"

Provide a helpful response based on the search results without any additional context.
"""
        logging.info(f"🔍 Using default search context (no conversation history)")
    
    # Prepare system message
    system_message = SEARCH_SUMMARIZATION_PROMPT
    
    # Prepare search results text
    search_results_text = ""
    is_fallback_data = False
    
    # Check if these are fallback results
    if results and any("Current President of the United States" in result.get('title', '') for result in results):
        is_fallback_data = True
        logging.info(f"🔍 Using fallback data for search results")
    
    for i, result in enumerate(results[:num_results], 1):
        title = result.get('title', 'No title')
        snippet = result.get('snippet', 'No snippet available')
        url = result.get('link', 'No URL')
        domain = extract_domain(url)
        
        search_results_text += f"[{i}] {title}\n"
        search_results_text += f"URL: {url}\n"
        search_results_text += f"Source: {domain}\n"
        search_results_text += f"Snippet: {snippet}\n\n"
    
    # Log search results for debugging
    logging.info(f"🔍 Search results for query: '{query}'")
    for i, result in enumerate(results[:num_results], 1):
        title = result.get('title', 'No title')
        snippet = result.get('snippet', 'No snippet available')[:100] + "..." if len(result.get('snippet', '')) > 100 else result.get('snippet', 'No snippet available')
        logging.info(f"🔍 Result {i}: {title} - {snippet}")
    
    # Prepare user message
    user_message = f"{context}SEARCH QUERY: {query}\n\nSEARCH RESULTS:\n\n{search_results_text}"
    
    if is_fallback_data:
        user_message += "\nNOTE: These results are from a fallback data source as the web search did not return relevant information. The information is current as of the AI's last update and should be verified for the most recent details.\n"
    
    user_message += "\nBased on the search results above, provide a smart, quick, and concise response to the query. Use a casual, text-message style tone with 1-2 relevant emojis. Be brief but informative - aim for 2-4 short sentences when possible. Skip any greetings and get straight to the information. If the search results don't have enough information, let me know in a conversational way. If the user is asking for links or how to find something, include direct links formatted as [text](URL) to the most relevant websites."
    
    # Prepare messages
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]
    
    # Make API call
    response = openai.chat.completions.create(
        model=DEFAULT_MODEL,  # Using DEFAULT_MODEL for consistency across the application
        messages=messages,
        temperature=0.3,  # Lower temperature for more factual responses
        max_tokens=1000   # Increased token limit for more comprehensive answers
    )
    
    # Track token usage
    track_token_usage(
        model=DEFAULT_MODEL,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        purpose="search_summary"
    )
    
    # Get the summary
    summary = response.choices[0].message.content.strip()
    
    # Store the search results for future context
    if chat_guid:
        LAST_SEARCH[chat_guid] = {
            'original_query': query,
            'last_response': summary,
            'timestamp': datetime.now()
        }
        logging.info(f"🔍 Stored search summary for future context")
    
    # Add the search results to the OpenAI assistant thread for context maintenance
    try:
        # Import here to avoid circular imports
        from ai.assistant import conversation_threads, check_and_wait_for_active_runs
        
        if chat_guid and chat_guid in conversation_threads:
            thread_id = conversation_threads[chat_guid]
            
            # Check for active runs and wait for them to complete
            if check_and_wait_for_active_runs(thread_id):
                # Add the user's search query to the thread
                openai.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=query  # Use the actual query text instead of "Search query: {query}"
                )
                
                # Add the search results as an assistant message to maintain context
                openai.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="assistant",
                    content=summary
                )
                logging.info(f"✅ Added web search results to Assistant thread for context continuity")
            else:
                logging.warning("⚠️ Could not add web search results to thread due to active runs")
    except Exception as e:
        logging.error(f"❌ Error adding web search results to Assistant thread: {e}")
        logging.error(traceback.format_exc())
    
    return summary

def is_weather_query(text):
    """
    Determine if a query is asking about weather
    
    Args:
        text (str): Query text
        
    Returns:
        bool: True if weather query
    """
    if not text:
        return False
        
    # Weather-related keywords
    weather_keywords = [
        "weather", "temperature", "forecast", "rain", "snow", "storm", 
        "sunny", "cloudy", "humidity", "wind", "precipitation", "cold", 
        "hot", "warm", "chilly", "freezing", "degrees"
    ]
    
    # Weather-related patterns
    weather_patterns = [
        r"(?i)weather\s+(in|for|at)\s+.+",
        r"(?i)temperature\s+(in|at)\s+.+",
        r"(?i)is\s+it\s+(raining|snowing|cold|hot|warm|sunny|cloudy)\s+(in|at)\s+.+",
        r"(?i)what'?s\s+the\s+(weather|forecast|temperature)\s+(like|in|at|for)\s+.+",
        r"(?i)how\s+(cold|hot|warm|chilly)\s+is\s+it\s+(in|at)\s+.+",
        r"(?i)will\s+it\s+(rain|snow|be\s+cold|be\s+hot|be\s+sunny|be\s+cloudy)\s+(in|at|today|tomorrow|this\s+week)\s+.+"
    ]
    
    # Check for weather keywords
    for keyword in weather_keywords:
        if keyword.lower() in text.lower():
            return True
    
    # Check for weather patterns
    for pattern in weather_patterns:
        if re.search(pattern, text):
            return True
    
    return False

def clean_search_cache():
    """
    Clean expired entries from the search cache
    """
    global SEARCH_CACHE
    
    current_time = datetime.now()
    expired_keys = []
    
    for key, cache_entry in SEARCH_CACHE.items():
        cache_time = cache_entry['timestamp']
        if current_time - cache_time > timedelta(seconds=SEARCH_CACHE_EXPIRY):
            expired_keys.append(key)
    
    for key in expired_keys:
        del SEARCH_CACHE[key]
    
    logging.info(f"🧹 Cleaned {len(expired_keys)} expired entries from search cache")

def needs_supplemental_web_search(ai_response, text_prompt):
    """
    Determine if an AI response needs supplemental web search
    
    Args:
        ai_response (str): AI response
        text_prompt (str): User prompt
        
    Returns:
        bool: True if supplemental search is needed
    """
    # Check for uncertainty indicators in the AI response
    uncertainty_patterns = [
        r"(?i)I don'?t have (the latest|current|up-to-date|real-time) information",
        r"(?i)I don'?t have access to (the latest|current|up-to-date|real-time) information",
        r"(?i)my (knowledge|information|data) (is limited to|only goes up to|cuts off at)",
        r"(?i)I (can'?t|cannot|don'?t) (access|browse|search) the (internet|web)",
        r"(?i)I (don'?t have|lack|cannot access) (current|real-time|live) data",
        r"(?i)my training (data|cut-off|knowledge) (is|was) (in|from|before)",
        r"(?i)I (don'?t|cannot|can'?t) provide (current|real-time|up-to-date) information",
        r"(?i)for the most (current|up-to-date|recent) information",
        r"(?i)you (may|might|should|could) (want to|need to) (check|verify|look up)",
        r"(?i)I'?m not (able to|capable of) (searching|browsing|accessing) the (internet|web)"
    ]
    
    for pattern in uncertainty_patterns:
        if re.search(pattern, ai_response):
            # If the AI expresses uncertainty, check if the prompt requires current information
            return is_realtime_information_query(text_prompt)
    
    return False

def _is_likely_related(current_query, previous_query):
    """
    Determine if the current query is likely related to the previous query
    
    Args:
        current_query (str): Current query
        previous_query (str): Previous query
        
    Returns:
        bool: True if likely related
    """
    # Check for pronouns that might refer to entities in the previous query
    pronouns = ["it", "they", "them", "these", "those", "this", "that", "their", "its"]
    has_pronouns = any(pronoun in current_query.lower().split() for pronoun in pronouns)
    
    # Check if the query is very short (likely needs context)
    is_short = len(current_query.split()) <= 5
    
    # Check if the query starts with common follow-up patterns
    followup_starters = ["how", "what", "when", "where", "why", "who", "which", "is", "are", "do", "does", "can", "could"]
    starts_with_followup = any(current_query.lower().startswith(starter) for starter in followup_starters)
    
    # Extract potential entities from the previous query
    previous_words = re.findall(r'\b[A-Z][a-z]+\b', previous_query)
    
    # If we have pronouns or it's a short query starting with a follow-up word, it's likely related
    return has_pronouns or (is_short and starts_with_followup) or len(previous_words) > 0 

@backoff.on_exception(
    backoff.expo,
    (openai.RateLimitError, openai.APIError),
    max_tries=3,
    factor=2
)
def interpret_follow_up_question(current_query, previous_query, previous_response=None):
    """
    Use AI to interpret a follow-up question in the context of the previous query
    
    Args:
        current_query (str): The current follow-up question
        previous_query (str): The previous query
        previous_response (str, optional): The previous response
        
    Returns:
        str: The interpreted search query
    """
    # Log that a follow-up question was detected
    logging.info(f"🔄 Follow-up question detected: '{current_query}'")
    
    # Import re module explicitly to avoid UnboundLocalError
    import re
    
    # Check if this is likely a follow-up question
    pronouns = ["they", "them", "their", "it", "its", "this", "that", "these", "those"]
    has_pronouns = any(pronoun in current_query.lower().split() for pronoun in pronouns)
    is_short = len(current_query.split()) <= 5
    
    if not (has_pronouns or is_short):
        # Not likely a follow-up, return original query
        return current_query
    
    # Check if the previous query was an image analysis
    is_image_analysis = "image analysis" in previous_query.lower()
    
    # Check for related topics in the conversation context
    chat_guid = None
    try:
        for guid, context in CONVERSATION_CONTEXT.items():
            if previous_query in context['recent_messages'] or any(previous_query in msg for msg in context['recent_messages']):
                chat_guid = guid
                break
    except Exception as e:
        logging.error(f"❌ Error finding chat context: {e}")
    
    # If we have relevant topics from the conversation, use them to enhance the query
    if is_short or has_pronouns:
        try:
            # Format the prompt for AI
            current_date = get_current_date_formatted()
            
            # Use the AI to interpret the follow-up question in context
            response = openai.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": FOLLOW_UP_QUESTION_PROMPT
                    },
                    {
                        "role": "user",
                        "content": f"DATE: {current_date}\n\nPrevious question: {previous_query}\n\n{'' if previous_response is None else 'Previous answer: ' + previous_response + '\n\n'}Follow-up question: {current_query}\n\nPlease interpret this follow-up question in the context of the previous question and answer. Return a specific, detailed query that captures the user's intent."
                    }
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            # Track token usage
            if hasattr(response, 'usage'):
                track_token_usage(
                    model=DEFAULT_MODEL,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    purpose="follow_up_interpretation"
                )
            
            # Extract the enhanced query from the response
            enhanced_query = response.choices[0].message.content.strip()
            
            # Clean up the response
            enhanced_query = re.sub(r'^(query|search|search query|enhanced query|interpreted query)[:\-]?\s*', '', enhanced_query, flags=re.IGNORECASE)
            enhanced_query = re.sub(r'^["\'](.*)["\']$', r'\1', enhanced_query)  # Remove quotes if present
            
            logging.info(f"🔄 Interpreted follow-up question: '{enhanced_query}' (original: '{current_query}')")
            
            return enhanced_query
        except Exception as e:
            logging.error(f"❌ Error interpreting follow-up question: {e}")
            logging.error(traceback.format_exc())
            # Return the original query if there's an error
            return current_query
    
    return current_query