
Python環境有効化
`source .venv/bin/activate`

サーバー起動
`uvicorn bot_system.app:app --reload`

# テストクライアント起動
- 配信者として接続:
`python bot_system/test_clients.py broadcaster`
- ボットリスナーとして接続
`python bot_system/test_clients.py bot-viewer`
