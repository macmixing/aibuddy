import os
import base64
import logging
import subprocess
import tempfile
import shutil
from PIL import Image
import sys
import time
import glob
import traceback

# Import configuration
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PICTURES_DIR

# Global list to track temporary files
TEMP_FILES = []

def add_temp_file(file_path):
    """Add a file to the list of temporary files to be cleaned up."""
    if file_path and os.path.exists(file_path):
        TEMP_FILES.append(file_path)
        logging.debug(f"📝 Added temporary file: {file_path}")

def cleanup_temp_files():
    """Clean up temporary files."""
    global TEMP_FILES
    
    if not TEMP_FILES:
        return
    
    logging.info(f"🧹 Cleaning up {len(TEMP_FILES)} temporary files")
    
    for file_path in TEMP_FILES:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.debug(f"🗑️ Removed temporary file: {file_path}")
        except Exception as e:
            logging.error(f"❌ Error removing temporary file {file_path}: {e}")
    
    # Clear the list
    TEMP_FILES = []
    logging.info("✅ Temporary files cleanup complete")

def optimize_image(input_path, output_path=None, max_size=1024):
    """Optimize an image for processing."""
    try:
        from PIL import Image
        
        # If no output path specified, use the input path
        if not output_path:
            output_path = input_path
        
        # Open the image
        img = Image.open(input_path)
        
        # Convert HEIC to JPG if needed
        if input_path.lower().endswith('.heic'):
            output_path = output_path.replace('.heic', '.jpg').replace('.HEIC', '.jpg')
        
        # Resize if needed
        width, height = img.size
        if width > max_size or height > max_size:
            # Calculate new dimensions
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            # Resize the image
            img = img.resize((new_width, new_height), Image.LANCZOS)
            logging.info(f"🖼️ Resized image from {width}x{height} to {new_width}x{new_height}")
        
        # Save the optimized image
        img.save(output_path, quality=85, optimize=True)
        
        # Add to temp files if different from input
        if output_path != input_path:
            add_temp_file(output_path)
        
        return output_path
    
    except ImportError:
        logging.warning("⚠️ PIL not installed, skipping image optimization")
        return input_path
    
    except Exception as e:
        logging.error(f"❌ Error optimizing image: {e}")
        return input_path

def encode_image_to_base64(image_path):
    """
    Convert image to base64 string with optimization
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str: Base64-encoded image string
    """
    start_time = time.time()
    
    try:
        # Check if the file is HEIC and convert if needed
        _, ext = os.path.splitext(image_path)
        if ext.lower() in ['.heic', '.heif']:
            logging.info(f"🔄 Converting HEIC image before encoding: {image_path}")
            image_path = convert_heic_to_jpeg(image_path)
        
        # Optimize image before encoding
        optimized_path = optimize_image(image_path)
        
        with open(optimized_path, "rb") as image_file:
            base64_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        end_time = time.time()
        logging.debug(f"🔄 Image encoded to base64 in {end_time - start_time:.2f} seconds")
        
        return base64_string
    except Exception as e:
        logging.error(f"❌ Error encoding image: {e}")
        return None

def convert_heic_to_jpeg(heic_path):
    """
    Convert HEIC image to JPEG format
    
    Args:
        heic_path (str): Path to the HEIC file
        
    Returns:
        str: Path to the converted JPEG file
    """
    global TEMP_FILES
    start_time = time.time()
    
    try:
        # Create output path with .jpg extension
        jpeg_path = os.path.splitext(heic_path)[0] + ".jpg"
        
        # Add both original HEIC and new JPEG to temp files list for later cleanup
        # Ensure the original HEIC file is in the temp files list
        if heic_path not in TEMP_FILES:
            TEMP_FILES.append(heic_path)
            logging.debug(f"📝 Added original HEIC file to temp files: {heic_path}")
        
        # Add the JPEG path to temp files list
        TEMP_FILES.append(jpeg_path)
        logging.debug(f"📝 Added converted JPEG file to temp files: {jpeg_path}")
        
        logging.info(f"🔄 Converting HEIC to JPEG: {heic_path}")
        
        # Try using sips (macOS built-in tool) - most reliable on macOS
        try:
            cmd = [
                "sips",
                "-s", "format", "jpeg",
                "-s", "formatOptions", "high",
                heic_path,
                "--out", jpeg_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(jpeg_path):
                end_time = time.time()
                logging.info(f"✅ Converted HEIC to JPEG using sips in {end_time - start_time:.2f} seconds: {jpeg_path}")
                return jpeg_path
            else:
                logging.warning(f"⚠️ sips conversion failed: {result.stderr}")
                # Fall back to other methods
        except Exception as e:
            logging.warning(f"⚠️ sips conversion error: {e}")
            # Fall back to other methods
        
        # Try using ImageMagick if available
        try:
            cmd = [
                "magick",
                "convert",
                heic_path,
                jpeg_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(jpeg_path):
                end_time = time.time()
                logging.info(f"✅ Converted HEIC to JPEG using ImageMagick in {end_time - start_time:.2f} seconds: {jpeg_path}")
                return jpeg_path
            else:
                logging.warning(f"⚠️ ImageMagick conversion failed: {result.stderr}")
                # Fall back to other methods
        except FileNotFoundError:
            try:
                # Try alternative ImageMagick command format
                cmd = [
                    "convert",
                    heic_path,
                    jpeg_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0 and os.path.exists(jpeg_path):
                    end_time = time.time()
                    logging.info(f"✅ Converted HEIC to JPEG using ImageMagick (convert) in {end_time - start_time:.2f} seconds: {jpeg_path}")
                    return jpeg_path
                else:
                    logging.warning(f"⚠️ ImageMagick (convert) failed: {result.stderr}")
            except Exception as e:
                logging.warning(f"⚠️ ImageMagick (convert) error: {e}")
        except Exception as e:
            logging.warning(f"⚠️ ImageMagick error: {e}")
        
        # Try using pillow_heif if available
        try:
            import pillow_heif
            from PIL import Image
            
            heif_file = pillow_heif.read_heif(heic_path)
            image = Image.frombytes(
                heif_file.mode, 
                heif_file.size, 
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride,
            )
            image.save(jpeg_path, format="JPEG", quality=95)
            
            if os.path.exists(jpeg_path):
                end_time = time.time()
                logging.info(f"✅ Converted HEIC to JPEG using pillow_heif in {end_time - start_time:.2f} seconds: {jpeg_path}")
                return jpeg_path
            else:
                logging.warning("⚠️ pillow_heif conversion failed")
        except ImportError:
            logging.warning("⚠️ pillow_heif not available")
        except Exception as e:
            logging.warning(f"⚠️ pillow_heif error: {e}")
        
        # If all methods failed, create a copy with .jpg extension
        # This won't actually convert the format, but it will allow the file to be processed
        # by the rest of the code that expects a JPEG file
        try:
            logging.warning("⚠️ All HEIC conversion methods failed, creating a copy with .jpg extension")
            shutil.copy2(heic_path, jpeg_path)
            return jpeg_path
        except Exception as e:
            logging.error(f"❌ Error creating copy with .jpg extension: {e}")
        
        # If all methods failed, return the original path
        logging.error("❌ All HEIC conversion methods failed")
        return heic_path
        
    except Exception as e:
        logging.error(f"❌ Error converting HEIC to JPEG: {e}")
        return heic_path

def convert_audio_to_mp3(audio_path):
    """
    Convert audio file to MP3 format for compatibility with transcription services
    
    Args:
        audio_path (str): Path to the audio file
        
    Returns:
        str: Path to the converted MP3 file
    """
    global TEMP_FILES
    start_time = time.time()
    
    try:
        # Get file extension
        _, ext = os.path.splitext(audio_path)
        ext = ext.lower()
        
        # If already MP3, return the original path
        if ext == '.mp3':
            return audio_path
            
        # Create output path with .mp3 extension
        mp3_path = os.path.splitext(audio_path)[0] + ".mp3"
        
        # Add to temp files list for later cleanup
        add_temp_file(mp3_path)
        logging.debug(f"📝 Added MP3 file to temp files: {mp3_path}")
        
        logging.info(f"🔄 Converting audio to MP3: {audio_path} (format: {ext})")
        
        # Check if ffmpeg is installed
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logging.error("❌ ffmpeg not found. Please install ffmpeg to enable audio conversion.")
            return audio_path
        
        # Use ffmpeg for conversion with improved parameters for various formats
        cmd = [
            "ffmpeg",
            "-i", audio_path,
            "-vn",  # No video
            "-ar", "44100",  # Sample rate
            "-ac", "2",  # Stereo
            "-b:a", "192k",  # Bitrate
            "-y",  # Overwrite output file
        ]
        
        # Add format-specific parameters if needed
        if ext in ['.caf', '.aiff', '.aif']:
            # For Apple-specific formats, ensure proper decoding
            cmd = [
                "ffmpeg",
                "-i", audio_path,
                "-vn",  # No video
                "-acodec", "libmp3lame",  # MP3 codec
                "-ar", "48000",  # Audio sampling rate (increased from 44100)
                "-ac", "1",  # Mono (most voice messages are mono)
                "-b:a", "256k",  # Bitrate (increased from 192k)
                "-af", "silenceremove=1:0:-50dB,loudnorm=I=-16:TP=-1.5:LRA=11",  # Remove silence and normalize audio
                "-y",  # Overwrite output file
                mp3_path
            ]
            logging.info(f"🔄 Using specialized conversion for CAF/AIFF: {' '.join(cmd)}")
        elif ext in ['.amr', '.3gp']:
            # For mobile formats, ensure proper decoding
            cmd.extend(["-acodec", "libmp3lame", "-ar", "16000"])
        elif ext in ['.opus', '.ogg']:
            # For Opus/Ogg formats
            cmd.extend(["-acodec", "libmp3lame"])
        
        # Add output path
        cmd.append(mp3_path)
        
        # Run the conversion
        logging.info(f"🔄 Running ffmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(mp3_path):
            end_time = time.time()
            logging.info(f"✅ Converted audio to MP3 in {end_time - start_time:.2f} seconds: {mp3_path}")
            return mp3_path
        else:
            logging.error(f"❌ ffmpeg conversion failed: {result.stderr}")
            # Try a simpler conversion as fallback
            fallback_cmd = [
                "ffmpeg",
                "-i", audio_path,
                "-y",  # Overwrite output file
                mp3_path
            ]
            logging.info(f"🔄 Trying fallback conversion: {' '.join(fallback_cmd)}")
            fallback_result = subprocess.run(fallback_cmd, capture_output=True, text=True)
            
            if fallback_result.returncode == 0 and os.path.exists(mp3_path):
                end_time = time.time()
                logging.info(f"✅ Fallback conversion succeeded in {end_time - start_time:.2f} seconds: {mp3_path}")
                return mp3_path
            else:
                logging.error(f"❌ Fallback conversion also failed: {fallback_result.stderr}")
                return audio_path
            
    except Exception as e:
        logging.error(f"❌ Error converting audio to MP3: {e}")
        logging.error(traceback.format_exc())
        return audio_path

def download_attachment_to_directory(attachment_path, file_type=None):
    """
    Copy an attachment to the pictures directory
    
    Args:
        attachment_path (str): Path to the attachment
        file_type (str, optional): Type of file (image, audio, document)
        
    Returns:
        str: Path to the copied file
    """
    global TEMP_FILES
    start_time = time.time()
    
    try:
        # Create pictures directory if it doesn't exist
        os.makedirs(PICTURES_DIR, exist_ok=True)
        
        # Get filename from path
        filename = os.path.basename(attachment_path)
        
        # Split filename into name and extension
        name, ext = os.path.splitext(filename)
        
        # Ensure extension is lowercase
        ext = ext.lower()
        
        # Create new filename with lowercase extension
        filename = name + ext
        
        # Create destination path
        destination_path = os.path.join(PICTURES_DIR, filename)
        
        # Add to temp files list for later cleanup (unless it's a generated image)
        # For images, we always want to add them to the temp files list
        if file_type == "image" or not filename.startswith("dalle_"):
            add_temp_file(destination_path)
            logging.debug(f"📝 Added attachment to temp files: {destination_path}")
        
        # Copy file
        shutil.copy2(attachment_path, destination_path)
        
        # If this is an image file with HEIC extension, convert it to JPEG
        _, ext = os.path.splitext(destination_path)
        if file_type == "image" and ext.lower() in ['.heic', '.heif']:
            # Convert HEIC to JPEG - this function will add both files to TEMP_FILES
            jpeg_path = convert_heic_to_jpeg(destination_path)
            
            # Ensure the original HEIC file is in the temp files list
            if destination_path not in TEMP_FILES:
                add_temp_file(destination_path)
                logging.debug(f"📝 Ensured original HEIC file is in temp files: {destination_path}")
            
            # Log the files that will be cleaned up
            logging.info(f"🧹 Files scheduled for cleanup: Original HEIC ({destination_path}) and converted JPEG ({jpeg_path})")
            
            destination_path = jpeg_path
        
        end_time = time.time()
        logging.info(f"📁 Copied attachment to {destination_path} in {end_time - start_time:.2f} seconds")
        
        return destination_path
    except Exception as e:
        logging.error(f"❌ Error copying attachment: {e}")
        return attachment_path

def get_file_type(file_path):
    """Determine the type of file based on extension and mime type."""
    if not file_path or not os.path.exists(file_path):
        return "unknown"
    
    # Get file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    # Image types
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.heic', '.webp', '.bmp', '.tiff', '.tif']:
        return "image"
    
    # Document types
    if ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.pages', '.xlsx', '.xls']:
        return "document"
    
    # Audio types - expanded list
    if ext in ['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.caf', '.aiff', '.aif', '.amr', '.3gp', '.opus', '.wma', '.alac', '.ape', '.au', '.mid', '.midi']:
        return "audio"
    
    # Video types
    if ext in ['.mp4', '.mov', '.avi', '.wmv', '.flv', '.mkv', '.webm']:
        return "video"
    
    # Try to determine type based on mime type if extension is not recognized
    try:
        import magic
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        
        if mime_type.startswith('audio/'):
            logging.info(f"🔍 Detected audio file by mime type: {mime_type} for {file_path}")
            return "audio"
        elif mime_type.startswith('image/'):
            return "image"
        elif mime_type.startswith('video/'):
            return "video"
        elif mime_type in ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']:
            return "document"
    except ImportError:
        logging.warning("⚠️ python-magic not installed, falling back to extension-based detection only")
    except Exception as e:
        logging.warning(f"⚠️ Error determining mime type: {e}")
    
    # Default to unknown
    return "unknown" 