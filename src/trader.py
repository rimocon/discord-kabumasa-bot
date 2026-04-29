"""
trader.py - トレード実行ロジック
"""
import math
from typing import Optional
from . import database as db
from .stock_fetcher import get_stock_price_jpy, get_current_portfolio_value_jpy
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


async def execute_sell(
    ticker: str,
    sell_ratio: float = 1.0,  # 0.0〜1.0 (1.0=全売却)
    is_auto: bool = False
) -> dict:
    """
    保有株を売却する擬似トレードを実行する

    Args:
        ticker:     銘柄コード
        sell_ratio: 売却割合 (デフォルト1.0=全売却)
    Returns:
        {"success": bool, "message": str, "details": dict}
    """
    holding = db.get_holding(ticker)
    if not holding:
        return {
            "success": False,
            "message": f"{ticker} は保有していません",
            "details": {}
        }

    sell_ratio = max(0.01, min(1.0, sell_ratio))
    shares_to_sell = math.floor(holding["shares"] * sell_ratio * 100) / 100
    if shares_to_sell <= 0:
        return {
            "success": False,
            "message": "売却株数が0になりました",
            "details": {}
        }

    price_jpy = await get_stock_price_jpy(ticker)
    if not price_jpy:
        return {
            "success": False,
            "message": f"{ticker} の株価を取得できませんでした",
            "details": {}
        }

    amount_jpy = shares_to_sell * price_jpy
    cost_basis  = holding["avg_cost_jpy"] * shares_to_sell
    gain_loss   = amount_jpy - cost_basis
    gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0

    # DB更新
    db.update_cash(amount_jpy)
    db.upsert_holding(ticker, holding["company_name"], -shares_to_sell, price_jpy)
    db.record_trade(
        trade_type="SELL",
        ticker=ticker,
        company_name=holding["company_name"],
        shares=shares_to_sell,
        price_jpy=price_jpy,
        amount_jpy=amount_jpy,
        ai_reasoning="",
        is_auto=is_auto
    )

    return {
        "success": True,
        "message": "売却成功",
        "details": {
            "ticker": ticker,
            "company_name": holding["company_name"],
            "shares": shares_to_sell,
            "price_jpy": price_jpy,
            "amount_jpy": amount_jpy,
            "gain_loss_jpy": gain_loss,
            "gain_loss_pct": gain_loss_pct,
        }
    }


async def run_ai_auto_trade(amount_jpy: float) -> dict:
    """
    AIの判断に基づいて自動トレードを実行する（SELL→BUYの順）

    Returns:
        {"summary": str, "results": [{"ticker": str, ..., "trade_result": dict}]}
    """
    # 現在の保有状況を取得してAIに渡す
    holdings   = db.get_holdings()
    valuations = await get_current_portfolio_value_jpy(holdings)

    analysis = await get_ai_trade_suggestion(amount_jpy, list(holdings), valuations)
    trades   = analysis.get("trades", [])
    summary  = analysis.get("summary", "")

    # SELL → BUY の順に実行（資金確保を先に）
    sell_trades = [t for t in trades if t.get("action", "").upper() == "SELL"]
    buy_trades  = [t for t in trades if t.get("action", "").upper() == "BUY"]

    results = []

    for trade in sell_trades:
        ticker = trade.get("ticker", "").upper()
        ratio  = float(trade.get("sell_ratio", 1.0))
        reason = trade.get("reason", "")
        if not ticker:
            continue

        # ai_reasoning を record_trade に渡すため execute_sell を直接拡張せず
        # ここで呼んだ後に DB の最後のトレードを更新する簡易対応
        result = await execute_sell(ticker=ticker, sell_ratio=ratio, is_auto=True)
        if result["success"] and reason:
            # reasoning を後から書き込む
            _update_last_trade_reasoning(ticker, reason)

        results.append({**trade, "trade_result": result})

    for trade in buy_trades:
        ticker       = trade.get("ticker", "")
        company_name = trade.get("company_name", ticker)
        trade_amount = float(trade.get("amount_jpy", 0))
        reason       = trade.get("reason", "")
        if not ticker or trade_amount <= 0:
            continue

        result = await execute_trade(
            ticker=ticker,
            company_name=company_name,
            amount_jpy=trade_amount,
            ai_reasoning=reason,
            is_auto=True
        )
        results.append({**trade, "trade_result": result})

    return {"summary": summary, "results": results}


def _update_last_trade_reasoning(ticker: str, reasoning: str):
    """直近のSELLトレードにAI根拠を書き込む"""
    try:
        with db.get_connection() as conn:
            conn.execute(
                """UPDATE trades SET ai_reasoning = ?
                   WHERE ticker = ? AND trade_type = 'SELL'
                   AND id = (SELECT MAX(id) FROM trades WHERE ticker = ? AND trade_type = 'SELL')""",
                (reasoning, ticker, ticker)
            )
    except Exception as e:
        print(f"[DB] reasoning更新失敗: {e}")


async def get_portfolio_snapshot() -> dict:
    """現在のポートフォリオの評価情報をまとめて返す"""
    portfolio = db.get_portfolio()
    holdings  = db.get_holdings()
    valuations = await get_current_portfolio_value_jpy(holdings)

    cash = portfolio["cash_jpy"]
    total_market_value = sum(v["market_value_jpy"] for v in valuations.values())
    total_gain_loss    = sum(v["gain_loss_jpy"]    for v in valuations.values())
    initial_balance    = float(__import__("os").getenv("INITIAL_BALANCE", "1000000"))
    total_value        = cash + total_market_value

    return {
        "portfolio": dict(portfolio),
        "holdings":  [dict(h) for h in holdings],
        "valuations": valuations,
        "cash": cash,
        "total_market_value": total_market_value,
        "total_gain_loss": total_gain_loss,
        "total_value": total_value,
        "initial_balance": initial_balance,
    }
