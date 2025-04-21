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

1. Clone this repository or download the source code
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your Telegram bot token:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

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

## Acknowledgments

- [Telepot](https://github.com/nickoala/telepot) for the Telegram bot framework
- [Wikipedia API](https://www.mediawiki.org/wiki/API:Main_page) for content access
- [Python-DOCX](https://python-docx.readthedocs.io/) for document generation