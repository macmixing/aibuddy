# AI Buddy: Advanced iMessage AI Assistant

<img src="https://github.com/macmixing/aibuddy/blob/main/aibuddy.png" width="150" height="150" alt="AI Buddy Logo">

## Overview

AI Buddy enables ChatGPT to automatically respond to your iMessages and SMS. It works with your existing iMessage setup, using any phone numbers or email addresses you've already configured. No special integration needed - AI Buddy simply monitors and responds through your Mac's Messages app.

- Works with all your configured iMessage addresses and phone numbers
- Responds from the same address/number that received the message
- Adapts automatically when you change your iMessage settings
- Handles both iMessages and SMS messages seamlessly

> **💡 Cost-Saving Note:** By default, AI Buddy uses gpt-4o-mini for most interactions to optimize token costs while maintaining high-quality responses. You can adjust this in the [configuration](#configuration-options-in-detail) if you prefer to use more powerful models.

## Quick Start (5 Simple Steps)

> **⚠️ IMPORTANT - ENABLE FULL DISK ACCESS FIRST:** Terminal requires Full Disk Access permission to access the iMessage database. This must be done before running any commands below.

```bash
# 1. Clone the repository and enter the directory
git clone https://github.com/macmixing/aibuddy.git && cd aibuddy

# 2. Set up Python environment
python3 -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt && brew install ffmpeg

# 4. Set up configuration and run
cp config_EXAMPLE.py config.py  # Then edit config.py with your API keys

# 5. Run AI Buddy
python3 main.py
```

> **Important:** When running for the first time, you may see a popup message saying: **"Terminal.app" wants access to control "Messages.app". Allowing control will provide access to documents and data in "Messages.app", and to perform actions within that app.** Click "OK" to allow Terminal to control Messages, which is necessary for AI Buddy to send and receive messages. You'll only see this mesage once, when a response is being sent to you for the first time. 

> **Note:** You'll need to edit `config.py` with your OpenAI API key and other settings before running.

> AI Buddy will continue to run until you close the Terminal window or stop the process.

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
3. Click "Create"
4. Configure your Assistant:
   - **Name**: Choose a name (e.g., "AI Buddy")
   - **Model**: Select "gpt-4o-mini" to optimize for cost (recommended) or another model if you prefer
   - **Instructions**: Paste the system prompt (see example below)
   - **Capabilities**: Enable "Code Interpreter" and "Retrieval" as needed
5. Click "Save"
6. Copy the Assistant ID (found in the URL or in the Assistant details)
7. Paste this ID into your `config.py` file as the `ASSISTANT_ID` value

### Example Assistant Instructions

You can use the following as a starting point for your Assistant instructions (this is the recommended prompt from the top of `prompts_config.py`):

```
When crafting a response to a text message, aim to be smart, quick, and concise. Incorporate emojis for a fun touch while ensuring the information you provide is accurate. Focus on brevity, as the medium is a text message. If anyone asks who you are, you are AI Buddy developed by Dom Esposito and powered by OpenAI. 

# Steps  
 
1. **Understand the Message Context:** Quickly determine the main topic or question from the text message you received.
2. **Craft a Concise Response:** Formulate a short, accurate answer or comment. Use clear language that conveys your message effectively.
3. **Add Fun Elements:** Select appropriate emojis that align with the tone of the message. Aim to add a light-hearted, fun touch without overdoing it.
4. **Review:** Double-check for clarity and correctness before sending.

# Output Format

- A short, concise sentence or two.
- Include relevant emojis to add a fun element, but not always only sometimes.
- Ensure the core information is accurate.

# Examples

**Example 1:**
- **Input:** "Hey! Do you know what time the party starts tonight?"
- **Output:** "Hey! 🎉 It kicks off at 8 PM. Can't wait! "

**Example 2:**
- **Input:** "What's the weather look like for tomorrow?"
- **Output:** "Sunny and bright, perfect day for a picnic! "

# Notes 
 
- Tailor the tone to match the original text message's style.
- Use emojis relevant to the context to enhance rather than distract, but don't overuse them. Only every other message or so.
```

Feel free to customize these instructions to match your preferred AI personality and capabilities.

For more information on creating and customizing Assistants, visit the [OpenAI Documentation](https://platform.openai.com/docs/assistants/overview).

## Google Custom Search API Setup

AI Buddy uses Google's Custom Search API to provide web search capabilities. Follow these steps to set up your Google Custom Search Engine:

### Creating a Google API Key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Library"
4. Search for "Custom Search API" and enable it
5. Go to "APIs & Services" > "Credentials"
6. Click "Create Credentials" > "API Key"
7. Copy your new API key
8. Paste this key into your `config.py` file as the `GOOGLE_API_KEY` value

### Setting Up a Custom Search Engine

1. Go to the [Programmable Search Engine](https://programmablesearchengine.google.com/about/) page
2. Click "Get Started" or "Create a Programmable Search Engine"
3. Configure your search engine:
   - **Sites to search**: Choose "Search the entire web" for general queries
   - **Name**: Give your search engine a name (e.g., "AI Buddy Web Search")
4. Click "Create"
5. On the next page, click "Control Panel"
6. Find your "Search engine ID" (it will look something like "012345678901234567890:abcdefghijk")
7. Copy this ID
8. Paste this ID into your `config.py` file as the `GOOGLE_CSE_ID` value

> **Note:** The free tier of Google Custom Search API allows 100 search queries per day. If you need more, you'll need to set up billing in the Google Cloud Console.

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

> **Note:** By default, AI Buddy stores its files in `~/Pictures/aibuddy/`. This location is chosen because macOS has limitations with sending photos from other directories through iMessage. While the exact reason is unknown, using the Pictures folder ensures reliable image handling.

## System Prompts

AI Buddy uses system prompts to guide the AI's behavior in different contexts. These prompts are defined in the `prompts_config.py` file and can be customized to change how the AI responds.

> **Note:** The OpenAI Assistant also has its own system instructions that are set in the OpenAI backend. A recommended template for these instructions is included at the top of the `prompts_config.py` file as a comment.

### Available System Prompts

- **SEARCH_SUMMARIZATION_PROMPT**: Guides the AI in summarizing web search results in a conversational way
- **FOLLOW_UP_QUESTION_PROMPT**: Helps the AI interpret follow-up questions in the context of previous queries
- **Query Enhancement Prompts**: Functions that return prompts for enhancing search queries with context
- **WEB_SEARCH_DETERMINATION_PROMPT**: Determines if a message requires a web search

### How to Modify System Prompts

To customize the system prompts:

1. Open your `prompts_config.py` file
2. Locate the prompt variables or functions in the file
3. Edit the prompt text to change the AI's behavior
4. Restart AI Buddy for the changes to take effect

Example of customizing a prompt in your prompts_config.py:

```python
SEARCH_SUMMARIZATION_PROMPT = """You are a smart, quick, and concise assistant that provides informative summaries of web search results. 
Extract the most relevant information from the search results to answer the user's query, but present it in a 
fun, conversational way as if you're texting a friend.
...
"""
```

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