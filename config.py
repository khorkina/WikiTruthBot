import os
import logging

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Language name mapping (from utils.py)
LANGUAGE_NAMES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'zh': 'Chinese',
    'ja': 'Japanese',
    'ru': 'Russian',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'ko': 'Korean',
    'tr': 'Turkish',
    # Add more languages as needed
}

# Quick access language selection for search
POPULAR_LANGUAGES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French', 
    'de': 'German',
    'ru': 'Russian',
    'zh': 'Chinese',
    'ar': 'Arabic',
    'ja': 'Japanese'
}

# Default language if none selected
DEFAULT_LANGUAGE = 'en'

# User state constants
SELECTING_LANGUAGE = 1
SEARCHING = 2
VIEWING_ARTICLE = 3
SELECTING_ACTION = 4
READING_ARTICLE = 5
TRANSLATING = 6
VIEWING_TRANSLATION = 7

# Callback prefixes for inline keyboards
CB_LANGUAGE = "lang"
CB_ARTICLE = "article"
CB_ACTION = "action"
CB_VIEW_LANG = "view_lang"
CB_TRANSLATE = "translate"

# Global cache for storing user data between callbacks
user_data_cache = {}
