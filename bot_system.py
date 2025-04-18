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

# APIを使ってボットの反応を生成する関数（Unicode対応版）
async def generate_bot_reaction(content: str, bot_info: dict, stream_context: dict = None) -> str:
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
        
        # 配信コンテキスト情報を構築
        stream_title = "不明な配信"
        stream_duration = 0
        stream_topics = []
        previous_messages = []
        
        if stream_context:
            stream_title = stream_context.get("title", "不明な配信")
            stream_duration = stream_context.get("duration", 0)
            stream_topics = stream_context.get("topics", [])
            previous_messages = stream_context.get("previous_messages", [])
        
        # Unicode問題を回避するためにASCII範囲外の文字をエスケープ
        def sanitize_text(text):
            if not isinstance(text, str):
                return str(text)
            # ASCII範囲外の文字をエスケープまたは置換
            return text.encode('ascii', 'backslashreplace').decode('ascii')
        
        # テキストデータをサニタイズ
        sanitized_title = sanitize_text(stream_title)
        sanitized_personality = sanitize_text(personality_type)
        sanitized_interests = sanitize_text(interests_str)
        
        # 前回のメッセージコンテキスト（最大3つ）
        context_messages = ""
        if previous_messages:
            for i, msg in enumerate(previous_messages[-3:]):
                sanitized_msg = sanitize_text(msg)
                context_messages += f"前回のメッセージ{i+1}: {sanitized_msg}\n"
        
        # より詳細なボット設定に基づくシステムメッセージ
        personality_descriptions = {
            "enthusiastic": "とても熱心で興奮しやすい。ポジティブで応援するような発言が多い。絵文字を多用する。",
            "critical": "少し批判的で分析的。質問や改善提案をすることが多い。",
            "curious": "好奇心旺盛で質問が多い。「なぜ」「どのように」といった疑問を投げかける。",
            "shy": "控えめで、短いコメントが多い。でも配信者の言葉には反応する。",
            "funny": "ユーモアがあり、冗談やおかしなコメントをすることが多い。",
            "technical": "技術的な話題に詳しく、専門的なコメントや質問をする。",
            "supportive": "サポート的で、共感や励ましのコメントが多い。"
        }
        
        emoji_descriptions = {
            "high": "絵文字を多用する（1-2個/メッセージ）",
            "medium": "絵文字を時々使う（50%の確率で1つ）",
            "low": "絵文字はあまり使わない（20%の確率で1つ）"
        }
        
        personality_desc = personality_descriptions.get(sanitized_personality, "標準的な反応をする")
        emoji_desc = emoji_descriptions.get(emoji_usage, "絵文字を適度に使う")
        
        # 配信時間に応じた視聴者の態度
        viewer_attitude = "初めて見た配信に興味を持っている"
        if stream_duration > 1800:  # 30分以上
            viewer_attitude = "しばらく視聴していて配信の流れを理解している"
        elif stream_duration > 300:  # 5分以上
            viewer_attitude = "少し視聴していて配信に慣れてきている"
        
        # 配信タイトルに基づく興味レベル
        interest_level = "普通"
        for interest in interests:
            # 興味と配信タイトルに共通のキーワードがあるか確認
            if isinstance(interest, str) and isinstance(stream_title, str):
                if interest.lower() in stream_title.lower():
                    interest_level = "高い"
                    break
        
        system_message = f"""あなたはライブ配信「{sanitized_title}」の視聴者ボットです。

【ボットの個性】
- 個性タイプ: {sanitized_personality}（{personality_desc}）
- 興味のある分野: {sanitized_interests}
- 絵文字の使用: {emoji_desc}
- 配信への興味レベル: {interest_level}
- 視聴者の態度: {viewer_attitude}

【配信コンテキスト】
- 配信タイトル: {sanitized_title}
- 配信時間: {int(stream_duration/60)}分{int(stream_duration%60)}秒
{context_messages}

配信内容に対して、上記の個性に基づいた自然な反応を一行で返してください。
実際の視聴者のように振る舞い、質問、感想、リアクション、絵文字などで反応してください。
返答は50文字以内に簡潔にしてください。"""

        # 配信内容もサニタイズ
        sanitized_content = sanitize_text(content)
        
        # OpenAI APIを呼び出し
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"配信内容: {sanitized_content}\n\n視聴者としての自然な反応を一行で書いてください。"}
            ],
            max_completion_tokens=60,
            temperature=0.8  # 個性をより出すために少し高めに設定
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
            "応援してます！",
            "どうやってやるんですか？",
            "初めて見ました！",
            "もっと教えてください！",
            "それってどういう意味ですか？"
        ]
        import random
        return random.choice(fallback_responses)


# StreamContextManagerのインスタンスを作成
from StreamContextManager import StreamContextManager
context_manager = StreamContextManager()

# 配信者エンドポイントの修正
@app.websocket("/broadcaster")
async def broadcaster_endpoint(websocket: WebSocket, background_tasks: BackgroundTasks):
    if not await manager.connect_broadcaster(websocket):
        return
    
    # 配信開始処理
    stream_id = str(uuid.uuid4())
    stream_context = context_manager.reset_context(stream_id)
    
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
                
                # コマンドの処理
                if "command" in message_data:
                    command = message_data["command"]
                    if command == "get_viewers":
                        await manager.send_to_broadcaster({
                            "type": "system_info",
                            "message": f"現在の視聴ボット数: {manager.get_bot_count()}",
                            "timestamp": time.time()
                        })
                        continue
                
                content = message_data.get("content", data)
                metadata = message_data.get("metadata", {})
                
                # ストリームコンテキストを更新
                if "stream_title" in metadata:
                    context_manager.update_title(metadata["stream_title"], stream_id)
                
                # メッセージをコンテキストに追加
                context_manager.add_message(content, stream_id)
                
                # 雰囲気分析
                context_manager.analyze_mood(content, stream_id)
                
                # 視聴者数を更新
                context_manager.update_viewers(manager.get_bot_count(), stream_id)
                
                # 更新されたコンテキストを取得
                current_context = context_manager.get_context(stream_id)
                
                # ボットに配信内容を送信
                await manager.broadcast_to_bots({
                    "type": "stream_content",
                    "content": content,
                    "timestamp": time.time(),
                    "stream_info": {
                        "title": current_context["title"],
                        "duration": current_context["duration"],
                        "viewers": manager.get_bot_count(),
                        "mood": current_context["mood"]
                    }
                })
                
                logger.info(f"配信内容をブロードキャスト: {content[:50]}...")
                
            except json.JSONDecodeError:
                # プレーンテキストの場合
                # メッセージをコンテキストに追加
                context_manager.add_message(data, stream_id)
                
                # 雰囲気分析
                context_manager.analyze_mood(data, stream_id)
                
                # 更新されたコンテキストを取得
                current_context = context_manager.get_context(stream_id)
                
                await manager.broadcast_to_bots({
                    "type": "stream_content",
                    "content": data,
                    "timestamp": time.time(),
                    "stream_info": {
                        "title": current_context["title"],
                        "duration": current_context["duration"],
                        "viewers": manager.get_bot_count(),
                        "mood": current_context["mood"]
                    }
                })
                
                logger.info(f"プレーンテキストをブロードキャスト: {data[:50]}...")
    
    except WebSocketDisconnect:
        await manager.disconnect_broadcaster()
    except Exception as e:
        logger.error(f"配信者エンドポイントエラー: {e}")
        await manager.disconnect_broadcaster()


# ボットビューアーエンドポイントの修正
@app.websocket("/bot-viewer")
async def bot_viewer_endpoint(websocket: WebSocket):
    await manager.connect_bot_viewer(websocket)
    
    # デフォルトのストリームコンテキストを取得
    stream_id = context_manager.default_stream_id
    current_context = context_manager.get_context(stream_id)
    
    # 現在の配信情報を送信
    if current_context["start_time"]:
        await manager.send_to_bot(websocket, {
            "type": "stream_info",
            "title": current_context["title"],
            "duration": current_context["duration"],
            "viewers": manager.get_bot_count(),
            "mood": current_context["mood"]
        })
    
    # 配信者に視聴者数変更を通知
    if manager.broadcaster:
        await manager.send_to_broadcaster({
            "type": "viewer_update",
            "count": manager.get_bot_count(),
            "event": "join",
            "timestamp": time.time()
        })
        
        # 視聴者数の更新
        context_manager.update_viewers(manager.get_bot_count(), stream_id)
    
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
                    
                    # 最新のコンテキストを取得
                    current_context = context_manager.get_context(stream_id)
                    
                    # AIを使って反応を生成
                    ai_reaction = await generate_bot_reaction(stream_content, bot_info, current_context)
                    
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
            
            # 視聴者数の更新
            context_manager.update_viewers(manager.get_bot_count(), stream_id)
    
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