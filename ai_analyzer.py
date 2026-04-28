"""
ai_analyzer.py - GeminiまたはClaudeを使って株のトレード判断を行う
"""
import os
import json
import re
from datetime import datetime
from typing import Optional
import asyncio

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()


TRADE_PROMPT_TEMPLATE = """
あなたは優秀な株式アナリストです。今日の日付は {today} です。

以下のタスクを実行してください：
1. 本日の最新ニュースや市場動向から、特に注目すべき日本株または米国株の銘柄を調査する
2. 投資額 {amount_jpy}円 を使って、最もリターンが期待できる銘柄への擬似投資を1〜3銘柄提案する
3. 各銘柄について根拠を明確に説明する

必ず以下のJSON形式のみで回答してください。JSONの前後に余計なテキストを含めないこと：

{{
  "summary": "本日の市場概況を2〜3文で説明",
  "trades": [
    {{
      "ticker": "銘柄コード(例: 7203.T または AAPL)",
      "company_name": "会社名(日本語)",
      "action": "BUY",
      "amount_jpy": 購入金額(整数・円),
      "reason": "購入理由を2〜3文で説明"
    }}
  ]
}}

注意事項：
- tickerは実在する銘柄コードを使用すること（日本株は末尾に.T）
- 全銘柄の amount_jpy の合計が {amount_jpy} 円を超えないようにすること
- 必ずJSON形式のみで返答すること
"""


def _extract_json(text: str) -> dict:
    """レスポンステキストからJSONを抽出してパース"""
    # コードブロック除去
    text = re.sub(r"```(?:json)?", "", text).strip()
    # 最初の { から最後の } までを抽出
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"JSONが見つかりません: {text[:200]}")
    return json.loads(text[start:end])


async def analyze_with_gemini(amount_jpy: float) -> dict:
    """Gemini APIでトレード分析"""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-2.0-flash-exp",
        generation_config={"response_mime_type": "application/json"}
    )

    today = datetime.now().strftime("%Y年%m月%d日")
    prompt = TRADE_PROMPT_TEMPLATE.format(today=today, amount_jpy=int(amount_jpy))

    # Web検索グラウンディングを使用（最新情報取得）
    try:
        from google.generativeai.types import Tool, GoogleSearchRetrieval
        search_tool = Tool(google_search_retrieval=GoogleSearchRetrieval())
        response = await asyncio.to_thread(
            model.generate_content, prompt, tools=[search_tool]
        )
    except Exception:
        # グラウンディングが使えない場合はそのまま実行
        response = await asyncio.to_thread(model.generate_content, prompt)

    return _extract_json(response.text)


async def analyze_with_claude(amount_jpy: float) -> dict:
    """Claude APIでトレード分析"""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY が設定されていません")

    client = anthropic.Anthropic(api_key=api_key)
    today = datetime.now().strftime("%Y年%m月%d日")
    prompt = TRADE_PROMPT_TEMPLATE.format(today=today, amount_jpy=int(amount_jpy))

    response = await asyncio.to_thread(
        client.messages.create,
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    # テキストブロックを結合
    text = " ".join(
        block.text for block in response.content if hasattr(block, "text")
    )
    return _extract_json(text)


async def get_ai_trade_suggestion(amount_jpy: float) -> dict:
    """
    設定されたAIプロバイダーでトレード提案を取得する

    Returns:
        {
          "summary": str,
          "trades": [{"ticker": str, "company_name": str, "action": str, "amount_jpy": int, "reason": str}]
        }
    """
    provider = AI_PROVIDER
    print(f"[AI] プロバイダー: {provider}, 分析金額: {amount_jpy:,.0f}円")

    try:
        if provider == "gemini":
            return await analyze_with_gemini(amount_jpy)
        elif provider == "claude":
            return await analyze_with_claude(amount_jpy)
        else:
            raise ValueError(f"不明なAIプロバイダー: {provider}")
    except Exception as e:
        print(f"[AI] エラー: {e}")
        raise
