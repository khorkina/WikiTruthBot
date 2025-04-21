"""
Module for handling Wikipedia article data and operations
"""

import os
import logging
import urllib.parse

from config import LANGUAGE_NAMES
from wiki_utils import (
    get_wikipedia_search_results,
    get_article_content,
    get_available_languages,
    get_article_in_language,
    translate_text
)

def get_language_name(lang_code):
    """Get language name from language code"""
    return LANGUAGE_NAMES.get(lang_code, lang_code.upper())

def search_wikipedia(query, language="en"):
    """
    Search Wikipedia for articles in the specified language
    
    Args:
        query (str): Search query
        language (str): Language code (e.g., 'en', 'es')
        
    Returns:
        list: List of article titles
    """
    return get_wikipedia_search_results(query, language)

def get_wikipedia_article(title, language="en"):
    """
    Get article content from Wikipedia
    
    Args:
        title (str): Article title
        language (str): Language code
        
    Returns:
        dict: Article content or None if not found
    """
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
    """
    Get the article in another available language
    
    Args:
        title (str): Article title in target language
        target_lang (str): Target language code
        
    Returns:
        dict: Article in target language or None if not available
    """
    # Get article in the target language (using title already in target language)
    article = get_article_in_language(title, target_lang)
    
    if not article:
        return None
    
    # Get available languages for this article
    available_languages = get_available_languages(title, target_lang)
    
    # Add available languages to article data
    article['available_languages'] = available_languages
    
    return article

def translate_article_content(article, from_lang, to_lang):
    """
    Translate article content from one language to another
    
    Args:
        article (dict): Article content dictionary
        from_lang (str): Source language code
        to_lang (str): Target language code
        
    Returns:
        dict: Article with translated content
    """
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
        logging.error(f"Translation error: {str(e)}")
        return None

def get_article_sharing_link(title, lang):
    """
    Generate a Wikipedia sharing link for the article
    
    Args:
        title (str): Article title
        lang (str): Language code
        
    Returns:
        str: Wikipedia URL for the article
    """
    try:
        # Create Wikipedia URL
        encoded_title = urllib.parse.quote(title.replace(' ', '_'))
        article_url = f"https://{lang}.wikipedia.org/wiki/{encoded_title}"
        
        return article_url
    except Exception as e:
        logging.error(f"Error generating article link: {str(e)}")
        return None