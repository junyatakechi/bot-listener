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

配信内容に対して、上記の個性に基づいた自然な反応を一行で返してください。
実際の視聴者のように振る舞い、質問、感想、リアクション、絵文字などで反応してください。
返答は50文字以内に簡潔にしてください。"""

            # 配信内容もサニタイズ
            sanitized_content = sanitize_text(content)
            
            # OpenAI APIを呼び出し
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"配信内容: {sanitized_content}\n\n視聴者としての自然な反応を一行で書いてください。"}
                ],
                max_tokens=60,
                temperature=0.8  # 個性をより出すために少し高めに設定
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"AI反応生成エラー: {e}")