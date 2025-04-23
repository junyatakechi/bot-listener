"""
Message models for Bot Listener System
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union
import json
import time


class BaseMessage(BaseModel):
    """Base message model for all message types"""
    type: str
    timestamp: float = Field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.model_dump()
    
    @classmethod
    def parse_raw_or_text(cls, data: str) -> 'BaseMessage':
        """Parse JSON data or treat as plain text"""
        try:
            return cls.model_validate_json(data)
        except Exception:
            # Fallback to plain text
            if cls == StreamContent:
                return StreamContent(
                    type="stream_content",
                    content=data,
                    timestamp=time.time()
                )
            elif cls == BotReaction:
                return BotReaction(
                    type="heartbeat",  # Default to heartbeat for unparseable bot messages
                    content="",
                    timestamp=time.time()
                )
            else:
                return cls(type="unknown", content=data)


class SystemMessage(BaseMessage):
    """System message model"""
    type: str = "system_info"
    message: str
    timestamp: float = Field(default_factory=time.time)


class StreamContent(BaseMessage):
    """Stream content message model"""
    type: str = "stream_content"
    content: str
    command: Optional[str] = None
    stream_info: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BotReaction(BaseMessage):
    """Bot reaction message model"""
    type: str = "bot_reaction"
    content: str = ""
    bot_info: Dict[str, Any] = Field(default_factory=dict)
    ai_generated: bool = False


class ViewerUpdate(BaseMessage):
    """Viewer update message model"""
    type: str = "viewer_update"
    count: int
    event: str  # "join" or "leave"