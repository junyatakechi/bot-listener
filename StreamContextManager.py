import time

# 配信コンテキストを管理するクラス
class StreamContextManager:
    def __init__(self):
        # 配信ごとのコンテキスト（配信IDをキーとする辞書）
        self.stream_contexts = {}
        # デフォルトのストリームID
        self.default_stream_id = "default"
        
        # デフォルトコンテキストの初期化
        self._init_context(self.default_stream_id)
    
    def _init_context(self, stream_id):
        """新しい配信コンテキストを初期化"""
        self.stream_contexts[stream_id] = {
            "title": "テスト配信",
            "start_time": time.time(),
            "duration": 0,
            "topics": [],
            "mood": "neutral",
            "previous_messages": [],  # 過去のメッセージを保存
            "viewers": 0,             # 視聴者数
            "broadcaster_info": {},   # 配信者情報
            "message_count": 0        # メッセージ数
        }
    
    def get_context(self, stream_id=None):
        """指定された配信IDのコンテキストを取得"""
        if stream_id is None:
            stream_id = self.default_stream_id
        
        # 存在しない場合は新規作成
        if stream_id not in self.stream_contexts:
            self._init_context(stream_id)
        
        # 現在の配信時間を更新
        ctx = self.stream_contexts[stream_id]
        ctx["duration"] = time.time() - ctx["start_time"]
        
        return ctx
    
    def update_title(self, title, stream_id=None):
        """配信タイトルを更新"""
        if stream_id is None:
            stream_id = self.default_stream_id
        
        ctx = self.get_context(stream_id)
        ctx["title"] = title
        
        # タイトルからトピックを自動抽出（簡易版）
        keywords = [word.lower() for word in title.split() if len(word) > 2]
        # 既存のトピックと重複を避けてマージ
        ctx["topics"] = list(set(ctx["topics"] + keywords))
        
        return ctx
    
    def add_message(self, message, stream_id=None):
        """配信メッセージを追加して履歴を更新"""
        if stream_id is None:
            stream_id = self.default_stream_id
        
        ctx = self.get_context(stream_id)
        
        # メッセージカウントを増やす
        ctx["message_count"] += 1
        
        # 最新の配信コンテンツを履歴に追加（最大10件保持）
        ctx["previous_messages"].append(message)
        if len(ctx["previous_messages"]) > 10:
            ctx["previous_messages"] = ctx["previous_messages"][-10:]
        
        return ctx
    
    def update_viewers(self, count, stream_id=None):
        """視聴者数を更新"""
        if stream_id is None:
            stream_id = self.default_stream_id
        
        ctx = self.get_context(stream_id)
        ctx["viewers"] = count
        
        return ctx
    
    def reset_context(self, stream_id=None):
        """配信コンテキストをリセット"""
        if stream_id is None:
            stream_id = self.default_stream_id
        
        self._init_context(stream_id)
        
        return self.get_context(stream_id)
    
    def analyze_mood(self, content, stream_id=None):
        """配信内容から雰囲気を分析（簡易版）"""
        if stream_id is None:
            stream_id = self.default_stream_id
        
        ctx = self.get_context(stream_id)
        
        # シンプルな感情分析（実際はもっと高度な方法を使うべき）
        positive_words = ["楽しい", "嬉しい", "面白い", "すごい", "好き", "最高", "happy", "fun", "great"]
        negative_words = ["難しい", "悲しい", "辛い", "苦しい", "嫌い", "最悪", "sad", "hard", "tough"]
        excited_words = ["わくわく", "興奮", "激アツ", "テンション", "excited", "amazing"]
        
        content_lower = content.lower()
        
        # 感情カウント
        positive_count = sum([1 for word in positive_words if word in content_lower])
        negative_count = sum([1 for word in negative_words if word in content_lower])
        excited_count = sum([1 for word in excited_words if word in content_lower])
        
        # ムードの決定（簡易版）
        if excited_count > 0:
            ctx["mood"] = "excited"
        elif positive_count > negative_count:
            ctx["mood"] = "positive"
        elif negative_count > positive_count:
            ctx["mood"] = "negative"
        else:
            # 以前のムードを維持するか、メッセージが増えるほど徐々に元に戻す
            if ctx["message_count"] % 5 == 0:
                ctx["mood"] = "neutral"
        
        return ctx