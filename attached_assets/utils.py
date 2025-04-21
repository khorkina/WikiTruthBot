from datetime import datetime

# Language name mapping
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

def get_language_name(lang_code):
    """Get language name from language code"""
    return LANGUAGE_NAMES.get(lang_code, lang_code)

def timestamp_to_date(timestamp):
    """Convert Unix timestamp to formatted date string"""
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        return 'Unknown date'
