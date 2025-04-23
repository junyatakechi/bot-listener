#!/usr/bin/env python3
"""
Bot Listener System Test Clients
-------------------------------
* Python 3.9+ recommended
* Dependencies: websockets, argparse, colorama
* Usage:
  - Broadcaster client: python test_clients.py broadcaster
  - Bot viewer client: python test_clients.py bot-viewer
  - Multiple bot simulation: python test_clients.py multi-bot --bots 5
"""

import asyncio
import sys
import os
import argparse
import websockets
import json
import time
import uuid
import random
from typing import List, Dict, Any, Optional
import logging
from colorama import init, Fore, Style

# Initialize colorama for cross-platform colored output
init()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("bot_client")


class BroadcasterClient:
    """Broadcaster client for Bot Listener System"""
    
    def __init__(self, uri: str):
        """
        Initialize broadcaster client
        
        Args:
            uri: WebSocket URI
        """
        self.uri = uri
        self.broadcaster_id = str(uuid.uuid4())
        self.stream_title = "Test Stream"
        self.stream_id = str(uuid.uuid4())
    
    async def run(self):
        """Run broadcaster client"""
        # Get stream title from user
        self.stream_title = input("Enter stream title: ")
        if not self.stream_title.strip():
            self.stream_title = "Test Stream"  # Default title
        
        print(f"{Fore.GREEN}🎬 Stream title: {self.stream_title}{Style.RESET_ALL}")
        
        async with websockets.connect(self.uri) as ws:
            print(f"{Fore.GREEN}✅ Connected as broadcaster to: {self.uri}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}👉 Enter stream content and press Enter. Ctrl+D / Ctrl+C to exit.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💡 Commands: /title <new title> (change title), /viewers (check viewer count){Style.RESET_ALL}\n")
            
            # Start receiver task
            receiver_task = asyncio.create_task(self._receive_messages(ws))
            
            # Start sender loop
            await self._send_messages(ws)
            
            # Clean up
            receiver_task.cancel()
            await ws.close()
            print(f"\n{Fore.RED}🔌 Stream ended, disconnected.{Style.RESET_ALL}")
    
    async def _receive_messages(self, ws: websockets.WebSocketClientProtocol):
        """
        Receive and process messages
        
        Args:
            ws: WebSocket connection
        """
        try:
            async for msg in ws:
                try:
                    # Parse JSON response
                    data = json.loads(msg)
                    
                    # Display bot reactions
                    if data.get("type") == "bot_reaction":
                        bot_name = data.get("bot_info", {}).get("name", "Anonymous Bot")
                        personality = data.get("bot_info", {}).get("personality_type", "")
                        content = data.get("content", "")
                        print(f"\r{Fore.MAGENTA}👤 {bot_name}({personality}): {content}{Style.RESET_ALL}\n> ", end="", flush=True)
                    
                    # Display viewer updates
                    elif data.get("type") == "viewer_update":
                        count = data.get("count", 0)
                        event = data.get("event", "")
                        if event == "join":
                            print(f"\r{Fore.CYAN}👥 New viewer joined (total: {count}){Style.RESET_ALL}\n> ", end="", flush=True)
                        elif event == "leave":
                            print(f"\r{Fore.YELLOW}👋 Viewer left (total: {count}){Style.RESET_ALL}\n> ", end="", flush=True)
                    
                    # Display system info
                    elif data.get("type") == "system_info":
                        print(f"\r{Fore.BLUE}📢 System: {data.get('message', '')}{Style.RESET_ALL}\n> ", end="", flush=True)
                    
                    # Display other messages in debug mode
                    else:
                        if os.environ.get("DEBUG") == "1":
                            print(f"\r{Fore.WHITE}🔄 Received: {json.dumps(data, ensure_ascii=False, indent=2)}{Style.RESET_ALL}\n> ", end="", flush=True)
                
                except json.JSONDecodeError:
                    print(f"\r{Fore.WHITE}🔄 Received: {msg}{Style.RESET_ALL}\n> ", end="", flush=True)
        
        except websockets.ConnectionClosedOK:
            print(f"\n{Fore.YELLOW}👋 Server closed the connection.{Style.RESET_ALL}")
        
        except Exception as e:
            print(f"\n{Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
    
    async def _send_messages(self, ws: websockets.WebSocketClientProtocol):
        """
        Send messages from user input
        
        Args:
            ws: WebSocket connection
        """
        loop = asyncio.get_running_loop()
        
        try:
            while True:
                # Get user input
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:  # EOF (Ctrl+D)
                    break
                
                # Check for special commands
                if line.startswith("/title "):
                    # Title change command
                    new_title = line[7:].strip()
                    if new_title:
                        self.stream_title = new_title
                        print(f"{Fore.GREEN}🎬 Changed stream title to: {self.stream_title}{Style.RESET_ALL}")
                    continue
                
                elif line.strip() == "/viewers":
                    # Viewer count command
                    await ws.send(json.dumps({"command": "get_viewers"}, ensure_ascii=True))
                    continue
                
                # Prepare stream data with metadata
                stream_data = {
                    "content": line.rstrip("\n"),
                    "metadata": {
                        "timestamp": time.time(),
                        "stream_id": self.stream_id,
                        "broadcaster_id": self.broadcaster_id,
                        "stream_title": self.stream_title,
                        "language": "ja"
                    }
                }
                
                # Send to server
                await ws.send(json.dumps(stream_data, ensure_ascii=True))
                print("> ", end="", flush=True)
        
        except KeyboardInterrupt:
            pass


class BotViewerClient:
    """Bot viewer client for Bot Listener System"""
    
    def __init__(self, uri: str, bot_id: Optional[str] = None):
        """
        Initialize bot viewer client
        
        Args:
            uri: WebSocket URI
            bot_id: Bot ID (optional)
        """
        self.uri = uri
        self.bot_id = bot_id or str(uuid.uuid4())
        
        # Generate random bot personality
        self.personality = self._generate_personality()
        
        # Print bot info
        personality_type = self.personality["personality_type"]
        interests = ", ".join(self.personality["interests"])
        emoji_usage = self.personality["emoji_usage"]
        print(f"{Fore.CYAN}🤖 Bot personality: {personality_type}, Interests: {interests}, Emoji usage: {emoji_usage}{Style.RESET_ALL}")
    
    def _generate_personality(self) -> Dict[str, Any]:
        """
        Generate random bot personality
        
        Returns:
            Dict[str, Any]: Bot personality
        """
        # Available personality types
        personality_types = ["enthusiastic", "critical", "curious", "shy", "funny", "technical", "supportive"]
        
        # Available interest sets
        interests = [
            ["Technology", "Games", "Music"],
            ["Anime", "Manga", "Movies"],
            ["Programming", "AI", "Machine Learning"],
            ["Sports", "Health", "Cooking"],
            ["Science", "Space", "History"]
        ]
        
        # Emoji usage levels
        emoji_usage = ["high", "medium", "low"]
        
        # Generate random personality
        return {
            "id": self.bot_id,
            "name": f"BotViewer_{self.bot_id[:6]}",
            "personality_type": random.choice(personality_types),
            "interests": random.choice(interests),
            "emoji_usage": random.choice(emoji_usage)
        }
    
    async def run(self):
        """Run bot viewer client"""
        async with websockets.connect(self.uri) as ws:
            print(f"{Fore.GREEN}✅ Connected as bot viewer to: {self.uri}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Waiting for stream content... (Ctrl+C to exit){Style.RESET_ALL}\n")
            
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(self._send_heartbeat(ws))
            
            try:
                # Receive and process messages
                async for msg in ws:
                    try:
                        # Parse received message
                        data = json.loads(msg)
                        
                        # Handle stream content
                        if "type" in data and data["type"] == "stream_content":
                            print(f"\r{Fore.YELLOW}📺 Stream content: {data['content']}{Style.RESET_ALL}")
                            
                            # Send AI generation request
                            ai_request = {
                                "type": "receive_stream_content",
                                "content": data['content'],
                                "bot_info": self.personality,
                                "timestamp": time.time()
                            }
                            
                            # Send request
                            await ws.send(json.dumps(ai_request, ensure_ascii=True))
                            print(f"{Fore.BLUE}🔄 Sent AI generation request...{Style.RESET_ALL}")
                        
                        # Handle AI-generated reaction
                        elif "type" in data and data["type"] == "reaction" and data.get("ai_generated", False):
                            print(f"{Fore.GREEN}🤖 AI-generated reaction: {data['content']}{Style.RESET_ALL}")
                        
                        # Handle other messages
                        else:
                            print(f"\r{Fore.WHITE}📩 Received: {json.dumps(data, ensure_ascii=False, indent=2)}{Style.RESET_ALL}")
                    
                    except json.JSONDecodeError:
                        print(f"\r{Fore.WHITE}📩 Received: {msg}{Style.RESET_ALL}")
            
            except websockets.ConnectionClosedOK:
                print(f"\n{Fore.YELLOW}👋 Server closed the connection.{Style.RESET_ALL}")
            
            except KeyboardInterrupt:
                pass
            
            # Clean up
            heartbeat_task.cancel()
            await ws.close()
            print(f"\n{Fore.RED}🔌 Disconnected.{Style.RESET_ALL}")
    
    async def _send_heartbeat(self, ws: websockets.WebSocketClientProtocol):
        """
        Send periodic heartbeat messages
        
        Args:
            ws: WebSocket connection
        """
        while True:
            try:
                # Send heartbeat with bot info
                await ws.send(json.dumps({
                    "type": "heartbeat", 
                    "bot_info": self.personality
                }, ensure_ascii=True))
                
                # Wait for next heartbeat
                await asyncio.sleep(30)  # 30 seconds between heartbeats
            except Exception:
                # Stop on any error
                break


async def run_multiple_bots(uri: str, num_bots: int):
    """
    Run multiple bot viewer clients
    
    Args:
        uri: WebSocket URI
        num_bots: Number of bots to run
    """
    print(f"{Fore.GREEN}✅ Simulating {num_bots} bot viewers...{Style.RESET_ALL}")
    
    # Create tasks for each bot
    tasks = []
    for i in range(num_bots):
        # Create unique URI with bot ID
        bot_uri = f"{uri}?bot_id={i+1}"
        bot_id = f"bot_{i+1}_{uuid.uuid4().hex[:6]}"
        
        # Create and run bot
        bot = BotViewerClient(bot_uri, bot_id)
        tasks.append(asyncio.create_task(bot.run()))
    
    try:
        # Wait for all bots to complete
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        # Cancel all tasks on interrupt
        for task in tasks:
            task.cancel()
        
        # Wait for tasks to cancel
        await asyncio.gather(*tasks, return_exceptions=True)
        print(f"\n{Fore.RED}🔌 All bots disconnected.{Style.RESET_ALL}")


def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Bot Listener System Test Clients")
    parser.add_argument(
        "client_type",
        choices=["broadcaster", "bot-viewer", "multi-bot"],
        help="Client type: broadcaster, bot-viewer, or multi-bot"
    )
    parser.add_argument(
        "--uri",
        default="ws://localhost:8000/",
        help="Base WebSocket URI (e.g., ws://example.com/)"
    )
    parser.add_argument(
        "--bots",
        type=int,
        default=3,
        help="Number of bots to simulate in multi-bot mode"
    )
    
    args = parser.parse_args()
    
    # Set full URI based on client type
    if args.client_type == "broadcaster":
        full_uri = f"{args.uri}broadcaster"
        # Create and run broadcaster client
        broadcaster = BroadcasterClient(full_uri)
        asyncio.run(broadcaster.run())
    
    elif args.client_type == "bot-viewer":
        full_uri = f"{args.uri}bot-viewer"
        # Create and run bot viewer client
        bot_viewer = BotViewerClient(full_uri)
        asyncio.run(bot_viewer.run())
    
    elif args.client_type == "multi-bot":
        full_uri = f"{args.uri}bot-viewer"
        # Run multiple bot viewers
        asyncio.run(run_multiple_bots(full_uri, args.bots))


if __name__ == "__main__":
    main()