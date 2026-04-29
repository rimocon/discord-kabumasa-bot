"""
bot.py - Discord Bot メインファイル
コマンド一覧:
  /trade [amount]         - AI分析トレードを実行
  /sell <ticker> [ratio]  - 保有株を売却（オートコンプリート対応）
  /portfolio              - ポートフォリオを円グラフ付きで表示
  /history                - トレード履歴を表示
  /status                 - Bot の状態確認
"""
import os
import io
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from dotenv import load_dotenv

load_dotenv()

from src import database as db
from src.trader import run_ai_auto_trade, execute_trade, execute_sell, get_portfolio_snapshot
from src.stock_fetcher import get_current_portfolio_value_jpy
from src.chart import generate_portfolio_chart
from src import embeds

# ---------- 設定 ----------
TOKEN            = os.getenv("DISCORD_TOKEN")
TRADE_CHANNEL_ID = int(os.getenv("TRADE_CHANNEL_ID", "0"))
DAILY_AMOUNT     = float(os.getenv("DAILY_TRADE_AMOUNT", "10000"))
TRADE_HOUR       = int(os.getenv("DAILY_TRADE_HOUR", "9"))
TRADE_MINUTE     = int(os.getenv("DAILY_TRADE_MINUTE", "0"))
JST              = pytz.timezone("Asia/Tokyo")

# ---------- Bot セットアップ ----------
intents = discord.Intents.default()
intents.message_content = True

bot       = commands.Bot(command_prefix="!", intents=intents)
tree      = bot.tree
scheduler = AsyncIOScheduler(timezone=JST)


# ---------- ヘルパー: ポートフォリオを画像付きで送信 ----------
async def send_portfolio(target, label: str = ""):
    snapshot    = await get_portfolio_snapshot()
    chart_bytes = await generate_portfolio_chart(snapshot)
    embed       = embeds.portfolio_summary_embed(snapshot)
    if label:
        embed.title = label

    if chart_bytes:
        file = discord.File(io.BytesIO(chart_bytes), filename="portfolio.png")
        await target.send(embed=embed, file=file)
    else:
        embed.set_image(url=None)
        await target.send(embed=embed)


# ---------- 自動トレード ----------
async def daily_auto_trade():
    channel = bot.get_channel(TRADE_CHANNEL_ID)
    if not channel:
        print(f"[Scheduler] チャンネルID {TRADE_CHANNEL_ID} が見つかりません")
        return

    print(f"[Scheduler] 自動トレード開始 ({DAILY_AMOUNT:,.0f}円)")

    # ① 開始通知
    await channel.send(
        embed=discord.Embed(
            title="🤖 自動トレード開始",
            description=(
                f"本日の自動トレードを開始します。分析金額: **{DAILY_AMOUNT:,.0f}円**\n"
                "AIが最新情報を収集中です…"
            ),
            color=discord.Color.yellow()
        )
    )

    try:
        # ② トレード実行
        result = await run_ai_auto_trade(DAILY_AMOUNT)

        # ③ トレード結果を投稿
        await channel.send(embed=embeds.trade_result_embed(result, is_auto=True))

        # ④ 最新ポートフォリオを円グラフ付きで投稿
        await send_portfolio(channel, label="💼 本日のトレード後ポートフォリオ")

    except Exception as e:
        await channel.send(
            embed=discord.Embed(
                title="❌ 自動トレードエラー",
                description=f"エラーが発生しました: {str(e)}",
                color=discord.Color.red()
            )
        )
        print(f"[Scheduler] エラー: {e}")


# ---------- オートコンプリート: 保有銘柄 ----------
async def holding_ticker_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    holdings = db.get_holdings()
    return [
        app_commands.Choice(
            name=f"{h['company_name']} ({h['ticker']})",
            value=h["ticker"]
        )
        for h in holdings
        if current.lower() in h["ticker"].lower() or current.lower() in h["company_name"].lower()
    ][:25]


# ---------- スラッシュコマンド ----------

@tree.command(name="trade", description="AI分析に基づいて擬似トレードを実行します")
@app_commands.describe(amount="トレード金額（円）例: 10000")
async def trade_command(interaction: discord.Interaction, amount: int = int(DAILY_AMOUNT)):
    await interaction.response.defer(thinking=True)

    if amount <= 0:
        await interaction.followup.send("❌ 金額は1円以上を指定してください")
        return

    try:
        result = await run_ai_auto_trade(float(amount))
        trade_embed = embeds.trade_result_embed(result, is_auto=False)
        trade_embed.title = f"📈 手動トレード実行 ({amount:,}円)"
        await interaction.followup.send(embed=trade_embed)
        await send_portfolio(interaction.followup)
    except Exception as e:
        await interaction.followup.send(
            embed=discord.Embed(
                title="❌ トレードエラー",
                description=str(e),
                color=discord.Color.red()
            )
        )


@tree.command(name="sell", description="保有株を売却します")
@app_commands.describe(
    ticker="売却する銘柄（入力で候補が出ます）",
    ratio="売却割合 0.0〜1.0 (デフォルト: 1.0=全売却)"
)
@app_commands.autocomplete(ticker=holding_ticker_autocomplete)
async def sell_command(
    interaction: discord.Interaction,
    ticker: str,
    ratio: float = 1.0
):
    await interaction.response.defer(thinking=True)

    if not (0 < ratio <= 1.0):
        await interaction.followup.send("❌ ratioは0より大きく1.0以下で指定してください")
        return

    result = await execute_sell(ticker=ticker.upper(), sell_ratio=ratio, is_auto=False)
    await interaction.followup.send(embed=embeds.sell_result_embed(result))

    if result["success"]:
        await send_portfolio(interaction.followup, label="💼 売却後ポートフォリオ")


@tree.command(name="portfolio", description="現在のポートフォリオを円グラフ付きで表示します")
async def portfolio_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    await send_portfolio(interaction.followup)


@tree.command(name="history", description="直近のトレード履歴を表示します")
async def history_command(interaction: discord.Interaction):
    trades = db.get_recent_trades(10)
    await interaction.response.send_message(embed=embeds.history_embed(trades))


@tree.command(name="status", description="Botの状態を確認します")
async def status_command(interaction: discord.Interaction):
    next_run = scheduler.get_job("daily_trade")
    next_run_str = (
        next_run.next_run_time.astimezone(JST).strftime("%Y/%m/%d %H:%M JST")
        if next_run and next_run.next_run_time
        else "未設定"
    )
    provider = os.getenv("AI_PROVIDER", "gemini").upper()
    embed = discord.Embed(title="🤖 Bot ステータス", color=discord.Color.blue())
    embed.add_field(name="状態",            value="✅ 稼働中",              inline=True)
    embed.add_field(name="AIプロバイダー",   value=provider,                 inline=True)
    embed.add_field(name="次回自動トレード",  value=next_run_str,             inline=False)
    embed.add_field(name="自動トレード金額",  value=f"{DAILY_AMOUNT:,.0f}円", inline=True)
    await interaction.response.send_message(embed=embed)


# ---------- Bot イベント ----------

@bot.event
async def on_ready():
    print(f"[Bot] ログイン成功: {bot.user} (ID: {bot.user.id})")
    db.init_db()

    try:
        synced = await tree.sync()
        print(f"[Bot] スラッシュコマンドを同期: {len(synced)}件")
    except Exception as e:
        print(f"[Bot] コマンド同期エラー: {e}")

    scheduler.add_job(
        daily_auto_trade,
        CronTrigger(hour=TRADE_HOUR, minute=TRADE_MINUTE, timezone=JST),
        id="daily_trade",
        replace_existing=True
    )
    scheduler.start()
    print(f"[Scheduler] 毎日 {TRADE_HOUR:02d}:{TRADE_MINUTE:02d} JST に自動トレードを実行します")

    channel = bot.get_channel(TRADE_CHANNEL_ID)
    if channel:
        await channel.send(
            embed=discord.Embed(
                title="🚀 擬似トレードBot 起動",
                description=(
                    f"**AIプロバイダー**: {os.getenv('AI_PROVIDER', 'gemini').upper()}\n"
                    f"**毎日の自動トレード**: {TRADE_HOUR:02d}:{TRADE_MINUTE:02d} JST / {DAILY_AMOUNT:,.0f}円\n\n"
                    "スラッシュコマンド:\n"
                    "`/trade [金額]` — 手動トレード\n"
                    "`/sell <銘柄> [割合]` — 売却\n"
                    "`/portfolio` — ポートフォリオ (円グラフ)\n"
                    "`/history` — トレード履歴\n"
                    "`/status` — Bot状態確認"
                ),
                color=discord.Color.green()
            )
        )


# ---------- 起動 ----------
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN が設定されていません。.env ファイルを確認してください。")
    bot.run(TOKEN)
