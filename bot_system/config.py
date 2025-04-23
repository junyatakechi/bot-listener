"""
Configuration module for Bot Listener System
"""
import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel
from functools import lru_cache

# Load environment variables
load_dotenv()


class Settings(BaseModel):
    """Settings model"""
    # API settings
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    
    # OpenAI settings
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    # Logging settings
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Application settings
    max_message_history: int = int(os.getenv("MAX_MESSAGE_HISTORY", "10"))
    max_bot_viewers: int = int(os.getenv("MAX_BOT_VIEWERS", "100"))
    heartbeat_interval: int = int(os.getenv("HEARTBEAT_INTERVAL", "30"))


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings
    
    Returns:
        Settings: Application settings
    """
    return Settings()


def setup_logging(name: str) -> logging.Logger:
    """
    Setup logging configuration
    
    Args:
        name: Logger name
        
    Returns:
        logging.Logger: Configured logger
    """
    log_level = get_settings().log_level
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create logger
    logger = logging.getLogger(name)
    
    return logger