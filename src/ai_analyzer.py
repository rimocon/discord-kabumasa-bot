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


def build_prompt(amount_jpy: float, holdings_info: str) -> str:
    today = datetime.now().strftime("%Y年%m月%d日")
    return f"""
あなたは優秀な株式アナリストです。今日の日付は {today} です。

【現在の保有銘柄】
{holdings_info}

【タスク】
最新ニュースや市場動向を調査し、以下を判断してください：
1. 保有銘柄について → 売却すべきか（SELL）、そのまま保有か（HOLD）
2. 新規購入について → 買い目な銘柄があれば購入（BUY）。新規購入の合計は {int(amount_jpy)}円 以内

【回答形式】
必ず以下のJSON形式のみで回答してください。前後に余計なテキストを含めないこと：

{{
  "summary": "本日の市場概況と判断の要点を2〜3文で説明",
  "trades": [
    {{
      "ticker": "銘柄コード(例: 7203.T または AAPL)",
      "company_name": "会社名(日本語)",
      "action": "SELL または BUY",
      "sell_ratio": 売却割合(0.0〜1.0, SELLのみ必須。1.0=全売却),
      "amount_jpy": 購入金額(整数・円, BUYのみ必須),
      "reason": "判断理由を2〜3文で説明"
    }}
  ]
}}

【注意事項】
- HOLDの銘柄はtradesに含めない（何もしない）
- SELLはすでに保有している銘柄のみ指定できる
- BUYのticker は実在する銘柄コード（日本株は末尾に.T）
- BUY の amount_jpy の合計が {int(amount_jpy)} 円を超えないこと
- 売却後に得た現金は今回のBUYには使わない（当日の購入予算は {int(amount_jpy)} 円固定）
- tradesが空の場合は {{"summary": "...", "trades": []}} を返す
- 必ずJSON形式のみで返答すること
"""


def _extract_json(text: str) -> dict:
    """レスポンステキストからJSONを抽出してパース"""
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"JSONが見つかりません: {text[:200]}")
    return json.loads(text[start:end])


def _format_holdings(holdings: list, valuations: dict) -> str:
    """保有銘柄をプロンプト用テキストに整形"""
    if not holdings:
        return "なし（現在保有銘柄はありません）"
    lines = []
    for h in holdings:
        v = valuations.get(h["ticker"], {})
        gl  = v.get("gain_loss_jpy", 0)
        glp = v.get("gain_loss_pct", 0)
        mv  = v.get("market_value_jpy", h["avg_cost_jpy"] * h["shares"])
        sign = "+" if gl >= 0 else ""
        lines.append(
            f"- {h['company_name']} ({h['ticker']}): "
            f"{h['shares']:.2f}株, 評価額 {mv:,.0f}円, "
            f"損益 {sign}{gl:,.0f}円 ({sign}{glp:.1f}%)"
        )
    return "\n".join(lines)


async def analyze_with_gemini(prompt: str) -> dict:
    """Gemini APIでトレード分析"""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-2.5-flash-lite",
        generation_config={"response_mime_type": "application/json"}
    )

    try:
        from google.generativeai.types import Tool, GoogleSearchRetrieval
        search_tool = Tool(google_search_retrieval=GoogleSearchRetrieval())
        response = await asyncio.to_thread(
            model.generate_content, prompt, tools=[search_tool]
        )
    except Exception:
        response = await asyncio.to_thread(model.generate_content, prompt)

    return _extract_json(response.text)


async def analyze_with_claude(prompt: str) -> dict:
    """Claude APIでトレード分析"""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY が設定されていません")

    client = anthropic.Anthropic(api_key=api_key)

    response = await asyncio.to_thread(
        client.messages.create,
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    text = " ".join(
        block.text for block in response.content if hasattr(block, "text")
    )
    return _extract_json(text)


async def get_ai_trade_suggestion(amount_jpy: float, holdings: list, valuations: dict) -> dict:
    """
    保有状況を渡してAIにBUY/SELL/HOLDを判断させる

    Args:
        amount_jpy: 新規購入に使える予算（円）
        holdings:   DB の holdings レコードリスト
        valuations: stock_fetcher の評価額dict

    Returns:
        {
          "summary": str,
          "trades": [
            {"ticker": str, "company_name": str, "action": "BUY"|"SELL",
             "sell_ratio": float,  # SELLのみ
             "amount_jpy": int,    # BUYのみ
             "reason": str}
          ]
        }
    """
    provider = AI_PROVIDER
    holdings_info = _format_holdings(holdings, valuations)
    prompt = build_prompt(amount_jpy, holdings_info)

    print(f"[AI] プロバイダー: {provider}, 予算: {amount_jpy:,.0f}円, 保有: {len(holdings)}銘柄")

    try:
        if provider == "gemini":
            return await analyze_with_gemini(prompt)
        elif provider == "claude":
            return await analyze_with_claude(prompt)
        else:
            raise ValueError(f"不明なAIプロバイダー: {provider}")
    except Exception as e:
        print(f"[AI] エラー: {e}")
        raise
