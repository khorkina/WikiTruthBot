"""
Module for generating document files from Wikipedia articles
"""

import os
import re
import tempfile
import logging
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from wiki_utils import split_content_into_sections

def create_document_from_article(article, language):
    """
    Create a Word document from a Wikipedia article
    
    Args:
        article (dict): Article content dictionary
        language (str): Language code
        
    Returns:
        str: Path to the generated document file
    """
    if not article:
        return None
    
    try:
        # Create a new document
        doc = Document()
        
        # Set document properties
        doc.core_properties.title = article['title']
        doc.core_properties.language = language
        
        # Add title
        title = doc.add_heading(article['title'], 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add source information
        source_para = doc.add_paragraph()
        source_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        source_para.add_run(f"Source: {article['url']}").italic = True
        
        # Add summary section
        doc.add_heading('Summary', 1)
        doc.add_paragraph(article['summary'])
        
        # Add a page break before the full content
        doc.add_page_break()
        
        # Split content into sections for better formatting
        sections = split_content_into_sections(article['content'])
        
        # Process each section
        for section in sections:
            if section['title']:
                # Calculate heading level (1-3)
                level = min(section['level'] - 1, 2) if section['level'] > 0 else 1
                doc.add_heading(section['title'], level)
            
            # Add section content
            content = section['content']
            
            # Split into paragraphs
            paragraphs = content.split('\n\n')
            for para_text in paragraphs:
                if para_text.strip():
                    doc.add_paragraph(para_text.strip())
        
        # Generate a temporary file for the document
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
        doc_path = temp_file.name
        temp_file.close()
        
        # Save the document
        doc.save(doc_path)
        
        return doc_path
        
    except Exception as e:
        logging.error(f"Error generating document: {str(e)}")
        return None