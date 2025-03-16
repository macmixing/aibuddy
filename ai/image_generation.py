import os
import sys
import logging
import time
import traceback
import requests
import backoff
import openai
from datetime import datetime

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_API_KEY, PICTURES_DIR
from utils.token_tracking import track_token_usage
from ai.openai_client import check_rate_limit

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

@backoff.on_exception(
    backoff.expo,
    (openai.RateLimitError, openai.APIError),
    max_tries=5,
    factor=2
)
def generate_image(prompt, size="1024x1024", quality="standard", model="dall-e-3"):
    """
    Generate an image using OpenAI's DALL-E
    
    Args:
        prompt (str): Image generation prompt
        size (str, optional): Image size (1024x1024, 1792x1024, or 1024x1792)
        quality (str, optional): Image quality (standard or hd)
        model (str, optional): DALL-E model to use
        
    Returns:
        str: Path to the generated image
    """
    start_time = time.time()
    
    try:
        # Create pictures directory if it doesn't exist
        os.makedirs(PICTURES_DIR, exist_ok=True)
        
        # Log the prompt
        logging.info(f"🎨 Generating image with prompt: {prompt}")
        
        # Check rate limit before making API call
        check_rate_limit()
        
        # Generate image with DALL-E
        logging.info(f"🎨 Calling DALL-E API to generate image")
        response = openai.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1
        )
        
        # Track token usage (approximate since image generation doesn't provide token counts)
        track_token_usage(
            model=model,
            prompt_tokens=len(prompt),
            completion_tokens=0,
            purpose="image_generation"
        )
        
        # Get the image URL
        image_url = response.data[0].url
        logging.info(f"🎨 Received image URL from DALL-E API")
        
        # Create a unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = os.path.join(PICTURES_DIR, f"dalle_{timestamp}.png")
        
        # Download the image
        logging.info(f"🎨 Downloading image to {image_path}")
        image_data = requests.get(image_url).content
        with open(image_path, "wb") as f:
            f.write(image_data)
        
        generation_time = time.time() - start_time
        logging.info(f"✅ Image generated in {generation_time:.2f} seconds and saved to {image_path}")
        
        return image_path
        
    except Exception as e:
        logging.error(f"❌ Error generating image: {e}")
        logging.error(traceback.format_exc())
        return None 