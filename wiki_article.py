"""
Module for handling Wikipedia article data and operations
"""

import json
import os
import logging
from datetime import datetime
import urllib.parse

# Import functions from provided wiki_utils.py
from wiki_utils import (
    get_wikipedia_search_results,
    get_article_content,
    get_available_languages,
    get_article_in_language,
    translate_text,
    split_content_into_sections
)

from config import LANGUAGE_NAMES

def get_language_name(lang_code):
    """Get language name from language code"""
    return LANGUAGE_NAMES.get(lang_code, lang_code)

def search_wikipedia(query, language="en"):
    """
    Search Wikipedia for articles in the specified language
    
    Args:
        query (str): Search query
        language (str): Language code (e.g., 'en', 'es')
        
    Returns:
        list: List of article titles
    """
    if not query:
        return []
    
    try:
        return get_wikipedia_search_results(query, language)
    except Exception as e:
        logging.error(f"Error searching Wikipedia: {str(e)}")
        return []

def get_wikipedia_article(title, language="en"):
    """
    Get article content from Wikipedia
    
    Args:
        title (str): Article title
        language (str): Language code
        
    Returns:
        dict: Article content or None if not found
    """
    if not title:
        return None
    
    try:
        article = get_article_content(title, language)
        if article:
            # Get available languages for this article
            available_langs = get_available_languages(title, language)
            article['available_languages'] = available_langs
            
            # Split content into sections for better display
            sections = split_content_into_sections(article['content'])
            article['sections'] = sections
            
            return article
        return None
    except Exception as e:
        logging.error(f"Error getting Wikipedia article: {str(e)}")
        return None

def get_article_in_other_language(title, source_lang, target_lang):
    """
    Get the article in another available language
    
    Args:
        title (str): Article title in source language
        source_lang (str): Source language code
        target_lang (str): Target language code
        
    Returns:
        dict: Article in target language or None if not available
    """
    try:
        # First get available languages for this article
        available_langs = get_available_languages(title, source_lang)
        
        if target_lang in available_langs:
            # Get the article title in target language
            target_title = available_langs[target_lang]
            return get_article_content(target_title, target_lang)
        else:
            return None
    except Exception as e:
        logging.error(f"Error getting article in other language: {str(e)}")
        return None

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
    if not article or from_lang == to_lang:
        return article
    
    try:
        # Create a copy of the article
        translated_article = dict(article)
        
        # Translate title
        translated_article['title'] = translate_text(article['title'], to_lang, from_lang)
        
        # Translate summary
        translated_article['summary'] = translate_text(article['summary'], to_lang, from_lang)
        
        # Translate sections if they exist
        if 'sections' in article and article['sections']:
            translated_sections = []
            for section in article['sections']:
                translated_section = dict(section)
                if section.get('title'):
                    translated_section['title'] = translate_text(section['title'], to_lang, from_lang)
                translated_section['content'] = translate_text(section['content'], to_lang, from_lang)
                translated_sections.append(translated_section)
            
            translated_article['sections'] = translated_sections
        
        return translated_article
    except Exception as e:
        logging.error(f"Error translating article: {str(e)}")
        return article

def get_article_sharing_link(title, lang):
    """
    Generate a Wikipedia sharing link for the article
    
    Args:
        title (str): Article title
        lang (str): Language code
        
    Returns:
        str: Wikipedia URL for the article
    """
    if not title:
        return None
    
    try:
        # Create Wikipedia URL
        encoded_title = urllib.parse.quote(title.replace(' ', '_'))
        article_url = f"https://{lang}.wikipedia.org/wiki/{encoded_title}"
        return article_url
    except Exception as e:
        logging.error(f"Error generating article link: {str(e)}")
        return None
