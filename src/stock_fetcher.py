"""
stock_fetcher.py - yfinanceを使って株価(円換算)を取得する
"""
import asyncio
from typing import Optional
import yfinance as yf


# USD→JPY レートの簡易取得（為替ティッカーから）
async def get_usd_jpy_rate() -> float:
    try:
        ticker = await asyncio.to_thread(yf.Ticker, "JPY=X")
        info = await asyncio.to_thread(lambda: ticker.fast_info)
        rate = getattr(info, "last_price", None)
        if rate and rate > 0:
            return float(rate)
    except Exception as e:
        print(f"[Stock] 為替レート取得失敗: {e}")
    return 150.0  # フォールバック


async def get_stock_price_jpy(ticker: str) -> Optional[float]:
    """
    株価を円で返す。
    日本株 (.T suffix) はそのまま円、米国株はUSD→JPY換算。
    """
    try:
        yf_ticker = await asyncio.to_thread(yf.Ticker, ticker)
        
        # fast_infoの代わりにhistory(period="1d")を使用
        # 1日分の履歴を取得し、その最後の終値(Close)を取得する
        df = await asyncio.to_thread(yf_ticker.history, period="1d")
        
        if df.empty:
            print(f"[Stock] {ticker} のデータが空です")
            return None
            
        price = df['Close'].iloc[-1]
        print(f"{ticker}: {price}")

        if price is None or price <= 0:
            return None

        # 日本株はすでに円
        if ticker.upper().endswith(".T"):
            return float(price)

        # 米国株はドル→円換算
        rate = await get_usd_jpy_rate()
        return float(price) * rate
    except Exception as e:
        print(f"[Stock] {ticker} の株価取得失敗: {e}")
        return None

async def get_current_portfolio_value_jpy(holdings: list) -> dict:
    """
    保有銘柄の現在評価額を計算する

    Returns:
        {ticker: {"current_price_jpy": float, "market_value_jpy": float, "gain_loss_jpy": float, "gain_loss_pct": float}}
    """
    result = {}
    for holding in holdings:
        ticker = holding["ticker"]
        current_price = await get_stock_price_jpy(ticker)
        if current_price:
            market_value = current_price * holding["shares"]
            cost_basis = holding["avg_cost_jpy"] * holding["shares"]
            gain_loss = market_value - cost_basis
            gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0
            result[ticker] = {
                "current_price_jpy": current_price,
                "market_value_jpy": market_value,
                "gain_loss_jpy": gain_loss,
                "gain_loss_pct": gain_loss_pct,
            }
        else:
            # 株価取得失敗時はコスト基準で評価
            result[ticker] = {
                "current_price_jpy": holding["avg_cost_jpy"],
                "market_value_jpy": holding["avg_cost_jpy"] * holding["shares"],
                "gain_loss_jpy": 0,
                "gain_loss_pct": 0,
            }
    return result
