"""
Utility functions for Bot Listener System
"""
import json
import time
from typing import Dict, Any, List, Optional, Union
import logging
import random
import asyncio

logger = logging.getLogger("bot_listener")


def sanitize_text(text: Union[str, Any]) -> str:
    """
    Sanitize text to handle Unicode and encoding issues
    
    Args:
        text: Text to sanitize
        
    Returns:
        str: Sanitized text
    """
    if not isinstance(text, str):
        return str(text)
    
    # Escape non-ASCII characters
    return text.encode('ascii', 'backslashreplace').decode('ascii')


def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """
    Extract keywords from text
    
    Args:
        text: Text to extract keywords from
        min_length: Minimum keyword length
        
    Returns:
        List[str]: Extracted keywords
    """
    if not text:
        return []
    
    # Simple word extraction, could be improved with NLP
    words = text.lower().split()
    keywords = [word for word in words if len(word) >= min_length]
    
    return keywords


def generate_unique_id(prefix: str = "") -> str:
    """
    Generate a unique ID
    
    Args:
        prefix: ID prefix
        
    Returns:
        str: Unique ID
    """
    import uuid
    
    unique_id = str(uuid.uuid4())
    if prefix:
        return f"{prefix}_{unique_id}"
    
    return unique_id


async def with_timeout(coro, timeout: float):
    """
    Run a coroutine with timeout
    
    Args:
        coro: Coroutine to run
        timeout: Timeout in seconds
        
    Returns:
        Any: Coroutine result or None if timeout
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Operation timed out after {timeout} seconds")
        return None


def calculate_mood(content: str) -> str:
    """
    Calculate mood from content using simple word-based sentiment analysis
    
    Args:
        content: Content to analyze
        
    Returns:
        str: Detected mood
    """
    # Word lists for simple sentiment analysis
    positive_words = ["楽しい", "嬉しい", "面白い", "すごい", "好き", "最高", "happy", "fun", "great"]
    negative_words = ["難しい", "悲しい", "辛い", "苦しい", "嫌い", "最悪", "sad", "hard", "tough"]
    excited_words = ["わくわく", "興奮", "激アツ", "テンション", "excited", "amazing"]
    
    content_lower = content.lower()
    
    # Count sentiment words
    positive_count = sum([1 for word in positive_words if word in content_lower])
    negative_count = sum([1 for word in negative_words if word in content_lower])
    excited_count = sum([1 for word in excited_words if word in content_lower])
    
    # Determine mood
    if excited_count > 0:
        return "excited"
    elif positive_count > negative_count:
        return "positive"
    elif negative_count > positive_count:
        return "negative"
    else:
        return "neutral"


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to a human-readable string
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        str: Formatted duration
    """
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"