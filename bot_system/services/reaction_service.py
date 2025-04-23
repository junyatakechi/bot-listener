"""
Bot reaction generation service for Bot Listener System (Japanese version)
ボットリスナーシステム用リアクション生成サービス（日本語版）
"""
import logging
import random
from typing import Dict, Any, List, Optional, Union
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("bot_listener")


class ReactionService:
    """ボットリアクション生成サービス"""
    
    def __init__(self, openai_api_key: str, openai_model: str = "gpt-3.5-turbo"):
        """
        リアクションサービスの初期化
        
        Args:
            openai_api_key: OpenAI APIキー
            openai_model: 使用するOpenAIモデル
        """
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.model = openai_model
        
        # 個性ごとの温度設定
        self.personality_temperatures = {
            "enthusiastic": 0.9,
            "critical": 0.6,
            "curious": 0.8,
            "shy": 0.5,
            "funny": 1.0,
            "technical": 0.4,
            "supportive": 0.7
        }
        
        # ボットの個性の説明（日本語）
        self.personality_descriptions = {
            "enthusiastic": "とても熱心で興奮しやすい。ポジティブで応援するような発言が多い。絵文字を多用する。",
            "critical": "少し批判的で分析的。質問や改善提案をすることが多い。",
            "curious": "好奇心旺盛で質問が多い。「なぜ」「どのように」といった疑問を投げかける。",
            "shy": "控えめで、短いコメントが多い。でも配信者の言葉には反応する。",
            "funny": "ユーモアがあり、冗談やおかしなコメントをすることが多い。",
            "technical": "技術的な話題に詳しく、専門的なコメントや質問をする。",
            "supportive": "サポート的で、共感や励ましのコメントが多い。"
        }
        
        # 絵文字の使用頻度の説明（日本語）
        self.emoji_descriptions = {
            "high": "絵文字を多用する（1-2個/メッセージ）",
            "medium": "絵文字を時々使う（50%の確率で1つ）",
            "low": "絵文字はあまり使わない（20%の確率で1つ）"
        }
    
    async def generate_reaction(self, content: str, bot_info: dict, stream_context: dict = None) -> str:
        """
        ストリームコンテンツに対するボットの反応を生成
        
        Args:
            content: ストリームコンテンツ
            bot_info: ボット情報
            stream_context: ストリームコンテキスト
            
        Returns:
            str: 生成された反応
        """
        try:
            # ボットの個性情報を抽出
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
            
            # 個性と絵文字の使用頻度の説明を取得
            personality_desc = self.personality_descriptions.get(
                sanitized_personality, 
                "標準的な反応をする"
            )
            emoji_desc = self.emoji_descriptions.get(
                emoji_usage, 
                "絵文字を適度に使う"
            )
            
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
                    
            # 文脈理解のためのヒストリーをより詳細に構築
            context_messages = ""
            if previous_messages:
                # メッセージと発言者情報を含める
                for i, msg_data in enumerate(previous_messages[-5:]):  # 5つまで拡大
                    msg = msg_data.get("content", "")
                    speaker = msg_data.get("speaker", "配信者")
                    timestamp = msg_data.get("timestamp", 0)
                    time_ago = int((stream_duration - timestamp) / 60) if timestamp > 0 else "?"
                    
                    sanitized_msg = sanitize_text(msg)
                    sanitized_speaker = sanitize_text(speaker)
                    
                    context_messages += f"{time_ago}分前 - {sanitized_speaker}: {sanitized_msg}\n"
            
            # キーワードと感情分析の追加
            content_keywords = extract_keywords(content)
            content_sentiment = analyze_sentiment(content)
            
            # 個性に応じた文字数制限の設定
            character_limits = {
                "enthusiastic": 60,
                "critical": 70,
                "curious": 60,
                "shy": 30,
                "funny": 60,
                "technical": 80,
                "supportive": 50
            }
            character_limit = character_limits.get(sanitized_personality, 50)
            
            # システムメッセージを構築
            system_message = f"""あなたはライブ配信「{sanitized_title}」の日本人の視聴者ボットです。

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
- 今までの配信で出たトピック: {", ".join(stream_topics) if stream_topics else "まだ特定されていません"}

配信内容に対して、上記の個性に基づいた自然な反応を一行で返してください。
実際の視聴者のように振る舞い、質問、感想、リアクション、絵文字などで反応してください。
返答は{character_limit}文字以内に簡潔にしてください。

【良い応答の例】
- enthusiastic: わぁ！それすごいですね！次も楽しみにしてます！✨✨
- critical: そのやり方だと効率が悪くないですか？別の方法も検討してみては？
- curious: なぜその技術を選んだんですか？他の選択肢も考えたんですか？
- shy: なるほど...（小声で）
- funny: 爆発しなくてよかったですね笑 私なら逃げ出してます🏃💨
- technical: そのアルゴリズムの計算量はO(n²)ですよね。並列化は検討されましたか？
- supportive: お疲れ様です！いつも素晴らしい配信をありがとう😊

【避けるべき応答の例】
- 不自然に長い文章
- ボットっぽい定型文
- 配信内容と無関係なコメント
- 個性と合わない反応スタイル

"""

            # 配信内容もサニタイズ
            sanitized_content = sanitize_text(content)
            
            # 個性に応じた温度の設定
            personality_type = bot_info.get("personality_type", "standard")
            temperature = self.personality_temperatures.get(personality_type, 0.7)
            
            # OpenAI APIを呼び出し
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"配信内容: {sanitized_content}\n\n視聴者としての自然な反応を一行で書いてください。"}
                ],
                max_tokens=100,  # 少し増やして十分な長さを確保
                temperature=temperature,  # 個性に基づいて調整
                presence_penalty=0.6,  # 繰り返しを減らす
                frequency_penalty=0.5  # バリエーションを増やす
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"AI反応生成エラー: {e}")

def extract_keywords(text):
    """簡単なキーワード抽出（実装例）"""
    # 実際の実装ではMeCab等の形態素解析ライブラリを使用することを推奨
    common_words = ["です", "ます", "した", "から", "ので", "けど", "って", "など"]
    words = text.split()
    keywords = []
    
    for word in words:
        if len(word) > 1 and word not in common_words:
            keywords.append(word)
    
    return keywords[:5]  # 最大5つのキーワードを返す

def analyze_sentiment(text):
    """簡易的な感情分析（実装例）"""
    # 実際の実装では感情分析APIや辞書ベースの分析を推奨
    positive_words = ["嬉しい", "楽しい", "素晴らしい", "好き", "良い", "すごい"]
    negative_words = ["悲しい", "つらい", "難しい", "嫌い", "悪い", "残念"]
    
    positive_count = sum(1 for word in positive_words if word in text)
    negative_count = sum(1 for word in negative_words if word in text)
    
    if positive_count > negative_count:
        return "ポジティブ"
    elif negative_count > positive_count:
        return "ネガティブ"
    else:
        return "中立"