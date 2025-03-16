# AI Buddy: Advanced iMessage AI Assistant

![AI Buddy Logo](https://github.com/macmixing/aibuddy/blob/main/aibuddy.png)

## Overview

AI Buddy is a powerful AI assistant for iMessage that integrates with your messaging app to provide intelligent responses, analyze images, process documents, search the web, and more. Built with a modular architecture, AI Buddy leverages OpenAI's advanced models to deliver a seamless AI experience directly in your iMessage conversations.

AI Buddy works with both iMessage and SMS, and will respond to messages sent to any phone number or email address you have configured in your iMessage settings.

## Features

### Core Capabilities
- **Intelligent Conversations**: Engage in natural, context-aware conversations powered by OpenAI's GPT models
- **Image Analysis**: Send images to AI Buddy for detailed analysis and descriptions
- **Image Generation**: Request AI-generated images with natural language prompts
- **Document Processing**: Extract and analyze text from various document formats (PDF, DOCX, XLSX, RTF, TXT)
- **Web Search**: Request real-time information from the web with intelligent search capabilities
- **Audio Transcription**: Transcribe audio messages and files automatically
- **Memory Management**: Maintains conversation context for more coherent interactions
- **Rate Limiting**: Built-in rate limiting to prevent API overuse

### Supported File Types
- **Images**: JPG, PNG, HEIC, GIF, BMP, TIFF (HEIC automatically converted)
- **Documents**: PDF, DOCX, XLSX, RTF, TXT, CSV, HTML
- **Audio**: MP3, MP4, M4A, WAV, WEBM, OGG (requires ffmpeg)

### Advanced Features
- **Context-aware responses**: AI Buddy remembers previous conversations for more coherent interactions
- **Follow-up question handling**: Intelligently interprets follow-up questions in context
- **Product information extraction**: Recognizes and tracks product details in conversations
- **Weather query detection**: Identifies and responds to weather-related questions
- **Token usage tracking**: Monitors and logs API token usage for cost management
- **Multi-turn conversations**: Maintains context across multiple messages
- **Automatic language detection**: Responds in the same language as the user's query

## Commands and Usage Examples

### General Conversation
Simply send a message to start a conversation. AI Buddy maintains context throughout the conversation.

### Image Analysis
- Send any supported image file and ask: "What's in this picture?"
- "Describe this image in detail"
- "What can you tell me about this photo?"
- "Is there any text in this image?"
- "What breed is this dog?"

### Image Generation
- "Generate an image of a sunset over mountains"
- "Create a picture of a futuristic city"
- "Draw a cartoon cat wearing sunglasses"
- "Make an illustration of a tropical beach"
- "AI generate a watercolor painting of flowers"

### Document Processing
- Send a PDF, DOCX, or other document and ask: "Summarize this document"
- "Extract the key points from this PDF"
- "What are the main ideas in this document?"
- "Find all the dates mentioned in this file"
- "Translate this document to Spanish"

### Web Search
- "Search for the latest iPhone reviews"
- "Find information about climate change"
- "Look up the recipe for chocolate chip cookies"
- "What's happening with the stock market today?"
- "Find recent news about renewable energy"

### Audio Transcription
- Send an audio file and AI Buddy will automatically transcribe it
- "Transcribe this audio file"
- "What is said in this recording?"
- "Summarize this audio clip"

## Requirements

### System Requirements
- macOS (required for iMessage integration)
- Python 3.8 or higher
- Access to the iMessage database (requires Full Disk Access permission)

### API Keys
- **OpenAI API Key**: Required for all AI capabilities (conversations, image analysis, document processing)
- **OpenAI Assistant ID**: Optional - if not provided, the system will use a default assistant or create a new one
- **Google API Key**: Required only for web search functionality
- **Google Custom Search Engine ID**: Required only for web search functionality

### External Dependencies
- **Tesseract OCR**: Required for text extraction from images
  ```
  brew install tesseract
  ```
- **ffmpeg**: Required for audio processing
  ```
  brew install ffmpeg
  ```
- **libheif** (optional): For better HEIC image support
  ```
  brew install libheif
  ```

## Installation

1. **Clone the repository**
   ```
   git clone https://github.com/yourusername/aibuddy.git
   cd aibuddy
   ```

2. **Create and activate a virtual environment**
   ```
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

4. **Set up configuration file**
   
   The repository includes a template configuration file named `config_EXAMPLE.py`. You need to:
   
   a. Rename this file to `config.py`:
   ```
   mv config_EXAMPLE.py config.py
   ```
   
   b. Edit the `config.py` file to add your API keys and customize settings:
   ```python
   # OpenAI API configuration
   OPENAI_API_KEY = "your-openai-api-key"  # Required
   ASSISTANT_ID = "your-openai-assistant-id"  # Required
   
   # Google Custom Search API credentials (for web search)
   GOOGLE_API_KEY = "your-google-api-key"  # Required for web search
   GOOGLE_CSE_ID = "your-google-cse-id"    # Required for web search
   
   # Other settings can be customized as needed
   DEFAULT_MODEL = "gpt-4o-mini"  # The OpenAI model to use
   THREAD_MESSAGE_LIMIT = 10  # Number of messages to keep in context
   ```
   
   c. Make sure to replace the placeholder values with your actual API keys

5. **Grant Full Disk Access permission**
   
   AI Buddy needs access to the iMessage database:
   - Open System Preferences > Security & Privacy > Privacy
   - Select "Full Disk Access" from the sidebar
   - Click the "+" button and add your Terminal or Python application

## Usage

### Starting AI Buddy

Run the main script to start the AI Buddy service:
```
python main.py
```

### Compatibility

AI Buddy works with:
- **iMessage**: Full functionality with all Apple iMessage users
- **SMS**: Works with standard SMS text messages to non-Apple users
- **Multiple accounts**: Responds to any phone number or email address configured in your iMessage settings

### Interacting with AI Buddy

Once running, AI Buddy will monitor your iMessages and SMS messages and respond to messages directed to it. Here are some example interactions:

#### Conversation Examples
- **General knowledge**: "What's the capital of France?"
- **Calculations**: "What's 15% of 67.50 plus 20?"
- **Creative writing**: "Write a short poem about autumn"
- **Coding help**: "How do I write a Python function to find prime numbers?"
- **Language translation**: "Translate 'hello, how are you?' to Japanese"

#### File Handling Examples
- **Send an image**: AI Buddy will analyze it automatically
- **Send a document**: AI Buddy will extract and analyze the text
- **Send an audio file**: AI Buddy will transcribe the content

#### Special Commands
- **Web search**: Any question about current events or specific information will trigger a web search
- **Image generation**: Start with "generate", "create", "draw", or "AI generate" to create images
- **Reset conversation**: "Let's start over" or "Reset our conversation" to clear context

### Configuration Options

You can customize AI Buddy's behavior by modifying the `config.py` file:

- **POLLING_INTERVAL**: Frequency of checking for new messages (in seconds)
- **DEFAULT_MODEL**: The OpenAI model to use for general responses
- **THREAD_MESSAGE_LIMIT**: Number of messages to keep in conversation context
- **WEB_SEARCH_ENABLED**: Enable/disable web search functionality
- **MAX_SEARCH_RESULTS**: Maximum number of search results to return
- **IMAGE_GENERATION_ENABLED**: Enable/disable image generation
- **AUDIO_TRANSCRIPTION_ENABLED**: Enable/disable audio transcription

## Project Structure

```
aibuddy/
├── ai/                     # AI-related modules
│   ├── assistant.py        # OpenAI Assistant API integration
│   ├── document_analysis.py # Document processing capabilities
│   ├── image_analysis.py   # Image analysis capabilities
│   └── openai_client.py    # OpenAI API client
├── database/               # Database interaction modules
├── messaging/              # Messaging modules
│   └── imessage.py         # iMessage integration
├── utils/                  # Utility modules
│   ├── file_handling.py    # File operations
│   ├── logging_setup.py    # Logging configuration
│   └── token_tracking.py   # Token usage tracking
├── web/                    # Web-related modules
│   └── search.py           # Web search capabilities
├── config_EXAMPLE.py       # Example configuration file (rename to config.py)
├── main.py                 # Main application entry point
└── requirements.txt        # Python dependencies
```

## Troubleshooting

### Common Issues

1. **Configuration File Issues**
   - Make sure you've renamed `config_EXAMPLE.py` to `config.py`
   - Verify all required API keys are properly set in the config file
   - Check that there are no syntax errors in your config.py file

2. **Permission Denied for iMessage Database**
   - Ensure your Terminal/Python application has Full Disk Access permission
   - Restart the application after granting permission

3. **API Key Issues**
   - Verify your API keys are correctly set in config.py
   - Check for any spaces or extra characters in your API keys
   - Ensure your OpenAI API key has sufficient credits and permissions

4. **Missing Dependencies**
   - Ensure all external dependencies (Tesseract, ffmpeg) are installed
   - Verify Python dependencies are installed with `pip list`

5. **No Responses to Messages**
   - Check the logs for any errors
   - Verify the service is running and monitoring messages
   - Ensure your iMessage account is properly configured

6. **Image Generation Not Working**
   - Verify your OpenAI API key has access to DALL-E
   - Check that your prompt follows the required format (starts with generation keywords)
   - Ensure the prompt doesn't violate OpenAI's content policy

7. **Audio Transcription Issues**
   - Verify ffmpeg is properly installed
   - Check that the audio file format is supported
   - Ensure the audio file is not corrupted or too large

### Logs

Logs are stored in `~/Pictures/aibuddy/imessage_ai.log` by default. Check this file for detailed information about any issues.

## Token Usage Tracking

AI Buddy tracks token usage to help manage costs. Usage data is stored in `~/Pictures/aibuddy/token_usage.csv` and includes:
- Timestamp
- Model used
- Number of input tokens
- Number of output tokens
- Estimated cost

## Security and Privacy

AI Buddy processes messages locally on your machine. However, message content is sent to OpenAI and potentially Google (for web searches) for processing. No message data is permanently stored by these services, but please review their privacy policies for more information.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- OpenAI for providing the AI models
- Google for the Custom Search API
- All contributors and open source libraries used in this project 