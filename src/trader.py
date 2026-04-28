"""
trader.py - トレード実行ロジック
"""
import math
from typing import Optional
from . import database as db
from .stock_fetcher import get_stock_price_jpy
from .ai_analyzer import get_ai_trade_suggestion


async def execute_trade(
    ticker: str,
    company_name: str,
    amount_jpy: float,
    ai_reasoning: str = "",
    is_auto: bool = True
) -> dict:
    """
    指定金額で銘柄を購入する擬似トレードを実行する

    Returns:
        {"success": bool, "message": str, "details": dict}
    """
    portfolio = db.get_portfolio()
    cash = portfolio["cash_jpy"]

    if amount_jpy > cash:
        return {
            "success": False,
            "message": f"残高不足です。残高: {cash:,.0f}円 / 必要: {amount_jpy:,.0f}円",
            "details": {}
        }

    # 現在株価を取得
    price_jpy = await get_stock_price_jpy(ticker)
    if not price_jpy:
        return {
            "success": False,
            "message": f"{ticker} の株価を取得できませんでした",
            "details": {}
        }

    # 購入株数（小数点2位まで）
    shares = math.floor((amount_jpy / price_jpy) * 100) / 100
    if shares <= 0:
        return {
            "success": False,
            "message": f"株価({price_jpy:,.0f}円)に対して購入金額({amount_jpy:,.0f}円)が少なすぎます",
            "details": {}
        }

    actual_amount = shares * price_jpy

    # DB更新
    db.update_cash(-actual_amount)
    db.upsert_holding(ticker, company_name, shares, price_jpy)
    db.record_trade(
        trade_type="BUY",
        ticker=ticker,
        company_name=company_name,
        shares=shares,
        price_jpy=price_jpy,
        amount_jpy=actual_amount,
        ai_reasoning=ai_reasoning,
        is_auto=is_auto
    )

    return {
        "success": True,
        "message": "購入成功",
        "details": {
            "ticker": ticker,
            "company_name": company_name,
            "shares": shares,
            "price_jpy": price_jpy,
            "amount_jpy": actual_amount,
        }
    }


async def run_ai_auto_trade(amount_jpy: float) -> dict:
    """
    AIの判断に基づいて自動トレードを実行する

    Returns:
        {"summary": str, "results": [{"ticker": str, ..., "trade_result": dict}]}
    """
    # AI分析
    analysis = await get_ai_trade_suggestion(amount_jpy)
    trades = analysis.get("trades", [])
    summary = analysis.get("summary", "")

    results = []
    for trade in trades:
        ticker = trade.get("ticker", "")
        company_name = trade.get("company_name", ticker)
        trade_amount = float(trade.get("amount_jpy", 0))
        reason = trade.get("reason", "")

        if not ticker or trade_amount <= 0:
            continue

        result = await execute_trade(
            ticker=ticker,
            company_name=company_name,
            amount_jpy=trade_amount,
            ai_reasoning=reason,
            is_auto=True
        )
        results.append({
            **trade,
            "trade_result": result
        })

    return {"summary": summary, "results": results}
