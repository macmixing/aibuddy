import os
import logging
import sys
import backoff
import openai
import time

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.token_tracking import track_token_usage
from ai.openai_client import check_rate_limit
from utils.file_handling import convert_heic_to_jpeg, convert_audio_to_mp3

def contains_url(text):
    """
    Check if text contains a URL
    
    Args:
        text (str): Text to check
        
    Returns:
        bool: True if text contains a URL
    """
    import re
    
    if not text:
        return False
        
    # URL pattern
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    
    # Check if text contains a URL
    return bool(re.search(url_pattern, text))

def is_image_request(text):
    """
    Determine if a message is requesting image generation
    
    Args:
        text (str): Message text
        
    Returns:
        bool: True if image generation is requested
    """
    if not text:
        return False
    
    # Log the text being analyzed
    logging.info(f"🔍 Checking if text is an image request: '{text}'")
        
    # Check for explicit image generation commands
    import re
    
    # Patterns that indicate image generation requests
    image_patterns = [
        r"(?i)^(generate|create|draw|show me|imagine)(\s+a|\s+an)?\s+.+",
        r"(?i)^(image|picture|photo|drawing|illustration|artwork|graphic)\s+of\s+.+",
        r"(?i)^(can you|could you|please)(\s+generate|\s+create|\s+make|\s+draw|\s+show me)(\s+a|\s+an)?\s+.+",
    ]
    
    for pattern in image_patterns:
        if re.match(pattern, text):
            # Make sure it's not a URL
            if not contains_url(text):
                logging.info(f"✅ Detected image request pattern: '{pattern}' in text: '{text}'")
                return True
            else:
                logging.info(f"⚠️ Text contains URL, not treating as image request: '{text}'")
    
    logging.info(f"❌ Text is not an image request: '{text}'")
    return False

def prepare_image_for_analysis(image_path):
    """
    Prepare an image for analysis by converting it to a supported format if needed
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str: Path to the prepared image
    """
    # Check if the file exists
    if not os.path.exists(image_path):
        logging.error(f"❌ Image file not found: {image_path}")
        return None
        
    # Check if the file is a HEIC image
    _, ext = os.path.splitext(image_path)
    if ext.lower() in ['.heic', '.heif']:
        logging.info(f"🔄 Converting HEIC image for analysis: {image_path}")
        return convert_heic_to_jpeg(image_path)
    
    # Return the original path for other image types
    return image_path

@backoff.on_exception(
    backoff.expo,
    (openai.RateLimitError, openai.APIError),
    max_tries=5,
    factor=2
)
def transcribe_audio(audio_path):
    """
    Transcribe audio using OpenAI Whisper API
    
    Args:
        audio_path (str): Path to the audio file
        
    Returns:
        tuple: (transcription_text, mp3_path) - The transcription text and the path to the MP3 file
    """
    start_time = time.time()
    
    try:
        # Check if file exists
        if not os.path.exists(audio_path):
            return "Audio file not found.", None
            
        # Convert to MP3 if needed
        mp3_path = convert_audio_to_mp3(audio_path)
        
        if not mp3_path or not os.path.exists(mp3_path):
            logging.error(f"❌ Failed to convert audio to MP3: {audio_path}")
            return "Failed to convert audio for transcription.", None
            
        # Check rate limit before making API call
        check_rate_limit()
        
        # Open the audio file
        with open(mp3_path, "rb") as audio_file:
            # Transcribe the audio
            logging.info(f"🎤 Transcribing audio: {mp3_path}")
            
            response = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            
            # Track token usage (approximate since Whisper doesn't provide token counts)
            # We'll estimate based on audio length
            import wave
            prompt_tokens = 1000  # Default value
            
            try:
                # For MP3 files, we can't use wave directly
                # Use ffprobe to get duration if available
                if mp3_path.lower().endswith('.mp3'):
                    try:
                        import subprocess
                        cmd = [
                            "ffprobe", 
                            "-v", "error", 
                            "-show_entries", "format=duration", 
                            "-of", "default=noprint_wrappers=1:nokey=1", 
                            mp3_path
                        ]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            duration = float(result.stdout.strip())
                            prompt_tokens = int(duration * 100)
                            logging.info(f"🎤 Audio duration: {duration:.2f} seconds")
                    except Exception as e:
                        logging.warning(f"⚠️ Could not determine MP3 duration: {e}")
                else:
                    with wave.open(mp3_path, "rb") as wav_file:
                        frames = wav_file.getnframes()
                        rate = wav_file.getframerate()
                        duration = frames / float(rate)
                        # Rough estimate: 100 tokens per second of audio
                        prompt_tokens = int(duration * 100)
            except Exception as e:
                # If we can't determine duration, use the default value
                logging.warning(f"⚠️ Could not determine audio duration: {e}")
            
            track_token_usage(
                model="whisper-1",
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                purpose="audio_transcription"
            )
            
            # Return the transcription
            transcription = response.text
            
            end_time = time.time()
            logging.info(f"✅ Transcription complete in {end_time - start_time:.2f} seconds: {transcription[:100]}...")
            
            return transcription, mp3_path
            
    except Exception as e:
        end_time = time.time()
        logging.error(f"❌ Error transcribing audio after {end_time - start_time:.2f} seconds: {e}")
        return f"Error transcribing audio: {str(e)}", None 