"""Text cleaning and normalization utilities for document processing."""

import re
from typing import Optional


def clean_text(text: Optional[str]) -> str:
    """Clean and normalize text content.

    This function performs the following operations:
    1. Handles None/empty input
    2. Normalizes whitespace (spaces, tabs, etc.) to single spaces
    3. Removes control characters (except newlines)
    4. Normalizes excessive line breaks (max 2 consecutive newlines)
    5. Strips leading/trailing whitespace

    Args:
        text: The text to clean. Can be None.

    Returns:
        Cleaned and normalized text string.

    Examples:
        >>> clean_text("Hello   world")
        'Hello world'
        >>> clean_text("Line 1\\n\\n\\n\\nLine 2")
        'Line 1\\n\\nLine 2'
    """
    if not text:
        return ""

    # Normalize whitespace (spaces, tabs, etc.) to single spaces
    # This preserves newlines while normalizing other whitespace
    text = re.sub(r'[ \t]+', ' ', text)

    # Remove control characters except newlines
    # \x00-\x08: NULL through BACKSPACE
    # \x0b: VERTICAL TAB (we keep \x0a which is newline)
    # \x0c: FORM FEED
    # \x0e-\x1f: SHIFT OUT through UNIT SEPARATOR
    # \x7f-\x9f: DELETE and C1 control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # Remove surrogate characters (invalid in UTF-8)
    # \ud800-\udfff: UTF-16 surrogates that cannot be encoded in UTF-8
    # These can appear in malformed PDFs or HTML content
    text = re.sub(r'[\ud800-\udfff]', '', text)

    # Normalize line breaks - reduce 3+ consecutive newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def count_tokens(text: Optional[str]) -> int:
    """Approximate token count for text.

    Uses a simple heuristic: word count * 1.3
    This provides a rough approximation for OpenAI-style tokenization.

    Args:
        text: The text to count tokens for. Can be None.

    Returns:
        Approximate token count as an integer.

    Examples:
        >>> count_tokens("Hello world test")
        3
        >>> count_tokens("This is a test sentence.")
        6
    """
    if not text:
        return 0

    # Count words (split on whitespace)
    words = len(text.split())

    # Apply 1.3 multiplier and convert to int
    return int(words * 1.3)
