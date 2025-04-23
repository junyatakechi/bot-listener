"""
Connection management service for Bot Listener System
"""
import json
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger("bot_listener")


class ConnectionService:
    """Manages WebSocket connections for broadcasters and bot viewers"""
    
    def __init__(self, max_bot_viewers: int = 100, heartbeat_interval: int = 30):
        """
        Initialize connection service
        
        Args:
            max_bot_viewers: Maximum number of bot viewers allowed
            heartbeat_interval: Interval for heartbeat messages in seconds
        """
        self.max_bot_viewers = max_bot_viewers
        self.heartbeat_interval = heartbeat_interval
        self.broadcaster: Optional[WebSocket] = None
        self.bot_viewers: List[WebSocket] = []
        self.bot_info: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect_broadcaster(self, websocket: WebSocket) -> bool:
        """
        Connect broadcaster
        
        Args:
            websocket: WebSocket connection
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        if self.broadcaster:
            await websocket.close(code=1000, reason="Another broadcaster is already connected")
            return False
        
        await websocket.accept()
        self.broadcaster = websocket
        logger.info("Broadcaster connected")
        return True
    
    async def disconnect_broadcaster(self) -> None:
        """Disconnect broadcaster"""
        self.broadcaster = None
        logger.info("Broadcaster disconnected")
    
    async def connect_bot_viewer(self, websocket: WebSocket) -> bool:
        """
        Connect bot viewer
        
        Args:
            websocket: WebSocket connection
            
        Returns:
            bool: True if connection successful
        """
        await websocket.accept()
        self.bot_viewers.append(websocket)
        self.bot_info[websocket] = {"connected_at": time.time()}
        logger.info(f"Bot viewer connected (total: {len(self.bot_viewers)})")
        return True
    
    async def disconnect_bot_viewer(self, websocket: WebSocket) -> None:
        """
        Disconnect bot viewer
        
        Args:
            websocket: WebSocket connection
        """
        if websocket in self.bot_viewers:
            self.bot_viewers.remove(websocket)
        
        if websocket in self.bot_info:
            del self.bot_info[websocket]
        
        logger.info(f"Bot viewer disconnected (remaining: {len(self.bot_viewers)})")
    
    async def broadcast_to_bots(self, message: dict) -> None:
        """
        Broadcast message to all connected bot viewers
        
        Args:
            message: Message to broadcast
        """
        if not self.bot_viewers:
            logger.warning("No bot viewers connected")
            return
        
        tasks = [self.send_to_bot(bot, message) for bot in self.bot_viewers]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_to_bot(self, bot: WebSocket, message: dict) -> None:
        """
        Send message to a specific bot viewer
        
        Args:
            bot: Bot WebSocket connection
            message: Message to send
        """
        try:
            await bot.send_text(json.dumps(message, ensure_ascii=True))
        except Exception as e:
            logger.error(f"Error sending to bot: {e}")
            # Try to disconnect the bot if there was an error
            try:
                await self.disconnect_bot_viewer(bot)
            except:
                pass
    
    async def send_to_broadcaster(self, message: dict) -> None:
        """
        Send message to broadcaster
        
        Args:
            message: Message to send
        """
        if not self.broadcaster:
            logger.warning("No broadcaster connected")
            return
        
        try:
            await self.broadcaster.send_text(json.dumps(message, ensure_ascii=True))
        except Exception as e:
            logger.error(f"Error sending to broadcaster: {e}")
            # Try to disconnect the broadcaster if there was an error
            try:
                await self.disconnect_broadcaster()
            except:
                pass
    
    def update_bot_info(self, websocket: WebSocket, info: dict) -> None:
        """
        Update bot information
        
        Args:
            websocket: Bot WebSocket connection
            info: Bot information
        """
        if websocket in self.bot_info:
            self.bot_info[websocket].update(info)
    
    def get_bot_count(self) -> int:
        """
        Get the number of connected bot viewers
        
        Returns:
            int: Number of connected bot viewers
        """
        return len(self.bot_viewers)
    
    def get_bot_info(self, websocket: WebSocket) -> Dict[str, Any]:
        """
        Get bot information
        
        Args:
            websocket: Bot WebSocket connection
            
        Returns:
            dict: Bot information
        """
        return self.bot_info.get(websocket, {})