"""
Stream context models for Bot Listener System
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import time


class StreamContext(BaseModel):
    """Stream context model"""
    title: str = "Test Stream"
    start_time: float = Field(default_factory=time.time)
    duration: float = 0
    topics: List[str] = Field(default_factory=list)
    mood: str = "neutral"
    previous_messages: List[str] = Field(default_factory=list)
    viewers: int = 0
    broadcaster_info: Dict[str, Any] = Field(default_factory=dict)
    message_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.model_dump()
    
    def update_duration(self) -> float:
        """Update and return the current duration"""
        self.duration = time.time() - self.start_time
        return self.duration
    
    def add_message(self, message: str) -> None:
        """Add a message to the stream context"""
        self.message_count += 1
        self.previous_messages.append(message)
        
        # Keep only the last 10 messages
        if len(self.previous_messages) > 10:
            self.previous_messages = self.previous_messages[-10:]
    
    def extract_topics_from_title(self) -> List[str]:
        """Extract topics from the stream title"""
        # Simple keyword extraction - can be improved with NLP
        keywords = [word.lower() for word in self.title.split() if len(word) > 2]
        # Merge with existing topics, avoiding duplicates
        self.topics = list(set(self.topics + keywords))
        return self.topics