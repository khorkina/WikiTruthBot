"""
WikiSearch Telegram Bot

A Telegram bot for searching, viewing, translating, and downloading
Wikipedia articles in multiple languages.
"""

import os
import asyncio
import logging
import json
import re
import urllib.parse
from datetime import datetime
import tempfile
import collections.abc

# Monkey patch collections for Python 3.11+
if not hasattr(collections, 'Hashable'):
    collections.Hashable = collections.abc.Hashable

import telepot
import telepot.aio
from telepot.aio.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("No bot token provided. Set the TELEGRAM_BOT_TOKEN environment variable.")
    exit(1)

# Language settings
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
}

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

DEFAULT_LANGUAGE = 'en'

# Constants for callback query data prefixes
CB_LANGUAGE = "lang"
CB_ARTICLE = "article"
CB_ACTION = "action"
CB_VIEW_LANG = "view_lang"
CB_TRANSLATE = "translate"

# Global state storage
USER_STATE = {}  # Store user states by chat_id
USER_DATA = {}   # Store user data by chat_id

# Import wiki utils functions
from wiki_utils import (
    get_wikipedia_search_results,
    get_article_content,
    get_available_languages,
    get_article_in_language,
    translate_text,
    split_content_into_sections
)

from document_generator import create_document_from_article

# Utility functions
def get_language_name(lang_code):
    """Get language name from language code"""
    return LANGUAGE_NAMES.get(lang_code, lang_code.upper())

def search_wikipedia(query, language="en"):
    """Search Wikipedia for articles in the specified language"""
    return get_wikipedia_search_results(query, language)

def get_wikipedia_article(title, language="en"):
    """Get article content from Wikipedia"""
    # Get article content
    article = get_article_content(title, language)
    
    if not article:
        return None
    
    # Get available languages for this article
    available_languages = get_available_languages(title, language)
    
    # Add available languages to article data
    article['available_languages'] = available_languages
    
    return article

def get_article_in_other_language(title, target_lang):
    """Get the article in another available language"""
    # Get article in the target language
    article = get_article_in_language(title, target_lang)
    
    if not article:
        return None
    
    # Get available languages for this article
    available_languages = get_available_languages(title, target_lang)
    
    # Add available languages to article data
    article['available_languages'] = available_languages
    
    return article

def translate_article_content(article, from_lang, to_lang):
    """Translate article content from one language to another"""
    if not article:
        return None
    
    try:
        # Translate title, summary, and content
        translated_title = translate_text(article['title'], to_lang, from_lang)
        translated_summary = translate_text(article['summary'], to_lang, from_lang)
        translated_content = translate_text(article['content'], to_lang, from_lang)
        
        # Create translated article object
        translated_article = {
            'title': translated_title,
            'summary': translated_summary,
            'content': translated_content,
            'url': article['url'],  # Keep original URL
            'available_languages': article.get('available_languages', {})  # Keep original language options
        }
        
        return translated_article
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return None

def get_article_sharing_link(title, lang):
    """Generate a Wikipedia sharing link for the article"""
    try:
        # Create Wikipedia URL
        encoded_title = urllib.parse.quote(title.replace(' ', '_'))
        article_url = f"https://{lang}.wikipedia.org/wiki/{encoded_title}"
        
        return article_url
    except Exception as e:
        logger.error(f"Error generating article link: {str(e)}")
        return None

class WikiBot:
    def __init__(self, token):
        self.token = token
        self.bot = telepot.aio.Bot(token)
        self._answerer = telepot.aio.helper.Answerer(self.bot)
    
    async def handle_message(self, msg):
        """Handle incoming messages"""
        content_type, chat_type, chat_id = telepot.glance(msg)
        logger.info(f"Message from {chat_id}: {content_type}")
        
        # Initialize user state if needed
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = "START"
        
        # Initialize user data if needed
        if chat_id not in USER_DATA:
            USER_DATA[chat_id] = {"language": DEFAULT_LANGUAGE}
            
        # Handle different message types
        if content_type == 'text':
            text = msg['text']
            
            # Handle commands
            if text.startswith('/'):
                command = text.split('@')[0].lower()
                await self.handle_command(command, chat_id)
            else:
                # Handle regular messages based on user state
                await self.handle_text_message(text, chat_id)
        else:
            await self.bot.sendMessage(
                chat_id, 
                "I can only process text messages. Please send a text message."
            )
    
    async def handle_command(self, command, chat_id):
        """Handle bot commands"""
        if command == '/start':
            await self.handle_start(chat_id)
        elif command == '/help':
            await self.handle_help(chat_id)
        elif command == '/cancel':
            await self.handle_cancel(chat_id)
        else:
            await self.bot.sendMessage(
                chat_id,
                "Unknown command. Try /start, /help, or /cancel."
            )
    
    async def handle_start(self, chat_id):
        """Handle /start command"""
        # Reset user state
        USER_STATE[chat_id] = "SELECTING_LANGUAGE"
        
        # Reset user data
        USER_DATA[chat_id] = {"language": DEFAULT_LANGUAGE}
        
        # Show language selection keyboard
        keyboard = []
        row = []
        
        for i, (lang_code, lang_name) in enumerate(POPULAR_LANGUAGES.items()):
            button = InlineKeyboardButton(
                text=f"{lang_name} ({lang_code})", 
                callback_data=f"{CB_LANGUAGE}:{lang_code}"
            )
            row.append(button)
            
            # Create rows with 2 buttons each
            if len(row) == 2 or i == len(POPULAR_LANGUAGES) - 1:
                keyboard.append(row)
                row = []
        
        # Send welcome message with language selection
        await self.bot.sendMessage(
            chat_id,
            "🌍 Welcome to WikiSearch Bot!\n\n"
            "I can help you search, read, and translate Wikipedia articles in multiple languages.\n\n"
            "Please select a language for your search:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    
    async def handle_help(self, chat_id):
        """Handle /help command"""
        help_text = (
            "📖 *WikiSearch Bot Help*\n\n"
            "*Commands:*\n"
            "/start - Start a new search\n"
            "/help - Show this help message\n"
            "/cancel - Cancel current operation\n\n"
            "*How to use:*\n"
            "1. Select a language for search\n"
            "2. Enter your search term\n"
            "3. Select an article from search results\n"
            "4. Choose what you want to do with the article\n\n"
            "You can view full articles, see them in other languages, translate them, "
            "or download them as documents."
        )
        
        await self.bot.sendMessage(
            chat_id,
            help_text,
            parse_mode="Markdown"
        )
    
    async def handle_cancel(self, chat_id):
        """Handle /cancel command"""
        USER_STATE[chat_id] = "START"
        
        await self.bot.sendMessage(
            chat_id,
            "Operation cancelled. Type /start to begin a new search."
        )
    
    async def handle_text_message(self, text, chat_id):
        """Handle non-command text messages based on user state"""
        state = USER_STATE.get(chat_id, "START")
        
        if state == "START":
            # If no active session, suggest starting
            await self.bot.sendMessage(
                chat_id,
                "Please use /start to begin searching for Wikipedia articles."
            )
        
        elif state == "SELECTING_LANGUAGE":
            # Should not reach here as this is handled by callback
            await self.bot.sendMessage(
                chat_id,
                "Please select a language from the options."
            )
        
        elif state == "SEARCHING":
            # Handle search query
            await self.handle_search(text, chat_id)
    
    async def handle_search(self, query, chat_id):
        """Process a search query"""
        # Store the query
        USER_DATA[chat_id]['search_query'] = query
        language = USER_DATA[chat_id].get('language', DEFAULT_LANGUAGE)
        
        # Show searching message
        wait_msg = await self.bot.sendMessage(
            chat_id,
            f"Searching for '{query}' in {get_language_name(language)}..."
        )
        
        # Search Wikipedia
        search_results = search_wikipedia(query, language)
        
        # Update state
        USER_STATE[chat_id] = "VIEWING_RESULTS"
        
        # Process search results
        if search_results:
            # Create keyboard with search results
            keyboard = []
            for title in search_results[:8]:  # Limit to 8 results
                keyboard.append([
                    InlineKeyboardButton(
                        text=title, 
                        callback_data=f"{CB_ARTICLE}:{title}"
                    )
                ])
            
            # Add "New Search" button
            keyboard.append([
                InlineKeyboardButton(
                    text="New Search", 
                    callback_data="new_search"
                )
            ])
            
            # Show results
            await self.bot.editMessageText(
                (chat_id, wait_msg['message_id']),
                f"Search results for '{query}' in {get_language_name(language)}:\n"
                f"Please select an article to view:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        else:
            # No results found
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="Try Different Search", 
                        callback_data="try_again"
                    ), 
                    InlineKeyboardButton(
                        text="Change Language", 
                        callback_data="new_search"
                    )
                ]
            ]
            
            await self.bot.editMessageText(
                (chat_id, wait_msg['message_id']),
                f"No results found for '{query}' in {get_language_name(language)}.\n\n"
                f"Would you like to try a different search or change the language?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
    
    async def display_article_section(self, chat_id, message_id, article, section_index):
        """Display a specific section of an article with navigation buttons"""
        user_data = USER_DATA[chat_id]
        sections = user_data.get('article_sections', [])
        
        if not sections or section_index >= len(sections) or section_index < 0:
            # Invalid section index, go back to article
            await self.handle_back_to_article(chat_id, message_id)
            return
        
        # Get the current section
        section = sections[section_index]
        
        # Create section navigation buttons
        keyboard = []
        nav_row = []
        
        # Previous section button (if not first section)
        if section_index > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Previous", 
                callback_data=f"section:{section_index-1}"
            ))
        
        # Next section button (if not last section)
        if section_index < len(sections) - 1:
            nav_row.append(InlineKeyboardButton(
                text="Next ▶️", 
                callback_data=f"section:{section_index+1}"
            ))
            
        if nav_row:
            keyboard.append(nav_row)
            
        # Translate section button
        language = user_data.get('language', DEFAULT_LANGUAGE)
        keyboard.append([
            InlineKeyboardButton(
                text="🔄 Translate Section", 
                callback_data=f"translate_section:{section_index}"
            )
        ])
        
        # Back button
        keyboard.append([
            InlineKeyboardButton(
                text="Back to Article", 
                callback_data="back_to_article"
            )
        ])
        
        # Format section content
        if section['title']:
            section_title = f"*{section['title']}*\n\n"
        else:
            if section_index == 0:
                section_title = f"*{article['title']}*\n\n"
            else:
                section_title = ""
                
        section_content = section['content']
                
        # Format the entire message
        message = (
            f"{section_title}{section_content}\n\n"
            f"_Section {section_index + 1} of {len(sections)}_"
        )
        
        # Make sure we don't exceed message limits
        if len(message) > 4000:
            message = message[:3997] + "..."
            
        try:
            # Try to edit the existing message
            await self.bot.editMessageText(
                (chat_id, message_id),
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except Exception as e:
            # If there's an error (e.g., message too old), send a new message
            logger.error(f"Error editing message: {str(e)}")
            await self.bot.sendMessage(
                chat_id,
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )

    async def handle_callback_query(self, msg):
        """Handle callback queries from inline keyboards"""
        query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        logger.info(f"Callback query from {chat_id}: {query_data}")
        
        # Initialize user state & data if needed
        if chat_id not in USER_STATE:
            USER_STATE[chat_id] = "START"
        if chat_id not in USER_DATA:
            USER_DATA[chat_id] = {"language": DEFAULT_LANGUAGE}
        
        # Always acknowledge the callback to stop loading indicator
        await self.bot.answerCallbackQuery(query_id)
        
        # Handle language selection
        if query_data.startswith(f"{CB_LANGUAGE}:"):
            await self.handle_language_selection(chat_id, message_id, query_data)
        
        # Handle article selection
        elif query_data.startswith(f"{CB_ARTICLE}:"):
            await self.handle_article_selection(chat_id, message_id, query_data)
        
        # Handle action selection
        elif query_data.startswith(f"{CB_ACTION}:"):
            await self.handle_action_selection(chat_id, message_id, query_data)
        
        # Handle language view selection
        elif query_data.startswith(f"{CB_VIEW_LANG}:"):
            await self.handle_view_language_selection(chat_id, message_id, query_data)
        
        # Handle translation language selection
        elif query_data.startswith(f"{CB_TRANSLATE}:"):
            await self.handle_translate_selection(chat_id, message_id, query_data)
            
        # Handle article section navigation
        elif query_data.startswith("section:"):
            section_index = int(query_data.split(":", 1)[1])
            article = USER_DATA[chat_id].get('current_article')
            if article:
                await self.display_article_section(chat_id, message_id, article, section_index)
                
        # Handle section translation
        elif query_data.startswith("translate_section:"):
            await self.handle_translate_section(chat_id, message_id, query_data)
        
        # Handle navigation actions
        elif query_data == "new_search":
            await self.handle_new_search(chat_id, message_id)
        
        elif query_data == "try_again":
            await self.handle_try_again(chat_id, message_id)
        
        elif query_data == "back_to_article":
            await self.handle_back_to_article(chat_id, message_id)
        
        elif query_data == "read_translation":
            await self.handle_read_translation(chat_id, message_id)
        
        elif query_data == "download_translation":
            await self.handle_download_translation(chat_id, message_id)
        
        elif query_data == "back_to_translation":
            await self.handle_back_to_translation(chat_id, message_id)
    
    async def handle_language_selection(self, chat_id, message_id, query_data):
        """Process language selection"""
        # Extract language code
        lang_code = query_data.split(':', 1)[1]
        
        # Update user data with selected language
        USER_DATA[chat_id]['language'] = lang_code
        
        # Update state
        USER_STATE[chat_id] = "SEARCHING"
        
        # Prompt for search term
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Selected language: {get_language_name(lang_code)}\n\n"
            f"Please enter a search term to find Wikipedia articles:"
        )
    
    async def handle_article_selection(self, chat_id, message_id, query_data):
        """Process article selection"""
        # Extract article title
        title = query_data.split(':', 1)[1]
        
        # Get user data
        user_data = USER_DATA[chat_id]
        language = user_data.get('language', DEFAULT_LANGUAGE)
        
        # Fetch article content
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Loading article '{title}'..."
        )
        
        article = get_wikipedia_article(title, language)
        
        if not article:
            # Article not found
            keyboard = [[
                InlineKeyboardButton(text="Try again", callback_data="try_again"),
                InlineKeyboardButton(text="New search", callback_data="new_search")
            ]]
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Sorry, could not retrieve the article '{title}'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            return
        
        # Store article data
        USER_DATA[chat_id]['current_article'] = article
        
        # Update state
        USER_STATE[chat_id] = "VIEWING_ARTICLE"
        
        # Get available languages for the article
        available_languages = article.get('available_languages', {})
        
        # Create keyboard for article actions
        keyboard = []
        
        # Read full article button
        keyboard.append([
            InlineKeyboardButton(
                text="Read Full Article", 
                callback_data=f"{CB_ACTION}:read"
            )
        ])
        
        # Other language versions button (if available)
        if available_languages and len(available_languages) > 1:
            keyboard.append([
                InlineKeyboardButton(
                    text="View in Another Language", 
                    callback_data=f"{CB_ACTION}:languages"
                )
            ])
        
        # Translate article button
        keyboard.append([
            InlineKeyboardButton(
                text="Translate Article", 
                callback_data=f"{CB_ACTION}:translate"
            )
        ])
        
        # Download article button
        keyboard.append([
            InlineKeyboardButton(
                text="Download as Document", 
                callback_data=f"{CB_ACTION}:download"
            )
        ])
        
        # Copy article link button
        keyboard.append([
            InlineKeyboardButton(
                text="Copy Wikipedia Link", 
                callback_data=f"{CB_ACTION}:link"
            )
        ])
        
        # New search button
        keyboard.append([
            InlineKeyboardButton(
                text="New Search", 
                callback_data="new_search"
            )
        ])
        
        # Format message with article summary (limit to ~1000 chars)
        summary = article['summary']
        if len(summary) > 1000:
            summary = summary[:997] + "..."
        
        message = (
            f"📚 *{article['title']}*\n\n"
            f"{summary}\n\n"
            f"_Language: {get_language_name(language)}_"
        )
        
        await self.bot.editMessageText(
            (chat_id, message_id),
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    
    async def handle_action_selection(self, chat_id, message_id, query_data):
        """Process action selection for an article"""
        # Extract action
        action = query_data.split(':', 1)[1]
        
        # Get user data
        user_data = USER_DATA[chat_id]
        article = user_data.get('current_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Article data not found. Please start a new search with /start."
            )
            return
        
        # Process the selected action
        if action == "read":
            # Update state
            USER_STATE[chat_id] = "READING_ARTICLE"
            
            # Split content into sections
            sections = split_content_into_sections(article['content'])
            
            # Store sections in user data
            user_data['article_sections'] = sections
            user_data['current_section'] = 0
            
            # Display the first section
            await self.display_article_section(chat_id, message_id, article, 0)
        
        elif action == "languages":
            # Show available languages
            available_languages = article.get('available_languages', {})
            
            if not available_languages:
                await self.bot.editMessageText(
                    (chat_id, message_id),
                    f"This article is only available in {get_language_name(user_data.get('language', DEFAULT_LANGUAGE))}.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="Back to Article", 
                            callback_data="back_to_article"
                        )
                    ]])
                )
                return
            
            # Create keyboard with available languages
            keyboard = []
            for lang_code, lang_title in available_languages.items():
                if lang_code != user_data.get('language', DEFAULT_LANGUAGE):  # Skip current language
                    keyboard.append([
                        InlineKeyboardButton(
                            text=f"{get_language_name(lang_code)} - {lang_title}", 
                            callback_data=f"{CB_VIEW_LANG}:{lang_code}"
                        )
                    ])
            
            # Add back button
            keyboard.append([
                InlineKeyboardButton(
                    text="Back to Article", 
                    callback_data="back_to_article"
                )
            ])
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"'{article['title']}' is available in these languages:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        
        elif action == "translate":
            # Show translation options
            language = user_data.get('language', DEFAULT_LANGUAGE)
            
            # Translation languages to show
            translation_languages = [
                "en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ko", "ar"
            ]
            
            # Remove current language from options
            if language in translation_languages:
                translation_languages.remove(language)
            
            # Create keyboard with translation options
            keyboard = []
            row = []
            
            for i, lang_code in enumerate(translation_languages):
                button = InlineKeyboardButton(
                    text=get_language_name(lang_code), 
                    callback_data=f"{CB_TRANSLATE}:{lang_code}"
                )
                row.append(button)
                
                # 2 buttons per row
                if len(row) == 2 or i == len(translation_languages) - 1:
                    keyboard.append(row)
                    row = []
            
            # Add back button
            keyboard.append([
                InlineKeyboardButton(
                    text="Back to Article", 
                    callback_data="back_to_article"
                )
            ])
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Translate '{article['title']}' to:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        
        elif action == "download":
            # Generate and send document
            language = user_data.get('language', DEFAULT_LANGUAGE)
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Generating document for '{article['title']}'..."
            )
            
            try:
                doc_path = create_document_from_article(article, language)
                
                if not doc_path or not os.path.exists(doc_path):
                    await self.bot.editMessageText(
                        (chat_id, message_id),
                        "Sorry, there was an error generating the document.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(
                                text="Back to Article", 
                                callback_data="back_to_article"
                            )
                        ]])
                    )
                    return
                
                # Send the document
                with open(doc_path, 'rb') as doc_file:
                    await self.bot.sendDocument(
                        chat_id,
                        document=doc_file
                    )
                
                # Clean up
                os.remove(doc_path)
                
                # Show success message
                await self.bot.sendMessage(
                    chat_id,
                    "Document generated successfully.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="Back to Article", 
                            callback_data="back_to_article"
                        )
                    ]])
                )
                
            except Exception as e:
                logger.error(f"Error generating document: {str(e)}")
                
                await self.bot.editMessageText(
                    (chat_id, message_id),
                    f"Error generating document: {str(e)}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="Back to Article", 
                            callback_data="back_to_article"
                        )
                    ]])
                )
        
        elif action == "link":
            # Get Wikipedia link
            language = user_data.get('language', DEFAULT_LANGUAGE)
            article_url = get_article_sharing_link(article['title'], language)
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Wikipedia link for '{article['title']}':\n{article_url}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
    
    async def handle_view_language_selection(self, chat_id, message_id, query_data):
        """Process viewing article in another language"""
        # Extract target language
        target_lang = query_data.split(':', 1)[1]
        
        # Get user data
        user_data = USER_DATA[chat_id]
        article = user_data.get('current_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Article data not found. Please start a new search with /start."
            )
            return
        
        # Get source language
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        
        # Show loading message
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Loading article in {get_language_name(target_lang)}..."
        )
        
        # Check if language is available
        available_languages = article.get('available_languages', {})
        
        if target_lang not in available_languages:
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"This article is not available in {get_language_name(target_lang)}.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        # Get article in target language
        target_title = available_languages[target_lang]
        target_article = get_article_in_other_language(target_title, target_lang)
        
        if not target_article:
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Failed to retrieve article in {get_language_name(target_lang)}.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        # Update user data
        user_data['current_article'] = target_article
        user_data['language'] = target_lang
        
        # Create keyboard for article actions
        keyboard = []
        
        # Read full article button
        keyboard.append([
            InlineKeyboardButton(
                text="Read Full Article", 
                callback_data=f"{CB_ACTION}:read"
            )
        ])
        
        # Other language versions button
        if available_languages and len(available_languages) > 1:
            keyboard.append([
                InlineKeyboardButton(
                    text="View in Another Language", 
                    callback_data=f"{CB_ACTION}:languages"
                )
            ])
        
        # Translate article button
        keyboard.append([
            InlineKeyboardButton(
                text="Translate Article", 
                callback_data=f"{CB_ACTION}:translate"
            )
        ])
        
        # Download article button
        keyboard.append([
            InlineKeyboardButton(
                text="Download as Document", 
                callback_data=f"{CB_ACTION}:download"
            )
        ])
        
        # Copy article link button
        keyboard.append([
            InlineKeyboardButton(
                text="Copy Wikipedia Link", 
                callback_data=f"{CB_ACTION}:link"
            )
        ])
        
        # New search button
        keyboard.append([
            InlineKeyboardButton(
                text="New Search", 
                callback_data="new_search"
            )
        ])
        
        # Format message with article summary
        summary = target_article['summary']
        if len(summary) > 1000:
            summary = summary[:997] + "..."
            
        message = (
            f"📚 *{target_article['title']}*\n\n"
            f"{summary}\n\n"
            f"_Language: {get_language_name(target_lang)}_"
        )
        
        await self.bot.editMessageText(
            (chat_id, message_id),
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    
    async def handle_translate_selection(self, chat_id, message_id, query_data):
        """Process translating article to selected language"""
        # Extract target language
        target_lang = query_data.split(':', 1)[1]
        
        # Get user data
        user_data = USER_DATA[chat_id]
        article = user_data.get('current_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Article data not found. Please start a new search with /start."
            )
            return
        
        # Get source language
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        
        # Update state
        USER_STATE[chat_id] = "TRANSLATING"
        
        # Show loading message
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Translating article from {get_language_name(source_lang)} to {get_language_name(target_lang)}...\n\n"
            f"This may take a moment."
        )
        
        # Translate the article
        try:
            translated_article = translate_article_content(article, source_lang, target_lang)
            
            if not translated_article:
                await self.bot.editMessageText(
                    (chat_id, message_id),
                    f"Failed to translate the article to {get_language_name(target_lang)}.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="Back to Article", 
                            callback_data="back_to_article"
                        )
                    ]])
                )
                return
            
            # Store the translated article
            user_data['translated_article'] = translated_article
            user_data['translation_language'] = target_lang
            
            # Update state
            USER_STATE[chat_id] = "VIEWING_TRANSLATION"
            
            # Format message with translated summary
            summary = translated_article['summary']
            if len(summary) > 1000:
                summary = summary[:997] + "..."
                
            # Create keyboard for translation actions
            keyboard = [
                [InlineKeyboardButton(
                    text="Read Full Translation", 
                    callback_data="read_translation"
                )],
                [InlineKeyboardButton(
                    text="Download Translation", 
                    callback_data="download_translation"
                )],
                [InlineKeyboardButton(
                    text="Back to Original Article", 
                    callback_data="back_to_article"
                )],
                [InlineKeyboardButton(
                    text="New Search", 
                    callback_data="new_search"
                )]
            ]
            
            message = (
                f"📚 *{translated_article['title']}*\n\n"
                f"Translated from {get_language_name(source_lang)} to {get_language_name(target_lang)}:\n\n"
                f"{summary}\n\n"
                f"_Note: This is a machine translation and may not be perfect._"
            )
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Translation error: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
    
    async def handle_new_search(self, chat_id, message_id):
        """Process new search request"""
        # Update state
        USER_STATE[chat_id] = "SELECTING_LANGUAGE"
        
        # Create keyboard with language options
        keyboard = []
        row = []
        
        for i, (lang_code, lang_name) in enumerate(POPULAR_LANGUAGES.items()):
            button = InlineKeyboardButton(
                text=f"{lang_name} ({lang_code})", 
                callback_data=f"{CB_LANGUAGE}:{lang_code}"
            )
            row.append(button)
            
            # Create rows with 2 buttons each
            if len(row) == 2 or i == len(POPULAR_LANGUAGES) - 1:
                keyboard.append(row)
                row = []
        
        # Update the message
        try:
            await self.bot.editMessageText(
                (chat_id, message_id),
                "🌍 Start a new search!\n\n"
                "Please select a language for your search:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except telepot.exception.TelegramError:
            # If we can't edit the message (e.g., too old), send a new one
            await self.bot.sendMessage(
                chat_id,
                "🌍 Start a new search!\n\n"
                "Please select a language for your search:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
    
    async def handle_try_again(self, chat_id, message_id):
        """Process try again request"""
        # Get current language
        language = USER_DATA[chat_id].get('language', DEFAULT_LANGUAGE)
        
        # Update state
        USER_STATE[chat_id] = "SEARCHING"
        
        # Prompt for a new search
        try:
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Please enter a new search query (language: {get_language_name(language)}):"
            )
        except telepot.exception.TelegramError:
            # If we can't edit the message, send a new one
            await self.bot.sendMessage(
                chat_id,
                f"Please enter a new search query (language: {get_language_name(language)}):"
            )
    
    async def handle_back_to_article(self, chat_id, message_id):
        """Process back to article request"""
        # Get user data
        user_data = USER_DATA[chat_id]
        article = user_data.get('current_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Article data not found. Please start a new search with /start."
            )
            return
        
        # Update state
        USER_STATE[chat_id] = "VIEWING_ARTICLE"
        
        # Get language
        language = user_data.get('language', DEFAULT_LANGUAGE)
        
        # Create keyboard for article actions
        keyboard = []
        
        # Get available languages
        available_languages = article.get('available_languages', {})
        
        # Read full article button
        keyboard.append([
            InlineKeyboardButton(
                text="Read Full Article", 
                callback_data=f"{CB_ACTION}:read"
            )
        ])
        
        # Other language versions button
        if available_languages and len(available_languages) > 1:
            keyboard.append([
                InlineKeyboardButton(
                    text="View in Another Language", 
                    callback_data=f"{CB_ACTION}:languages"
                )
            ])
        
        # Translate article button
        keyboard.append([
            InlineKeyboardButton(
                text="Translate Article", 
                callback_data=f"{CB_ACTION}:translate"
            )
        ])
        
        # Download article button
        keyboard.append([
            InlineKeyboardButton(
                text="Download as Document", 
                callback_data=f"{CB_ACTION}:download"
            )
        ])
        
        # Copy article link button
        keyboard.append([
            InlineKeyboardButton(
                text="Copy Wikipedia Link", 
                callback_data=f"{CB_ACTION}:link"
            )
        ])
        
        # New search button
        keyboard.append([
            InlineKeyboardButton(
                text="New Search", 
                callback_data="new_search"
            )
        ])
        
        # Format message with article summary
        summary = article['summary']
        if len(summary) > 1000:
            summary = summary[:997] + "..."
            
        message = (
            f"📚 *{article['title']}*\n\n"
            f"{summary}\n\n"
            f"_Language: {get_language_name(language)}_"
        )
        
        try:
            await self.bot.editMessageText(
                (chat_id, message_id),
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except telepot.exception.TelegramError:
            # If we can't edit the message, send a new one
            await self.bot.sendMessage(
                chat_id,
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
    
    async def handle_read_translation(self, chat_id, message_id):
        """Process read translation request"""
        # Get user data
        user_data = USER_DATA[chat_id]
        translated_article = user_data.get('translated_article')
        
        if not translated_article:
            await self.bot.sendMessage(
                chat_id,
                "Translation not found. Please translate the article again.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        # Get language info
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        target_lang = user_data.get('translation_language', "en")
        
        # Send the full translated content
        content = translated_article['content']
        
        # Split into chunks if too long (Telegram has a 4096 char limit)
        chunks = []
        max_length = 3000  # Leave room for formatting
        
        while content:
            if len(content) <= max_length:
                chunks.append(content)
                break
            
            # Find a good breaking point
            split_point = content[:max_length].rfind('\n\n')
            if split_point == -1:
                split_point = content[:max_length].rfind('\n')
            if split_point == -1:
                split_point = content[:max_length].rfind('. ')
            if split_point == -1:
                split_point = max_length
            
            chunks.append(content[:split_point+1])
            content = content[split_point+1:]
        
        # Send each chunk
        for i, chunk in enumerate(chunks):
            if i == 0:
                await self.bot.sendMessage(
                    chat_id,
                    f"*{translated_article['title']}*\n\n"
                    f"Translated from {get_language_name(source_lang)} to {get_language_name(target_lang)}\n\n"
                    f"{chunk}",
                    parse_mode="Markdown"
                )
            else:
                await self.bot.sendMessage(
                    chat_id,
                    chunk,
                    parse_mode="Markdown"
                )
        
        # Add back button
        await self.bot.sendMessage(
            chat_id,
            "End of translated article.\n\n"
            "_Note: This is a machine translation and may not be perfect._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="Back to Translation", 
                    callback_data="back_to_translation"
                )
            ]])
        )
    
    async def handle_download_translation(self, chat_id, message_id):
        """Process download translation request"""
        # Get user data
        user_data = USER_DATA[chat_id]
        translated_article = user_data.get('translated_article')
        
        if not translated_article:
            await self.bot.editMessageText(
                (chat_id, message_id),
                "Translation not found. Please translate the article again.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        # Get language info
        target_lang = user_data.get('translation_language', "en")
        
        # Show loading message
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Generating document for translated article..."
        )
        
        try:
            # Create document
            doc_path = create_document_from_article(translated_article, target_lang)
            
            if not doc_path or not os.path.exists(doc_path):
                await self.bot.editMessageText(
                    (chat_id, message_id),
                    "Sorry, there was an error generating the document.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="Back to Translation", 
                            callback_data="back_to_translation"
                        )
                    ]])
                )
                return
            
            # Send the document
            with open(doc_path, 'rb') as doc_file:
                await self.bot.sendDocument(
                    chat_id,
                    document=doc_file
                )
            
            # Clean up
            os.remove(doc_path)
            
            # Show success message
            await self.bot.sendMessage(
                chat_id,
                "Translation document generated successfully.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Translation", 
                        callback_data="back_to_translation"
                    )
                ]])
            )
            
        except Exception as e:
            logger.error(f"Error generating document: {str(e)}")
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Error generating document: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Translation", 
                        callback_data="back_to_translation"
                    )
                ]])
            )
    
    async def handle_translate_section(self, chat_id, message_id, query_data):
        """Handle translating a specific section of an article"""
        # Extract section index
        section_index = int(query_data.split(':', 1)[1])
        
        # Get user data
        user_data = USER_DATA[chat_id]
        article = user_data.get('current_article')
        sections = user_data.get('article_sections', [])
        
        if not article or not sections or section_index >= len(sections):
            await self.bot.sendMessage(
                chat_id,
                "Section data not found. Please start a new search with /start."
            )
            return
        
        # Get source language
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        
        # Show translation language options
        keyboard = []
        translation_languages = [
            "en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ko", "ar"
        ]
        
        # Remove current language from options
        if source_lang in translation_languages:
            translation_languages.remove(source_lang)
        
        # Create keyboard with translation options
        row = []
        for i, lang_code in enumerate(translation_languages):
            button = InlineKeyboardButton(
                text=get_language_name(lang_code), 
                callback_data=f"section_translate:{section_index}:{lang_code}"
            )
            row.append(button)
            
            # 2 buttons per row
            if len(row) == 2 or i == len(translation_languages) - 1:
                keyboard.append(row)
                row = []
        
        # Add back button
        keyboard.append([
            InlineKeyboardButton(
                text="Back to Section", 
                callback_data=f"section:{section_index}"
            )
        ])
        
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Translate this section to:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    async def handle_section_translate(self, chat_id, message_id, query_data):
        """Process section translation to the selected language"""
        # Extract data from callback query
        parts = query_data.split(':')
        section_index = int(parts[1])
        target_lang = parts[2]
        
        # Get user data
        user_data = USER_DATA[chat_id]
        article = user_data.get('current_article')
        sections = user_data.get('article_sections', [])
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        
        if not article or not sections or section_index >= len(sections):
            await self.bot.sendMessage(
                chat_id,
                "Section data not found. Please start a new search with /start."
            )
            return
        
        # Get the section to translate
        section = sections[section_index]
        
        # Show loading message
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Translating section from {get_language_name(source_lang)} to {get_language_name(target_lang)}..."
        )
        
        try:
            # Translate section title if it exists
            title = section['title']
            if title:
                translated_title = translate_text(title, target_lang, source_lang)
            else:
                if section_index == 0:
                    translated_title = translate_text(article['title'], target_lang, source_lang)
                else:
                    translated_title = ""
            
            # Translate section content
            translated_content = translate_text(section['content'], target_lang, source_lang)
            
            # Create keyboard with back buttons
            keyboard = [
                [InlineKeyboardButton(
                    text="Back to Original Section", 
                    callback_data=f"section:{section_index}"
                )],
                [InlineKeyboardButton(
                    text="Back to Article", 
                    callback_data="back_to_article"
                )]
            ]
            
            # Format the translated section
            if translated_title:
                message = f"*{translated_title}*\n\n{translated_content}\n\n"
            else:
                message = f"{translated_content}\n\n"
                
            message += (
                f"_Translated from {get_language_name(source_lang)} to {get_language_name(target_lang)}_\n"
                f"_Section {section_index + 1} of {len(sections)}_"
            )
            
            # Make sure we don't exceed message limits
            if len(message) > 4000:
                message = message[:3997] + "..."
                
            await self.bot.editMessageText(
                (chat_id, message_id),
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            
        except Exception as e:
            logger.error(f"Section translation error: {str(e)}")
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Translation error: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Section", 
                        callback_data=f"section:{section_index}"
                    )
                ]])
            )
            
    async def display_translated_section(self, chat_id, message_id, article, section_index):
        """Display a specific section of a translated article with navigation buttons"""
        user_data = USER_DATA[chat_id]
        sections = user_data.get('translated_sections', [])
        
        if not sections or section_index >= len(sections) or section_index < 0:
            # Invalid section index, go back to translation
            await self.handle_back_to_translation(chat_id, message_id)
            return
        
        # Get the current section
        section = sections[section_index]
        
        # Create section navigation buttons
        keyboard = []
        nav_row = []
        
        # Previous section button (if not first section)
        if section_index > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Previous", 
                callback_data=f"trans_section:{section_index-1}"
            ))
        
        # Next section button (if not last section)
        if section_index < len(sections) - 1:
            nav_row.append(InlineKeyboardButton(
                text="Next ▶️", 
                callback_data=f"trans_section:{section_index+1}"
            ))
            
        if nav_row:
            keyboard.append(nav_row)
            
        # Back button
        keyboard.append([
            InlineKeyboardButton(
                text="Back to Translation", 
                callback_data="back_to_translation"
            )
        ])
        
        # Format section content
        if section['title']:
            section_title = f"*{section['title']}*\n\n"
        else:
            if section_index == 0:
                section_title = f"*{article['title']}*\n\n"
            else:
                section_title = ""
                
        section_content = section['content']
                
        # Format the entire message
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        target_lang = user_data.get('translation_language', 'en')
        
        message = (
            f"{section_title}{section_content}\n\n"
            f"_Translated from {get_language_name(source_lang)} to {get_language_name(target_lang)}_\n"
            f"_Section {section_index + 1} of {len(sections)}_"
        )
        
        # Make sure we don't exceed message limits
        if len(message) > 4000:
            message = message[:3997] + "..."
            
        try:
            # Try to edit the existing message
            await self.bot.editMessageText(
                (chat_id, message_id),
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except Exception as e:
            # If there's an error (e.g., message too old), send a new message
            logger.error(f"Error editing message: {str(e)}")
            await self.bot.sendMessage(
                chat_id,
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            
    async def handle_back_to_translation(self, chat_id, message_id):
        """Process back to translation request"""
        # Get user data
        user_data = USER_DATA[chat_id]
        translated_article = user_data.get('translated_article')
        
        if not translated_article:
            await self.bot.sendMessage(
                chat_id,
                "Translation not found. Please translate the article again.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        # Update state
        USER_STATE[chat_id] = "VIEWING_TRANSLATION"
        
        # Get language info
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        target_lang = user_data.get('translation_language', "en")
        
        # Format message with translated summary
        summary = translated_article['summary']
        if len(summary) > 1000:
            summary = summary[:997] + "..."
            
        # Create keyboard for translation actions
        keyboard = [
            [InlineKeyboardButton(
                text="Read Full Translation", 
                callback_data="read_translation"
            )],
            [InlineKeyboardButton(
                text="Download Translation", 
                callback_data="download_translation"
            )],
            [InlineKeyboardButton(
                text="Back to Original Article", 
                callback_data="back_to_article"
            )],
            [InlineKeyboardButton(
                text="New Search", 
                callback_data="new_search"
            )]
        ]
        
        message = (
            f"📚 *{translated_article['title']}*\n\n"
            f"Translated from {get_language_name(source_lang)} to {get_language_name(target_lang)}:\n\n"
            f"{summary}\n\n"
            f"_Note: This is a machine translation and may not be perfect._"
        )
        
        try:
            await self.bot.editMessageText(
                (chat_id, message_id),
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except telepot.exception.TelegramError:
            # If we can't edit the message, send a new one
            await self.bot.sendMessage(
                chat_id,
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )

def main():
    """Start the WikiSearch Telegram bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("No bot token provided. Set the TELEGRAM_BOT_TOKEN environment variable.")
        exit(1)
    
    # Create bot instance
    bot = WikiBot(TELEGRAM_BOT_TOKEN)
    
    # Set up message handlers
    loop = asyncio.get_event_loop()
    
    # Handle incoming messages
    loop.create_task(MessageLoop(
        bot.bot, 
        {'chat': bot.handle_message, 'callback_query': bot.handle_callback_query}
    ).run_forever())
    
    logger.info("WikiSearch Telegram Bot is running...")
    
    # Keep the program running
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        loop.close()

if __name__ == "__main__":
    main()