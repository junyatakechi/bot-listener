#!/usr/bin/env python3
"""
Bot Listener System Server
-------------------------
* Python 3.9+ recommended
* Dependencies: fastapi, uvicorn, websockets, openai, python-dotenv
* Start with: uvicorn bot_system.app:app --reload
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
import logging
import time
import uuid
import json

# Import local modules
from bot_system.services.connection_service import ConnectionService
from bot_system.services.context_service import StreamContextService
from bot_system.services.reaction_service import ReactionService
from bot_system.models.message import SystemMessage, StreamContent, BotReaction
from bot_system.config import setup_logging, get_settings

# Setup logging
logger = setup_logging("bot_listener")

# 設定を取得
settings = get_settings()

# サービスを初期化（必要な設定だけを渡す）
connection_service = ConnectionService(
    max_bot_viewers=settings.max_bot_viewers,
    heartbeat_interval=settings.heartbeat_interval
)

context_service = StreamContextService(
    max_message_history=settings.max_message_history
)

reaction_service = ReactionService(
    openai_api_key=settings.openai_api_key,
    openai_model=settings.openai_model
)


# FastAPI application
app = FastAPI(title="Bot Listener System")


# Broadcaster endpoint
@app.websocket("/broadcaster")
async def broadcaster_endpoint(websocket: WebSocket, background_tasks: BackgroundTasks):
    """Endpoint for broadcasters to connect and send stream content"""
    if not await connection_service.connect_broadcaster(websocket):
        return
    
    # Initialize stream
    stream_id = str(uuid.uuid4())
    stream_context = context_service.reset_context(stream_id)
    
    try:
        # Notify about current viewer count
        await connection_service.send_to_broadcaster(
            SystemMessage(
                message=f"Current bot viewers: {connection_service.get_bot_count()}",
                timestamp=time.time()
            ).to_dict()
        )
        
        # Message receiving loop
        while True:
            data = await websocket.receive_text()
            await process_broadcaster_message(data, stream_id)
    
    except WebSocketDisconnect:
        await connection_service.disconnect_broadcaster()
    except Exception as e:
        logger.error(f"Broadcaster endpoint error: {e}")
        await connection_service.disconnect_broadcaster()


async def process_broadcaster_message(data: str, stream_id: str):
    """Process messages from the broadcaster"""
    try:
        # Try to parse as JSON, fall back to plain text
        message_data = StreamContent.parse_raw_or_text(data)
        
        # Handle commands
        if command := message_data.command:
            await handle_broadcaster_command(command)
            return
        
        # Update stream context
        if title := message_data.metadata.get("stream_title"):
            context_service.update_title(title, stream_id)
        
        # Add message to context
        context_service.add_message(message_data.content, stream_id)
        
        # Analyze mood
        context_service.analyze_mood(message_data.content, stream_id)
        
        # Update viewer count
        context_service.update_viewers(connection_service.get_bot_count(), stream_id)
        
        # Get current context
        current_context = context_service.get_context(stream_id)
        
        # Broadcast to bot viewers
        await connection_service.broadcast_to_bots(
            StreamContent(
                type="stream_content",
                content=message_data.content,
                timestamp=time.time(),
                stream_info={
                    "title": current_context["title"],
                    "duration": current_context["duration"],
                    "viewers": connection_service.get_bot_count(),
                    "mood": current_context["mood"]
                }
            ).to_dict()
        )
        
        logger.info(f"Broadcasted content: {message_data.content[:50]}...")
    
    except Exception as e:
        logger.error(f"Error processing broadcaster message: {e}")


async def handle_broadcaster_command(command: str):
    """Handle commands from the broadcaster"""
    if command == "get_viewers":
        await connection_service.send_to_broadcaster(
            SystemMessage(
                message=f"Current bot viewers: {connection_service.get_bot_count()}",
                timestamp=time.time()
            ).to_dict()
        )


# Bot viewer endpoint
@app.websocket("/bot-viewer")
async def bot_viewer_endpoint(websocket: WebSocket):
    """Endpoint for bot viewers to connect and receive stream content"""
    await connection_service.connect_bot_viewer(websocket)
    
    # Get default stream context
    stream_id = context_service.default_stream_id
    current_context = context_service.get_context(stream_id)
    
    # Send current stream info
    if current_context["start_time"]:
        await connection_service.send_to_bot(
            websocket,
            StreamContent(
                type="stream_info",
                content="",
                timestamp=time.time(),
                stream_info={
                    "title": current_context["title"],
                    "duration": current_context["duration"],
                    "viewers": connection_service.get_bot_count(),
                    "mood": current_context["mood"]
                }
            ).to_dict()
        )
    
    # Notify broadcaster about viewer joining
    if connection_service.broadcaster:
        await connection_service.send_to_broadcaster({
            "type": "viewer_update",
            "count": connection_service.get_bot_count(),
            "event": "join",
            "timestamp": time.time()
        })
        
        # Update viewer count
        context_service.update_viewers(connection_service.get_bot_count(), stream_id)
    
    try:
        # Message receiving loop
        while True:
            data = await websocket.receive_text()
            await process_bot_message(websocket, data, stream_id)
    
    except WebSocketDisconnect:
        await handle_bot_disconnect(websocket, stream_id)
    except Exception as e:
        logger.error(f"Bot viewer endpoint error: {e}")
        await handle_bot_disconnect(websocket, stream_id)


async def process_bot_message(websocket: WebSocket, data: str, stream_id: str):
    """Process messages from bot viewers"""
    try:
        message_data = BotReaction.parse_raw_or_text(data)
        message_type = message_data.type

        # Handle heartbeat
        if message_type == "heartbeat":
            connection_service.update_bot_info(websocket, message_data.bot_info)
            return
        
        # Handle bot reaction
        if message_type == "reaction":
            if connection_service.broadcaster:
                await connection_service.send_to_broadcaster(
                    BotReaction(
                        type="bot_reaction",
                        content=message_data.content,
                        bot_info=message_data.bot_info,
                        timestamp=time.time()
                    ).to_dict()
                )
            
            logger.info(f"Bot reaction: {message_data.content[:50]}...")
            return
        
        # Handle stream content reception
        if message_type == "receive_stream_content":
            # Get current context
            current_context = context_service.get_context(stream_id)
            
            # Generate AI reaction
            ai_reaction = await reaction_service.generate_reaction(
                message_data.content,
                message_data.bot_info,
                current_context
            )
            
            # Create response
            response = BotReaction(
                type="reaction",
                content=ai_reaction,
                bot_info=message_data.bot_info,
                timestamp=time.time(),
                ai_generated=True
            ).to_dict()
            
            # Send to bot
            await websocket.send_text(json.dumps(response, ensure_ascii=True))
            
            # Forward to broadcaster
            if connection_service.broadcaster:
                await connection_service.send_to_broadcaster({
                    "type": "bot_reaction",
                    "content": ai_reaction,
                    "bot_info": message_data.bot_info,
                    "timestamp": time.time(),
                    "ai_generated": True
                })
            
            logger.info(f"AI generated reaction: {ai_reaction[:50]}...")
    
    except Exception as e:
        logger.error(f"Error processing bot message: {e}")


async def handle_bot_disconnect(websocket: WebSocket, stream_id: str):
    """Handle bot viewer disconnection"""
    await connection_service.disconnect_bot_viewer(websocket)
    
    # Notify broadcaster
    if connection_service.broadcaster:
        await connection_service.send_to_broadcaster({
            "type": "viewer_update",
            "count": connection_service.get_bot_count(),
            "event": "leave",
            "timestamp": time.time()
        })
        
        # Update viewer count
        context_service.update_viewers(connection_service.get_bot_count(), stream_id)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    default_context = context_service.get_context()
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "stream_active": default_context["start_time"] is not None,
        "connected_bots": connection_service.get_bot_count()
    }


# Main page
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Bot Listener System API",
        "endpoints": {
            "broadcaster": "/broadcaster",
            "bot_viewer": "/bot-viewer",
            "health": "/health"
        },
        "documentation": "/docs"
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("Bot Listener System started")
    logger.info("Endpoints: /broadcaster (broadcaster), /bot-viewer (bot viewer)")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("Bot Listener System shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot_system.app:app", host="0.0.0.0", port=8000, reload=True)