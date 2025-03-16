# AI Buddy: Advanced iMessage AI Assistant

<img src="https://github.com/macmixing/aibuddy/blob/main/aibuddy.png" width="150" height="150" alt="AI Buddy Logo">

## Overview

AI Buddy is a powerful AI assistant for iMessage that integrates with your messaging app to provide intelligent responses, analyze images, process documents, search the web, and more. Built with a modular architecture, AI Buddy leverages OpenAI's advanced models to deliver a seamless AI experience directly in your iMessage conversations.

AI Buddy works with both iMessage and SMS, and will respond to messages sent to any phone number or email address you have configured in your iMessage settings.

> **⚠️ Important:** AI Buddy requires Full Disk Access permission for your Terminal or the application you use to run it. This is necessary to access the iMessage database.
> - Open System Preferences > Security & Privacy > Privacy
> - Select "Full Disk Access" from the sidebar
> - Click the "+" button and add your Terminal application
> - You must grant this permission before running the application

## Quick Start (4 Simple Steps)

```bash
# 1. Clone the repository and enter the directory
git clone https://github.com/macmixing/aibuddy.git && cd aibuddy

# 2. Set up Python environment
python -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt && brew install ffmpeg

# 4. Set up configuration and run
cp config_EXAMPLE.py config.py  # Then edit config.py with your API keys
python main.py
```

> **Note:** You'll need to edit `config.py` with your OpenAI API key and other settings before running.

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
- **OpenAI Assistant ID**: Required for the assistant functionality
- **Google API Key**: Required only for web search functionality
- **Google Custom Search Engine ID**: Required only for web search functionality

### External Dependencies
- **ffmpeg**: Required for audio processing
  ```
  brew install ffmpeg
  ```

## Configuration

After copying `config_EXAMPLE.py` to `config.py`, edit it to add your API keys:

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

## OpenAI Assistant API Setup

AI Buddy primarily uses OpenAI's Assistant API to process messages, which provides enhanced capabilities like maintaining conversation context and handling various content types. You'll need to create an Assistant in your OpenAI account and obtain its ID.

### Creating an OpenAI Assistant

1. Go to the [OpenAI Platform](https://platform.openai.com/assistants)
2. Sign in to your OpenAI account
3. Click "Create Assistant"
4. Configure your Assistant:
   - **Name**: Choose a name (e.g., "AI Buddy")
   - **Model**: Select "gpt-4o" or your preferred model
   - **Instructions**: Paste the system prompt (see example below)
   - **Capabilities**: Enable "Code Interpreter" and "Retrieval" as needed
5. Click "Save"
6. Copy the Assistant ID (found in the URL or in the Assistant details)
7. Paste this ID into your `config.py` file as the `ASSISTANT_ID` value

### Example Assistant Instructions

You can use the following as a starting point for your Assistant instructions:

```
You are AI Buddy, a helpful AI assistant integrated with iMessage.
Your goal is to provide helpful, accurate, and friendly responses.
You can analyze images, process documents, search the web, and engage in natural conversations.
Always be respectful, avoid harmful content, and prioritize user privacy and safety.
When appropriate, use emojis to make your responses more engaging.
If you don't know something, admit it rather than making up information.
```

Feel free to customize these instructions to match your preferred AI personality and capabilities.

For more information on creating and customizing Assistants, visit the [OpenAI Documentation](https://platform.openai.com/docs/assistants/overview).

## Configuration Options in Detail

The `config.py` file contains numerous settings that allow you to customize AI Buddy's behavior. Here are the key configuration options:

### API Keys and IDs
- **OPENAI_API_KEY**: Your OpenAI API key for accessing GPT models and other OpenAI services
- **ASSISTANT_ID**: Your OpenAI Assistant ID for using the Assistant API
- **GOOGLE_API_KEY**: Your Google API key for web search functionality
- **GOOGLE_CSE_ID**: Your Google Custom Search Engine ID for web search

### Model Settings
- **DEFAULT_MODEL**: The OpenAI model to use for general responses (e.g., "gpt-4o-mini", "gpt-4o", "gpt-4-turbo")
- **VISION_MODEL**: The model to use for image analysis (default: "gpt-4o")
- **EMBEDDING_MODEL**: The model to use for embeddings (default: "text-embedding-3-small")

### Message Handling
- **POLLING_INTERVAL**: How frequently to check for new messages (in seconds)
- **THREAD_MESSAGE_LIMIT**: Number of messages to keep in conversation context
- **MAX_TOKENS**: Maximum number of tokens for AI responses
- **TEMPERATURE**: Controls randomness in responses (0.0-2.0, lower is more deterministic)
- **ENABLE_TYPING_INDICATOR**: Whether to show typing indicators during processing

### Feature Toggles
- **WEB_SEARCH_ENABLED**: Enable/disable web search functionality
- **MAX_SEARCH_RESULTS**: Maximum number of search results to return
- **ENABLE_IMAGE_GENERATION**: Enable/disable image generation capability
- **ENABLE_AUDIO_TRANSCRIPTION**: Enable/disable audio transcription
- **ENABLE_DOCUMENT_ANALYSIS**: Enable/disable document analysis

### Rate Limiting
- **RATE_LIMIT_PERIOD**: Time period for rate limiting (in seconds)
- **MAX_REQUESTS_PER_PERIOD**: Maximum number of requests allowed in the rate limit period
- **RATE_LIMIT_ENABLED**: Enable/disable rate limiting

### File Paths
- **LOG_FILE_PATH**: Path to store log files
- **TOKEN_USAGE_FILE**: Path to store token usage data
- **CHAT_HISTORY_DIR**: Directory to store chat history

## System Prompts

AI Buddy uses system prompts to guide the AI's behavior in different contexts. These prompts are defined directly in the `config.py` file and can be customized to change how the AI responds.

### Available System Prompts

- **SYSTEM_PROMPT**: The main prompt that defines AI Buddy's personality and capabilities
- **SYSTEM_PROMPT_VISION**: Used specifically for image analysis
- **DOCUMENT_ANALYSIS_PROMPT**: Used for analyzing documents
- **WEB_SEARCH_PROMPT**: Used when performing web searches
- **PRODUCT_DETECTION_PROMPT**: Used to identify product mentions in conversations

### How to Modify System Prompts

To customize the system prompts:

1. Open your `config.py` file
2. Locate the prompt variables in the file
3. Edit the prompt text to change the AI's behavior
4. Restart AI Buddy for the changes to take effect

Example of customizing the main system prompt in your config.py:

```python
SYSTEM_PROMPT = """
You are AI Buddy, a helpful and friendly AI assistant.
Your personality traits:
- Helpful and informative
- Friendly and conversational
- Concise but thorough
- [Add your custom traits here]

Your capabilities include:
- Answering questions on a wide range of topics
- [Add or modify capabilities as needed]

When responding to users:
- [Add your custom instructions here]
"""
```

### Tips for Effective Prompt Engineering

- Be specific about the AI's personality and tone
- Clearly define what the AI should and shouldn't do
- Include examples of ideal responses if helpful
- Consider adding instructions for handling sensitive topics
- Test your prompts with various inputs to ensure they produce the desired behavior

## Full Disk Access Permission

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
   - Ensure ffmpeg is installed: `brew install ffmpeg`
   - Verify Python dependencies are installed with `pip list`

5. **No Responses to Messages**
   - Check the logs for any errors
   - Verify the service is running and monitoring messages
   - Ensure your iMessage account is properly configured

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

## Configuration 