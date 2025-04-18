#!/usr/bin/env python3
"""
ボットリスナーシステム サーバー
-----------------------------
* Python 3.9+ 推奨
* 依存: fastapi, uvicorn, websockets, openai, python-dotenv
* 起動方法: uvicorn bot_system:app --reload
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
import json
import asyncio
import time
import uuid
import logging
from typing import List, Dict, Any

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("bot_listener")

# 環境変数読み込み
load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# FastAPIアプリケーション
app = FastAPI(title="Bot Listener System")

# 接続管理クラス
class ConnectionManager:
    def __init__(self):
        self.broadcaster = None
        self.bot_viewers: List[WebSocket] = []
        self.bot_info: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect_broadcaster(self, websocket: WebSocket):
        if self.broadcaster:
            await websocket.close(code=1000, reason="別の配信者が既に接続中です")
            return False
        
        await websocket.accept()
        self.broadcaster = websocket
        logger.info("配信者が接続しました")
        return True
    
    async def disconnect_broadcaster(self):
        self.broadcaster = None
        logger.info("配信者が切断しました")
    
    async def connect_bot_viewer(self, websocket: WebSocket):
        await websocket.accept()
        self.bot_viewers.append(websocket)
        self.bot_info[websocket] = {"connected_at": time.time()}
        logger.info(f"ボットビューアーが接続しました (現在{len(self.bot_viewers)}個)")
        return True
    
    async def disconnect_bot_viewer(self, websocket: WebSocket):
        if websocket in self.bot_viewers:
            self.bot_viewers.remove(websocket)
        
        if websocket in self.bot_info:
            del self.bot_info[websocket]
        
        logger.info(f"ボットビューアーが切断しました (残り{len(self.bot_viewers)}個)")
    
    async def broadcast_to_bots(self, message: dict):
        if not self.bot_viewers:
            logger.warning("接続中のボットがいません")
            return
        
        tasks = [self.send_to_bot(bot, message) for bot in self.bot_viewers]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_to_bot(self, bot: WebSocket, message: dict):
        try:
            await bot.send_text(json.dumps(message, ensure_ascii=True))
        except Exception as e:
            logger.error(f"ボットへの送信エラー: {e}")
    
    async def send_to_broadcaster(self, message: dict):
        if not self.broadcaster:
            logger.warning("配信者が接続されていません")
            return
        
        try:
            await self.broadcaster.send_text(json.dumps(message, ensure_ascii=True))
        except Exception as e:
            logger.error(f"配信者への送信エラー: {e}")
    
    def update_bot_info(self, websocket: WebSocket, info: dict):
        if websocket in self.bot_info:
            self.bot_info[websocket].update(info)
    
    def get_bot_count(self):
        return len(self.bot_viewers)


# 接続マネージャのインスタンス
manager = ConnectionManager()

# ストリーム情報
stream_context = {
    "stream_id": str(uuid.uuid4()),
    "title": "デフォルト配信",
    "start_time": None,
    "topics": [],
    "mood": "neutral"
}


# APIを使ってボットの反応を生成する関数
async def generate_bot_reaction(content: str, bot_info: dict) -> str:
    try:
        # ボット情報からシステムメッセージを構築
        personality_type = bot_info.get("personality_type", "standard")
        interests = bot_info.get("interests", [])
        emoji_usage = bot_info.get("emoji_usage", "medium")
        
        # interestsが配列の場合は文字列に変換
        if isinstance(interests, list):
            interests_str = ", ".join(interests)
        else:
            interests_str = str(interests)
        
        system_message = f"""あなたはライブ配信の視聴者ボットです。個性: {personality_type}、興味: {interests_str}、絵文字使用頻度: {emoji_usage}。
配信内容に対して自然な反応を一行で返してください。実際の視聴者のように振る舞い、質問、感想、リアクション、絵文字などで反応してください。返答は50文字以内に簡潔にしてください。"""
        
        # OpenAI APIを呼び出し (metadataを削除)
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",  # 適切なモデルに変更
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"配信内容: {content}\n\n視聴者としての自然な反応を一行で書いてください。"}
            ],
            max_completion_tokens=60,  # max_tokensではなくmax_completion_tokensを使用
            temperature=0.7
            # metadataパラメータは削除
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        logger.error(f"AI反応生成エラー: {e}")
        # エラーの場合はフォールバック反応を返す
        fallback_responses = [
            "面白いですね！",
            "なるほど～",
            "それは興味深いです！",
            "へぇ～！",
            "続き気になります！",
            "わかります！",
            "すごい！",
            "応援してます！"
        ]
        import random
        return random.choice(fallback_responses)


# 配信者エンドポイント
@app.websocket("/broadcaster")
async def broadcaster_endpoint(websocket: WebSocket, background_tasks: BackgroundTasks):
    if not await manager.connect_broadcaster(websocket):
        return
    
    # 配信開始処理
    stream_context["start_time"] = time.time()
    stream_context["stream_id"] = str(uuid.uuid4())
    
    try:
        # 現在の視聴ボット数を通知
        await manager.send_to_broadcaster({
            "type": "system_info",
            "message": f"現在の視聴ボット数: {manager.get_bot_count()}",
            "timestamp": time.time()
        })
        
        # メッセージ受信ループ
        while True:
            data = await websocket.receive_text()
            
            try:
                # JSONデータとしてパース
                message_data = json.loads(data)
                content = message_data.get("content", data)
                metadata = message_data.get("metadata", {})
                
                # ストリームコンテキストを更新
                if "stream_title" in metadata:
                    stream_context["title"] = metadata["stream_title"]
                
                # ボットに配信内容を送信
                await manager.broadcast_to_bots({
                    "type": "stream_content",
                    "content": content,
                    "timestamp": time.time(),
                    "stream_info": {
                        "title": stream_context["title"],
                        "duration": time.time() - stream_context["start_time"],
                        "viewers": manager.get_bot_count()
                    }
                })
                
                logger.info(f"配信内容をブロードキャスト: {content[:50]}...")
                
            except json.JSONDecodeError:
                # プレーンテキストの場合
                await manager.broadcast_to_bots({
                    "type": "stream_content",
                    "content": data,
                    "timestamp": time.time()
                })
                
                logger.info(f"プレーンテキストをブロードキャスト: {data[:50]}...")
    
    except WebSocketDisconnect:
        await manager.disconnect_broadcaster()
    except Exception as e:
        logger.error(f"配信者エンドポイントエラー: {e}")
        await manager.disconnect_broadcaster()


# ボットビューアーエンドポイント
@app.websocket("/bot-viewer")
async def bot_viewer_endpoint(websocket: WebSocket):
    await manager.connect_bot_viewer(websocket)
    
    # 現在の配信情報を送信
    if stream_context["start_time"]:
        await manager.send_to_bot(websocket, {
            "type": "stream_info",
            "title": stream_context["title"],
            "duration": time.time() - stream_context["start_time"],
            "viewers": manager.get_bot_count()
        })
    
    # 配信者に視聴者数変更を通知
    if manager.broadcaster:
        await manager.send_to_broadcaster({
            "type": "viewer_update",
            "count": manager.get_bot_count(),
            "event": "join",
            "timestamp": time.time()
        })
    
    try:
        # メッセージ受信ループ
        while True:
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "unknown")
                
                # ハートビートメッセージの処理
                if message_type == "heartbeat":
                    bot_info = message_data.get("bot_info", {})
                    manager.update_bot_info(websocket, bot_info)
                    continue
                
                # ボットの反応メッセージの処理
                if message_type == "reaction":
                    content = message_data.get("content", "")
                    bot_info = message_data.get("bot_info", {})
                    
                    # 配信者に転送
                    if manager.broadcaster:
                        await manager.send_to_broadcaster({
                            "type": "bot_reaction",
                            "content": content,
                            "bot_info": bot_info,
                            "timestamp": time.time()
                        })
                    
                    logger.info(f"ボット反応: {content[:50]}...")
                
                # ストリームコンテンツに対する自動反応
                if message_type == "receive_stream_content":
                    stream_content = message_data.get("content", "")
                    bot_info = message_data.get("bot_info", {})
                    
                    # AIを使って反応を生成
                    ai_reaction = await generate_bot_reaction(stream_content, bot_info)
                    
                    response = {
                        "type": "reaction",
                        "content": ai_reaction,
                        "bot_info": bot_info,
                        "timestamp": time.time(),
                        "ai_generated": True
                    }
                    
                    # ボットに反応を送信
                    await websocket.send_text(json.dumps(response, ensure_ascii=True))
                    
                    # 配信者にも転送
                    if manager.broadcaster:
                        await manager.send_to_broadcaster({
                            "type": "bot_reaction",
                            "content": ai_reaction,
                            "bot_info": bot_info,
                            "timestamp": time.time(),
                            "ai_generated": True
                        })
                    
                    logger.info(f"AI生成反応: {ai_reaction[:50]}...")
            
            except json.JSONDecodeError:
                # ハートビートとして扱う
                pass
    
    except WebSocketDisconnect:
        await manager.disconnect_bot_viewer(websocket)
        
        # 配信者に視聴者数変更を通知
        if manager.broadcaster:
            await manager.send_to_broadcaster({
                "type": "viewer_update",
                "count": manager.get_bot_count(),
                "event": "leave",
                "timestamp": time.time()
            })
    
    except Exception as e:
        logger.error(f"ボットビューアーエンドポイントエラー: {e}")
        await manager.disconnect_bot_viewer(websocket)


# ヘルスチェックエンドポイント
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "stream_active": stream_context["start_time"] is not None,
        "connected_bots": manager.get_bot_count()
    }


# メインページ
@app.get("/")
async def root():
    return {
        "message": "ボットリスナーシステム API",
        "endpoints": {
            "broadcaster": "/broadcaster",
            "bot_viewer": "/bot-viewer",
            "health": "/health"
        },
        "documentation": "/docs"
    }


# 起動メッセージ
@app.on_event("startup")
async def startup_event():
    logger.info("ボットリスナーシステムを起動しました")
    logger.info("エンドポイント: /broadcaster (配信者), /bot-viewer (ボットビューアー)")


# シャットダウンメッセージ
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("ボットリスナーシステムをシャットダウンしています")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot_system:app", host="0.0.0.0", port=8000, reload=True)