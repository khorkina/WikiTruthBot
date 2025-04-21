"""
WikiSearch Telegram Bot

A Telegram bot for searching, viewing, translating, and downloading
Wikipedia articles in multiple languages.
"""

import os
import logging
import time
import asyncio
import telepot
from telepot.aio.loop import MessageLoop
from telepot.aio.delegate import pave_event_space, per_chat_id, create_open, per_callback_query_origin
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

from handlers import (
    BotHandler,
    CallbackQueryHandler
)
from config import TELEGRAM_BOT_TOKEN, logger

# Check if token is available
if not TELEGRAM_BOT_TOKEN:
    logger.error("No bot token provided. Set the TELEGRAM_BOT_TOKEN environment variable.")
    exit(1)

def main():
    """Start the bot"""
    # Create the bot instance
    bot = telepot.aio.DelegatorBot(TELEGRAM_BOT_TOKEN, [
        pave_event_space()(
            per_chat_id(), create_open, BotHandler, timeout=120
        ),
        pave_event_space()(
            per_callback_query_origin(), create_open, CallbackQueryHandler, timeout=120
        ),
    ])
    
    # Start the bot
    logger.info("Starting WikiSearch Telegram Bot")
    
    loop = asyncio.get_event_loop()
    loop.create_task(MessageLoop(bot).run_forever())
    
    # Keep the program running
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        loop.close()

if __name__ == "__main__":
    main()
