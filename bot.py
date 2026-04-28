"""
bot.py - Discord Bot メインファイル
コマンド一覧:
  /trade [amount]   - 手動でAI分析トレードを実行
  /portfolio        - ポートフォリオを表示
  /history          - トレード履歴を表示
  /status           - Bot の状態確認
"""
import os
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
from src.trader import run_ai_auto_trade, execute_trade
from src.stock_fetcher import get_current_portfolio_value_jpy
from src import embeds

# ---------- 設定 ----------
TOKEN = os.getenv("DISCORD_TOKEN")
TRADE_CHANNEL_ID = int(os.getenv("TRADE_CHANNEL_ID", "0"))
DAILY_AMOUNT = float(os.getenv("DAILY_TRADE_AMOUNT", "10000"))
TRADE_HOUR = int(os.getenv("DAILY_TRADE_HOUR", "9"))
TRADE_MINUTE = int(os.getenv("DAILY_TRADE_MINUTE", "0"))
JST = pytz.timezone("Asia/Tokyo")

# ---------- Bot セットアップ ----------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
scheduler = AsyncIOScheduler(timezone=JST)


# ---------- 自動トレード ----------
async def daily_auto_trade():
    """毎日定時に実行される自動トレード"""
    channel = bot.get_channel(TRADE_CHANNEL_ID)
    if not channel:
        print(f"[Scheduler] チャンネルID {TRADE_CHANNEL_ID} が見つかりません")
        return

    print(f"[Scheduler] 自動トレード開始 ({DAILY_AMOUNT:,.0f}円)")
    await channel.send(
        embed=discord.Embed(
            title="🤖 自動トレード開始",
            description=f"本日の自動トレードを開始します。分析金額: **{DAILY_AMOUNT:,.0f}円**\nAIが最新情報を収集中です...",
            color=discord.Color.yellow()
        )
    )

    try:
        result = await run_ai_auto_trade(DAILY_AMOUNT)
        embed = embeds.trade_result_embed(result, is_auto=True)
        await channel.send(embed=embed)
    except Exception as e:
        await channel.send(
            embed=discord.Embed(
                title="❌ 自動トレードエラー",
                description=f"エラーが発生しました: {str(e)}",
                color=discord.Color.red()
            )
        )
        print(f"[Scheduler] エラー: {e}")


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
        embed = embeds.trade_result_embed(result, is_auto=False)
        embed.title = f"📈 手動トレード実行 ({amount:,}円)"
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(
            embed=discord.Embed(
                title="❌ トレードエラー",
                description=f"{str(e)}",
                color=discord.Color.red()
            )
        )


@tree.command(name="portfolio", description="現在のポートフォリオを表示します")
async def portfolio_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    portfolio = db.get_portfolio()
    holdings = db.get_holdings()

    # 現在価格で評価
    valuations = await get_current_portfolio_value_jpy(holdings)
    embed = embeds.portfolio_embed(dict(portfolio), holdings, valuations)
    await interaction.followup.send(embed=embed)


@tree.command(name="history", description="直近のトレード履歴を表示します")
async def history_command(interaction: discord.Interaction):
    trades = db.get_recent_trades(10)
    embed = embeds.history_embed(trades)
    await interaction.followup.send(embed=embed)


@tree.command(name="status", description="Botの状態を確認します")
async def status_command(interaction: discord.Interaction):
    next_run = scheduler.get_job("daily_trade")
    next_run_str = (
        next_run.next_run_time.astimezone(JST).strftime("%Y/%m/%d %H:%M JST")
        if next_run and next_run.next_run_time
        else "未設定"
    )

    provider = os.getenv("AI_PROVIDER", "gemini").upper()
    embed = discord.Embed(
        title="🤖 Bot ステータス",
        color=discord.Color.blue()
    )
    embed.add_field(name="状態", value="✅ 稼働中", inline=True)
    embed.add_field(name="AIプロバイダー", value=provider, inline=True)
    embed.add_field(name="次回自動トレード", value=next_run_str, inline=False)
    embed.add_field(name="自動トレード金額", value=f"{DAILY_AMOUNT:,.0f}円", inline=True)
    await interaction.response.send_message(embed=embed)


# ---------- Bot イベント ----------

@bot.event
async def on_ready():
    print(f"[Bot] ログイン成功: {bot.user} (ID: {bot.user.id})")

    # DB初期化
    db.init_db()

    # コマンド同期
    try:
        synced = await tree.sync()
        print(f"[Bot] スラッシュコマンドを同期: {len(synced)}件")
    except Exception as e:
        print(f"[Bot] コマンド同期エラー: {e}")

    # スケジューラー設定（毎日JST指定時刻）
    scheduler.add_job(
        daily_auto_trade,
        CronTrigger(hour=TRADE_HOUR, minute=TRADE_MINUTE, timezone=JST),
        id="daily_trade",
        replace_existing=True
    )
    scheduler.start()
    print(f"[Scheduler] 毎日 {TRADE_HOUR:02d}:{TRADE_MINUTE:02d} JST に自動トレードを実行します")

    # 起動通知
    channel = bot.get_channel(TRADE_CHANNEL_ID)
    if channel:
        await channel.send(
            embed=discord.Embed(
                title="🚀 擬似トレードBot 起動",
                description=(
                    f"**AIプロバイダー**: {os.getenv('AI_PROVIDER', 'gemini').upper()}\n"
                    f"**毎日の自動トレード**: {TRADE_HOUR:02d}:{TRADE_MINUTE:02d} JST / {DAILY_AMOUNT:,.0f}円\n\n"
                    "スラッシュコマンド:\n"
                    "`/trade [金額]` - 手動トレード\n"
                    "`/portfolio` - ポートフォリオ確認\n"
                    "`/history` - トレード履歴\n"
                    "`/status` - Bot状態確認"
                ),
                color=discord.Color.green()
            )
        )


# ---------- 起動 ----------
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN が設定されていません。.env ファイルを確認してください。")
    bot.run(TOKEN)
