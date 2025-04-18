#!/usr/bin/env python3
"""
ボットリスナーシステム テストクライアント
---------------------------------------
* Python 3.9+ 推奨
* 依存: websockets, argparse
* 使用方法:
  - 配信者クライアント: python test_clients.py broadcaster
  - ボットリスナークライアント: python test_clients.py bot-viewer
"""

import asyncio
import sys
import argparse
import websockets
import json
import time
import uuid
import random


async def broadcaster_client(uri: str) -> None:
    """配信者クライアント: 標準入力からテキストを読み取り配信する"""
    async with websockets.connect(uri) as ws:
        print(f"✅ 配信者として接続完了: {uri}")
        print("👉 配信内容を入力して Enter。Ctrl‑D / Ctrl‑C で終了。\n")

        # 受信タスク
        async def receiver():
            try:
                async for msg in ws:
                    # JSONレスポンスを整形して表示
                    try:
                        data = json.loads(msg)
                        # print(f"\r🔄 フィードバック受信: {json.dumps(data, ensure_ascii=True, indent=2)}\n> ", end="", flush=True)
                    except json.JSONDecodeError:
                        print(f"\r🔄 メッセージ受信: {msg}\n> ", end="", flush=True)
            except websockets.ConnectionClosedOK:
                print("\n👋 サーバが接続を終了しました。")
            except Exception as e:
                print(f"\n❌ エラーが発生しました: {str(e)}")

        recv_task = asyncio.create_task(receiver())

        # 送信ループ
        loop = asyncio.get_running_loop()
        try:
            while True:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:  # EOF（Ctrl‑D）
                    break
                
                # 配信コンテンツをメタデータと共に送信
                stream_data = {
                    "content": line.rstrip("\n"),
                    "metadata": {
                        "timestamp": time.time(),
                        "stream_id": str(uuid.uuid4()),
                        "broadcaster_id": "test_broadcaster",
                        "stream_title": "テスト配信",
                        "language": "ja"
                    }
                }
                
                # エンコードエラーを防ぐためにASCII文字のみを許可
                await ws.send(json.dumps(stream_data, ensure_ascii=True))
                print("> ", end="", flush=True)
        except KeyboardInterrupt:
            pass

        recv_task.cancel()
        await ws.close()
        print("\n🔌 配信終了、切断しました。")


async def bot_viewer_client(uri: str) -> None:
    """ボットビューアークライアント: サーバーから配信内容を受け取り、反応する"""
    async with websockets.connect(uri) as ws:
        print(f"✅ ボットビューアーとして接続完了: {uri}")
        print("受信待機中... (Ctrl‑C で終了)\n")

        # ボットの個性情報
        personality_types = ["enthusiastic", "critical", "curious", "shy", "funny", "technical", "supportive"]
        interests = [
            ["テクノロジー", "ゲーム", "音楽"],
            ["アニメ", "マンガ", "映画"],
            ["プログラミング", "AI", "機械学習"],
            ["スポーツ", "健康", "料理"],
            ["科学", "宇宙", "歴史"]
        ]
        emoji_usage = ["high", "medium", "low"]
        
        bot_personality = {
            "id": str(uuid.uuid4()),
            "name": f"BotViewer_{uuid.uuid4().hex[:6]}",
            "personality_type": random.choice(personality_types),
            "interests": random.choice(interests),
            "emoji_usage": random.choice(emoji_usage)
        }
        
        print(f"🤖 ボット個性: {bot_personality['personality_type']}, 興味: {', '.join(bot_personality['interests'])}, 絵文字使用: {bot_personality['emoji_usage']}")

        # ハートビート送信タスク
        async def send_heartbeat():
            while True:
                try:
                    await ws.send(json.dumps({"type": "heartbeat", "bot_info": bot_personality}))
                    await asyncio.sleep(30)  # 30秒ごとにハートビート
                except:
                    break

        heartbeat_task = asyncio.create_task(send_heartbeat())

        # 受信して反応するタスク
        try:
            async for msg in ws:
                try:
                    # 受信したメッセージを解析
                    data = json.loads(msg)
                    
                    if "type" in data and data["type"] == "stream_content":
                        # print(f"\r📺 配信内容: {data['content']}")
                        
                        # AI生成のリクエストを送信
                        ai_request = {
                            "type": "receive_stream_content",
                            "content": data['content'],
                            "bot_info": bot_personality,
                            "timestamp": time.time()
                        }
                        
                        # AIサーバーにリクエストを送信
                        await ws.send(json.dumps(ai_request, ensure_ascii=True))
                        # print("🔄 AI生成リクエスト送信...")
                        
                    elif "type" in data and data["type"] == "reaction" and data.get("ai_generated", False):
                        # AIが生成した反応を表示
                        print(f"🤖 AI生成反応: {data['content']}")
                    else:
                        print(f"\r📩 メッセージ受信: {json.dumps(data, ensure_ascii=True, indent=2)}")
                        
                except json.JSONDecodeError:
                    print(f"\r📩 メッセージ受信: {msg}")
        except websockets.ConnectionClosedOK:
            print("\n👋 サーバが接続を終了しました。")
        except KeyboardInterrupt:
            pass

        heartbeat_task.cancel()
        await ws.close()
        print("\n🔌 切断しました。")


async def multi_bot_simulation(uri: str, num_bots: int) -> None:
    """複数のボットを同時にシミュレーションする"""
    print(f"✅ {num_bots}個のボットビューアーをシミュレーションします...")
    
    tasks = []
    for i in range(num_bots):
        # 各ボットに少し異なるURIを渡して一意に識別
        bot_uri = f"{uri}?bot_id={i+1}"
        tasks.append(asyncio.create_task(bot_viewer_client(bot_uri)))
    
    try:
        # すべてのボットタスクが完了するまで待機
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        # キーボード割り込みでクリーンアップ
        for task in tasks:
            task.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(description="ボットリスナーシステム テストクライアント")
    parser.add_argument(
        "client_type",
        choices=["broadcaster", "bot-viewer", "multi-bot"],
        help="クライアントタイプ: broadcaster (配信者), bot-viewer (視聴ボット), multi-bot (複数ボット)"
    )
    parser.add_argument(
        "--uri",
        default="ws://localhost:8000/",
        help="接続先ベースURI（例: ws://example.com/）"
    )
    parser.add_argument(
        "--bots",
        type=int,
        default=3,
        help="multi-botモード時のボット数"
    )
    
    args = parser.parse_args()
    
    # クライアントタイプに応じたURIを設定
    if args.client_type == "broadcaster":
        full_uri = f"{args.uri}broadcaster"
        asyncio.run(broadcaster_client(full_uri))
    elif args.client_type == "bot-viewer":
        full_uri = f"{args.uri}bot-viewer"
        asyncio.run(bot_viewer_client(full_uri))
    elif args.client_type == "multi-bot":
        full_uri = f"{args.uri}bot-viewer"
        asyncio.run(multi_bot_simulation(full_uri, args.bots))


if __name__ == "__main__":
    main()