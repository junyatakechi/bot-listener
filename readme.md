
Python環境有効化
`source .venv/bin/activate`

サーバー起動
`uvicorn bot_system:app --reload`

# テストクライアント起動
- 配信者として接続:
`python test_clients.py broadcaster --uri ws://localhost:8000/`
- ボットリスナーとして接続
`python test_clients.py bot-viewer --uri ws://localhost:8000/`
- または複数のボットを同時に起動:
`python test_clients.py multi-bot --uri ws://localhost:8000/ --bots 5`
