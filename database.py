"""
database.py - SQLiteによるポートフォリオ・トレード履歴の永続化
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "portfolio.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """テーブル初期化"""
    initial_balance = float(os.getenv("INITIAL_BALANCE", "1000000"))
    with get_connection() as conn:
        conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY,
                cash_jpy REAL NOT NULL DEFAULT {initial_balance},
                total_invested_jpy REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                company_name TEXT NOT NULL,
                shares REAL NOT NULL DEFAULT 0,
                avg_cost_jpy REAL NOT NULL DEFAULT 0,
                purchased_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(ticker)
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_type TEXT NOT NULL,          -- 'BUY' or 'SELL'
                ticker TEXT NOT NULL,
                company_name TEXT NOT NULL,
                shares REAL NOT NULL,
                price_jpy REAL NOT NULL,           -- 約定単価(円)
                amount_jpy REAL NOT NULL,          -- 合計金額(円)
                ai_reasoning TEXT,                 -- AIの判断根拠
                executed_at TEXT NOT NULL DEFAULT (datetime('now')),
                is_auto INTEGER NOT NULL DEFAULT 1 -- 1=自動, 0=手動
            );

            INSERT OR IGNORE INTO portfolio (id, cash_jpy) VALUES (1, {initial_balance});
        """)
    print("[DB] 初期化完了")


# ---------- Portfolio ----------

def get_portfolio() -> sqlite3.Row:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM portfolio WHERE id=1").fetchone()


def update_cash(delta_jpy: float):
    """現金残高を増減する"""
    with get_connection() as conn:
        conn.execute(
            "UPDATE portfolio SET cash_jpy = cash_jpy + ?, updated_at = ? WHERE id=1",
            (delta_jpy, datetime.utcnow().isoformat())
        )


# ---------- Holdings ----------

def get_holdings() -> list:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM holdings ORDER BY ticker").fetchall()


def get_holding(ticker: str) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM holdings WHERE ticker=?", (ticker,)).fetchone()


def upsert_holding(ticker: str, company_name: str, shares_delta: float, price_jpy: float):
    """保有株を更新（買い増し・売却）"""
    with get_connection() as conn:
        existing = conn.execute("SELECT * FROM holdings WHERE ticker=?", (ticker,)).fetchone()
        now = datetime.utcnow().isoformat()
        if existing:
            new_shares = existing["shares"] + shares_delta
            if new_shares <= 0.0001:
                conn.execute("DELETE FROM holdings WHERE ticker=?", (ticker,))
            else:
                # 買い増し時のみ平均取得単価を更新
                if shares_delta > 0:
                    total_cost = existing["avg_cost_jpy"] * existing["shares"] + price_jpy * shares_delta
                    new_avg = total_cost / new_shares
                else:
                    new_avg = existing["avg_cost_jpy"]
                conn.execute(
                    "UPDATE holdings SET shares=?, avg_cost_jpy=?, updated_at=? WHERE ticker=?",
                    (new_shares, new_avg, now, ticker)
                )
        else:
            if shares_delta > 0:
                conn.execute(
                    "INSERT INTO holdings (ticker, company_name, shares, avg_cost_jpy, purchased_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (ticker, company_name, shares_delta, price_jpy, now, now)
                )


# ---------- Trades ----------

def record_trade(
    trade_type: str,
    ticker: str,
    company_name: str,
    shares: float,
    price_jpy: float,
    amount_jpy: float,
    ai_reasoning: str = "",
    is_auto: bool = True
):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO trades
               (trade_type, ticker, company_name, shares, price_jpy, amount_jpy, ai_reasoning, executed_at, is_auto)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (trade_type, ticker, company_name, shares, price_jpy, amount_jpy,
             ai_reasoning, datetime.utcnow().isoformat(), 1 if is_auto else 0)
        )


def get_recent_trades(limit: int = 10) -> list:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM trades ORDER BY executed_at DESC LIMIT ?", (limit,)
        ).fetchall()
