"""
Stream context management service for Bot Listener System
"""
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("bot_listener")


class StreamContextService:
    """Manages stream contexts for different streams"""
    
    def __init__(self, max_message_history: int = 10):
        """
        Initialize stream context service
        
        Args:
            max_message_history: Maximum number of messages to keep in history
        """
        self.max_message_history = max_message_history
        self.stream_contexts: Dict[str, Dict[str, Any]] = {}
        self.default_stream_id = "default"
        
        # Initialize default context
        self._init_context(self.default_stream_id)
    
    def _init_context(self, stream_id: str) -> None:
        """
        Initialize a new stream context
        
        Args:
            stream_id: Stream ID
        """
        self.stream_contexts[stream_id] = {
            "title": "Test Stream",
            "start_time": time.time(),
            "duration": 0,
            "topics": [],
            "mood": "neutral",
            "previous_messages": [],  # Store previous messages
            "viewers": 0,             # Viewer count
            "broadcaster_info": {},   # Broadcaster information
            "message_count": 0        # Message count
        }
    
    def get_context(self, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get stream context
        
        Args:
            stream_id: Stream ID (default: default_stream_id)
            
        Returns:
            dict: Stream context
        """
        if stream_id is None:
            stream_id = self.default_stream_id
        
        # Create context if it doesn't exist
        if stream_id not in self.stream_contexts:
            self._init_context(stream_id)
        
        # Update duration
        ctx = self.stream_contexts[stream_id]
        if ctx["start_time"]:
            ctx["duration"] = time.time() - ctx["start_time"]
        
        return ctx
    
    def update_title(self, title: str, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Update stream title
        
        Args:
            title: New title
            stream_id: Stream ID (default: default_stream_id)
            
        Returns:
            dict: Updated stream context
        """
        if stream_id is None:
            stream_id = self.default_stream_id
        
        ctx = self.get_context(stream_id)
        ctx["title"] = title
        
        # Extract topics from title
        keywords = [word.lower() for word in title.split() if len(word) > 2]
        # Merge with existing topics, avoiding duplicates
        ctx["topics"] = list(set(ctx["topics"] + keywords))
        
        return ctx
    
    def add_message(self, message: str, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Add message to stream context
        
        Args:
            message: Message to add
            stream_id: Stream ID (default: default_stream_id)
            
        Returns:
            dict: Updated stream context
        """
        if stream_id is None:
            stream_id = self.default_stream_id
        
        ctx = self.get_context(stream_id)
        
        # Increment message count
        ctx["message_count"] += 1
        
        # Add message to history (keep last 10)
        ctx["previous_messages"].append(message)
        if len(ctx["previous_messages"]) > 10:
            ctx["previous_messages"] = ctx["previous_messages"][-10:]
        
        return ctx
    
    def update_viewers(self, count: int, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Update viewer count
        
        Args:
            count: New viewer count
            stream_id: Stream ID (default: default_stream_id)
            
        Returns:
            dict: Updated stream context
        """
        if stream_id is None:
            stream_id = self.default_stream_id
        
        ctx = self.get_context(stream_id)
        ctx["viewers"] = count
        
        return ctx
    
    def reset_context(self, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Reset stream context
        
        Args:
            stream_id: Stream ID (default: default_stream_id)
            
        Returns:
            dict: New stream context
        """
        if stream_id is None:
            stream_id = self.default_stream_id
        
        self._init_context(stream_id)
        
        return self.get_context(stream_id)
    
    def analyze_mood(self, content: str, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze mood from content
        
        Args:
            content: Content to analyze
            stream_id: Stream ID (default: default_stream_id)
            
        Returns:
            dict: Updated stream context
        """
        if stream_id is None:
            stream_id = self.default_stream_id
        
        ctx = self.get_context(stream_id)
        
        # Simple sentiment analysis
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
            ctx["mood"] = "excited"
        elif positive_count > negative_count:
            ctx["mood"] = "positive"
        elif negative_count > positive_count:
            ctx["mood"] = "negative"
        else:
            # Reset mood occasionally to avoid getting stuck
            if ctx["message_count"] % 5 == 0:
                ctx["mood"] = "neutral"
        
        return ctx