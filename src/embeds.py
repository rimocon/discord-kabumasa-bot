"""
embeds.py - Discordの見やすいEmbedメッセージを生成する
"""
import discord
from datetime import datetime
from typing import Optional


def trade_result_embed(trade_data: dict, is_auto: bool = True) -> discord.Embed:
    """トレード実行結果のEmbed"""
    summary = trade_data.get("summary", "")
    results = trade_data.get("results", [])

    success_count = sum(1 for r in results if r.get("trade_result", {}).get("success"))
    fail_count = len(results) - success_count

    color = discord.Color.green() if success_count > 0 else discord.Color.red()
    title = "🤖 AI自動トレード実行" if is_auto else "📈 手動トレード実行"

    embed = discord.Embed(
        title=title,
        description=f"**本日の市場概況**\n{summary}" if summary else "",
        color=color,
        timestamp=datetime.utcnow()
    )

    for r in results:
        trade_result = r.get("trade_result", {})
        details = trade_result.get("details", {})
        ticker = r.get("ticker", "?")
        company = r.get("company_name", ticker)
        reason = r.get("reason", "")

        if trade_result.get("success"):
            field_value = (
                f"✅ **購入成功**\n"
                f"単価: {details.get('price_jpy', 0):,.0f}円\n"
                f"株数: {details.get('shares', 0):.2f}株\n"
                f"金額: {details.get('amount_jpy', 0):,.0f}円\n"
                f"理由: {reason}"
            )
        else:
            field_value = (
                f"❌ **購入失敗**\n"
                f"{trade_result.get('message', '不明なエラー')}\n"
                f"理由: {reason}"
            )

        embed.add_field(
            name=f"📊 {company} ({ticker})",
            value=field_value,
            inline=False
        )

    embed.set_footer(text=f"成功: {success_count}件 / 失敗: {fail_count}件")
    return embed


def single_trade_embed(ticker: str, company_name: str, amount_jpy: float, result: dict) -> discord.Embed:
    """単一トレードのEmbed"""
    details = result.get("details", {})
    success = result.get("success", False)

    embed = discord.Embed(
        title="📈 トレード実行結果",
        color=discord.Color.green() if success else discord.Color.red(),
        timestamp=datetime.utcnow()
    )

    if success:
        embed.add_field(name="銘柄", value=f"{company_name} ({ticker})", inline=True)
        embed.add_field(name="単価", value=f"{details.get('price_jpy', 0):,.0f}円", inline=True)
        embed.add_field(name="株数", value=f"{details.get('shares', 0):.2f}株", inline=True)
        embed.add_field(name="合計金額", value=f"{details.get('amount_jpy', 0):,.0f}円", inline=True)
        embed.description = "✅ 購入が完了しました"
    else:
        embed.description = f"❌ 購入失敗\n{result.get('message', '')}"

    return embed


def portfolio_embed(portfolio: dict, holdings: list, valuations: dict) -> discord.Embed:
    """ポートフォリオ一覧のEmbed"""
    cash = portfolio["cash_jpy"]
    total_market_value = sum(v["market_value_jpy"] for v in valuations.values())
    total_gain_loss = sum(v["gain_loss_jpy"] for v in valuations.values())
    total_value = cash + total_market_value

    gain_color = discord.Color.green() if total_gain_loss >= 0 else discord.Color.red()
    gain_emoji = "📈" if total_gain_loss >= 0 else "📉"

    embed = discord.Embed(
        title="💼 ポートフォリオ",
        color=gain_color,
        timestamp=datetime.utcnow()
    )

    embed.add_field(name="💴 現金残高", value=f"{cash:,.0f}円", inline=True)
    embed.add_field(name="📊 株式評価額", value=f"{total_market_value:,.0f}円", inline=True)
    embed.add_field(name="🏦 総資産", value=f"{total_value:,.0f}円", inline=True)
    embed.add_field(
        name=f"{gain_emoji} 評価損益",
        value=f"{'+' if total_gain_loss >= 0 else ''}{total_gain_loss:,.0f}円",
        inline=True
    )

    if holdings:
        holdings_text = ""
        for h in holdings:
            v = valuations.get(h["ticker"], {})
            gain = v.get("gain_loss_jpy", 0)
            pct = v.get("gain_loss_pct", 0)
            sign = "+" if gain >= 0 else ""
            emoji = "🟢" if gain >= 0 else "🔴"
            holdings_text += (
                f"{emoji} **{h['company_name']}** ({h['ticker']})\n"
                f"　{h['shares']:.2f}株 @ {v.get('current_price_jpy', h['avg_cost_jpy']):,.0f}円 "
                f"| {sign}{gain:,.0f}円 ({sign}{pct:.1f}%)\n"
            )
        embed.add_field(name="📋 保有銘柄", value=holdings_text or "なし", inline=False)
    else:
        embed.add_field(name="📋 保有銘柄", value="現在保有している銘柄はありません", inline=False)

    return embed


def history_embed(trades: list) -> discord.Embed:
    """トレード履歴のEmbed"""
    embed = discord.Embed(
        title="📜 トレード履歴 (直近10件)",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    if not trades:
        embed.description = "トレード履歴がありません"
        return embed

    for t in trades:
        action_emoji = "🟢" if t["trade_type"] == "BUY" else "🔴"
        auto_tag = "🤖" if t["is_auto"] else "👤"
        embed.add_field(
            name=f"{action_emoji} {t['company_name']} ({t['ticker']}) {auto_tag}",
            value=(
                f"{t['trade_type']} {t['shares']:.2f}株 @ {t['price_jpy']:,.0f}円\n"
                f"合計: {t['amount_jpy']:,.0f}円 | {t['executed_at'][:10]}"
            ),
            inline=False
        )

    return embed
