"""
embeds.py - Discordの見やすいEmbedメッセージを生成する
"""
import discord
from datetime import datetime
from typing import Optional


def trade_result_embed(trade_data: dict, is_auto: bool = True) -> discord.Embed:
    """トレード実行結果のEmbed（BUY/SELL両対応）"""
    summary = trade_data.get("summary", "")
    results = trade_data.get("results", [])

    success_count = sum(1 for r in results if r.get("trade_result", {}).get("success"))
    fail_count    = len(results) - success_count

    color = discord.Color.green() if success_count > 0 else discord.Color.red()
    title = "🤖 AI自動トレード実行" if is_auto else "📈 手動トレード実行"

    embed = discord.Embed(
        title=title,
        description=f"**本日の市場概況**\n{summary}" if summary else "",
        color=color,
        timestamp=datetime.utcnow()
    )

    if not results:
        embed.add_field(name="判断結果", value="本日はトレードなし（全銘柄HOLD）", inline=False)
        embed.set_footer(text="成功: 0件 / 失敗: 0件")
        return embed

    for r in results:
        action       = r.get("action", "BUY").upper()
        trade_result = r.get("trade_result", {})
        details      = trade_result.get("details", {})
        ticker       = r.get("ticker", "?")
        company      = r.get("company_name", ticker)
        reason       = r.get("reason", "")

        if action == "SELL":
            if trade_result.get("success"):
                gl   = details.get("gain_loss_jpy", 0)
                glp  = details.get("gain_loss_pct", 0)
                sign = "+" if gl >= 0 else ""
                field_value = (
                    f"🔴 **売却成功**\n"
                    f"売却単価: {details.get('price_jpy', 0):,.0f}円\n"
                    f"売却株数: {details.get('shares', 0):.2f}株\n"
                    f"売却金額: {details.get('amount_jpy', 0):,.0f}円\n"
                    f"損益: {sign}{gl:,.0f}円 ({sign}{glp:.2f}%)\n"
                    f"理由: {reason}"
                )
            else:
                field_value = (
                    f"❌ **売却失敗**\n"
                    f"{trade_result.get('message', '不明なエラー')}\n"
                    f"理由: {reason}"
                )
            embed.add_field(name=f"📉 {company} ({ticker})", value=field_value, inline=False)

        else:  # BUY
            if trade_result.get("success"):
                field_value = (
                    f"🟢 **購入成功**\n"
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
            embed.add_field(name=f"📈 {company} ({ticker})", value=field_value, inline=False)

    embed.set_footer(text=f"成功: {success_count}件 / 失敗: {fail_count}件")
    return embed


def sell_result_embed(result: dict) -> discord.Embed:
    """売却結果のEmbed"""
    success = result.get("success", False)
    details = result.get("details", {})

    embed = discord.Embed(
        title="💴 売却結果",
        color=discord.Color.green() if success else discord.Color.red(),
        timestamp=datetime.utcnow()
    )

    if success:
        gl     = details.get("gain_loss_jpy", 0)
        gl_pct = details.get("gain_loss_pct", 0)
        sign   = "+" if gl >= 0 else ""
        gl_color_text = "📈 利益" if gl >= 0 else "📉 損失"

        embed.description = "✅ 売却が完了しました"
        embed.add_field(name="銘柄",   value=f"{details.get('company_name')} ({details.get('ticker')})", inline=True)
        embed.add_field(name="売却単価", value=f"{details.get('price_jpy', 0):,.0f}円", inline=True)
        embed.add_field(name="売却株数", value=f"{details.get('shares', 0):.2f}株", inline=True)
        embed.add_field(name="売却金額", value=f"{details.get('amount_jpy', 0):,.0f}円", inline=True)
        embed.add_field(
            name=gl_color_text,
            value=f"{sign}{gl:,.0f}円 ({sign}{gl_pct:.2f}%)",
            inline=True
        )
    else:
        embed.description = f"❌ 売却失敗\n{result.get('message', '')}"

    return embed


def portfolio_summary_embed(snapshot: dict) -> discord.Embed:
    """
    自動トレード後などに添付するコンパクトなポートフォリオ概要 Embed。
    円グラフ画像は別途 discord.File として添付する。
    """
    cash               = snapshot["cash"]
    total_market_value = snapshot["total_market_value"]
    total_gain_loss    = snapshot["total_gain_loss"]
    total_value        = snapshot["total_value"]
    initial_balance    = snapshot.get("initial_balance", total_value)
    holdings           = snapshot["holdings"]
    valuations         = snapshot["valuations"]

    overall_pct = ((total_value - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0
    gain_color  = discord.Color.green() if total_gain_loss >= 0 else discord.Color.red()
    gain_sign   = "+" if total_gain_loss >= 0 else ""
    gain_emoji  = "📈" if total_gain_loss >= 0 else "📉"

    embed = discord.Embed(
        title="💼 ポートフォリオ",
        color=gain_color,
        timestamp=datetime.utcnow()
    )

    # サマリー行
    embed.add_field(name="🏦 総資産",    value=f"{total_value:,.0f}円",          inline=True)
    embed.add_field(name="💴 現金",      value=f"{cash:,.0f}円",                 inline=True)
    embed.add_field(name="📊 株式評価額", value=f"{total_market_value:,.0f}円",   inline=True)
    embed.add_field(
        name=f"{gain_emoji} 評価損益",
        value=f"{gain_sign}{total_gain_loss:,.0f}円\n({gain_sign}{overall_pct:.2f}%)",
        inline=True
    )

    # 保有銘柄を1フィールドにまとめてコンパクトに
    if holdings:
        lines = []
        for h in holdings:
            v    = valuations.get(h["ticker"], {})
            gl   = v.get("gain_loss_jpy", 0)
            glp  = v.get("gain_loss_pct", 0)
            mv   = v.get("market_value_jpy", h["avg_cost_jpy"] * h["shares"])
            pct  = (mv / total_value * 100) if total_value > 0 else 0
            s    = "+" if gl >= 0 else ""
            e    = "🟢" if gl >= 0 else "🔴"
            lines.append(
                f"{e} **{h['company_name']}** `{h['ticker']}`\n"
                f"　{h['shares']:.2f}株 | {mv:,.0f}円 ({pct:.1f}%) | {s}{gl:,.0f}円 ({s}{glp:.1f}%)"
            )
        # 文字数制限(1024)を考慮して分割
        chunk, chunks = "", []
        for line in lines:
            if len(chunk) + len(line) + 1 > 1000:
                chunks.append(chunk)
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk:
            chunks.append(chunk)

        for i, c in enumerate(chunks):
            embed.add_field(
                name="📋 保有銘柄" if i == 0 else "📋 保有銘柄 (続き)",
                value=c,
                inline=False
            )
    else:
        embed.add_field(name="📋 保有銘柄", value="現在保有している銘柄はありません", inline=False)

    # 円グラフを添付するのでimage参照を設定
    embed.set_image(url="attachment://portfolio.png")

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
