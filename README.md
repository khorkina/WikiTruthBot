# WikiSearch Telegram Bot

A Python Telegram bot that allows users to search, view, translate, and download Wikipedia articles in multiple languages.

## Features

- **Multi-language Support**: Search Wikipedia in 10+ languages
- **Section Navigation**: Read articles section by section with next/previous navigation
- **Translation**: Translate entire articles or individual sections between languages
- **Document Export**: Download articles as Word documents
- **Article Sharing**: Get shareable Wikipedia links
- **Language Switching**: View articles in alternate languages when available

## Requirements

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Internet connection for Wikipedia API access

## Installation

### Local Installation

1. Clone this repository or download the source code
2. Install the required dependencies listed in `dependencies.txt`:

```bash
pip install aiohttp==3.7.4.post0 async-timeout==3.0.1 docx==0.2.4 python-docx==0.8.11 python-dotenv==1.0.0 requests==2.28.2 telepot==12.7
```

3. Create a `.env` file in the root directory with your Telegram bot token:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

### Quick Start Guide

1. Create a new bot with [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` to BotFather
   - Follow the prompts to set a name and username
   - Copy the API token provided

2. Set up the bot:
   - Add the token to your `.env` file
   - Run the bot using `python bot.py`
   - Start interacting with your bot on Telegram

3. If using Replit:
   - Set your token as a secret named `TELEGRAM_BOT_TOKEN`
   - Start the "telegram_bot" workflow
   - Your bot will remain active as long as the Replit is running

## Running the Bot

There are two ways to run the bot:

### 1. Direct Python Execution

Run the bot directly with Python:

```bash
python bot.py
```

### 2. Using the Workflow (on Replit)

Start the `telegram_bot` workflow:

```bash
# No direct command needed - use the Replit workflow UI
```

## Bot Usage

1. **Start**: Send `/start` to begin
2. **Language Selection**: Choose a language for searching
3. **Search**: Enter a search term to find articles
4. **Article Selection**: Choose an article from the search results
5. **Reading**: View article summaries and full content with section navigation
6. **Translation**: Translate articles or individual sections
7. **Downloads**: Save articles as Word documents
8. **Navigation**: Use inline buttons to navigate between functions

## Editing the Bot

### Project Structure

- `bot.py`: Entry point that imports from bot_new.py
- `bot_new.py`: Main bot implementation (handlers, UI, logic)
- `wiki_article.py`: Wikipedia article data handling
- `wiki_utils.py`: Utilities for Wikipedia API and translation
- `document_generator.py`: Word document creation
- `config.py`: Configuration settings and constants
- `telepot_patch.py`: Patch for Python 3.11+ compatibility

### Key Components

- **Handlers**: Process messages and callback queries
- **User States**: Track conversation states (`USER_STATE`)
- **User Data**: Store user preferences and article data (`USER_DATA`) 
- **Callbacks**: Handle button interactions with prefix-based routing
- **Section Navigation**: Split articles into manageable sections for better reading

## Troubleshooting

### Common Issues

- **Bot Not Responding**: Check that the token is correct and the bot is running
- **Translation Errors**: The translation service has rate limits, retry after a few minutes
- **API Timeouts**: Wikipedia API may occasionally time out, retry your search
- **Missing Sections**: Some Wikipedia articles may have unusual formatting

## License

This project is open source and available under the MIT License.

## Key Features In Detail

### Section Navigation
Articles are automatically split into logical sections based on headings. This provides:
- Better readability with manageable content chunks
- Previous/Next navigation between sections
- Direct access to section translation
- Clear indication of your current position in the article

### Individual Section Translation
Each section can be translated independently:
- Translate only the parts you're interested in
- Compare original and translated content side by side
- Choose from multiple target languages
- Faster processing than full article translation

### Document Download
Articles can be downloaded as Word documents:
- Preserves formatting and headings
- Includes article metadata
- Works for both original and translated articles
- Offline reading without Telegram

## Acknowledgments

- [Telepot](https://github.com/nickoala/telepot) for the Telegram bot framework
- [Wikipedia API](https://www.mediawiki.org/wiki/API:Main_page) for content access
- [Python-DOCX](https://python-docx.readthedocs.io/) for document generation