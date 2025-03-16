import openai
import os
import time
import logging
import backoff
import sys

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, DEFAULT_MODEL
from utils.token_tracking import track_token_usage

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Rate limiting variables
last_request_time = 0
request_count = 0
MAX_REQUESTS_PER_MINUTE = 50
REQUEST_INTERVAL = 60 / MAX_REQUESTS_PER_MINUTE

def check_rate_limit():
    """
    Implement rate limiting for OpenAI API calls
    """
    global last_request_time, request_count
    
    current_time = time.time()
    
    # Reset counter if a minute has passed
    if current_time - last_request_time >= 60:
        request_count = 0
        last_request_time = current_time
    
    # If we've made too many requests, wait
    if request_count >= MAX_REQUESTS_PER_MINUTE:
        sleep_time = 60 - (current_time - last_request_time)
        if sleep_time > 0:
            logging.info(f"⏳ Rate limit reached, waiting {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            # Reset after waiting
            request_count = 0
            last_request_time = time.time()
    
    # Increment request counter
    request_count += 1
    
    # Add a small delay between requests to avoid bursts
    if request_count > 1:  # Don't delay the first request
        time.sleep(REQUEST_INTERVAL)

def verify_openai_models():
    """
    Verify that the configured OpenAI models are available
    
    Returns:
        bool: True if all models are available, False otherwise
    """
    try:
        # Check rate limit before making API call
        check_rate_limit()
        
        # Get available models
        models = openai.models.list()
        available_models = [model.id for model in models.data]
        
        # Check if our models are available
        models_to_check = [DEFAULT_MODEL]
        missing_models = []
        
        for model in models_to_check:
            if model not in available_models:
                missing_models.append(model)
        
        if missing_models:
            logging.error(f"❌ The following models are not available: {', '.join(missing_models)}")
            return False
        
        logging.info(f"✅ All required OpenAI models are available")
        return True
        
    except Exception as e:
        logging.error(f"❌ Error verifying OpenAI models: {e}")
        return False

@backoff.on_exception(
    backoff.expo,
    (openai.RateLimitError, openai.APIError),
    max_tries=5,
    factor=2
)
def get_completion(prompt, model=None, system_message=None, temperature=0.7, max_tokens=None):
    """
    Get a completion from the OpenAI API
    
    Args:
        prompt (str): The user prompt
        model (str, optional): The model to use
        system_message (str, optional): The system message
        temperature (float, optional): The temperature
        max_tokens (int, optional): The maximum number of tokens
        
    Returns:
        str: The completion text
    """
    if model is None:
        model = DEFAULT_MODEL
    
    start_time = time.time()
    
    try:
        # Check rate limit before making API call
        check_rate_limit()
        
        # Prepare messages
        messages = []
        
        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        # Add user message
        messages.append({"role": "user", "content": prompt})
        
        # Prepare parameters
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        # Add max_tokens if provided
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        # Make API call
        response = openai.chat.completions.create(**params)
        
        # Track token usage
        track_token_usage(
            model=model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            purpose="text_completion"
        )
        
        end_time = time.time()
        logging.debug(f"⏱️ OpenAI completion took {end_time - start_time:.2f} seconds")
        
        # Return the completion text
        return response.choices[0].message.content
        
    except Exception as e:
        end_time = time.time()
        logging.error(f"❌ Error getting completion after {end_time - start_time:.2f} seconds: {e}")
        return f"I'm sorry, I encountered an error: {str(e)}"

# The analyze_image_with_ai function has been removed as it's not used in the current flow 