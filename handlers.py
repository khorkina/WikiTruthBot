"""
Handlers for Telegram bot commands and callbacks
"""

import os
import re
import json
import logging

import telepot
from telepot.aio.delegate import per_chat_id
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    POPULAR_LANGUAGES,
    DEFAULT_LANGUAGE,
    LANGUAGE_NAMES,
    SELECTING_LANGUAGE,
    SEARCHING,
    VIEWING_ARTICLE,
    SELECTING_ACTION,
    READING_ARTICLE,
    TRANSLATING,
    VIEWING_TRANSLATION,
    CB_LANGUAGE,
    CB_ARTICLE,
    CB_ACTION,
    CB_VIEW_LANG,
    CB_TRANSLATE,
    user_data_cache,
    logger
)

from wiki_article import (
    get_language_name,
    search_wikipedia,
    get_wikipedia_article,
    get_article_in_other_language,
    translate_article_content,
    get_article_sharing_link
)

from document_generator import create_document_from_article

class BotHandler(telepot.aio.helper.ChatHandler):
    """Handler for handling regular messages and commands"""
    
    def __init__(self, *args, **kwargs):
        super(BotHandler, self).__init__(*args, **kwargs)
        self.state = SELECTING_LANGUAGE
        self.language = DEFAULT_LANGUAGE
        self.chat_id = self.chat_id  # Store chat_id for cross-referencing with CallbackQueryHandler
    
    async def on_chat_message(self, msg):
        """Handle incoming chat messages and commands"""
        content_type, chat_type, chat_id = telepot.glance(msg)
        
        if content_type != 'text':
            await self.bot.sendMessage(
                chat_id,
                "I can only process text messages. Please send a text message."
            )
            return
        
        text = msg['text']
        
        # Handle commands
        if text.startswith('/'):
            command = text.split('@')[0].lower()  # Remove bot username from command
            
            if command == '/start':
                await self.handle_start()
            elif command == '/help':
                await self.handle_help()
            elif command == '/cancel':
                await self.handle_cancel()
            else:
                await self.bot.sendMessage(
                    chat_id,
                    "Unknown command. Try /start, /help, or /cancel."
                )
            return
        
        # Handle regular text based on state
        if self.state == SEARCHING:
            await self.handle_search(text)
        else:
            # Default response for unexpected messages
            await self.bot.sendMessage(
                chat_id,
                "I'm not sure what you mean. Use /start to begin searching for Wikipedia articles."
            )
    
    async def handle_start(self):
        """Start the conversation and show language selection"""
        chat_id = self.chat_id
        
        # Clear any existing user data
        if chat_id in user_data_cache:
            del user_data_cache[chat_id]
        
        # Initialize new user data
        user_data_cache[chat_id] = {
            "language": DEFAULT_LANGUAGE
        }
        
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
        
        # Send welcome message with language selection
        await self.bot.sendMessage(
            chat_id,
            "🌍 Welcome to WikiSearch Bot!\n\n"
            "I can help you search, read, and translate Wikipedia articles in multiple languages.\n\n"
            "Please select a language for your search:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
        self.state = SELECTING_LANGUAGE
    
    async def handle_help(self):
        """Display help information"""
        chat_id = self.chat_id
        
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
    
    async def handle_cancel(self):
        """Cancel the current operation"""
        chat_id = self.chat_id
        
        await self.bot.sendMessage(
            chat_id,
            "Operation cancelled. Type /start to begin a new search."
        )
        
        self.state = SELECTING_LANGUAGE
    
    async def handle_search(self, query):
        """Search Wikipedia for the given query"""
        chat_id = self.chat_id
        
        # Get current language for the user
        if chat_id not in user_data_cache:
            user_data_cache[chat_id] = {}
        
        user_data = user_data_cache[chat_id]
        language = user_data.get('language', DEFAULT_LANGUAGE)
        
        # Save the query
        user_data['search_query'] = query
        
        # Show searching message
        wait_msg = await self.bot.sendMessage(
            chat_id,
            f"Searching for '{query}' in {get_language_name(language)}..."
        )
        
        # Search Wikipedia
        search_results = search_wikipedia(query, language)
        
        # Process search results
        if search_results:
            # Create keyboard with search results
            keyboard = []
            for title in search_results[:8]:  # Limit to 8 results to keep menu size reasonable
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
        
        self.state = VIEWING_ARTICLE


class CallbackQueryHandler(telepot.aio.helper.CallbackQueryOriginHandler):
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
                        document=doc_file,
                        filename=f"{article['title']}.docx"
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
    
    async def handle_view_language_selection(self, msg, query_data):
        """Handle viewing article in another language"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Extract target language from callback data
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
        self.language = target_lang
        
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
    
    async def handle_translate_selection(self, msg, query_data):
        """Handle translation of article to selected language"""
        chat_id = msg['message']['chat']['id']
        message_id = msg['message']['message_id']
        
        # Extract target language from callback data
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
        
        # Get source language
        source_lang = user_data.get('language', DEFAULT_LANGUAGE)
        
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
    
    async def handle_new_search(self, msg):
        """Handle new search button click"""
        chat_id = msg['message']['chat']['id']
        
        # Get current language
        if chat_id in user_data_cache:
            language = user_data_cache[chat_id].get('language', DEFAULT_LANGUAGE)
        else:
            language = DEFAULT_LANGUAGE
            
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
                (chat_id, msg['message']['message_id']),
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
        
        # Update the state for the chat handler
        for handler in self.bot._router._handlers:
            if isinstance(handler, BotHandler) and handler.chat_id == chat_id:
                handler.state = SELECTING_LANGUAGE
                break
                
    async def handle_try_again(self, msg):
        """Handle try again button click"""
        chat_id = msg['message']['chat']['id']
        
        # Get user data
        if chat_id not in user_data_cache:
            user_data_cache[chat_id] = {}
            
        user_data = user_data_cache[chat_id]
        language = user_data.get('language', DEFAULT_LANGUAGE)
        
        # Prompt for a new search
        try:
            await self.bot.editMessageText(
                (chat_id, msg['message']['message_id']),
                f"Please enter a new search query (language: {get_language_name(language)}):"
            )
        except telepot.exception.TelegramError:
            # If we can't edit the message, send a new one
            await self.bot.sendMessage(
                chat_id,
                f"Please enter a new search query (language: {get_language_name(language)}):"
            )
        
        # Update the state for the chat handler
        for handler in self.bot._router._handlers:
            if isinstance(handler, BotHandler) and handler.chat_id == chat_id:
                handler.state = SEARCHING
                break
                
    async def handle_back_to_article(self, msg):
        """Navigate back to article summary view"""
        chat_id = msg['message']['chat']['id']
        
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
            
        # Get language
        language = user_data.get('language', DEFAULT_LANGUAGE)
        
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
        available_languages = article.get('available_languages', {})
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
                (chat_id, msg['message']['message_id']),
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
    
    async def handle_download_translation(self, msg):
        """Generate and send a document with the translated article"""
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
                    document=doc_file,
                    filename=f"{translated_article['title']}_{target_lang}.docx"
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
    
    async def handle_back_to_translation(self, msg):
        """Return to the translation summary view"""
        chat_id = msg['message']['chat']['id']
        
        # Get user data
        if chat_id not in user_data_cache:
            await self.bot.sendMessage(
                chat_id,
                "Session expired. Please start a new search with /start."
            )
            return
            
        user_data = user_data_cache[chat_id]
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
                (chat_id, msg['message']['message_id']),
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