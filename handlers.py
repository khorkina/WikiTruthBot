"""
Handlers for Telegram bot commands and callbacks
"""

import os
import logging
import json
import asyncio
import telepot
from telepot.aio.delegate import per_chat_id, create_open, pave_event_space, per_callback_query_origin
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

from wiki_article import (
    search_wikipedia,
    get_wikipedia_article,
    get_article_in_other_language,
    translate_article_content,
    get_article_sharing_link,
    get_language_name
)
from document_generator import create_document_from_article
from config import LANGUAGE_NAMES, POPULAR_LANGUAGES, DEFAULT_LANGUAGE, logger

# Callback data constants
CB_LANGUAGE = "lang"
CB_ARTICLE = "article"
CB_ACTION = "action"
CB_TRANSLATE = "translate"
CB_VIEW_LANG = "view_lang"

# States for the conversation
SELECTING_LANGUAGE = 0
SEARCHING = 1
VIEWING_ARTICLE = 2
SELECTING_ACTION = 3

# Cache for storing user data
user_data_cache = {}

class BotHandler(telepot.aio.helper.ChatHandler):
    """Handler for handling regular messages and commands"""
    
    def __init__(self, *args, **kwargs):
        super(BotHandler, self).__init__(*args, **kwargs)
        self.state = None
        self.language = DEFAULT_LANGUAGE
        
    async def on_chat_message(self, msg):
        """Handle incoming chat messages and commands"""
        content_type, chat_type, chat_id = telepot.glance(msg)
        
        if content_type != 'text':
            await self.sender.sendMessage("Sorry, I can only process text messages.")
            return
        
        text = msg['text']
        
        # Process commands
        if text.startswith('/'):
            command = text.split('@')[0].lower()
            
            if command == '/start':
                await self.handle_start()
            elif command == '/help':
                await self.handle_help()
            elif command == '/cancel':
                await self.handle_cancel()
            else:
                await self.sender.sendMessage("Unknown command. Type /help for available commands.")
            return
            
        # Process text based on current state
        if self.state == SEARCHING:
            await self.handle_search(text)
        else:
            await self.sender.sendMessage("Please use /start to begin a new search.")
    
    async def handle_start(self):
        """Start the conversation and show language selection"""
        # Create keyboard with popular languages
        keyboard = []
        row = []
        for i, (lang_code, lang_name) in enumerate(POPULAR_LANGUAGES.items()):
            # Create rows of 2 buttons each
            if i > 0 and i % 2 == 0:
                keyboard.append(row)
                row = []
            row.append(InlineKeyboardButton(
                text=lang_name, 
                callback_data=f"{CB_LANGUAGE}:{lang_code}"
            ))
        
        # Add the last row if it has buttons
        if row:
            keyboard.append(row)
        
        await self.sender.sendMessage(
            "Welcome to WikiSearch Bot! 📚\n\n"
            "I can help you search and explore Wikipedia articles in multiple languages.\n\n"
            "Please select your preferred language for searching:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        self.state = SELECTING_LANGUAGE
    
    async def handle_help(self):
        """Display help information"""
        help_text = (
            "WikiSearch Bot Help 🔍\n\n"
            "Commands:\n"
            "/start - Start a new search\n"
            "/help - Show this help message\n"
            "/cancel - Cancel current operation\n\n"
            "How to use:\n"
            "1. Select a language for search\n"
            "2. Enter a search term\n"
            "3. Select an article from search results\n"
            "4. Choose what you want to do with the article\n\n"
            "You can view full articles, see them in other languages, translate them, or download them as documents."
        )
        await self.sender.sendMessage(help_text)
    
    async def handle_cancel(self):
        """Cancel the current operation"""
        self.state = None
        await self.sender.sendMessage(
            "Operation cancelled. Type /start to begin a new search."
        )
    
    async def handle_search(self, query):
        """Search Wikipedia for the given query"""
        await self.sender.sendMessage(f"Searching for '{query}' in {get_language_name(self.language)}...")
        
        results = search_wikipedia(query, self.language)
        
        if not results:
            keyboard = [[
                InlineKeyboardButton(text="Try a different search", callback_data="try_again"),
                InlineKeyboardButton(text="Change language", callback_data="new_search")
            ]]
            
            await self.sender.sendMessage(
                f"No results found for '{query}' in {get_language_name(self.language)}. "
                f"Try a different search term or language.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
            return
        
        # Cache the query for this user
        user_id = self.chat_id
        if user_id not in user_data_cache:
            user_data_cache[user_id] = {}
        user_data_cache[user_id]['query'] = query
        
        # Create keyboard with search results (max 8 results to avoid message size limits)
        keyboard = []
        for title in results[:8]:
            keyboard.append([
                InlineKeyboardButton(
                    text=title, 
                    callback_data=f"{CB_ARTICLE}:{title}"
                )
            ])
        
        # Add a button to start a new search
        keyboard.append([
            InlineKeyboardButton(text="New Search", callback_data="new_search")
        ])
        
        await self.sender.sendMessage(
            f"Search results for '{query}' in {get_language_name(self.language)}:\n"
            f"Please select an article to view:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        self.state = VIEWING_ARTICLE


class CallbackQueryHandler(telepot.aio.helper.CallbackQueryHandler):
    """Handler for handling callback queries from inline buttons"""
    
    def __init__(self, *args, **kwargs):
        super(CallbackQueryHandler, self).__init__(*args, **kwargs)
        self.language = DEFAULT_LANGUAGE
    
    async def on_callback_query(self, msg):
        """Handle callback queries from inline keyboards"""
        query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
        
        # Always acknowledge the callback query to stop the loading indicator
        await self.bot.answerCallbackQuery(query_id)
        
        # Handle language selection
        if query_data.startswith(f"{CB_LANGUAGE}:"):
            await self.handle_language_selection(msg, query_data)
        
        # Handle article selection
        elif query_data.startswith(f"{CB_ARTICLE}:"):
            await self.handle_article_selection(msg, query_data)
        
        # Handle action selection
        elif query_data.startswith(f"{CB_ACTION}:"):
            await self.handle_action_selection(msg, query_data)
        
        # Handle language view selection
        elif query_data.startswith(f"{CB_VIEW_LANG}:"):
            await self.handle_view_language_selection(msg, query_data)
        
        # Handle translation language selection
        elif query_data.startswith(f"{CB_TRANSLATE}:"):
            await self.handle_translate_selection(msg, query_data)
        
        # Handle navigation actions
        elif query_data == "new_search":
            await self.handle_new_search(msg)
        
        elif query_data == "try_again":
            await self.handle_try_again(msg)
        
        elif query_data == "back_to_article":
            await self.handle_back_to_article(msg)
        
        elif query_data == "read_translation":
            await self.handle_read_translation(msg)
        
        elif query_data == "download_translation":
            await self.handle_download_translation(msg)
        
        elif query_data == "back_to_translation":
            await self.handle_back_to_translation(msg)
    
    async def handle_language_selection(self, msg, query_data):
        """Handle language selection callback"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Extract language code from callback data
        lang_code = query_data.split(':', 1)[1]
        
        # Save the selected language
        self.language = lang_code
        
        # Update user data cache
        if chat_id not in user_data_cache:
            user_data_cache[chat_id] = {}
        user_data_cache[chat_id]['language'] = lang_code
        
        # Prompt for search term
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Selected language: {get_language_name(lang_code)}\n\n"
            f"Please enter a search term to find Wikipedia articles:"
        )
        
        # Update the state for the chat handler
        for handler in self.bot._router._handlers:
            if isinstance(handler, BotHandler) and handler.chat_id == chat_id:
                handler.state = SEARCHING
                handler.language = lang_code
                break
    
    async def handle_article_selection(self, msg, query_data):
        """Handle article selection callback"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Extract article title from callback data
        title = query_data.split(':', 1)[1]
        
        # Get user data
        if chat_id not in user_data_cache:
            user_data_cache[chat_id] = {}
        user_data = user_data_cache[chat_id]
        
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
        
        # Cache the article data
        user_data['current_article'] = article
        
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
        
        # Update the state for the chat handler
        for handler in self.bot._router._handlers:
            if isinstance(handler, BotHandler) and handler.chat_id == chat_id:
                handler.state = SELECTING_ACTION
                break
    
    async def handle_action_selection(self, msg, query_data):
        """Handle action selection for an article"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Extract action from callback data
        action = query_data.split(':', 1)[1]
        
        # Get user data
        if chat_id not in user_data_cache:
            await self.bot.sendMessage(
                chat_id,
                "Session expired. Please start a new search with /start."
            )
            return
        
        user_data = user_data_cache[chat_id]
        article = user_data.get('current_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Article data not found. Please start a new search with /start."
            )
            return
        
        # Process the selected action
        if action == "read":
            # Send the full article content
            content = article['content']
            
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
                        f"*{article['title']}*\n\n{chunk}",
                        parse_mode="Markdown"
                    )
                else:
                    await self.bot.sendMessage(
                        chat_id,
                        chunk,
                        parse_mode="Markdown"
                    )
            
            # Add back to article button
            keyboard = [[
                InlineKeyboardButton(
                    text="Back to Article", 
                    callback_data="back_to_article"
                )
            ]]
            
            await self.bot.sendMessage(
                chat_id,
                "End of article.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        
        elif action == "languages":
            # Show available languages
            available_languages = article.get('available_languages', {})
            
            if not available_languages:
                await self.bot.editMessageText(
                    (chat_id, message_id),
                    f"This article is only available in {get_language_name(self.language)}.",
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
                if lang_code != self.language:  # Skip current language
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
                f"*{article['title']}*\n\nAvailable languages:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        
        elif action == "translate":
            # Show translation language options
            keyboard = []
            
            # Add a few common languages
            translation_languages = {
                "en": "English",
                "es": "Spanish",
                "fr": "French",
                "de": "German",
                "it": "Italian",
                "pt": "Portuguese",
                "ru": "Russian",
                "ja": "Japanese",
                "zh": "Chinese",
                "ar": "Arabic"
            }
            
            source_lang = user_data.get('language', DEFAULT_LANGUAGE)
            
            # Create rows of 2 buttons each
            row = []
            for i, (lang_code, lang_name) in enumerate(translation_languages.items()):
                # Skip the source language
                if lang_code == source_lang:
                    continue
                
                # Create rows of 2 buttons each
                if i > 0 and i % 2 == 0:
                    keyboard.append(row)
                    row = []
                
                row.append(InlineKeyboardButton(
                    text=lang_name, 
                    callback_data=f"{CB_TRANSLATE}:{lang_code}"
                ))
            
            # Add the last row if it has buttons
            if row:
                keyboard.append(row)
            
            # Add back button
            keyboard.append([
                InlineKeyboardButton(
                    text="Back to Article", 
                    callback_data="back_to_article"
                )
            ])
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"*{article['title']}*\n\nSelect a language to translate to:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        
        elif action == "download":
            # Create and send document
            language = user_data.get('language', DEFAULT_LANGUAGE)
            
            await self.bot.sendMessage(
                chat_id,
                f"Generating document for '{article['title']}'..."
            )
            
            try:
                doc_path = create_document_from_article(article, language)
                
                if doc_path and os.path.exists(doc_path):
                    with open(doc_path, 'rb') as doc_file:
                        await self.bot.sendDocument(
                            chat_id,
                            doc_file,
                            filename=f"{article['title']}.docx"
                        )
                    
                    # Clean up the file
                    os.remove(doc_path)
                    
                    # Add back to article button
                    keyboard = [[
                        InlineKeyboardButton(
                            text="Back to Article", 
                            callback_data="back_to_article"
                        )
                    ]]
                    
                    await self.bot.sendMessage(
                        chat_id,
                        "Document generated successfully.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
                    )
                else:
                    await self.bot.sendMessage(
                        chat_id,
                        "Failed to generate document. Please try again.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(
                                text="Back to Article", 
                                callback_data="back_to_article"
                            )
                        ]])
                    )
            except Exception as e:
                logger.error(f"Error generating document: {e}")
                await self.bot.sendMessage(
                    chat_id,
                    "An error occurred while generating the document. Please try again.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="Back to Article", 
                            callback_data="back_to_article"
                        )
                    ]])
                )
        
        elif action == "link":
            # Send Wikipedia link
            language = user_data.get('language', DEFAULT_LANGUAGE)
            link = get_article_sharing_link(article['title'], language)
            
            await self.bot.sendMessage(
                chat_id,
                f"Wikipedia link for '{article['title']}':\n{link}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
    
    async def handle_view_language_selection(self, msg, query_data):
        """Handle viewing article in another language"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Extract language code from callback data
        lang_code = query_data.split(':', 1)[1]
        
        # Get user data
        if chat_id not in user_data_cache:
            await self.bot.sendMessage(
                chat_id,
                "Session expired. Please start a new search with /start."
            )
            return
        
        user_data = user_data_cache[chat_id]
        article = user_data.get('current_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Article data not found. Please start a new search with /start."
            )
            return
        
        # Get available languages
        available_languages = article.get('available_languages', {})
        
        if lang_code not in available_languages:
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"This article is not available in {get_language_name(lang_code)}.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        # Get article title in the target language
        target_title = available_languages[lang_code]
        
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Loading article '{target_title}' in {get_language_name(lang_code)}..."
        )
        
        # Fetch the article in the target language
        target_article = get_article_in_other_language(article['title'], user_data.get('language', DEFAULT_LANGUAGE), lang_code)
        
        if not target_article:
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"Failed to retrieve the article in {get_language_name(lang_code)}.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        # Cache the article data
        user_data['current_article'] = target_article
        user_data['language'] = lang_code
        
        # Format message with article summary (limit to ~1000 chars)
        summary = target_article['summary']
        if len(summary) > 1000:
            summary = summary[:997] + "..."
        
        message = (
            f"📚 *{target_article['title']}*\n\n"
            f"{summary}\n\n"
            f"_Language: {get_language_name(lang_code)}_"
        )
        
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
        
        await self.bot.editMessageText(
            (chat_id, message_id),
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        # Update handlers with new language
        for handler in self.bot._router._handlers:
            if isinstance(handler, BotHandler) and handler.chat_id == chat_id:
                handler.language = lang_code
                break
    
    async def handle_translate_selection(self, msg, query_data):
        """Handle translation of article to selected language"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Extract target language code from callback data
        target_lang = query_data.split(':', 1)[1]
        
        # Get user data
        if chat_id not in user_data_cache:
            await self.bot.sendMessage(
                chat_id,
                "Session expired. Please start a new search with /start."
            )
            return
        
        user_data = user_data_cache[chat_id]
        article = user_data.get('current_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Article data not found. Please start a new search with /start."
            )
            return
        
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Translating article '{article['title']}' from {get_language_name(source_lang)} to {get_language_name(target_lang)}..."
        )
        
        try:
            # Translate the article
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
            
            # Cache the translated article
            user_data['translated_article'] = translated_article
            user_data['target_language'] = target_lang
            
            # Format message with translated summary (limit to ~1000 chars)
            summary = translated_article['summary']
            if len(summary) > 1000:
                summary = summary[:997] + "..."
            
            message = (
                f"📚 *{translated_article['title']}* "
                f"({get_language_name(source_lang)} → {get_language_name(target_lang)})\n\n"
                f"{summary}\n\n"
                f"_Note: This is a machine translation and may not be perfect._"
            )
            
            # Create keyboard for translation actions
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="Read Full Translation", 
                        callback_data="read_translation"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Download Translation", 
                        callback_data="download_translation"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Back to Original Article", 
                        callback_data="back_to_article"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="New Search", 
                        callback_data="new_search"
                    )
                ]
            ]
            
            await self.bot.editMessageText(
                (chat_id, message_id),
                message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        
        except Exception as e:
            logger.error(f"Translation error: {e}")
            await self.bot.editMessageText(
                (chat_id, message_id),
                f"An error occurred during translation: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
    
    async def handle_new_search(self, msg):
        """Handle new search button click"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Create keyboard with popular languages
        keyboard = []
        row = []
        for i, (lang_code, lang_name) in enumerate(POPULAR_LANGUAGES.items()):
            # Create rows of 2 buttons each
            if i > 0 and i % 2 == 0:
                keyboard.append(row)
                row = []
            row.append(InlineKeyboardButton(
                text=lang_name, 
                callback_data=f"{CB_LANGUAGE}:{lang_code}"
            ))
        
        # Add the last row if it has buttons
        if row:
            keyboard.append(row)
        
        await self.bot.editMessageText(
            (chat_id, message_id),
            "Starting a new search.\n\n"
            "Please select your preferred language for searching:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        # Update the state for the chat handler
        for handler in self.bot._router._handlers:
            if isinstance(handler, BotHandler) and handler.chat_id == chat_id:
                handler.state = SELECTING_LANGUAGE
                break
    
    async def handle_try_again(self, msg):
        """Handle try again button click"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Get user language
        if chat_id in user_data_cache:
            language = user_data_cache[chat_id].get('language', DEFAULT_LANGUAGE)
        else:
            language = DEFAULT_LANGUAGE
        
        await self.bot.editMessageText(
            (chat_id, message_id),
            f"Please enter a new search term to find Wikipedia articles in {get_language_name(language)}:"
        )
        
        # Update the state for the chat handler
        for handler in self.bot._router._handlers:
            if isinstance(handler, BotHandler) and handler.chat_id == chat_id:
                handler.state = SEARCHING
                break
    
    async def handle_back_to_article(self, msg):
        """Navigate back to article summary view"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Get user data
        if chat_id not in user_data_cache:
            await self.bot.sendMessage(
                chat_id,
                "Session expired. Please start a new search with /start."
            )
            return
        
        user_data = user_data_cache[chat_id]
        article = user_data.get('current_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Article data not found. Please start a new search with /start."
            )
            return
        
        language = user_data.get('language', DEFAULT_LANGUAGE)
        
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
    
    async def handle_read_translation(self, msg):
        """Display the full translated article content"""
        chat_id = msg['message']['chat']['id']
        
        # Get user data
        if chat_id not in user_data_cache:
            await self.bot.sendMessage(
                chat_id,
                "Session expired. Please start a new search with /start."
            )
            return
        
        user_data = user_data_cache[chat_id]
        article = user_data.get('translated_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Translation data not found. Please try translating again.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        target_lang = user_data.get('target_language', 'en')
        
        # Send the full translated content
        content = article['content']
        
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
                    f"*{article['title']}* ({get_language_name(source_lang)} → {get_language_name(target_lang)})\n\n{chunk}",
                    parse_mode="Markdown"
                )
            else:
                await self.bot.sendMessage(
                    chat_id,
                    chunk,
                    parse_mode="Markdown"
                )
        
        # Add back to translation button
        keyboard = [[
            InlineKeyboardButton(
                text="Back to Translation Summary", 
                callback_data="back_to_translation"
            )
        ]]
        
        await self.bot.sendMessage(
            chat_id,
            "End of translated article.\n\n_Note: This is a machine translation and may not be perfect._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    
    async def handle_download_translation(self, msg):
        """Generate and send a document with the translated article"""
        chat_id = msg['message']['chat']['id']
        
        # Get user data
        if chat_id not in user_data_cache:
            await self.bot.sendMessage(
                chat_id,
                "Session expired. Please start a new search with /start."
            )
            return
        
        user_data = user_data_cache[chat_id]
        article = user_data.get('translated_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Translation data not found. Please try translating again.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        target_lang = user_data.get('target_language', 'en')
        
        await self.bot.sendMessage(
            chat_id,
            f"Generating document for translated article '{article['title']}'..."
        )
        
        try:
            doc_path = create_document_from_article(article, target_lang)
            
            if doc_path and os.path.exists(doc_path):
                with open(doc_path, 'rb') as doc_file:
                    await self.bot.sendDocument(
                        chat_id,
                        doc_file,
                        filename=f"{article['title']}_{target_lang}.docx"
                    )
                
                # Clean up the file
                os.remove(doc_path)
                
                # Add back to translation button
                keyboard = [[
                    InlineKeyboardButton(
                        text="Back to Translation Summary", 
                        callback_data="back_to_translation"
                    )
                ]]
                
                await self.bot.sendMessage(
                    chat_id,
                    "Translation document generated successfully.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
                )
            else:
                await self.bot.sendMessage(
                    chat_id,
                    "Failed to generate document. Please try again.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="Back to Translation Summary", 
                            callback_data="back_to_translation"
                        )
                    ]])
                )
        except Exception as e:
            logger.error(f"Error generating document: {e}")
            await self.bot.sendMessage(
                chat_id,
                "An error occurred while generating the document. Please try again.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Translation Summary", 
                        callback_data="back_to_translation"
                    )
                ]])
            )
    
    async def handle_back_to_translation(self, msg):
        """Return to the translation summary view"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Get user data
        if chat_id not in user_data_cache:
            await self.bot.sendMessage(
                chat_id,
                "Session expired. Please start a new search with /start."
            )
            return
        
        user_data = user_data_cache[chat_id]
        article = user_data.get('translated_article')
        
        if not article:
            await self.bot.sendMessage(
                chat_id,
                "Translation data not found. Please try translating again.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="Back to Article", 
                        callback_data="back_to_article"
                    )
                ]])
            )
            return
        
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        target_lang = user_data.get('target_language', 'en')
        
        # Format message with translated summary (limit to ~1000 chars)
        summary = article['summary']
        if len(summary) > 1000:
            summary = summary[:997] + "..."
        
        message = (
            f"📚 *{article['title']}* "
            f"({get_language_name(source_lang)} → {get_language_name(target_lang)})\n\n"
            f"{summary}\n\n"
            f"_Note: This is a machine translation and may not be perfect._"
        )
        
        # Create keyboard for translation actions
        keyboard = [
            [
                InlineKeyboardButton(
                    text="Read Full Translation", 
                    callback_data="read_translation"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Download Translation", 
                    callback_data="download_translation"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Back to Original Article", 
                    callback_data="back_to_article"
                )
            ],
            [
                InlineKeyboardButton(
                    text="New Search", 
                    callback_data="new_search"
                )
            ]
        ]
        
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation and show language selection"""
    user_id = update.effective_user.id
    
    # Clear any existing user data
    if user_id in user_data_cache:
        del user_data_cache[user_id]
    
    # Initialize user data
    user_data_cache[user_id] = {
        "search_lang": DEFAULT_LANGUAGE
    }
    
    # Create keyboard with language options
    keyboard = []
    row = []
    for i, lang_code in enumerate(POPULAR_LANGUAGES):
        lang_name = get_language_name(lang_code)
        button = InlineKeyboardButton(f"{lang_name} ({lang_code})", callback_data=f"{CB_LANGUAGE}:{lang_code}")
        row.append(button)
        
        # Create rows with 2 buttons each
        if len(row) == 2 or i == len(POPULAR_LANGUAGES) - 1:
            keyboard.append(row)
            row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌍 Welcome to WikiSearch Bot!\n\n"
        "I can help you search, read, and translate Wikipedia articles in multiple languages.\n\n"
        "Please select a language for your search:",
        reply_markup=reply_markup
    )
    
    return SELECTING_LANGUAGE

async def language_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection and prompt for search query"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang_code = query.data.split(':')[1]
    
    # Store the selected language
    if user_id not in user_data_cache:
        user_data_cache[user_id] = {}
    
    user_data_cache[user_id]["search_lang"] = lang_code
    lang_name = get_language_name(lang_code)
    
    await query.edit_message_text(
        f"🔍 You selected: {lang_name} ({lang_code})\n\n"
        f"Please enter your search query in {lang_name}:"
    )
    
    return SEARCHING

async def search_articles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for articles and display results"""
    user_id = update.effective_user.id
    search_query = update.message.text.strip()
    
    # Get the selected language
    if user_id not in user_data_cache or "search_lang" not in user_data_cache[user_id]:
        user_data_cache[user_id] = {"search_lang": DEFAULT_LANGUAGE}
    
    search_lang = user_data_cache[user_id]["search_lang"]
    
    # Search Wikipedia
    await update.message.reply_text(f"🔍 Searching for '{search_query}' in {get_language_name(search_lang)}...")
    
    results = search_wikipedia(search_query, search_lang)
    
    if not results:
        # No results found, offer to try again or change language
        keyboard = [
            [InlineKeyboardButton("Change Language", callback_data="new_search")],
            [InlineKeyboardButton("Try Different Search", callback_data="try_again")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ No results found.\n\n"
            "Please try a different search term or language.",
            reply_markup=reply_markup
        )
        return SELECTING_ACTION
    
    # Display search results as inline buttons
    keyboard = []
    for i, result in enumerate(results[:8]):  # Limit to 8 results
        keyboard.append([InlineKeyboardButton(result, callback_data=f"{CB_ARTICLE}:{result}")])
    
    # Add button to try a different search
    keyboard.append([InlineKeyboardButton("New Search", callback_data="new_search")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📚 Found {len(results)} results for '{search_query}'.\n\n"
        "Please select an article to view:",
        reply_markup=reply_markup
    )
    
    return VIEWING_ARTICLE

async def view_article(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display article summary and options"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    article_title = query.data.split(':')[1]
    
    # Get user's search language
    search_lang = user_data_cache[user_id].get("search_lang", DEFAULT_LANGUAGE)
    
    # Inform user that article is being retrieved
    await query.edit_message_text(f"📝 Retrieving article: {article_title}...")
    
    # Get article content
    article = get_wikipedia_article(article_title, search_lang)
    
    if not article:
        # Article not found
        keyboard = [
            [InlineKeyboardButton("Try Another Search", callback_data="try_again")],
            [InlineKeyboardButton("Change Language", callback_data="new_search")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Article not found or error occurred.\n\nPlease try again.",
            reply_markup=reply_markup
        )
        return SELECTING_ACTION
    
    # Store the article in user data
    user_data_cache[user_id]["current_article"] = article
    user_data_cache[user_id]["current_lang"] = search_lang
    
    # Format and send the article summary
    message = f"📄 *{article['title']}*\n\n{article['summary']}\n\n"
    message += f"🌐 Language: {get_language_name(search_lang)} ({search_lang})\n"
    message += f"🔗 [View on Wikipedia]({article['url']})"
    
    # Create keyboard with article options
    keyboard = []
    
    # Check available languages for this article
    available_langs = article.get('available_languages', {})
    if len(available_langs) > 1:
        keyboard.append([InlineKeyboardButton("🌍 View in Another Language", callback_data=f"{CB_ACTION}:languages")])
    
    # Other action buttons
    keyboard.extend([
        [InlineKeyboardButton("📚 Read Full Article", callback_data=f"{CB_ACTION}:full")],
        [InlineKeyboardButton("🔄 Translate Article", callback_data=f"{CB_ACTION}:translate")],
        [InlineKeyboardButton("📥 Download as Document", callback_data=f"{CB_ACTION}:download")],
        [InlineKeyboardButton("🔍 New Search", callback_data="new_search")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=message,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    
    return SELECTING_ACTION

async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle article actions (read full, translate, download, etc.)"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "new_search":
        # Start a new search by selecting language
        await start(update, context)
        return SELECTING_LANGUAGE
    
    if query.data == "try_again":
        # Try another search with the same language
        search_lang = user_data_cache[user_id].get("search_lang", DEFAULT_LANGUAGE)
        lang_name = get_language_name(search_lang)
        
        await query.edit_message_text(
            f"🔍 Search in {lang_name} ({search_lang})\n\n"
            "Please enter your search query:"
        )
        return SEARCHING
    
    # Get action from callback data
    action = query.data.split(':')[1]
    
    # Get current article and language from user data
    article = user_data_cache[user_id].get("current_article")
    current_lang = user_data_cache[user_id].get("current_lang")
    
    if not article:
        await query.edit_message_text("❌ Error: Article data not found. Please start a new search.")
        return ConversationHandler.END
    
    if action == "languages":
        # Show available languages for this article
        available_langs = article.get('available_languages', {})
        
        if not available_langs:
            await query.edit_message_text(
                "❌ No language information available for this article.\n"
                "Please try another action or search."
            )
            return SELECTING_ACTION
        
        # Create keyboard with language options
        keyboard = []
        for lang_code, title in available_langs.items():
            if lang_code != current_lang:  # Skip current language
                lang_name = get_language_name(lang_code)
                keyboard.append([
                    InlineKeyboardButton(
                        f"{lang_name} ({lang_code})", 
                        callback_data=f"{CB_VIEW_LANG}:{lang_code}"
                    )
                ])
        
        # Add back button
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_article")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🌍 Available languages for '{article['title']}':\n\n"
            "Please select a language to view:",
            reply_markup=reply_markup
        )
        
        return SELECTING_ACTION
    
    elif action == "full":
        # Display full article content with sections
        sections = article.get('sections', [])
        
        if not sections:
            # If no sections, just show the full content
            message = f"📄 *{article['title']}* (Full Article)\n\n{article['content']}\n\n"
            message += f"🌐 Language: {get_language_name(current_lang)} ({current_lang})\n"
            message += f"🔗 [View on Wikipedia]({article['url']})"
            
            # Message might be too long, so split it
            if len(message) > 4000:
                # Send in parts
                first_part = message[:4000] + "...\n(Continued in next message)"
                await context.bot.send_message(
                    chat_id=user_id,
                    text=first_part,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                
                second_part = "...(Continued)\n\n" + message[4000:]
                await context.bot.send_message(
                    chat_id=user_id,
                    text=second_part,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
        else:
            # Send message with sections one by one
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📄 *{article['title']}* (Full Article)\n\n"
                     f"🌐 Language: {get_language_name(current_lang)} ({current_lang})\n"
                     f"🔗 [View on Wikipedia]({article['url']})",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            
            # Send message with table of contents first
            toc_message = "*Table of Contents*\n\n"
            for i, section in enumerate(sections):
                if section.get('title'):
                    level = section.get('level', 0)
                    indent = "  " * level
                    toc_message += f"{indent}• {section['title']}\n"
            
            await context.bot.send_message(
                chat_id=user_id,
                text=toc_message,
                parse_mode="Markdown"
            )
            
            # Send sections one by one (max 3 to avoid spam)
            section_count = min(len(sections), 10)
            for i in range(section_count):
                section = sections[i]
                section_title = section.get('title', 'Section')
                section_content = section.get('content', 'No content')
                
                # Format section message
                section_level = section.get('level', 0) + 1
                section_message = f"{'#' * section_level} {section_title}\n\n{section_content}"
                
                # Send section
                if len(section_message) > 4000:
                    # Split long sections
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=section_message[:4000] + "...",
                        parse_mode="Markdown"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=section_message,
                        parse_mode="Markdown"
                    )
            
            # If there are more sections, inform the user
            if len(sections) > section_count:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Article has {len(sections)} sections in total. "
                         f"Only showing first {section_count} to avoid spam.\n\n"
                         f"For full content, please download the article or view it on Wikipedia."
                )
        
        # Add options to go back or new search
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Summary", callback_data="back_to_article")],
            [InlineKeyboardButton("🔍 New Search", callback_data="new_search")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text="What would you like to do next?",
            reply_markup=reply_markup
        )
        
        return SELECTING_ACTION
    
    elif action == "translate":
        # Show translation language options
        keyboard = []
        row = []
        
        # Add popular languages for translation
        for i, lang_code in enumerate(POPULAR_LANGUAGES):
            if lang_code != current_lang:  # Skip current language
                lang_name = get_language_name(lang_code)
                button = InlineKeyboardButton(
                    f"{lang_name} ({lang_code})", 
                    callback_data=f"{CB_TRANSLATE}:{lang_code}"
                )
                row.append(button)
                
                # Create rows with 2 buttons each
                if len(row) == 2 or i == len(POPULAR_LANGUAGES) - 1:
                    keyboard.append(row)
                    row = []
        
        # Add back button
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_article")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🔄 Translate '{article['title']}' to:\n\n"
            "Please select a target language:",
            reply_markup=reply_markup
        )
        
        return SELECTING_ACTION
    
    elif action == "download":
        # Generate and send document file
        await query.edit_message_text(f"📥 Generating document for '{article['title']}'...")
        
        doc_path = create_document_from_article(article, current_lang)
        
        if not doc_path or not os.path.exists(doc_path):
            # Error generating document
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Error generating document. Please try again."
            )
        else:
            # Send the document
            with open(doc_path, 'rb') as document:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=document,
                    filename=os.path.basename(doc_path),
                    caption=f"📄 {article['title']} ({get_language_name(current_lang)})"
                )
            
            # Delete the temporary file
            try:
                os.remove(doc_path)
            except Exception as e:
                logging.error(f"Error removing temporary file: {str(e)}")
        
        # Add options to go back or new search
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Article", callback_data="back_to_article")],
            [InlineKeyboardButton("🔍 New Search", callback_data="new_search")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text="What would you like to do next?",
            reply_markup=reply_markup
        )
        
        return SELECTING_ACTION
    
    return SELECTING_ACTION

async def view_article_in_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle viewing the article in another language"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    target_lang = query.data.split(':')[1]
    
    # Get current article and language from user data
    article = user_data_cache[user_id].get("current_article")
    current_lang = user_data_cache[user_id].get("current_lang")
    
    if not article:
        await query.edit_message_text("❌ Error: Article data not found. Please start a new search.")
        return ConversationHandler.END
    
    # Get available languages for this article
    available_langs = article.get('available_languages', {})
    
    if target_lang not in available_langs:
        await query.edit_message_text(
            f"❌ Article not available in {get_language_name(target_lang)}.\n"
            "Please try another language or action."
        )
        return SELECTING_ACTION
    
    # Get article title in target language
    target_title = available_langs[target_lang]
    
    # Show loading message
    await query.edit_message_text(f"🔄 Loading article in {get_language_name(target_lang)}...")
    
    # Get article in target language
    new_article = get_article_in_other_language(article['title'], current_lang, target_lang)
    
    if not new_article:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ Failed to retrieve article in {get_language_name(target_lang)}.\n"
                 "Please try another language or action."
        )
        return SELECTING_ACTION
    
    # Update current article and language in user data
    user_data_cache[user_id]["current_article"] = new_article
    user_data_cache[user_id]["current_lang"] = target_lang
    
    # Format and send the article summary
    message = f"📄 *{new_article['title']}*\n\n{new_article['summary']}\n\n"
    message += f"🌐 Language: {get_language_name(target_lang)} ({target_lang})\n"
    message += f"🔗 [View on Wikipedia]({new_article['url']})"
    
    # Create keyboard with article options
    keyboard = []
    
    # Check available languages for this article
    available_langs = new_article.get('available_languages', {})
    if len(available_langs) > 1:
        keyboard.append([InlineKeyboardButton("🌍 View in Another Language", callback_data=f"{CB_ACTION}:languages")])
    
    # Other action buttons
    keyboard.extend([
        [InlineKeyboardButton("📚 Read Full Article", callback_data=f"{CB_ACTION}:full")],
        [InlineKeyboardButton("🔄 Translate Article", callback_data=f"{CB_ACTION}:translate")],
        [InlineKeyboardButton("📥 Download as Document", callback_data=f"{CB_ACTION}:download")],
        [InlineKeyboardButton("🔍 New Search", callback_data="new_search")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=message,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    
    return SELECTING_ACTION

async def translate_article(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Translate the article to the selected language"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    target_lang = query.data.split(':')[1]
    
    # Get current article and language from user data
    article = user_data_cache[user_id].get("current_article")
    current_lang = user_data_cache[user_id].get("current_lang")
    
    if not article:
        await query.edit_message_text("❌ Error: Article data not found. Please start a new search.")
        return ConversationHandler.END
    
    # Show translation in progress message
    await query.edit_message_text(
        f"🔄 Translating '{article['title']}' from {get_language_name(current_lang)} to {get_language_name(target_lang)}...\n\n"
        "This may take a moment."
    )
    
    # Translate article summary first (faster response)
    translated_summary = None
    try:
        from wiki_utils import translate_text
        translated_summary = translate_text(article['summary'], target_lang, current_lang)
    except Exception as e:
        logging.error(f"Error translating summary: {str(e)}")
    
    if translated_summary:
        # Send the translated summary first
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🔄 *{article['title']}* - Translated Summary\n\n{translated_summary}\n\n"
                 f"(Translating full article content... please wait)",
            parse_mode="Markdown"
        )
    
    # Translate the full article
    try:
        translated_article = translate_article_content(article, current_lang, target_lang)
        
        if not translated_article:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Translation failed. Please try again or try another language."
            )
            return SELECTING_ACTION
        
        # Store translated article in user data as a new entry
        translated_article['original_lang'] = current_lang
        translated_article['translated_to'] = target_lang
        
        user_data_cache[user_id]["translated_article"] = translated_article
        
        # Format and send the translated article
        message = f"🔄 *{translated_article['title']}*\n\n"
        message += f"Translated from {get_language_name(current_lang)} to {get_language_name(target_lang)}\n\n"
        message += f"{translated_article['summary']}\n\n"
        message += f"🔗 [View Original on Wikipedia]({article['url']})"
        
        # Create keyboard with article options
        keyboard = [
            [InlineKeyboardButton("📚 Read Full Translation", callback_data="read_translation")],
            [InlineKeyboardButton("📥 Download Translation", callback_data="download_translation")],
            [InlineKeyboardButton("⬅️ Back to Original", callback_data="back_to_article")],
            [InlineKeyboardButton("🔍 New Search", callback_data="new_search")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logging.error(f"Error translating article: {str(e)}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Error during translation. Please try again or try another language."
        )
    
    return SELECTING_ACTION

async def handle_back_to_article(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to the original article summary view"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Get current article and language from user data
    article = user_data_cache[user_id].get("current_article")
    current_lang = user_data_cache[user_id].get("current_lang")
    
    if not article:
        await query.edit_message_text("❌ Error: Article data not found. Please start a new search.")
        return ConversationHandler.END
    
    # Format and send the article summary
    message = f"📄 *{article['title']}*\n\n{article['summary']}\n\n"
    message += f"🌐 Language: {get_language_name(current_lang)} ({current_lang})\n"
    message += f"🔗 [View on Wikipedia]({article['url']})"
    
    # Create keyboard with article options
    keyboard = []
    
    # Check available languages for this article
    available_langs = article.get('available_languages', {})
    if len(available_langs) > 1:
        keyboard.append([InlineKeyboardButton("🌍 View in Another Language", callback_data=f"{CB_ACTION}:languages")])
    
    # Other action buttons
    keyboard.extend([
        [InlineKeyboardButton("📚 Read Full Article", callback_data=f"{CB_ACTION}:full")],
        [InlineKeyboardButton("🔄 Translate Article", callback_data=f"{CB_ACTION}:translate")],
        [InlineKeyboardButton("📥 Download as Document", callback_data=f"{CB_ACTION}:download")],
        [InlineKeyboardButton("🔍 New Search", callback_data="new_search")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    
    return SELECTING_ACTION

async def read_translation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the full translated article content"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Get translated article from user data
    translated_article = user_data_cache[user_id].get("translated_article")
    
    if not translated_article:
        await query.edit_message_text("❌ Error: Translation data not found. Please try translating again.")
        return SELECTING_ACTION
    
    original_lang = translated_article.get('original_lang', 'unknown')
    target_lang = translated_article.get('translated_to', 'unknown')
    
    # Send translation info
    await context.bot.send_message(
        chat_id=user_id,
        text=f"🔄 *{translated_article['title']}* - Full Translation\n\n"
             f"Translated from {get_language_name(original_lang)} to {get_language_name(target_lang)}\n",
        parse_mode="Markdown"
    )
    
    # Get the translated sections
    sections = translated_article.get('sections', [])
    
    if not sections:
        # If no sections, just show the full content
        message = f"{translated_article.get('content', 'No content available')}"
        
        # Message might be too long, so split it
        if len(message) > 4000:
            # Send in parts
            first_part = message[:4000] + "...\n(Continued in next message)"
            await context.bot.send_message(
                chat_id=user_id,
                text=first_part
            )
            
            second_part = "...(Continued)\n\n" + message[4000:]
            await context.bot.send_message(
                chat_id=user_id,
                text=second_part
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=message
            )
    else:
        # Send sections one by one (max 3 to avoid spam)
        section_count = min(len(sections), 5)
        for i in range(section_count):
            section = sections[i]
            section_title = section.get('title', 'Section')
            section_content = section.get('content', 'No content')
            
            # Format section message
            section_level = section.get('level', 0) + 1
            section_message = f"{'#' * section_level} {section_title}\n\n{section_content}"
            
            # Send section
            if len(section_message) > 4000:
                # Split long sections
                await context.bot.send_message(
                    chat_id=user_id,
                    text=section_message[:4000] + "..."
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=section_message
                )
        
        # If there are more sections, inform the user
        if len(sections) > section_count:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⚠️ Article has {len(sections)} sections in total. "
                     f"Only showing first {section_count} to avoid spam.\n\n"
                     f"For full content, please download the translation."
            )
    
    # Add options to go back or new search
    keyboard = [
        [InlineKeyboardButton("⬅️ Back to Translation Summary", callback_data="back_to_translation")],
        [InlineKeyboardButton("⬅️ Back to Original Article", callback_data="back_to_article")],
        [InlineKeyboardButton("🔍 New Search", callback_data="new_search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text="What would you like to do next?",
        reply_markup=reply_markup
    )
    
    return SELECTING_ACTION

async def download_translation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send a document with the translated article"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Get translated article from user data
    translated_article = user_data_cache[user_id].get("translated_article")
    
    if not translated_article:
        await query.edit_message_text("❌ Error: Translation data not found. Please try translating again.")
        return SELECTING_ACTION
    
    original_lang = translated_article.get('original_lang', 'unknown')
    target_lang = translated_article.get('translated_to', 'unknown')
    
    # Show generating document message
    await query.edit_message_text(
        f"📥 Generating translated document for '{translated_article['title']}'..."
    )
    
    # Generate and send document file
    doc_path = create_document_from_article(translated_article, f"{original_lang}-to-{target_lang}")
    
    if not doc_path or not os.path.exists(doc_path):
        # Error generating document
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Error generating translated document. Please try again."
        )
    else:
        # Send the document
        with open(doc_path, 'rb') as document:
            await context.bot.send_document(
                chat_id=user_id,
                document=document,
                filename=os.path.basename(doc_path),
                caption=f"📄 {translated_article['title']} (Translated from {get_language_name(original_lang)} to {get_language_name(target_lang)})"
            )
        
        # Delete the temporary file
        try:
            os.remove(doc_path)
        except Exception as e:
            logging.error(f"Error removing temporary file: {str(e)}")
    
    # Add options to go back or new search
    keyboard = [
        [InlineKeyboardButton("⬅️ Back to Translation", callback_data="back_to_translation")],
        [InlineKeyboardButton("⬅️ Back to Original Article", callback_data="back_to_article")],
        [InlineKeyboardButton("🔍 New Search", callback_data="new_search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text="What would you like to do next?",
        reply_markup=reply_markup
    )
    
    return SELECTING_ACTION

async def back_to_translation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to the translation summary view"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Get translated article from user data
    translated_article = user_data_cache[user_id].get("translated_article")
    original_article = user_data_cache[user_id].get("current_article")
    
    if not translated_article or not original_article:
        await query.edit_message_text("❌ Error: Translation data not found. Please try translating again.")
        return SELECTING_ACTION
    
    original_lang = translated_article.get('original_lang', 'unknown')
    target_lang = translated_article.get('translated_to', 'unknown')
    
    # Format and send the translated article summary
    message = f"🔄 *{translated_article['title']}*\n\n"
    message += f"Translated from {get_language_name(original_lang)} to {get_language_name(target_lang)}\n\n"
    message += f"{translated_article['summary']}\n\n"
    message += f"🔗 [View Original on Wikipedia]({original_article['url']})"
    
    # Create keyboard with article options
    keyboard = [
        [InlineKeyboardButton("📚 Read Full Translation", callback_data="read_translation")],
        [InlineKeyboardButton("📥 Download Translation", callback_data="download_translation")],
        [InlineKeyboardButton("⬅️ Back to Original", callback_data="back_to_article")],
        [InlineKeyboardButton("🔍 New Search", callback_data="new_search")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    
    return SELECTING_ACTION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel and end the conversation"""
    user_id = update.effective_user.id
    
    # Clear user data
    if user_id in user_data_cache:
        del user_data_cache[user_id]
    
    await update.message.reply_text(
        "✅ Operation cancelled. Type /start to begin a new search."
    )
    
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued"""
    help_text = (
        "🌍 *WikiSearch Bot Help*\n\n"
        "*Available Commands:*\n"
        "/start - Start a new search\n"
        "/help - Show this help message\n"
        "/cancel - Cancel the current operation\n\n"
        
        "*Features:*\n"
        "• Search Wikipedia articles in multiple languages\n"
        "• View article summaries and full content\n"
        "• Switch between available languages for an article\n"
        "• Translate articles to other languages\n"
        "• Download articles as Word documents\n"
        "• Copy article links for sharing\n\n"
        
        "*Usage Tips:*\n"
        "1. Start with /start to select a search language\n"
        "2. Enter your search query\n"
        "3. Select an article from the results\n"
        "4. Use the provided buttons to explore options\n\n"
        
        "For any issues or feedback, please contact the bot administrator."
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown"
    )
